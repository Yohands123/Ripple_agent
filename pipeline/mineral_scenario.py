"""A documented cobalt export policy event, without invented stock outcomes."""
import copy

from pipeline.mineral_routes import attach_minerals

EVENT_ID = 'copperbelt-cobalt-2025'


def build_scenario(backbone, minerals):
    config = minerals['reference']
    event_source = config['sources']['event']
    quota_source = config['sources']['quota']
    network = {'snapshotYear':2025, 'sampleData':False, 'eventId':EVENT_ID,
               'asOfDate':'2025-02-22', 'contextOnly':True, 'nodes':copy.deepcopy(backbone['nodes']),
               'edges':copy.deepcopy(backbone['edges']), 'coverage':{'matchedLocations':0,'manufacturingLocations':0,'supplierAccessLinks':0},
               'scope':'Separately dated contemporary geographic and mineral context. No FY2025 Apple Supplier List is substituted, no historical supplier cohort or stock outcome is asserted.',
               'snapshotYearBasis':'Calendar year of mineral disclosure and event; not a supplier-roster year',
               'backbone':{k:backbone[k] for k in ['referenceAsOf','scope','approval','routeDefinition','nearestGatewayDefinition']}}
    attach_minerals(network, minerals)
    origin = next(n for n in network['nodes'] if n['id']=='mineral-mine-copperbelt-drc')
    blocked = [e['id'] for e in network['edges'] if e['relation']=='route' and e['from']==origin['id'] and 'cobalt' in e.get('minerals',[])]
    scenario = {'id':EVENT_ID, 'title':'DRC cobalt export suspension, 2025', 'type':'land',
                'start':'2025-02-22','end':'2025-10-15','snapshotYear':2025,'sampleData':False,'contextOnly':True,
                'networkPath':'networks/'+EVENT_ID+'.json',
                'shock':{'nodeIds':[origin['id']], 'capacityLoss':None, 'mineral':'cobalt',
                         'location':{'lon':origin['lon'],'lat':origin['lat'],'precision':origin['precision'],
                                     'basis':'Copperbelt regional display anchor for a nationwide DRC cobalt export policy; not a closed individual mine',
                                     'sources':[event_source,*origin['sources']]}},
                'headline':'DRC suspended cobalt exports; a quota system replaced the suspension on October 16, 2025. Copper and physical road/rail closures are not asserted.',
                'predictions':[],'actual':[],'options':[],'quota':None,'sensitivity':[],
                'money':{'coinUsd':500000000,'revenueAtRisk':None,'delayedShare':None,'assumption':False},
                'affectedRoutes':{'blocked':blocked,'detour':[],'expedited':[]},'affectedRoutesStatus':'inferred',
                'affectedRoutesBasis':'Illustrative cobalt-only restriction on DRC regional export corridors. The routes themselves are not reported closed and copper is not prohibited. No alternative is assigned to evade an export ban.',
                'affectedRoutesScope':'Contemporary context only; excluded from stock labels, features, model selection and optimizer',
                'affectedRoutesSources':[event_source,quota_source],
                'outcomeDefinition':'No CAR or production outcome is evaluated for this context-only event.',
                'predictionScope':'No prediction: own-year supplier roster and labels are unavailable.',
                'unknowns':['Apple-specific exposure and shipment quantities','Apple production capacity loss','Primary versus recycled feedstock','Actual purchases between mining regions, refiners and component companies','Production tier for an unknown share of sites (supplier locations undisclosed)'],
                'dateBasis':'IEA records the cobalt export suspension beginning February 22, 2025.',
                'endBasis':'IEA records the suspension through October 15, replaced by export quotas on October 16, 2025.',
                'sources':[event_source,quota_source]}
    return network,scenario
