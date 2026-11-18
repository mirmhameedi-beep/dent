import Foundation

@MainActor
final class DentStore: ObservableObject {
    static let target: Int64 = 1_000_000_000

    @Published var totalTaps: Int64 = 0
    @Published var reachable = true
    @Published var wall: [WallEntry] = []

    private(set) var mac: String

    private let session: URLSession
    private let baseURL: URL

    init(baseURL: URL = API.baseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.mac = DeviceID.load()
    }

    func refresh() async {
        await loadStone()
        await loadWall()
    }

    func tap() {
        totalTaps += 1
    }

    func sendTap(position: CGPoint) async -> Dent? {
        do {
            let payload = TapRequest(mac: mac, x: Double(position.x), y: Double(position.y))
            var request = URLRequest(url: baseURL.appendingPathComponent("tap"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(payload)
            let (data, _) = try await session.data(for: request)
            let response = try JSONDecoder().decode(TapResponse.self, from: data)
            totalTaps = response.total
            return Dent(position: position, mac: mac, at: Date(timeIntervalSince1970: response.at))
        } catch {
            reachable = false
            return nil
        }
    }

    func loadStone() async {
        do {
            let (data, _) = try await session.data(from: baseURL.appendingPathComponent("stone"))
            let response = try JSONDecoder().decode(StoneResponse.self, from: data)
            totalTaps = response.total
            reachable = true
        } catch {
            reachable = false
        }
    }

    func loadWall() async {
        do {
            let (data, _) = try await session.data(from: baseURL.appendingPathComponent("wall"))
            wall = try JSONDecoder().decode([WallEntry].self, from: data)
        } catch {
            wall = []
        }
    }
}

struct TapRequest: Encodable {
    let mac: String
    let x: Double
    let y: Double
}

struct TapResponse: Decodable {
    let total: Int64
    let at: Double
}

struct StoneResponse: Decodable {
    let total: Int64
}

struct WallEntry: Decodable, Identifiable {
    let mac: String
    let taps: Int64
    let at: Double

    var id: String { mac }
}

enum API {
    static let baseURL = URL(string: "https://your-backend.example.com")!
}
