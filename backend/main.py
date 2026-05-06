# main.py - MotoMeter FastAPI backend
# Indítás: uvicorn main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from api import tracks, sessions, analysis, live

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title       = "MotoMeter API",
    description = "Motoros telemetria és köridőmérő backend",
    version     = "0.1.0",
)

# ============================================================
# CORS — frontend (localhost:5173 dev, éles domainen is)
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # élesbe: konkrét domain
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ============================================================
# ROUTEREK
# ============================================================

app.include_router(tracks.router,   prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(live.router,     prefix="/api")

# ============================================================
# STARTUP — DB init
# ============================================================

@app.on_event("startup")
def on_startup():
    init_db()
    print("MotoMeter API indult -> http://localhost:8000")
    print("Docs -> http://localhost:8000/docs")

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "service": "motometer-api"}


# ============================================================
# DEMO ADAT BETÖLTÉS (csak dev módban)
# ============================================================

@app.post("/api/dev/seed", tags=["system"], include_in_schema=False)
def seed_demo_data():
    """
    Demo adatok betöltése teszteléshez.
    Létrehoz egy Kakucs Ring pályát és egy minta sessiont.
    """
    from database import SessionLocal
    from models import Track, Session, Lap
    import json
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        # Ha már van adat, skip
        if db.query(Track).count() > 0:
            return {"status": "skipped", "reason": "már van adat"}

        # --- Kakucs Ring demo pálya ---
        track = Track(
            name       = "Kakucs Ring",
            country    = "HU",
            track_type = "circuit",
            length_m   = 1050.0,
        )
        track.finish_line = {
            "lat1": 47.087900, "lon1": 19.282800,
            "lat2": 47.088100, "lon2": 19.283200,
        }
        track.sectors = [
            {"name": "S1", "lat1": 47.089200, "lon1": 19.284500,
                           "lat2": 47.089400, "lon2": 19.284900},
            {"name": "S2", "lat1": 47.091000, "lon1": 19.283000,
                           "lat2": 47.091200, "lon2": 19.283400},
            {"name": "S3", "lat1": 47.090200, "lon1": 19.280500,
                           "lat2": 47.090400, "lon2": 19.280900},
        ]
        # Egyszerűsített centerline (valódi pálya közelítése)
        track.centerline = [
            {"lat": 47.088000, "lon": 19.283000},
            {"lat": 47.088500, "lon": 19.283800},
            {"lat": 47.089300, "lon": 19.284700},
            {"lat": 47.090200, "lon": 19.284500},
            {"lat": 47.091100, "lon": 19.283200},
            {"lat": 47.091200, "lon": 19.282000},
            {"lat": 47.090800, "lon": 19.280800},
            {"lat": 47.090300, "lon": 19.280600},
            {"lat": 47.089500, "lon": 19.281200},
            {"lat": 47.088800, "lon": 19.282000},
            {"lat": 47.088000, "lon": 19.283000},
        ]
        db.add(track)
        db.flush()

        # --- Demo session ---
        session = Session(
            device_id  = "mm_demo001",
            track_id   = track.id,
            rider_name = "Demo Rider",
            started_at = datetime(2026, 4, 24, 10, 30, 0, tzinfo=timezone.utc),
        )
        session.conditions = {"weather": "sunny", "temp_c": 18}
        db.add(session)
        db.flush()

        # --- 5 demo kör ---
        demo_laps = [
            (63_400, [10_200, 12_100, 11_500, 10_800, 11_200,  7_600]),
            (61_800, [ 9_900, 11_700, 11_100, 10_200, 10_900,  8_000]),
            (60_500, [ 9_700, 11_400, 10_800,  9_900, 10_600,  8_100]),
            (61_200, [ 9_800, 11_600, 10_900, 10_100, 10_700,  8_100]),
            (59_900, [ 9_500, 11_200, 10_500,  9_700, 10_400,  8_600]),  # best
        ]
        sector_names = ["S1", "S2", "S3", "S4", "S5", "S6"]

        for i, (lap_ms, sectors) in enumerate(demo_laps, start=1):
            lap = Lap(
                session_id  = session.id,
                lap_number  = i,
                lap_time_ms = lap_ms,
                is_valid    = True,
            )
            lap.sector_times = [
                {"name": sector_names[j], "time_ms": t}
                for j, t in enumerate(sectors)
            ]
            # Mini GPS trace (egyszerűsített, vizualizációhoz)
            lap.gps_trace = _make_demo_trace(track.centerline, lap_ms)
            db.add(lap)

        db.commit()
        return {
            "status":     "ok",
            "track_id":   track.id,
            "session_id": session.id,
            "laps":       len(demo_laps),
        }

    finally:
        db.close()


def _make_demo_trace(centerline: list, lap_ms: int) -> list:
    """Egyszerű demo GPS trace a centerline pontjaiból."""
    import math
    n     = len(centerline)
    trace = []
    for i, pt in enumerate(centerline):
        progress = i / max(n - 1, 1)
        ts_ms    = int(progress * lap_ms)
        speed    = 60.0 + 40.0 * math.sin(progress * math.pi)   # 60–100 km/h szinuszos
        trace.append({
            "lat":       pt["lat"],
            "lon":       pt["lon"],
            "speed_kmh": round(speed, 1),
            "ts_ms":     ts_ms,
        })
    return trace
