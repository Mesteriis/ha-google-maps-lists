import {destinationCamera} from './camera.js';
import {placesGeoJSON} from './model.js';
import {StreetParticles} from './particles.js';
const STYLES={dark:'https://tiles.openfreemap.org/styles/dark',light:'https://tiles.openfreemap.org/styles/liberty'};
export class PlacesMap {
  constructor(container,onSelect,engine,onError){
    this.container=container;this.places=[];this.onSelect=onSelect;this.engine=engine;this.dark=true;
    this.map=new engine.Map({container,style:STYLES.dark,center:[2.17,41.39],zoom:10,attributionControl:false,interactive:false,pitch:0});
    if(container.ownerDocument)this.particles=new StreetParticles(container,this.map);
    this.map.on('load',()=>this.paint());this.map.on('style.load',()=>this.paint(true));
    this.map.on('error',onError);
    this.map.on('click','saved-point',e=>{const id=e.features?.[0]?.properties?.place_id;if(id)this.onSelect(id);});
    this.map.on('click','saved-cluster',async e=>{
      const f=e.features?.[0];if(!f)return;
      const zoom=await this.map.getSource('saved').getClusterExpansionZoom(f.properties.cluster_id);
      this.map.easeTo({center:f.geometry.coordinates,zoom,duration:250});
    });
  }
  paint(styleReady=false){
    if(!this.map||(!styleReady&&!this.map.isStyleLoaded()))return;
    const data=placesGeoJSON(this.places);
    if(this.map.getSource('saved'))this.map.getSource('saved').setData(data);
    else this.map.addSource('saved',{type:'geojson',data,cluster:true,clusterMaxZoom:14,clusterRadius:44});
    if(!this.map.getLayer('saved-cluster')){
      this.map.addLayer({id:'saved-cluster',type:'circle',source:'saved',filter:['has','point_count'],paint:{'circle-color':'#28748c','circle-radius':21,'circle-stroke-width':1,'circle-stroke-color':'#8bd4e4'}});
      this.map.addLayer({id:'saved-count',type:'symbol',source:'saved',filter:['has','point_count'],layout:{'text-field':['get','point_count_abbreviated'],'text-font':['Noto Sans Regular'],'text-size':13},paint:{'text-color':'#ffffff'}});
      this.map.addLayer({id:'saved-point',type:'circle',source:'saved',filter:['!', ['has','point_count']],paint:{'circle-color':['get','color'],'circle-radius':8,'circle-stroke-width':2,'circle-stroke-color':this.dark?'#e5f4f6':'#173945'}});
    }
  }
  setPlaces(places){
    this.places=places;this.paint();
    if(this.selection)return;
    this.fitPlaces();
  }
  fitPlaces(){
    const coords=placesGeoJSON(this.places).features.map(f=>f.geometry.coordinates);
    if(coords.length===1)this.map.easeTo({center:coords[0],zoom:15,duration:0});
    else if(coords.length>1)this.map.fitBounds([[Math.min(...coords.map(c=>c[0])),Math.min(...coords.map(c=>c[1]))],[Math.max(...coords.map(c=>c[0])),Math.max(...coords.map(c=>c[1]))]],{padding:60,maxZoom:15,duration:0});
  }
  setSelection(selection){
    const key=JSON.stringify(selection);if(this.selectionKey===key)return;this.selectionKey=key;this.selection=selection;
    if(selection)this.map.easeTo(destinationCamera(selection,this.container.clientWidth||1000,this.container.clientHeight||700));
    else this.fitPlaces();
    this.particles?.setSelection(selection);
  }
  setTheme(dark){if(dark===this.dark)return;this.dark=dark;this.map.setStyle(dark?STYLES.dark:STYLES.light,{diff:false});}
  resize(){this.map?.resize();if(this.selection)this.map.easeTo(destinationCamera(this.selection,this.container.clientWidth||1000,this.container.clientHeight||700));}
  destroy(){this.particles?.destroy();this.particles=null;this.map?.remove();this.map=null;}
}
