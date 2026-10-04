import SwiftUI
import Combine
import UIKit
import WebKit

// MARK: - 共用 Glass 風格輔助
private extension View {
    func glassBackground(cornerRadius: CGFloat = 20, material: Material = .ultraThinMaterial) -> some View {
        self
            .background(material, in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .strokeBorder(
                        LinearGradient(colors: [
                            .white.opacity(0.50),
                            .white.opacity(0.20),
                            .clear
                        ], startPoint: .topLeading, endPoint: .bottomTrailing),
                        lineWidth: 1
                    )
                    .blendMode(.overlay)
            )
            .shadow(color: .black.opacity(0.15), radius: 18, x: 0, y: 10)
    }

    func glassButtonStyle(tint: Color) -> some View {
        self
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(.ultraThinMaterial, in: Capsule(style: .continuous))
            .overlay(
                Capsule(style: .continuous)
                    .strokeBorder(tint.opacity(0.45), lineWidth: 1.2)
                    .shadow(color: tint.opacity(0.35), radius: 6, x: 0, y: 4)
            )
    }

    func glassCardPadding() -> some View {
        self.padding(12)
    }
}

// MARK: - 漂浮 Liquid Glass 圓形按鈕樣式（可設定主色）
struct GlassIconButtonStyle: ButtonStyle {
    var size: CGFloat = 68
    var tint: Color = .yellow

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: size * 0.44, weight: .semibold))
            .foregroundStyle(tint)
            .frame(width: size, height: size)
            .background(.ultraThinMaterial, in: Circle())
            .overlay(
                Circle()
                    .strokeBorder(
                        LinearGradient(colors: [
                            Color.white.opacity(0.65),
                            tint.opacity(0.45),
                            .clear
                        ], startPoint: .topLeading, endPoint: .bottomTrailing),
                        lineWidth: 0.8
                    )
                    .blendMode(.overlay)
            )
            .scaleEffect(configuration.isPressed ? 0.94 : 1.0)
            .animation(.spring(response: 0.25, dampingFraction: 0.8), value: configuration.isPressed)
    }
}

// MARK: - 黃色底 + 白色符號的圓形按鈕樣式（更適合淺色模式）
struct FilledIconButtonStyle: ButtonStyle {
    var size: CGFloat = 74
    var tint: Color = .yellow

    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        // 更明顯的按壓縮放
        let pressedScale: CGFloat = configuration.isPressed ? 0.88 : 1.0
        let disabledScale: CGFloat = isEnabled ? 1.0 : 0.94
        let disabledOpacity: Double = isEnabled ? 1.0 : 0.45
        let shadowOpacity: Double = isEnabled ? 0.45 : 0.15

        return configuration.label
            .font(.system(size: size * 0.44, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(
                Circle()
                    .fill(tint.gradient)
            )
            .overlay(
                Circle()
                    .strokeBorder(Color.white.opacity(0.25), lineWidth: 1)
            )
            .shadow(color: tint.opacity(shadowOpacity), radius: 10, x: 0, y: 6)
            .opacity(disabledOpacity)
            .scaleEffect(pressedScale * disabledScale)
            // 按壓彈動
            .animation(.spring(response: 0.22, dampingFraction: 0.65), value: configuration.isPressed)
            // 禁用/啟用過渡
            .animation(.easeInOut(duration: 0.2), value: isEnabled)
    }
}

struct EmbeddedWebView: UIViewRepresentable {
    let url: URL
    
    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: EmbeddedWebView
        init(parent: EmbeddedWebView) { self.parent = parent }
        
        func webView(_ webView: WKWebView,
                     runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping () -> Void) {
            print("JS Alert: \(message)")
            completionHandler()
        }

        func webView(_ webView: WKWebView,
                     runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (Bool) -> Void) {
            print("JS Confirm: \(message)")
            completionHandler(true)
        }

