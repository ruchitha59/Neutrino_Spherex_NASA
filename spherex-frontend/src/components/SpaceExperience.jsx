import { Canvas, useFrame, useLoader } from '@react-three/fiber'
import { Stars, Sparkles } from '@react-three/drei'
import { useRef, } from 'react'
import * as THREE from 'three'

function Nebula() {
  const material = useRef()

  useFrame((state) => {
    if (material.current) {
      material.current.uniforms.uTime.value = state.clock.elapsedTime
    }
  })

  return (
    <mesh position={[0, 0, -20]}>
      <planeGeometry args={[120, 80]} />
      <shaderMaterial
        ref={material}
        uniforms={{ uTime: { value: 0 } }}
        vertexShader={`
          varying vec2 vUv;

          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform float uTime;
          varying vec2 vUv;

          float hash(vec2 p) {
            return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
          }

          float noise(vec2 p) {
            vec2 i = floor(p);
            vec2 f = fract(p);
            f = f * f * (3.0 - 2.0 * f);

            return mix(
              mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
              mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
              f.y
            );
          }

          float fbm(vec2 p) {
            float value = 0.0;
            float amplitude = 0.5;

            for (int i = 0; i < 6; i++) {
              value += noise(p) * amplitude;
              p *= 2.0;
              amplitude *= 0.5;
            }

            return value;
          }

          void main() {
            vec2 uv = vUv;
            vec2 flow = uv * 3.0;

            flow.x += uTime * 0.018;
            flow.y += sin(uTime * 0.08 + uv.x * 4.0) * 0.08;

            float cloud = fbm(flow);
            float detail = fbm(flow * 1.8 + vec2(2.4, 1.7));
            float density = smoothstep(0.28, 0.78, cloud * 0.75 + detail * 0.35);

            vec3 deepSpace = vec3(0.012, 0.018, 0.045);
            vec3 violet = vec3(0.20, 0.12, 0.32);
            vec3 teal = vec3(0.08, 0.30, 0.34);
            vec3 amber = vec3(0.48, 0.23, 0.12);

            vec3 color = mix(deepSpace, violet, density * 0.85);

            float warmFlow = smoothstep(0.48, 0.85, fbm(flow + vec2(3.0, 1.0)));
            color = mix(color, amber, warmFlow * density * 0.55);

            float coolFlow = smoothstep(0.42, 0.82, fbm(flow + vec2(-2.0, 4.0)));
            color = mix(color, teal, coolFlow * density * 0.5);

            float edge = smoothstep(0.0, 0.22, uv.y) *
                         smoothstep(0.0, 0.22, 1.0 - uv.y);

            color *= edge * 0.65 + 0.35;

            gl_FragColor = vec4(color, 1.0);
          }
        `}
      />
    </mesh>
  )
}

// A slowly rotating planet with an optional ring.
function Planet({ position, size, texture, ringColor, tilt = 0.3 }) {
  const planet = useRef()
  const ring = useRef()
  const planetGroup = useRef()

  const surface = useLoader(THREE.TextureLoader, texture)

  useFrame((state) => {

  const scrollRange =
    document.documentElement.scrollHeight - window.innerHeight

  const progress =
    scrollRange > 0 ? window.scrollY / scrollRange : 0

  if (planetGroup.current) {
  const fadeStart = 0.90
  const fadeEnd = 1.0

  const fadeProgress = THREE.MathUtils.clamp(
    (progress - fadeStart) / (fadeEnd - fadeStart),
    0,
    1
  )

  planetGroup.current.traverse((child) => {
    if (child.isMesh && child.material) {
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material]

      materials.forEach((material) => {
        if (material.userData.baseOpacity === undefined) {
          material.userData.baseOpacity = material.opacity
        }

        material.transparent = true
        material.opacity =
          material.userData.baseOpacity * (1 - fadeProgress)
      })
    }
  })

  planetGroup.current.visible = progress < fadeEnd
}

  if (planet.current) {
    planet.current.rotation.y = state.clock.elapsedTime * 0.025
  }
})
  return (
    <group ref={planetGroup} position={position} scale={size}>
      {/* Textured planetary surface */}
      <mesh ref={planet}>
        <sphereGeometry args={[1, 128, 128]} />
        <meshStandardMaterial
          map={surface}
          roughness={0.95}
          metalness={0}
        />
      </mesh>

      {/* Atmospheric edge */}
      <mesh scale={1.025}>
        <sphereGeometry args={[1, 96, 96]} />
        <meshBasicMaterial
          color="#A9C9E8"
          transparent
          opacity={0.12}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Planetary rings */}
      {ringColor && (
        <group ref={ring} rotation={[tilt, 0, 0.25]}>
          <mesh>
            <ringGeometry args={[1.35, 2.05, 192]} />
            <meshStandardMaterial
              color={ringColor}
              side={THREE.DoubleSide}
              transparent
              opacity={0.55}
              roughness={1}
              depthWrite={false}
            />
          </mesh>
        </group>
      )}
    </group>
  )
}

