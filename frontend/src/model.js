export const MODES=['transit','driving','walking','bicycling'];
export function normalizeCardConfig(raw={}) {
  const lists=raw.lists??'all',mode=raw.default_transport??'transit';
  if(lists!=='all'&&(!Array.isArray(lists)||lists.some(x=>typeof x!=='string')))throw new Error('lists: all или список id');
  if(!MODES.includes(mode))throw new Error('Неизвестный транспорт');
  return {origin_entity:raw.origin_entity??'zone.home',lists,default_transport:mode,show_search:raw.show_search!==false};
}
export function selectPlaces(catalog,selectedIds,query='') {
  const ids=new Set(selectedIds),q=query.trim().toLocaleLowerCase('ru');
  const colors=new Map(catalog.groups.map(g=>[g.id,g.color]));
  return catalog.places.filter(p=>p.memberships.some(m=>ids.has(m.list_id)))
    .filter(p=>!q||[placeTitle(p),p.name,p.address,...p.memberships.map(m=>m.note),...catalog.groups.filter(g=>p.memberships.some(m=>m.list_id===g.id)&&ids.has(g.id)).map(g=>g.name)].join(' ').toLocaleLowerCase('ru').includes(q))
    .map(p=>({...p,color:colors.get(p.memberships.find(m=>ids.has(m.list_id)).list_id)??'#67c8d8'}));
}
export function placesGeoJSON(places) {
  return {type:'FeatureCollection',features:places.filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude))
    .map(p=>({type:'Feature',id:p.id,geometry:{type:'Point',coordinates:[p.longitude,p.latitude]},properties:{place_id:p.id,color:p.color??'#67c8d8'}}))};
}
export function safeRouteUrl(value) {
  const u=new URL(value);
  if(u.protocol!=='https:'||u.hostname!=='www.google.com'||u.pathname!=='/maps/dir/'||u.searchParams.get('api')!=='1'||u.username||u.password)throw new Error('Некорректный маршрут');
  return u.href;
}
export function placeTitle(place){return typeof place?.label==='string'&&place.label.trim()?place.label.trim():place?.name??'';}
export function placeHierarchy(catalog,groups,query=''){
  const q=query.trim().toLocaleLowerCase('ru');
  return groups.map(group=>({...group,places:catalog.places.filter(p=>p.memberships.some(m=>m.list_id===group.id))
    .filter(p=>!q||[placeTitle(p),p.name,p.address,...p.memberships.filter(m=>m.list_id===group.id).map(m=>m.note)].join(' ').toLocaleLowerCase('ru').includes(q)||group.name.toLocaleLowerCase('ru').includes(q))
    .map(p=>({...p,color:group.color}))})).filter(group=>!q||group.places.length);
}
export function safePhotoUrl(value){
  if(typeof value!=='string'||value.length>2048)return null;
  try{const u=new URL(value);if(u.protocol!=='https:'||!/^lh[3-6]\.googleusercontent\.com$/.test(u.hostname)||u.username||u.password||u.port||u.hash||!/^\/(p|gps-cs-s)\/[A-Za-z0-9_-]+/.test(u.pathname))return null;return u.href;}catch{return null;}
}
