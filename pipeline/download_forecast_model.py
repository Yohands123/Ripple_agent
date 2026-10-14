"""Cache pinned public Chronos weights in data/raw/ without an API credential."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def download():
    spec = json.loads((ROOT / "data/sources/costs.json").read_text())["model"]
    folder = ROOT / "data/raw/cost_models" / spec["revision"]
    folder.mkdir(parents=True, exist_ok=True)
    for name in ["config.json", "model.safetensors"]:
        path = folder / name
        if not path.exists():
            url = f"https://huggingface.co/{spec['id']}/resolve/{spec['revision']}/{name}"
            with urllib.request.urlopen(url, timeout=120) as response:
                payload = response.read()
            if name == "model.safetensors" and hashlib.sha256(payload).hexdigest() != spec["weightsSha256"]:
                raise ValueError("Model weight checksum mismatch")
            path.write_bytes(payload)
        if name == "model.safetensors" and hashlib.sha256(path.read_bytes()).hexdigest() != spec["weightsSha256"]:
            raise ValueError("Cached model weight checksum mismatch")
        print(name, path.stat().st_size, flush=True)
    return folder


if __name__ == "__main__":
    download()
