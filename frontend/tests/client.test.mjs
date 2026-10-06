import test from 'node:test';import assert from 'node:assert/strict';import {PlacesClient} from '../src/client.js';
test('disconnect fences delayed catalog and unsubscribes',async()=>{let done,unsub=0,received=[];const hass={callWS:()=>new Promise(r=>done=r),connection:{subscribeMessage:async()=>()=>unsub++}};const client=new PlacesClient(hass,c=>received.push(c),()=>{});const p=client.connect();await new Promise(r=>setTimeout(r,0));client.disconnect();done({version:1,revision:1,groups:[],places:[]});await p;assert.equal(unsub,1);assert.equal(received.length,0);});
test('source error is surfaced rather than an empty success',async()=>{let error;const hass={callWS:async()=>{throw new Error('offline')},connection:{subscribeMessage:async()=>()=>{}}};const c=new PlacesClient(hass,()=>assert.fail(),e=>error=e);await c.connect();assert.ok(error);c.disconnect();});
test('same connection resubscription revision refetches offline changes',async()=>{
 let revision=1,callback,received=[];
 const connection={subscribeMessage:async cb=>{callback=cb;return()=>{};}};
 const hass={connection,callWS:async()=>({revision,groups:revision===1?['old']:['new'],places:[]})};
 const client=new PlacesClient(hass,c=>received.push(c),()=>assert.fail());await client.connect();
 revision=2;callback({revision});await new Promise(r=>setTimeout(r,0));
 assert.equal(hass.connection,connection);assert.deepEqual(received.at(-1).groups,['new']);client.disconnect();
});
