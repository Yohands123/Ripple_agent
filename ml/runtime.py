"""Load a project-local OpenMP runtime when the system does not provide one."""

import ctypes
import ctypes.util
import hashlib
import io
import json
import platform
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
_OPENMP = None


def ensure_openmp():
    global _OPENMP
    if _OPENMP is not None or platform.system() != "Linux":
        return
    system = ctypes.util.find_library("gomp")
    if system:
        _OPENMP = ctypes.CDLL(system, mode=ctypes.RTLD_GLOBAL)
        return
    if platform.machine() != "x86_64":
        raise RuntimeError("This project-local OpenMP fallback is for Linux amd64")
    config = json.loads((ROOT / "data/sources/openmp.json").read_text(encoding="utf-8"))
    raw = ROOT / "data/raw/runtime"
    raw.mkdir(parents=True, exist_ok=True)
    package = raw / "libgomp1.deb"
    if not package.exists():
        with urlopen(config["url"], timeout=30) as response:
            package.write_bytes(response.read())
    if hashlib.sha256(package.read_bytes()).hexdigest() != config["sha256"]:
        raise ValueError("OpenMP package differs from pinned Ubuntu SHA-256")
    archive = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(package)], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:
        matches = [member for member in handle.getmembers() if member.isfile() and member.name.endswith("/libgomp.so.1.0.0")]
        if len(matches) != 1:
            raise ValueError("OpenMP package contains no unique runtime library")
        contents = handle.extractfile(matches[0]).read()
    library = raw / "libgomp.so.1.0.0"
    if not library.exists() or library.read_bytes() != contents:
        library.write_bytes(contents)
    _OPENMP = ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)
