# L1 – Üzleti Folyamat – Kijelző & Felhasználói Visszajelzés

**Modul:** M03
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.4.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-05-03
**Státusz:** ✅ Implementálva

---

## 1. Modul célja

Az M03 modul kezeli a CoreS3 beépített **2" IPS kijelzőjét** (320×240 px). A motoros a kijelzőn látja a legfontosabb adatokat kör közben — sisakrostélyon át, sisak nélkül egyaránt.

**Üzleti értékek:**
- Futó stopper: mindig látható, mozgó szám → mérés aktív jelzése sisakból is
- Delta vizualizáció: zöld = javulás, piros = romlás
- GPS státusz: mindig látható (fix elvesztéskor azonnali jelzés)
- Tartóban/sisakban is olvasható: nagy, kontrasztos, mozgó számok
- Zöld képernyővillans (1 mp): rajtvonal beállítás visszajelzése sisakból látható

---

## 2. Kijelző layout — MODE_MAIN (320×240)

```
┌──────────────────────────────────────────┐  y=0
│ ●GPS 9sat    WiFi●   85%          MAIN  │  y=0-16  státuszsor (size 1)
├──────────────────────────────────────────┤  y=16   elválasztó
│ STOPPER                                  │  y=20   felirat (size 1, szürke)
│                                          │
│            0:42.17                       │  y=30   CYAN nagy szám (size 5)
│                                          │         ha nincs mérés: sötétszürke --:--.--
├──────────────────────────────────────────┤  y=105  elválasztó
│ BEST              ELOZO                  │  y=109  feliratok (size 1, szürke)
│ 1:01.87           1:02.35               │  y=119  értékek (size 2: sárga/fehér)
│                   127 km/h              │  y=138  kör max sebessége (size 1, narancs)
│ DELTA +0.35s      PRED  1:01.50         │  y=159  (size 2)
│                         1:01.50         │  y=175  PRED érték (ha külön sor kell)
├──────────────────────────────────────────┤  y=192  elválasztó
│ SESSION MAX                              │  y=196  felirat (size 1, szürke)
│ 127 km/h                                │  y=206  session max (size 2, narancs)
└──────────────────────────────────────────┘  y=240
```

**Fontos:** A STOPPER (futó kör ideje) az elsődleges nagy adat:
- Aktív méréskor: **CYAN** szín, folyamatosan pörög (200 ms / 5 Hz)
- Nincs mérés (rajtvonal nincs beállítva): sötétszürke `--:--.--`
- Rajtvonal átlépéskor: nullázódik és újraindul → vizuálisan egyértelmű visszajelzés

---

## 3. Képernyő módok

Navigáció: rövid érintés (bármely ponton, nem SETUP módban) → következő mód körkörösen.

```
MAIN (0) → LEAN (4) → KAMM (6) → SLIP (7) → CALIB (5) → STATS (2) → DIAG (3) → SETUP (1) → MAIN
```

### MODE_MAIN (0) — köridőmérés

Stopper | BEST | előző kör + max sebesség | DELTA | prediktív körido | Session MAX.
Részletes layout: lásd §2.

### MODE_LEAN / MODE_IMU (4) — dőlésszög műhorizont

Kör alakú műhorizont (r=88px, 320×240 közepén):
- Scan-line kitöltés: ég (kék) / talaj (barna) az aktuális dőlésszög alapján
- Fehér körkerület + fokjelzők (±15°, ±30°, ±45°, ±60°)
- Narancssárga peak-hold nyilak a körön kívül (bal/jobb maximum dőlés)
- Fejléc: dőlésszög | GPS sebesség km/h | lateral G
- Alul: BAL MAX és JOBB MAX peak értékek fokokban

### MODE_KAMM (6) — Kamm kör dinamikus

Lat G (vízszintes) vs Lon G (függőleges) trail grafikon:
- Mozgó trail: fehér (legújabb) → narancs → sötét → szürke (20 minta)
- **Piros kör** = első kerék tapadási határ (fékezésnél nő — súlyáthelyezés előre)
- **Cián kör** = hátsó kerék tapadási határ (gyorsításnál nő — súlyáthelyezés hátra)
- Dinamikus sugár: `ΔW = lon_g × h/L`, ratio_első = (wf − ΔW)/wf
- Alul: LAT G | LON G | F% | R% (kerékenként Kamm kihasználtság)
- Paraméterek (config.py): KAMM_WHEELBASE_M, KAMM_CG_HEIGHT_M, KAMM_WEIGHT_FRONT, KAMM_MU

### MODE_SLIP (7) — yaw rate discrepancy (csúszásmonitor)

