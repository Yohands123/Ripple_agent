"""Schematic, sourced mineral corridors; not observed Apple shipments."""
from pipeline.backbone import citations, nearest_gateway
from pipeline.sea_geometry import geometry, sea_route_errors
from pipeline.sea_routes import WaterRouter, distance_km
from pipeline.mineral_catalog import identifier, source
import math


def dense(points, step=.05):
    result = [points[0]]
    for a, b in zip(points, points[1:]):
        count = max(1, math.ceil(max(abs(a[0]-b[0]), abs(a[1]-b[1])) / step))
        result.extend([[round(a[0]+(b[0]-a[0])*i/count, 6), round(a[1]+(b[1]-a[1])*i/count, 6)] for i in range(1, count+1)])
    return result


def build_routes(nodes, base, gazetteer, config):
    by_id = {n['id']: n for n in base['nodes'] + nodes}
    edges = []
    def edge(a, b, mode, evidence, **extra):
        value = {'id': identifier('route', a, b, mode), 'from': a, 'to': b, 'relation': 'route',
                 'mode': mode, 'carriesTier': 1, 'status': 'inferred', 'confidence': 'low',
                 'layer': 'backbone', 'contextLayer': 'minerals', 'routingVerified': False, 'modelEligible': False,
                 'basis': 'Commodity-compatible reference corridor, not evidence of an Apple shipment or a navigable track. Local access, border permissions, volumes and actual mode are unknown.',
                 'sources': citations(evidence, by_id[a]['sources'], by_id[b]['sources']), **extra}
        edges.append(value)
        return value
    for region in ['copperbelt-drc', 'copperbelt-zambia']:
        a = 'mineral-mine-' + region
        for port, mode, source_key, stops in [
            ('lobito', 'rail', 'lobito', [('Kolwezi','Democratic Republic of the Congo'), ('Luena','Angola'), ('Huambo','Angola')]),
            ('dar-es-salaam', 'rail', 'tazara', [('Kapiri Mposhi','Zambia'), ('Kasama','Zambia'), ('Mbeya','Tanzania'), ('Morogoro','Tanzania')]),
            ('durban', 'road', 'southern', [('Lusaka','Zambia'), ('Harare','Zimbabwe'), ('Johannesburg','South Africa')]),
            ('walvis-bay', 'road', 'walvis', [('Lusaka','Zambia'), ('Livingstone','Zambia'), ('Windhoek','Namibia')]),
        ]:
            via = []
            for city, country in stops:
                point, _ = gazetteer.match(city + ', ' + country, country)
                if point and point['precision'] == 'city':
                    via.append([point['lon'], point['lat']])
            item = edge(a, 'backbone-mineral-port-' + port, mode, [config['sources'][source_key]],
                        via=via, viaNodeIds=[], minerals=['cobalt','copper'], corridor='Copperbelt to ' + port,
                        geometryBasis='Inferred city-reference corridor. Rail routes include unverified feeder transfers; not a surveyed continuous rail alignment. The proposed new Zambia-Lobito railway is not asserted to exist.')
            item['sources'] = citations(item['sources'], [config['sources']['southern']])
    for region in ['eastern-drc', 'rwanda']:
        points = []
        for city,country in [('Kigali','Rwanda'), ('Dodoma','Tanzania'), ('Morogoro','Tanzania')]:
            p,_ = gazetteer.match(city + ', ' + country, country)
            if p and p['precision']=='city':
                points.append([p['lon'],p['lat']])
        edge('mineral-mine-'+region,'backbone-mineral-port-dar-es-salaam','road',
             [config['sources']['central']], via=points, viaNodeIds=[], minerals=['tin','tantalum','tungsten'],
             corridor='Great Lakes to Dar es Salaam via Central Corridor',
             geometryBasis='Inferred road-access sketch through regional city references; actual border access, roads and mineral shipments remain unverified. Apple excludes DRC/Rwanda-origin 3TG.')
    land, _ = geometry()
    router = WaterRouter(land=land.buffer(.005))
    fine = WaterRouter(step=.05, bounds=(94,0,106,8.5), land=router.land)
    locals_ = {}
    def pos(key):
        n = by_id[key]
        return [n['lon'], n['lat']]
    def coastal(key, coarse):
        p = pos(key)
        if key not in locals_:
            x,y = p
            locals_[key] = WaterRouter(step=.05, bounds=(round(x-3,1),round(y-3,1),round(x+3,1),round(y+3,1)), land=router.land)
        local = locals_[key]
        path = local.route(p, coarse)
        return [p] + path + [coarse]
    # Regional gateways are illustrative aggregation points. They do not
    # assert each refinery's port, throughput, or last-mile transport.
    destinations = {'Asia':'backbone-port-singapore', 'Europe':'backbone-port-rotterdam',
                    'North America':'backbone-port-new-york', 'South America':'backbone-mineral-port-santos',
                    'Africa':'backbone-mineral-port-durban'}
    for port in ['dar-es-salaam','durban','lobito','walvis-bay']:
        a = 'backbone-mineral-port-' + port
        east = port in {'dar-es-salaam','durban'}
        for region, b in destinations.items():
            if a == b:
                continue
            gates = []
            if (region == 'Asia' and not east) or (region != 'Asia' and east and region != 'Africa'):
                gates = [[15,-36],[30,-36]] if region == 'Asia' else [[30,-36],[15,-36]]
            if region == 'Africa' and not east:
                gates = [[15,-36],[30,-36]]
            if region == 'Asia':
                gates += [[75,0],[96,6]]
            elif region == 'Europe':
                gates += [[-15,0],[-8,49]]
            elif region == 'North America':
                gates += [[-30,5],[-65,35]]
            elif region == 'South America':
                gates += [[-15,-25],[-40,-27]]
            start = router.point(router.snap(tuple(pos(a))))
            points = coastal(a, start)
            cursor = start
            for target in gates:
                leg = router.route(cursor, target)
                points.extend(leg)
                cursor = leg[-1]
            if region == 'Asia':
                leg = fine.route(cursor, pos(b))
                points.extend([cursor] + leg + [pos(b)])
            else:
                finish = router.point(router.snap(tuple(pos(b))))
                points.extend(router.route(cursor, finish))
                points.extend(reversed(coastal(b, finish)))
            points = dense([p for i,p in enumerate(points) if not i or p != points[i-1]])
            sea_evidence = citations(*[e['sources'] for e in base['edges'] if e['mode']=='sea'])
            item = edge(a,b,'sea', [source(config['datasets']['apple_ungp_2026.pdf']), *sea_evidence],
                        via=points[1:-1], viaNodeIds=['backbone-malacca'] if region == 'Asia' else [],
                        laneName=by_id[a]['name'] + ' to ' + region + ' refining region', corridor='Mineral regional sea corridor',
                        refiningRegion=region, minerals=['cobalt','gold','tantalum','tin','tungsten'],
                        geometryBasis='Inferred water-grid path; Cape routing where needed. Regional aggregation only, not a measured or shortest shipping service.')
            errors = sea_route_errors(item, by_id)
            if errors:
                raise ValueError(item['id'] + ': ' + '; '.join(errors))
            print('Built mineral sea corridor ' + port + ' -> ' + region, flush=True)
    return edges


