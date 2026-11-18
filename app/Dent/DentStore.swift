import Foundation

struct TapRequest: Encodable {
    let mac: String
    let x: Double
    let y: Double
}

struct TapResponse: Decodable {
    let total: Int64
    let at: Double
    let dent: Dent
}

struct StoneResponse: Decodable {
    let total: Int64
    let dents: [Dent]?
}

struct WallEntry: Decodable, Identifiable, Equatable {
    let mac: String
    let taps: Int64
    let at: Double

    var id: String { mac }
}

enum API {
    static let baseURL = URL(string: "https://your-backend.example.com")!
}

struct PendingTap: Codable, Identifiable, Equatable {
    let id: UUID
    let x: Double
    let y: Double

    init(x: Double, y: Double) {
        self.id = UUID()
        self.x = x
        self.y = y
    }
}

final class PendingTapStore: @unchecked Sendable {
    private let defaults: UserDefaults
    private let key = "dent.pendingTaps"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func taps() -> [PendingTap] {
        guard let data = defaults.data(forKey: key),
              let taps = try? JSONDecoder().decode([PendingTap].self, from: data) else {
            return []
        }
        return taps
    }

    var count: Int { taps().count }

    func append(_ tap: PendingTap) {
        if let data = try? JSONEncoder().encode(taps() + [tap]) {
            defaults.set(data, forKey: key)
        }
    }

    func removeAll(ids: [UUID]) {
        guard !ids.isEmpty else { return }
        let removed = Set(ids)
        if let data = try? JSONEncoder().encode(taps().filter { !removed.contains($0.id) }) {
            defaults.set(data, forKey: key)
        }
    }
}

@MainActor
final class DentStore: ObservableObject {
    static let target: Int64 = 1_000_000_000
    static let maxVisibleDents = 400

    @Published var totalTaps: Int64 = 0
    @Published var reachable = true
    @Published var wall: [WallEntry] = []
    @Published var dents: [Dent] = []
    @Published private(set) var pendingCount = 0

    private(set) var mac: String

    private let session: URLSession
    private let baseURL: URL
    private let pendingStore: PendingTapStore

    init(baseURL: URL = API.baseURL, session: URLSession = .shared, pendingStore: PendingTapStore = PendingTapStore()) {
        self.baseURL = baseURL
        self.session = session
        self.pendingStore = pendingStore
        self.mac = DeviceID.load()
        pendingCount = pendingStore.count
    }

    func refresh() async {
        await loadStone()
        await loadWall()
        await flushPending()
    }

    func tap() {
        totalTaps += 1
        let position = Dent.randomPosition()
        let local = Dent(position: position, mac: mac, at: Date())
        dents.append(local)
        if dents.count > Self.maxVisibleDents { dents.removeFirst(dents.count - Self.maxVisibleDents) }
        Task {
            await sendTap(position: position)
        }
    }

    private func sendTap(position: CGPoint) async {
        await submit(TapRequest(mac: mac, x: Double(position.x), y: Double(position.y)))
    }

    func loadStone() async {
        do {
            let (data, _) = try await session.data(from: baseURL.appendingPathComponent("stone"))
            let response = try JSONDecoder().decode(StoneResponse.self, from: data)
            totalTaps = max(totalTaps, response.total)
            dents = response.dents ?? []
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

    private func submit(_ request: TapRequest) async {
        do {
            let response = try await post(request)
            totalTaps = max(totalTaps, response.total)
            reachable = true
        } catch {
            reachable = false
            pendingStore.append(PendingTap(x: request.x, y: request.y))
            pendingCount = pendingStore.count
        }
    }

    func flushPending() async {
        var delivered: [UUID] = []
        for pending in pendingStore.taps() {
            do {
                let response = try await post(TapRequest(mac: mac, x: pending.x, y: pending.y))
                delivered.append(pending.id)
                totalTaps = max(totalTaps, response.total)
                reachable = true
            } catch {
                reachable = false
                break
            }
        }
        pendingStore.removeAll(ids: delivered)
        pendingCount = pendingStore.count
    }

    private func post(_ payload: TapRequest) async throws -> TapResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent("tap"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(payload)
        let (data, response) = try await session.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(TapResponse.self, from: data)
    }
}
