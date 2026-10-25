import { type ReactNode } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import { Link } from 'wouter';

type MagneticLinkProps = {
  href: string;
  className: string;
  children: ReactNode;
  testId: string;
};

export function MagneticLink({ href, className, children, testId }: MagneticLinkProps) {
  const reduceMotion = useReducedMotion() ?? false;
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 260, damping: 22, mass: 0.18 });
  const springY = useSpring(y, { stiffness: 260, damping: 22, mass: 0.18 });

  return (
    <motion.div
      className="magnetic-link-wrap"
      style={{ x: springX, y: springY }}
      onPointerMove={(event) => {
        if (reduceMotion || event.pointerType !== 'mouse') return;
        const bounds = event.currentTarget.getBoundingClientRect();
        x.set(((event.clientX - bounds.left) / bounds.width - 0.5) * 5);
        y.set(((event.clientY - bounds.top) / bounds.height - 0.5) * 4);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      <Link href={href} className={className} data-testid={testId}>
        {children}
      </Link>
    </motion.div>
  );
}
