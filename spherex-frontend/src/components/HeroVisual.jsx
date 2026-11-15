import { Canvas, useFrame } from '@react-three/fiber'
import { Stars, Float } from '@react-three/drei'
import { useRef } from 'react'

function CosmicObject() {
  const planet = useRef()
  const rings = useRef()

  useFrame((state, delta) => {
    planet.current.rotation.y += delta * 0.12
    planet.current.rotation.x += delta * 0.04

    rings.current.rotation.z += delta * 0.08
  })

  return (
    <>
      <ambientLight intensity={0.5} />

      <pointLight
        position={[3, 3, 3]}
        color="#F4AE52"
        intensity={25}
      />

      <Float speed={1.2} floatIntensity={0.4}>
        <group position={[0, 0, 0]}>

          <mesh ref={planet}>
            <icosahedronGeometry args={[1.65, 3]} />
            <meshStandardMaterial
              color="#D4621A"
              wireframe
              transparent
              opacity={0.65}
              emissive="#8B3E12"
              emissiveIntensity={0.8}
            />
          </mesh>

          <mesh scale={0.98}>
            <sphereGeometry args={[1.65, 48, 48]} />
            <meshBasicMaterial
              color="#F4AE52"
              wireframe
              transparent
              opacity={0.08}
            />
          </mesh>

          <group ref={rings}>
            <mesh rotation={[1.1, 0.3, 0]}>
              <torusGeometry args={[2.1, 0.012, 8, 120]} />
              <meshBasicMaterial color="#F4AE52" />
            </mesh>

            <mesh rotation={[1.1, 0.3, 0]}>
              <torusGeometry args={[2.35, 0.008, 8, 120]} />
              <meshBasicMaterial
                color="#D4621A"
                transparent
                opacity={0.7}
              />
            </mesh>
          </group>

        </group>
      </Float>

      <Stars
        radius={50}
        depth={30}
        count={1800}
        factor={3}
        saturation={0}
        fade
        speed={0.5}
      />
    </>
  )
}

export default function HeroVisual() {
  return (
    <div className="hero-visual">
      <Canvas camera={{ position: [0, 0, 7], fov: 45 }}>
        <CosmicObject />
      </Canvas>
    </div>
  )
}