# L1 – Üzleti Folyamat – Szektorelemzés & Delta

**Modul:** M02
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve

---

## 1. Modul célja

Az M02 modul a köridőt **szektorokra bontja** és ezek alapján:
1. Méri az egyes szektorok idejét
2. Tárolja a best szektor időket
3. Számítja a **prediktált köridőt** a kör közben (extrapoláció)
4. Meghatározza az aktuális **delta a best laphoz képest**
5. Számolja az elméleti **theoretical best lap**-et (best szektorok összege)

**Üzleti értékek:**
- A motoros kör közben látja: várható köridő + delta a best laphoz
- Minél több szektor → sűrűbb predikció-frissítés
- Theoretical best: megmutatja, mekkora a potenciális tartalék
- Szektor elemzéssel azonosítható a pálya azon szakasza, ahol a legtöbbet lehet nyerni

---

## 2. Szektor definíció

```
Szektorok a pályán s-koordináta alapján (0.0 = rajtvonal, 1.0 = egy teljes kör):

Példa Kakucs Ring-re (6 szektor):
  S1: 0.00 → 0.17  (rajtvonal → 1. kanyar kijárat)
  S2: 0.17 → 0.34  (1. kanyar kijárat → 2. kanyar belépés)
  S3: 0.34 → 0.51  (2. kanyar → pálya közepe)
  S4: 0.51 → 0.68  (közepe → chicane belépés)
  S5: 0.68 → 0.84  (chicane → utolsó kanyar)
  S6: 0.84 → 1.00  (utolsó kanyar → rajtvonal)

Technikai megvalósítás:
  Szektor határ = virtuális GPS vonal (rajzvonalhoz hasonló)
  config.py-ban definiált koordináta párok
  LapDetector-hoz hasonló vonalmetszés logika
  
Alternatíva (egyszerűsített első verzió):
  Szektorok s-koordináta alapján (GPS trace hossz %)
  → Nem igényel manuális szektor-vonal felvételt
  → Pályakerület ismerete szükséges
```

---

## 3. Fő folyamat

```
[Kör kezdete] → M01 jelzi: in_lap állapot
      │
      ▼
Szektor timer reset (minden szektor = 0)
Aktuális szektor: S1 aktív
      │
      ▼
GPS frissítésenként:
  → Ellenőrzés: elértük-e a következő szektor határát?
      NEM → sector_elapsed_ms frissítve
      IGEN → szektor idő rögzítve:
               sector_time[i] = elapsed
               best_sector[i] = min(best_sector[i], sector_time[i])
               prediktált köridő frissítve
               következő szektor aktív
      │
      ▼
Prediktált köridő számítás (minden szektor-átlépésnél):
  elapsed = eltelt idő a kör elejétől
  remaining_best = sum(best_sector[i] for i in remaining_sectors)
  predicted = elapsed + remaining_best
  delta = predicted - best_lap_ms
      │
      ▼
[Kör vége] → M01 jelzi: lap_recorded
  → Elmenti az összes sector_time-ot a körhöz
  → Frissíti best_sector értékeket
  → Számítja theoretical_best_lap-et
  → Reset: következő körhöz
```

---

## 4. Prediktált köridő részletei

```
Elv: a már megtett szektorok tényleges ideje + a maradék szektorok
     eddig legjobb ideje

Példa (6 szektor, best lap = 60 000 ms):
  best_sector = [9500, 11200, 10800, 9800, 10500, 8200] (ms)

  S4 után (kör közben):
    elapsed = 42 100 ms (S1+S2+S3+S4 tényleges)
    remaining_best = best_sector[S5] + best_sector[S6]
                   = 10 500 + 8 200 = 18 700 ms
    predicted = 42 100 + 18 700 = 60 800 ms
    delta = 60 800 - 60 000 = +800 ms (lassabb a best lapnál)

Az első körben (nincs best szektor adat):
  → predicted = None (nem számítható)
  → Kijelzőn: csak az eltelt idő
```

---

## 5. Theoretical Best Lap

```
Minden szektor best idejének összege:
  theoretical_best = sum(best_sector)

Feltétel: minden szektorban legalább 1 érvényes mérés

Értelmezés:
  Ha best_lap = 60 000 ms és theoretical_best = 58 200 ms:
  → 1.8 s tartalék van, ha minden szektorban a legjobb időt futja
  → Ez motiváló adat az analitikában (M06)
```

---

## 6. Eseményindítók

| Esemény | Következmény |
|---------|-------------|
| M01: in_lap | Szektor timer reset, S1 aktív |
| GPS update (szektor határ elérve) | Szektor idő rögzítve, prediktált köridő frissítve |
| M01: lap_recorded | Összes sector_time mentése, best_sector frissítés |
| Theoretical best kérés (M06) | sum(best_sector) visszaadva |

---

## 7. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M01 GPS & Köridőmérés | **Esemény fogadás** — in_lap, lap_recorded |
| M03 Kijelző | **Adatszolgáltatás** — predicted_ms, delta_ms |
| M04 WiFi Uplink | **Adatszolgáltatás** — sector_times körhöz csatolva |
| M06 Session Analitika | **Adatszolgáltatás** — theoretical_best, best_sector adatok |
