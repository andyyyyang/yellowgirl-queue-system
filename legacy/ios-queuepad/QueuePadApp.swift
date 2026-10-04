import SwiftUI
import Combine
import ActivityKit
import UIKit

struct LiveTestAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var count: Int
    }

    var title: String
}

// MARK: - 遠端資料控制 ViewModel（含模擬模式）
@MainActor
class RemoteQueueVM: ObservableObject {
    @Published var current: Int?
    @Published var waiting: [Int] = []
    @Published var missed: [Int] = []
    
    private var timer: Timer?
    private let isMockMode = false
    private let serverURL = URL(string: "https://aad1bd16a15a.ngrok-free.app")!
    // https://ticket-server-246181962314.asia-east1.run.app
    init() {
        if isMockMode {
            setupMockData()
        } else {
            Task { await self.fetchStatus() }
        }
        
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            if self.isMockMode {
                self.advanceMockStatus()
            } else {
                Task { await self.fetchStatus() }
            }
        }

        startLiveActivity()
    }
    
    private func setupMockData() {
        self.current = 1
        self.waiting = [2, 3, 4, 5]
        self.missed = []
    }
    
    private func advanceMockStatus() {
        if let cur = current {
            missed.append(cur)
        }
        current = waiting.isEmpty ? nil : waiting.removeFirst()
        if let last = (waiting + [current ?? 0]).max() {
            waiting.append(last + 1)
        }
        updateLiveActivity(to: current ?? 0)
    }
    
    func deleteMissedFromServer(_ number: Int) async {
        guard let url = URL(string: "/missed/\(number)", relativeTo: serverURL) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode != 204 {
                print("⚠️ 刪除失敗，狀態碼：\(httpResponse.statusCode)")
            }
        } catch {
            print("❌ 刪除錯誤：\(error)")
        }
    }

    func takeTicket() {
        if isMockMode {
            let newNumber = (waiting + [current ?? 0]).max() ?? 0
            let nextNumber = newNumber + 1
            waiting.append(nextNumber)
            triggerPrint(for: nextNumber, service: "內用")  // 自動印刷
        } else {
            // 先預測號碼（本地沒拿到伺服器回傳，但我們用 next_no 推估）
            let predictedNumber = (waiting + [current ?? 0]).max() ?? 0 + 1
            triggerPrint(for: predictedNumber, service: "內用")  // 印刷

            sendCommand(endpoint: "take")  // 實際跟伺服器說已取號
        }

        updateLiveActivity(to: current ?? 0)
    }
    
    func triggerPrint(for number: Int, service: String = "內用") {
        guard let url = URL(string: "http://192.168.0.151:8080/print") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: Any] = [
            "ticketNumber": number,
            "service": service,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            URLSession.shared.dataTask(with: request).resume()
        } catch {
            print("❌ Failed to encode print payload:", error)
        }
    }

    
    func callNext() {
        if isMockMode {
            if let cur = current {
                missed.append(cur)
            }
            current = waiting.isEmpty ? nil : waiting.removeFirst()
            updateLiveActivity(to: current ?? 0)
        } else {
            sendCommand(endpoint: "next")
        }
    }

    func markMissed() {
        if isMockMode {
            if let cur = current {
                missed.append(cur)
                current = waiting.isEmpty ? nil : waiting.removeFirst()
            }
            updateLiveActivity(to: current ?? 0)
        } else {
            sendCommand(endpoint: "miss")
        }
    }

    func eta(for index: Int) -> Int {
        switch waiting.count {
        case 0...5: return (index + 1) * 1
        case 6...10: return (index + 1) * 2
        default: return (index + 1) * 3
        }
    }

    func fetchStatus() async {
        guard let url = URL(string: "/status", relativeTo: serverURL) else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode(StatusPayload.self, from: data)
            self.current = decoded.current
            self.waiting = decoded.waiting
            self.missed = decoded.missed
            updateLiveActivity(to: current ?? 0)
        } catch {
            print("❌ Failed to fetch status:", error)
        }
    }

    func sendCommand(endpoint: String) {
        guard let url = URL(string: "/\(endpoint)", relativeTo: serverURL) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request).resume()
    }

    func startLiveActivity() {
        Task {
            // 結束舊的
            for activity in Activity<LiveTestAttributes>.activities {
                await activity.end(dismissalPolicy: .immediate)
            }

            let attr = LiveTestAttributes(title: "QueuePad")
            let state = LiveTestAttributes.ContentState(count: current ?? 0)

            do {
                _ = try Activity<LiveTestAttributes>.request(
                    attributes: attr,
                    contentState: state
                    )
                print("✅ Live Activity 啟動成功")
            } catch {
                print("❌ 無法啟動 Live Activity：\(error.localizedDescription)")
            }
        }
    }

    func updateLiveActivity(to number: Int) {
        Task {
            let newState = LiveTestAttributes.ContentState(count: number)
            for activity in Activity<LiveTestAttributes>.activities {
                await activity.update(using: newState)
            }
        }
    }


    func endLiveActivity() {
        Task {
            for activity in Activity<LiveTestAttributes>.activities {
                await activity.end(dismissalPolicy: .immediate)
            }
        }
    }

    struct StatusPayload: Codable {
        let current: Int?
        let waiting: [Int]
        let missed: [Int]
    }
}