        func webView(_ webView: WKWebView,
                     createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction,
                     windowFeatures: WKWindowFeatures) -> WKWebView? {
            webView.load(navigationAction.request)
            return nil
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }
    
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        if #available(iOS 14.0, *) {
            let pagePreferences = WKWebpagePreferences()
            pagePreferences.allowsContentJavaScript = true
            config.defaultWebpagePreferences = pagePreferences
        } else {
            config.preferences.javaScriptEnabled = true
        }

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.backgroundColor = .systemBackground
        webView.isOpaque = true
        webView.load(URLRequest(url: url))
        return webView
    }
    
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

struct PiWebView: View {
    @Environment(\.dismiss) private var dismiss
    let url: URL
    
    var body: some View {
        NavigationView {
            EmbeddedWebView(url: url)
                .navigationBarTitle("外接裝置設定", displayMode: .inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: { dismiss() }) {
                            Image(systemName: "xmark")
                        }
                    }
                }
        }
    }
}

// MARK: - 遠端資料控制 ViewModel（含模擬模式）
@MainActor
class RemoteQueueVM: ObservableObject {
    @Published var current: Int?
    @Published var waiting: [Int] = []
    @Published var missed: [Int] = []
    // 伺服器同步的標注集合
    @Published var marked: Set<Int> = []
    
    // 用於整卡片一致動畫的快照與旗標
    @Published var lastWaitingSnapshot: [Int] = []
    @Published var isAnimatingChange: Bool = false
    
    @AppStorage("serverURLString") private var serverURLString: String = "https://yellowgirl.up.railway.app"
    
    private var pollingTask: Task<Void, Never>?
    private let isMockMode = false
    
    private var serverURL: URL? {
        URL(string: serverURLString)
    }
    
    init() {
        if isMockMode {
            setupMockData()
        } else {
            Task {
                await self.fetchStatus()
                self.lastWaitingSnapshot = self.waiting
            }
        }
        
        startPolling()
    }
    
    deinit {
        pollingTask?.cancel()
    }
    
    private func startPolling() {
        pollingTask?.cancel()
        pollingTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                if self.isMockMode {
                    await MainActor.run { self.advanceMockStatus() }
                } else {
                    await self.fetchStatus()
                    // 伺服器同步後更新快照（非本地動作，不觸發動畫旗標）
                    self.lastWaitingSnapshot = self.waiting
                }
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }
    
    private func setupMockData() {
        self.current = 1
        self.waiting = [2, 3, 4, 5]
        self.missed = []
        self.marked = []
        self.lastWaitingSnapshot = self.waiting
    }
    
    private func advanceMockStatus() {
        if let cur = current {
            missed.append(cur)
        }
        current = waiting.isEmpty ? nil : waiting.removeFirst()
        if let last = (waiting + [current ?? 0]).max() {
            waiting.append(last + 1)
        }
        lastWaitingSnapshot = waiting
    }
    
