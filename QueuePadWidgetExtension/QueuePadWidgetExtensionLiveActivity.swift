//
//  QueuePadWidgetExtensionLiveActivity.swift
//  QueuePadWidgetExtension
//
//  Created by ANDY Yang on 2025/7/17.
//

import ActivityKit
import WidgetKit
import SwiftUI

struct QueuePadWidgetExtensionAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        // Dynamic stateful properties about your activity go here!
        var emoji: String
    }

    // Fixed non-changing properties about your activity go here!
    var name: String
}

struct QueuePadWidgetExtensionLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: QueuePadWidgetExtensionAttributes.self) { context in
            // Lock screen/banner UI goes here
            VStack {
                Text("Hello \(context.state.emoji)")
            }
            .activityBackgroundTint(Color.cyan)
            .activitySystemActionForegroundColor(Color.black)

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI goes here.  Compose the expanded UI through
                // various regions, like leading/trailing/center/bottom
                DynamicIslandExpandedRegion(.leading) {
                    Text("Leading")
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text("Trailing")
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("Bottom \(context.state.emoji)")
                    // more content
                }
            } compactLeading: {
                Text("L")
            } compactTrailing: {
                Text("T \(context.state.emoji)")
            } minimal: {
                Text(context.state.emoji)
            }
            .widgetURL(URL(string: "http://www.apple.com"))
            .keylineTint(Color.red)
        }
    }
}

extension QueuePadWidgetExtensionAttributes {
    fileprivate static var preview: QueuePadWidgetExtensionAttributes {
        QueuePadWidgetExtensionAttributes(name: "World")
    }
}

extension QueuePadWidgetExtensionAttributes.ContentState {
    fileprivate static var smiley: QueuePadWidgetExtensionAttributes.ContentState {
        QueuePadWidgetExtensionAttributes.ContentState(emoji: "😀")
     }
     
     fileprivate static var starEyes: QueuePadWidgetExtensionAttributes.ContentState {
         QueuePadWidgetExtensionAttributes.ContentState(emoji: "🤩")
     }
}

#Preview("Notification", as: .content, using: QueuePadWidgetExtensionAttributes.preview) {
   QueuePadWidgetExtensionLiveActivity()
} contentStates: {
    QueuePadWidgetExtensionAttributes.ContentState.smiley
    QueuePadWidgetExtensionAttributes.ContentState.starEyes
}
