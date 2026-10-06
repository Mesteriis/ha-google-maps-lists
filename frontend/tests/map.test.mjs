import test from 'node:test';import assert from 'node:assert/strict';import {PlacesMap} from '../src/map.js';
class Engine {
 constructor(){this.events={};this.sources={};this.fit=[];this.layers=[];this.style=true;}
 on(name,...args){this.events[name]=args.at(-1);} isStyleLoaded(){return this.style;} getSource(id){return this.sources[id];}
 addSource(id,source){this.sources[id]={...source,setData:data=>this.sources[id].data=data};} getLayer(id){return this.layers.find(l=>l.id===id);} addLayer(layer){this.layers.push(layer);}
 fitBounds(bounds){this.fit.push(bounds);} easeTo(value){this.center=value;} setStyle(url,options){this.sources={};this.layers=[];if(options?.diff===false)this.events['style.load']?.();} resize(){this.resized=true;} remove(){this.removed=true;}
 getCanvas(){return {style:{}};}
}
const place={id:'1:2',name:'Cafe',latitude:41,longitude:2,color:'#edbd61'};
test('theme rebuild preserves places and empty does not fit invalid bounds',()=>{
 const view=new PlacesMap({},()=>{}, {Map:Engine},()=>{});view.setPlaces([place]);assert.equal(view.map.getSource('saved').data.features.length,1);
 view.setTheme(false);assert.equal(view.map.getSource('saved').data.features.length,1);
 view.setPlaces([]);assert.equal(view.map.fit.length,0);const engine=view.map;view.destroy();assert.equal(engine.removed,true);
});
test('hidden tab resize is forwarded and source error keeps place data',()=>{
 let error;const view=new PlacesMap({},()=>{}, {Map:Engine},e=>error=e);view.setPlaces([place]);view.resize();view.map.events.error({error:Error('tiles')});
 assert.ok(error);assert.equal(view.places.length,1);assert.equal(view.map.resized,true);
});
test('style.load reattaches saved markers while base tiles are loading',()=>{
 const view=new PlacesMap({},()=>{}, {Map:Engine},()=>{});view.setPlaces([place]);
 view.map.style=false;view.setTheme(false);assert.equal(view.map.getSource('saved').data.features.length,1);
});
test('selection centers destination; refresh does not reset selection and closing restores all places',()=>{
 const view=new PlacesMap({},()=>{}, {Map:Engine},()=>{});view.setPlaces([place]);
 const selected={id:place.id,destination:[2,41],origin:[2.1,41.1],color:'#edbd61',dark:true};
 view.setSelection(selected);assert.deepEqual(view.map.center.center,[2,41]);assert.equal(view.map.center.pitch,0);
 view.setPlaces([place]);view.setSelection({...selected});assert.equal(view.map.fit.length,0);
 view.setSelection(null);assert.deepEqual(view.map.center.center,[2,41]);view.destroy();
});
