import test from 'node:test';import assert from 'node:assert/strict';
import {StreetParticles} from '../src/particles.js';
function fixture(){
 const listeners=new Map(),frames=new Map();let serial=0,visible;
 const ctx=new Proxy({},{get:()=>()=>{}}),canvases=[];
 const media={matches:false,addEventListener:(n,f)=>listeners.set('media',f),removeEventListener:()=>listeners.delete('media')};
 const win={matchMedia:()=>media,performance:{now:()=>100},devicePixelRatio:1,requestAnimationFrame:f=>{frames.set(++serial,f);return serial;},cancelAnimationFrame:id=>frames.delete(id),IntersectionObserver:class{constructor(f){visible=f;}observe(){}disconnect(){listeners.set('observerClosed',true);}}};
 const doc={hidden:false,defaultView:win,createElement:()=>{const c={style:{},setAttribute(){},getContext:()=>ctx,remove(){c.removed=true;}};canvases.push(c);return c;},addEventListener:(n,f)=>listeners.set(n,f),removeEventListener:n=>listeners.delete(n)};
 const container={ownerDocument:doc,clientWidth:600,clientHeight:400,append(){},classList:{toggle(){},remove(){}}};
 const events=new Map(),map={on:(n,f)=>events.set(n,f),off:n=>events.delete(n),isStyleLoaded:()=>true,isMoving:()=>false,project:c=>({x:c[0]*100,y:c[1]*100}),getStyle:()=>({layers:[{id:'highway_minor',type:'line','source-layer':'transportation'},{id:'road_minor',type:'line','source-layer':'transportation'},{id:'road_major_rail',type:'line','source-layer':'transportation'},{id:'waterway',type:'line','source-layer':'waterway'}]}),queryRenderedFeatures:({layers})=>{assert.deepEqual(layers,['highway_minor','road_minor']);return [{geometry:{type:'LineString',coordinates:[[2,1],[2.1,1],[2.2,1]]}}];}};
 return {effect:new StreetParticles(container,map),frames,doc,media,listeners,events,canvases,visibility:value=>visible([{isIntersecting:value}])};
}
const selection={destination:[2.2,1],origin:[2,1],name:'Cafe',dark:true,color:'#edbd61'};
test('street animation cancels on deselection, hidden page and teardown',()=>{
 const f=fixture();f.effect.setSelection(selection);assert.ok(f.effect.paths.length);assert.equal(f.frames.size,1);
 f.doc.hidden=true;f.listeners.get('visibilitychange')();assert.equal(f.frames.size,0);
 f.doc.hidden=false;f.listeners.get('visibilitychange')();assert.equal(f.frames.size,1);
 f.visibility(false);assert.equal(f.frames.size,0);f.visibility(true);assert.equal(f.frames.size,1);
 f.effect.setSelection(null);assert.equal(f.frames.size,0);assert.equal(f.effect.paths.length,0);
 f.effect.setSelection(selection);f.effect.destroy();assert.equal(f.frames.size,0);assert.equal(f.events.size,0);assert.equal(f.listeners.has('visibilitychange'),false);assert.ok(f.canvases.every(c=>c.removed));
});
test('reduced motion uses a still image and resuming uses one animation loop',()=>{
 const f=fixture();f.media.matches=true;f.effect.setSelection(selection);assert.equal(f.frames.size,0);
 f.media.matches=false;f.listeners.get('media')();assert.equal(f.frames.size,1);f.events.get('idle')();assert.equal(f.frames.size,1);f.effect.destroy();
});
