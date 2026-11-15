
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

function ViewerScene() {
  return (
    <>
      <ambientLight intensity={0.8} />
      <pointLight position={[5, 5, 5]} intensity={1.5} />

      {/* Decorative 3D object — not real SPHEREx data */}
      <mesh>
        <sphereGeometry args={[1.2, 64, 64]} />
        <meshStandardMaterial
          color="#BD5579"
          wireframe
          transparent
          opacity={0.65}
        />
      </mesh>
    </>
  )
}

export default function SkyViewer() {
  return (
    <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
      <ViewerScene />
      <OrbitControls enableZoom enableRotate />
    </Canvas>
  )
}
