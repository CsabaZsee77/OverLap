# api/live.py — valós idejű GPS live tracking endpoint
# MotoMeter backend

import time
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/live", tags=["live"])

# In-memory state: device_id → {points, lap_number, updated_at}
_state: dict = {}
MAX_POINTS = 600   # ~2 perc 5 Hz-en


class LivePoint(BaseModel):
    lat:       float
    lon:       float
    speed_kmh: float = 0.0
    ts_ms:     int   = 0
    lean_deg:  float | None = None
    lat_g:     float | None = None
    lon_g:     float | None = None

    model_config = {"extra": "ignore"}


class LivePush(BaseModel):
    device_id:  str
    points:     list[LivePoint]
    lap_number: int | None = None


@router.post("/{device_id}", include_in_schema=True)
def push_live(device_id: str, payload: LivePush):
    s = _state.setdefault(device_id, {"points": [], "lap_number": None, "updated_at": 0.0})

    # Új kör → töröljük a régi trace-t
    if payload.lap_number is not None and payload.lap_number != s["lap_number"]:
        s["points"]     = []
        s["lap_number"] = payload.lap_number

    new_pts = [p.model_dump(exclude_none=True) for p in payload.points]
    s["points"].extend(new_pts)
    if len(s["points"]) > MAX_POINTS:
        s["points"] = s["points"][-MAX_POINTS:]
    s["updated_at"] = time.time()

    return {"ok": True, "count": len(s["points"])}


@router.get("/")
def list_active():
    """Aktív eszközök (utolsó 15 másodpercben küldtek adatot)."""
    now = time.time()
    return [
        {
            "device_id":  did,
            "lap_number": s["lap_number"],
            "updated_at": s["updated_at"],
            "point_count": len(s["points"]),
        }
        for did, s in _state.items()
        if now - s["updated_at"] < 15
    ]


@router.get("/{device_id}")
def get_live(device_id: str):
    s   = _state.get(device_id, {"points": [], "lap_number": None, "updated_at": 0.0})
    now = time.time()
    return {
        "device_id":  device_id,
        "lap_number": s["lap_number"],
        "points":     s["points"],
        "updated_at": s["updated_at"],
        "stale":      now - s["updated_at"] > 10,
    }


@router.delete("/{device_id}", include_in_schema=False)
def clear_live(device_id: str):
    _state.pop(device_id, None)
    return {"ok": True}
