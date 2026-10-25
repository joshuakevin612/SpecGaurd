import { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion';
import { SCROLL_SPRING } from '@/lib/motion';

const steps=[
  ['01','Write the contract','Tell SpecGuard what your Python code should do. Supply your implementation alongside it.'],
  ['02','Run the challenge','Generate requirement-linked tests and execute them in an isolated sandbox.'],
  ['03','Read the evidence','Inspect passing and failing assertions, review proposed fixes, and retest.'],
];

function MethodStep({step}:{step:string[]}) {
  const ref=useRef<HTMLDivElement>(null);
  const reduced=useReducedMotion();
  const {scrollYProgress}=useScroll({target:ref,offset:['start 92%','end 30%']});
  const progress=useSpring(scrollYProgress,SCROLL_SPRING);
  const y=useTransform(progress,[0,.5,1],[30,0,-6]);
  const x=useTransform(progress,[0,.5,1],[12,0,0]);
  const rule=useTransform(progress,[0,.55],[0,1]);
  const numberY=useTransform(progress,[0,1],[14,-8]);
  return <div ref={ref} className="method-row">
    <motion.span className="method-sequence-rule" style={reduced?undefined:{scaleX:rule}} aria-hidden="true" />
    <motion.span className="method-number" style={reduced?undefined:{y:numberY}}>{step[0]}</motion.span>
    <motion.div style={reduced?undefined:{x,y}}><h3>{step[1]}</h3><p>{step[2]}</p></motion.div>
  </div>;
}

export function MethodSequence() {
  const ref=useRef<HTMLElement>(null);
  const reduced=useReducedMotion();
  const {scrollYProgress}=useScroll({target:ref,offset:['start end','end start']});
  const progress=useSpring(scrollYProgress,SCROLL_SPRING);
  const headingY=useTransform(progress,[0,.4,1],[24,0,-14]);
  const lineX=useTransform(progress,[0,.4,1],[12,0,-8]);
  return <section ref={ref} className="method-section method-sequence" aria-labelledby="method-title">
    <div className="method-intro">
      <motion.h2 id="method-title" style={reduced?undefined:{y:headingY}}>Written intent.<br />{' '}<motion.span style={reduced?undefined:{x:lineX}}>Executable evidence.</motion.span></motion.h2>
      <p>Every result traces back to a written requirement. Follow the evidence from the first assertion to the final report.</p>
    </div>
    <div className="method-steps">{steps.map(step=><MethodStep key={step[0]} step={step} />)}</div>
  </section>;
}
