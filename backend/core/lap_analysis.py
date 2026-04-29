# core/lap_analysis.py - Session és kör analitikai számítások
# MotoMeter backend

import math
from typing import Optional
from core.track_math import gps_trace_to_s_speed, build_s_index, gps_to_s


# ============================================================
# Theoretical Best Lap
# ============================================================

def theoretical_best_ms(laps: list) -> Optional[int]:
    """
    Elméleti legjobb köridő: minden szektorban a legjobb idő összege.

    Args:
        laps: Lap ORM objektumok listája (session.laps)

    Returns:
        int ms, vagy None ha nincs elég szektor adat
    """
    if not laps:
        return None

    # Szektornév → legjobb idő ms
    sector_bests: dict[str, int] = {}

    for lap in laps:
        if not lap.is_valid:
            continue
        for st in lap.sector_times:
            name = st["name"]
            t    = st["time_ms"]
            if name not in sector_bests or t < sector_bests[name]:
                sector_bests[name] = t

    if not sector_bests:
        return None

    return sum(sector_bests.values())


def sector_bests_detail(laps: list) -> list[dict]:
    """
    Szektoronkénti legjobb idők, melyik körben születtek.

    Returns:
        [{"name": "S1", "time_ms": 9800, "lap_number": 3}, ...]
    """
    best: dict[str, dict] = {}

    for lap in laps:
        if not lap.is_valid:
            continue
        for st in lap.sector_times:
            name = st["name"]
            t    = st["time_ms"]
            if name not in best or t < best[name]["time_ms"]:
                best[name] = {"name": name, "time_ms": t, "lap_number": lap.lap_number}

    return sorted(best.values(), key=lambda x: x["name"])


# ============================================================
# Consistency Score
# ============================================================

def consistency_score(laps: list) -> Optional[float]:
    """
    Konzisztencia pontszám (0–100).
    100 = minden kör azonos idő, 0 = szórás > átlag.

    Számítás: 100 * (1 - std_dev / mean)
    """
    times = [l.lap_time_ms for l in laps if l.is_valid]
    if len(times) < 2:
        return None

    mean = sum(times) / len(times)
    if mean == 0:
        return None

    variance = sum((t - mean) ** 2 for t in times) / len(times)
    std_dev  = math.sqrt(variance)

    score = max(0.0, 100.0 * (1.0 - std_dev / mean))
    return round(score, 1)


# ============================================================
# Delta grafikon (két kör összehasonlítása)
# ============================================================

def delta_curve(
    lap_a_trace: list[dict],
    lap_b_trace: list[dict],
    s_index:     list[dict],
    resolution:  int = 50,
) -> list[dict]:
    """
    Két kör delta görbéje s-koordináta mentén.
    Pozitív delta = lap_b lassabb mint lap_a.

    Args:
        lap_a_trace: referencia kör GPS trace [{lat,lon,speed_kmh,ts_ms}]
        lap_b_trace: összehasonlítandó kör GPS trace
        s_index:     pálya s-index (build_s_index())
        resolution:  hány pontba mintavételezzük a görbét

    Returns:
        [{"s": float, "delta_ms": int}, ...]
    """
    if not s_index:
        return []

    def trace_to_s_time(trace: list[dict]) -> list[tuple[float, int]]:
        """GPS trace → [(s, ts_ms), ...] növekvő s szerint."""
        pts = []
        for pt in trace:
            s = gps_to_s(pt["lat"], pt["lon"], s_index)
            if s is not None:
                pts.append((s, pt["ts_ms"]))
        pts.sort(key=lambda x: x[0])
        return pts

    pts_a = trace_to_s_time(lap_a_trace)
    pts_b = trace_to_s_time(lap_b_trace)

    if len(pts_a) < 2 or len(pts_b) < 2:
        return []

    def interp_time(pts: list[tuple], s_target: float) -> Optional[float]:
        """Lineáris interpoláció: adott s-nél mennyi ms telt el."""
        for i in range(1, len(pts)):
            s0, t0 = pts[i - 1]
            s1, t1 = pts[i]
            if s0 <= s_target <= s1:
                if s1 == s0:
                    return float(t0)
                ratio = (s_target - s0) / (s1 - s0)
                return t0 + ratio * (t1 - t0)
        return None

    # Normalizálás: nullázzuk az első ponthoz képest
    t0_a = pts_a[0][1]
    t0_b = pts_b[0][1]

    result = []
    for i in range(resolution + 1):
        s = i / resolution
        ta = interp_time(pts_a, s)
        tb = interp_time(pts_b, s)
        if ta is not None and tb is not None:
            delta = int((tb - t0_b) - (ta - t0_a))
            result.append({"s": round(s, 3), "delta_ms": delta})

    return result


# ============================================================
# Lap summary a session analitikához
# ============================================================

def lap_analysis_rows(laps: list) -> list[dict]:
    """
    Minden körre: lap_time, delta vs best, szektor idők.

    Returns:
        [{"lap_number", "lap_time_ms", "is_best", "delta_ms",
          "sector_times": [{"name","time_ms"}]}, ...]
    """
    valid = [l for l in laps if l.is_valid]
    if not valid:
        return []

    best_ms = min(l.lap_time_ms for l in valid)

    rows = []
    for lap in laps:
        rows.append({
            "lap_number":   lap.lap_number,
            "lap_time_ms":  lap.lap_time_ms,
            "is_best":      lap.lap_time_ms == best_ms and lap.is_valid,
            "delta_ms":     lap.lap_time_ms - best_ms if lap.is_valid else 0,
            "sector_times": lap.sector_times,
        })
    return rows
