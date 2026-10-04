//
//  QueueManager.swift
//  QueuePad
//
//  Created by ANDY Yang on 2025/7/13.
//

import Foundation
import Combine     // ← 加這行
import Network


@MainActor
final class QueueManager: ObservableObject {
    static let shared = QueueManager()

    @Published private(set) var currentNumber = 0
    @Published private(set) var waitingList: [Int] = []

    private var listener: NWListener?
    private var connections: [NWConnection] = []

    private init() { startServer() }

    // ── 叫號邏輯 ───────────
    func addTicket() {
        let new = (waitingList.last ?? currentNumber) + 1
        waitingList.append(new);     broadcast()
    }
    func next()  { guard let n = waitingList.first else { return }
                   currentNumber = n; waitingList.removeFirst(); broadcast() }
    func reset() { currentNumber = 0; waitingList.removeAll();  broadcast() }

    // ── 區網 WebSocket / JSON ──
    private func startServer() {
        listener = try? NWListener(using: .tcp, on: 8080)
        listener?.service = NWListener.Service(name: "QueuePad",
                                               type: "_http._tcp") // Bonjour
        listener?.newConnectionHandler = { [weak self] conn in
            self?.setup(conn)
        }
        listener?.start(queue: .main)
    }

    private func setup(_ conn: NWConnection) {
        connections.append(conn)
        conn.receiveMessage { _, _, _, _ in }
        conn.start(queue: .main)
        sendStatus(to: conn)         // 初始狀態
    }

    private func broadcast() {       // 推播給所有連線
        connections.forEach(sendStatus)
    }

    private func sendStatus(to conn: NWConnection) {
        let payload = try! JSONEncoder().encode(
            ["current": currentNumber,
             "waiting": waitingList.count])
        conn.send(content: payload, completion: .contentProcessed { _ in })
    }
}
