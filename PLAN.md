# MotoMeter — Fejlesztési Terv

## Rendszer áttekintés

Egy ESP32-alapú motoros telemetria és köridőmérő rendszer, amely GPS-alapú pályakövetést, szektorelemzést, prediktált köridőt és szinkronizált multi-rider vizualizációt biztosít. A rendszer három rétegből áll: hardver/firmware, backend szerver, webes elemző felület.

---

## Hardver komponensek

| Eszköz | Modell | Feladat |
|---|---|---|
| Vezérlő | M5Stack CoreS3 | Fő processzor, kijelző, WiFi |
| GPS | M5Stack GPS Unit (AT6558) | Pozíció, sebesség, idő |
| IMU | CoreS3 beépített BMI270 | Gyorsulás, szögsebességi szög, lean angle |
| Ház | 3D nyomtatott | Kormányra rögzítés, védelem |
| Opcionális | SIM7080G LTE-M modul | Pálya WiFi nélküli feltöltés |

**GPS konfiguráció:** AT6558 alapból 1 Hz → 10 Hz-re konfigurálható NMEA paranccsal (kritikus a pontossághoz).

**Pontossági elvárás:** 10 Hz GPS + Kalman szűrő → ±0.05–0.1 s köridőhiba 100 km/h sebességnél.

---

## 1. FÁZIS — Firmware (CoreS3, MicroPython)

### Célok
- GPS adat fogadása, NMEA parsálás
- Köridő mérése virtuális rajtvonal alapján
- Szektordefiníció és szektoridők
- Prediktált köridő kijelzőn
- WiFi-n keresztüli adatfeltöltés

### Fájlstruktúra

```
firmware/
  main.py           # boot, async task scheduler
  config.py         # rajtvonal koordináták, szektor definíciók, WiFi
  gps.py            # AT6558 NMEA parser (GGA, RMC)
  imu.py            # BMI270 gyorsulás + szögsebességi olvasás
  kalman.py         # 2D Kalman szűrő (GPS + IMU fúzió)
  lap.py            # virtuális vonalmetszés, köridő számítás
  sector.py         # szektor időmérés, best sector tárolás
  delta.py          # prediktált köridő, best lap delta kalkuláció
  display.py        # CoreS3 kijelző kezelés (320x240)
  uplink.py         # WiFi kapcsolat, HTTP POST / MQTT
  logger.py         # lokális flash log (session mentés)
```

### Kijelző layout (320×240)

```
┌─────────────────────────────┐
│  ELŐZŐ KÖR      BEST LAP    │
│   1:02.341       1:01.872   │
├─────────────────────────────┤
│                             │
│   PREDIKTÁLT:  1:01.9       │
│                             │
│   DELTA:     -0.4 s  🟢     │
│                             │
├─────────────────────────────┤
│  GPS: FIX ●  SAT: 9  S2/5  │
└─────────────────────────────┘
```

### Köridőmérés logikája

1. Felhasználó a pálya mellé áll → megjelöli a GPS pozíciót mint rajtvonal egyik vége
2. A másik végpont kézzel megadható (irány + távolság) vagy második GPS felvétel
3. Minden GPS frissítésnél: két egymást követő pont alkotja a mozgásvektort
4. Ha ez a vektor metszi a rajtvonal-szegmenst → kör detektálva, interpolált idő rögzítve

### Virtuális vonalmetszés algoritmus

```
P1(t-1) és P2(t) = két egymást követő GPS pont
L1, L2 = rajtvonal két végpontja

Ha segment_intersect(P1, P2, L1, L2):
    t_cross = interpolált áthaladási idő
    lap_time = t_cross - t_prev_cross
```

### Prediktált köridő

- A pálya N szektorra van osztva
- Minden szektor belépésekor: `prediktált = eltelt_idő + (best_lap_hátralévő_szektorok_összege)`
- Kijelzőn: aktuális prediktált idő + delta a best laphoz képest
- Frissítési sűrűség: minden szektor átlépésnél (minél több szektor, annál sűrűbb)

### Kalman szűrő (2D pozíció + sebesség)

```
Állapotvektor: [x, y, vx, vy]
Mérés: GPS (x, y) — 10 Hz, ~2 m hiba
Input: IMU gyorsulás (ax, ay) — 200 Hz
→ sima, 50 Hz-es pályavonal
→ pontosabb vonalmetszés-detektálás
```

### WiFi uplink stratégia

- **Realtime mód:** telefon hotspot → köridők azonnal feltöltve HTTP POST-tal
- **Offline mód:** lokális flash mentés → WiFi elérésekor batch feltöltés
- **Pálya WiFi mód (jövő):** fix AP a rajtvonalnál, eszköz minden kör után feltölt

---

## 2. FÁZIS — Backend szerver (Python, FastAPI)

### Célok
- Session és köridő adatok fogadása és tárolása
- Pálya geometria kezelése (középvonal, szektorok)
- Leaderboard számítás
- Replay adat előkészítése
- Theoretical best lap kalkuláció

### Adatstruktúra

```
Track
  id, name, country
  centerline: [GeoJSON LineString]  ← műholdképen rajzolt középvonal
  sectors: [{start_pct, end_pct, name}]  ← s-koordináta alapú
  finish_line: {lat1, lon1, lat2, lon2}

Session
  id, user_id, track_id, date, conditions

Lap
  id, session_id, lap_number
  lap_time_ms
  gps_trace: [{lat, lon, speed, ts}]  ← 10 Hz-es pontok
  sector_times: [{sector_id, time_ms}]

User
  id, name, avatar, bio, public_profile
```

### API végpontok

