# schemas.py - Pydantic request/response sémák
# MotoMeter backend

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# TRACK sémák
# ============================================================

class FinishLineSchema(BaseModel):
    lat1: float
    lon1: float
    lat2: float
    lon2: float


class SectorSchema(BaseModel):
    name: str
    lat1: float
    lon1: float
    lat2: float
    lon2: float


class CenterlinePointSchema(BaseModel):
    lat: float
    lon: float


class StartLineSchema(BaseModel):
    lat1: float
    lon1: float
    lat2: float
    lon2: float


class TrackCreate(BaseModel):
    name:        str            = Field(..., min_length=1, max_length=120)
    country:     str            = Field("HU", max_length=60)
    track_type:  str            = Field("circuit")   # "circuit" | "stage"
    finish_line: FinishLineSchema
    start_line:  StartLineSchema | None = None        # csak stage módban
    sectors:     list[SectorSchema]          = Field(default_factory=list)
    centerline:  list[CenterlinePointSchema] = Field(default_factory=list)


class TrackResponse(BaseModel):
    id:          int
    name:        str
    country:     str
    created_at:  datetime
    track_type:  str
    finish_line: FinishLineSchema
    start_line:  StartLineSchema | None
    sectors:     list[SectorSchema]
    centerline:  list[CenterlinePointSchema]
    length_m:    float

    model_config = {"from_attributes": True}


class TrackListItem(BaseModel):
    id:            int
    name:          str
    country:       str
    length_m:      float
    sectors_count: int
    track_type:    str

    model_config = {"from_attributes": True}


# ============================================================
# SESSION / LAP sémák (firmware feltöltés)
# ============================================================

class GpsPointSchema(BaseModel):
    lat:         float
    lon:         float
    speed_kmh:   float = 0.0
    ts_ms:       int   = 0
    lean:        float | None = None   # dőlésszög fokban (lap.py: 'lean')
    lean_deg:    float | None = None   # alternatív mező neve (gps_task replace)
    lat_g:       float | None = None   # oldalsó G-erő
    lon_g:       float | None = None   # hosszirányú G-erő
    kamm_angle:  float | None = None   # irányvektor szöge

    model_config = {"extra": "ignore"}

    @property
    def lean_val(self) -> float | None:
        """lean vagy lean_deg, amelyik nem None."""
        return self.lean if self.lean is not None else self.lean_deg


class SectorTimeSchema(BaseModel):
    name:    str
    time_ms: int


class LapUpload(BaseModel):
    lap_number:       int
    lap_time_ms:      int
    lap_start_ts:     int | None = None
    lap_end_ts:       int | None = None
    sector_times_ms:  list[int]  = Field(default_factory=list)
    gps_trace:        list[GpsPointSchema] = Field(default_factory=list)
    max_speed_kmh:    float | None = None
    max_lean_right:   float | None = None
    max_lean_left:    float | None = None
    peak_kamm_g:      float | None = None
    peak_kamm_angle:  float | None = None


class SessionUpload(BaseModel):
    """A firmware által feltöltött session payload."""
    device_id:   str
    track_id:    int | None = None    # None = ismeretlen pálya
    rider_name:  str        = ""
    started_at:  str        = ""      # ISO 8601 vagy üres
    laps:        list[LapUpload] = Field(default_factory=list)
    conditions:  dict       = Field(default_factory=dict)


class LapResponse(BaseModel):
    id:          int
    lap_number:  int
    lap_time_ms: int
    is_valid:    bool
    sector_times: list[SectorTimeSchema]
    has_trace:   bool

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id:          int
    device_id:   str
    rider_name:  str
    track_id:    int | None
    started_at:  datetime
    ended_at:    datetime | None
    lap_count:   int
    best_lap_ms: int | None
    laps:        list[LapResponse]

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id:          int
    device_id:   str
    rider_name:  str
    track_id:    int | None
    track_name:  str | None
    started_at:  datetime
    lap_count:   int
    best_lap_ms: int | None

    model_config = {"from_attributes": True}


# ============================================================
# ANALYSIS sémák
# ============================================================

class SectorBestSchema(BaseModel):
    name:        str
    time_ms:     int
    lap_number:  int


class LapDeltaPoint(BaseModel):
    """Egy pont a delta grafikonhoz: s-koordináta + delta ms"""
    s:        float    # 0.0 – 1.0 pályahaladás
    delta_ms: int


class SpeedPoint(BaseModel):
    s:         float
    speed_kmh: float


class LapAnalysisRow(BaseModel):
    lap_number:     int
    lap_time_ms:    int
    is_best:        bool
    delta_ms:       int       # vs best lap
    sector_times:   list[SectorTimeSchema]
    max_lean_right:  float | None = None
    max_lean_left:   float | None = None
    peak_kamm_g:     float | None = None
    peak_kamm_angle: float | None = None


class SessionAnalysis(BaseModel):
    session_id:          int
    track_name:          str | None
    lap_count:           int
    best_lap_ms:         int | None
    theoretical_best_ms: int | None
    consistency_score:   float | None   # 0–100
    sector_bests:        list[SectorBestSchema]
    laps:                list[LapAnalysisRow]


class LapDetail(BaseModel):
    """Egy kör részletes adatai vizualizációhoz."""
    lap_id:      int
    lap_number:  int
    lap_time_ms: int
    gps_trace:   list[GpsPointSchema]
    speed_curve: list[SpeedPoint]        # s-koordináta + sebesség


class LapCompare(BaseModel):
    """Két kör delta összehasonlítása."""
    lap_a_id:    int
    lap_b_id:    int
    delta_curve: list[LapDeltaPoint]     # s-koordináta + delta
