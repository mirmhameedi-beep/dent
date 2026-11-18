import SwiftUI
import UIKit

struct StoneView: View {
    @EnvironmentObject private var store: DentStore
    @State private var dents: [Dent] = []
    @State private var pressed = false
    @State private var pulse = false

    private var stoneDiameter: CGFloat {
        let side = UIScreen.main.bounds.width
        return min(side * 0.82, 340)
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 24) {
                ProgressHeader(store: store)
                    .padding(.top, 16)

                ZStack {
                    stone
                    ForEach(dents) { dent in
                        DentMark(dent: dent, stoneDiameter: stoneDiameter)
                    }
                }
                .frame(width: stoneDiameter, height: stoneDiameter)
                .scaleEffect(pressed ? 0.975 : 1)
                .animation(.spring(response: 0.22, dampingFraction: 0.55), value: pressed)
                .opacity(pulse ? 1 : 0)
                .onAppear {
                    withAnimation(.easeIn(duration: 0.6)) { pulse = true }
                }

                TapButton(dents: $dents, pressed: $pressed, stoneDiameter: stoneDiameter)
                    .padding(.bottom, 12)

                Text("Begun before you arrived. Ending long after you're gone.")
                    .font(.caption2)
                    .foregroundColor(.gray)
                    .padding(.bottom, 24)
            }
        }
    }

    private var stone: some View {
        StoneShape()
            .fill(
                RadialGradient(
                    colors: [Color(white: 0.46), Color(white: 0.2)],
                    center: UnitPoint(x: 0.38, y: 0.32),
                    startRadius: 4,
                    endRadius: stoneDiameter * 0.75
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
    @Binding var dents: [Dent]
    @Binding var pressed: Bool
    let stoneDiameter: CGFloat

    var body: some View {
        Button(action: tap) {
            Text("TAP")
                .font(.system(size: 22, weight: .heavy, design: .monospaced))
                .foregroundColor(.black)
                .frame(width: stoneDiameter * 0.72, height: stoneDiameter * 0.19)
                .background(Capsule().fill(Color.white))
        }
        .buttonStyle(PressStyle(isPressed: $pressed))
        .disabled(!store.reachable)
    }

    private func tap() {
        guard store.reachable else { return }
        let position = Dent.randomPosition()
        UIImpactFeedbackGenerator(style: .rigid).impactOccurred()
        store.tap()
        let local = Dent(position: position, mac: store.mac, at: Date())
        dents.append(local)
        if dents.count > 400 { dents.removeFirst(dents.count - 400) }

        Task {
            let confirmed = await store.sendTap(position: position)
            if let confirmed {
                await MainActor.run {
                    if let index = dents.firstIndex(where: { $0.id == local.id }) {
                        dents[index] = confirmed
                    }
                }
            }
        }
    }
}

struct PressStyle: ButtonStyle {
    @Binding var isPressed: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .onChange(of: configuration.isPressed) { newValue in
                isPressed = newValue
            }
    }
}
