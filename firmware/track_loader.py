# track_loader.py - Pálya / szektor konfiguráció betöltése JSON fájlból
# MotoMeter v0.1 - M5Stack CoreS3
#
# Két üzemmód:
#   "circuit" — zárt körpálya (start = finish vonal), csak finish_line szükséges
#   "stage"   — útszakasz (hillclimb, gyorsulás), start_line + finish_line kell
#
# Formátum: minden vonalhoz két explicit GPS pont kell.
# Ezeket Google Maps-ből szeded: jobb kattintás → koordináta másolás.
# A két pont az út két oldalán legyen, keresztezve az útpályát.
#
# Körpálya példa:
#   {
#     "name": "Kakucs Ring",
#     "track_type": "circuit",
#     "finish_line": {"lat1": 47.xxx, "lon1": 19.xxx, "lat2": 47.yyy, "lon2": 19.yyy},
#     "sectors": [{"name":"S1", "lat1":..., ...}]
#   }
#
# Útszakasz példa:
#   {
#     "name": "Zsámbék-Etyek",
#     "track_type": "stage",
#     "start_line":  {"lat1": ..., "lon1": ..., "lat2": ..., "lon2": ...},
#     "finish_line": {"lat1": ..., "lon1": ..., "lat2": ..., "lon2": ...},
#     "sectors": [...]
#   }
#
# Fájl elhelyezése (prioritás sorrendben):
#   1. /sd/track.json    ← SD kártyáról
#   2. /flash/track.json ← Flash fallback

import json
import math

_SEARCH_PATHS = ['/sd/track.json', '/flash/track.json']


class TrackLine:
    """Egy virtuális vonalszegmens két GPS végponttal."""
    __slots__ = ('name', 'lat1', 'lon1', 'lat2', 'lon2')

    def __init__(self, name, lat1, lon1, lat2, lon2):
        self.name = name
        self.lat1 = lat1
        self.lon1 = lon1
        self.lat2 = lat2
        self.lon2 = lon2

    def __repr__(self):
        return "TrackLine({}, ({:.6f},{:.6f})–({:.6f},{:.6f}))".format(
            self.name, self.lat1, self.lon1, self.lat2, self.lon2)


class TrackConfig:
    """Betöltött pályakonfiguráció."""

    def __init__(self):
        self.name        = "Ismeretlen pálya"
        self.track_type  = "circuit"   # "circuit" | "stage"
        self.finish_line = None        # TrackLine
        self.start_line  = None        # TrackLine | None — csak stage módban
        self.sectors     = []          # [TrackLine, ...]
        self.loaded_from = None

    @property
    def has_finish_line(self):
        return self.finish_line is not None

    @property
    def has_start_line(self):
        return self.start_line is not None

    @property
    def is_circuit(self):
        return self.track_type == "circuit"

    @property
    def is_stage(self):
        return self.track_type == "stage"

    @property
    def is_ready(self):
        """True ha a módhoz szükséges vonalak mind definiáltak."""
        if self.is_circuit:
            return self.has_finish_line
        else:  # stage
            return self.has_finish_line and self.has_start_line

    @property
    def sector_count(self):
        return len(self.sectors)

    def summary(self):
        if self.is_circuit:
            return "{} [circuit] | cél:{} | szektorok:{}".format(
                self.name,
                "✓" if self.has_finish_line else "✗",
                self.sector_count
            )
        else:
            return "{} [stage] | start:{} | cél:{} | szektorok:{}".format(
                self.name,
                "✓" if self.has_start_line else "✗",
                "✓" if self.has_finish_line else "✗",
                self.sector_count
            )


def load_track():
    """
    Pálya konfiguráció betöltése JSON fájlból.
    Returns: TrackConfig ha sikerült, None ha nem található fájl.
    """
    for path in _SEARCH_PATHS:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            tc = _parse(data, path)
            print("TrackLoader: betöltve →", tc.summary())
            if not tc.is_ready:
                print("TrackLoader: FIGYELMEZTETÉS — hiányos konfiguráció!")
            return tc
        except OSError:
            continue
        except Exception as e:
            print("TrackLoader: hiba ({}) →".format(path), e)
            continue

    print("TrackLoader: nincs track.json — töltsd fel SD-re vagy /flash-re")
    return None


def save_track(tc):
    """TrackConfig mentése /flash/track.json-ba."""
    try:
        data = _serialize(tc)
        with open('/flash/track.json', 'w') as f:
            json.dump(data, f)
        print("TrackLoader: elmentve → /flash/track.json")
        return True
    except Exception as e:
        print("TrackLoader: mentési hiba →", e)
        return False


