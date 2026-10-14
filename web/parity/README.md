# Visual parity (W8)

Side-by-side images of the app against `design/reference/*.html`, at 1840 × 810 with
reduced motion (so ships and coins sit still). Regenerate with:

```bash
cd web && npm run build && npm start   # in one terminal
node scripts/screenshot.mjs --reduced --fixtures  # in another
```

`--fixtures` hides `web/public/data/real/` from the browser so the comparison uses the
fixture data the references were drawn from.

| State | Reference | App | Side by side |
|---|---|---|---|
| Free flow | `free-flow.reference.png` | `free-flow.app.png` | `free-flow.side-by-side.png` |
| Suez blocked (day 3 of 6) | `suez-blocked.reference.png` | `suez-blocked.app.png` | `suez-blocked.side-by-side.png` |

Matched exactly: map framing (equirectangular, 8.6 px per degree, top-left at 25°W 57°N),
every spec color, node symbols and sizes, pill type, Apple Park card, year tag, panel
spacing (title, status, quota, money key, map key, tier key, button), the Suez zone,
blocked and queued ships, grey blocked lane, detour around Africa, thicker air arcs,
delayed coin stack, falling lost coins, and the four disruption sections with the chart.

## Fixed in this pass

- One of the three spend coins started off the right edge of the map.
- Day 3 of the replay showed the disruption half built; effects now build over the
  first half of the event, so day 3 of 6 matches the reference.

## Remaining differences, with reasons

| Difference | Reason |
|---|---|
| Land shapes | Natural Earth 1:50m coastlines, as the spec requires; the reference uses hand-drawn shapes. |
| Sea lanes are dashed | Every fixture edge is `"status": "inferred"`, and the spec says inferred links are a dashed version of their normal style. The reference draws them solid. Real exports with `known` edges render solid. |
| Fewer nodes and labels (no Vietnam, Korea, Jiangsu, extra suppliers) | The app draws only the nodes in `network.json`; the fixture has 17 nodes. |
| Air arcs end at Rotterdam, not Frankfurt | The fixture's air edges go to `port-rotterdam`. |
| A purple Taiwan → Shenzhen parts route | It is in the fixture (`e-parts-taiwan`); the reference omits it. |
| Some pills sit elsewhere (Japan, Shenzhen, air freight, sea lane, revenue) | Pills are placed from data and avoid nodes, lanes and each other; the reference's "AIR FREIGHT" overlaps the Europe pill and its revenue pill covers the Madrid retailer. |
| Coins are 24 px on the map | Spec: coin 24 px (20 in legends). The reference uses 26 px gold and 20/22 px others. |
| 5 delayed and 3 lost coins (reference: 4 and 4) | Split from the scenario's `delayedShare` of 0.6 over 8 at-risk coins. |
| Egypt is highlighted during the Suez disruption | Spec: highlighted land includes the shock country. The reference does not highlight it. |
| Year subtitle reads "Day 3 of 6. Suez Canal blocked" | "Based on the Ever Given blockage" is not in the scenario file; the title is. |
| Quota note reads "On track: 99 of 100 units shipped", coin note "1 coin = $500M per week" | Filled from the scenario file where the reference has placeholders. |
| What's affected lists two rows, not three | The fixture has two predictions; "Ships queued in Red Sea" is not a node prediction. |
| Extra panel lines: option assumption note, "Back to a normal week", "What matters most", replay section | Data rules require labeling assumptions; W11 adds the sensitivity chart and W7 the replay (the panel scrolls); the link returns to free flow. |
| Quota chart has 5 points, not 7 | The fixture has 5 weeks. |
| Zoom controls (+, −, Reset view) in the map's bottom-right corner | Added at the human's request: the map pans and zooms over the whole world so sites in the Americas can be reached. It opens on the concept-art view, so everything else in that view is unchanged. |
