# Dent

One stone. One billion taps. Nobody who starts it will finish it.

Every tap anywhere in the world removes a microscopic sliver of a single shared stone.
The counter is global and permanent. The Wall records everyone who ever added a dent.
App Store pitch in one line: *a multi-generational group project with no purpose.*

## Repo layout

```
app/       SwiftUI iOS app (iOS 17+, XcodeGen project)
backend/   FastAPI service: global counter, per-device tally, Wall
```

## iOS app

Generate the Xcode project with [XcodeGen](https://github.com/yonaskolb/XcodeGen), then build
to a device or simulator:

```bash
cd app
xcodegen generate
open Dent.xcodeproj
```

Point the app at your backend in `app/Dent/DentStore.swift` (`API.baseURL`).

Features in this build:
- Photoreal dark stone with radial lighting, rendered in ShapeLayer-friendly SwiftUI.
- Every tap places a persistent dent at a random spot on the stone (optimistic local dent,
  confirmed by the server), with rigid haptic feedback and a spring squash.
- Live global counter with animated roll and infinite-journey progress bar.
- The Wall: anonymous tap hall-of-fame, paginated by the backend.

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

SQLite by default (`DENT_DB` env var to relocate). Endpoints:

| Method | Path     | Purpose                                    |
|--------|----------|--------------------------------------------|
| GET    | `/`      | live public counter website (viral engine)  |
| GET    | `/stone` | `{total, target, remaining}`                |
| POST   | `/tap`   | register a tap, returns new global total    |
| GET    | `/wall`  | top tappers, `?limit=50`                    |

Tests run with `pytest backend` (CI runs them on every push).

## CI

`.github/workflows/ci.yml` runs the backend test suite on Linux and compiles the iOS app on a
macOS runner (`xcodegen generate` + `xcodebuild` against the iOS Simulator, unsigned).

## Deploying

Any container host works (Fly.io, Railway, Render). For App Store launch-scale traffic on the
`/tap` endpoint, front it with a queue or Redis `INCR` and flush batches — the SQLite fallback
here is deliberately simple for a first deploy.
