import {streetGraph,streetJourney,walkStreet,pointAlong,preparePath} from './streets.js';
export class StreetParticles {
  constructor(container,map){
    this.container=container;this.map=map;this.document=container.ownerDocument;this.window=this.document.defaultView;
    this.base=this.document.createElement('canvas');this.flow=this.document.createElement('canvas');
    this.base.className='ghost-streets';this.flow.className='ghost-flow';this.base.setAttribute('aria-hidden','true');this.flow.setAttribute('aria-hidden','true');
    container.append(this.base,this.flow);this.context=this.flow.getContext('2d');this.background=this.base.getContext('2d');
    this.paths=[];this.visible=true;this.reduced=this.window.matchMedia('(prefers-reduced-motion: reduce)');
    this.onIdle=()=>this.rebuild();this.onMove=()=>{this.clearFrame();this.background?.clearRect(0,0,this.base.width,this.base.height);};this.onVisibility=()=>this.schedule();
    map.on('idle',this.onIdle);map.on('movestart',this.onMove);map.on('moveend',this.onIdle);
    this.document.addEventListener('visibilitychange',this.onVisibility);this.reduced.addEventListener('change',this.onVisibility);
    this.intersection=new this.window.IntersectionObserver(entries=>{this.visible=entries.some(e=>e.isIntersecting);this.schedule();});this.intersection.observe(container);
  }
  setSelection(selection){
    this.selection=selection;this.clearFrame();this.paths=[];this.container.classList.toggle('ghost-active',Boolean(selection));
    if(!selection){this.background?.clearRect(0,0,this.base.width,this.base.height);return;}
    this.rebuild();
  }
  clearFrame(){if(this.frame!=null)this.window.cancelAnimationFrame(this.frame);this.frame=null;this.context?.clearRect(0,0,this.flow.width,this.flow.height);}
  rebuild(){
    if(!this.selection||!this.map.isStyleLoaded()||this.map.isMoving()||!this.context||!this.background)return;
    const layers=this.map.getStyle().layers.filter(l=>l.type==='line'&&l['source-layer']==='transportation'&&/^(highway|road|bridge|tunnel)_/.test(l.id)&&!/rail/.test(l.id)).map(l=>l.id);
    const graph=streetGraph(layers.length?this.map.queryRenderedFeatures({layers}):[],30000);
    const {origin,destination}=this.selection;
    const journey=streetJourney(graph,origin,destination);
    const paths=journey.length>1?[journey]:[];
    this.hasJourney=journey.length>1;
    const seeds=[...graph.values()];
    for(let i=0;i<70&&seeds.length;i++){const walk=walkStreet(graph,seeds[Math.floor(i*seeds.length/70)].coordinate,40);if(walk.length>1)paths.push(walk);}
    const width=this.container.clientWidth,height=this.container.clientHeight,dpr=Math.min(this.window.devicePixelRatio||1,2);
    for(const canvas of [this.base,this.flow]){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;canvas.getContext('2d').setTransform(dpr,0,0,dpr,0,0);}
    this.paths=paths.map(path=>preparePath(path.map(c=>this.map.project(c))));this.started=this.window.performance.now();this.lastFrame=0;
    const ctx=this.background;ctx.clearRect(0,0,width,height);ctx.strokeStyle='#5b93a8';ctx.globalAlpha=.5;ctx.lineWidth=.85;ctx.beginPath();
    for(const [id,node] of graph){const a=this.map.project(node.coordinate);for(const next of node.links)if(next>id){const b=this.map.project(graph.get(next).coordinate);ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);}}ctx.stroke();ctx.globalAlpha=1;
    this.draw(this.started);this.schedule();
  }
  draw(now){
    const ctx=this.context,width=this.container.clientWidth,height=this.container.clientHeight;if(!ctx||!this.selection)return;
    ctx.clearRect(0,0,width,height);const raw=this.selection.color;const color=!this.selection.dark&&/^#[0-9a-f]{6}$/i.test(raw)?'#'+raw.slice(1).match(/../g).map(pair=>Math.round(parseInt(pair,16)*.65).toString(16).padStart(2,'0')).join(''):raw;ctx.lineCap='round';ctx.strokeStyle=color;ctx.fillStyle=color;
    this.paths.forEach((path,index)=>{
      const main=this.hasJourney&&index===0,color=main?'#ffd186':'#46c8ef';ctx.strokeStyle=color;ctx.fillStyle=color;
      ctx.globalAlpha=main?.35:.02;ctx.lineWidth=main?2:1;ctx.beginPath();path.points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
      for(let particle=0;particle<(main?18:4);particle++){
        const phase=((now-this.started)/(14000+index*1800)+particle/(main?18:4)+index*.09)%1;
        for(let tail=6;tail>0;tail--){const a=pointAlong(path,phase-tail*.003),b=pointAlong(path,phase-(tail-1)*.003);if(!a||!b||phase-tail*.003<0)continue;ctx.globalAlpha=(1-tail/7)*.6;ctx.lineWidth=1.6;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}
        const p=pointAlong(path,phase);if(p){ctx.globalAlpha=main?.95:Math.sin(phase*Math.PI)*.65;ctx.shadowColor=color;ctx.shadowBlur=main?5:0;ctx.beginPath();ctx.arc(p.x,p.y,main?2.2:1.3,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
      }
    });
    ctx.globalAlpha=1;
    for(const [coordinate,label] of [[this.selection.origin,''],[this.selection.destination,this.selection.name]]){
      if(!coordinate)continue;const p=this.map.project(coordinate);ctx.strokeStyle=label?'#ffd186':'#46c8ef';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.x,p.y,9,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.arc(p.x,p.y,3,0,Math.PI*2);ctx.fill();
      if(!label)continue;ctx.font='18px system-ui';ctx.textAlign=p.x>width*.6?'right':'left';const text=label.length>30?`${label.slice(0,29)}…`:label;ctx.fillStyle=this.selection.dark?'#e0f1f7':'#173b48';ctx.fillText(text,p.x+(ctx.textAlign==='right'?-16:16),Math.max(16,p.y-14),width*.5);
    }
  }
  schedule(){
    if(this.frame!=null)this.window.cancelAnimationFrame(this.frame);this.frame=null;
    if(!this.selection||!this.visible||this.document.hidden||this.map.isMoving())return;
    if(this.reduced.matches){this.draw(this.started||0);return;}
    if(!this.paths.length)return;
    this.frame=this.window.requestAnimationFrame(now=>{this.frame=null;if(now-this.lastFrame>=32){this.draw(now);this.lastFrame=now;}this.schedule();});
  }
  destroy(){
    this.clearFrame();this.map.off('idle',this.onIdle);this.map.off('movestart',this.onMove);this.map.off('moveend',this.onIdle);
    this.document.removeEventListener('visibilitychange',this.onVisibility);this.reduced.removeEventListener('change',this.onVisibility);this.intersection.disconnect();
    this.base.remove();this.flow.remove();this.container.classList.remove('ghost-active');this.selection=null;this.paths=[];
  }
}
