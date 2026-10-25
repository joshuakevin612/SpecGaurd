import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useReducedMotion } from 'framer-motion';
import * as THREE from 'three';

type CursorPosition = { x: number; y: number; active: boolean };

function ShieldMesh({
  reducedMotion,
  interactive,
  cursor,
}: {
  reducedMotion: boolean;
  interactive: boolean;
  cursor: { current: CursorPosition };
}) {
  const group = useRef<THREE.Group>(null);
  const coreMaterial = useRef<THREE.MeshStandardMaterial>(null);
  const edgeLine = useRef<THREE.LineSegments>(null);
  const dynamicLight = useRef<THREE.PointLight>(null);
  const particleMaterials = useRef<Array<THREE.MeshBasicMaterial | null>>([]);

  const geometry = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(0, 1.25);
    shape.lineTo(0.9, 0.86);
    shape.lineTo(0.76, -0.36);
    shape.quadraticCurveTo(0.56, -0.96, 0, -1.35);
    shape.quadraticCurveTo(-0.56, -0.96, -0.76, -0.36);
    shape.lineTo(-0.9, 0.86);
    shape.closePath();
    return new THREE.ExtrudeGeometry(shape, {
      depth: 0.18,
      bevelEnabled: true,
      bevelSegments: 4,
      steps: 1,
      bevelSize: 0.06,
      bevelThickness: 0.05,
    });
  }, []);

  const outline = useMemo(() => new THREE.EdgesGeometry(geometry, 22), [geometry]);

  // Orbiting energy particles around the shield
  const particles = useMemo(
    () =>
      Array.from({ length: 18 }, (_, index) => {
        const angle = (index / 18) * Math.PI * 2;
        const radius = 1.55 + (index % 4) * 0.18;
        return {
          key: index,
          baseAngle: angle,
          radius,
          speed: 0.6 + (index % 3) * 0.4,
          zOffset: -0.2 + (index % 5) * 0.09,
          scale: index % 3 === 0 ? 0.05 : 0.03,
        };
      }),
    [],
  );

  useFrame((state, delta) => {
    if (!group.current || reducedMotion) return;

    const time = state.clock.getElapsedTime();
    const isActive = interactive && cursor.current.active;

    // Aggressive mouse tracking: substantial rotation & springy dampening
    const targetRotX = isActive ? -cursor.current.y * 0.52 : Math.sin(time * 0.8) * 0.08;
    const targetRotY = isActive ? cursor.current.x * 0.72 : Math.cos(time * 0.7) * 0.1;
    const targetRotZ = isActive ? (cursor.current.x * cursor.current.y) * 0.25 : 0;

    group.current.rotation.x = THREE.MathUtils.damp(group.current.rotation.x, targetRotX, 5.2, delta);
    group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, targetRotY, 5.2, delta);
    group.current.rotation.z = THREE.MathUtils.damp(group.current.rotation.z, targetRotZ, 4.0, delta);

    // Subtle breathing translation when active
    const targetZ = isActive ? 0.25 : 0;
    group.current.position.z = THREE.MathUtils.damp(group.current.position.z, targetZ, 4.0, delta);

    // Dynamic point light tracks cursor aggressively in 3D
    if (dynamicLight.current) {
      const lx = isActive ? cursor.current.x * 3.2 : Math.sin(time * 1.5) * 2;
      const ly = isActive ? cursor.current.y * 3.2 : Math.cos(time * 1.5) * 2;
      dynamicLight.current.position.x = THREE.MathUtils.damp(dynamicLight.current.position.x, lx, 6.0, delta);
      dynamicLight.current.position.y = THREE.MathUtils.damp(dynamicLight.current.position.y, ly, 6.0, delta);
      dynamicLight.current.intensity = THREE.MathUtils.damp(
        dynamicLight.current.intensity,
        isActive ? 3.8 : 1.4,
        4.0,
        delta,
      );
    }

    // Shield core emissive glow
    if (coreMaterial.current) {
      coreMaterial.current.emissiveIntensity = THREE.MathUtils.damp(
        coreMaterial.current.emissiveIntensity,
        isActive ? 1.6 : 0.45,
        5.0,
        delta,
      );
    }

    // Particle swirl acceleration on active
    const particleOpacityTarget = isActive ? 0.95 : 0.4;
    particleMaterials.current.forEach((mat) => {
      if (!mat) return;
      mat.opacity = THREE.MathUtils.damp(mat.opacity, particleOpacityTarget, 4.0, delta);
    });
  });

  return (
    <group>
      <pointLight ref={dynamicLight} position={[0, 0, 2.5]} color="#E8457A" intensity={1.6} distance={6} />
      <group ref={group}>
        <mesh geometry={geometry} castShadow receiveShadow>
          <meshStandardMaterial
            ref={coreMaterial}
            color="#120c11"
            metalness={0.88}
            roughness={0.22}
            emissive="#E8457A"
            emissiveIntensity={0.45}
          />
        </mesh>
        <lineSegments ref={edgeLine} geometry={outline} position={[0, 0, 0.12]}>
          <lineBasicMaterial color="#FF7597" transparent opacity={0.85} />
        </lineSegments>
        {/* Verification Checkmark (Glowing Mint) */}
        <mesh position={[-0.2, -0.16, 0.22]} rotation={[0, 0, -0.78]}>
          <boxGeometry args={[0.44, 0.065, 0.05]} />
          <meshStandardMaterial
            color="#38EF7D"
            metalness={0.3}
            roughness={0.2}
            emissive="#38EF7D"
            emissiveIntensity={0.6}
          />
        </mesh>
        <mesh position={[0.15, -0.005, 0.22]} rotation={[0, 0, 0.81]}>
          <boxGeometry args={[0.78, 0.065, 0.05]} />
          <meshStandardMaterial
            color="#38EF7D"
            metalness={0.3}
            roughness={0.2}
            emissive="#38EF7D"
            emissiveIntensity={0.6}
          />
        </mesh>
      </group>

      {/* Reactive Particle Field */}
      {particles.map((p) => (
        <mesh
          key={p.key}
          position={[
            Math.cos(p.baseAngle) * p.radius,
            Math.sin(p.baseAngle) * p.radius * 0.76,
            p.zOffset,
          ]}
          scale={p.scale}
        >
          <octahedronGeometry args={[1, 0]} />
          <meshBasicMaterial
            ref={(instance) => {
              particleMaterials.current[p.key] = instance;
            }}
            color={p.key % 2 === 0 ? '#E8457A' : '#FF94B4'}
            transparent
            opacity={0.3}
          />
        </mesh>
      ))}
    </group>
  );
}

