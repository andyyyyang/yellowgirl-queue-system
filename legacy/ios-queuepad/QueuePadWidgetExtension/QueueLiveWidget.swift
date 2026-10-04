import WidgetKit
import SwiftUI
import ActivityKit

struct QueueLiveWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: LiveTestAttributes.self) { context in
            VStack {
                Text("\(context.state.count)")
                    .font(.system(size: 48, weight: .bold))
                    .monospacedDigit()
                Text("點我叫下一號")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding()
            .activityBackgroundTint(.white.opacity(0.3))
            .activitySystemActionForegroundColor(.black)
            .widgetURL(URL(string: "queuepad://next")) // ✅ Deep Link 設定

        } dynamicIsland: { context in
            // 🟢 Dynamic Island（iPhone 14 Pro+）
            DynamicIsland {
                // 展開時的顯示內容
                DynamicIslandExpandedRegion(.center) {
                    Text("目前號碼：\(context.state.count)")
                        .font(.title2)
                        .monospacedDigit()
                }
                DynamicIslandExpandedRegion(.leading) {
                    Text("候位中")
                        .font(.caption)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text("#\(context.state.count)")
                        .font(.caption)
                }
            } compactLeading: {
                Text("叫")
                    .font(.caption)
            } compactTrailing: {
                Text("\(context.state.count)")
                    .font(.caption)
            } minimal: {
                Text("\(context.state.count)")
                    .font(.caption)
            }
        }
    }
}
