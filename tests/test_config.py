import pytest
import voluptuous as vol
from custom_components.google_maps_lists.config import validate_config

BASE = {"lists": [{"id":"one", "url":"https://maps.app.goo.gl/Abc123"}]}

def test_yaml_contract():
 c=validate_config(BASE)
 assert (c.update_interval,c.stale_after,c.route_origin)==(21600,86400,"zone.home")
 assert c.lists[0].name is None

@pytest.mark.parametrize("url", ["http://maps.app.goo.gl/Abc", "https://evil.test/maps/", "https://www.google.com.evil.test/maps/", "https://user@www.google.com/maps/", "https://maps.app.goo.gl:8443/A", "https://www.google.com/maps/preview/entitylist/delete", "https://maps.app.goo.gl/A?invite=edit", "https://www.google.com/maps/@?foo=bar"])
def test_invalid_source_url(url):
 with pytest.raises(vol.Invalid): validate_config({"lists":[{"id":"one","url":url}]})

@pytest.mark.parametrize("rows", [[{"id":"a","url":"https://maps.app.goo.gl/A"},{"id":"a","url":"https://maps.app.goo.gl/B"}], [{"id":"a","url":"https://maps.app.goo.gl/A"},{"id":"b","url":"https://maps.app.goo.gl/A"}]])
def test_duplicate_ids_urls_rejected(rows):
 with pytest.raises(vol.Invalid): validate_config({"lists":rows})

@pytest.mark.parametrize("override", [{"route_origin":"person.someone"},{"notify_service":"script.run"},{"update_interval":0},{"stale_after":-1},{"surprise":1}])
def test_invalid_authority_config(override):
 with pytest.raises(vol.Invalid): validate_config({**BASE,**override})