# ------------------------------------------------------------------
# Parse
# ------------------------------------------------------------------

def _parse(data, source_path):
    tc = TrackConfig()
    tc.name        = data.get('name', 'Névtelen pálya')
    tc.loaded_from = source_path
    tc.track_type  = data.get('track_type', 'circuit')

    fl_data = data.get('finish_line')
    if fl_data:
        tc.finish_line = _parse_line('FINISH', fl_data)

    sl_data = data.get('start_line')
    if sl_data:
        tc.start_line = _parse_line('START', sl_data)

    for i, s in enumerate(data.get('sectors', [])):
        name = s.get('name', 'S{}'.format(i + 1))
        line = _parse_line(name, s)
        if line:
            tc.sectors.append(line)

    return tc


def _parse_line(name, d):
    """
    Vonal parse: csak explicit két végpont fogadott el.
    lat1/lon1 = az út egyik oldala
    lat2/lon2 = az út másik oldala
    """
    if all(k in d for k in ('lat1', 'lon1', 'lat2', 'lon2')):
        return TrackLine(name, d['lat1'], d['lon1'], d['lat2'], d['lon2'])
    print("TrackLoader: hiányzó lat1/lon1/lat2/lon2 a '{}' vonalnál".format(name))
    return None


# ------------------------------------------------------------------
# Serialize
# ------------------------------------------------------------------

def _serialize(tc):
    data = {
        'name':       tc.name,
        'track_type': tc.track_type,
    }

    if tc.finish_line:
        fl = tc.finish_line
        data['finish_line'] = {
            'lat1': fl.lat1, 'lon1': fl.lon1,
            'lat2': fl.lat2, 'lon2': fl.lon2
        }

    if tc.start_line:
        sl = tc.start_line
        data['start_line'] = {
            'lat1': sl.lat1, 'lon1': sl.lon1,
            'lat2': sl.lat2, 'lon2': sl.lon2
        }

    sectors = []
    for s in tc.sectors:
        sectors.append({
            'name': s.name,
            'lat1': s.lat1, 'lon1': s.lon1,
            'lat2': s.lat2, 'lon2': s.lon2
        })
    data['sectors'] = sectors
    return data


# ------------------------------------------------------------------
# SET FINISH LINE — GPS alapú helyszíni felvétel
# A haladási irányra valóban merőleges, mert a course_deg-et
# a GPS adja (RMC mondatból), tehát az aktuális menetirány ismert.
# ------------------------------------------------------------------

def make_track_from_gps(name, center_lat, center_lon, course_deg,
                        width_m=8.0, track_type='circuit',
                        start_lat=None, start_lon=None, start_course_deg=None):
    """
    Rajtvonal létrehozása GPS pozícióból és haladási irányból.
    A haladási irány a GPS RMC mondatból jön — ez valóban az aktuális
    menetirány, nem becsült. Kanyarban is pontos, ha motorozás közben
    rögzítjük (nem állóban).

    Circuit mód: csak a célvonal közepe + irány kell.
    Stage mód:   a célvonal adatai + opcionálisan a startvonal adatai.
                 Ha a startvonal nincs megadva, a célvonal lesz a start is.

    Args:
        name            : pálya neve
        center_lat/lon  : célvonal közepe
        course_deg      : haladási irány a célvonalnál (RMC, fok, 0=É)
        width_m         : vonal szélessége (ajánlott 8–12 m)
        track_type      : 'circuit' | 'stage'
        start_lat/lon   : startvonal közepe (stage módban, opcionális)
        start_course_deg: haladási irány a startvonalon (stage módban)

    Returns:
        TrackConfig
    """
    tc = TrackConfig()
    tc.name       = name
    tc.track_type = track_type

    tc.finish_line = _make_line_from_gps('FINISH', center_lat, center_lon,
                                         course_deg, width_m)

    if track_type == 'stage' and start_lat is not None:
        sc = start_course_deg if start_course_deg is not None else course_deg
        tc.start_line = _make_line_from_gps('START', start_lat, start_lon, sc, width_m)

    return tc


def _make_line_from_gps(name, center_lat, center_lon, course_deg, width_m):
    perp_rad = math.radians(course_deg + 90.0)
    half_m   = width_m / 2.0
    dlat = (half_m / 111320.0) * math.cos(perp_rad)
    dlon = (half_m / (111320.0 * math.cos(math.radians(center_lat)))) * math.sin(perp_rad)
    return TrackLine(
        name,
        center_lat + dlat, center_lon + dlon,
        center_lat - dlat, center_lon - dlon
    )