    func deleteMissedFromServer(_ number: Int) async {
        guard let serverURL, let url = URL(string: "/missed/\(number)", relativeTo: serverURL) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.timeoutInterval = 5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode != 204 {
                print("⚠️ 刪除失敗，狀態碼：\(httpResponse.statusCode)")
            }
        } catch {
            print("❌ 刪除錯誤：\(error)")
        }
    }

    // MARK: 更絲滑：樂觀更新 + 同步驗證（帶快照，動畫期間凍結等候時間）
    private struct Snapshot {
        var current: Int?
        var waiting: [Int]
        var missed: [Int]
        var marked: Set<Int>
    }
    
    private func performOptimisticUpdate(
        mutate: () -> Void,
        serverAction: @escaping () async throws -> Void
    ) {
        let snapshot = Snapshot(current: current, waiting: waiting, missed: missed, marked: marked)
        // 記錄快照並開啟動畫旗標，凍結等候時間顯示
        lastWaitingSnapshot = waiting
        isAnimatingChange = true
        
        // 立即更新本地，帶來“很跟手”的體感
        mutate()
        
        Task {
            do {
                try await serverAction()
                // 與伺服器狀態對齊
                await fetchStatus()
                // 動畫時間到後再解除凍結
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.30) {
                    self.lastWaitingSnapshot = self.waiting
                    self.isAnimatingChange = false
                }
            } catch {
                // 失敗即還原
                print("❌ 同步失敗，還原本地：\(error)")
                current = snapshot.current
                waiting = snapshot.waiting
                missed = snapshot.missed
                marked = snapshot.marked
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.30) {
                    self.lastWaitingSnapshot = self.waiting
                    self.isAnimatingChange = false
                }
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
        }
    }

    func takeTicket() {
        if isMockMode {
            let newNumber = (waiting + [current ?? 0]).max() ?? 0
            let nextNumber = newNumber + 1
            waiting.append(nextNumber)
            lastWaitingSnapshot = waiting
        } else {
            performOptimisticUpdate(mutate: { [current, waiting] in
                let newNumber = (waiting + [current ?? 0]).max() ?? 0
                let nextNumber = newNumber + 1
                self.waiting.append(nextNumber)
            }, serverAction: {
                try await self.sendCommand(endpoint: "take")
            })
        }
    }
    
    func takeMultiple(_ count: Int) {
        guard count > 0 else { return }
        Task {
            for _ in 0..<count {
                self.takeTicket()
                try? await Task.sleep(nanoseconds: 80_000_000)
            }
        }
    }
    
    func callNext() {
        if isMockMode {
            if let cur = current {
                missed.append(cur)
            }
            current = waiting.isEmpty ? nil : waiting.removeFirst()
            lastWaitingSnapshot = waiting
        } else {
            performOptimisticUpdate(mutate: {
                if let cur = self.current {
                    self.missed.append(cur)
                }
                self.current = self.waiting.isEmpty ? nil : self.waiting.removeFirst()
            }, serverAction: {
                try await self.sendCommand(endpoint: "next")
            })
        }
    }

    func markMissed() {
        if isMockMode {
            if let cur = current {
                missed.append(cur)
                current = waiting.isEmpty ? nil : waiting.removeFirst()
            }
            lastWaitingSnapshot = waiting
        } else {
            performOptimisticUpdate(mutate: {
                if let cur = self.current {
                    self.missed.append(cur)
                }
                self.current = self.waiting.isEmpty ? nil : self.waiting.removeFirst()
            }, serverAction: {
                try await self.sendCommand(endpoint: "miss")
            })
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
        guard let serverURL, let url = URL(string: "/status", relativeTo: serverURL) else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode(StatusPayload.self, from: data)
            self.current = decoded.current
            self.waiting = decoded.waiting
            self.missed = decoded.missed
            self.marked = Set(decoded.marked ?? [])
        } catch {
            print("❌ Failed to fetch status:", error)
        }
    }

    @discardableResult
    private func sendCommand(endpoint: String) async throws -> StatusPayload? {
        guard let serverURL, let url = URL(string: "/\(endpoint)", relativeTo: serverURL) else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let code = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw NSError(domain: "QueuePad", code: code, userInfo: [NSLocalizedDescriptionKey: "HTTP \(code)"])
        }
        if !data.isEmpty {
            if let payload = try? JSONDecoder().decode(StatusPayload.self, from: data) {
                self.current = payload.current
                self.waiting = payload.waiting
                self.missed = payload.missed
                self.marked = Set(payload.marked ?? [])
                return payload
            }
        }
        return nil
    }

    func testConnection() async -> Bool {
        guard let serverURL, let url = URL(string: "/status", relativeTo: serverURL) else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                return true
            }
        } catch {
            return false
        }
        return false
    }

    struct StatusPayload: Codable {
        let current: Int?
        let marked: [Int]?
        let missed: [Int]
        let next_no: Int?
        let waiting: [Int]
    }
}

struct SettingsView: View {
    @AppStorage("serverURLString") private var serverURLString: String = "https://yellowgirl.up.railway.app"
    
    @AppStorage("cooldownTake") private var cooldownTake: Double = 2.0
    @AppStorage("cooldownNext") private var cooldownNext: Double = 2.0
    @AppStorage("cooldownMiss") private var cooldownMiss: Double = 2.0
    
    @EnvironmentObject private var vm: RemoteQueueVM
    @State private var connectionStatus: String?
    @State private var actionStatus: String?
    @State private var showPiWeb = false

