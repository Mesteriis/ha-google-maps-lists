export class PlacesClient {
  constructor(hass,onCatalog,onError){this.hass=hass;this.onCatalog=onCatalog;this.onError=onError;this.generation=0;this.active=false;}
  async load(generation=this.generation){
    try {const data=await this.hass.callWS({type:'google_maps_lists/catalog'});
      if(this.active&&generation===this.generation)this.onCatalog(data);
    } catch(err){if(this.active&&generation===this.generation)this.onError(err);}
  }
  async connect(){
    if(this.active)return;
    this.active=true;const generation=++this.generation;
    try {const unsubscribe=await this.hass.connection.subscribeMessage(()=>this.load(generation),{type:'google_maps_lists/subscribe'});
      if(!this.active||generation!==this.generation){unsubscribe();return;}
      this.unsubscribe=unsubscribe;
    } catch(err){if(this.active)this.onError(err);}
    if(this.active&&generation===this.generation)await this.load(generation);
  }
  disconnect(){this.active=false;this.generation++;this.unsubscribe?.();this.unsubscribe=null;}
}
