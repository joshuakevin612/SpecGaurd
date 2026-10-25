import { useRef, useState } from 'react';
import { Link } from 'wouter';
import { motion, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion';
import { ArrowDown, ArrowUpRight, RotateCcw } from 'lucide-react';
import { POINTER_SPRING, SCROLL_SPRING } from '@/lib/motion';

export function VerificationIntro() {
  const section = useRef<HTMLElement>(null);
  const reduced = useReducedMotion() ?? false;
  const { scrollYProgress } = useScroll({ target: section, offset: ['start start', 'end end'] });
  const progress = useSpring(scrollYProgress, SCROLL_SPRING);
  const rotateX = useTransform(progress, [0, 1], [-18, 0]);
  const rotateY = useTransform(progress, [0, .55, 1], [-25, -8, 0]);
  const rotateZ = useTransform(progress, [0, 1], [-12, 0]);
  const spread = useTransform(progress, [0, 1], [48, 0]);
  const headingY = useTransform(progress, [0, 1], [0, -36]);
  const middleX = useTransform(progress, [0, 1], [0, 18]);
  const lastX = useTransform(progress, [0, 1], [0, 36]);
  const pointerX = useSpring(0, POINTER_SPRING);
  const pointerY = useSpring(0, POINTER_SPRING);
  const [replay, setReplay] = useState(0);

  return (
    <section ref={section} className="verification-intro" aria-labelledby="intro-title">
      <div className="intro-stage">
        <div className="intro-topline" key={`top-${replay}`}><span>Python verification, from specification to evidence.</span><button className="intro-replay" onClick={() => { pointerX.jump(0); pointerY.jump(0); setReplay(value => value + 1); window.dispatchEvent(new CustomEvent('specguard:fluid-pulse', {detail:{x:innerWidth*.68,y:innerHeight*.45}})); }} aria-label="Replay introduction"><RotateCcw size={16} /> Replay</button></div>
        <div className="intro-composition">
          <motion.div className="intro-type" style={reduced ? undefined : { y: headingY }}>
            <h1 id="intro-title" aria-label="Make code keep its word." key={replay}>
              {['Make code', 'keep its', 'word.'].map((line, index) => <motion.span className="type-mask" aria-hidden="true" key={line} style={reduced ? undefined : { x: index === 1 ? middleX : index === 2 ? lastX : 0 }}><motion.span initial={reduced ? false : { y: '110%' }} animate={{ y: '0%' }} transition={{ duration: 1.1, delay: index * .12, ease: [.16, 1, .3, 1] }}>{line}</motion.span></motion.span>)}
            </h1>
          </motion.div>
          <div className="proof-stage" onPointerMove={event => {
            if (reduced || event.pointerType !== 'mouse') return;
            const bounds = event.currentTarget.getBoundingClientRect();
            pointerX.set(((event.clientX - bounds.left) / bounds.width - .5) * 12);
            pointerY.set(((event.clientY - bounds.top) / bounds.height - .5) * -12);
          }} onPointerLeave={() => { pointerX.set(0); pointerY.set(0); }}>
            <motion.div className="proof-pointer" style={reduced ? undefined : { rotateX: pointerY, rotateY: pointerX }}>
              <motion.div className="proof-press" style={reduced ? undefined : { rotateX, rotateY, rotateZ }}>
                <motion.div key={`back-${replay}`} className="proof-plate plate-back" style={reduced ? undefined : { y: spread }} initial={reduced ? false : {x:-65,opacity:0}} animate={{x:0,opacity:1}} transition={{duration:1.2,ease:[.16,1,.3,1]}} aria-hidden="true"><span>{'{ }'}</span></motion.div>
                <motion.div key={`middle-${replay}`} className="proof-plate plate-middle" initial={reduced ? false : {x:45,opacity:0}} animate={{x:0,opacity:1}} transition={{duration:1.1,delay:.12,ease:[.16,1,.3,1]}} aria-hidden="true" />
                <motion.div className="proof-plate plate-front" key={replay} initial={reduced ? false : { opacity: 0, y: 70, x: 30, scale: .92 }} animate={{ opacity: 1, y: 0, x: 0, scale: 1 }} transition={{ duration: 1.25, delay: .24, ease: [.16, 1, .3, 1] }}>
                  <div className="proof-plate-header"><span>spec → test</span><span className="proof-cross" aria-hidden="true">+</span></div>
                  <div className="proof-symbol" aria-hidden="true"><span>[</span><svg viewBox="0 0 100 80"><motion.path d="M17 40 40 63 85 17" fill="none" stroke="currentColor" strokeWidth="12" initial={reduced ? false : {pathLength:0}} animate={{pathLength:1}} transition={{duration:.7,delay:.65,ease:[.16,1,.3,1]}} /></svg><span>]</span></div>
                  <div className="proof-example"><span>Example assertion</span><code>assert cart.total == 0</code></div>
                  <div className="proof-plate-footer"><span>Requirements → evidence.</span><ArrowDown size={18} /></div>
                </motion.div>
              </motion.div>
            </motion.div>
          </div>
        </div>
        <div className="intro-bottom" key={`bottom-${replay}`}><p>Describe the behavior.<br />{' '}Test the implementation.<br />{' '}See exactly where it stands.</p><Link href="/verify" className="intro-cta" data-testid="link-dashboard-new-verify"><span>New verification</span><ArrowUpRight size={24} /></Link><a href="#workspace" className="intro-scroll"><span>Scroll to inspect</span><ArrowDown size={19} /></a></div>
        <div className="intro-rule" aria-hidden="true"><motion.div style={{scaleX: reduced ? 1 : progress}} /></div>
      </div>
    </section>
  );
}
