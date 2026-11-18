import XCTest
@testable import Dent

@MainActor
final class DentStoreTests: XCTestCase {
    private var store: DentStore!

    override func setUp() async throws {
        MockURLProtocol.reset()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let defaults = UserDefaults(suiteName: "test.dent.pending")!
        defaults.removePersistentDomain(forName: "test.dent.pending")
        store = await DentStore(
            baseURL: URL(string: "https://api.test")!,
            session: URLSession(configuration: config),
            pendingStore: PendingTapStore(defaults: defaults)
        )
    }

    func testLoadStonePopulatesCounterAndDents() async {
        MockURLProtocol.handler = { path in
            path == "/stone" ? .json(["total": 77, "target": 1_000_000_000, "remaining": 999_999_923, "dents": [
                ["id": "11111111-1111-1111-1111-111111111111", "x": 0.4, "y": 0.6, "mac": "someone-else", "at": 1_000.0]
            ]]) : nil
        }
        await store.loadStone()
        XCTAssertEqual(store.totalTaps, 77)
        XCTAssertEqual(store.dents.count, 1)
        XCTAssertEqual(store.dents.first?.mac, "someone-else")
        XCTAssertTrue(store.reachable)
    }

    func testLoadStoneNeverMovesCounterBackward() async {
        store.totalTaps = 100
        MockURLProtocol.handler = { path in
            path == "/stone" ? .json(["total": 40, "target": 1_000_000_000, "remaining": 999_999_960, "dents": []]) : nil
        }
        await store.loadStone()
        XCTAssertEqual(store.totalTaps, 100)
    }

    func testSendTapSuccessKeepsCounterMovingForward() async {
        store.totalTaps = 50
        MockURLProtocol.handler = { path in
            path == "/tap" ? .json(["total": 51, "at": 2_000.0, "dent": [
                "id": "22222222-2222-2222-2222-222222222222", "x": 0.5, "y": 0.5, "mac": "local", "at": 2_000.0
            ]]) : nil
        }
        await store.sendTap(position: CGPoint(x: 0.5, y: 0.5))
        XCTAssertEqual(store.totalTaps, 51)
        XCTAssertTrue(store.reachable)
        XCTAssertEqual(store.pendingCount, 0)
    }

    func testFailedTapIsQueuedAndFlushedLater() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? nil : .json(["total": 0, "target": 1, "remaining": 0, "dents": []])
        }
        await store.sendTap(position: CGPoint(x: 0.3, y: 0.3))
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertFalse(store.reachable)

        MockURLProtocol.handler = { path in
            path == "/tap" ? .json(["total": 999, "at": 3_000.0, "dent": [
                "id": "33333333-3333-3333-3333-333333333333", "x": 0.3, "y": 0.3, "mac": "local", "at": 3_000.0
            ]]) : nil
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.totalTaps, 999)
        XCTAssertTrue(store.reachable)
    }

    @MainActor
    func testTapAddsLocalDentImmediately() {
        store.tap()
        store.tap()
        XCTAssertEqual(store.totalTaps, 2)
        XCTAssertEqual(store.dents.count, 2)
    }

    @MainActor
    func testVisibleDentsAreCapped() {
        for _ in 0..<450 { store.tap() }
        XCTAssertEqual(store.dents.count, DentStore.maxVisibleDents)
    }
}

final class PendingTapStoreTests: XCTestCase {
    private var defaults: UserDefaults!

    override func setUp() {
        defaults = UserDefaults(suiteName: "test.dent.store")!
        defaults.removePersistentDomain(forName: "test.dent.store")
    }

    func testPersistAcrossInstances() {
        let first = PendingTapStore(defaults: defaults)
        first.append(PendingTap(x: 0.1, y: 0.2))
        let second = PendingTapStore(defaults: defaults)
        XCTAssertEqual(second.count, 1)
        XCTAssertEqual(second.taps().first?.x, 0.1)
    }

    func testRemoveByIds() {
        let store = PendingTapStore(defaults: defaults)
        let a = PendingTap(x: 0, y: 0)
        let b = PendingTap(x: 1, y: 1)
        store.append(a)
        store.append(b)
        store.removeAll(ids: [a.id])
        XCTAssertEqual(store.taps().map(\.id), [b.id])
    }
}

final class ModelTests: XCTestCase {
    func testDentCodableRoundTrip() throws {
        let dent = Dent(position: CGPoint(x: 0.25, y: 0.75), mac: "abc-1234", at: Date(timeIntervalSince1970: 1_234))
        let data = try JSONEncoder().encode(dent)
        let decoded = try JSONDecoder().decode(Dent.self, from: data)
        XCTAssertEqual(decoded.position.x, dent.position.x, accuracy: 0.0001)
        XCTAssertEqual(decoded.position.y, dent.position.y, accuracy: 0.0001)
        XCTAssertEqual(decoded.mac, dent.mac)
        XCTAssertEqual(decoded.at.timeIntervalSince1970, 1_234, accuracy: 0.001)
    }

    func testRandomPositionStaysInStone() {
        for _ in 0..<200 {
            let point = Dent.randomPosition()
            let dx = Double(point.x - 0.5)
            let dy = Double(point.y - 0.5)
            XCTAssertLessThanOrEqual(sqrt(dx * dx + dy * dy), 0.86 + 0.0001)
            XCTAssertGreaterThanOrEqual(point.x, 0)
            XCTAssertLessThanOrEqual(point.x, 1)
            XCTAssertGreaterThanOrEqual(point.y, 0)
            XCTAssertLessThanOrEqual(point.y, 1)
        }
    }
}

final class MockURLProtocol: URLProtocol {
    static var handler: ((String) -> MockResponse?)?

    enum MockResponse {
        case json([String: Any])
    }

    static func reset() {
        handler = nil
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.handler,
              let path = request.url?.path else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        switch handler(path) {
        case .json(let payload):
            let data = try! JSONSerialization.data(withJSONObject: payload)
            client?.urlProtocol(self, didReceive: URLResponse(url: request.url!, mimeType: "application/json", expectedContentLength: data.count, textEncodingName: "utf-8"), cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        default:
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
        }
    }

    override func stopLoading() {}
}
