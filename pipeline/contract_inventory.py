"""Keep the approved contract's field inventory aligned with real exports."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!-- BEGIN REAL EXPORT FIELD INVENTORY -->"


def field_inventory(folder):
    groups = defaultdict(lambda: defaultdict(set))

    def visit(value, path, fields):
        kind = "null" if value is None else "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "object"
        fields[path or "$"].add(kind)
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, (path + "." if path else "") + key, fields)
        elif isinstance(value, list):
            for child in value:
                visit(child, path + "[]", fields)

    for path in sorted(folder.rglob("*.json")):
        relative = path.relative_to(folder).as_posix()
        group = "Network" if relative == "network.json" or relative.startswith("networks/") else "Scenario index" if relative == "scenarios/index.json" else "Scenario" if relative.startswith("scenarios/") else path.stem.title()
        visit(json.loads(path.read_text(encoding="utf-8")), "", groups[group])
    return groups


def inventory_text(folder):
    lines = [MARKER, "## Complete real-export field inventory", "",
             "Every emitted field is enumerated below, including nested evidence and assumption records. Types describe observed JSON values; the semantic rules above define allowed nulls and ranges. Variant-specific fields are optional. `[]` denotes array elements; `$` denotes the root. Integer is a subtype of number. Qualitative confidence is never a probability.", ""]
    for group, fields in sorted(field_inventory(folder).items()):
        lines += ["### " + group, "", "| Field | Observed JSON types |", "|---|---|"]
        for name, types in sorted(fields.items()):
            lines.append("| `" + name + "` | " + ", ".join(sorted(types)) + " |")
        lines.append("")
    lines += ["<!-- END REAL EXPORT FIELD INVENTORY -->", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "docs/contracts.md"
    document = path.read_text(encoding="utf-8")
    prefix = document.split(MARKER)[0].rstrip() + "\n\n"
    expected = prefix + inventory_text(ROOT / "web/public/data/real")
    if args.check:
        if document != expected:
            raise SystemExit("Contract field inventory differs from the real export; review and regenerate it")
        print("Every real-export field is documented")
    else:
        path.write_text(expected, encoding="utf-8")
        print("Updated approved contract field inventory")


if __name__ == "__main__":
    main()
