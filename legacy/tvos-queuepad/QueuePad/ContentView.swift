//
//  ContentView.swift
//  QueuePad
//
//  Created by ANDY Yang on 2025/7/13.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var qm = QueueManager.shared

    var body: some View {
        VStack(spacing: 48) {
            Text(qm.currentNumber == 0 ? "--" : String(qm.currentNumber))
                .font(.system(size: 160, weight: .bold, design: .rounded))
                .frame(maxWidth: .infinity)
                .minimumScaleFactor(0.5)

            Text("排隊人數：\(qm.waitingList.count)")
                .font(.title2)

            HStack(spacing: 24) {
                Button("新增號碼") { qm.addTicket() }
                Button("下一號")  { qm.next() }.disabled(qm.waitingList.isEmpty)
                Button("重設")   { qm.reset() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
