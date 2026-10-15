import copy
import json
from pathlib import Path

import pytest

from pipeline.export import build_bundle
from pipeline.validate import Validator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def return_network():
    return build_bundle()['network.json']


def test_tier_seven_references_separate_real_facilities_from_collection_examples(return_network):
    nodes = [n for n in return_network['nodes'] if n.get('contextLayer')=='returns']
    assert len(nodes)==9
    assert sum(n['serviceRole']=='recycling' for n in nodes)==3
    assert sum(n['serviceRole']=='refurbishment' for n in nodes)==1
    assert sum(n['serviceRole']=='trade_in_collection' for n in nodes)==5
    for n in nodes:
        assert n['kind']=='repair' and n['tier']==7 and n['tierStatus']==n['status']=='inferred'
        assert n['sources'] and n['positionStatus']=='inferred' and n['confidence']=='low'
        assert n['positionScope'] and n['historicalPresenceAsserted'] is False and 'companyId' not in n
        assert n['ticker'] is None and n['appleRevenueShare'] is None
    austin = next(n for n in nodes if n['id']=='return-austin-mrl')
    assert austin['recoveredMetals']==['cobalt','tin']
    assert 'undisclosed' in next(n['positionScope'] for n in nodes if n['id']=='return-santa-clara-arc')


def test_returns_cover_five_regions_and_close_only_matching_metal_loops(return_network):
    by_id = {n['id']:n for n in return_network['nodes']}
    edges = [e for e in return_network['edges'] if e.get('contextLayer')=='returns']
    assert len(edges)==21
    collection = [e for e in edges if e['returnStage']=='collection']
    assert {e['from'] for e in collection}=={n['id'] for n in by_id.values() if n['kind']=='sales_region'}
    for e in edges:
        assert e['relation']=='route' and e['purpose']=='return' and e['status']=='inferred'
        assert e['confidence']=='low' and e['basis'] and e['sources']
        assert e['carriesTier']==7 and e['modelEligible'] is False and e['routingVerified'] is False
        assert e['from'] in by_id and e['to'] in by_id
    recovered = [e for e in edges if e['returnStage']=='recovered_material']
    assert len(recovered)==5 and {e['metal'] for e in recovered}=={'cobalt','tin','tungsten'}
    for e in recovered:
        a,b = by_id[e['from']],by_id[e['to']]
        assert e['metal'] in a['recoveredMetals'] and e['metal']==b['metal']
        assert a['tier']==7 and b['tier']==2 and b['kind']=='refinery'


@pytest.mark.parametrize('mutation,expected',[
    ('known','return context must remain inferred'),
    ('model','return context cannot enter historical model'),
    ('metal','incompatible recovered metal'),
])
def test_invalid_reverse_flow_claims_are_rejected(return_network,mutation,expected,tmp_path):
    network = copy.deepcopy(return_network)
    e = next(e for e in network['edges'] if e.get('returnStage')=='recovered_material')
    if mutation=='known': e['status']='known'
    elif mutation=='model': e['modelEligible']=True
    else: e['metal']='copper'
    validator=Validator(tmp_path)
    validator.network(network,'test')
    assert any(expected in error for error in validator.errors)
