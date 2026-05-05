# OverLAP — Dokumentáció Index

**Projekt:** OverLAP — Motoros Telemetria & Track Analytics Platform
**Hardver:** M5Stack CoreS3 + AT6558 GPS + BMI270 IMU
**Firmware:** MicroPython (UIFlow2 kompatibilis)
**Backend:** Python / FastAPI
**Verzió:** v1.2.0
**Utolsó frissítés:** 2026-05-04

---

## Modulok

| Modul | Leírás | Státusz |
|-------|--------|---------|
| [M01 GPS & Köridőmérés](M01_GPS_KORIDOMEZES/) | AT6558 NMEA parse, Kalman szűrő, virtuális rajtvonal, köridő detektálás | 🔲 Tervezve |
| [M02 Szektorelemzés & Delta](M02_SZEKTORELEMZES/) | Szektor időmérés, prediktált köridő, best lap delta | 🔲 Tervezve |
| [M03 Kijelző & Visszajelzés](M03_KIJELZO/) | CoreS3 320×240 kijelző, köridő, prediktált idő, delta megjelenítés | 🔲 Tervezve |
| [M04 WiFi Uplink & Log](M04_WIFI_UPLINK/) | WiFi kapcsolat, HTTP POST, offline flash log, batch feltöltés | 🔲 Tervezve |
| [M05 Pálya Geometria Editor](M05_PALYA_GEOMETRIA/) | Műholdkép, középvonal rajzolás, szektor definíció, görbületi profil | 🔲 Tervezve |
| [M06 Session Analitika](M06_SESSION_ANALITIKA/) | Lap breakdown, theoretical best, delta graph, speed vs. position | 🔲 Tervezve |
| [M07 Szinkronizált Replay](M07_SZINKRONIZALT_REPLAY/) | Multi-rider vizualizáció, timeline editor, linearizált pályanézet | 🔲 Tervezve |
| [M08 Leaderboard & Bajnokság](M08_LEADERBOARD/) | Időszakos ranglisták, virtuális bajnokság, nevezési rendszer | 🔲 Tervezve |

---

## Fájlstruktúra

```
firmware/
  main.py             ← boot, async task scheduler
  config.py           ← rajtvonal, szektorok, WiFi credentials
  gps.py              ← AT6558 NMEA parser (GGA, RMC)  [M01]
  kalman.py           ← 2D Kalman szűrő, GPS+IMU fúzió [M01]
  imu.py              ← BMI270 gyorsulás + szögsebességi olvasás [M01]
  lap.py              ← virtuális vonalmetszés, köridő [M01]
  sector.py           ← szektor időmérés, best sector [M02]
  delta.py            ← prediktált köridő, delta kalkuláció [M02]
  display.py          ← CoreS3 kijelző kezelés 320×240 [M03]
  uplink.py           ← WiFi / HTTP POST / MQTT [M04]
  logger.py           ← lokális flash log [M04]

backend/
  main.py             ← FastAPI app
  api/
    sessions.py       ← session CRUD
    tracks.py         ← pálya geometria [M05]
    leaderboard.py    ← ranglisták [M08]
    replay.py         ← replay adat [M07]
  core/
    lap_analysis.py   ← theoretical best, sector stitching [M06]
    track_unwrap.py   ← 1D linearizált pálya (s-koordináta) [M05]
    sync_engine.py    ← vezérkör szinkronizáció [M07]
    curvature.py      ← görbületi profil számítás [M05]
  db/
    models.py         ← PostgreSQL + PostGIS modellek

frontend/
  (stack: döntés folyamatban — React+Vite vagy Plotly Dash)
  pages/
    dashboard/        ← M01-M02 áttekintő
    track_explorer/   ← M05 pálya editor
    session/          ← M06 analitika
    replay/           ← M07 vizualizáció
    leaderboard/      ← M08 ranglisták
    device/           ← firmware státusz

docs/
  INDEX.md            ← ez a fájl
  CLAUDE.md           ← munkamódszer szabályok
  M01_GPS_KORIDOMEZES/
  M02_SZEKTORELEMZES/
  M03_KIJELZO/
  M04_WIFI_UPLINK/
  M05_PALYA_GEOMETRIA/
  M06_SESSION_ANALITIKA/
  M07_SZINKRONIZALT_REPLAY/
  M08_LEADERBOARD/
```

---

## Architektúra összefoglaló