    var body: some View {
        Form {
            Section {
                TextField("輸入伺服器網址", text: $serverURLString)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
            } header: {
                Text("伺服器設定")
            }
            
            Section {
                Button("測試連線") {
                    Task {
                        let ok = await vm.testConnection()
                        connectionStatus = ok ? "✅ 連線成功" : "❌ 連線失敗"
                    }
                }
                if let connectionStatus {
                    Text(connectionStatus)
                        .foregroundColor(connectionStatus.contains("成功") ? .green : .red)
                }
            }
            
            Section {
                VStack(alignment: .leading) {
                    Text("取號：\(String(format: "%.1f", cooldownTake)) 秒")
                    Slider(value: $cooldownTake, in: 0...10, step: 0.1)
                }
                VStack(alignment: .leading) {
                    Text("下一位：\(String(format: "%.1f", cooldownNext)) 秒")
                    Slider(value: $cooldownNext, in: 0...10, step: 0.1)
                }
                VStack(alignment: .leading) {
                    Text("過號：\(String(format: "%.1f", cooldownMiss)) 秒")
                    Slider(value: $cooldownMiss, in: 0...10, step: 0.1)
                }
            } header: {
                Text("動作緩衝秒數")
            }
            
            Section {
                Button("🌐 打開設定頁") {
                    showPiWeb = true
                }
            } header: {
                Text("外接裝置設定")
            }
            
            Section {
                Button("🔄 手動歸零") {
                    Task {
                        let ok = await vm.resetQueue()
                        actionStatus = ok ? "✅ 已手動歸零" : "❌ 歸零失敗"
                    }
                }
                .tint(.red)

                Button("⬅️ 返回前一號") {
                    Task {
                        let ok = await vm.goPrevious()
                        actionStatus = ok ? "✅ 已返回前一號" : "❌ 返回失敗"
                    }
                }
                .tint(.blue)

                if let actionStatus {
                    Text(actionStatus)
                        .foregroundColor(actionStatus.contains("✅") ? .green : .red)
                }
            } header: {
                Text("伺服器操作")
            }
        }
        .navigationTitle("設定")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showPiWeb) {
            PiWebView(url: URL(string: "http://queuepad-pi.local:8000/ads?pw=yellowgirl")!)
        }
    }
}

// MARK: - 主畫面 View
struct MainQueueView: View {
    @EnvironmentObject private var vm: RemoteQueueVM
    @State private var navPath = NavigationPath()
    @State private var takeSymbolTrigger = false
    @State private var nextSymbolTrigger = false
    @State private var missSymbolTrigger = false
    
    // 三個 cooldown 狀態
    @State private var isTakeCooling = false
    @State private var isNextCooling = false
    @State private var isMissCooling = false
    
    @AppStorage("cooldownTake") private var cooldownTake: Double = 2.0
    @AppStorage("cooldownNext") private var cooldownNext: Double = 2.0
    @AppStorage("cooldownMiss") private var cooldownMiss: Double = 2.0

    @State private var showBulkTakeSheet = false
    @State private var bulkCount: Int = 5

    // 每個按鈕的彈動狀態
    @State private var takeBouncing = false
    @State private var nextBouncing = false
    @State private var missBouncing = false

