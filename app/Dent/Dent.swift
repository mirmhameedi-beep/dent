import SwiftUI

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

    init(id: UUID, position: CGPoint, mac: String, at: Date) {
        self.id = id
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
}
