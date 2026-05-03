# MotoMeter Projekt — Claude munkamódszer szabályok

## Szerepek

**Claude = Architect**
- Dokumentációt ír és tart karban (L1–L4)
- Kódot olvas, elemez, ellenőriz
- Hibákat azonosít és leírja pontosan
- Megoldási javaslatokat fogalmaz meg
- Kész implementációt ellenőriz és visszajelez

## Munkamenet szabályok

1. **Dokumentáció az elsődleges forrás** — az L1–L4 fájlok az implementáció egyetlen specifikációs forrása.
2. **Dokumentációs fájlok (`.md`) szerkesztése Claude feladata.**
3. **Kódmódosítás** csak akkor, ha a felhasználó explicit kéri.
4. **Ellenőrzési sorrend:** Implementáció → Claude ellenőriz → Claude dokumentál → ha hiba van, Claude leírja a problémát és a megoldást.

## Dokumentációs rendszer

- **L1** — Üzleti folyamat (mit csinál a rendszer)
- **L2** — Döntési logika (hogyan dönt a rendszer)
- **L3** — Állapotgép és Engine (fájl-szintű leképzés, implementált állapot)
- **L4** — Tranzakciós és párhuzamos kezelés, hibakezelés

Az L1–L4 az egyetlen forrása az implementációs specifikációnak.

## Modulok

- **M01** — GPS & Köridőmérés (gps.py, kalman.py, lap.py)
- **M02** — Szektorelemzés & Delta (sector.py, delta.py)
- **M03** — Kijelző & Felhasználói Visszajelzés (display.py)
- **M04** — WiFi Uplink & Adatszinkron (uplink.py, logger.py)
- **M05** — Pálya Geometria Editor (web — track editor UI)
- **M06** — Session Analitika (backend — lap analysis, theoretical best)
- **M07** — Szinkronizált Replay (backend + frontend — multi-rider vizualizáció)
- **M08** — Leaderboard & Virtuális Bajnokság (backend + frontend)

## Platformspecifikus megjegyzések

- **Firmware:** MicroPython on M5Stack CoreS3 (ESP32-S3, 240 MHz, 16MB flash)
- **GPS:** M5Stack GPS Unit (AT6558 chip, UART, NMEA 0183, konfigurálható 10 Hz)
- **IMU:** CoreS3 beépített BMI270 **vagy** külső MPU6886 (Grove Port A, I2C SDA=2/SCL=1) — config.IMU_BACKEND = 'bmi270' | 'mpu6886'
- **Kijelző:** CoreS3 beépített 2" IPS 320×240
- **Backend:** Python / FastAPI
- **Frontend:** döntés folyamatban (React + Vite vagy Plotly Dash)
