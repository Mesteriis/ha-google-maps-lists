import test from 'node:test';
import assert from 'node:assert/strict';
import {streetGraph,streetJourney,walkStreet,pointAlong} from '../src/streets.js';
const line=coordinates=>({geometry:{type:'LineString',coordinates}});
const features=[line([[2,41],[2.01,41],[2.02,41]]),line([[2.01,41],[2.01,41.01]])];
test('journey and branches stay on street edges; duplicate tile geometries do not duplicate links',()=>{
 const graph=streetGraph([...features,...features]);
 assert.equal(graph.size,4);assert.equal(graph.get('2.01000,41.00000').links.size,3);
 const path=streetJourney(graph,[2,41],[2.01,41.01]);
 assert.deepEqual(path,[[2,41],[2.01,41],[2.01,41.01]]);
 const walk=walkStreet(graph,[2,41],10,()=>0);
 for(let i=1;i<walk.length;i++)assert.ok(graph.get(walk[i-1].map(n=>n.toFixed(5)).join(',')).links.has(walk[i].map(n=>n.toFixed(5)).join(',')));
});
test('disconnected streets never produce a fabricated connector',()=>{
 const graph=streetGraph([line([[2,41],[2.01,41]]),line([[3,41],[3.01,41]])]);
 assert.deepEqual(streetJourney(graph,[2,41],[3,41]),[]);
 assert.deepEqual(streetJourney(graph,null,[3,41]),[]);
});
test('invalid features are ignored and network construction is bounded',()=>{
 const graph=streetGraph([line([[NaN,41],[2,41]]),line([[2,41],[2.01,41],[2.02,41],[2.03,41]])],3);
 assert.ok(graph.size<=3);assert.deepEqual(streetGraph([]).size,0);
});
test('particle interpolation follows distance and every corner, not a straight chord',()=>{
 const path=[{x:0,y:0},{x:10,y:0},{x:10,y:30}];
 assert.deepEqual(pointAlong(path,.5),{x:10,y:10});
 assert.deepEqual(pointAlong(path,1),{x:10,y:30});
 assert.deepEqual(pointAlong([],.5),null);
});

test('nearby isolated footpaths do not replace a connected street flow',()=>{
 const roads=[[2.0001,41],[2.01,41],[2.02,41]];
 const graph=streetGraph([line([[2,41],[2,41.0001]]),line(roads)]);
 assert.deepEqual(streetJourney(graph,[2,41],[2.02,41]),roads);
});
