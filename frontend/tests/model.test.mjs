import {placeTitle,placeHierarchy,safePhotoUrl} from '../src/model.js';
import test from 'node:test';import assert from 'node:assert/strict';
import {normalizeCardConfig,selectPlaces,placesGeoJSON} from '../src/model.js';
const catalog={version:1,revision:1,groups:[{id:'a',color:'#edbd61'},{id:'b',color:'#6f9df5'}],places:[{id:'1:2',name:'Cafe',address:'Street',latitude:41,longitude:2,memberships:[{list_id:'a',note:'first'},{list_id:'b',note:'second'}]},{id:'2:3',name:'Shop',latitude:null,longitude:null,memberships:[{list_id:'b',note:''}]}]};
test('overlap produces one marker but keeps both notes',()=>{const p=selectPlaces(catalog,['a','b'],'');assert.equal(p.length,2);const geo=placesGeoJSON(p);assert.equal(geo.features.length,1);assert.deepEqual(geo.features[0].geometry.coordinates,[2,41]);assert.equal(p[0].memberships.length,2);});
test('search matches membership notes and filters groups',()=>{assert.deepEqual(selectPlaces(catalog,['a'],'second').map(p=>p.id),['1:2']);assert.equal(selectPlaces(catalog,['a'],'Shop').length,0);});
test('many groups have no fixed count',()=>{const c={...catalog,groups:Array.from({length:40},(_,i)=>({id:'g'+i,color:'#edbd61'})),places:[{...catalog.places[0],memberships:[{list_id:'g39',note:''}]}]};assert.equal(selectPlaces(c,['g39'],'').length,1);});
test('config rejects invalid mode and ignores caller origin authority',()=>{assert.equal(normalizeCardConfig({}).default_transport,'transit');assert.throws(()=>normalizeCardConfig({default_transport:'spaceship'}));assert.throws(()=>normalizeCardConfig({lists:123}));});
import {safeRouteUrl} from '../src/model.js';
test('route URL rejects foreign origins and executable schemes',()=>{for(const url of ['javascript:alert(1)','https://evil.test/maps/dir/?api=1','https://www.google.com.evil.test/maps/dir/?api=1'])assert.throws(()=>safeRouteUrl(url));assert.ok(safeRouteUrl('https://www.google.com/maps/dir/?api=1&origin=41,2&destination=42,3').startsWith('https://www.google.com/'));});

test('hierarchy follows lists and label takes precedence without replacing original name',()=>{
 const catalog={groups:[{id:'a',name:'Food',color:'#edbd61'},{id:'b',name:'Shops',color:'#6f9df5'}],places:[{id:'1',name:'Original',label:'Моё место',memberships:[{list_id:'a',note:'Coffee'},{list_id:'b',note:'Gift'}]}]};
 assert.equal(placeTitle(catalog.places[0]),'Моё место');assert.equal(placeTitle({name:'Original',label:'  '}),'Original');
 assert.equal(selectPlaces(catalog,['a','b'],'моё').length,1);assert.equal(selectPlaces(catalog,['a'],'food').length,1);
 const tree=placeHierarchy(catalog,catalog.groups,'моё');assert.equal(tree.length,2);assert.equal(tree[0].places[0].color,'#edbd61');assert.equal(tree[1].places[0].color,'#6f9df5');
 assert.equal(placeHierarchy(catalog,catalog.groups,'not found').length,0);
});
test('place images only accept public Google photo paths, excluding contributor avatars and foreign URLs',()=>{
 assert.ok(safePhotoUrl('https://lh3.googleusercontent.com/p/AF1QExample=w600-h400-k-no'));
 assert.equal(safePhotoUrl('https://lh3.googleusercontent.com/a-/avatar'),null);
 assert.equal(safePhotoUrl('https://evil.test/p/photo'),null);
 assert.equal(safePhotoUrl('javascript:alert(1)'),null);
 assert.equal(safePhotoUrl('https://lh3.googleusercontent.com:444/p/photo'),null);
 assert.equal(safePhotoUrl('https://u@lh3.googleusercontent.com/p/photo'),null);
});
