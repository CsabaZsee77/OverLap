# api/tracks.py - Pálya CRUD végpontok
# MotoMeter backend

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Track
from schemas import TrackCreate, TrackResponse, TrackListItem, StartLineSchema
from core.track_math import centerline_length_m

router = APIRouter(prefix="/tracks", tags=["tracks"])


# ============================================================
# GET /tracks  — pályák listája
# ============================================================

@router.get("/", response_model=list[TrackListItem])
def list_tracks(db: Session = Depends(get_db)):
    tracks = db.query(Track).order_by(Track.name).all()
    result = []
    for t in tracks:
        result.append(TrackListItem(
            id             = t.id,
            name           = t.name,
            country        = t.country,
            length_m       = t.length_m,
            sectors_count  = len(t.sectors),
            track_type     = t.track_type,
        ))
    return result


# ============================================================
# GET /tracks/{id}  — egy pálya részletei
# ============================================================

@router.get("/{track_id}", response_model=TrackResponse)
def get_track(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")
    return _to_response(track)


# ============================================================
# POST /tracks  — új pálya mentése
# ============================================================

@router.post("/", response_model=TrackResponse, status_code=status.HTTP_201_CREATED)
def create_track(payload: TrackCreate, db: Session = Depends(get_db)):
    cl = [p.model_dump() for p in payload.centerline]
    length = centerline_length_m(cl)

    track = Track(
        name=payload.name, country=payload.country,
        track_type=payload.track_type, length_m=length,
    )
    track.finish_line = payload.finish_line.model_dump()
    track.start_line  = payload.start_line.model_dump() if payload.start_line else None
    track.sectors     = [s.model_dump() for s in payload.sectors]
    track.centerline  = cl

    db.add(track)
    db.commit()
    db.refresh(track)
    return _to_response(track)


# ============================================================
# PUT /tracks/{id}  — pálya frissítése (centerline / szektorok módosítás)
# ============================================================

@router.put("/{track_id}", response_model=TrackResponse)
def update_track(track_id: int, payload: TrackCreate, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")

    cl = [p.model_dump() for p in payload.centerline]
    track.name        = payload.name
    track.country     = payload.country
    track.track_type  = payload.track_type
    track.finish_line = payload.finish_line.model_dump()
    track.start_line  = payload.start_line.model_dump() if payload.start_line else None
    track.sectors     = [s.model_dump() for s in payload.sectors]
    track.centerline  = cl
    track.length_m    = centerline_length_m(cl)

    db.commit()
    db.refresh(track)
    return _to_response(track)


# ============================================================
# DELETE /tracks/{id}
# ============================================================

@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")
    db.delete(track)
    db.commit()


# ============================================================
# GET /tracks/{id}/firmware-json  — board-kompatibilis track.json letöltés
# ============================================================

@router.get("/{track_id}/firmware-json")
def get_firmware_json(track_id: int, db: Session = Depends(get_db)):
    import json as _json
    from fastapi.responses import Response as _Response

    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")

    data: dict = {
        "name":       track.name,
        "track_type": track.track_type,
        "finish_line": track.finish_line,
    }
    if track.start_line:
        data["start_line"] = track.start_line
    data["sectors"] = track.sectors or []

    content = _json.dumps(data, indent=2, ensure_ascii=False)
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in track.name).strip("_") or "track"
    return _Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe}_track.json"'},
    )


# ============================================================
# GET /tracks/{id}/curvature  — görbületi profil
# ============================================================

@router.get("/{track_id}/curvature")
def get_curvature(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")

    from core.track_math import curvature_profile
    profile = curvature_profile(track.centerline)
    return {"track_id": track_id, "curvature": profile}


# ============================================================
# Segéd
# ============================================================

def _to_response(track: Track) -> TrackResponse:
    from schemas import FinishLineSchema, SectorSchema, CenterlinePointSchema
    fl = track.finish_line
    sl = track.start_line
    return TrackResponse(
        id          = track.id,
        name        = track.name,
        country     = track.country,
        created_at  = track.created_at,
        track_type  = track.track_type,
        finish_line = FinishLineSchema(**fl),
        start_line  = StartLineSchema(**sl) if sl else None,
        sectors     = [SectorSchema(**s) for s in track.sectors],
        centerline  = [CenterlinePointSchema(**p) for p in track.centerline],
        length_m    = track.length_m,
    )
