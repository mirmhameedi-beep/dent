import SwiftUI

struct WallView: View {
    @EnvironmentObject private var store: DentStore

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            Group {
                if store.wall.isEmpty {
                    VStack(spacing: 12) {
                        Text("The wall is bare.")
                            .font(.system(.title3, design: .monospaced))
                            .foregroundColor(.gray)
                        Text("Be one of the first names on it.")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundColor(Color(white: 0.4))
                    }
                } else {
                    List(store.wall) { entry in
                        HStack {
                            Text(short(entry.mac))
                                .font(.system(.body, design: .monospaced))
                                .foregroundColor(.white)
                            Spacer()
                            Text("\(entry.taps) dents")
                                .font(.system(.caption, design: .monospaced))
                                .foregroundColor(.gray)
                        }
                        .listRowBackground(Color.black)
                        .listRowSeparatorTint(Color(white: 0.15))
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
        }
        .task { await store.loadWall() }
        .refreshable { await store.loadWall() }
    }

    private func short(_ mac: String) -> String {
        String(mac.prefix(8))
    }
}

#Preview {
    WallView()
        .environmentObject(DentStore())
        .preferredColorScheme(.dark)
}
