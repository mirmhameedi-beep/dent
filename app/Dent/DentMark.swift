import SwiftUI

struct StoneShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.addEllipse(in: rect)
        return path
    }
}

struct Dent: Identifiable, Codable, Equatable {
    let id: UUID
    let position: CGPoint
    let mac: String
    let at: Date

    enum CodingKeys: String, CodingKey {
        case id
        case x
        case y
        case mac
        case at
    }

    init(position: CGPoint, mac: String, at: Date) {
        self.id = UUID()
        self.position = position
        self.mac = mac
        self.at = at
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        let x = try container.decode(Double.self, forKey: .x)
        let y = try container.decode(Double.self, forKey: .y)
        position = CGPoint(x: x, y: y)
        mac = try container.decode(String.self, forKey: .mac)
        let seconds = try container.decode(Double.self, forKey: .at)
        at = Date(timeIntervalSince1970: seconds)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(Double(position.x), forKey: .x)
        try container.encode(Double(position.y), forKey: .y)
        try container.encode(mac, forKey: .mac)
        try container.encode(at.timeIntervalSince1970, forKey: .at)
    }

    static func randomPosition() -> CGPoint {
        let angle = Double.random(in: 0...(2 * .pi))
        let radius = sqrt(Double.random(in: 0...1)) * 0.48
        return CGPoint(x: 0.5 + cos(angle) * radius, y: 0.5 + sin(angle) * radius)
    }
}

struct DentMark: View {
    let dent: Dent
    let stoneDiameter: CGFloat

    var body: some View {
        Circle()
            .fill(Color.black.opacity(0.55))
            .frame(width: 6, height: 6)
            .blur(radius: 1.2)
            .overlay(
                Circle()
                    .stroke(Color(white: 0.7).opacity(0.25), lineWidth: 0.7)
                    .blur(radius: 0.5)
            )
            .position(
                x: dent.position.x * stoneDiameter,
                y: dent.position.y * stoneDiameter
            )
            .transition(.scale(scale: 2.2).combined(with: .opacity))
            .animation(.easeOut(duration: 0.3), value: dent.id)
    }
}
