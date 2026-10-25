import { useState, useRef, useEffect } from 'react';
import { motion, useMotionValue, useSpring, useReducedMotion } from 'framer-motion';
import { ShieldCheck, Activity, Zap, Cpu } from 'lucide-react';

export function SpecificationEnforcement() {
  const reduceMotion = useReducedMotion() ?? false;
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mouseVelocity, setMouseVelocity] = useState(0);
  const lastMousePos = useRef<{ x: number; y: number; time: number }>({ x: 0, y: 0, time: 0 });

  // Spring physics for aggressive cursor tracking
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const rawRotateX = useMotionValue(0);
  const rawRotateY = useMotionValue(0);

  const springConfig = { stiffness: 400, damping: 25, mass: 0.2 };
  const x = useSpring(rawX, springConfig);
  const y = useSpring(rawY, springConfig);
  const rotateX = useSpring(rawRotateX, springConfig);
  const rotateY = useSpring(rawRotateY, springConfig);

  const [bars, setBars] = useState([40, 75, 90, 60, 85, 95, 70, 50, 80]);

  // Dynamic visualizer frequencies responding to cursor speed and time
  useEffect(() => {
    if (reduceMotion) return;
    const interval = setInterval(() => {
      setBars((prev) =>
        prev.map((val) => {
          const boost = isHovered ? Math.random() * 50 + 40 : Math.random() * 25 + 15;
          return Math.min(100, Math.max(15, Math.round(val * 0.4 + boost)));
        }),
      );
    }, 90);
    return () => clearInterval(interval);
  }, [isHovered, reduceMotion]);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reduceMotion || e.pointerType !== 'mouse') return;
    const card = cardRef.current;
    if (!card) return;

    const rect = card.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    // Aggressive translation (up to 16px) & rotation (up to 15 degrees)
    const normX = (px - centerX) / centerX;
    const normY = (py - centerY) / centerY;

    rawX.set(normX * 16);
    rawY.set(normY * 12);
    rawRotateX.set(-normY * 16);
    rawRotateY.set(normX * 18);

    // Calculate mouse velocity for reactive spark
    const now = performance.now();
    const dt = now - lastMousePos.current.time;
    if (dt > 16) {
      const dist = Math.hypot(e.clientX - lastMousePos.current.x, e.clientY - lastMousePos.current.y);
      const vel = Math.min(100, Math.round((dist / dt) * 100));
      setMouseVelocity(vel);
      lastMousePos.current = { x: e.clientX, y: e.clientY, time: now };
    }
  };

  const handlePointerLeave = () => {
    setIsHovered(false);
    rawX.set(0);
    rawY.set(0);
    rawRotateX.set(0);
    rawRotateY.set(0);
    setMouseVelocity(0);
  };

  return (
    <div
      ref={cardRef}
      onPointerEnter={() => setIsHovered(true)}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      style={{
        perspective: '900px',
        width: '100%',
        maxWidth: '380px',
        padding: '8px',
        cursor: 'crosshair',
      }}
    >
      <motion.div
        style={{
          x,
          y,
          rotateX,
          rotateY,
          transformStyle: 'preserve-3d',
        }}
        className="spec-enforcement-badge"
        role="status"
        aria-label="Specification Enforcement Active Telemetry"
      >
        {/* Dynamic laser radar scanline across badge */}
        <div className={`spec-scanline ${isHovered ? 'active' : ''}`} aria-hidden="true" />

        {/* Ambient reactive bloom under cursor */}
        <div
          className="spec-bloom"
          style={{
            opacity: isHovered ? 0.9 : 0.35,
            filter: `blur(${isHovered ? '16px' : '8px'})`,
          }}
          aria-hidden="true"
        />

        {/* Top telemetry bar */}
        <div className="spec-header">
          <div className="spec-status-core">
            <span className="spec-pulse-ring" />
            <span className="spec-pulse-ring-outer" />
            <span className="spec-core-dot" />
          </div>
          <div className="spec-title-group">
            <span className="spec-title">SPECIFICATION ENFORCEMENT</span>
            <span className="spec-subtitle">
              {isHovered ? 'AST ENGINE // CRITICAL OVERWATCH' : 'REALTIME VERIFICATION ACTIVE'}
            </span>
          </div>
          <div className="spec-mode-pill">
            <Zap size={11} className="spec-zap-icon" />
            <span>ACTIVE</span>
          </div>
        </div>

        {/* Frequency visualizer equalizer bars */}
        <div className="spec-bars-container" aria-hidden="true">
          <div className="spec-bars-track">
            {bars.map((height, i) => (
              <span
                key={i}
                className="spec-bar"
                style={{
                  height: `${height}%`,
                  opacity: 0.35 + (height / 100) * 0.65,
                }}
              />
            ))}
          </div>
          <span className="spec-velocity-label">
            {isHovered ? `SENSITIVITY: ${(100 + mouseVelocity * 1.5).toFixed(0)}%` : 'SYSTEM NOMINAL 99.8%'}
          </span>
        </div>

        {/* Micro-telemetry footer with cyber specs */}
        <div className="spec-footer">
          <div className="spec-footer-item">
            <Cpu size={11} style={{ color: 'var(--accent)' }} />
            <span>AST PARSER: LOCK</span>
          </div>
          <div className="spec-footer-item">
            <Activity size={11} style={{ color: 'var(--status-pass)' }} />
            <span>ISOLATION: SECURE</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