// MARK: - 主畫面 View
struct MainQueueView: View {
    @EnvironmentObject private var vm: RemoteQueueVM
    @State private var navPath = NavigationPath()
    @State private var takeSymbolTrigger = false
    @State private var nextSymbolTrigger = false
    @State private var missSymbolTrigger = false

    var body: some View {
        NavigationStack(path: $navPath) {
            VStack(spacing: 10) {
                header
                waitingGrid
                controls
            }
            .padding()
            .navigationTitle("QueuePad")
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button {
                        vm.startLiveActivity()
                    } label: {
                        Label("重啟", systemImage: "bolt.circle")
                    }

                    Button("過號") {
                        navPath.append("missed")
                    }
                }
            }
            .navigationDestination(for: String.self) { _ in
                MissedView().environmentObject(vm)
            }
            .gesture(
                DragGesture()
                    .onEnded { value in
                        if value.translation.width < -100 {
                            navPath.append("missed")
                        }
                    }
            )
        }
    }

    private var header: some View {
        VStack(spacing: 6) {
            if let cur = vm.current {
                Text(String(format: "%03d", cur))
                    .font(.system(size: 100, weight: .bold, design: .monospaced))
            } else {
                ContentUnavailableView("尚未叫號", systemImage: "person.3")
            }
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var waitingGrid: some View {
        ScrollView {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 12) {
                ForEach(Array(vm.waiting.enumerated()), id: \.1) { idx, number in
                    VStack(spacing: 4) {
                        Text(String(format: "%03d", number))
                            .font(.title3.bold())
                        Text("等候時間 \(vm.eta(for: idx)) 分")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 70)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private var controls: some View {
        HStack(spacing: 10) {
            Button {
                withAnimation { vm.takeTicket(); takeSymbolTrigger.toggle() }
            } label: {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 48))
                    .symbolEffect(.bounce, value: takeSymbolTrigger)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            Button {
                withAnimation { vm.callNext(); nextSymbolTrigger.toggle() }
            } label: {
                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: 48))
                    .symbolEffect(.bounce, value: nextSymbolTrigger)
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)
            .controlSize(.large)
            .disabled(vm.waiting.isEmpty && vm.current == nil)

            Button {
                withAnimation { vm.markMissed(); missSymbolTrigger.toggle() }
            } label: {
                Image(systemName: "arrow.uturn.left.circle.fill")
                    .font(.system(size: 35))
                    .symbolEffect(.pulse, value: missSymbolTrigger)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
            .disabled(vm.current == nil)
        }
    }
}

// MARK: - 過號清單 View
struct MissedView: View {
    @EnvironmentObject var vm: RemoteQueueVM

    var body: some View {
        if vm.missed.isEmpty {
            ContentUnavailableView("沒有過號", systemImage: "checkmark")
                .navigationTitle("過號清單")
        } else {
            List {
                ForEach(vm.missed, id: \.self) { t in
                    Text(String(format: "%03d", t))
                        .bold()
                }
                .onDelete(perform: deleteMissed)
            }
            .navigationTitle("過號清單")
        }
    }

    private func deleteMissed(at offsets: IndexSet) {
        for index in offsets {
            let numberToDelete = vm.missed[index]
            Task {
                await vm.deleteMissedFromServer(numberToDelete)
            }
        }
        vm.missed.remove(atOffsets: offsets)
    }
}

// MARK: - App 進入點，處理 Deep Link
@main
struct QueuePadApp: App {
    @StateObject private var vm = RemoteQueueVM()

    var body: some Scene {
        WindowGroup {
            MainQueueView()
                .environmentObject(vm)
                .onOpenURL { url in
                    handleDeepLink(url)
                }
        }
    }

    private func handleDeepLink(_ url: URL) {
        switch url.host {
        case "next":
            vm.callNext()
        case "miss":
            vm.markMissed()
        default:
            break
        }
    }
}