    var body: some View {
        NavigationStack(path: $navPath) {
            VStack(spacing: 12) {
                header
                    .padding(.top, 8)

                waitingGrid
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.horizontal, 12)
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        navPath.append("settings")
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 8) {
                        Image("Asset 3")
                            .resizable()
                            .scaledToFit()
                            .frame(height: 28)
                            .shadow(color: .black.opacity(0.25), radius: 6, x: 0, y: 3)
                    }
                }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button("過號") {
                        navPath.append("missed")
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: String.self) { route in
                switch route {
                case "missed":
                    MissedView().environmentObject(vm)
                case "settings":
                    SettingsView().environmentObject(vm)
                default:
                    EmptyView()
                }
            }
            .gesture(
                DragGesture()
                    .onEnded { value in
                        if value.translation.width < -100 {
                            navPath.append("missed")
                        }
                    }
            )
            .sheet(isPresented: $showBulkTakeSheet) {
                NavigationView {
                    Form {
                        Section(header: Text("一次生成張數")) {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("張數")
                                    Spacer()
                                    Text("\(bulkCount) 張").bold()
                                }
                                Slider(value: Binding(
                                    get: { Double(bulkCount) },
                                    set: { bulkCount = Int($0.rounded()) }
                                ), in: 1...20, step: 1)
                                Stepper("調整張數", value: $bulkCount, in: 1...20)
                            }
                        }
                    }
                    .navigationTitle("批量取號")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("取消") { showBulkTakeSheet = false }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("生成 \(bulkCount) 張") {
                                vm.takeMultiple(bulkCount)
                                takeSymbolTrigger.toggle()
                                showBulkTakeSheet = false
                            }
                            .bold()
                        }
                    }
                }
            }
            // 底部控制按鈕
            .safeAreaInset(edge: .bottom, spacing: 0) {
                HStack(spacing: 18) {
                    // 取號（黃色）
                    Button {
                        handleAction(bounce: $takeBouncing, isCooling: $isTakeCooling, cooldown: cooldownTake) {
                            vm.takeTicket()
                            takeSymbolTrigger.toggle()
                        }
                    } label: {
                        Image(systemName: "plus")
                    }
                    .buttonStyle(FilledIconButtonStyle(size: 74, tint: .yellow))
                    .scaleEffect(takeBouncing ? 0.86 : 1.0)
                    .animation(.spring(response: 0.28, dampingFraction: 0.55), value: takeBouncing)
                    .contextMenu {
                        Button {
                            showBulkTakeSheet = true
                        } label: {
                            Label("批量取號…", systemImage: "square.stack.3d.up.fill")
                        }
                    }
                    .disabled(isTakeCooling)

                    // 下一位（咖色）
                    Button {
                        handleAction(bounce: $nextBouncing, isCooling: $isNextCooling, cooldown: cooldownNext) {
                            vm.callNext()
                            nextSymbolTrigger.toggle()
                        }
                    } label: {
                        Image(systemName: "arrow.right")
                    }
                    .buttonStyle(FilledIconButtonStyle(size: 74, tint: .brown))
                    .scaleEffect(nextBouncing ? 0.86 : 1.0)
                    .animation(.spring(response: 0.28, dampingFraction: 0.55), value: nextBouncing)
                    .disabled(isNextCooling || (vm.waiting.isEmpty && vm.current == nil))

                    // 過號（黃色）
                    Button {
                        handleAction(bounce: $missBouncing, isCooling: $isMissCooling, cooldown: cooldownMiss) {
                            vm.markMissed()
                            missSymbolTrigger.toggle()
                        }
                    } label: {
                        Image(systemName: "arrow.uturn.left")
                    }
                    .buttonStyle(FilledIconButtonStyle(size: 74, tint: .yellow))
                    .scaleEffect(missBouncing ? 0.86 : 1.0)
                    .animation(.spring(response: 0.28, dampingFraction: 0.55), value: missBouncing)
                    .disabled(isMissCooling || vm.current == nil)
                }
                .padding(.vertical, 12)
                .background(Color.systemGroupedBackground.opacity(0.001)) // 保持點擊透傳且在淺色有適度分層
            }
            .background(Color.systemGroupedBackground) // 淺色模式更一致
        }
    }

    // MARK: Header
    private var header: some View {
        VStack(spacing: 6) {
            if let cur = vm.current {
                let isMarked = vm.marked.contains(cur)
                Text(String(format: "%03d", cur))
                    .font(.system(size: 96, weight: .bold, design: .monospaced))
                    .foregroundStyle(.primary)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(isMarked ? Color.yellow.opacity(0.25) : .clear)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(isMarked ? Color.yellow.opacity(0.6) : .clear, lineWidth: isMarked ? 2 : 0)
                    )
                    .animation(.spring(response: 0.25, dampingFraction: 0.9), value: isMarked)
            } else {
                ContentUnavailableView("尚未叫號", systemImage: "person.3")
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }

    // MARK: Waiting Grid
    private var waitingGrid: some View {
        ScrollView {
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 110), spacing: 12)],
                spacing: 10
            ) {
                ForEach(Array(vm.waiting.enumerated()), id: \.1) { idx, number in
                    // 動畫期間使用快照的索引，讓卡片整體內容一起移動
                    let effectiveIndex: Int = {
                        if vm.isAnimatingChange,
                           let snapIndex = vm.lastWaitingSnapshot.firstIndex(of: number) {
                            return snapIndex
                        } else if let liveIndex = vm.waiting.firstIndex(of: number) {
                            return liveIndex
                        } else {
                            return idx
                        }
                    }()

                    let isMarked = vm.marked.contains(number)
                    VStack(spacing: 4) {
                        Text(String(format: "%03d", number))
                            .font(.headline.weight(.semibold))
                            .foregroundStyle(.primary)
                        Text("等候時間 \(vm.eta(for: effectiveIndex)) 分")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 56, alignment: .center)
                    .multilineTextAlignment(.center)
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(isMarked ? Color.yellow.opacity(0.25) : Color.secondarySystemGroupedBackground)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .stroke(isMarked ? Color.yellow.opacity(0.6) : .clear, lineWidth: isMarked ? 2 : 0)
                    )
                    .contentShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .onLongPressGesture(minimumDuration: 0.25) {
                        withAnimation(.spring(response: 0.25, dampingFraction: 0.9)) {
                            toggleMark(number)
                        }
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    }
                }
            }
            .padding(.horizontal, 4)
            .padding(.bottom, 6)
        }
        .background(Color.systemGroupedBackground)
    }

    private func toggleMark(_ number: Int) {
        let willMark = !vm.marked.contains(number)
        // 樂觀更新
        if willMark {
            vm.marked.insert(number)
        } else {
            vm.marked.remove(number)
        }
        Task {
            let ok: Bool
            if willMark {
                ok = await vm.mark(number: number)
            } else {
                ok = await vm.unmark(number: number)
            }
            if !ok {
                // 回滾
                await MainActor.run {
                    if willMark {
                        vm.marked.remove(number)
                    } else {
                        vm.marked.insert(number)
                    }
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
        }
    }

    // MARK: 防誤觸 Cooldown（先播完彈動，再進入禁用）
    private func handleAction(bounce: Binding<Bool>, isCooling: Binding<Bool>, cooldown: Double, action: () -> Void) {
        guard !isCooling.wrappedValue else { return }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
            action()
        }
        bounce.wrappedValue = true
        let bounceDuration: TimeInterval = 0.28
        DispatchQueue.main.asyncAfter(deadline: .now() + bounceDuration) {
            withAnimation(.spring(response: 0.28, dampingFraction: 0.55)) {
                bounce.wrappedValue = false
            }
            isCooling.wrappedValue = true
            DispatchQueue.main.asyncAfter(deadline: .now() + cooldown) {
                isCooling.wrappedValue = false
            }
        }
    }
}

