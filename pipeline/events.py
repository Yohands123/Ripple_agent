"""Write sourced event dates and explicitly approximate geographic anchors."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline.geocode import Gazetteer, load_datasets

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    config = json.loads((ROOT / "data/sources/events.json").read_text(encoding="utf-8"))
    geography = json.loads((ROOT / "data/sources/natural_earth.json").read_text(encoding="utf-8"))
    gazetteer = Gazetteer(**load_datasets(geography, ROOT / "data/raw/natural_earth", True))
    city = next(d for d in geography["datasets"] if d["id"] == "cities")
    city_source = {"title": city["title"], "url": geography["baseUrl"] + city["file"]}
    manifest = json.loads((ROOT / "data/interim/supplier_list_manifest.json").read_text(encoding="utf-8"))
    available = {r["snapshotYear"] for r in manifest["editions"]}
    output, gaps = [], []
    for event in config["events"]:
        if event["snapshotYear"] not in available:
            gaps.append({"eventId": event["id"], "snapshotYear": event["snapshotYear"], "reason": "No verified own-year Supplier List; omitted under the user's verified-editions-and-explicit-gaps policy",
                         "source": {"title": event["sourceTitle"], "url": event["sourceUrl"]}})
            continue
        row = {k: v for k, v in event.items() if k not in {"earthquakeId", "referencePoint", "endSource", "zone"}}
        sources = [{"title": event["sourceTitle"], "url": event["sourceUrl"]}]
        row["eventUtc"] = ""
        row["knowledgeCutoffDate"] = event["start"]
        if event.get("endSource"):
            sources.append(event["endSource"])
        if event.get("earthquakeId"):
            raw = ROOT / f"data/raw/events/{event['earthquakeId']}.geojson"
            raw.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/{event['earthquakeId']}.geojson"
            if not raw.exists():
                response = requests.get(url, timeout=(10, 45))
                response.raise_for_status()
                document = response.json()
                if document.get("id") != event["earthquakeId"]:
                    raise ValueError("USGS event identifier differs from requested earthquake")
                raw.write_bytes(response.content)
            document = json.loads(raw.read_text(encoding="utf-8"))
            lon, lat = document["geometry"]["coordinates"][:2]
            row["eventUtc"] = datetime.fromtimestamp(document["properties"]["time"] / 1000, tz=UTC).isoformat().replace("+00:00", "Z")
            row["knowledgeCutoffDate"] = min(event["start"], row["eventUtc"][:10])
            row.update(lon=lon, lat=lat, locationPrecision="exact", locationBasis="Published USGS epicenter; not a factory coordinate")
            sources.append({"title": f"USGS earthquake GeoJSON: {event['earthquakeId']}", "url": url})
        elif event.get("referencePoint"):
            point = event["referencePoint"]
            row.update(lon=point["lon"], lat=point["lat"], locationPrecision=point["precision"], locationBasis=point["basis"])
            sources.append(point["source"])
        else:
            match, reason = gazetteer.match(event["location"], event["country"])
            if not match or match["precision"] != "city":
                raise ValueError(f"Event city anchor unavailable: {event['id']} ({reason})")
            row.update(lon=match["lon"], lat=match["lat"], locationPrecision="city", locationBasis="Natural Earth city point; not an exact disrupted-facility coordinate")
            sources.append(city_source)
        row["zone"] = json.dumps(event["zone"])
        row["sources"] = json.dumps(sources, ensure_ascii=False)
        output.append(row)
    with (ROOT / "data/events.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["id", "title", "type", "start", "end", "eventYear", "snapshotYear", "eventUtc", "knowledgeCutoffDate", "location", "country", "lon", "lat", "locationPrecision", "locationBasis", "dateBasis", "endBasis", "zone", "sourceTitle", "sourceUrl", "sources"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    (ROOT / "data/review/event_gaps.json").write_text(json.dumps({"policy": "Use verified editions and record gaps (user instruction); do not substitute another year's list", "events": gaps}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output)} sourced events; {len(gaps)} event-year snapshot gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
