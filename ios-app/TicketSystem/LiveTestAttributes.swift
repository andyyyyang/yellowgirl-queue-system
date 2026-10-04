import ActivityKit

struct LiveTestAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var count: Int
    }

    var title: String
}