// MARK: - 過號清單（支援多選勾選與右滑單刪）
struct MissedView: View {
    @EnvironmentObject var vm: RemoteQueueVM
    @State private var selection = Set<Int>()
    @State private var editMode: EditMode = .inactive

    private var isEditing: Bool { editMode == .active }

    var body: some View {
        VStack {
            if vm.missed.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.circle")
                        .font(.largeTitle)
                        .foregroundStyle(.secondary)
                    Text("沒有過號")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.systemGroupedBackground)
            } else {
                List(selection: $selection) {
                    ForEach(vm.missed, id: \.self) { t in
                        let isMarked = vm.marked.contains(t)
                        HStack {
                            Text(String(format: "%03d", t))
                                .bold()
                                .foregroundStyle(.primary)
                            if isMarked {
                                Spacer()
                                Text("未結帳")
                                    .font(.caption2.weight(.semibold))
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(
                                        Capsule(style: .continuous)
                                            .fill(Color.yellow.opacity(0.20))
                                    )
                                    .overlay(
                                        Capsule(style: .continuous)
                                            .stroke(Color.yellow.opacity(0.6), lineWidth: 1)
                                    )
                                    .foregroundStyle(.primary)
                            }
                        }
                        .listRowBackground(isMarked ? Color.yellow.opacity(0.15) : Color.clear)
                    }
                    .onDelete(perform: deleteAtOffsets)
                }
                .listStyle(.insetGrouped)
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        EditButton()
                    }
                    ToolbarItemGroup(placement: .bottomBar) {
                        if isEditing {
                            Button {
                                toggleSelectAll()
                            } label: {
                                Text(selectAllTitle())
                            }
                            .disabled(vm.missed.isEmpty)

                            Spacer()

                            Button(role: .destructive) {
                                deleteSelected()
                            } label: {
                                Text(selection.isEmpty ? "刪除" : "刪除已選 (\(selection.count))").bold()
                            }
                            .disabled(selection.isEmpty)
                        }
                    }
                }
            }
        }
        .navigationTitle("過號清單")
        .navigationBarTitleDisplayMode(.inline)
        .background(Color.systemGroupedBackground)
        .environment(\.editMode, $editMode)
        .onChange(of: editMode) { _, newValue in
            if newValue == .inactive {
                selection.removeAll()
            }
        }
    }

    private func selectAllTitle() -> String {
        selection.count == vm.missed.count ? "全不選" : "全選"
    }

    private func toggleSelectAll() {
        if selection.count == vm.missed.count {
            selection.removeAll()
        } else {
            selection = Set(vm.missed)
        }
    }

    private func deleteAtOffsets(_ offsets: IndexSet) {
        let numbers = offsets.compactMap { index in
            vm.missed.indices.contains(index) ? vm.missed[index] : nil
        }
        vm.missed.remove(atOffsets: offsets)
        Task {
            for n in numbers {
                await vm.deleteMissedFromServer(n)
            }
        }
        selection.subtract(numbers)
    }

    private func deleteSelected() {
        let toDelete = selection.sorted()
        Task {
            for number in toDelete {
                await vm.deleteMissedFromServer(number)
            }
        }
        vm.missed.removeAll { selection.contains($0) }
        selection.removeAll()
        editMode = .inactive
    }
}

