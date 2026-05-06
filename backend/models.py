# models.py - SQLAlchemy ORM modellek
# MotoMeter backend

import json
from datetime import datetime, timezone
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# TRACK — pálya definíció
# ============================================================

class Track(Base):
    """
    Egy pálya teljes definíciója:
      - finish_line: két GPS pont JSON-ban
      - sectors:    lista GPS pont-párokból JSON-ban
      - centerline: polyline GPS pontok listája JSON-ban
    """
    __tablename__ = "tracks"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    name:        Mapped[str]  = mapped_column(String(120), nullable=False)
    country:     Mapped[str]  = mapped_column(String(60),  nullable=False, default="HU")
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=_now)

    # circuit (start = finish) vagy stage (külön startvonal)
    track_type: Mapped[str] = mapped_column(String(16), nullable=False, default="circuit")

    # Rajtvonal / célvonal — {"lat1":x,"lon1":x,"lat2":x,"lon2":x}
    finish_line_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Startvonal (csak stage módban) — None = nincs, circuit módban nem használt
    start_line_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Szektorok — [{"name":"S1","lat1":x,"lon1":x,"lat2":x,"lon2":x}, ...]
    sectors_json:     Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Középvonal — [{"lat":x,"lon":x}, ...]
    centerline_json:  Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Számított pályahossz (m) — centerline-ból
    length_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    sessions: Mapped[list["Session"]] = relationship(back_populates="track")

    # --- property shortcutok ---

    @property
    def finish_line(self) -> dict:
        return json.loads(self.finish_line_json)

    @finish_line.setter
    def finish_line(self, value: dict):
        self.finish_line_json = json.dumps(value)

    @property
    def start_line(self) -> dict | None:
        if self.start_line_json is None:
            return None
        return json.loads(self.start_line_json)

    @start_line.setter
    def start_line(self, value: dict | None):
        self.start_line_json = json.dumps(value) if value is not None else None

    @property
    def sectors(self) -> list:
        return json.loads(self.sectors_json)

    @sectors.setter
    def sectors(self, value: list):
        self.sectors_json = json.dumps(value)

    @property
    def centerline(self) -> list:
        return json.loads(self.centerline_json)

    @centerline.setter
    def centerline(self, value: list):
        self.centerline_json = json.dumps(value)


# ============================================================
# SESSION — egy motoros egy napi edzés-blokkja
# ============================================================

class Session(Base):
    """
    Egy mérési session (pl. egy nap Kakucson).
    Egy session több kört tartalmaz.
    """
    __tablename__ = "sessions"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    device_id:  Mapped[str]  = mapped_column(String(40),  nullable=False, index=True)
    track_id:   Mapped[int]  = mapped_column(ForeignKey("tracks.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Opcionális felhasználói azonosítás (majd M08 user rendszerrel)
    rider_name: Mapped[str]  = mapped_column(String(80), nullable=False, default="")

    # Körülmények (opcionális)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    track:  Mapped["Track"]       = relationship(back_populates="sessions")
    laps:   Mapped[list["Lap"]]   = relationship(back_populates="session",
                                                  order_by="Lap.lap_number")

    @property
    def conditions(self) -> dict:
        return json.loads(self.conditions_json)

    @conditions.setter
    def conditions(self, value: dict):
        self.conditions_json = json.dumps(value)

    @property
    def best_lap_ms(self) -> int | None:
        valid = [l.lap_time_ms for l in self.laps if l.is_valid]
        return min(valid) if valid else None

    @property
    def lap_count(self) -> int:
        return len([l for l in self.laps if l.is_valid])


# ============================================================
# LAP — egy kör adatai
# ============================================================

class Lap(Base):
    """
    Egy köridő összes adatával:
      - gps_trace:     [{lat, lon, speed_kmh, ts_ms}, ...]  ~5 Hz
      - sector_times:  [{name, time_ms}, ...]
    """
    __tablename__ = "laps"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    session_id:  Mapped[int]  = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    lap_number:  Mapped[int]  = mapped_column(Integer, nullable=False)
    lap_time_ms: Mapped[int]  = mapped_column(Integer, nullable=False)
    is_valid:    Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Körkezdet / vége UTC timestamp (ms)
    lap_start_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_end_ts:   Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-kör IMU csúcsértékek (firmware v1.3+)
    max_speed_kmh:   Mapped[float | None] = mapped_column(Float, nullable=True)
    max_lean_right:  Mapped[float | None] = mapped_column(Float, nullable=True)
    max_lean_left:   Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_kamm_g:     Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_kamm_angle: Mapped[float | None] = mapped_column(Float, nullable=True)

    # GPS trace — [{lat, lon, speed_kmh, ts_ms}, ...]
    gps_trace_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Szektoridők — [{"name":"S1","time_ms":9800}, ...]
    sector_times_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    session: Mapped["Session"] = relationship(back_populates="laps")

    @property
    def gps_trace(self) -> list:
        return json.loads(self.gps_trace_json)

    @gps_trace.setter
    def gps_trace(self, value: list):
        self.gps_trace_json = json.dumps(value)

    @property
    def sector_times(self) -> list:
        return json.loads(self.sector_times_json)

    @sector_times.setter
    def sector_times(self, value: list):
        self.sector_times_json = json.dumps(value)

    def format_time(self) -> str:
        """'1:01.234' formátum."""
        ms = self.lap_time_ms
        s_total = ms // 1000
        return f"{s_total // 60}:{s_total % 60:02d}.{ms % 1000:03d}"
