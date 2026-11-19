import test from "node:test";
import assert from "node:assert/strict";

import {
  TapPipeline,
  clampTotal,
  QUEUE_CAPACITY,
  BACKOFF_START_MS,
  BACKOFF_CAP_MS,
  TARGET,
} from "../../static/dent-core.js";

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  };
}

function makePipeline(overrides = {}) {
  const storage = overrides.storage ?? fakeStorage();
  const sends = [];
  let respond = overrides.respond ?? (() => ({ status: 200, body: { total: 1 } }));
  const events = { acked: [], rejected: [], throttled: [], transient: [], unaccepted: [], completed: 0 };
  const pipeline = new TapPipeline({
    storage,
    sendTap: async (entry) => {
      sends.push(JSON.parse(JSON.stringify(entry)));
      return respond(sends.length, entry);
    },
    backoffStartMs: overrides.backoffStartMs ?? 5,
    backoffCapMs: overrides.backoffCapMs ?? 40,
    queueCapacity: overrides.queueCapacity,
    onAcked: (e) => events.acked.push(e),
    onRejected: (e, n) => events.rejected.push({ entry: e, count: n }),
    onThrottled: (e) => events.throttled.push(e),
    onTransient: (e) => events.transient.push(e),
    onUnaccepted: (e) => events.unaccepted.push(e),
    onCompleted: () => events.completed += 1,
  });
  pipeline.events = events;
  return { pipeline, storage, sends, events, setRespond: (fn) => { respond = fn; } };
}

async function settle(ms = 150) {
  await new Promise((r) => setTimeout(r, ms));
}

const MAC = "web-test-device-0001";

test("each new tap gets a unique UUID persisted before sending", async () => {
  const { pipeline, storage, sends } = makePipeline();
  const first = pipeline.tap({ x: 0.1, y: 0.2, mac: MAC });
  assert.equal(first.queued, true);
  const second = pipeline.tap({ x: 0.3, y: 0.4, mac: MAC });
  assert.notEqual(first.entry.id, second.entry.id);
  const stored = JSON.parse(storage.getItem("dent.pendingTaps"));
  assert.equal(stored.length, 2);
  assert.deepEqual(stored.map((t) => t.id), [first.entry.id, second.entry.id]);
  assert.equal(sends.length, 0);
});

test("retry reuses the exact same UUID and payload", async () => {
  const { pipeline, sends, setRespond } = makePipeline();
  const tapped = pipeline.tap({ x: 0.5, y: 0.6, mac: MAC });
  setRespond((n) => {
    if (n === 1) throw new TypeError("network down");
    return { status: 200, body: { total: 1 } };
  });
  await pipeline.flush();
  await settle(100);
  assert.ok(sends.length >= 2);
  for (const sent of sends) {
    assert.equal(sent.id, tapped.entry.id);
    assert.equal(sent.mac, MAC);
    assert.equal(sent.x, 0.5);
    assert.equal(sent.y, 0.6);
  }
});

test("pending taps survive a page reload and resume flushing", async () => {
  const shared = fakeStorage();
  const first = makePipeline({ storage: shared, respond: () => { throw new TypeError("offline"); } });
  const tapped = first.pipeline.tap({ x: 0.7, y: 0.8, mac: MAC });
  await first.pipeline.flush();

  const reloaded = makePipeline({ storage: shared, respond: () => ({ status: 200, body: { total: 4242 } }) });
  assert.equal(reloaded.pipeline.queue().length, 1);
  assert.equal(reloaded.pipeline.queue()[0].id, tapped.entry.id);
  await reloaded.pipeline.flush();
  assert.equal(reloaded.pipeline.queue().length, 0);
  assert.equal(reloaded.events.acked.length, 1);
  assert.equal(reloaded.events.acked[0].total, 4242);
});

test("acknowledged tap is removed from the queue", async () => {
  const { pipeline, events } = makePipeline({ respond: () => ({ status: 200, body: { total: 9 } }) });
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  await pipeline.flush();
  assert.equal(pipeline.queue().length, 0);
  assert.equal(events.acked.length, 1);
  assert.equal(events.acked[0].total, 9);
});

