import SwiftUI

struct StoneView: View {
    @EnvironmentObject private var store: DentStore
    @State private var pulse = false

    var body: some View {
        GeometryReader { geo in
            let stoneSize = min(geo.size.width * 0.94, geo.size.height * 0.54)

            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 18) {
                    ProgressHeader()
                        .padding(.top, 16)
                        .accessibilityElement(children: .combine)

                    Stone3DView()
                        .frame(width: stoneSize, height: stoneSize)
                        .opacity(pulse ? 1 : 0)

                    VStack(spacing: 8) {
                        Text("Drag to spin. Tap the stone to dent it.")
                            .font(.caption)
                            .foregroundColor(.gray)

                        if store.stoneComplete {
                            Text("The stone is complete. Every dent is in place.")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.7))
                        } else if !store.reachable {
                            Text("Offline - dents queue up and send later")
                                .font(.caption2)
                                .foregroundColor(.orange.opacity(0.8))
                        } else if store.queueIsFull {
                            Text("Too many queued dents - you can dent again once the queue clears")
                                .font(.caption2)
                                .foregroundColor(.orange.opacity(0.8))
                        } else if let rejection = store.rejection {
                            Text(rejection)
                                .font(.caption2)
                                .foregroundColor(.orange.opacity(0.8))
                        } else if store.coolingDown {
                            Text("Server is busy - queued dents retry shortly")
                                .font(.caption2)
                                .foregroundColor(.gray)
                        } else if store.pendingCount > 0 {
                            Text("\(store.pendingCount) queued dents sending...")
                                .font(.caption2)
                                .foregroundColor(.gray)
                        }
                    }

                    Text("Begun before you arrived. Ending long after you're gone.")
                        .font(.caption2)
                        .foregroundColor(.gray)
                        .padding(.bottom, 24)
                }
            }
        }
        .onAppear {
            withAnimation(.easeIn(duration: 0.6)) { pulse = true }
        }
    }
}

struct ProgressHeader: View {
    @EnvironmentObject private var store: DentStore

    var body: some View {
        VStack(spacing: 6) {
            Text(human(store.displayTotal))
                .font(.system(size: 34, weight: .bold, design: .monospaced))
                .contentTransition(.numericText())
                .animation(.easeOut(duration: 0.25), value: store.displayTotal)
                .accessibilityLabel("Global dent count: \(human(store.displayTotal)) of \(human(DentStore.target))")

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(white: 0.18))
                    Capsule()
                        .fill(LinearGradient(colors: [.white.opacity(0.9), .gray], startPoint: .leading, endPoint: .trailing))
                        .frame(width: max(6, geo.size.width * CGFloat(store.displayTotal) / CGFloat(DentStore.target)))
                }
            }
            .frame(height: 6)
            .padding(.horizontal, 40)
            .accessibilityHidden(true)

            Text("\(human(max(0, DentStore.target - store.displayTotal))) taps remain")
                .font(.caption)
                .foregroundColor(.gray)
        }
    }

    private func human(_ value: Int64) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        return formatter.string(from: NSNumber(value: value)) ?? "\(value)"
    }
}