```
┌──────────────────────────────────────────────────────┐
│                  M5Stack CoreS3                      │
│                                                      │
│  AT6558 GPS (UART)  →  gps.py → kalman.py → lap.py  │
│  BMI270 IMU (I2C)   ↗             ↓                  │
│                             sector.py → delta.py     │
│                                   ↓                  │
│                             display.py (320×240)     │
│                                   ↓                  │
│                    uplink.py ← logger.py             │
│                        ↓                             │
│                   WiFi (hotspot / pálya AP)          │
└──────────────────────────┬───────────────────────────┘
                           │ HTTP POST / WebSocket
                           ▼
┌──────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                                                      │
│  /sessions  /tracks  /leaderboard  /replay           │
│       ↓                                              │
│  PostgreSQL + PostGIS                                │
│  (GPS trace, lap times, sector times, track geom.)   │
└──────────────────────────┬───────────────────────────┘
                           │ REST / WebSocket
                           ▼
┌──────────────────────────────────────────────────────┐
│                  Webes Felület                       │
│                                                      │
│  Dashboard │ Track Explorer │ Session Analysis       │
│  Virtual Replay │ Leaderboard │ Device Status        │
└──────────────────────────────────────────────────────┘
```

---

## GPS pontossági referencia

| GPS konfiguráció | Pozícióhiba | Időhiba 100 km/h-nál |
|---|---|---|
| AT6558 @ 1 Hz (alapértelmezett) | 2–5 m | ±0.07–0.18 s |
| AT6558 @ 10 Hz (konfigurált) | 2–5 m | ±0.07–0.09 s |
| AT6558 @ 10 Hz + Kalman (GPS+IMU) | ~1–2 m | ±0.04–0.07 s |

**Cél:** 10 Hz GPS + Kalman szűrő → ±0.05–0.1 s köridőhiba, ami rekreációs használatra megfelelő.

---

## Fejlesztési sorrend (MVP)

```
[1] ✅ Tervezés, dokumentáció
[2] ✅ M01 firmware alap: GPS parse + köridőmérés (v1.2: 30m vonal, MIN_OUTLAP_MS)
[3] ✅ M03 kijelző: köridő, lean, Kamm, SLIP, STATS, SETUP (v1.2: OverLAP branding)
[4] ✅ M02 szektorelemzés + prediktált köridő
[5] ✅ M04 WiFi uplink + offline log (v1.2: lean/Kamm Telegram + log mezők)
[6] 🔲 M01 Kalman szűrő finomhangolás (GPS+IMU fúzió javítása)
[7] 🔲 M05 pálya geometria editor (web)
[8] 🔲 M06 session analitika dashboard
[9] 🔲 M07 szinkronizált replay
[10] 🔲 M08 leaderboard + virtuális bajnokság
```

---

## Kapcsolódó dokumentumok

- [CLAUDE.md](CLAUDE.md) — munkamódszer szabályok
- [M01 L1 GPS & Köridőmérés folyamat](M01_GPS_KORIDOMEZES/M01_L1_UZLETI_FOLYAMAT.md)
- [M01 L2 Döntési logika](M01_GPS_KORIDOMEZES/M01_L2_DONTESI_LOGIKA.md)
- [M01 L3 Állapotgép & Engine](M01_GPS_KORIDOMEZES/M01_L3_ALLAPOTGEP_ES_ENGINE.md)
- [M01 L4 Tranzakciós & párhuzamos kezelés](M01_GPS_KORIDOMEZES/M01_L4_TRANZAKCIOS_ES_PARHUZAMOS.md)
- [M02 L1 Szektorelemzés folyamat](M02_SZEKTORELEMZES/M02_L1_UZLETI_FOLYAMAT.md)
- [M03 L1 Kijelző folyamat](M03_KIJELZO/M03_L1_UZLETI_FOLYAMAT.md)
- [M04 L1 WiFi Uplink folyamat](M04_WIFI_UPLINK/M04_L1_UZLETI_FOLYAMAT.md)
- [M05 L1 Pálya Geometria folyamat](M05_PALYA_GEOMETRIA/M05_L1_UZLETI_FOLYAMAT.md)
- [M06 L1 Session Analitika folyamat](M06_SESSION_ANALITIKA/M06_L1_UZLETI_FOLYAMAT.md)
- [M07 L1 Szinkronizált Replay folyamat](M07_SZINKRONIZALT_REPLAY/M07_L1_UZLETI_FOLYAMAT.md)
- [M08 L1 Leaderboard folyamat](M08_LEADERBOARD/M08_L1_UZLETI_FOLYAMAT.md)
