import {readFileSync} from 'node:fs';

const css=readFileSync(new URL('../src/design.css',import.meta.url),'utf8');
const rgb=hex=>hex.match(/[a-f\d]{2}/gi).map(value=>parseInt(value,16));
const luminance=color=>color.map(value=>value/255).map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
const inverse=color=>color.map(value=>255-value);
let failed=false;
for(const theme of ['dark','light']) {
  const block=css.match(new RegExp(`:root\\[data-theme="${theme}"\\] \\{([^}]+)`))[1];
  const tokens=Object.fromEntries([...block.matchAll(/--([\w-]+):#([a-f\d]{6})(?=[;}])/gi)].map(([,name,hex])=>[name,rgb(hex)]));
  const foregrounds=['ink','muted','status-neutral','status-pass','status-fail','status-warn'];
  const backgrounds=['bg','surface','surface-raised','surface-card'];
  if(theme==='light') tokens.placeholder=rgb('656154'),foregrounds.push('placeholder');
  let minimum=Infinity,worst='';
  for(const foreground of foregrounds) for(const background of backgrounds) {
    // Also check inverse semantic colors conservatively for inline report values.
    const states=[false,true];
    for(const inverted of states) {
      const result=contrast(inverted?inverse(tokens[foreground]):tokens[foreground],inverted?inverse(tokens[background]):tokens[background]);
      if(result<minimum) minimum=result,worst=`${foreground} on ${background}${inverted?' (revealed inverse)':''}`;
    }
  }
  console.log(`${theme}: minimum ${minimum.toFixed(2)}:1 (${worst}); checks original and fully revealed inverse text/background pairs`);
  if(minimum<4.5) failed=true;
}
if(failed) process.exitCode=1;
