import json
from datetime import datetime
from pathlib import Path

def clamp(v, lo, hi): return max(lo, min(hi, v))

def timestamp(fmt="%Y%m%d_%H%M%S") -> str:
    return datetime.now().strftime(fmt)

def write_meta(path: Path, kind: str, pan: float, tilt: float, extra=None):
    meta = {
        "file": str(path),
        "type": kind,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "pan": pan,
        "tilt": tilt,
    }
    if extra: meta.update(extra)
    with open(str(path) + ".json", "w") as f:
        json.dump(meta, f, indent=2)