// MARK: - iOS 系統色輔助
extension Color {
    static let systemGroupedBackground = Color(UIColor.systemGroupedBackground)
    static let secondarySystemGroupedBackground = Color(UIColor.secondarySystemGroupedBackground)
}

// MARK: - RemoteQueueVM 新增兩個 API 呼叫
extension RemoteQueueVM {
    func resetQueue() async -> Bool {
        guard let serverURL, let url = URL(string: "/reset", relativeTo: serverURL) else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                print("✅ 手動歸零成功")
                await fetchStatus()
                lastWaitingSnapshot = waiting
                return true
            }
        } catch {
            print("❌ 手動歸零失敗：\(error)")
        }
        return false
    }
    
    func goPrevious() async -> Bool {
        guard let serverURL, let url = URL(string: "/previous", relativeTo: serverURL) else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                print("✅ 返回前一號成功")
                await fetchStatus()
                lastWaitingSnapshot = waiting
                return true
            }
        } catch {
            print("❌ 返回前一號失敗：\(error)")
        }
        return false
    }

    // MARK: - 票號標注 API
    @discardableResult
    func mark(number: Int) async -> Bool {
        guard let serverURL, let url = URL(string: "/mark/\(number)", relativeTo: serverURL) else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                print("⚠️ 標注失敗：HTTP \(http.statusCode)")
                return false
            } else {
                print("✅ 已標注 \(number)")
                return true
            }
        } catch {
            print("❌ 標注錯誤：\(error)")
            return false
        }
    }
    
    @discardableResult
    func unmark(number: Int) async -> Bool {
        guard let serverURL, let url = URL(string: "/unmark/\(number)", relativeTo: serverURL) else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.timeoutInterval = 5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                print("⚠️ 取消標注失敗：HTTP \(http.statusCode)")
                return false
            } else {
                print("✅ 已取消標注 \(number)")
                return true
            }
        } catch {
            print("❌ 取消標注錯誤：\(error)")
            return false
        }
    }
}

// MARK: - App 進入點
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