function EarthEnding() {
  const earth = useRef()
  const earthSurface = useRef()
  const moonOrbit = useRef()
const moonTexture = useLoader(
  THREE.TextureLoader,
  '/textures/moon.jpg'
)

const earthTexture = useLoader(
  THREE.TextureLoader,
  '/textures/earth.png'
)

 useFrame((state) => {
  if (!earth.current) return

  const scrollRange =
    document.documentElement.scrollHeight - window.innerHeight

  const progress =
    scrollRange > 0 ? window.scrollY / scrollRange : 0

  // Earth enters during the closing section.
  const start = 0.82
  const end = 0.94

  const t = THREE.MathUtils.clamp(
    (progress - start) / (end - start),
    0,
    1
  )

  // Rise slowly from below.
  const smoothT = t * t * (3 - 2 * t)

  earth.current.position.y = THREE.MathUtils.lerp(
    -30,
    -11,
    smoothT
  )

  // Place Earth in front of the distant space background.
  earth.current.position.z = -18

  // Gentle continuous rotation.
  earthSurface.current.rotation.y =
  state.clock.elapsedTime * 0.08

    // Moon continuously revolves around Earth.
if (moonOrbit.current) {
  moonOrbit.current.rotation.y = 0.45

  moonOrbit.current.rotation.z =
    state.clock.elapsedTime * 0.2
}
})

  return (
    <group ref={earth}>


            {/* Moon orbiting Earth */}
      <group ref={moonOrbit}>
        <mesh position={[14, 2, 0]}>
          <sphereGeometry args={[1.2, 64, 64]} />
          <meshStandardMaterial
            map={moonTexture}
            roughness={0.9}
          />
        </mesh>

        
      </group>

      <group ref={earthSurface}>
      {/* Realistic Earth surface */}
<mesh>
  <sphereGeometry args={[12, 128, 128]} />
  <meshStandardMaterial
    map={earthTexture}
    roughness={1}
    metalness={0}
  />
</mesh>

      {/* Warm glowing atmosphere */}
      <mesh scale={1.06}>
        <sphereGeometry args={[10, 128, 128]} />
        <meshBasicMaterial
          color="#62D8E8"
          transparent
          opacity={0.16}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Outer glow */}
      <mesh scale={1.12}>
        <sphereGeometry args={[10, 128, 128]} />
        <meshBasicMaterial
          color="#E6A7FF"
          transparent
          opacity={0.07}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      </group>
    </group>
  )
}

const dustTailShape = new THREE.Shape()

dustTailShape.moveTo(0, 0.12)
dustTailShape.quadraticCurveTo(1.2, 0.42, 2.4, 0.25)
dustTailShape.quadraticCurveTo(3.6, 0.12, 4.8, 0.02)
dustTailShape.quadraticCurveTo(3.5, -0.18, 2.4, -0.25)
dustTailShape.quadraticCurveTo(1.2, -0.05, 0, -0.12)
dustTailShape.closePath()

