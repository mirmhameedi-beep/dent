import XCTest
import simd
@testable import Dent

@MainActor
final class DentStoreTests: XCTestCase {
    private var store: DentStore!
    private var queue: PendingTapStore!
    private var defaults: UserDefaults!

    override func setUp() async throws {
        MockURLProtocol.reset()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        defaults = UserDefaults(suiteName: "test.dent.pending")!
        defaults.removePersistentDomain(forName: "test.dent.pending")
        queue = PendingTapStore(defaults: defaults)
        store = await DentStore(
            baseURL: URL(string: "https://api.test")!,
            session: URLSession(configuration: config),
            pendingStore: queue
        )
    }

    override func tearDown() async throws {
        store?.stopBackgroundWork()
    }

    private func stoneResponse(_ total: Int) -> MockResponse {
        .json(["total": total, "target": 1_000_000_000, "remaining": 1_000_000_000 - total, "dents": []])
    }

    private func tapResponse(_ total: Int) -> MockResponse {
        .json(["total": total, "at": 2_000.0, "dent": [
            "id": "22222222-2222-2222-2222-222222222222", "x": 0.5, "y": 0.5, "mac": "local", "at": 2_000.0
        ]])
    }

    private func waitUntil(_ condition: @MainActor () -> Bool, timeout: TimeInterval = 5) async {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if condition() { return }
            try? await Task.sleep(for: .milliseconds(20))
        }
    }

    private func tapBodyIDs(x: Double = 0.5, y: Double = 0.5) -> [String] {
        MockURLProtocol.sentBodies(path: "/tap").compactMap { data in
            let body = MockURLProtocol.bodyDictionary(data)
            let bodyX = body?["x"] as? Double
            let bodyY = body?["y"] as? Double
            guard bodyX == x, bodyY == y else { return nil }
            return body?["id"] as? String
        }
    }

    func testLoadStonePopulatesCounterAndDents() async {
        MockURLProtocol.handler = { path in
            path == "/stone" ? .json(["total": 77, "target": 1_000_000_000, "remaining": 999_999_923, "dents": [
                ["id": "11111111-1111-1111-1111-111111111111", "x": 0.4, "y": 0.6, "mac": "someone-else", "at": 1_000.0]
            ]]) : nil
        }
        await store.loadStone()
        XCTAssertEqual(store.confirmedTotal, 77)
        XCTAssertEqual(store.displayTotal, 77)
        XCTAssertEqual(store.dents.count, 1)
        XCTAssertEqual(store.dents.first?.mac, "someone-else")
        XCTAssertTrue(store.reachable)
    }

    func testLoadStoneNeverMovesCounterBackward() async {
        store.confirmedTotal = 100
        MockURLProtocol.handler = { path in
            path == "/stone" ? .json(["total": 40, "target": 1_000_000_000, "remaining": 999_999_960, "dents": []]) : nil
        }
        await store.loadStone()
        XCTAssertEqual(store.confirmedTotal, 100)
    }

    func testTapSuccessRemovesPendingAndReconciles() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(51) : self.stoneResponse(51)
        }
        store.tap(position: CGPoint(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 51)
        XCTAssertEqual(store.displayTotal, 51)
        XCTAssertTrue(store.reachable)
    }

    func testFailedTapIsQueuedAndFlushedLater() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? nil : self.stoneResponse(0)
        }
        store.tap(position: CGPoint(x: 0.3, y: 0.3))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertFalse(store.reachable)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(999) : self.stoneResponse(999)
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 999)
        XCTAssertTrue(store.reachable)
    }

    @MainActor
    func testTapAddsLocalDentImmediately() {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(2) : self.stoneResponse(2)
        }
        store.tap(position: CGPoint(x: 0.2, y: 0.3))
        store.tap(position: CGPoint(x: 0.7, y: 0.9))
        XCTAssertEqual(store.pendingCount, 2)
        XCTAssertEqual(store.displayTotal, 2)
        XCTAssertEqual(store.dents.count, 2)
    }

    @MainActor
    func testVisibleDentsAreCapped() {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        for i in 0..<450 {
            store.tap(position: CGPoint(x: 0.1, y: 0.1).offsetByMilli(i))
        }
        XCTAssertEqual(store.dents.count, DentStore.maxVisibleDents)
    }

    func testTapPersistsUUIDBeforeSubmissionAndSendsIt() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        store.tap(position: CGPoint(x: 0.5, y: 0.5))
        let persistedID = queue.taps().first?.id
        XCTAssertNotNil(persistedID)
        XCTAssertEqual(queue.count, 1)
        await store.flushPending()
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 1)
        XCTAssertTrue(ids.allSatisfy { $0 == persistedID?.uuidString })
    }

    func testUUIDReusedAfterTimeout() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? nil : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 2)
        XCTAssertEqual(Set(ids).count, 1)
    }

    func testUUIDReusedAfter429AndNoPhantomIncrements() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(429, ["detail": "Slow down. The stone is patient."]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertEqual(store.confirmedTotal, 0)
        XCTAssertEqual(store.displayTotal, 1)
        XCTAssertTrue(store.coolingDown)
        XCTAssertTrue(store.reachable)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 1)
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 2)
        XCTAssertEqual(Set(ids).count, 1)
    }

    func testNoRequestsDuringCooldown() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(429, ["detail": "Slow down."]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(tapBodyIDs().count, 1)
        await store.flushPending()
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertEqual(store.coolingDown, true)
    }

    func testUUIDSurvivesAppRestart() async {
        let restartDefaults = UserDefaults(suiteName: "test.dent.restart")!
        restartDefaults.removePersistentDomain(forName: "test.dent.restart")
        let restartQueue = PendingTapStore(defaults: restartDefaults)
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let firstStore = await DentStore(
            baseURL: URL(string: "https://api.test")!,
            session: URLSession(configuration: config),
            pendingStore: restartQueue
        )
        MockURLProtocol.handler = { path in
            path == "/tap" ? nil : self.stoneResponse(0)
        }
        firstStore.tap(position: CGPoint(x: 0.5, y: 0.5))
        await firstStore.flushPending()
        let originalID = restartQueue.taps().first?.id
        XCTAssertNotNil(originalID)
        firstStore.stopBackgroundWork()

        let restartedStore = await DentStore(
            baseURL: URL(string: "https://api.test")!,
            session: URLSession(configuration: config),
            pendingStore: restartQueue
        )
        XCTAssertEqual(restartedStore.pendingCount, 1)
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await restartedStore.flushPending()
        XCTAssertEqual(tapBodyIDs().first, originalID?.uuidString)
        restartedStore.stopBackgroundWork()
    }

    func testAcknowledgedTapRemovedFromPendingQueue() async {
        queue.append(PendingTap(x: 0.5, y: 0.5))
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await store.flushPending()
        XCTAssertEqual(queue.count, 0)
        XCTAssertEqual(store.pendingCount, 0)
    }

    func testDuplicateSuccessResponsesDoNotDoubleCount() async {
        queue.append(PendingTap(x: 0.5, y: 0.5))
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(51) : self.stoneResponse(51)
        }
        await store.flushPending()
        await store.flushPending()
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertEqual(store.confirmedTotal, 51)
        XCTAssertEqual(store.displayTotal, 51)
    }

    func testValidationRejectionRecordedAndNotRetried() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(422, ["detail": "Invalid tap id"]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(queue.rejectedCount, 1)
        XCTAssertNotNil(store.rejection)
        XCTAssertEqual(store.confirmedTotal, 0)

        await store.flushPending()
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertEqual(queue.rejectedCount, 1)
    }

    func testNetworkErrorPreservesPendingTap() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? nil : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(queue.count, 1)
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertEqual(store.confirmedTotal, 0)
        XCTAssertFalse(store.reachable)
    }

    func testFailedItemDoesNotBlockLaterItems() async {
        let counter = ThreadSafeCounter()
        MockURLProtocol.handler = { path in
            path == "/tap" ? (counter.next() == 1 ? .status(422, ["detail": "nope"]) : self.tapResponse(77)) : self.stoneResponse(77)
        }
        queue.append(PendingTap(x: 0.1, y: 0.1))
        queue.append(PendingTap(x: 0.2, y: 0.2))
        await store.flushPending()
        XCTAssertEqual(queue.count, 0)
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 77)
        XCTAssertNotNil(store.rejection)
    }

    func testQueueCapacityRejectsNewTapWithoutDiscarding() {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        for i in 0..<PendingTapStore.capacity {
            XCTAssertTrue(queue.append(PendingTap(x: Double(i) / Double(PendingTapStore.capacity), y: 0.5)))
        }
        let firstID = queue.taps().first?.id
        let lastID = queue.taps().last?.id
        store.tap(position: CGPoint(x: 0.123, y: 0.456))
        XCTAssertTrue(store.queueIsFull)
        XCTAssertEqual(queue.count, PendingTapStore.capacity)
        XCTAssertEqual(store.pendingCount, PendingTapStore.capacity)
        XCTAssertEqual(queue.taps().first?.id, firstID)
        XCTAssertEqual(queue.taps().last?.id, lastID)
        XCTAssertEqual(store.confirmedTotal, 0)
        let containsNewTap = queue.taps().contains { $0.x == 0.123 && $0.y == 0.456 }
        XCTAssertFalse(containsNewTap)
    }

    func testCompletedStoneResponseStopsSubmissions() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(410, ["detail": "gone"]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertTrue(store.stoneComplete)
        XCTAssertEqual(queue.count, 0)
        XCTAssertEqual(store.pendingCount, 0)

        store.tap(position: CGPoint(x: 0.4, y: 0.4))
        XCTAssertEqual(queue.count, 0)
        XCTAssertEqual(store.pendingCount, 0)
        let ids = tapBodyIDs(x: 0.4, y: 0.4)
        XCTAssertEqual(ids.count, 0)
    }

    func testStaleTotalCannotMoveConfirmedBackward() async {
        store.confirmedTotal = 500
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(50) : self.stoneResponse(50)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.confirmedTotal, 500)
        XCTAssertEqual(store.pendingCount, 0)
    }

    func testFlushPicksUpTapsAppendedWhileInFlight() async {
        MockURLProtocol.holdRequests = true
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        store.tap(position: CGPoint(x: 0.5, y: 0.5))
        await waitUntil { self.tapBodyIDs().count == 1 }
        XCTAssertEqual(tapBodyIDs().count, 1)
        let firstID = queue.taps().first?.id
        XCTAssertNotNil(firstID)

        store.tap(position: CGPoint(x: 0.2, y: 0.2))
        let secondID = queue.taps().last?.id
        XCTAssertNotNil(secondID)
        XCTAssertNotEqual(firstID, secondID)
        XCTAssertEqual(store.pendingCount, 2)

        MockURLProtocol.holdRequests = false
        MockURLProtocol.holdGate.signal()
        await waitUntil { self.store.pendingCount == 0 }
        XCTAssertEqual(store.pendingCount, 0)
        let firstBodies = tapBodyIDs().filter { $0 == firstID?.uuidString }
        let secondBodies = tapBodyIDs(x: 0.2, y: 0.2).filter { $0 == secondID?.uuidString }
        XCTAssertEqual(firstBodies.count, 1)
        XCTAssertEqual(secondBodies.count, 1)
    }

    func testScheduledRetryFiresAfterCooldown() async {
        store.retryDelayStart = 0.1
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(429, ["detail": "Slow down."]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertTrue(store.coolingDown)

        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await waitUntil { self.store.pendingCount == 0 }
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 1)
        XCTAssertFalse(store.coolingDown)
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 2)
        XCTAssertEqual(Set(ids).count, 1)
    }

    func testServer500RetainsAndRetriesSameUUID() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(500, ["detail": "boom"]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertEqual(store.confirmedTotal, 0)
        XCTAssertFalse(store.reachable)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.confirmedTotal, 1)
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 2)
        XCTAssertEqual(Set(ids).count, 1)
    }

    func testMalformedSuccessRetainsTapForRetry() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? .json(["unexpected": true]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 1)
        XCTAssertEqual(store.confirmedTotal, 0)
        XCTAssertEqual(tapBodyIDs().count, 1)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        await store.flushPending()
        XCTAssertEqual(store.pendingCount, 0)
        let ids = tapBodyIDs()
        XCTAssertGreaterThanOrEqual(ids.count, 2)
        XCTAssertEqual(Set(ids).count, 1)
    }

    func testStopBackgroundWorkCancelsScheduledRetry() async {
        store.retryDelayStart = 0.1
        MockURLProtocol.handler = { path in
            path == "/tap" ? .status(429, ["detail": "Slow down."]) : self.stoneResponse(0)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertEqual(store.pendingCount, 1)

        store.stopBackgroundWork()
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        try? await Task.sleep(for: .milliseconds(400))
        XCTAssertEqual(tapBodyIDs().count, 1)
        XCTAssertEqual(store.pendingCount, 1)
    }

    func testQueueFullWarningClearsAfterAckFreesCapacity() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(1) : self.stoneResponse(1)
        }
        for i in 0..<PendingTapStore.capacity {
            _ = queue.append(PendingTap(x: Double(i) / Double(PendingTapStore.capacity), y: 0.5))
        }
        store.tap(position: CGPoint(x: 0.123, y: 0.456))
        XCTAssertTrue(store.queueIsFull)

        queue.removeAll(ids: queue.taps().map(\.id))
        queue.append(PendingTap(x: 0.7, y: 0.7))
        store.stopBackgroundWork()
        await store.flushPending()
        XCTAssertFalse(store.queueIsFull)
        XCTAssertEqual(store.pendingCount, 0)
    }

    func testRefreshAfterAckReconcilesWithStone() async {
        MockURLProtocol.handler = { path in
            path == "/tap" ? self.tapResponse(51) : self.stoneResponse(60)
        }
        queue.append(PendingTap(x: 0.5, y: 0.5))
        await store.flushPending()
        XCTAssertEqual(store.confirmedTotal, 60)
        XCTAssertEqual(store.pendingCount, 0)
        XCTAssertEqual(store.displayTotal, 60)
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

    func testAppendAtCapacityRejectsAndPreserves() {
        let store = PendingTapStore(defaults: defaults)
        let first = PendingTap(x: 0, y: 0)
        let last = PendingTap(x: 1, y: 1)
        XCTAssertTrue(store.append(first))
        for _ in 1..<(PendingTapStore.capacity - 1) {
            store.append(PendingTap(x: 0.5, y: 0.5))
        }
        XCTAssertTrue(store.append(last))
        let overflow = PendingTap(x: 0.9, y: 0.9)
        XCTAssertFalse(store.append(overflow))
        XCTAssertEqual(store.count, PendingTapStore.capacity)
        XCTAssertEqual(store.taps().first?.id, first.id)
        XCTAssertEqual(store.taps().last?.id, last.id)
        XCTAssertFalse(store.taps().contains(overflow))
    }

    func testRejectionTallyPersists() {
        let store = PendingTapStore(defaults: defaults)
        XCTAssertEqual(store.rejectedCount, 0)
        store.recordRejection()
        store.recordRejection()
        let reopened = PendingTapStore(defaults: defaults)
        XCTAssertEqual(reopened.rejectedCount, 2)
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

    func testGlobalRoundTrip() {
        for (u, v) in [(0.13, 0.77), (0.0, 0.5), (0.999, 0.02), (0.5, 1.0), (0.25, 0.999)] {
            let point = Globe.spherePoint(u: u, v: v)
            let back = Globe.globe(from: point)
            XCTAssertEqual(back.u, u, accuracy: 1e-9, "u failed for (\(u), \(v))")
            XCTAssertEqual(back.v, v, accuracy: 1e-9, "v failed for (\(u), \(v))")
        }
    }

    func testRotateInvertsUnrotate() {
        let point = Globe.spherePoint(u: 0.31, v: 0.64)
        let rotated = Globe.rotate(point, yaw: 1.234, pitch: -0.432)
        let back = Globe.unrotate(rotated, yaw: 1.234, pitch: -0.432)
        XCTAssertLessThan(simd_length(point - back), 1e-9)
        XCTAssertEqual(simd_length(rotated), 1, accuracy: 1e-12)
    }

    func testGlobeRejectsOffSphereInput() {
        let scaled = Globe.spherePoint(u: 0.4, v: 0.6) * 17.0
        let coordinates = Globe.globe(from: scaled)
        let standard = Globe.spherePoint(u: 0.4, v: 0.6)
        XCTAssertEqual(coordinates.u, Globe.globe(from: standard).u, accuracy: 1e-12)
        XCTAssertEqual(coordinates.v, Globe.globe(from: standard).v, accuracy: 1e-12)
    }
}

private extension CGPoint {
    func offsetByMilli(_ index: Int) -> CGPoint {
        CGPoint(x: x, y: y + Double(index) * 1e-9)
    }
}

final class ThreadSafeCounter {
    private let lock = NSLock()
    private var value = 0

    func next() -> Int {
        lock.lock()
        defer { lock.unlock() }
        value += 1
        return value
    }
}

final class MockURLProtocol: URLProtocol {
    static var handler: ((String) -> MockResponse?)?
    private static let sentLock = NSLock()
    private static var sentRequests: [(path: String, body: Data)] = []

    enum MockResponse {
        case json([String: Any])
        case status(Int, [String: Any]?)
    }

    static let holdGate = DispatchSemaphore(value: 0)
    static var holdRequests = false

    static func reset() {
        sentLock.lock()
        defer { sentLock.unlock() }
        handler = nil
        sentRequests = []
        holdRequests = false
    }

    static func sentBodies(path: String) -> [Data] {
        sentLock.lock()
        defer { sentLock.unlock() }
        return sentRequests.filter { $0.path == path }.map(\.body)
    }

    static func bodyDictionary(_ data: Data) -> [String: Any]? {
        try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        if let data = Self.bodyData(from: request) {
            Self.sentLock.lock()
            Self.sentRequests.append((request.url?.path ?? "", data))
            Self.sentLock.unlock()
        }
        guard let handler = Self.handler, let path = request.url?.path else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        if Self.holdRequests {
            _ = Self.holdGate.wait(timeout: .now() + 10)
        }
        switch handler(path) {
        case .some(.json(let payload)):
            respond(200, payload)
        case .some(.status(let code, let payload)):
            respond(code, payload ?? [:])
        case .none:
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
        }
    }

    override func stopLoading() {}

    private func respond(_ code: Int, _ payload: [String: Any]) {
        let data = (try? JSONSerialization.data(withJSONObject: payload)) ?? Data()
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: code,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    private static func bodyData(from request: URLRequest) -> Data? {
        if let data = request.httpBody { return data }
        guard let stream = request.httpBodyStream else { return nil }
        stream.open()
        defer { stream.close() }
        var data = Data()
        let bufferSize = 4096
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer { buffer.deallocate() }
        while stream.hasBytesAvailable {
            let read = stream.read(buffer, maxLength: bufferSize)
            if read <= 0 { break }
            data.append(buffer, count: read)
        }
        return data
    }
}
