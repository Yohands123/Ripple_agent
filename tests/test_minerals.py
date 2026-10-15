import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from pipeline.export import build_bundle
from pipeline.mineral_routes import component_metals
from pipeline.sea_geometry import sea_route_errors

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def mineral_bundle():
    return build_bundle()


def test_complete_apple_annex_and_honest_location_precision(mineral_bundle):
    rows = list(csv.DictReader((ROOT/'data/interim/apple_refiners_2025.csv').open(encoding='utf-8')))
    assert Counter(r['metal'] for r in rows) == {'cobalt':12,'gold':92,'tantalum':32,'tin':52,'tungsten':33}
    network = mineral_bundle['network.json']
    refiners = [n for n in network['nodes'] if n['kind']=='refinery']
    assert len(refiners)==len(rows)==221
    assert {(n['metal'],n['reportEntryName'],n['reportCountry']) for n in refiners} == {(r['metal'],r['name'],r['country']) for r in rows}
    assert all(n['tier']==2 and n['sources'] and n['historicalPresenceAsserted'] is False for n in refiners)
    assert all(n['precision']=='country' for n in refiners if not n['city'])
    assert all(n['precision'] in {'country','city'} and n['appleMineOriginAsserted'] is False for n in refiners)


def test_mineral_links_retain_apple_origin_restriction_and_never_enter_model(mineral_bundle):
    network = mineral_bundle['network.json']
    nodes = {n['id']:n for n in network['nodes']}
    links = [e for e in network['edges'] if e['layer']=='mineral_supply']
    assert links
    for e in links:
        a,b = nodes[e['from']],nodes[e['to']]
        assert e['status']=='inferred' and e['confidence']=='low' and e['basis'] and e['sources']
        assert e['mode'] is None and e['modelEligible'] is False
        if a['kind']=='mine':
            assert e['metal'] in a['minerals'] and e['metal']==b['metal']
            if a['country'] in {'Rwanda','Democratic Republic of the Congo'} and e['metal']!='cobalt':
                assert e['appleSourcingStatus']=='excluded-by-published-origin-policy'
        else:
            assert a['tier']==2 and b['tier']==3 and e['metal'] in component_metals(b['partType'])
    assert component_metals('ceramic capacitors') == set()
    assert component_metals('printed circuit boards and IC substrates') == {'tin','gold'}
    assert component_metals('battery cells') == {'cobalt'}


def test_every_mineral_sea_route_passes_independent_land_check(mineral_bundle):
    network = mineral_bundle['network.json']
    nodes = {n['id']:n for n in network['nodes']}
    routes = [e for e in network['edges'] if e.get('contextLayer')=='minerals' and e['mode']=='sea']
    assert len(routes)==19
    for edge in routes:
        assert not sea_route_errors(edge,nodes)
        assert edge['laneName'] and edge['status']=='inferred'


def test_cobalt_policy_has_no_fabricated_roster_outcomes_or_evasion(mineral_bundle):
    event = mineral_bundle['scenarios/copperbelt-cobalt-2025.json']
    network = mineral_bundle[event['networkPath']]
    edges = {e['id']:e for e in network['edges']}
    assert event['contextOnly'] is True and event['type']=='land'
    assert event['start']=='2025-02-22' and event['end']=='2025-10-15'
    assert event['predictions']==event['actual']==event['options']==[]
    assert event['quota'] is None and event['shock']['capacityLoss'] is None
    assert event['affectedRoutes']['detour']==event['affectedRoutes']['expedited']==[]
    assert len(event['affectedRoutes']['blocked'])==4
    assert all(edges[e]['relation']=='route' and edges[e]['from']=='mineral-mine-copperbelt-drc' for e in event['affectedRoutes']['blocked'])
    assert not any(n.get('companyId') for n in network['nodes'])
    assert not any(e.get('modelEligible') for e in network['edges'])
    assert 'copperbelt-cobalt-2025' not in {r['eventId'] for r in mineral_bundle['metrics.json']['loeo']}
