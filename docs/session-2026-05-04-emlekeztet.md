# OverLap fejlesztési session összefoglaló
**Dátum:** 2026-05-04  
**Branch:** main

---

## Elvégzett módosítások

### 1. Verzió: v1.1 → v1.2
**Fájl:** `firmware/display.py:100`  
A boot képernyőn megjelenő verziószám frissítve.

---

### 2. Rajtvonal-detektálás vizsgálata és javítások

#### A probléma
A rajtvonal GPS-sel való felvétele után több áthaladás után sem érzékelte az átlépést.

#### Hogyan működik az algoritmus

A `firmware/lap.py`-ban a `_segments_intersect` (CCW teszt) két feltételt ellenőriz egyszerre:

1. **d1, d2** – az előző és az aktuális GPS pont a rajtvonal ellentétes oldalán van-e
2. **d3, d4** – a rajtvonal két végpontja (L1, L2) a mozgási szegmens ellentétes oldalán van-e

```
Előző GPS pont (P1) ──────────────► Aktuális GPS pont (P2)
                         │
               ──────────┼──────────   ← 30m-es rajtvonal (L1 ←→ L2)
                         │
                   ← DETEKTÁLÁS (ha a szegmens metszi a vonalat)
```

A vonal nem végtelen egyenes, hanem **véges szegmens** – csak akkor tüzel, ha a tényleges GPS nyomvonal (P1→P2) ezen belül metszi.

#### Időmérés pontossága
- GPS: **10 Hz** (100ms között pozíciók) – NEM 5 Hz (az 5 Hz a kijelzőé)
- Az átlépési időt **interpolálja** a kód (`_interpolate_cross_time`):
  - arány = P1 távolsága / (P1 + P2 távolsága) a vonaltól
  - elméletileg ms-os felbontás lehetséges
- **Valódi korlát:** GPS pozíciós pontatlanság (±3–5 m)
  - 100 km/h-nál: ±180 ms időhiba
  - Professzionális transponder: ±1–5 ms (IR/RF technológia)
- A Kalman-szűrő lag **kör-kör összehasonlításnál kiesik** (relatív pontosság jó)

---

### 3. Rajtvonal szélessége: 20 m → 30 m
**Fájl:** `firmware/main.py:218`  
GPS-es vonalrögzítésnél (`set_finish_line_from_gps`) a generált vonal szélessége növelve, hogy GPS eltolódás esetén is biztosan érzékelje az átlépést.

---

### 4. Közbülső kísérlet és visszaállítás (tanulság!)

**Megpróbált fix:** A `_segments_intersect` helyett `_sign_changed` – csak az előjelváltást figyeli (d1, d2), nem a szegmens határait (d3, d4).

**Probléma:** A 30 m-es rajtvonal **végtelen meghosszabbítását** figyelte. Ha a pálya kanyarodik és a mozgás visszametszi ezt a képzeletbeli egyenest, **hamis detektálás** keletkezik ~100 m-rel a valódi vonaltól.

**Konklúzió:** Vissza kell állni a `_segments_intersect`-re – ez pontosan azt csinálja, amit kell: csak a tényleges GPS nyomvonal (P1→P2 szegmens) és a véges rajtvonal szegmens metszését figyeli.

---

### 5. MIN_OUTLAP_MS guard (5 s) — `firmware/lap.py`

Az első rajtvonal-átlépésnél (STATE_WAITING → STATE_IN_LAP) új feltétel:
```python
MIN_OUTLAP_MS = 5_000
since_set = ticks_diff(t_cross, self._line_set_ms)
if since_set < MIN_OUTLAP_MS:
    return None  # elutasítva
```
Megelőzi, hogy GPS-kiesés utáni késett első detektálás rövid "hamis" Lap #1-et adjon.

---

### 6. IMU adatok logolása — `firmware/main.py` + `firmware/logger.py`

Per-kör csúcsok:
- `lap_peak_lean_right`, `lap_peak_lean_left` — max dőlésszög körenként (fokban)
- `lap_peak_kamm_g` — max kombinált G-erő (Kamm kör sugara)
- `lap_peak_kamm_angle` — irányszög a max Kamm pillanatában (fok, 0=gyorsítás, 90=bal, 180=fékezés, 270=jobb)

GPS trace gazdagítás: minden pont tartalmaz IMU-pillanatképet:
```python
{
  'lat': ..., 'lon': ..., 'speed_kmh': ..., 'ts_ms': ...,
  'lean_deg': ..., 'lat_g': ..., 'lon_g': ..., 'kamm_angle': ...
}
```

---

### 7. OverLAP branding — `firmware/telegram.py`

Az összes Telegram üzenetben „MotoMeter" → „OverLAP".
Kör-üzenetbe bekerültek:
- Max dőlés: Bal / Jobb (fok)
- Max Kamm G-erő (szektornévvel: Gyorsítás / Bal kanyar / Fékezés / Jobb kanyar stb.)

---

### 8. IMU kalibráció cím — `firmware/display.py`

`"IMU KALIBRÁCIÓ"` → `"IMU KALIBRACIO"` (ékezetek nélkül, MicroPython font-korlát miatt).

---

## Jelenlegi állapot (main branch, v1.2)

| Komponens | Állapot |
|---|---|
| `firmware/display.py` | v1.2 verzió kiírás, IMU KALIBRACIO felirat |
| `firmware/lap.py` | CCW teszt (véges szegmens), MIN_OUTLAP_MS=5s guard |
| `firmware/main.py` | 30 m-es GPS rajtvonal, per-kör IMU csúcsok, trace gazdagítás |
| `firmware/telegram.py` | OverLAP branding, lean + Kamm adatok üzenetben |
| `firmware/logger.py` | lean/Kamm mezők lapban, IMU-mezős GPS trace |

---

## Nyitott kérdések / jövőbeli fejlesztési lehetőségek

- **GPS jitter / kiesés robusztusság:** Ha GPS kiesés éppen az átlépés pillanatában, az interpolált nyomvonal esetleg nem metszi a vonalat. Lehetséges megoldás: közelség alapú fallback, de csak a vonalon belüli zónára korlátozva.
- **Kalman szűrő hangolás:** Q érték növelése (`gps.py:57`, jelenleg `Q=0.1`) → gyorsabb reagálás, több zaj. Érdemes tesztelni `Q=0.5`-tel.
- **Időmérés pontosság javítása:** IMU + GPS fúzió (dead reckoning) magasabb frekvenciájú pozícióbecsléshez – nagyobb fejlesztés.
- **Log fájl böngésző képernyő:** MODE_FILES — session fájlok listázása, Telegram-ra küldés mellékletként.
- **SD kártya:** Ha csatlakoztatva van, `/sd/overlap_logs/` elsődleges; flashre csak fallback.
