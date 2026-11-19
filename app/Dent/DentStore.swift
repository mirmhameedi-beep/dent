import Foundation

struct TapRequest: Encodable {
    let id: String
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
    static let baseURL = URL(string: "https://dent-production-eecd0f14.up.railway.app")!
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
    static let capacity = 2_000
    private let defaults: UserDefaults
    private let key = "dent.pendingTaps"
    private let rejectedKey = "dent.rejectedTaps"

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

    @discardableResult
    func append(_ tap: PendingTap) -> Bool {
        var current = taps()
        guard current.count < Self.capacity else { return false }
        current.append(tap)
        guard let data = try? JSONEncoder().encode(current) else { return false }
        defaults.set(data, forKey: key)
        return true
    }

    func removeAll(ids: [UUID]) {
        guard !ids.isEmpty else { return }
        let removed = Set(ids)
        if let data = try? JSONEncoder().encode(taps().filter { !removed.contains($0.id) }) {
            defaults.set(data, forKey: key)
        }
    }

    var rejectedCount: Int {
        defaults.integer(forKey: rejectedKey)
    }

    func recordRejection() {
        defaults.set(rejectedCount + 1, forKey: rejectedKey)
    }
}

@MainActor
final class DentStore: ObservableObject {
    static let target: Int64 = 1_000_000_000
    static let maxVisibleDents = 400
    static let defaultRetryDelay: TimeInterval = 2
    static let retryDelayCap: TimeInterval = 60

    @Published var confirmedTotal: Int64 = 0
    @Published var reachable = true
    @Published var wall: [WallEntry] = []
    @Published var dents: [Dent] = []
    @Published private(set) var pendingCount = 0
    @Published private(set) var queueIsFull = false
    @Published private(set) var rejection: String?
    @Published private(set) var stoneComplete = false
    @Published private(set) var coolingDown = false

    var displayTotal: Int64 { confirmedTotal + Int64(pendingCount) }

    private(set) var mac: String

    var retryDelayStart: TimeInterval = DentStore.defaultRetryDelay

    private let session: URLSession
    private let baseURL: URL
    private let pendingStore: PendingTapStore
    private var flushInFlight = false
    private var flushTask: Task<Void, Never>?
    private var flushAgain = false
    private var retryTask: Task<Void, Never>?
    private var nextRetryAt = Date.distantPast
    private var backoff: TimeInterval = 0
    private var backgroundStopped = false

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

    func tap(position: CGPoint) {
        guard !stoneComplete else { return }
        let pending = PendingTap(x: Double(position.x), y: Double(position.y))
        guard pendingStore.append(pending) else {
            queueIsFull = true
            return
        }
        queueIsFull = false
        pendingCount = pendingStore.count
        let local = Dent(position: position, mac: mac, at: Date())
        dents.append(local)
        if dents.count > Self.maxVisibleDents { dents.removeFirst(dents.count - Self.maxVisibleDents) }
        startFlush()
    }

    func loadStone() async {
        do {
            let (data, _) = try await session.data(from: baseURL.appendingPathComponent("stone"))
            let response = try JSONDecoder().decode(StoneResponse.self, from: data)
            confirmedTotal = max(confirmedTotal, response.total)
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

    func flushPending() async {
        guard !flushInFlight, !stoneComplete, pendingCount > 0, Date() >= nextRetryAt else { return }
        flushInFlight = true
        defer { flushInFlight = false }
        while !stoneComplete, pendingCount > 0, Date() >= nextRetryAt, !Task.isCancelled {
            var progressed = false
            for pending in pendingStore.taps() {
                let outcome = await post(TapRequest(id: pending.id.uuidString, mac: mac, x: pending.x, y: pending.y))
                switch outcome {
                case .acked(let response):
                    acknowledge(pending.id, response)
                    progressed = true
                case .rejected:
                    reject(pending.id)
                    progressed = true
                case .complete:
                    completeStone(pending.id)
                    return
                case .throttled:
                    reachable = true
                    scheduleRetry()
                    return
                case .transient:
                    reachable = false
                    scheduleRetry()
                    return
                }
            }
            if progressed {
                await loadStone()
            } else {
                break
            }
        }
    }

    func stopBackgroundWork() {
        backgroundStopped = true
        flushTask?.cancel()
        flushTask = nil
        flushAgain = false
        retryTask?.cancel()
        retryTask = nil
        coolingDown = false
        nextRetryAt = .distantPast
        backoff = 0
    }

    private func startFlush() {
        guard !backgroundStopped else { return }
        guard flushTask == nil else {
            flushAgain = true
            return
        }
        flushTask = Task { [weak self] in
            await self?.drainFlushes()
        }
    }

    private func drainFlushes() async {
        while !Task.isCancelled {
            await flushPending()
            guard !Task.isCancelled else { break }
            if flushAgain {
                flushAgain = false
            } else {
                break
            }
        }
        flushTask = nil
    }

    private func acknowledge(_ id: UUID, _ response: TapResponse) {
        pendingStore.removeAll(ids: [id])
        pendingCount = pendingStore.count
        confirmedTotal = max(confirmedTotal, response.total)
        reachable = true
        rejection = nil
        if pendingCount < PendingTapStore.capacity {
            queueIsFull = false
        }
        backoff = 0
        nextRetryAt = .distantPast
        coolingDown = false
    }

    private func reject(_ id: UUID) {
        pendingStore.removeAll(ids: [id])
        pendingCount = pendingStore.count
        pendingStore.recordRejection()
        let count = pendingStore.rejectedCount
        rejection = count == 1 ? "1 dent was rejected by the server" : "\(count) dents were rejected by the server"
    }

    private func completeStone(_ id: UUID) {
        pendingStore.removeAll(ids: [id])
        pendingCount = pendingStore.count
        stoneComplete = true
        reachable = true
        coolingDown = false
        retryTask?.cancel()
        retryTask = nil
    }

    private func scheduleRetry() {
        guard !backgroundStopped else { return }
        backoff = backoff == 0 ? retryDelayStart : min(backoff * 2, Self.retryDelayCap)
        nextRetryAt = Date().addingTimeInterval(backoff)
        coolingDown = true
        retryTask?.cancel()
        retryTask = Task { [weak self, delay = backoff] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, !Task.isCancelled else { return }
            self.coolingDown = false
            await self.flushPending()
        }
    }

    private enum Submission {
        case acked(TapResponse)
        case rejected
        case complete
        case throttled
        case transient
    }

    private func post(_ payload: TapRequest) async -> Submission {
        var request = URLRequest(url: baseURL.appendingPathComponent("tap"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 10
        guard let body = try? JSONEncoder().encode(payload) else { return .transient }
        request.httpBody = body
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .transient }
            switch http.statusCode {
            case 200...299:
                return (try? JSONDecoder().decode(TapResponse.self, from: data)).map { Submission.acked($0) } ?? .transient
            case 400, 422:
                return .rejected
            case 410:
                return .complete
            case 429:
                return .throttled
            default:
                return .transient
            }
        } catch {
            return .transient
        }
    }
}
