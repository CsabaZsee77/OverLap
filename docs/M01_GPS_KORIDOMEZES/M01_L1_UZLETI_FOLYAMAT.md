# L1 – Üzleti Folyamat – GPS & Köridőmérés

**Modul:** M01
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.2.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-28
**Státusz:** ✅ Implementálva

---

## 1. Modul célja

Az M01 modul a **GPS pozíció fogadásától a köridő detektálásáig** terjedő teljes firmware folyamatot valósítja meg a CoreS3-on. Ez a rendszer alapköve: minden más modul (M02 szektorelemzés, M03 kijelző, M04 uplink) az M01 által számított adatokra épül.

A firmware:
1. Fogadja a GPS modul (AT6558) NMEA adatfolyamát UART-on
2. Olvassa a BMI270 IMU gyorsulás- és szögsebességi adatait
3. Kalman szűrővel fúzionálja a két adatforrást → sima, pontos pályavonal
4. Felhasználó által definiált virtuális rajtvonallal detektálja a kör kezdetét/végét
5. Rögzíti a köridőt ezredmásodperc pontossággal

**Üzleti értékek:**
- Nincs szükség fizikai szenzorra a pályán (transponder, induktív hurok)
- A motoros hordja az egységet — önálló, infrastruktúra-független mérés
- ±0.05–0.1 s pontosság 10 Hz GPS + Kalman szűrővel (rekreációs szinten elegendő)
- Rajtvonal helyszíni felvétele GPS-szel (nincs koordináta-beírás szükséges)
- Offline működés: ha nincs WiFi, lokálisan tárol; feltöltés utólag

---

## 2. Szereplők

| Szereplő | Szerepkör |
|----------|-----------|
| Motoros | Eszközt rögzíti a motorra, rajtvonalat vesz fel, kör közben adatot gyűjt |
| CoreS3 | GPS adatot fogad, Kalman szűröz, köridőt számít, kijelzőn megmutatja |
| AT6558 GPS modul | 10 Hz-es NMEA adatfolyam szolgáltatása UART-on |
| BMI270 IMU | Gyorsulás és szögsebességi adat I2C-n |
| Backend szerver | Köridők fogadása WiFi-n (M04 továbbítja) |

---

## 3. Fő folyamat

```
[Boot] → main.py inicializálás
      │
      ▼
GPS inicializálás:
  - UART kapcsolat az AT6558 modullal (Grove UART port)
  - 10 Hz-re konfigurálás: PMTK parancs küldése
  - GGA és RMC mondatok engedélyezése
  - Várakozás első GPS FIX-re (timeout: 60 s)
      │
      ▼
IMU inicializálás:
  - BMI270 I2C kapcsolat (CoreS3 beépített, cím: 0x68)
  - Gyorsulásmérő: ±4g, 200 Hz
  - Giroszkóp: ±500°/s, 200 Hz
      │
      ▼
Rajtvonal betöltése:
  A) config.py-ból: előre mentett koordináták betöltése
  B) Helyszíni felvétel mód:
     - Felhasználó a rajtvonal mellé áll
     - Gomb megnyomás → GPS pozíció 1. vége rögzítve
     - Irány + 6 méter offset → rajtvonal 2. végpontja számítva
     - config.py-ba mentés
      │
      ▼
Fő mérési loop (async, folyamatos):

  ┌─────────────────────────────────────────┐
  │  GPS Task (10 Hz):                      │
  │    NMEA mondat fogadása UART-ról        │
  │    GGA → lat, lon, fix quality, sats   │
  │    RMC → speed, course, timestamp      │
  │    → Kalman frissítés (measurement)    │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  IMU Task (50 Hz):                      │
  │    ax, ay, az, gx, gy, gz olvasása     │
  │    → Kalman frissítés (prediction)     │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  Kalman Output (50 Hz):                 │
  │    filtered_lat, filtered_lon           │
  │    filtered_speed                       │
  │    lean_angle (giroszkóp integrálból)  │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  Köridő Detektálás (minden GPS pontnal) │
  │    P_prev → P_curr vektor               │
  │    Metszi a rajtvonal-szegmenst?        │
  │      IGEN → köridő számítás            │
  │      NEM  → folytatás                  │
  └──────────────┬──────────────────────────┘
                 │
      ▼
Köridő rögzítve:
  - lap_time = t_cross - t_prev_cross (ms)
  - lap_max_speed = kör alatt mért legnagyobb sebesség (km/h)
  - GPS trace mentése a körből (logger.py)
  - best_lap frissítés ha szükséges
  - lap_max_speed_kmh nullázódik → következő kör mérése kezdődik
  - M02 értesítése (szektor reset)
  - M03 értesítése (kijelző frissítés: stopper nulláz, ELOZO + max sebesség)
  - M04 értesítése (uplink queue, Telegram: per-kör max sebesség)
```

