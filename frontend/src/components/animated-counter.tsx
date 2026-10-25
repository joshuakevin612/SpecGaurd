import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

type Props = {
  value: number;
  duration?: number;
  formatter?: (val: number) => string;
};

export function AnimatedCounter({
  value,
  duration = 950,
  formatter = (v) => v.toLocaleString(),
}: Props) {
  const [current, setCurrent] = useState(0);
  const reduceMotion = useReducedMotion() ?? false;

  useEffect(() => {
    if (reduceMotion) {
      setCurrent(value);
      return;
    }

    let start = 0;
    let animId = 0;
    const initial = current;

    const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4);

    const step = (now: number) => {
      if (!start) start = now;
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / duration);
      const eased = easeOutQuart(progress);
      const nextVal = Math.round(initial + (value - initial) * eased);
      setCurrent(nextVal);

      if (progress < 1) {
        animId = requestAnimationFrame(step);
      }
    };

    animId = requestAnimationFrame(step);

    return () => cancelAnimationFrame(animId);
  }, [value, duration, reduceMotion]);

  return <span className="mono num">{formatter(current)}</span>;
}
