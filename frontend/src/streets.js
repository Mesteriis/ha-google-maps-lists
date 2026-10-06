// Decorative topology from the streets already visible on the map, not navigation data.
const valid=c=>Array.isArray(c)&&c.length>=2&&Number.isFinite(c[0])&&Number.isFinite(c[1])&&Math.abs(c[0])<=180&&Math.abs(c[1])<=90;
const key=c=>c.map(n=>n.toFixed(5)).join(',');
export function streetGraph(features,limit=10000){
  const graph=new Map();
  for(const feature of features){
    const geometry=feature.geometry;
    const lines=geometry?.type==='LineString'?[geometry.coordinates]:geometry?.type==='MultiLineString'?geometry.coordinates:[];
    for(const line of lines){
      for(let i=1;i<line.length;i++){
        const a=line[i-1],b=line[i];if(!valid(a)||!valid(b))continue;
        const ak=key(a),bk=key(b);if(ak===bk)continue;
        if((!graph.has(ak)||!graph.has(bk))&&graph.size+Number(!graph.has(ak))+Number(!graph.has(bk))>limit)continue;
        if(!graph.has(ak))graph.set(ak,{coordinate:a,links:new Set()});
        if(!graph.has(bk))graph.set(bk,{coordinate:b,links:new Set()});
        graph.get(ak).links.add(bk);graph.get(bk).links.add(ak);
      }
    }
  }
  return graph;
}
function nearest(graph,coordinate){
  if(!valid(coordinate))return null;
  let selected=null,distance=Infinity;const scale=Math.cos(coordinate[1]*Math.PI/180);
  for(const [id,node] of graph){const d=((node.coordinate[0]-coordinate[0])*scale)**2+(node.coordinate[1]-coordinate[1])**2;if(d<distance){distance=d;selected=id;}}
  return selected;
}
export function streetJourney(graph,origin,destination){
  if(!valid(origin)||!valid(destination))return [];
  // Tiny disconnected footpaths must not steal the flow from the nearby street network.
  // Select a shared component only when BOTH anchors are near its existing street nodes.
  const scale=Math.cos(origin[1]*Math.PI/180),distance=(a,b)=>Math.hypot((a[0]-b[0])*scale,a[1]-b[1]);
  const snap=Math.min(.005,Math.max(.001,distance(origin,destination)*.04));
  const seen=new Set();let start=null,end=null,best=Infinity;
  for(const seed of graph.keys()){
    if(seen.has(seed))continue;
    const queue=[seed];seen.add(seed);let a=null,b=null,ad=Infinity,bd=Infinity;
    for(let i=0;i<queue.length;i++){
      const node=graph.get(queue[i]),da=distance(node.coordinate,origin),db=distance(node.coordinate,destination);
      if(da<ad){ad=da;a=queue[i];}if(db<bd){bd=db;b=queue[i];}
      for(const next of node.links)if(!seen.has(next)){seen.add(next);queue.push(next);}
    }
    if(ad<=snap&&bd<=snap&&ad+bd<best){start=a;end=b;best=ad+bd;}
  }
  if(!start||!end)return [];
  const parents=new Map([[start,null]]),queue=[start];
  for(let i=0;i<queue.length&&!parents.has(end);i++)for(const id of graph.get(queue[i]).links)if(!parents.has(id)){parents.set(id,queue[i]);queue.push(id);}
  if(!parents.has(end))return [];
  const path=[];for(let id=end;id!==null;id=parents.get(id))path.push(graph.get(id).coordinate);
  return path.reverse();
}
export function walkStreet(graph,origin,steps=60,random=Math.random){
  let current=nearest(graph,origin),previous=null;if(!current)return [];
  const path=[graph.get(current).coordinate];
  for(let i=0;i<steps;i++){
    const all=[...graph.get(current).links],forward=all.filter(id=>id!==previous),choices=forward.length?forward:all;
    if(!choices.length)break;
    const next=choices[Math.min(choices.length-1,Math.floor(random()*choices.length))];
    previous=current;current=next;path.push(graph.get(current).coordinate);
  }
  return path;
}
export function preparePath(points){
  const cumulative=[0];for(let i=1;i<points.length;i++)cumulative.push(cumulative.at(-1)+Math.hypot(points[i].x-points[i-1].x,points[i].y-points[i-1].y));
  return {points,cumulative,length:cumulative.at(-1)};
}
export function pointAlong(path,fraction){
  const prepared=Array.isArray(path)?preparePath(path):path,{points,cumulative,length}=prepared;
  if(!points.length)return null;
  const distance=Math.max(0,Math.min(1,fraction))*length;
  let lo=1,hi=points.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(cumulative[mid]<distance)lo=mid+1;else hi=mid;}
  if(!length||points.length===1)return points[0];
  const a=points[lo-1],b=points[lo],segment=cumulative[lo]-cumulative[lo-1],t=segment?(distance-cumulative[lo-1])/segment:0;
  return {x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t};
}
