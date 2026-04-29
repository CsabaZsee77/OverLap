# core/track_math.py - Pálya geometriai számítások
# MotoMeter backend
#
# s-koordináta: normalizált pályahaladás (0.0 = rajtvonal, 1.0 = egy teljes kör)
# Minden vizualizációs grafikon erre az egységre épül.

import math
from typing import Optional


# ============================================================
# Alap geodéziai számítások
# ============================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Két GPS pont közötti távolság méterben (Haversine formula).
    Kis távolságokon (<50 km) elegendően pontos.
    """
    R = 6_371_000.0  # Föld sugara méterben
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================
# Centerline → s-koordináta leképzés
# ============================================================

def build_s_index(centerline: list[dict]) -> list[dict]:
    """
    Centerline GPS pontokból kumulált ívhossz-index építése.

    Args:
        centerline: [{"lat": x, "lon": x}, ...]

    Returns:
        [{"lat": x, "lon": x, "dist_m": d, "s": 0.0–1.0}, ...]
        ahol s = kumulált_távolság / teljes_pályahossz
    """
    if len(centerline) < 2:
        return []

    # Kumulált távolságok
    cumulative = [0.0]
    for i in range(1, len(centerline)):
        d = haversine_m(
            centerline[i - 1]["lat"], centerline[i - 1]["lon"],
            centerline[i]["lat"],     centerline[i]["lon"]
        )
        cumulative.append(cumulative[-1] + d)

    total = cumulative[-1]
    if total == 0:
        return []

    return [
        {
            "lat":    centerline[i]["lat"],
            "lon":    centerline[i]["lon"],
            "dist_m": cumulative[i],
            "s":      cumulative[i] / total,
        }
        for i in range(len(centerline))
    ]


def gps_to_s(lat: float, lon: float, s_index: list[dict]) -> Optional[float]:
    """
    GPS pozíció → s-koordináta (0.0–1.0) a legközelebbi centerline pont alapján.

    Args:
        lat, lon  : GPS pozíció
        s_index   : build_s_index() kimenetele

    Returns:
        s érték 0.0–1.0, vagy None ha s_index üres
    """
    if not s_index:
        return None

    best_dist = float("inf")
    best_s    = 0.0

    for pt in s_index:
        d = haversine_m(lat, lon, pt["lat"], pt["lon"])
        if d < best_dist:
            best_dist = d
            best_s    = pt["s"]

    return best_s


def gps_trace_to_s_speed(
    gps_trace: list[dict],
    s_index:   list[dict],
) -> list[dict]:
    """
    GPS trace → s-koordináta + sebesség párok vizualizációhoz.

    Args:
        gps_trace : [{"lat", "lon", "speed_kmh", "ts_ms"}, ...]
        s_index   : build_s_index() kimenetele

    Returns:
        [{"s": 0.0–1.0, "speed_kmh": float}, ...]  növekvő s szerint rendezve
    """
    points = []
    for pt in gps_trace:
        s = gps_to_s(pt["lat"], pt["lon"], s_index)
        if s is not None:
            points.append({"s": s, "speed_kmh": pt.get("speed_kmh", 0.0)})

    return sorted(points, key=lambda p: p["s"])


# ============================================================
# Pályahossz számítás
# ============================================================

def centerline_length_m(centerline: list[dict]) -> float:
    """Centerline teljes hossza méterben."""
    total = 0.0
    for i in range(1, len(centerline)):
        total += haversine_m(
            centerline[i - 1]["lat"], centerline[i - 1]["lon"],
            centerline[i]["lat"],     centerline[i]["lon"]
        )
    return total


# ============================================================
# Görbületi profil
# ============================================================

def curvature_profile(centerline: list[dict]) -> list[dict]:
    """
    Görbületi profil számítása a centerline mentén.
    Eredmény: [{"s": float, "curvature": float}, ...]
    Pozitív = bal kanyar, negatív = jobb kanyar.

    Algoritmus: három szomszédos pont által bezárt szög / ívhossz.
    """
    s_idx = build_s_index(centerline)
    if len(s_idx) < 3:
        return []

    profile = []
    for i in range(1, len(s_idx) - 1):
        A = s_idx[i - 1]
        B = s_idx[i]
        C = s_idx[i + 1]

        # Vektorok (méter, kis területen lineáris közelítés)
        scale_lat = 111_320.0
        scale_lon = 111_320.0 * math.cos(math.radians(B["lat"]))

        abx = (B["lat"] - A["lat"]) * scale_lat
        aby = (B["lon"] - A["lon"]) * scale_lon
        bcx = (C["lat"] - B["lat"]) * scale_lat
        bcy = (C["lon"] - B["lon"]) * scale_lon

        ab_len = math.sqrt(abx**2 + aby**2)
        bc_len = math.sqrt(bcx**2 + bcy**2)
        ds = (ab_len + bc_len) / 2.0

        if ab_len == 0 or bc_len == 0 or ds == 0:
            continue

        # Keresztszorzat (előjel = bal/jobb)
        cross = abx * bcy - aby * bcx

        # Szög (ívmérték)
        dot   = abx * bcx + aby * bcy
        cos_a = max(-1.0, min(1.0, dot / (ab_len * bc_len)))
        angle = math.acos(cos_a)

        curvature = (angle / ds) * (1 if cross > 0 else -1)

        profile.append({"s": B["s"], "curvature": round(curvature, 6)})

    return profile
