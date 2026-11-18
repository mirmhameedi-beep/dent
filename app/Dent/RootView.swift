import SwiftUI

struct RootView: View {
    @StateObject private var store = DentStore()

    var body: some View {
        TabView {
            StoneView()
                .environmentObject(store)
                .tabItem {
                    Label("Stone", systemImage: "circle.fill")
                }
            WallView()
                .environmentObject(store)
                .tabItem {
                    Label("Wall", systemImage: "text.bubble")
                }
        }
        .tint(.white)
        .task { await store.refresh() }
    }
}

#Preview {
    RootView()
        .preferredColorScheme(.dark)
}