test("HTTP 429 retains the tap and retries after cooldown", async () => {
  const { pipeline, sends, setRespond } = makePipeline();
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  setRespond((n) => (n === 1 ? { status: 429, body: null } : { status: 200, body: { total: 3 } }));
  await pipeline.flush();
  assert.equal(pipeline.queue().length, 1);
  assert.ok(pipeline.coolingUntil > 0);
  await settle(120);
  assert.equal(sends.length, 2);
  assert.equal(pipeline.queue().length, 0);
  assert.equal(pipeline.events.acked.length, 1);
});

test("network failure retains the tap for retry", async () => {
  const { pipeline, storage, setRespond } = makePipeline();
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  setRespond(() => { throw new TypeError("connection reset"); });
  await pipeline.flush();
  assert.equal(pipeline.queue().length, 1);
  assert.equal(JSON.parse(storage.getItem("dent.pendingTaps")).length, 1);
  assert.equal(pipeline.events.acked.length, 0);
  pipeline.stopRetries();
});

test("HTTP 5xx retains the tap for retry", async () => {
  const { pipeline, setRespond } = makePipeline();
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  setRespond(() => ({ status: 502, body: null }));
  await pipeline.flush();
  assert.equal(pipeline.queue().length, 1);
  assert.equal(pipeline.events.transient.length, 1);
  pipeline.stopRetries();
});

test("HTTP 400/422 is a permanent rejection and is not retried", async () => {
  const { pipeline, sends, setRespond } = makePipeline();
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  setRespond(() => ({ status: 422, body: { detail: "invalid" } }));
  await pipeline.flush();
  await settle(80);
  assert.equal(pipeline.queue().length, 0);
  assert.equal(sends.length, 1);
  assert.equal(pipeline.rejectedCount(), 1);
  assert.equal(pipeline.events.rejected.length, 1);
  assert.equal(pipeline.events.acked.length, 0);
});

test("HTTP 410 marks completion and stops new taps", async () => {
  const { pipeline, events } = makePipeline({ respond: () => ({ status: 410, body: null }) });
  const tapped = pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  await pipeline.flush();
  assert.equal(pipeline.completed, true);
  assert.equal(events.completed, 1);
  assert.equal(pipeline.queue().length, 0);
  assert.equal(pipeline.events.unaccepted.length, 1);
  assert.equal(pipeline.events.acked.length, 0);
  const after = pipeline.tap({ x: 0.2, y: 0.2, mac: MAC });
  assert.equal(after.queued, false);
  assert.equal(after.reason, "complete");
});

test("a 410 discards only its own tap; other pending taps still resolve", async () => {
  const shared = fakeStorage();
  const first = makePipeline({ storage: shared, respond: () => ({ status: 410, body: null }) });
  const a = first.pipeline.tap({ x: 0.1, y: 0.1, mac: MAC });
  const b = first.pipeline.tap({ x: 0.2, y: 0.2, mac: MAC });
  assert.equal(first.pipeline.queue().length, 2);

  const second = makePipeline({
    storage: shared,
    respond: (n) => (n === 1 ? { status: 410, body: null } : { status: 200, body: { total: 2 } }),
  });
  await second.pipeline.flush();
  assert.equal(second.pipeline.queue().length, 0);
  assert.equal(second.pipeline.events.unaccepted.length, 1);
  assert.equal(second.pipeline.events.unaccepted[0].id, a.entry.id);
  assert.equal(second.pipeline.events.acked.length, 1);
  assert.equal(second.pipeline.events.acked[0].entry.id, b.entry.id);
  assert.equal(second.pipeline.completed, true);
});

test("previously accepted UUID retried after completion still gets its stored result", async () => {
  const shared = fakeStorage();
  const first = makePipeline({ storage: shared, respond: () => { throw new TypeError("response lost"); } });
  const accepted = first.pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  await first.pipeline.flush();
  first.pipeline.stopRetries();
  assert.equal(first.pipeline.queue().length, 1);

  const reloaded = makePipeline({
    storage: shared,
    respond: () => ({ status: 200, body: { total: 1_000_000_000 } }),
  });
  reloaded.pipeline.markCompleted();
  assert.equal(reloaded.pipeline.completed, true);
  assert.equal(reloaded.pipeline.queue().length, 1);
  await reloaded.pipeline.flush();
  assert.equal(reloaded.pipeline.queue().length, 0);
  assert.equal(reloaded.events.acked.length, 1);
  assert.equal(reloaded.events.acked[0].entry.id, accepted.entry.id);
  assert.equal(reloaded.events.acked[0].total, 1_000_000_000);
});

