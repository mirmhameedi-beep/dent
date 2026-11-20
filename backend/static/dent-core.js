export const QUEUE_CAPACITY = 2000;
export const BACKOFF_START_MS = 2000;
export const BACKOFF_CAP_MS = 60000;
export const TARGET = 1_000_000_000;

export function clampTotal(total, target) {
  return Math.max(0, Math.min(total, target));
}

function makeUUID(cryptoObj) {
  if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
    return cryptoObj.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
}

function isValidEntry(entry) {
  return (
    entry !== null &&
    typeof entry === "object" &&
    typeof entry.id === "string" &&
    entry.id.length === 36 &&
    typeof entry.mac === "string" &&
    entry.mac.length >= 8 &&
    typeof entry.x === "number" &&
    entry.x >= 0 &&
    entry.x <= 1 &&
    typeof entry.y === "number" &&
    entry.y >= 0 &&
    entry.y <= 1
  );
}

export class TapPipeline {
  constructor(options) {
    const o = options || {};
    if (typeof o.sendTap !== "function") throw new Error("sendTap is required");
    this.storage = o.storage;
    this.target = o.target ?? TARGET;
    this.queueCapacity = o.queueCapacity ?? QUEUE_CAPACITY;
    this.backoffStartMs = o.backoffStartMs ?? BACKOFF_START_MS;
    this.backoffCapMs = o.backoffCapMs ?? BACKOFF_CAP_MS;
    this.sendTap = o.sendTap;
    this.now = o.now ?? Date.now;
    this.timers = o.timers ?? globalThis;
    this.pendingKey = o.pendingKey ?? "dent.pendingTaps";
    this.rejectedKey = o.rejectedKey ?? "dent.rejectedTaps";
    this.onAcked = o.onAcked;
    this.onRejected = o.onRejected;
    this.onThrottled = o.onThrottled;
    this.onTransient = o.onTransient;
    this.onUnaccepted = o.onUnaccepted;
    this.onCompleted = o.onCompleted;
    this.backoffMs = 0;
    this.coolingUntil = 0;
    this.completed = false;
    this.flushing = false;
    this.flushAgain = false;
    this.retryTimer = null;
    this.stopped = false;
  }

  queue() {
    try {
      const raw = this.storage.getItem(this.pendingKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(isValidEntry);
    } catch {
      return [];
    }
  }

  saveQueue(list) {
    this.storage.setItem(this.pendingKey, JSON.stringify(list));
  }

  rejectedCount() {
    try {
      const raw = this.storage.getItem(this.rejectedKey);
      const n = Number.parseInt(raw ?? "0", 10);
      return Number.isFinite(n) && n > 0 ? n : 0;
    } catch {
      return 0;
    }
  }

  recordRejection() {
    const next = this.rejectedCount() + 1;
    this.storage.setItem(this.rejectedKey, String(next));
    return next;
  }

  tap({ x, y, mac }) {
    if (this.completed) return { queued: false, reason: "complete" };
    const current = this.queue();
    if (current.length >= this.queueCapacity) return { queued: false, reason: "capacity" };
    const entry = { id: makeUUID(globalThis.crypto), mac, x, y, queuedAt: this.now() };
    try {
      this.saveQueue(current.concat([entry]));
    } catch {
      return { queued: false, reason: "storage" };
    }
    return { queued: true, entry };
  }

  removeByIds(ids) {
    const drop = new Set(ids);
    this.saveQueue(this.queue().filter((t) => !drop.has(t.id)));
  }

  markCompleted() {
    if (!this.completed) {
      this.completed = true;
      if (this.onCompleted) this.onCompleted();
    }
  }

  stopRetries() {
    this.stopped = true;
    if (this.retryTimer && typeof this.timers.clearTimeout === "function") {
      this.timers.clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }

  scheduleRetry() {
    if (this.stopped) return;
    this.backoffMs = this.backoffMs === 0 ? this.backoffStartMs : Math.min(this.backoffMs * 2, this.backoffCapMs);
    this.coolingUntil = this.now() + this.backoffMs;
    if (this.retryTimer && typeof this.timers.clearTimeout === "function") {
      this.timers.clearTimeout(this.retryTimer);
    }
    this.retryTimer = this.timers.setTimeout(() => {
      this.retryTimer = null;
      this.coolingUntil = 0;
      this.flush();
    }, this.backoffMs);
  }

  resetBackoff() {
    this.backoffMs = 0;
    this.coolingUntil = 0;
  }

  async flush() {
    if (this.flushing) {
      this.flushAgain = true;
      return;
    }
    if (this.stopped) return;
    this.flushing = true;
    try {
      while (!this.stopped) {
        const pending = this.queue();
        if (pending.length === 0) break;
        if (this.coolingUntil > this.now()) break;
        const head = pending[0];
        const outcome = await this.attempt(head);
        if (outcome === "retry") {
          this.scheduleRetry();
          break;
        }
      }
    } finally {
      this.flushing = false;
    }
    if (this.flushAgain && !this.stopped) {
      this.flushAgain = false;
      await this.flush();
    }
  }

  async attempt(entry) {
    let response;
    try {
      response = await this.sendTap(entry);
    } catch {
      if (this.onTransient) this.onTransient(entry);
      return "retry";
    }
    if (response === null || typeof response !== "object" || typeof response.status !== "number") {
      if (this.onTransient) this.onTransient(entry);
      return "retry";
    }
    const status = response.status;
    if (status >= 200 && status < 300) {
      const total = response.body && typeof response.body.total === "number" ? response.body.total : null;
      if (total === null) {
        if (this.onTransient) this.onTransient(entry);
        return "retry";
      }
      this.resetBackoff();
      this.removeByIds([entry.id]);
      if (this.onAcked) this.onAcked({ entry, total: clampTotal(total, this.target) });
      return "acked";
    }
    if (status === 429) {
      if (this.onThrottled) this.onThrottled(entry);
      return "retry";
    }
    if (status === 410) {
      this.removeByIds([entry.id]);
      this.markCompleted();
      if (this.onUnaccepted) this.onUnaccepted(entry);
      return "unaccepted";
    }
    if (status === 400 || status === 422) {
      this.removeByIds([entry.id]);
      const count = this.recordRejection();
      if (this.onRejected) this.onRejected(entry, count);
      return "rejected";
    }
    if (this.onTransient) this.onTransient(entry);
    return "retry";
  }
}
