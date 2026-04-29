# api/sessions.py - Session és lap feltöltés / lekérés
# MotoMeter backend

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session, Lap, Track
from schemas import (
    SessionUpload, SessionResponse, SessionListItem,
    LapResponse, SectorTimeSchema, GpsPointSchema,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ============================================================
# POST /sessions/upload  — firmware batch feltöltés
# ============================================================

@router.post("/upload", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def upload_session(payload: SessionUpload, db: DBSession = Depends(get_db)):
    """
    A CoreS3 firmware ezt a végpontot hívja session feltöltéskor.
    Egy payload = egy session, benne az összes kör adatával.
    """
    # started_at parse (ha üres → most)
    started_at = _parse_dt(payload.started_at)

    session = Session(
        device_id  = payload.device_id,
        track_id   = payload.track_id,
        rider_name = payload.rider_name,
        started_at = started_at,
    )
    session.conditions = payload.conditions
    db.add(session)
    db.flush()   # session.id megkapja az értékét

    # Szektornév lista a track-ből (ha van)
    sector_names = _get_sector_names(payload.track_id, db)

    for lap_data in payload.laps:
        # Szektoridők összerendelése névvel
        sector_times = _zip_sector_times(lap_data.sector_times_ms, sector_names)

        lap = Lap(
            session_id   = session.id,
            lap_number   = lap_data.lap_number,
            lap_time_ms  = lap_data.lap_time_ms,
            lap_start_ts = lap_data.lap_start_ts,
            lap_end_ts   = lap_data.lap_end_ts,
            is_valid     = True,
        )
        lap.gps_trace    = [p.model_dump() for p in lap_data.gps_trace]
        lap.sector_times = sector_times
        db.add(lap)

    # ended_at = utolsó kör vége vagy most
    if payload.laps:
        last = payload.laps[-1]
        session.ended_at = _parse_dt("") if not last.lap_end_ts else \
                           datetime.fromtimestamp(last.lap_end_ts / 1000, tz=timezone.utc)

    db.commit()
    db.refresh(session)
    return _to_session_response(session)


# ============================================================
# GET /sessions  — session lista
# ============================================================

@router.get("/", response_model=list[SessionListItem])
def list_sessions(
    track_id:  int | None = None,
    device_id: str | None = None,
    limit:     int = 50,
    db: DBSession = Depends(get_db),
):
    q = db.query(Session).order_by(Session.started_at.desc())
    if track_id:
        q = q.filter(Session.track_id == track_id)
    if device_id:
        q = q.filter(Session.device_id == device_id)
    sessions = q.limit(limit).all()

    result = []
    for s in sessions:
        track_name = s.track.name if s.track else None
        valid_laps = [l for l in s.laps if l.is_valid]
        best_ms    = min((l.lap_time_ms for l in valid_laps), default=None)
        result.append(SessionListItem(
            id          = s.id,
            device_id   = s.device_id,
            rider_name  = s.rider_name,
            track_id    = s.track_id,
            track_name  = track_name,
            started_at  = s.started_at,
            lap_count   = len(valid_laps),
            best_lap_ms = best_ms,
        ))
    return result


# ============================================================
# GET /sessions/{id}  — session részletei
# ============================================================

@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nem található")
    return _to_session_response(session)


# ============================================================
# GET /sessions/{id}/laps/{lap_id}/trace  — GPS trace lekérés
# ============================================================

@router.get("/{session_id}/laps/{lap_id}/trace")
def get_lap_trace(session_id: int, lap_id: int, db: DBSession = Depends(get_db)):
    lap = db.get(Lap, lap_id)
    if not lap or lap.session_id != session_id:
        raise HTTPException(status_code=404, detail="Kör nem található")
    return {
        "lap_id":      lap.id,
        "lap_number":  lap.lap_number,
        "lap_time_ms": lap.lap_time_ms,
        "gps_trace":   lap.gps_trace,
    }


# ============================================================
# DELETE /sessions/{id}
# ============================================================

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DBSession = Depends(get_db)):
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nem található")
    db.delete(session)
    db.commit()


# ============================================================
# Segédek
# ============================================================

def _parse_dt(s: str) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _get_sector_names(track_id: int | None, db: DBSession) -> list[str]:
    if not track_id:
        return []
    track = db.get(Track, track_id)
    if not track:
        return []
    return [s["name"] for s in track.sectors]


def _zip_sector_times(times_ms: list[int], names: list[str]) -> list[dict]:
    """Szektoridő ms lista + névlista → [{"name": "S1", "time_ms": 9800}, ...]"""
    result = []
    for i, t in enumerate(times_ms):
        name = names[i] if i < len(names) else f"S{i + 1}"
        result.append({"name": name, "time_ms": t})
    return result


def _to_session_response(s: Session) -> SessionResponse:
    valid_laps = [l for l in s.laps if l.is_valid]
    best_ms    = min((l.lap_time_ms for l in valid_laps), default=None)

    laps_out = []
    for lap in s.laps:
        laps_out.append(LapResponse(
            id           = lap.id,
            lap_number   = lap.lap_number,
            lap_time_ms  = lap.lap_time_ms,
            is_valid     = lap.is_valid,
            sector_times = [SectorTimeSchema(**st) for st in lap.sector_times],
            has_trace    = len(lap.gps_trace) > 0,
        ))

    return SessionResponse(
        id          = s.id,
        device_id   = s.device_id,
        rider_name  = s.rider_name,
        track_id    = s.track_id,
        started_at  = s.started_at,
        ended_at    = s.ended_at,
        lap_count   = len(valid_laps),
        best_lap_ms = best_ms,
        laps        = laps_out,
    )
