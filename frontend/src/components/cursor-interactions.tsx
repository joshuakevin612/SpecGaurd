import { useEffect } from 'react';
import { useReducedMotion } from 'framer-motion';

export function CursorInteractions() {
  const reduceMotion = useReducedMotion() ?? false;

  useEffect(() => {
    const supportsFinePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    if (reduceMotion || !supportsFinePointer) return;

    const root = document.documentElement;
    let activeSurface: HTMLElement | null = null;
    let frame = 0;
    let pointerX = window.innerWidth / 2;
    let pointerY = window.innerHeight / 3;

    const resetSurface = () => {
      if (!activeSurface) return;
      activeSurface.classList.remove('cursor-active');
      activeSurface.style.setProperty('--cursor-glow', '0');
      activeSurface.style.setProperty('--tilt-x', '0deg');
      activeSurface.style.setProperty('--tilt-y', '0deg');
      activeSurface = null;
    };

    const update = () => {
      frame = 0;
      root.style.setProperty('--cursor-light-x', `${pointerX}px`);
      root.style.setProperty('--cursor-light-y', `${pointerY}px`);

      const hovered = document.elementFromPoint(pointerX, pointerY);
      const surface = hovered instanceof Element
        ? hovered.closest<HTMLElement>('.panel')
        : null;

      if (surface !== activeSurface) resetSurface();
      activeSurface = surface;
      if (!surface) return;

      const bounds = surface.getBoundingClientRect();
      surface.classList.add('cursor-active');
      const normalizedX = Math.max(-1, Math.min(1, (pointerX - bounds.left) / bounds.width * 2 - 1));
      const normalizedY = Math.max(-1, Math.min(1, (pointerY - bounds.top) / bounds.height * 2 - 1));
      surface.style.setProperty('--cursor-x', `${((normalizedX + 1) * 50).toFixed(1)}%`);
      surface.style.setProperty('--cursor-y', `${((normalizedY + 1) * 50).toFixed(1)}%`);
      surface.style.setProperty('--tilt-x', `${(normalizedX * 0.7).toFixed(2)}deg`);
      surface.style.setProperty('--tilt-y', `${(-normalizedY * 0.7).toFixed(2)}deg`);
      surface.style.setProperty('--cursor-glow', '1');
    };

    const onPointerMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return;
      pointerX = event.clientX;
      pointerY = event.clientY;
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    const onPointerOut = (event: PointerEvent) => {
      if (event.relatedTarget !== null) return;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      resetSurface();
      root.style.removeProperty('--cursor-light-x');
      root.style.removeProperty('--cursor-light-y');
    };

    document.addEventListener('pointermove', onPointerMove, { passive: true });
    document.addEventListener('pointerout', onPointerOut);

    return () => {
      document.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('pointerout', onPointerOut);
      if (frame) window.cancelAnimationFrame(frame);
      resetSurface();
      root.style.removeProperty('--cursor-light-x');
      root.style.removeProperty('--cursor-light-y');
    };
  }, [reduceMotion]);

  return <div className="cursor-atmosphere" aria-hidden="true" />;
}
