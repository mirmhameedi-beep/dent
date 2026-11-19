import Foundation
import simd

enum Globe {
    struct Coordinates: Equatable {
        let u: Double
        let v: Double
    }

    static func spherePoint(u: Double, v: Double) -> simd_double3 {
        let theta = 2 * .pi * u
        let latitude = (0.5 - v) * .pi
        let horizontal = cos(latitude)
        return simd_double3(
            x: horizontal * cos(theta),
            y: sin(latitude),
            z: horizontal * sin(theta)
        )
    }

    static func globe(from point: simd_double3) -> Coordinates {
        let normalized = point / max(simd_length(point), 1e-12)
        let latitude = asin(min(1, max(-1, normalized.y)))
        var theta = atan2(normalized.z, normalized.x)
        if theta < 0 { theta += 2 * .pi }
        return Coordinates(u: theta / (2 * .pi), v: 0.5 - latitude / .pi)
    }

    static func rotate(_ point: simd_double3, yaw: Double, pitch: Double) -> simd_double3 {
        let yawed = simd_double3(
            x: point.x * cos(yaw) + point.z * sin(yaw),
            y: point.y,
            z: -point.x * sin(yaw) + point.z * cos(yaw)
        )
        return simd_double3(
            x: yawed.x,
            y: yawed.y * cos(pitch) - yawed.z * sin(pitch),
            z: yawed.y * sin(pitch) + yawed.z * cos(pitch)
        )
    }

    static func unrotate(_ point: simd_double3, yaw: Double, pitch: Double) -> simd_double3 {
        let unpitched = simd_double3(
            x: point.x,
            y: point.y * cos(pitch) + point.z * sin(pitch),
            z: -point.y * sin(pitch) + point.z * cos(pitch)
        )
        return simd_double3(
            x: unpitched.x * cos(yaw) - unpitched.z * sin(yaw),
            y: unpitched.y,
            z: unpitched.x * sin(yaw) + unpitched.z * cos(yaw)
        )
    }
}
