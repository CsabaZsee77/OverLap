# L1 – Üzleti Folyamat – Szinkronizált Replay

**Modul:** M07
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve (backend + frontend)

---

## 1. Modul célja

Az M07 az egész rendszer **leginnovatívabb komponense**: tetszőleges felhasználók tetszőleges köreit szinkronizálva jeleníti meg egy pályán, mintha egyszerre versenyeznének. A "vezérkör" szinkronizáció + linearizált pályanézet + timeline editor kombinációja egyedi a nyílt/olcsó rendszerek között.

**Üzleti értékek:**
- Valós időben: padokon ülő nézők látják a virtuális versenyt
- Utólag: részletes elemzés, hol nyílt/zárt a gap
- Multi-rider overlay: azonosítható, hol lehet előzni
- Timeline editor: precíz szinkronizáció tetszőleges pontra

---

## 2. Vezérkör szinkronizáció

```
Elv:
  Kijelölt vezérkör: A motoros adott körének s(t) pályahaladása
  Minden más kör (rider, saját): ugyanarra az s(t) → idő mappingre igazítva

Számítás:
  ref_lap: GPS trace → s(t) görbe (s = normalizált pályahaladás)
  
  Minden más laphoz:
    s_i(t_relative) interpolálva a ref_lap s(t)-jével
    Ha ref_lap s=0.3 -nál tart t=18.5 s-nél,
    akkor a többi kör is annál a pályapontnál jelenik meg

Eredmény:
  Pályatérképen: minden motoros egy mozgó pont
  Látható: ki hol előz, hol nyílik a gap
```

---

## 3. Realtime mód (élő vizualizáció)

```
Egy kör késleltetéssel:

  T=0: Motoros A elindul
  T=55s: Motoros A célba ér (körbeért)
  
  Közben bárki elindulhat (B, C, D...)
  
  T=55s-tól: A vezérkör = A motoros épp befejezett köre
  Vizualizáción megjelennek: B, C, D szinkronizálva A-hoz
  
  Néző látja: mintha A, B, C, D egyszerre indultak volna
  Meg lehet figyelni: ki volt hol gyorsabb, hol zárkózott

Technikai megvalósítás:
  Backend: WebSocket push (minden GPS update → backend → frontend)
  Frontend: mozgó pontok animáció (requestAnimationFrame)
  Késleltetés: 1 teljes kör (a vezérkör befejezéséig)
```

---

## 4. Sztatikus Multi-rider Overlay

```
Vizualizáció 1: Pályatérkép overlay
  Minden kör GPS trace-e megjelenítve a pályán
  Szín: különböző rider / kör
  Látható: nyomvonalak különbségei (kanyar bevétel, féktáv)

Vizualizáció 2: Linearizált pályanézet
  X tengely: idő (s)
  Y tengely: s-koordináta (0.0–1.0, pályahaladás)
  
  Minden kör egy sor (vízszintes vonal helyett ferde görbe):
    Meredekebb = gyorsabb az adott szakaszon
    Görbe keresztezése = előzés a szimulált versenyen
  
  Alatta: görbületi profil (M05 alapján)
    → Látható: kanyarban gyorsabb / lassabb

Vizualizáció 3: Gap grafikon
  X tengely: s-koordináta
  Y tengely: időkülönbség (s) a vezérkörhöz képest
  Pozitív = lemarad, negatív = vezet
```

---

## 5. Timeline Editor mód

```
Cél: Precíz szinkronizáció tetszőleges pályapontra

UI: video szerkesztő szerű interface
  Felül: pályatérkép
  Alul: "trackok" egymás alatt (egy sor = egy kör/rider)
  
  Szinkronizációs pont kiválasztása:
    - Start pont (0.0) → mindenki az indulásnál szinkronizálva
    - Szektor határ (pl. S3 belépése) → csak onnan elemez
    - Tetszőleges s-koordináta → drag & drop markerrel
  
  Drag & drop:
    Egy kör trackjét húzva eltolható az időtengelyen
    → pl. S3-tól szinkronizálva, az előző szakasz nem számít
  
  Hasznos ha:
    Két kör nagyon különböző → S4-től szinkronizálva vizsgálandó
    Specifikus kanyar összehasonlítása → apex pontra szinkronizálás
```

---

## 6. Rider kiválasztó UI

```
Bal panel:
  Saját körök listája (session-ből)
  Más felhasználók keresése (publikus profilok)
  
  Rider kártya:
    Avatar | Név | Best Lap | Szesszió dátuma
    [ADD TO COMPARISON] gomb

Kiválasztott riderek (max. 6):
  Különböző szín hozzárendelve
  Bármikor eltávolítható

Szinkronizációs alap:
  Default: start pont
  Módosítható: timeline editorban
```

---

## 7. Események

| Esemény | Következmény |
|---------|-------------|
| Rider hozzáadása | GPS trace betöltése backendről, szinkronizálás |
| Szinkronizációs pont mozgatása | Összes görbe újraszámítása |
| Play gomb | Animáció indul (pályatérkép + linearizált nézet) |
| Track drag (timeline editor) | Adott kör időbeli eltolása |
| Realtime mode bekapcsolása | WebSocket kapcsolat a backendhez |
| Vezérkör befejezése (realtime) | Szinkronizált vizualizáció frissítése |

---

## 8. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M05 Pálya Geometria | **Alap geometria** — s-koordináta, pályatérkép |
| M06 Session Analitika | **Adatforrás** — session és kör GPS trace-ek |
| M04 WiFi Uplink | **Realtime adat** — WebSocket élő köridők |
| M08 Leaderboard | **Kapcsolódó nézet** — leaderboard sorból replay nyitható |
