import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

export function AtmosphereCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const reduceMotion = useReducedMotion() ?? false;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || reduceMotion) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let animId = 0;
    let isVisible = true;
    let mouseX = -9999;
    let mouseY = -9999;
    let timestamp = 0;

    type Petal = {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      angle: number;
      vAngle: number;
      tilt: number;
      vTilt: number;
      phase: number;
      alpha: number;
      color: string;
    };

    const petals: Petal[] = [];

    const PALETTE = [
      '#E8457A', // Primary hot magenta
      '#F4789A', // Soft cherry pink
      '#FF94B4', // Light sakura pink
      '#C83468', // Deep petal rose
      '#FFAEC5', // Pale blossom highlight
    ];

    const spawn = (initial = false): Petal => ({
      x: Math.random() * (width + 100) - 50,
      y: initial ? Math.random() * height : -30,
      vx: 0.3 + Math.random() * 0.8, // gentle drift right
      vy: 0.6 + Math.random() * 1.2, // downward falling
      size: 5 + Math.random() * 7,
      angle: Math.random() * Math.PI * 2,
      vAngle: (Math.random() - 0.5) * 0.04,
      tilt: Math.random() * Math.PI,
      vTilt: 0.02 + Math.random() * 0.03,
      phase: Math.random() * Math.PI * 2,
      alpha: 0.35 + Math.random() * 0.45,
      color: PALETTE[Math.floor(Math.random() * PALETTE.length)],
    });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const targetCount = Math.min(55, Math.max(25, Math.round((width * height) / 28000)));
      while (petals.length < targetCount) petals.push(spawn(true));
      petals.length = targetCount;
    };

    const onPointerMove = (e: PointerEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    };

    const onPointerLeave = () => {
      mouseX = -9999;
      mouseY = -9999;
    };

    // Draw realistic stylized sakura petal
    const drawPetal = (p: Petal) => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle);
      // 3D tilt effect via scaleY
      const scaleY = Math.cos(p.tilt);
      ctx.scale(1, scaleY);

      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.alpha;

      ctx.beginPath();
      // Organic petal curve with notch
      ctx.moveTo(0, -p.size);
      ctx.bezierCurveTo(p.size * 0.7, -p.size * 0.6, p.size * 0.8, p.size * 0.4, 0, p.size);
      ctx.bezierCurveTo(-p.size * 0.8, p.size * 0.4, -p.size * 0.7, -p.size * 0.6, 0, -p.size);
      ctx.fill();

      // Delicate inner vein / shadow for depth
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 0.75;
      ctx.beginPath();
      ctx.moveTo(0, -p.size * 0.7);
      ctx.lineTo(0, p.size * 0.6);
      ctx.stroke();

      ctx.restore();
    };

    const render = (time: number) => {
      const dt = Math.min(40, time - timestamp || 16);
      timestamp = time;

      if (!isVisible) {
        animId = requestAnimationFrame(render);
        return;
      }

      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < petals.length; i++) {
        const p = petals[i];
        p.angle += p.vAngle;
        p.tilt += p.vTilt;

        // Flutter oscillation in breeze
        const flutter = Math.sin(p.phase + time * 0.0018);
        const drift = p.vx + flutter * 0.4;

        // Bold interactive mouse swirl: petals swirl and disperse around cursor
        const dx = p.x - mouseX;
        const dy = p.y - mouseY;
        const distSq = dx * dx + dy * dy;
        const blastRadiusSq = 35000; // ~187px radius
        if (distSq < blastRadiusSq && distSq > 0) {
          const dist = Math.sqrt(distSq);
          const force = (1 - dist / 187) * 4.5;
          // Tangential push + slight outward repulse (swirling aerodynamic wake)
          p.x += (dx / dist) * force * 1.5 - (dy / dist) * force * 1.2;
          p.y += (dy / dist) * force * 1.5 + (dx / dist) * force * 1.2;
          p.angle += 0.08 * force;
        }

        p.x += drift * dt * 0.06;
        p.y += p.vy * dt * 0.06;

        // Reset if drifted beyond view
        if (p.y > height + 40 || p.x > width + 60 || p.x < -60) {
          Object.assign(p, spawn(false));
          p.y = -20;
          p.x = Math.random() * (width + 80) - 40;
        }

        drawPetal(p);
      }

      animId = requestAnimationFrame(render);
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerleave', onPointerLeave);

    const observer = new IntersectionObserver(([entry]) => {
      isVisible = entry.isIntersecting;
    });
    observer.observe(canvas);

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerleave', onPointerLeave);
      observer.disconnect();
    };
  }, [reduceMotion]);

  if (reduceMotion) return null;

  return <canvas ref={canvasRef} className="atmosphere-canvas" aria-hidden="true" />;
}
