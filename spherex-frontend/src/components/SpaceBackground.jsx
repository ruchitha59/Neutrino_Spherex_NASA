
import { Canvas } from '@react-three/fiber'
import { Stars } from '@react-three/drei'

function SpaceScene() {
  return (
    <>
      <ambientLight intensity={1.5} />

      <Stars
        radius={35}
        depth={25}
        count={2500}
        factor={4}
        saturation={0}
        fade={false}
        speed={1}
      />

      <mesh position={[2, 1, -3]}>
        <sphereGeometry args={[0.7, 32, 32]} />
        <meshStandardMaterial
          color="#F4AE52"
          wireframe
          transparent
          opacity={0.35}
        />
      </mesh>

      <mesh position={[-2, -1, -4]}>
        <icosahedronGeometry args={[0.8, 2]} />
        <meshStandardMaterial
          color="#D4621A"
          wireframe
          transparent
          opacity={0.25}
        />
      </mesh>
    </>
  )
}

export default function SpaceBackground() {
  return (
    <div className="space-background">
      <Canvas camera={{ position: [0, 0, 5], fov: 60 }}>
        <SpaceScene />
      </Canvas>
    </div>
  )
}
