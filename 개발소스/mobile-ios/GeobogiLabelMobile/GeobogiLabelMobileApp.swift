import SwiftUI

@main
struct GeobogiLabelMobileApp: App {
    @StateObject private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            AppView()
                .environmentObject(store)
        }
    }
}