---

## 4. Rajtvonal felvétel részletei

```
Két módszer:

A) Automatikus (GPS alapú) — SETUP képernyőn, bal oldal 2 mp nyomva tartás:
   - Felhasználó a rajtvonalnál áll (GPS FIX szükséges)
   - 2 másodperces hosszú érintés → GPS koordináta rögzítve mint L1
   - Mozgásirány alapján merőleges számítva → L2 pont (20 m széles vonal)
   - Azonnali visszajelzés: 1 mp-es teljes zöld képernyő villanás
   - Stopper azonnal elindul a beállítás pillanatától
   - Csak memóriában tárolódik (track.json nem módosul)

B) Fájlból (track.json) — SETUP képernyőn, jobb oldal érintés:
   {
     "name": "Kakucs Ring",
     "track_type": "circuit",
     "finish_line": {
       "lat1": 47.246053, "lon1": 19.377900,
       "lat2": 47.246395, "lon2": 19.378474
     }
   }
```

---

## 5. Köridő detektálás algoritmusa

```
Minden GPS frissítésnél:

Input:
  P1 = (prev_lat, prev_lon)     ← előző GPS pont
  P2 = (curr_lat, curr_lon)     ← aktuális GPS pont
  L1 = (finish_lat1, finish_lon1)  ← rajtvonal 1. vége
  L2 = (finish_lat2, finish_lon2)  ← rajtvonal 2. vége

Algoritmus: 2D szegmens metszés (CCW teszt)

1. Számítsd cross-product előjelét:
   d1 = direction(L1, L2, P1)
   d2 = direction(L1, L2, P2)
   d3 = direction(P1, P2, L1)
   d4 = direction(P1, P2, L2)

2. Metszés feltétele:
   (d1 != d2) AND (d3 != d4)

3. Ha metszés van → interpolált áthaladási idő:
   t = t_P1 + (t_P2 - t_P1) * interpolation_factor
   ahol interpolation_factor = geometriai arány a metszési ponthoz

4. Kördetektálás:
   Ha már volt előző áthaladás ÉS eltelt > MIN_LAP_TIME (pl. 30 s):
     lap_time = t - t_prev_crossing
     t_prev_crossing = t
```

---

## 6. Kalman szűrő összefoglalás

```
Állapotvektor: [lat, lon, v_lat, v_lon]  (4D)

Predikciós lépés (IMU alapján, 50 Hz):
  x_pred = F * x + B * u
  ahol u = (a_north, a_east) IMU gyorsulás (koordináta-rendszerbe transzformálva)

Frissítési lépés (GPS alapján, 10 Hz):
  K = P * H^T * (H * P * H^T + R)^-1
  x = x_pred + K * (z - H * x_pred)
  ahol z = (GPS_lat, GPS_lon) mért pozíció

Zaj paraméterek:
  Q (folyamat zaj): IMU drift alapján hangolva
  R (mérési zaj): GPS CEP ~2 m alapján hangolva
```

---

## 7. Eseményindítók

| Esemény | Következmény |
|---------|-------------|
| Boot | GPS + IMU inicializálás, config betöltés |
| GPS FIX megszerzése | Mérési loop indítása, kijelzőn FIX jelzés |
| GPS FIX elvesztése (>5 s) | Kijelzőn figyelmeztetés, IMU-only mód |
| "SET FINISH LINE" bal 2 mp | GPS koordináta rögzítése, zöld villanás, stopper indul |
| Rajtvonal metszése (érvényes) | Köridő + per-kör max sebesség rögzítés, stopper nulláz |
| Rajtvonal metszése (<30 s után) | Kihagyva (outlap, hibás detektálás) |
| WiFi kapcsolat fel | M04 queue flush |
| Gomb megnyomás | Kijelző mód váltás (M03) |

---

## 8. Végállapotok

| Állapot | Leírás |
|---------|--------|
| `booting` | Inicializálás folyamatban |
| `no_fix` | GPS FIX nincs, mérés nem lehetséges |
| `fix_ok` | GPS FIX megvan, várakozás a rajtvonalra |
| `no_finish_line` | Nincs mentett rajtvonal, felvétel szükséges |
| `ready` | GPS FIX + rajtvonal kész, mérés aktív |
| `in_lap` | Kör folyamatban (rajtvonal már egyszer átszelve) |
| `lap_recorded` | Köridő rögzítve, azonnal visszaáll `in_lap` állapotba |

---

## 9. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M02 Szektorelemzés | **Értesítés** — lap_recorded esemény → szektor reset |
| M03 Kijelző | **Adatszolgáltatás** — filtered_pos, speed, lap_time, best_lap |
| M04 WiFi Uplink | **Adatszolgáltatás** — lap_time, GPS trace queue-ba kerül |
