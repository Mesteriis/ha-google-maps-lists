import test from 'node:test';import assert from 'node:assert/strict';import {destinationCamera} from '../src/camera.js';
test('destination stays centered on a flat plane and home rotates lower right',()=>{
 const a=destinationCamera({destination:[2,41],origin:[2.2,41.1]},1200,800);
 assert.deepEqual(a.center,[2,41]);assert.equal(a.pitch,0);assert.ok(a.zoom>8&&a.zoom<16);
 const lat=41.1*Math.PI/180,b=41*Math.PI/180,dx=.2/360,dy=-(Math.log(Math.tan(Math.PI/4+lat/2))-Math.log(Math.tan(Math.PI/4+b/2)))/(2*Math.PI);
 const angle=a.bearing*Math.PI/180,x=dx*Math.cos(angle)+dy*Math.sin(angle),y=-dx*Math.sin(angle)+dy*Math.cos(angle);
 assert.ok(x>0&&y>0);assert.ok(Math.abs(y/x-(800*.39)/(1200*.41))<1e-8);
});
test('missing home, coincident points, polar and dateline positions remain finite',()=>{
 for(const selection of [{destination:[2,41]},{destination:[2,41],origin:[2,41]},{destination:[179.9,89],origin:[-179.9,85]}]){
  const camera=destinationCamera(selection);assert.ok(Number.isFinite(camera.zoom)&&Number.isFinite(camera.bearing));assert.equal(camera.pitch,0);
 }
});

test('home overview stays centered without a destination selection',()=>{const camera=destinationCamera({destination:[2,41],overview:true});assert.deepEqual(camera.center,[2,41]);assert.equal(camera.zoom,13);assert.equal(camera.bearing,0);});