function Comet() {
  const comet = useRef()

  useFrame(() => {
    if (!comet.current) return

    const scrollRange =
      document.documentElement.scrollHeight - window.innerHeight

    const progress =
      scrollRange > 0 ? window.scrollY / scrollRange : 0

    // Comet appears during the third part of the journey.
    const start = 0.42
    const end = 0.70

    const t = THREE.MathUtils.clamp(
      (progress - start) / (end - start),
      0,
      1
    )

    comet.current.visible =
      progress >= start && progress <= end

    // Travel from right to left as the user scrolls.
    comet.current.position.set(
      11 - t * 22,
      3 - t * 5,
      -12
    )
    comet.current.rotation.z = Math.sin(t * Math.PI * 2) * 0.08
    comet.current.rotation.x = Math.sin(t * Math.PI) * 0.05
  })

  return (
    <group ref={comet} visible={false}>
      {/* Glowing comet nucleus */}
      <mesh>
  <icosahedronGeometry args={[0.22, 3]} />
  <meshStandardMaterial
    color="#81766B"
    roughness={1}
    metalness={0}
  />
</mesh>

      {/* Soft comet coma */}
<mesh scale={2.8}>
  <sphereGeometry args={[0.22, 32, 32]} />
  <meshBasicMaterial
    color="#B9E5FF"
    transparent
    opacity={0.09}
    blending={THREE.AdditiveBlending}
    depthWrite={false}
  />
</mesh>

{/* Brighter inner coma */}
<mesh scale={1.8}>
  <sphereGeometry args={[0.22, 32, 32]} />
  <meshBasicMaterial
    color="#E1F4FF"
    transparent
    opacity={0.16}
    blending={THREE.AdditiveBlending}
    depthWrite={false}
  />
</mesh>

{/* Smooth curved dust tail */}
<mesh
  position={[0.2, 0.25, 0]}
  rotation={[0, 0, -0.12]}
>
  <shapeGeometry args={[dustTailShape, 32]} />
  <meshBasicMaterial
    color="#A9DFFF"
    transparent
    opacity={0.16}
    side={THREE.DoubleSide}
    blending={THREE.AdditiveBlending}
    depthWrite={false}
  />
</mesh>

      {/* Thin ion tail */}
<mesh
  position={[2.5, 0.25, -0.03]}
  rotation={[0, 0, -0.04]}
>
  <planeGeometry args={[5, 0.055, 32, 1]} />
  <meshBasicMaterial
    color="#E4F5FF"
    transparent
    opacity={0.42}
    side={THREE.DoubleSide}
    blending={THREE.AdditiveBlending}
    depthWrite={false}
  />
</mesh>

      <pointLight
        color="#9DDCFF"
        intensity={5}
        distance={8}
      />
    </group>
  )
}


// Different celestial bodies are placed at different depths.
// They gradually come closer as the camera travels forward.

function createRockGeometry(seed) {
  const geometry = new THREE.IcosahedronGeometry(1, 1)
  const positions = geometry.attributes.position

  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i)
    const y = positions.getY(i)
    const z = positions.getZ(i)

    const distortion =
      1 +
      0.22 * Math.sin(x * 9 + seed) *
      Math.cos(y * 8 + seed) *
      Math.sin(z * 7 + seed)

    positions.setXYZ(
      i,
      x * distortion,
      y * distortion,
      z * distortion
    )
  }

  geometry.computeVertexNormals()
  return geometry
}

