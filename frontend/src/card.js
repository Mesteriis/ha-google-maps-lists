import {LitElement,html,nothing} from 'lit';
import * as maplibregl from 'maplibre-gl';
import {styles} from './styles.js';
import {normalizeCardConfig,selectPlaces,safeRouteUrl,placeTitle,placeHierarchy,safePhotoUrl} from './model.js';
import {PlacesClient} from './client.js';
import {PlacesMap} from './map.js';
maplibregl.setWorkerUrl(new URL('./maplibre-worker.mjs',import.meta.url).href);
const ERROR={source_timeout:'Google не ответил вовремя',source_unavailable:'Источник временно недоступен',schema_changed:'Google изменил формат списка',potentially_incomplete:'Список слишком большой: загрузка может быть неполной',blocked_source:'Источник не прошёл проверку ссылки',cache_invalid:'Кэш недоступен — ожидаем новую загрузку',cache_write_failed:'Не удалось сохранить обновление',home_unavailable:'Координаты дома недоступны',unknown_place:'Место больше не доступно',place_has_no_coordinates:'У места нет координат',notify_unavailable:'Телефон пока недоступен',notify_failed:'Не удалось отправить на телефон'};
export class BelovodiePlacesCard extends LitElement {
  static styles=styles;
  static properties={catalog:{state:true},selectedIds:{state:true},query:{state:true},selectedId:{state:true},mode:{state:true},feedback:{state:true},pending:{state:true},connectionError:{state:true},mapError:{state:true},rowLimit:{state:true},openGroupIds:{state:true},placeDetail:{state:true},detailsPending:{state:true},detailError:{state:true},photoFailed:{state:true},drawerOpen:{state:true}};
  constructor(){super();this.selectedIds=null;this.query='';this.feedback='';this.mode='transit';this.rowLimit=80;this.catalog=null;this.onKey=e=>this.handleKey(e);}
  setConfig(raw){this._config=normalizeCardConfig(raw);this.mode=this._config.default_transport;this.selectedIds=null;this.selectedId=null;this.openGroupIds=null;this.placeDetail=null;this._detailRequest=null;this.detailsPending=false;this.rowLimit=80;this.requestUpdate();this.connectClient();}
  getCardSize(){return 10;}
  set hass(value){const old=this._hass;this._hass=value;if(this.client)this.client.hass=value;
    if(old?.connection!==value?.connection){this.client?.disconnect();this.client=null;this.connectClient();}
    this.mapView?.setTheme(value?.themes?.darkMode??true);this.requestUpdate();
  }
  get hass(){return this._hass;}
  connectedCallback(){super.connectedCallback();this.addEventListener('keydown',this.onKey);this.requestUpdate();this.connectClient();}
  disconnectedCallback(){super.disconnectedCallback();this.removeEventListener('keydown',this.onKey);this.client?.disconnect();this.client=null;this.observer?.disconnect();this.mapView?.destroy();this.mapView=null;this._paintConfig=null;this._detailRequest=null;}
  connectClient(){
    if(!this.isConnected||!this._config||!this._hass?.connection||this.client)return;
    this.client=new PlacesClient(this._hass,data=>{this.catalog=data;this.connectionError='';
      const valid=new Set(this.groups.map(g=>g.id));if(this.selectedIds)this.selectedIds=this.selectedIds.filter(id=>valid.has(id));
      if(this.selectedId&&!data.places.some(p=>p.id===this.selectedId))this.selectedId=null;
      if(!this.selectedId)this.selectedId=this.places[0]?.id;
    },()=>{this.connectionError='Нет подключения к спискам. Проверьте интеграцию Google Maps Lists.';});
    this.client.connect();
  }
  get groups(){const all=this.catalog?.groups??[];return this._config?.lists==='all'?all:(this._config?.lists??[]).map(id=>all.find(g=>g.id===id)).filter(Boolean);}
  get activeIds(){return this.selectedIds??this.groups.map(g=>g.id);}
  get places(){return this.catalog?selectPlaces(this.catalog,this.activeIds,this.query):[];}
  get selected(){const p=this.catalog?.places.find(p=>p.id===this.selectedId);return p?{...p,...(this.placeDetail?.id===p.id?this.placeDetail:{})}:null;}
  async updated(){
    if(!this._config)return;
    const container=this.renderRoot.querySelector('.map');
    if(!container&&this.mapView){this.observer?.disconnect();this.mapView.destroy();this.mapView=null;this._paintConfig=null;}
    if(container&&!this.mapView){try{
      this.mapView=new PlacesMap(container,id=>this.openDetails(id),maplibregl,()=>{this.mapError='Карта временно недоступна. Места доступны в списке.';});
      this.mapView.setTheme(this._hass?.themes?.darkMode??true);
      this.observer=new ResizeObserver(()=>this.mapView?.resize());this.observer.observe(container);
    }catch{this.mapError='Карта недоступна на этом устройстве. Используйте список мест.';}}
    if(this.mapView&&(this._paintConfig!==this._config||this._paintCatalog!==this.catalog||this._paintIds!==this.selectedIds||this._paintQuery!==this.query)){
      this._paintConfig=this._config;this._paintCatalog=this.catalog;this._paintIds=this.selectedIds;this._paintQuery=this.query;this.mapView.setPlaces(this.places);
    }
    const p=this.selected,home=this._hass?.states?.[this._config.origin_entity];
    const valid=(lat,lon)=>Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180;
    const lat=home?.attributes?.latitude,lon=home?.attributes?.longitude;
    const origin=home&&!['unavailable','unknown'].includes(home.state)&&valid(lat,lon)?[lon,lat]:null;
    const color=this.places.find(place=>place.id===p?.id)?.color??this.groups.find(g=>p?.memberships.some(m=>m.list_id===g.id))?.color??'#67c8d8';
    this.mapView?.setSelection(p&&valid(p.latitude,p.longitude)?{id:p.id,name:placeTitle(p),destination:[p.longitude,p.latitude],origin,color,dark:this._hass?.themes?.darkMode??true}:null);
  }
  toggleTreeGroup(id){const ids=new Set(this.openGroupIds??[this.groups[0]?.id]);if(ids.has(id))ids.delete(id);else ids.add(id);this.openGroupIds=[...ids];}
  async openDetails(id){this._detailRequest=null;this.drawerOpen=false;this.selectedId=id;this.feedback='';this.routeLink=null;this.placeDetail=null;this.photoFailed=false;this.mapError='';this.detailsPending=false;this.restorePlaceId=id;}
  async showDrawer(){this.drawerOpen=true;await this.updateComplete;this.renderRoot.querySelector('.drawer-close')?.focus();if(!this.placeDetail)this.loadDetails();}
  async loadDetails(){
    const id=this.selectedId;if(!id)return;const request={};this._detailRequest=request;this.detailsPending=true;this.detailError='';
    try{const data=await this._hass.callWS({type:'google_maps_lists/details',place_id:id});if(this._detailRequest===request&&this.selectedId===id)this.placeDetail={...data,id};}
    catch{if(this._detailRequest===request)this.detailError='Фото пока недоступно';}
    finally{if(this._detailRequest===request)this.detailsPending=false;}
  }
  closeDetails(){this.drawerOpen=false;this.updateComplete.then(()=>this.renderRoot.querySelector('.details-button')?.focus());}
  handleKey(e){
    if(!this.drawerOpen)return;
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();this.closeDetails();}
    if(e.key==='Tab'){
      const controls=[...this.renderRoot.querySelector('.drawer').querySelectorAll('button,a[href]')].filter(el=>!el.disabled);
      const first=controls[0],last=controls.at(-1),active=this.renderRoot.activeElement;
      if(e.shiftKey&&active===first){e.preventDefault();last?.focus();}
      else if(!e.shiftKey&&active===last){e.preventDefault();first?.focus();}
    }
  }
  async route(phone=false){
    if(this.pending||!this.selected)return;const place_id=this.selectedId,mode=this.mode;
    const tab=phone?null:window.open('about:blank','_blank');if(tab)tab.opener=null;
    this.pending=true;this.feedback='';
    try{const response=await this._hass.callWS({type:phone?'google_maps_lists/send_to_phone':'google_maps_lists/route',place_id,mode});
      if(phone)this.feedback='Отправлено в приложение телефона';
      else {this.routeLink=safeRouteUrl(response.url);if(tab)tab.location.href=this.routeLink;else this.feedback='Открыть маршрут:';}
    }catch(err){tab?.close();this.feedback=ERROR[err?.message]??'Не удалось выполнить действие. Попробуйте ещё раз.';}
    finally{this.pending=false;}
  }
  renderStatus(){
    const groups=this.groups,errors=groups.filter(g=>g.error),waiting=groups.filter(g=>!g.last_success),stale=groups.filter(g=>g.stale&&g.last_success),collision=groups.some(g=>g.color_collision);
    let text=this.connectionError||ERROR[this.catalog?.collection_error];
    if(!text&&errors.length)text=errors.slice(0,2).map(g=>`${g.name}: ${ERROR[g.error]??'Ошибка обновления'}`).join(' · ')+(errors.length>2?` · ещё ${errors.length-2} списков`: '');
    if(!text&&waiting.length)text='Ожидаем загрузку списков';
    if(!text&&stale.length)text='Сохранённые данные устарели';
    if(!text&&collision)text='У списков совпадают цвета — можно изменить color в YAML';
    if(!text&&groups.length){const at=groups.map(g=>g.last_success).filter(Boolean).sort()[0];if(at)text=`Обновлено ${new Intl.DateTimeFormat('ru',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(at))}`;}
    return text?html`<div class=${`status ${errors.length||this.connectionError?'error':''}`} role="status">${text}</div>`:nothing;
  }
  renderSummary(){const p=this.selected;if(!p)return nothing;const mapped=Number.isFinite(p.latitude)&&Number.isFinite(p.longitude);
    const group=this.groups.find(g=>p.memberships.some(m=>m.list_id===g.id));
    return html`<section class="place-summary glass" aria-labelledby="summary-title"><div class="eyebrow">${group?.name??'Выбранное место'}</div><h2 id="summary-title">${placeTitle(p)}</h2>
      <div class="actions"><button class="icon-action" aria-label="Открыть маршрут в Google Maps" title="Google Maps" ?disabled=${this.pending||!mapped} @click=${()=>this.route(false)}><ha-icon icon="mdi:navigation-outline"></ha-icon></button>
      <button class="icon-action" aria-label="Отправить маршрут на телефон" title="На телефон" ?disabled=${this.pending||!mapped} @click=${()=>this.route(true)}><ha-icon icon="mdi:cellphone"></ha-icon></button>
      <button class="details-button" @click=${()=>this.showDrawer()}><ha-icon icon="mdi:image-text"></ha-icon>Описание и фото</button></div>
      <select aria-label="Вид транспорта" .value=${this.mode} @change=${e=>this.mode=e.target.value}><option value="transit">Транспорт</option><option value="driving">Машина</option><option value="walking">Пешком</option><option value="bicycling">Велосипед</option></select>
      ${!mapped?html`<div class="status">У места нет координат</div>`:nothing}${this.pending?html`<div role="status" class="feedback">Подготавливаем…</div>`:nothing}${this.feedback?html`<div role="status" class="feedback">${this.feedback}${this.routeLink?html`<a href=${this.routeLink} target="_blank" rel="noopener noreferrer">Google Maps</a>`:nothing}</div>`:nothing}</section>`;
  }
  renderDetails(){const p=this.selected;if(!p||!this.drawerOpen)return nothing;const photo=this.photoFailed?null:safePhotoUrl(p.photo_url);
    return html`<button class="drawer-scrim" aria-label="Закрыть описание" tabindex="-1" @click=${()=>this.closeDetails()}></button><section class="drawer glass" role="dialog" aria-modal="true" aria-labelledby="place-title">
      <header class="drawer-header"><h2 id="place-title">${placeTitle(p)}</h2><button class="drawer-close icon-action" aria-label="Закрыть описание и фото" @click=${()=>this.closeDetails()}><ha-icon icon="mdi:close"></ha-icon></button></header>
      ${photo?html`<div class="photo-frame"><img class="place-photo" src=${photo} alt=${placeTitle(p)} referrerpolicy="no-referrer" @error=${()=>this.photoFailed=true}><a class="photo-credit" href=${p.google_maps_url} target="_blank" rel="noopener noreferrer">Google Maps</a></div>`:html`<div class="photo-empty" role="status"><ha-icon icon="mdi:image-outline"></ha-icon>${this.detailsPending?'Загружаем фото…':this.detailError||'Фото пока недоступно'}</div>`}
      ${p.label&&p.label.trim()!==p.name?html`<p class="original-name">${p.name}</p>`:nothing}<p class="detail-address">${p.address||'Адрес не указан'}</p>
      ${p.category?html`<p>${p.category}${p.rating?html` · ★ ${p.rating}`:nothing}</p>`:nothing}
      <section class="notes"><h3>Моё примечание</h3>${p.memberships.some(m=>m.note)?p.memberships.filter(m=>m.note).map(m=>html`<div class="membership"><div class="membership-title">${this.catalog.groups.find(g=>g.id===m.list_id)?.name??m.list_id}</div><p class="note">${m.note}</p></div>`):html`<p class="muted">Примечание не добавлено</p>`}</section></section>`;
  }
  renderTree(){
    const tree=this.catalog?placeHierarchy(this.catalog,this.groups,this.query):[],open=new Set(this.openGroupIds??[this.groups[0]?.id]);
    return html`<div class="tree" aria-label="Списки сохранённых мест">${tree.map(g=>{const expanded=Boolean(this.query.trim())||open.has(g.id);return html`<section class="tree-group" style=${`--group-color:${g.color}`}><button class="tree-header" aria-expanded=${expanded} aria-controls=${`list-${g.id}`} @click=${()=>this.toggleTreeGroup(g.id)}><ha-icon .icon=${g.icon}></ha-icon><span>${g.name}</span><span class="count">${g.places.length}</span><span class="disclosure" aria-hidden="true">${expanded?'−':'+'}</span></button>${expanded?html`<div class="tree-rows" id=${`list-${g.id}`} role="group" aria-label=${g.name}>${g.places.slice(0,this.rowLimit).map(p=>html`<button class=${`row ${p.id===this.selectedId?'selected':''}`} aria-pressed=${p.id===this.selectedId} data-place-id=${p.id} @click=${()=>this.openDetails(p.id)}><span class="dot"></span><span class="row-text"><span class="name">${placeTitle(p)}</span>${p.label&&p.label.trim()!==p.name?html`<span class="original-name">${p.name}</span>`:nothing}${p.address?html`<span class="address">${p.address}</span>`:nothing}</span></button>`)}${!g.places.length?html`<div class="empty">В списке пока нет мест</div>`:nothing}${g.places.length>this.rowLimit?html`<button class="chip" @click=${()=>this.rowLimit+=80}>Показать ещё</button>`:nothing}</div>`:nothing}</section>`;})}${!tree.length?html`<div class="empty">${this.catalog?'Нет мест по выбранным условиям':'Подключаем списки…'}</div>`:nothing}</div>`;
  }
  render(){if(!this._config)return nothing;
    return html`<div class="surface"><div class="map" aria-label="Декоративная карта улиц выбранного места"></div><div class="map-fade"></div><div class="map-desaturate"></div>
      <div class="interface" ?inert=${this.drawerOpen}><aside class="sidebar glass"><div class="shelf"><div class="title"><ha-icon icon="mdi:map-marker-multiple-outline"></ha-icon>Мои места</div><div class="subtitle">${this.places.length} мест · ${this.groups.length} списков</div>
      ${this._config.show_search?html`<input class="input" type="search" aria-label="Поиск мест" placeholder="Место или примечание…" .value=${this.query} @input=${e=>{this.query=e.target.value;this.rowLimit=80;}}>`:nothing}${this.renderStatus()}</div>${this.renderTree()}</aside>${this.renderSummary()}</div>
      ${this.mapError?html`<div class="map-error" role="status">${this.mapError}</div>`:nothing}${this.renderDetails()}<details class="map-attribution"><summary aria-label="Источники карты" title="Источники карты"><ha-icon icon="mdi:information-outline"></ha-icon></summary><a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a><a href="https://openmaptiles.org/" target="_blank" rel="noopener noreferrer">© OpenMapTiles</a><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a></details></div>`;
  }

}
if(!customElements.get('belovodie-places-card'))customElements.define('belovodie-places-card',BelovodiePlacesCard);
window.customCards=window.customCards??[];window.customCards.push({type:'belovodie-places-card',name:'Мои места',description:'Списки Google Maps и маршруты от дома'});
