import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';
import { useLocation } from 'wouter';
import palettes from '@/lib/fluid-palettes.json';

/** One viewport-space field flows continuously across every surface. */
export function FluidInk() {
  const reduced = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const colorRef = useRef<HTMLCanvasElement>(null);
  const [location] = useLocation();
  useEffect(() => {
    if (reduced || !canvasRef.current) return;
    const fine = matchMedia('(hover: hover) and (pointer: fine)');
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) return;
    let w = 96, h = 60, width = document.documentElement.clientWidth, height = innerHeight;
    let u = new Float32Array(0), v = new Float32Array(0), nextU = new Float32Array(0), nextV = new Float32Array(0);
    let dye = new Float32Array(0), nextDye = new Float32Array(0), pressure = new Float32Array(0), divergence = new Float32Array(0), curl = new Float32Array(0);
    let tint = new Float32Array(0), nextTint = new Float32Array(0);
    let frame = 0, previousTime = 0, lastInput = -10000, lastPointer = {x:0,y:0,t:0};
    let pixels: ImageData;
    let palettePixels = new Uint8ClampedArray(0);
    const output = canvasRef.current;
    const outputContext = output.getContext('2d');
    const colorOutput = colorRef.current;
    const colorContext = colorOutput?.getContext('2d');
    let lastScroll = scrollY, scrollImpulse = 0, scrollCurrent = 0;
    const emitter={x:0,y:0,vx:0,vy:0,ready:false};
    const nestedScroll = new WeakMap<HTMLElement,number>();
    let light = document.documentElement.dataset.theme === 'light';
    const reset = () => {
      cancelAnimationFrame(frame); frame = 0; lastPointer.t = 0;
      emitter.ready=false;emitter.vx=0;emitter.vy=0;scrollImpulse=0;scrollCurrent=0;
      u.fill(0); v.fill(0); dye.fill(0);tint.fill(0);
      outputContext?.clearRect(0,0,output.width,output.height);
      colorContext?.clearRect(0,0,width,height);
    };
    const resize = () => {
      cancelAnimationFrame(frame); frame=0;
      const oldW=w,oldH=h,oldU=u,oldV=v,oldDye=dye,oldTint=tint;
      // Fixed canvases use the layout viewport, excluding the browser scrollbar.
      // Matching CSS pixels here prevents the colored strip at the right border.
      width = document.documentElement.clientWidth; height = innerHeight;
      w = width < 650 ? 64 : 128; h = Math.max(40, Math.min(144, Math.round(w * height / width)));
      const size = w * h;
      u = new Float32Array(size); v = new Float32Array(size); nextU = new Float32Array(size); nextV = new Float32Array(size);
      dye = new Float32Array(size); nextDye = new Float32Array(size); pressure = new Float32Array(size); divergence = new Float32Array(size); curl = new Float32Array(size);
      tint=new Float32Array(size);nextTint=new Float32Array(size);
      if(oldDye.length) for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {
        const i=y*w+x,previous=Math.min(oldH-1,Math.round(y/h*oldH))*oldW+Math.min(oldW-1,Math.round(x/w*oldW));
        u[i]=oldU[previous]*w/oldW;v[i]=oldV[previous]*h/oldH;dye[i]=oldDye[previous];tint[i]=oldTint[previous];
      }
      canvas.width = w; canvas.height = h; pixels = context.createImageData(w,h);
      palettePixels = new Uint8ClampedArray(size*3);
      output.width = width; output.height = height;
      if (colorOutput) { colorOutput.width = width; colorOutput.height = height; }
      if(oldDye.length) render(performance.now());
    };
    const sample = (field:Float32Array, x:number, y:number) => {
      x = Math.max(.5,Math.min(w-1.5,x)); y = Math.max(.5,Math.min(h-1.5,y));
      const x0 = Math.floor(x), y0 = Math.floor(y), fx = x-x0, fy = y-y0, i = y0*w+x0;
      return (field[i]*(1-fx)+field[i+1]*fx)*(1-fy)+(field[i+w]*(1-fx)+field[i+w+1]*fx)*fy;
    };
    const splat = (x:number,y:number,dx:number,dy:number,strength=1,radius=.034,pigment=0) => {
      const cx=1+x/width*(w-2), cy=1+y/height*(h-2), r=w*radius*Math.min(1,1440/width);
      for(let iy=Math.max(1,Math.floor(cy-r*2));iy<Math.min(h-1,cy+r*2);iy++) {
        for(let ix=Math.max(1,Math.floor(cx-r*2));ix<Math.min(w-1,cx+r*2);ix++) {
          const i=iy*w+ix, falloff=Math.exp(-((ix-cx)**2+(iy-cy)**2)/(r*r));
          u[i]=Math.max(-130,Math.min(130,u[i]+dx/width*w*falloff*strength));
          v[i]=Math.max(-130,Math.min(130,v[i]+dy/height*h*falloff*strength));
          const added=falloff*.78*strength;
          tint[i]=(tint[i]*dye[i]+pigment*added)/(dye[i]+added+.00001);
          dye[i]=Math.min(1,dye[i]+added);
        }
      }
    };
    const step = (dt:number) => {
      const drag=Math.exp(-dt*1.1),viscosity=1-Math.exp(-dt*8);
      for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {
        const i=y*w+x, px=x-u[i]*dt, py=y-v[i]*dt;
        // Velocity diffusion couples neighboring cells: weighted liquid, not smoke.
        const averageU=(u[i-1]+u[i+1]+u[i-w]+u[i+w])*.25;
        const averageV=(v[i-1]+v[i+1]+v[i-w]+v[i+w])*.25;
        nextU[i]=(sample(u,px,py)*(1-viscosity)+averageU*viscosity)*drag;
        nextV[i]=(sample(v,px,py)*(1-viscosity)+averageV*viscosity)*drag;
      }
      [u,nextU]=[nextU,u]; [v,nextV]=[nextV,v];
      for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {const i=y*w+x;curl[i]=.5*(v[i+1]-v[i-1]-u[i+w]+u[i-w]);}
      for(let y=2;y<h-2;y++) for(let x=2;x<w-2;x++) {
        const i=y*w+x, nx=Math.abs(curl[i+1])-Math.abs(curl[i-1]), ny=Math.abs(curl[i+w])-Math.abs(curl[i-w]), length=Math.hypot(nx,ny)+.001;
        u[i]+=ny/length*curl[i]*dt*3.4; v[i]-=nx/length*curl[i]*dt*3.4;
      }
      pressure.fill(0);
      for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {const i=y*w+x;divergence[i]=-.5*(u[i+1]-u[i-1]+v[i+w]-v[i-w]);}
      for(let iteration=0;iteration<10;iteration++) for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {const i=y*w+x;pressure[i]=(divergence[i]+pressure[i-1]+pressure[i+1]+pressure[i-w]+pressure[i+w])*.25;}
      const decay=Math.exp(-dt*1.02);
      for(let y=1;y<h-1;y++) for(let x=1;x<w-1;x++) {
        const i=y*w+x; u[i]-=.5*(pressure[i+1]-pressure[i-1]); v[i]-=.5*(pressure[i+w]-pressure[i-w]);
        u[i]=Math.max(-75,Math.min(75,u[i]));v[i]=Math.max(-75,Math.min(75,v[i]));
        nextDye[i]=sample(dye,x-u[i]*dt,y-v[i]*dt)*decay;
        nextTint[i]=sample(tint,x-u[i]*dt,y-v[i]*dt);
      }
      [dye,nextDye]=[nextDye,dye];
      [tint,nextTint]=[nextTint,tint];
    };
    const render = (now:number) => {
      frame=0; const dt=Math.max(.001,Math.min(.05,(now-previousTime)/1000 || 1/60)); previousTime=now;
      // Pointer events only update a target. Deposit a continuous, sampled stroke
      // once per frame so mouse polling rate cannot change the simulation's energy.
      if(emitter.ready && now-lastPointer.t<180) {
        const follow=1-Math.exp(-dt/0.065),velocityFollow=1-Math.exp(-dt/.09);
        const x=emitter.x+(lastPointer.x-emitter.x)*follow,y=emitter.y+(lastPointer.y-emitter.y)*follow;
        const dx=x-emitter.x,dy=y-emitter.y,distance=Math.hypot(dx,dy);
        emitter.vx+=(Math.max(-1600,Math.min(1600,dx/dt))-emitter.vx)*velocityFollow;
        emitter.vy+=(Math.max(-1600,Math.min(1600,dy/dt))-emitter.vy)*velocityFollow;
        if(distance>.15) {
          const count=Math.max(1,Math.min(8,Math.ceil(distance/Math.max(4,Math.min(width,1440)*.046*.3))));
          const strength=Math.min(1,distance/(dt*300))*.5*dt*60/count;
          for(let segment=1;segment<=count;segment++) splat(emitter.x+dx*segment/count,emitter.y+dy*segment/count,emitter.vx*.7,emitter.vy*.7,strength,.046,Math.min(1,Math.hypot(emitter.vx,emitter.vy)/1300));
        }
        emitter.x=x;emitter.y=y;
      }
      scrollImpulse *= Math.exp(-dt*5);
      scrollCurrent+=(scrollImpulse-scrollCurrent)*(1-Math.exp(-dt*9));
      if(Math.abs(scrollCurrent)>1 && lastPointer.t) {
        splat(emitter.x,emitter.y,emitter.vx*.12,-scrollCurrent*1.8,.12*dt*60,.053,0);
      }
      // Bound the advection interval on slower frames rather than making large jumps.
      const substeps=Math.ceil(dt/(1/60));
      for(let iteration=0;iteration<substeps;iteration++) step(dt/substeps);
      let energy=0;
      const palette=light?palettes.light:palettes.dark;
      for(let i=0;i<dye.length;i++) {
        const offset=i*4, density=Math.max(0,Math.min(1,(dye[i]-.018)*1.6));
        const sheen=Math.min(1,Math.abs(curl[i])*.065);
        // Slow strokes carry teal ink, fast strokes iris/clay, clicks a gold core.
        // Pigment is advected with the liquid, so its behavior survives scrolling.
        const pigment=Math.min(1.999,Math.max(0,tint[i]+sheen*.12));
        const stop=Math.floor(pigment),blend=pigment-stop;
        for(let channel=0;channel<3;channel++) {
          const value=palette.colors[stop][channel]*(1-blend)+palette.colors[stop+1][channel]*blend;
          palettePixels[i*3+channel]=value;
          pixels.data[offset+channel]=255;
        }
        // The alpha filter thresholds this field after it is smoothly upscaled.
        // Full inversion swaps foreground and background together; the filter
        // leaves only a narrow antialiased transition at the contour.
        pixels.data[offset+3]=Math.round(Math.max(0,Math.min(1,(dye[i]-.06)*3.4))*255); energy+=density;
      }
      context.putImageData(pixels,0,0);
      if(outputContext) {
        outputContext.clearRect(0,0,width,height);outputContext.imageSmoothingEnabled=true;outputContext.imageSmoothingQuality='high';
        outputContext.drawImage(canvas,1,1,w-2,h-2,0,0,width,height);
      }
      if(colorContext) {
        for(let i=0;i<dye.length;i++) {
          const o=i*4, density=Math.max(0,Math.min(1,(dye[i]-.06)*3.4));
          pixels.data[o]=palettePixels[i*3];pixels.data[o+1]=palettePixels[i*3+1];pixels.data[o+2]=palettePixels[i*3+2];
          pixels.data[o+3]=Math.round(density*255);
        }
        context.putImageData(pixels,0,0);
        colorContext.clearRect(0,0,width,height);colorContext.imageSmoothingEnabled=true;colorContext.imageSmoothingQuality='high';
        // Both passes use the same field and crop. Saturated surfaces receive
        // pigment while neutral surfaces retain their paired inverse contrast.
        // No section or panel masks: strokes remain whole across every boundary.
        colorContext.drawImage(canvas,1,1,w-2,h-2,0,0,width,height);
      }
      if(!document.hidden && (now-lastInput<2300 || energy>3)) frame=requestAnimationFrame(render); else reset();
    };
    const start=()=>{lastInput=performance.now();if(!frame){previousTime=lastInput;frame=requestAnimationFrame(render);}};
    const move=(event:PointerEvent)=>{
      if(!fine.matches || event.pointerType!=='mouse' || document.hidden) return;
      const now=performance.now();
      if(!emitter.ready || now-lastPointer.t>180) {emitter.x=event.clientX;emitter.y=event.clientY;emitter.vx=0;emitter.vy=0;emitter.ready=true;}
      lastPointer={x:event.clientX,y:event.clientY,t:now};
      start();
    };
    const scroll=(event:Event)=>{
      const element=event.target instanceof HTMLElement?event.target:null;
      const position=element?element.scrollTop:scrollY;
      const previous=element?(nestedScroll.get(element) || 0):lastScroll;
      const delta=position-previous;
      if(element) nestedScroll.set(element,position);else lastScroll=position;
      scrollImpulse=Math.max(-180,Math.min(180,scrollImpulse+delta));
      // Keep the same viewport-space field alive, including while the pointer is stationary.
      if(lastPointer.t || frame) start();
    };
    const press=(event:PointerEvent)=>{
      if(event.pointerType==='touch' || (event.target instanceof Element && event.target.closest('input,textarea,select,[contenteditable="true"]'))) return;
      splat(event.clientX,event.clientY,220,-160,1.1,.059,2);start();
    };
    const pulse=(event:Event)=>{
      const detail=(event as CustomEvent<{x:number;y:number}>).detail;
      if(!detail) return;
      splat(detail.x,detail.y,80,360,1.2,.062,1.6);
      splat(detail.x+40,detail.y+22,-240,60,.7,.049,.7);
      start();
    };
    resize();
    window.addEventListener('pointermove',move,{passive:true});window.addEventListener('pointerdown',press,{passive:true});window.addEventListener('resize',resize);document.addEventListener('scroll',scroll,{capture:true,passive:true});
    window.addEventListener('specguard:fluid-pulse',pulse);document.addEventListener('visibilitychange',reset);
    const observer=new MutationObserver(()=>{light=document.documentElement.dataset.theme==='light';});observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
    return()=>{reset();observer.disconnect();window.removeEventListener('pointermove',move);window.removeEventListener('pointerdown',press);window.removeEventListener('resize',resize);document.removeEventListener('scroll',scroll,true);window.removeEventListener('specguard:fluid-pulse',pulse);document.removeEventListener('visibilitychange',reset);};
  },[reduced,location]);

  return <>
    <svg className="fluid-definitions" aria-hidden="true"><defs><filter id="fluid-reveal-edge" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB"><feComponentTransfer><feFuncA type="linear" slope="16" intercept="-7.5" /></feComponentTransfer></filter></defs></svg>
    <canvas ref={canvasRef} className="fluid-inversion-layer" aria-hidden="true" />
    <canvas ref={colorRef} className="fluid-color-layer" aria-hidden="true" />
  </>;
}
