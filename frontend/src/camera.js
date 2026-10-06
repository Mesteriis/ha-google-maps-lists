const mercator=c=>{const latitude=Math.max(-85,Math.min(85,c[1]))*Math.PI/180;return [(c[0]+180)/360,(1-Math.log(Math.tan(Math.PI/4+latitude/2))/Math.PI)/2];};
// Rotate the flat street plane so home projects into the lower right, keeping the destination centered.
export function destinationCamera(selection,width=1000,height=700){
  const center=selection.destination,options={center,pitch:0,zoom:selection.overview?13:14,bearing:0,duration:0};
  if(!selection.origin)return options;
  const a=mercator(selection.origin),b=mercator(center);let dx=a[0]-b[0];dx-=Math.round(dx);const dy=a[1]-b[1],distance=Math.hypot(dx,dy);
  if(distance<1e-8)return options;
  const x=width*.41,y=height*.39;
  options.bearing=(Math.atan2(dy,dx)-Math.atan2(y,x))*180/Math.PI;
  options.zoom=Math.max(1,Math.min(16,Math.log2(Math.hypot(x,y)/(512*distance))));
  return options;
}
