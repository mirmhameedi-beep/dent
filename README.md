# Dent

One stone. One billion taps. Nobody who starts it will finish it.

Every tap anywhere in the world carves a permanent dent into a single shared stone.
The counter is global and permanent; the Wall records everyone who ever added a dent.
App Store pitch in one line: *a multi-generational group project with no purpose.*

## Repo layout

```
app/       SwiftUI iOS app (iOS 17+, XcodeGen project, unit tests included)
backend/   FastAPI service: dents, global counter, per-device tally, Wall, public site
```

## ⚠️ Before running the app

`app/Dent/DentStore.swift` ends with a **placeholder backend URL**:

```swift
enum API {
    static let baseURL = URL(string: "https://your-backend.example.com")!
}
```

Point it at your deployed backend before building — until you do, every network call fails
(taps still work and queue up locally, then send once a backend is reachable).

## iOS app

Generate the Xcode project with [XcodeGen](https://github.com/yonaskolb/XcodeGen), then build
to a device or simulator:

```bash
cd app
xcodegen generate
open Dent.xcodeproj
# Cmd+U to run the unit tests
```

Features in this build:
- Photoreal dark stone with radial lighting, laid out via `GeometryReader`.
- Every tap carves a dent: **server-persisted**, so the stone you see is the stone *everyone*
  sees — the newest 400 dents worldwide load from `/stone`.
- Offline-first tapping: taps always work; if the network is down they persist in a local
  queue (`UserDefaults`) and flush automatically when the backend is reachable again.
- Global counter reconciles by `max()` — it can never visibly move backwards.
- Device identity survives uninstall via Keychain, so Wall names persist.
- Rigid haptics, tap-squash animation, VoiceOver labels, pull-to-refresh Wall.

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

SQLite in WAL mode with a 5s busy timeout (`DENT_DB` env var to relocate the file). Endpoints:

| Method | Path     | Purpose                                        |
|--------|----------|------------------------------------------------|
| GET    | `/`      | live public counter website (the web can tap too) |
| GET    | `/stone` | `{total, target, remaining, dents[<=400]}`     |
| POST   | `/tap`   | validated tap → dent row + counter, `429` over limit |
| GET    | `/wall`  | top tappers, `?limit=50`                       |

Rate limiting is a per-IP **and** per-device sliding window, `DENT_TAPS_PER_SECOND` taps/sec
per key (default 12). It is in-memory and per-process: run a single worker behind a proxy, or
swap `allow()` for Redis before scaling past one box.

Tests: `pytest backend` (9 tests — counter integrity, dent persistence, wall ranking,
validation, rate limiting, docs-off, site serving).

## Deploying

Any container host works (Fly.io, Railway, Render) — one process serves the API, the SQLite
store, and the public website. For launch-scale traffic on `/tap`, front it with Redis `INCR`
and flush batches; the SQLite fallback here is deliberately simple for a first deploy.

## CI

`.github/workflows/ci.yml` runs the backend suite on Linux and the app's unit tests on a
macOS runner (`xcodegen generate` + `xcodebuild test` against the iPhone 16 Simulator).