```
POST /sessions              → új session indítás
POST /sessions/{id}/laps    → köridő + GPS trace feltöltés
GET  /tracks/{id}/leaderboard?period=week
GET  /sessions/{id}/analysis
GET  /replay/{session_ids}  → szinkronizált replay adat
```

### Theoretical best lap

```python
theoretical_best = sum(min(lap.sector_times[s] for lap in session.laps)
                       for s in range(num_sectors))
```

### Stack

- **FastAPI** — REST + WebSocket
- **PostgreSQL + PostGIS** — térbeli lekérdezések, GPS trace tárolás
- **Redis** — realtime lap push (pub/sub)
- **TimescaleDB** (opcionális) — idősor optimalizálás

---

## 3. FÁZIS — Track Analytics (pálya geometria)

### Pálya középvonal feldolgozás

1. Felhasználó műholdképen megrajzolja a pálya középvonalát (polyline)
2. A polyline → s-koordináta rendszer (0.0 = rajtvonal, 1.0 = egy teljes kör)
3. Görbületi profil számítás: minden pontban a szomszédos pontokra illesztett kör sugara
4. Kanyar detektálás görbület-küszöb alapján

### Linearizált pályanézet (track unwrapping)

```
Valódi pályatérkép (2D):         Linearizált nézet (1D):

    ╭─────╮                      ──────────────────────────
   ╱       ╲                     S1   S2    S3   S4   S5
  │    ●    │          →         ↑    ↑     ↑    ↑    ↑
   ╲       ╱                     kanyar görbületi profil alatta
    ╰─────╯
```

### Görbületi profil megjelenítés

- Vízszintes tengely: s-koordináta (pálya hossza mentén)
- Függőleges tengely: görbület (1/R, előjeles: bal/jobb kanyar)
- Pozitív = balra kanyar, negatív = jobbra kanyar
- A nullátmenet = egyenes szakasz

---

## 4. FÁZIS — Szinkronizált Multi-rider Replay

### Vezérkör szinkronizáció

```
Vezérkör: A motoros adott körének s(t) pályahaladása
Többi kör: ugyanarra az s(t) görbére szinkronizálva

Megjelenítés: pályatérképen minden motoros egy pont
             → látható ki hol előz, hol nyílik a gap
```

### Timeline editor mód

- Két vagy több kör egymás mellé rakva (mint videószerkesztőben a trackok)
- Drag & drop eltolás: tetszőleges szinkronizációs pont (start, szektor, apex)
- Hasznos: ha két kör nagyon eltér egymástól, a releváns szakasznál lehet szinkronizálni

### Statikus overlay nézet

- Linearizált pályán minden motoros/kör haladása egy görbe
- X tengely: idő, Y tengely: s-koordináta (pályán megtett arány)
- Meredekebb görbe = gyorsabb haladás az adott szakaszon
- Görbék keresztezése = előzés

### Realtime verzió

- Egy kör késleltetéssel: amíg az első motoros körbeér, az utolsó elinduló szinkronizálódik
- Padokon ülő nézők látják a „virtuális versenyt" a monitoron

---

## 5. FÁZIS — Webes felület

### Technológia (döntés later)
- **React + Vite + TypeScript** → production-ready, komplex dashboard
- **Plotly Dash** → ha Python stack prioritás

### Oldalak
1. **Dashboard** — utolsó sessionök, personal best, quick insights
2. **Track Explorer** — pályarajz, szektor definíció, görbületi profil
3. **Session Analysis** — lap breakdown, delta graph, speed vs. position
4. **Virtual Replay** — szinkronizált vizualizáció, timeline editor
5. **Leaderboard** — napi/heti/havi/event szűrők, theoretical best
6. **Device** — CoreS3 státusz, GPS fix, sync állapot

---

## 6. FÁZIS — Üzleti modell (opcionális)

### Hardver
- CoreS3 + GPS + ház: ~15–20 000 Ft gyártási költség
- Bérlés: napi díj a pályán (recepción)
- Vétel: saját eszköz

### Platform
- Alap: ingyenes (saját adatok megtekintése)
- Előfizetés (minimális): feltöltési korlát nélkül, publikus profil
- Verseny nevezési díj (pl. 2 000 Ft): rangsorolás, díjazás

### Virtuális bajnokság logika
- Időszakos ranglisták (havi, esemény-alapú)
- Nevezés → profil nyilvánossá tehető (kép, bemutatkozás)
- Top 3 díjazás
- Nem szervezett verseny: „MotoMeter mért rangsor" — független a pálya szervezésétől

---

## Fejlesztési sorrend (MVP)

```
[1] Firmware alap: GPS parse + köridőmérés + kijelző
[2] Rajtvonal felvétel (helyszíni GPS jelölés)
[3] Szektordefiníció + prediktált köridő
[4] WiFi uplink → egyszerű backend (FastAPI + SQLite)
[5] Kalman szűrő (GPS+IMU fúzió)
[6] Pálya geometria editor (web, műholdkép)
[7] Session analysis dashboard
[8] Szinkronizált replay
[9] Leaderboard + virtuális bajnokság
[10] Üzleti funkciók (bérlés, előfizetés, nevezés)
```

---

## Nyitott kérdések (döntés szükséges)

1. **Firmware nyelv:** MicroPython (gyorsabb fejlesztés) vs. C++/Arduino (jobb performance)?
2. **GPS Grove port:** Port A (I2C) vagy Port C (UART2) a CoreS3-on?
3. **Van SD kártya modul?** (offline log tároláshoz)
4. **WiFi stratégia:** mindig telefon hotspot, vagy pálya fix WiFi is tervezett?
5. **Frontend stack:** React vagy Dash?
