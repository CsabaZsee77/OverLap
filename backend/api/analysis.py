# api/analysis.py - Session analitika végpontok
# MotoMeter backend

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session, Lap, Track
from schemas import (
    SessionAnalysis, SectorBestSchema, LapAnalysisRow,
    SectorTimeSchema, LapDetail, LapCompare, GpsPointSchema,
    SpeedPoint, LapDeltaPoint,
)
from core.lap_analysis import (
    theoretical_best_ms,
    sector_bests_detail,
    consistency_score,
    lap_analysis_rows,
    delta_curve,
)
from core.track_math import build_s_index, gps_trace_to_s_speed

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ============================================================
# GET /analysis/session/{id}  — teljes session analitika
# ============================================================

@router.get("/session/{session_id}", response_model=SessionAnalysis)
def session_analysis(session_id: int, db: DBSession = Depends(get_db)):
    """
    Egy session összes analitikai adata egy válaszban:
    best lap, theoretical best, consistency score, szektor bontás, lap lista.
    """
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nem található")

    laps        = session.laps
    track_name  = session.track.name if session.track else None
    valid_laps  = [l for l in laps if l.is_valid]
    best_ms     = min((l.lap_time_ms for l in valid_laps), default=None)

    # Theoretical best
    th_best = theoretical_best_ms(laps)

    # Consistency
    consistency = consistency_score(laps)

    # Szektor bontás
    sb = sector_bests_detail(laps)
    sector_bests_out = [
        SectorBestSchema(name=x["name"], time_ms=x["time_ms"], lap_number=x["lap_number"])
        for x in sb
    ]

    # Lap sorok
    rows = lap_analysis_rows(laps)
    laps_out = []
    for r in rows:
        laps_out.append(LapAnalysisRow(
            lap_number   = r["lap_number"],
            lap_time_ms  = r["lap_time_ms"],
            is_best      = r["is_best"],
            delta_ms     = r["delta_ms"],
            sector_times = [SectorTimeSchema(**st) for st in r["sector_times"]],
        ))

    return SessionAnalysis(
        session_id          = session_id,
        track_name          = track_name,
        lap_count           = len(valid_laps),
        best_lap_ms         = best_ms,
        theoretical_best_ms = th_best,
        consistency_score   = consistency,
        sector_bests        = sector_bests_out,
        laps                = laps_out,
    )


# ============================================================
# GET /analysis/lap/{id}  — egy kör részletes adatai + sebesség görbe
# ============================================================

@router.get("/lap/{lap_id}", response_model=LapDetail)
def lap_detail(lap_id: int, db: DBSession = Depends(get_db)):
    """
    Egy kör GPS trace-e + s-koordináta alapú sebesség görbe.
    A frontend térképen és grafikonon jeleníti meg.
    """
    lap = db.get(Lap, lap_id)
    if not lap:
        raise HTTPException(status_code=404, detail="Kör nem található")

    # S-koordináta index a pályából (ha van)
    s_index = _get_s_index(lap.session.track_id, db)

    speed_curve = []
    if s_index:
        pts = gps_trace_to_s_speed(lap.gps_trace, s_index)
        speed_curve = [SpeedPoint(s=p["s"], speed_kmh=p["speed_kmh"]) for p in pts]

    return LapDetail(
        lap_id      = lap.id,
        lap_number  = lap.lap_number,
        lap_time_ms = lap.lap_time_ms,
        gps_trace   = [GpsPointSchema(**p) for p in lap.gps_trace],
        speed_curve = speed_curve,
    )


# ============================================================
# GET /analysis/compare?lap_a=1&lap_b=2  — két kör delta görbéje
# ============================================================

@router.get("/compare", response_model=LapCompare)
def compare_laps(
    lap_a: int,
    lap_b: int,
    db: DBSession = Depends(get_db),
):
    """
    Két kör delta görbéje s-koordináta mentén.
    lap_a = referencia (pl. best lap), lap_b = összehasonlítandó.
    """
    la = db.get(Lap, lap_a)
    lb = db.get(Lap, lap_b)
    if not la:
        raise HTTPException(status_code=404, detail=f"Kör {lap_a} nem található")
    if not lb:
        raise HTTPException(status_code=404, detail=f"Kör {lap_b} nem található")

    # S-index: lap_a session pályájából (ha nincs, üres delta)
    s_index = _get_s_index(la.session.track_id, db)

    curve = delta_curve(la.gps_trace, lb.gps_trace, s_index)
    delta_out = [LapDeltaPoint(s=p["s"], delta_ms=p["delta_ms"]) for p in curve]

    return LapCompare(lap_a_id=lap_a, lap_b_id=lap_b, delta_curve=delta_out)


# ============================================================
# GET /analysis/leaderboard/{track_id}  — pálya rangliasta
# ============================================================

@router.get("/leaderboard/{track_id}")
def leaderboard(
    track_id: int,
    period:   str = "all",   # all | today | week | month
    limit:    int = 20,
    db: DBSession = Depends(get_db),
):
    """
    Egy pálya legjobb köridői. Period szűrő: all / today / week / month.
    """
    from datetime import date, timedelta

    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pálya nem található")

    # Időszak szűrő
    cutoff = None
    today  = date.today()
    if period == "today":
        cutoff = datetime_from_date(today)
    elif period == "week":
        cutoff = datetime_from_date(today - timedelta(days=7))
    elif period == "month":
        cutoff = datetime_from_date(today - timedelta(days=30))

    from sqlalchemy import func
    from models import Session as SessionModel

    q = (
        db.query(
            func.min(Lap.lap_time_ms).label("best_ms"),
            SessionModel.device_id,
            SessionModel.rider_name,
            SessionModel.id.label("session_id"),
        )
        .join(SessionModel, Lap.session_id == SessionModel.id)
        .filter(SessionModel.track_id == track_id)
        .filter(Lap.is_valid == True)
    )
    if cutoff:
        q = q.filter(SessionModel.started_at >= cutoff)

    q = q.group_by(SessionModel.device_id).order_by("best_ms").limit(limit)
    rows = q.all()

    result = []
    for i, r in enumerate(rows):
        best_ms = r.best_ms
        result.append({
            "rank":       i + 1,
            "device_id":  r.device_id,
            "rider_name": r.rider_name or r.device_id,
            "session_id": r.session_id,
            "best_lap_ms": best_ms,
            "best_lap_fmt": _fmt_ms(best_ms),
        })

    return {
        "track_id":   track_id,
        "track_name": track.name,
        "period":     period,
        "entries":    result,
    }


# ============================================================
# Segédek
# ============================================================

def _get_s_index(track_id: int | None, db: DBSession) -> list[dict]:
    if not track_id:
        return []
    track = db.get(Track, track_id)
    if not track or not track.centerline:
        return []
    return build_s_index(track.centerline)


def _fmt_ms(ms: int) -> str:
    s_total = ms // 1000
    return f"{s_total // 60}:{s_total % 60:02d}.{ms % 1000:03d}"


def datetime_from_date(d):
    from datetime import datetime, timezone
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
