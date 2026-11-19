import SwiftUI
import SceneKit

struct Stone3DView: UIViewRepresentable {
    @EnvironmentObject private var store: DentStore

    func makeCoordinator() -> Coordinator {
        Coordinator(store: store)
    }

    func makeUIView(context: Context) -> SCNView {
        let scene = SCNScene()

        let sphere = SCNSphere(radius: 1)
        sphere.segmentCount = 128
        let material = SCNMaterial()
        material.lightingModel = .physicallyBased
        material.diffuse.contents = UIColor(red: 0.30, green: 0.30, blue: 0.31, alpha: 1)
        material.roughness.contents = 0.92
        material.metalness.contents = 0.05
        sphere.materials = [material]

        let stoneNode = SCNNode(geometry: sphere)
        stoneNode.name = "stone"

        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.camera?.fieldOfView = 46
        camera.position = SCNVector3(0, 0, 3.4)
        scene.rootNode.addChildNode(camera)

        let keyLight = SCNNode()
        keyLight.light = SCNLight()
        keyLight.light?.type = .directional
        keyLight.light?.intensity = 950
        keyLight.eulerAngles = SCNVector3(-0.55, 0.5, 0)
        scene.rootNode.addChildNode(keyLight)

        let fillLight = SCNNode()
        fillLight.light = SCNLight()
        fillLight.light?.type = .ambient
        fillLight.light?.intensity = 320
        fillLight.light?.color = UIColor(white: 0.55, alpha: 1)
        scene.rootNode.addChildNode(fillLight)

        let view = SCNView()
        view.scene = scene
        view.backgroundColor = .black
        view.antialiasingMode = .multisampling4X
        view.allowsCameraControl = false
        view.isUserInteractionEnabled = true

        context.coordinator.attach(stone: stoneNode, view: view)
        view.addGestureRecognizer(
            UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.onPan(_:)))
        )
        view.addGestureRecognizer(
            UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.onTap(_:)))
        )
        return view
    }

    func updateUIView(_ uiView: SCNView, context: Context) {
        context.coordinator.syncDents(store.dents)
    }

    final class Coordinator: NSObject {
        private let store: DentStore
        private weak var stoneNode: SCNNode?
        private weak var scnView: SCNView?

        init(store: DentStore) {
            self.store = store
        }

        func attach(stone: SCNNode, view: SCNView) {
            stoneNode = stone
            scnView = view
        }

        func syncDents(_ dents: [Dent]) {
            guard let stoneNode else { return }
            stoneNode.enumerateChildNodes { node, _ in
                if node.name == "dent" {
                    node.removeFromParentNode()
                }
            }
            let geometryRadius = (stoneNode.geometry as? SCNSphere)?.radius ?? 1
            let embeddedSurface = Double(geometryRadius) * 0.982
            for dent in dents.prefix(DentStore.maxVisibleDents) {
                let crater = SCNSphere(radius: 0.034)
                let material = SCNMaterial()
                material.lightingModel = .constant
                material.diffuse.contents = UIColor(white: 0.03, alpha: 1)
                crater.materials = [material]

                let node = SCNNode(geometry: crater)
                node.name = "dent"
                let surface = Globe.spherePoint(u: Double(dent.position.x), v: Double(dent.position.y))
                node.position = SCNVector3(
                    surface.x * embeddedSurface,
                    surface.y * embeddedSurface,
                    surface.z * embeddedSurface
                )
                stoneNode.addChildNode(node)
            }
        }

        @objc func onPan(_ gesture: UIPanGestureRecognizer) {
            guard let stoneNode else { return }
            let translation = gesture.translation(in: gesture.view)
            gesture.setTranslation(.zero, in: gesture.view)
            stoneNode.eulerAngles.y += Float(translation.x) * 0.01
            stoneNode.eulerAngles.x = max(-1.1, min(1.1, stoneNode.eulerAngles.x + Float(translation.y) * 0.008))
        }

        @objc func onTap(_ gesture: UITapGestureRecognizer) {
            guard let scnView, let stoneNode else { return }
            let location = gesture.location(in: scnView)
            let hits = scnView.hitTest(location, options: [
                SCNHitTestOption.searchMode: SCNHitTestSearchMode.closest.rawValue
            ])
            guard let hit = hits.first(where: { $0.node === stoneNode }) else { return }
            let local = stoneNode.convertPosition(hit.worldCoordinates, from: nil)
            let point = simd_double3(x: Double(local.x), y: Double(local.y), z: Double(local.z))
            guard simd_length(point) > 0.85 else { return }
            let coordinates = Globe.globe(from: point)
            UIImpactFeedbackGenerator(style: .rigid).impactOccurred()
            store.tap(position: CGPoint(x: coordinates.u, y: coordinates.v))
        }
    }
}
