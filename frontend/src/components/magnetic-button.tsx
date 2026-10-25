import { useRef, type ReactNode } from 'react';
import { motion, useMotionValue, useSpring, useReducedMotion } from 'framer-motion';

type MagneticButtonProps = {
  children: ReactNode;
  className?: string;
  onClick?: (e: React.MouseEvent) => void;
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
  style?: React.CSSProperties;
  'data-testid'?: string;
  strength?: number;
};

export function MagneticButton({
  children,
  className = 'btn btn-primary',
  onClick,
  type = 'button',
  disabled = false,
  style = {},
  'data-testid': testId,
  strength = 14,
}: MagneticButtonProps) {
  const reduceMotion = useReducedMotion() ?? false;
  const buttonRef = useRef<HTMLButtonElement>(null);

  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);

  const springConfig = { stiffness: 450, damping: 20, mass: 0.15 };
  const x = useSpring(rawX, springConfig);
  const y = useSpring(rawY, springConfig);

  const handlePointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (reduceMotion || disabled || e.pointerType !== 'mouse') return;
    const btn = buttonRef.current;
    if (!btn) return;

    const rect = btn.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const deltaX = (e.clientX - centerX) / (rect.width / 2);
    const deltaY = (e.clientY - centerY) / (rect.height / 2);

    rawX.set(deltaX * strength);
    rawY.set(deltaY * strength);
  };

  const handlePointerLeave = () => {
    rawX.set(0);
    rawY.set(0);
  };

  return (
    <motion.button
      ref={buttonRef}
      type={type}
      className={className}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      style={{
        x,
        y,
        position: 'relative',
        ...style,
      }}
      whileTap={{ scale: 0.94 }}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      {children}
    </motion.button>
  );
}
