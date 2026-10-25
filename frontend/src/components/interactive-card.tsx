import { useState, useRef, type ReactNode } from 'react';
import { motion, useMotionValue, useSpring, useReducedMotion } from 'framer-motion';

type InteractiveCardProps = {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  maxTilt?: number;
};

export function InteractiveCard({
  children,
  className = '',
  style = {},
  maxTilt = 8,
}: InteractiveCardProps) {
  const reduceMotion = useReducedMotion() ?? false;
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [spotlightPos, setSpotlightPos] = useState({ x: 50, y: 50 });

  const rawRotateX = useMotionValue(0);
  const rawRotateY = useMotionValue(0);
  const rawScale = useMotionValue(1);

  const springConfig = { stiffness: 350, damping: 25, mass: 0.2 };
  const rotateX = useSpring(rawRotateX, springConfig);
  const rotateY = useSpring(rawRotateY, springConfig);
  const scale = useSpring(rawScale, springConfig);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reduceMotion || e.pointerType !== 'mouse') return;
    const card = cardRef.current;
    if (!card) return;

    const rect = card.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;

    const normX = (px / rect.width - 0.5) * 2;
    const normY = (py / rect.height - 0.5) * 2;

    rawRotateX.set(-normY * maxTilt);
    rawRotateY.set(normX * maxTilt);
    rawScale.set(1.02);
    setSpotlightPos({
      x: Math.round((px / rect.width) * 100),
      y: Math.round((py / rect.height) * 100),
    });
  };

  const handlePointerLeave = () => {
    setIsHovered(false);
    rawRotateX.set(0);
    rawRotateY.set(0);
    rawScale.set(1);
  };

  return (
    <div
      ref={cardRef}
      onPointerEnter={() => setIsHovered(true)}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      style={{ perspective: '1000px', ...style }}
      className={`interactive-card-wrapper ${className}`}
    >
      <motion.div
        style={{
          rotateX,
          rotateY,
          scale,
          transformStyle: 'preserve-3d',
        }}
        className="interactive-card-inner"
      >
        {/* Dynamic cursor specular shine overlay */}
        <div
          className="interactive-card-shine"
          style={{
            opacity: isHovered && !reduceMotion ? 0.9 : 0,
            background: `radial-gradient(circle 240px at ${spotlightPos.x}% ${spotlightPos.y}%, rgba(232, 69, 122, 0.16), transparent 75%)`,
          }}
          aria-hidden="true"
        />
        {children}
      </motion.div>
    </div>
  );
}