test("queue capacity rejects new taps without deleting existing pending taps", async () => {
  const { pipeline, storage } = makePipeline({ queueCapacity: 3 });
  const ids = [];
  for (let i = 0; i < 3; i++) {
    const r = pipeline.tap({ x: 0.1 * (i + 1), y: 0.5, mac: MAC });
    assert.equal(r.queued, true);
    ids.push(r.entry.id);
  }
  const overflow = pipeline.tap({ x: 0.9, y: 0.9, mac: MAC });
  assert.equal(overflow.queued, false);
  assert.equal(overflow.reason, "capacity");
  const stored = JSON.parse(storage.getItem("dent.pendingTaps"));
  assert.equal(stored.length, 3);
  assert.deepEqual(stored.map((t) => t.id), ids);
});

test("displayed total is clamped so it can never exceed one billion", () => {
  assert.equal(clampTotal(1_000_000_005, TARGET), 1_000_000_000);
  assert.equal(clampTotal(TARGET + 42, TARGET), TARGET);
  assert.equal(clampTotal(-3, TARGET), 0);
  assert.equal(clampTotal(999_999_999, TARGET), 999_999_999);
  const { pipeline } = makePipeline({
    respond: () => ({ status: 200, body: { total: TARGET + 7 } }),
  });
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  return pipeline.flush().then(() => {
    assert.equal(pipeline.events.acked.length, 1);
    assert.equal(pipeline.events.acked[0].total, TARGET);
  });
});

test("concurrent flush calls run serially and never duplicate a submission", async () => {
  const { pipeline, sends } = makePipeline(({ }) => ({}));
  let release;
  const gate = new Promise((r) => { release = r; });
  let inFlight = 0;
  let maxInFlight = 0;
  pipeline.sendTap = async (entry) => {
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    sends.push(JSON.parse(JSON.stringify(entry)));
    await gate;
    inFlight -= 1;
    return { status: 200, body: { total: 1 } };
  };
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  const a = pipeline.flush();
  const b = pipeline.flush();
  release();
  await Promise.all([a, b]);
  await settle(50);
  assert.equal(sends.length, 1);
  assert.equal(maxInFlight, 1);
  assert.equal(pipeline.queue().length, 0);
});

test("backoff grows exponentially and resets after an acknowledgement", async () => {
  const { pipeline } = makePipeline({
    backoffStartMs: 5,
    backoffCapMs: 40,
    respond: () => { throw new TypeError("offline"); },
  });
  pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  await pipeline.flush();
  assert.equal(pipeline.backoffMs, 5);
  await settle(200);
  assert.equal(pipeline.backoffMs, 40);
  assert.ok(pipeline.coolingUntil > 0 || pipeline.queue().length === 0);
  pipeline.stopRetries();
  assert.ok(BACKOFF_START_MS === 2000 && BACKOFF_CAP_MS === 60000);
  assert.ok(QUEUE_CAPACITY === 2000);

  const { pipeline: resetPipeline } = makePipeline({
    backoffStartMs: 5,
    respond: (n) => (n === 1 ? { status: 429, body: null } : { status: 200, body: { total: 1 } }),
  });
  resetPipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  await resetPipeline.flush();
  await settle(120);
  assert.equal(resetPipeline.backoffMs, 0);
  assert.equal(resetPipeline.queue().length, 0);
});

test("storage failure is reported honestly and no tap is silently queued", async () => {
  const failing = {
    getItem: () => null,
    setItem: () => { throw new DOMException("quota", "QuotaExceededError"); },
    removeItem: () => {},
  };
  const { pipeline, sends } = makePipeline({ storage: failing });
  const result = pipeline.tap({ x: 0.5, y: 0.5, mac: MAC });
  assert.equal(result.queued, false);
  assert.equal(result.reason, "storage");
  const flushed = pipeline.flush();
  await flushed;
  assert.equal(sends.length, 0);
});
