# Google Maps Saved Lists + Belovodie Places Card

YAML-only Home Assistant integration with a private saved-place catalog. The card keeps a searchable hierarchy on the left third over a full-height flat street map. Selection centers the destination with home toward the lower right. Amber particles trace a continuous street path when the visible topology connects both anchors; cyan particles flow through surrounding streets. Details open in a right-hand half-width drawer with public Google photos, address and list-specific personal notes. The decorative flow is not navigation guidance. Navigation routes open in Google Maps. Origin is read from live `zone.home` for every action.

## Configure

In configuration.yaml:

```yaml
google_maps_lists: !include google_maps_lists.yaml
```

Independent `google_maps_lists.yaml`:

```yaml
update_interval: 21600
stale_after: 86400
route_origin: zone.home
notify_service: notify.mobile_app_phone
labels: {}
# Optional display labels, keyed by stable place id from the authenticated catalog:
# labels:
#   "100:200": Любимое место  # illustrative id; replace with the actual catalog id
lists:
  - id: restaurants
    url: https://maps.app.goo.gl/YOUR_VIEW_LINK
    name: Рестораны
    icon: mdi:silverware-fork-knife
    color: '#edbd61'
```

Use a view link from Share, never an editor invitation. Each id and normalized URL must be unique; id/url required, display name/icon/color optional. Missing names use the source title. Automatically assigned colors persist across reorder/restart; an explicit duplicate color produces a catalog diagnostic. No fixed group count. `notify_service` is the existing HA Companion notify service; callers cannot choose another target. Route origin is restricted to zone.home.

Install custom_components/google_maps_lists, add the include, and run `ha core check` before the initial approved core restart. Later changes to the separate file apply via administrator-only `google_maps_lists.reload`, without restarting HA or editing card YAML. `google_maps_lists.refresh` refreshes the configured sources, with a 60-second manual debounce.

## Install with HACS

Add `https://github.com/Mesteriis/ha-google-maps-lists` as a custom **Integration** repository in HACS and download the selected release. This is a custom repository, not an entry in the default HACS catalog. Validate HA configuration and restart once after installing/upgrading the Python component.

The integration serves its bundled card and worker at `/google_maps_lists/card/` and automatically registers the versioned frontend module. No additional dashboard resource is required. When migrating a manual installation, remove the old `/local/belovodie-places-card/belovodie-places-card.js` resource through HA resource settings; do not load both copies. Existing separate YAML configuration and HA Storage catalog remain outside the package and survive HACS updates.

```yaml
type: custom:belovodie-places-card
origin_entity: zone.home
lists: all
show_search: true
default_transport: transit
```

An ordered array of group ids is accepted instead of `lists: all`. `origin_entity` is display metadata, never routing authority. Available modes: transit/driving/walking/bicycling.

## Data, errors and privacy

The Google source is an undocumented anonymous web interface, not an official Saved Lists API. It extracts the read-only getlist preload from a shared list page. No Google login/cookie export/API key. Responses, redirects, hosts, paths, time and size are bounded. If Google presents a consent redirect, the same allowlisted list page is retried once using its public no-cookie view flag; no consent host is contacted.

At 500 returned places the response is considered potentially incomplete until pagination is verified; it never replaces last-good data. A valid empty list does replace its previous contents. Missing coordinates keep the textual entry but disable its map marker and route. Cross-list duplicates share a marker and keep list-specific notes.

Cache is stored privately in HA Storage; sensors contain counts/status only. Catalog access requires an authenticated HA WebSocket connection. Only administrators may reload/refresh. There is no public www catalog. Raw URLs/notes/addresses/coordinates and provider exceptions do not enter routine logs. Invalid storage is backed up privately and a fresh collection is attempted.

Collection is sequential every configured interval. Errors retain successful snapshots and their ages indefinitely, with a stale label after stale_after. Removing a source or changing its URL discards that source snapshot. Disk failure must not publish a partial new snapshot. Reload generation fencing prevents stale in-flight results from repopulating removed lists.

OpenFreeMap tile requests are needed for the base map; the panel displays provider attribution. If WebGL/tiles fail, the saved places remain available in the list. Backend-generated directions open Google Maps with live home origin. Phone success means HA accepted the notify call; actual receipt must be checked separately. No estimated travel duration is fabricated.

## Protocol and operating checks

Authenticated commands: google_maps_lists/catalog, /subscribe, /details, /route, /send_to_phone. Details accepts only place_id and checks catalog membership before constructing a public Google request. Route/send accept only place_id and mode. Notification service `google_maps_lists.send_to_phone` uses the same strict schema and caller context.

## Development

Python 3.14 with Home Assistant 2026.9.3: `python -m pip install -r requirements-test.txt`, then `PYTHONPATH=. python -m pytest tests -q`.
Frontend: `cd frontend && npm ci && npm test && npm run build`. The build includes the JS, CSP worker and third-party licenses under `custom_components/google_maps_lists/frontend/`.

Before deployment, compare built/installed hashes, run `ha core check`, and verify actual hierarchy, search, selection and drawer in a browser. Keep a private backup of the installed component and resource entry. To roll back, reinstall the previous HACS release and restart after validation. Never commit your YAML, HA Storage, notes, private list links or screenshots containing personal information.

## Display labels and public photos

A nonempty `labels` override is the primary title in list rows, details and map endpoint. The original Google name remains secondary. Labels participate in search. They are optional and apply by stable place id across every membership; edits use the existing administrator reload service. Unknown ids have no effect. Source names and durable snapshots are preserved; no cache migration is needed.

Google calls account labels private: https://support.google.com/maps/answer/6257830. Current anonymous shared-list responses do not contain those private labels. This implementation does not export Google cookies or infer labels from comments. `labels` in the dedicated YAML file supplies an explicit local override when needed.

Photos are loaded lazily from the anonymous Google place preview, with verified feature identity. Only the selected place's public gallery photo paths on lh3–lh6.googleusercontent.com are accepted; author avatars are excluded. The card requests a display-sized version while retaining Google panorama framing, uses object-fit:cover and credits Google Maps. It never substitutes an author's avatar for a missing photo. This remains an undocumented upstream interface and can return no photo or change schema. That state affects details only, not saved lists or routing.

Requests are serialized and cached in memory with a 64-place limit: successful photos for one hour; no photo or upstream errors for one minute. Reload fences in-flight responses; shutdown cancels outstanding requests. Details use authenticated HA WebSocket, with no new public catalog endpoint. The public Google image loads directly in the browser with no-referrer. Photos are not downloaded or stored in www.

The first available place is selected automatically. Map tiles load with the card. Selecting another place redraws the centered scene without replacing the list. The icon actions open Google Maps or send a route to the configured phone. “Описание и фото” opens the drawer; Escape/close restores focus and retains map selection. The drawer uses half the width on desktop and full width on phones. Hidden cards cancel particle animation; reduced motion uses a still scene. Compact map attribution remains available through the information control.
