import SwiftUI

struct StoneView: View {
    @EnvironmentObject private var store: DentStore
    @State private var squash = false
    @State private var pulse = false

    var body: some View {
        GeometryReader { geo in
            let stoneDiameter = min(geo.size.width * 0.82, 340)

            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 24) {
                    ProgressHeader()
                        .padding(.top, 16)
                        .accessibilityElement(children: .combine)

                    ZStack {
                        stone(diameter: stoneDiameter)
                        ForEach(store.dents) { dent in
                            DentMark(dent: dent, stoneDiameter: stoneDiameter)
                        }
                    }
                    .frame(width: stoneDiameter, height: stoneDiameter)
                    .scaleEffect(squash ? 0.975 : 1)
                    .opacity(pulse ? 1 : 0)
                    .accessibilityHidden(true)

                    VStack(spacing: 10) {
                        TapButton(stoneDiameter: stoneDiameter)
                            .accessibilityLabel("Add a dent")
                        if !store.reachable {
                            Text("Offline — dents queue up and send later")
                                .font(.caption2)
                                .foregroundColor(.orange.opacity(0.8))
                        } else if store.pendingCount > 0 {
                            Text("\(store.pendingCount) queued dents sending…")
                                .font(.caption2)
                                .foregroundColor(.gray)
                        }
                    }
                    .padding(.bottom, 12)

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
        .onChange(of: store.dents.count) {
            withAnimation(.spring(response: 0.14, dampingFraction: 0.5)) { squash = true }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) { squash = false }
            }
        }
    }

    private func stone(diameter: CGFloat) -> some View {
        StoneShape()
            .fill(
                RadialGradient(
                    colors: [Color(white: 0.46), Color(white: 0.2)],
                    center: UnitPoint(x: 0.38, y: 0.32),
                    startRadius: 4,
                    endRadius: diameter * 0.75
                )
            )
            .overlay(
                StoneShape()
                    .stroke(Color(white: 0.62).opacity(0.35), lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.8), radius: 28, x: 0, y: 18)
    }
}

struct ProgressHeader: View {
    @EnvironmentObject private var store: DentStore

    var body: some View {
        VStack(spacing: 6) {
            Text(human(store.totalTaps))
                .font(.system(size: 34, weight: .bold, design: .monospaced))
                .contentTransition(.numericText())
                .animation(.easeOut(duration: 0.25), value: store.totalTaps)
                .accessibilityLabel("Global dent count: \(human(store.totalTaps)) of \(human(DentStore.target))")

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(white: 0.18))
                    Capsule()
                        .fill(LinearGradient(colors: [.white.opacity(0.9), .gray], startPoint: .leading, endPoint: .trailing))
                        .frame(width: max(6, geo.size.width * CGFloat(store.totalTaps) / CGFloat(DentStore.target)))
                }
            }
            .frame(height: 6)
            .padding(.horizontal, 40)
            .accessibilityHidden(true)

            Text("\(human(DentStore.target - store.totalTaps)) taps remain")
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

struct TapButton: View {
    @EnvironmentObject private var store: DentStore
    let stoneDiameter: CGFloat

    var body: some View {
        Button(action: tap) {
            Text("TAP")
                .font(.system(size: 22, weight: .heavy, design: .monospaced))
                .foregroundColor(.black)
                .frame(width: stoneDiameter * 0.72, height: stoneDiameter * 0.19)
                .background(Capsule().fill(Color.white))
        }
        .buttonStyle(PressStyle())
    }

    private func tap() {
        UIImpactFeedbackGenerator(style: .rigid).impactOccurred()
        store.tap()
    }
}

struct PressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .animation(.spring(response: 0.18, dampingFraction: 0.6), value: configuration.isPressed)
    }
}
