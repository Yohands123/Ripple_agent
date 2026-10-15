# Mineral reference layer

The mineral layer is contemporary display context. It does not add companies,
mine-level Apple sourcing claims, labels or features to the historical model.
The selected distance model and its seven evaluated events remain unchanged.

Apple's May 2026 [Form SD](https://www.sec.gov/Archives/edgar/data/320193/000114036126023149/ef20073373_sd.htm)
does not file a Conflict Minerals Report. The latest available
[CMR, covering 2024](https://www.sec.gov/Archives/edgar/data/320193/000114036125012359/ef20046400_ex1-01.htm),
contains origin countries and refers to a separate facility list. Facility rows
are therefore parsed from the [2026 Apple UNGP materials annex](https://s203.q4cdn.com/367071867/files/doc_downloads/gov_docs/2026/Apple-UNGP-Mapping-2026.pdf),
pages 28–34, as of December 31, 2025. The older static smelter-list PDF covers
2022 and is not used. Source bytes and editions are pinned in
`data/sources/minerals.json`.

There are 221 metal/facility/country records: 12 cobalt, 92 gold, 32 tantalum,
52 tin and 33 tungsten. A name repeated for different metals is not assumed
to denote the same physical plant. Apple generally publishes countries only:
220 records have country-level map coordinates and one has a city-level
coordinate. Three operator-published city names are retained, even where the
pinned gazetteer lacks a unique city point. These dots are approximate
references, never invented factory addresses. Apple publishes no copper
facility list in this annex; copper-producing regions do not manufacture one.

Thirty-eight broad producing regions cover the named nonzero producers in
the six [USGS Mineral Commodity Summaries 2026](https://pubs.usgs.gov/periodicals/mcs2026/)
tables, including the Katanga and Zambia Copperbelt, eastern DRC and Rwanda.
They represent mineral geography, not individual mines or verified Apple
origins. Region-to-refiner links match metals only. Apple’s stated exclusion
of DRC/Rwanda-origin 3TG is retained explicitly on the relevant links.
Refinery location does not establish the origin of its feedstock.

Eight road/rail corridor sketches connect the two Copperbelt regions to
Dar es Salaam, Durban, Lobito and Walvis Bay. They cite the corridor operators
and African Development Bank. Rail sketches include feeder transfers and do
not assert that the proposed new Zambia–Lobito railway already exists.
Two additional Central Corridor road sketches connect eastern DRC and Rwanda
to Dar es Salaam. These remain global transport context subject to Apple's
published 3TG-origin restriction. Other USGS national regions remain mineral
context where no land corridor to the selected ports is established; no
road is invented across water for Madagascar or for distant West Africa.
Nineteen sea corridors connect these ports to regional refining gateways;
all pass both polyline and smoothed-path checks against the pinned Natural
Earth land polygons. Regional gateways do not assert each refinery's actual
port, last-mile route, shipment, mode or volume.

Refiner-to-component links use narrow material categories: cobalt for
batteries, tin/gold for PCB/solder categories, tantalum for explicitly
tantalum capacitors, and tungsten for haptic/vibration categories. Generic
ceramic capacitors are not treated as tantalum. Each refiner selects at most
three nearest distinct compatible companies to keep the display sparse.
These are material-use inferences, not named commercial buyer relationships.
All mineral edges are inferred, low-confidence and excluded from model hops.

The [IEA-documented DRC cobalt export suspension](https://www.iea.org/policies/28969-temporary-suspension-of-cobalt-export-from-the-democratic-republic-of-congo)
is shown from February 22 through October 15, 2025. The next day's
[quota system](https://www.iea.org/policies/29138-drc-arecoms-decision-no-0042025-cobalt-quota-system)
provides the end basis. This `land` scenario marks cobalt export restrictions
on illustrative DRC corridors, not physical road closures or copper export
prohibitions. It has no CAR evaluation, substituted supplier roster, invented
capacity loss, production estimate or hypothetical route evading the ban.