function AsteroidBelt() {
  const belt = useRef()

  const asteroids = Array.from({ length: 45 }, (_, i) => {
    const angle = (i / 45) * Math.PI * 2
    const radius = 4.2 + (i % 5) * 0.22

   const size = 0.07 + (i % 4) * 0.035

return {
  position: [
    Math.cos(angle) * radius,
    Math.sin(angle) * 1.3,
    Math.sin(angle * 3) * 0.8
  ],
  scale: [
    size * (1 + (i % 3) * 0.3),
    size * (0.8 + (i % 4) * 0.15),
    size * (1 + (i % 5) * 0.2)
  ]
}
  })

  return (
    <group
  ref={belt}
  position={[7, 6.2, -8]}
  rotation={[0.15, 0, 0.2]}
>
      {asteroids.map((asteroid, i) => (
        <mesh
          key={i}
          position={asteroid.position}
          scale={asteroid.scale}
        >
          <primitive
  object={createRockGeometry(i)}
  attach="geometry"
/>
          <meshStandardMaterial
 color={["#777777", "#888888", "#999999", "#AAAAAA", "#666666"][i % 5]}
  roughness={1}
  metalness={0.05}
  flatShading
/>
        </mesh>
      ))}
    </group>
  )
}

function CelestialJourney() {
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight
        position={[-8, 5, 6]}
        intensity={2.2}
        color="#FFE0BD"
      />

      <pointLight
        position={[5, 2, -12]}
        intensity={35}
        distance={35}
        color="#9B8CFF"
      />

      <Planet
  position={[-7, 2, -5]}
  size={1.65}
  texture="/textures/mars.jpg"
  tilt={0.45}
/>

<Planet
  position={[3, 2, -11]}
  size={1.05}
  texture="/textures/jupiter.jpg"
  tilt={0.8}
/>



<Planet
  position={[13, -4, -10]}
  size={1.5}
  texture="/textures/neptune.jpg"
  tilt={0.35}
/>
      <AsteroidBelt />
    </>
  )
}


function MovingSpace() {
  const space = useRef()

useFrame((state) => {
  const scrollRange =
    document.documentElement.scrollHeight - window.innerHeight

  const progress =
    scrollRange > 0 ? window.scrollY / scrollRange : 0

  // Cursor controls the camera's viewing direction.
  const targetX =
    Math.sin(progress * Math.PI * 2) * 1.4 +
    state.pointer.x * 1.8

  const targetY =
    -progress * 2.5 +
    state.pointer.y * 1.1

  const targetZ = 8 - progress * 8

  // Smooth camera movement.
  state.camera.position.x = THREE.MathUtils.lerp(
    state.camera.position.x,
    targetX,
    0.035
  )

  state.camera.position.y = THREE.MathUtils.lerp(
    state.camera.position.y,
    targetY,
    0.035
  )

  state.camera.position.z = THREE.MathUtils.lerp(
    state.camera.position.z,
    targetZ,
    0.035
  )

  // Look slightly towards the cursor.
  state.camera.lookAt(
    state.pointer.x * 2,
    -progress * 2.5 + state.pointer.y * 1.2,
    -20
  )

  // Gentle continuous movement.
  if (space.current) {
    space.current.rotation.z =
      state.clock.elapsedTime * 0.008

    space.current.rotation.y =
      Math.sin(state.clock.elapsedTime * 0.04) * 0.025
  }
})

  return (
    <>
      <Nebula />

      <group ref={space}>
        <Stars
          radius={75}
          depth={55}
          count={2200}
          factor={4}
          saturation={0.25}
          fade
          speed={0.35}
        />

        <Sparkles
          count={180}
          scale={[35, 22, 35]}
          size={3}
          speed={0.25}
          opacity={0.65}
          color="#D9C5FF"
        />

        <Sparkles
          count={90}
          scale={[28, 18, 28]}
          size={5}
          speed={0.15}
          opacity={0.35}
          color="#F4AE52"
        />
      </group>

      <CelestialJourney />
      <Comet />
      <EarthEnding />
    </>
  )
}

export default function SpaceExperience() {
  return (
    <div className="space-experience">
      <Canvas
        camera={{
          position: [0, 0, 8],
          fov: 55,
          near: 0.1,
          far: 150,
        }}
        dpr={[1, 1.5]}
      >
        <MovingSpace />
      </Canvas>
    </div>
  )
}