Összehasonlítja a mért yaw rate-et (IMU gz) az elvárt yaw rate-tel (lat_g/v):
- `delta = gz_mért − lat_g × g / v`
- **delta < 0** → első gumi csúszik (motor tart kifelé, kevesebb yaw mint várt)
- **delta > 0** → hátsó gumi csúszik (farok kiszáll, több yaw mint várt)
- Gauge sáv: zöld (±0.05 r/s) → sárga (±0.10) → piros (>±0.10)
- Alul: ω várható | ω mért | lat G | lean szög
- Csak >10 km/h felett érvényes (osztás nullával elkerülése)
- **Megjegyzés:** gz tengely valódi hardveren ellenőrizendő (yaw ≠ pitch/roll?)

### MODE_CALIB (5) — IMU kalibráció

Aktuális dőlésszög és lateral G megjelenítése.
Hosszú érintés → 20 mintás újrakalibrálás (accel referencia + gyro bias).
„OK – egyenes" jelzés ha |szög| < 3°.

### MODE_STATS (2) — session statisztika

BEST LAP | KÖRÖK SZÁMA | MAX SEBESSÉG

### MODE_DIAG (3) — diagnosztika

LAT, LON, SPD, CRS, SAT, FIX, WiFi állapot — valós idejű GPS adatok.

### MODE_SETUP (1) — rajtvonal felvétel

[BAL] GPS 20m — 2 mp hosszú érintés → zöld villanás + stopper indul
[JOBB] Fájlból (track.json) — rövid érintés
Aktuális GPS koordináták (lat/lon/sat).

---

## 4. Rajtvonal beállítás visszajelzése

```
GPS alapú rajtvonal beállítás (bal oldal 2 mp tartás SETUP módban):
  1. Rövid hangjelzés (1200 Hz, 150 ms)
  2. Teljes képernyő: ZÖLD — 800 ms-ig látható (sisakból is)
  3. Automatikusan visszaáll MODE_MAIN-re
  4. STOPPER azonnal elindul (azonnali mérés)
  5. Ha GPS nincs: mély hang (400 Hz, 500 ms), semmi nem változik
```

---

## 5. Stopper logika

```
lap_start_ts = None  → stopper: sötétszürke "--:--.--"

lap_start_ts beállítódik:
  A) GPS rajtvonal felvételkor (set_finish_line_from_gps)
  B) Első rajtvonal-átlépéskor (gps_task STATE_IN_LAP átmenet)

Futó stopper:
  elapsed_ms = ticks_diff(ticks_ms(), lap_start_ts)
  Frissítés: 5 Hz (200 ms-onként)

Rajtvonal átlépéskor:
  lap_start_ts = result.cross_ts_ms  → stopper nulláz, újraindul
```

---

## 6. Delta megjelenítés logika

```
delta_ms > 0 (lassabb a best lapnál):  PIROS  "+1.35s"
delta_ms < 0 (gyorsabb a best lapnál): ZÖLD   "-0.36s"
delta_ms == None (első kör):           SZÜRKE "DELTA ---"

Forrás:
  Ha van PRED: delta = predicted_ms - best_lap_ms
  Ha nincs PRED: delta = prev_lap_ms - best_lap_ms
```

---

## 7. Max sebesség megjelenítés

```
SESSION MAX (y=206, narancs, size 2):
  max_speed_kmh — session-szintű maximum, soha nem nullázódik
  Felirat: "SESSION MAX" (size 1, szürke)

ELOZO kör max sebesség (y=138, narancs, size 1):
  prev_lap_max_kmh — az előző befejezett kör maximuma
  Csak akkor jelenik meg, ha > 0
  Felirat formátum: "127 km/h"
```

---

## 8. GPS státusz indikátor

```
GPS FIX OK, SAT >= 7:  zöld ● prefix
GPS FIX OK, SAT 4–6:   sárga ● prefix
GPS NO FIX:            piros ● + "NO FIX"
```

---

## 9. Eseményindítók

| Esemény | Következmény |
|---------|-------------|
| M01: lap_recorded | ELOZO + max sebessége frissítés, STOPPER nullázódik |
| M01: set_finish_line_from_gps OK | Zöld villanás (800 ms), STOPPER indul |
| M02: predicted frissítve | PRED + DELTA frissítés (5 Hz) |
| Érintés (rövid, nem SETUP) | Képernyő mód váltás |
| Boot | MotoMeter logó (1.5 s) |

---

## 10. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M01 GPS & Köridőmérés | **Adatfogadás** — lap_start_ts, prev_lap_ms, prev_lap_max_kmh, best_lap |
| M02 Szektorelemzés | **Adatfogadás** — predicted_ms, delta_ms |
| M04 WiFi Uplink | **Státusz adat** — wifi_connected |
