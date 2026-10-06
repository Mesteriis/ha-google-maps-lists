import json
from datetime import datetime, UTC
import pytest
from custom_components.google_maps_lists.source import parse_getlist, SourceError, validate_request_url

NOW=datetime(2026,10,6,tzinfo=UTC)
def item(feature="200", name="Cafe", note="first", coords=(41.1,2.2)):
 return [None,[None,None,"",None,"Street",[None,None,*coords],["100",feature],"/g/example"],name,note,None,None,None,[],None,None,None,None,["PRIVATE OWNER","PRIVATE PHOTO","PRIVATE ID"]]
def payload(items=None):
 row=[None]*21;row[0]=["abc_TOKEN"];row[4]="List";row[8]=[item()] if items is None else items
 return b")]}'\n"+json.dumps([row,None,None,None,None,None,None]).encode()

def test_preload_reader():
 snap=parse_getlist(payload(),"one","abc_TOKEN",NOW)
 assert snap.title=="List" and snap.places[0].name=="Cafe"
 assert snap.places[0].id=="100:200"
 assert "PRIVATE" not in repr(snap)

def test_confirmed_empty():
 assert parse_getlist(payload([]),"one","abc_TOKEN",NOW).places==()

@pytest.mark.parametrize("body,code", [(b"wrong","schema_changed"),(b")]}'\n[[]]","schema_changed"),(payload([item()]*500),"potentially_incomplete")])
def test_schema_drift_and_at_limit(body,code):
 with pytest.raises(SourceError) as e:parse_getlist(body,"one","abc_TOKEN",NOW)
 assert e.value.code==code

def test_wrong_list_identity():
 with pytest.raises(SourceError):parse_getlist(payload(),"one","another",NOW)

def test_identity_not_name_and_missing_coords():
 snap=parse_getlist(payload([item(),item("201",coords=(None,None))]),"one","abc_TOKEN",NOW)
 assert [p.id for p in snap.places]==["100:200","100:201"]
 assert snap.places[1].latitude is None

@pytest.mark.parametrize("coords",[(91,2),(41,float("nan")),(True,2),(41,None)])
def test_coordinate_validation(coords):
 with pytest.raises(SourceError): parse_getlist(payload([item(coords=coords)]),"one","abc_TOKEN",NOW)

@pytest.mark.parametrize("url",["https://evil.test/maps/", "https://www.google.com/maps/preview/entitylist/delete", "https://www.google.com/accounts/login", "https://www.google.com/maps/@41,2", "http://www.google.com/maps/", "https://www.google.com:444/maps/", "https://u@www.google.com/maps/"])
def test_redirect_policy(url):
 with pytest.raises(SourceError):validate_request_url(url,"page")

def test_request_allowlist():
 assert validate_request_url("https://maps.app.goo.gl/Abc123","page")
 assert validate_request_url("https://www.google.com/maps/@/data=!4m3!11m2!2sabc_TOKEN!3e3","page")
 assert validate_request_url("https://www.google.com/maps/preview/entitylist/getlist?pb=anonymous","json")
 with pytest.raises(SourceError):validate_request_url("https://www.google.com/maps/preview/entitylist/getlist?pb=x","page")

import asyncio
from types import SimpleNamespace
from custom_components.google_maps_lists.source import GoogleListSource
class Response:
 def __init__(self,status=200,body=b'ok',location=None):
  self.status=status;self.body=body;self.headers={} if location is None else {'Location':location}
  self.content=self
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def iter_chunked(self,n):yield self.body
class Session:
 def __init__(self,responses):self.responses=iter(responses);self.urls=[]
 def get(self,url,**kwargs):self.urls.append(str(url));return next(self.responses)

def test_consent_redirect_never_fetches_consent_or_cookies():
 async def case():
  page='https://www.google.com/maps/@/data=!4m3!11m2!2sabc_TOKEN!3e3'
  session=Session([Response(302,location='https://consent.google.com/m?continue=example'),Response()])
  body,url=await GoogleListSource(session)._get(page,'page')
  assert body==b'ok' and 'ucbcb=1' in url
  assert all('consent.google.com' not in u for u in session.urls)
 asyncio.run(case())

def test_body_limit():
 async def case():
  source=GoogleListSource(Session([Response(body=b'x'*(4*1024*1024+1))]))
  with pytest.raises(SourceError) as e:await source._get('https://maps.app.goo.gl/A','page')
  assert e.value.code=='response_too_large'
 asyncio.run(case())

def test_foreign_redirect_not_requested():
 async def case():
  session=Session([Response(302,location='https://evil.test/')])
  with pytest.raises(SourceError):await GoogleListSource(session)._get('https://maps.app.goo.gl/A','page')
  assert len(session.urls)==1
 asyncio.run(case())

def test_signed_google_feature_ids():
 snap=parse_getlist(payload([item('-200')]),'one','abc_TOKEN',NOW)
 assert snap.places[0].id=='100:-200'
