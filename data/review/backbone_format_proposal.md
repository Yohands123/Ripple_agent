# Backbone format decision

Approved by the user on October 14, 2026: "Approve backbone extensions".
The approval is recorded in `data/sources/backbone.json`. Human-owned
contracts are not edited by this implementation.

The requested backbone includes geographic sales regions, straits, and event
anchors rather than only supplier factories. The frozen `docs/contracts.md`
node-kind enum has no `sales_region`, `chokepoint`, or `event_anchor`. It also
requires an integer `carriesTier` for every edge, although the user explicitly
requires unknown supplier tiers to remain null.

Proposed additions, leaving human-owned contracts untouched:

```json
{
  "nodeKinds": ["chokepoint", "sales_region", "event_anchor"],
  "edgeExample": {
    "from": "supplier-with-unknown-part-type",
    "to": "nearest-backbone-gateway",
    "mode": "road",
    "carriesTier": null,
    "status": "inferred",
    "sources": [{"title": "Supplier disclosure and gateway evidence", "url": "https://example.org/source"}]
  }
}
```

Every added node uses `layer: "backbone"`. Source citations establish the
place or public production role; inferred routes describe a schematic
connection, not a disclosed Apple shipment. Five sales-region markers use
sourced geographic reference anchors, not invented retail facilities.
Event anchors cover regional disruptions that cannot truthfully be assigned
to an established assembly factory or port.

The backbone is a dated contemporary reference layer and is explicitly
separate from each historical Supplier List. It does not assign undisclosed
2011 suppliers factory coordinates. Their company predictions remain
unlocated even when reference geography is visible beside them. The model,
feature graph, distances, and CAR labels are not updated from these routes.

Port, airport, headquarters, and region nodes with no part type retain null
tiers. Road links from suppliers with unknown part types retain null
`carriesTier`; assigning a default tier would invent a category. The consumer
needs matching kind rendering and unknown-tier handling under Claude's ownership.