def supply_edge(a, b, metal, evidence, basis, **extra):
    return {'id': identifier('supply', a['id'], b['id'], metal), 'from':a['id'], 'to':b['id'],
            'relation':'supply', 'mode':None, 'carriesTier':a['tier'], 'layer':'mineral_supply', 'contextLayer':'minerals',
            'metal':metal, 'status':'inferred', 'confidence':'low', 'modelEligible':False, 'routingVerified':False,
            'basis':basis, 'sources':citations(a['sources'], b['sources'], evidence), **extra}


def component_metals(part_type):
    text = (part_type or '').lower()
    metals = set()
    if any(s in text for s in ['battery','batteries']):
        metals.add('cobalt')
    if any(s in text for s in ['printed circuit','pcb','ic substrate','solder']):
        metals.update(['tin','gold'])
    if 'tantalum' in text and 'capacitor' in text:
        metals.add('tantalum')
    if any(s in text for s in ['taptic','haptic','vibration']):
        metals.add('tungsten')
    return metals


def attach_minerals(network, catalog):
    import copy
    network['nodes'].extend(copy.deepcopy(catalog['nodes']))
    network['edges'].extend(copy.deepcopy(catalog['edges']))
    nodes = network['nodes']
    refiners = [n for n in nodes if n['kind'] == 'refinery']
    sites = [n for n in nodes if n.get('layer') == 'supplier' and n['tier'] == 3]
    config = catalog['reference']
    cmr = source(config['datasets']['apple_cmr_2024.html'])
    for refiner in refiners:
        metal = refiner['metal']
        compatible = [s for s in sites if metal in component_metals(s['partType'])]
        # One representative site per company, then three nearest companies.
        ordered = sorted(compatible, key=lambda s:(distance_km((refiner['lon'],refiner['lat']),(s['lon'],s['lat'])), s['id']))
        seen = set()
        for site in ordered:
            if site['companyId'] in seen:
                continue
            seen.add(site['companyId'])
            network['edges'].append(supply_edge(refiner,site,metal,[cmr,source(config['datasets'][f'mcs2026-{metal}.pdf'])],
                'Material-use compatibility and three-nearest distinct qualifying companies for a sparse display. No named buyer relationship, purchase, primary/recycled share, historical availability or Apple-specific bill of materials is asserted.'))
            if len(seen) == 3:
                break
    # A newly added port changes the curated nearest-gateway set. Preserve
    # exactly one access edge per supplier, with an honestly recomputed target.
    by_id = {n['id']:n for n in nodes}
    gateways = [n for n in nodes if n['kind'] in {'port','airport'} and n['layer'] == 'backbone']
    for edge in network['edges']:
        if edge['layer'] != 'supplier_access':
            continue
        site = by_id[edge['from']]
        target = nearest_gateway(site,gateways)
        edge.update(to=target['id'], distanceKm=round(distance_km((site['lon'],site['lat']),(target['lon'],target['lat'])),3),
                    sources=citations(site['sources'],target['sources']))
    network['mineralReference'] = {k:config[k] for k in ['referenceAsOf','scope','sourceChoice','originPolicy']}
    network['coverage'].update(mineralNodes=len(catalog['nodes']), mineralSupplyLinks=sum(e['layer']=='mineral_supply' for e in network['edges']),
                               backboneNodes=sum(n['layer']=='backbone' for n in nodes), backboneRoutes=sum(e['layer']=='backbone' for e in network['edges']))