export function VerificationShield() {
  const reducedMotion = useReducedMotion() ?? false;
  const [canUseWebGL, setCanUseWebGL] = useState(false);
  const [hasFinePointer, setHasFinePointer] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const cursor = useRef<CursorPosition>({ x: 0, y: 0, active: false });

  useEffect(() => {
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const updatePointerCapability = () => setHasFinePointer(finePointer.matches);
    updatePointerCapability();
    finePointer.addEventListener('change', updatePointerCapability);

    const canvas = document.createElement('canvas');
    let context: WebGLRenderingContext | WebGL2RenderingContext | null = null;
    try {
      context = canvas.getContext('webgl2') ?? canvas.getContext('webgl');
    } catch {
      context = null;
    }
    if (context) {
      context.getExtension('WEBGL_lose_context')?.loseContext();
    }
    setCanUseWebGL(Boolean(context));
    return () => finePointer.removeEventListener('change', updatePointerCapability);
  }, []);

  if (!canUseWebGL) {
    return (
      <div className="shield-static-fallback" role="img" aria-label="Shield symbol for software verification">
        <svg viewBox="0 0 64 76" aria-hidden="true">
          <path d="M32 3 59 14v21c0 18-11 29-27 38C16 64 5 53 5 35V14L32 3Z" />
          <path d="m20 37 8 8 17-18" />
        </svg>
      </div>
    );
  }

  return (
    <div
      className={`shield-renderer ${isHovered ? 'shield-renderer-active' : ''}`}
      onPointerEnter={() => setIsHovered(true)}
      onPointerMove={(event) => {
        if (reducedMotion || !hasFinePointer || event.pointerType !== 'mouse') return;
        const bounds = event.currentTarget.getBoundingClientRect();
        cursor.current = {
          x: THREE.MathUtils.clamp(((event.clientX - bounds.left) / bounds.width) * 2 - 1, -1, 1),
          y: THREE.MathUtils.clamp(1 - ((event.clientY - bounds.top) / bounds.height) * 2, -1, 1),
          active: true,
        };
      }}
      onPointerLeave={() => {
        setIsHovered(false);
        cursor.current = { x: 0, y: 0, active: false };
      }}
    >
      <Canvas
        className="shield-canvas"
        aria-label="A three-dimensional shield representing software verification"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 4.6], fov: 38 }}
        frameloop={reducedMotion || !hasFinePointer ? 'demand' : 'always'}
        gl={{ alpha: true, antialias: true }}
      >
        <ambientLight intensity={0.9} />
        <directionalLight position={[4, 4, 5]} intensity={2.4} color="#ffd4e3" />
        <directionalLight position={[-4, -3, 3]} intensity={1.8} color="#E8457A" />
        <ShieldMesh reducedMotion={reducedMotion} interactive={hasFinePointer} cursor={cursor} />
      </Canvas>
    </div>
  );
}
