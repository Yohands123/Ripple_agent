"""Minimal tier-seven context; all return routes and stage labels are inferred."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re

from pipeline.backbone import citations
from pipeline.geocode import Gazetteer, load_datasets, normalize
from pipeline.minerals import ROOT, read
from pipeline.mineral_catalog import source, identifier
from pipeline.sea_routes import distance_km

TIER_BASIS = 'reverse logistics role: recycling, refurbishment or trade-in collection'


def build_catalog(offline=False):
    import requests
    config = read(ROOT/'data/sources/returns.json')
    raw = ROOT/'data/raw/reverse'
    raw.mkdir(parents=True, exist_ok=True)
    for item in config['datasets'].values():
        path = raw/item['file']
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            response = requests.get(item['url'], timeout=(10,90))
            response.raise_for_status()
            path.write_bytes(response.content)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Review changed reverse-logistics source before repinning: '+item['file'])
    geo_config = read(ROOT/'data/sources/natural_earth.json')
    gazetteer = Gazetteer(**load_datasets(geo_config,ROOT/'data/raw/natural_earth',offline))
    city_source = next(d for d in geo_config['datasets'] if d['id']=='cities')
    natural_earth = {'title':city_source['title'], 'url':geo_config['baseUrl']+city_source['file']}
    california = list(csv.DictReader((raw/'california_places_2025.txt').open(encoding='utf-8'),delimiter='|'))
    california = [{k.strip():v.strip() for k,v in row.items()} for row in california]

    def position(city,country):
        if city in {'Santa Clara','Elk Grove'}:
            record = next(r for r in california if r['NAME']==city+' city')
            return float(record['INTPTLONG']),float(record['INTPTLAT']),source(config['datasets']['california_places_2025.txt'])
        if city=='Breda':
            matches = [r for r in read(raw/'breda_pdok.json')['response']['docs'] if r.get('woonplaatsnaam')=='Breda']
            if len(matches)!=1:
                raise ValueError('Breda settlement must match exactly, not another settlement in its municipality')
            xy = [float(v) for v in re.findall(r'[-\d.]+',matches[0]['centroide_ll'])]
            return *xy,source(config['datasets']['breda_pdok.json'])
        iso = gazetteer.iso_by_country[normalize(country)]
        matches = gazetteer.unique(gazetteer.cities.get((iso,normalize(city)),[]))
        if len(matches)!=1:
            raise ValueError('Reverse context needs an unambiguous city reference: '+city)
        record = matches[0]
        return record['lon'],record['lat'],natural_earth

    def evidence(keys):
        return [source(config['datasets'][key]) if key in config['datasets'] else config['sources'][key] for key in keys]

    nodes = []
    def node(key,name,city,country,role,sources,**extra):
        lon,lat,geographic_source = position(city,country)
        n = {'id':'return-'+key, 'name':name, 'kind':'repair','tier':7,
             'tierStatus':'inferred','tierBasis':TIER_BASIS, 'status':'inferred','confidence':'low',
             'confidenceKind':'Qualitative stage and geographic inference, not a probability',
             'layer':'backbone','contextLayer':'returns','lon':lon,'lat':lat,'precision':'city',
             'region':city+', '+country,'city':city,'country':country, 'ticker':None,'appleRevenueShare':None,
             'partType':'reverse logistics','serviceRole':role,'referenceAsOf':config['referenceAsOf'],
             'historicalPresenceAsserted':False,'positionStatus':'inferred',
             'positionBasis':'Public city reference only; neither a precise facility coordinate nor a regional shipping origin',
             'basis':'Tier 7 is an inferred display convention for publicly documented end-of-life collection, reuse or material recovery.',
             'sources':citations(sources,[geographic_source]),'scope':config['scope'],**extra}
        nodes.append(n)
        return n
    for item in config['facilities']:
        node(item['key'],item['name'],item['city'],item['country'],item['serviceRole'],evidence(item['sources']),
             recoveredMetals=item['recoveredMetals'],operator=item['operator'],positionScope=item['positionScope'],
             facilityScope='Documented facility or operation; tier, displayed position and route allocation remain inferred')
    for item in config['collections']:
        node('trade-in-'+item['key'],item['name'],item['city'],item['country'],'trade_in_collection',
             [item['storeSource'],item['programSource']], salesRegionKey=item['key'],program='Apple Trade In',
             recoveredMetals=[],positionScope='Representative public collection store at city precision, not a refinery or refurbishment factory',
             facilityScope='Example collection point for the regional program, not an exhaustive service footprint')
    minerals = read(ROOT/'data/processed/minerals.json')
    backbone = read(ROOT/'data/processed/backbone.json')
    by_id = {n['id']:n for n in nodes + minerals['nodes'] + backbone['nodes']}
    edges = []
    def route(a,b,stage,metal=None):
        d = distance_km((a['lon'],a['lat']),(b['lon'],b['lat']))
        e = {'id':identifier('return',a['id'],b['id'],metal or stage),'from':a['id'],'to':b['id'],
             'relation':'route','purpose':'return','returnStage':stage,'layer':'backbone','contextLayer':'returns',
             'mode':'road' if d<500 else 'air','carriesTier':7,'status':'inferred','confidence':'low',
             'modelEligible':False,'routingVerified':False, 'distanceKm':round(d,3),
             'distanceDefinition':'Great-circle reference distance, not observed shipment or road length',
             'basis':'Inferred reverse-logistics reference. Collection and downstream reuse/recovery are documented in general; this allocation, carrier, transport mode, intermediate processing and cross-border permissions are unverified. No actual shipment or commercial relationship is asserted.',
             'geometryBasis':'Schematic road connector or illustrative geodesic air leg. Actual routing and mode are unknown; road connectors do not establish continuous drivable roads.',
             'sources':citations(a['sources'],b['sources'],[config['sources']['tradeIn']])}
        if metal:
            e['metal']=metal
            e['basis']+=' Recovered metal matches the listed refiner; nearest approximate reference chosen for a minimal display. Acceptance of this feedstock, intermediary treatment and refining volume are unknown.'
        edges.append(e)
    recyclers = [n for n in nodes if n['serviceRole']=='recycling']
    refurbisher = by_id['return-elk-grove-refurbishment']
    for collection in [n for n in nodes if n['serviceRole']=='trade_in_collection']:
        region = by_id['backbone-sales-'+collection['salesRegionKey']]
        route(region,collection,'collection')
        # Representative regional-to-facility links are hypotheses, not a
        # claim that foreign e-waste may legally be sent to the nearest dot.
        nearest = min(recyclers,key=lambda n:(distance_km((collection['lon'],collection['lat']),(n['lon'],n['lat'])),n['id']))
        route(collection,nearest,'recycling')
        if collection['salesRegionKey']=='americas':
            route(collection,by_id['return-austin-mrl'],'recycling')
        route(collection,refurbisher,'refurbishment')
    for recycler in recyclers:
        for metal in recycler['recoveredMetals']:
            candidates = [n for n in minerals['nodes'] if n['kind']=='refinery' and n['metal']==metal]
            if not candidates:
                raise ValueError('No same-metal tier-two endpoint: '+metal)
            closest = min(candidates,key=lambda n:(distance_km((recycler['lon'],recycler['lat']),(n['lon'],n['lat'])),n['id']))
            route(recycler,closest,'recovered_material',metal)
    return {'referenceAsOf':config['referenceAsOf'],'scope':config['scope'],'nodes':nodes,'edges':edges}


def attach_returns(network,catalog):
    network['nodes'].extend(copy.deepcopy(catalog['nodes']))
    network['edges'].extend(copy.deepcopy(catalog['edges']))
    network['returnReference']={k:catalog[k] for k in ['referenceAsOf','scope']}
    network['coverage'].update(returnNodes=len(catalog['nodes']),returnRoutes=len(catalog['edges']),
                               backboneNodes=sum(n['layer']=='backbone' for n in network['nodes']),
                               backboneRoutes=sum(e['layer']=='backbone' for e in network['edges']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    catalog=build_catalog(args.offline)
    (ROOT/'data/processed/returns.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(f"Built {len(catalog['nodes'])} inferred tier-seven nodes and {len(catalog['edges'])} return routes")
