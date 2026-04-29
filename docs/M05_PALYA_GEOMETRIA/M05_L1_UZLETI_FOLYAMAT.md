# L1 – Üzleti Folyamat – Pálya Geometria Editor

**Modul:** M05
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve (webes komponens)

---

## 1. Modul célja

Az M05 modul egy **webes pálya-editor**, amellyel a felhasználó műholdképen megrajzolhatja a pályaközépvonalat, definiálhatja a szektorokat, és kiszámolhatja a pálya görbületi profilját. Az eredmény az összes analitikai modul alapja.

**Üzleti értékek:**
- Bármely pálya felmérése műholdképből (nem csak Kakucs)
- Szektor definíció drag & drop szerkesztővel
- Görbületi profil: vizuálisan megmutatja, hol vannak a kanyarok
- Linearizált pályanézet: minden analitikai grafikon alapja
- Pálya adatok megoszthatók más felhasználókkal

---

## 2. Fő folyamat

```
[Track Explorer oldal megnyitása]
      │
      ▼
Műholdkép betöltése (Leaflet / MapLibre, ESRI World Imagery)
  Alapértelmezett nézet: Kakucs Ring (47.088°N, 19.283°E)
      │
      ▼
Középvonal rajzolás:
  - Kattintások sorozatával polyline rajzolás
  - Snap to: legközelebbi út (opcionális)
  - Szerkesztés: csúcspontok húzhatók
  - Zárt hurok: utolsó pont = első pont (pályahurok zárása)
      │
      ▼
Rajtvonal kijelölés:
  - A polyline egyik szegmensének kijelölése
  - "SET AS FINISH LINE" gomb
  - A szegmens merőleges vonalként jelenik meg
      │
      ▼
Szektor definíció:
  - Polyline mentén csúsztatható határoló markerek
  - Alapértelmezett: 6 egyenlő szektor
  - Kézzel húzhatók, szám módosítható (1–20)
      │
      ▼
Görbületi profil számítás:
  - Polyline csúcspontjain görbület kiszámítva
  - Eredmény: s-koordináta → görbület (1/R, előjeles) görbe
  - Megjelenítés: pálya alatt hullámvonal
      │
      ▼
Pálya mentése:
  - Neve, ország, körülmény
  - GeoJSON formátumban backend-re feltöltve
  - Más felhasználók számára is elérhető (publikus pályák)
```

---

## 3. Linearizált pályanézet (track unwrapping)

```
Bemenet: zárt polyline (GPS koordináták sorozata)

Feldolgozás:
  1. Kumulált ívhossz számítás minden csúcspontnál (Haversine)
  2. Normálás: s = 0.0 (rajtvonal) → s = 1.0 (egy teljes kör)
  3. Minden GPS pont leképezése (lat, lon) → s értékre

Megjelenítés:
  Vízszintes tengely: s-koordináta (0.0–1.0)
  Függőleges: görbület (kanyar irány és meredekség)
  Felül: szektor határok jelölve
  Alul: görbületi profil görbe

Görbületi profil értelmezése:
  Pozitív (vonal feljebb): balra kanyar
  Negatív (vonal lejjebb): jobbra kanyar
  Nulla: egyenes szakasz
  Meredek csúcs: éles kanyar
  Lapos hullám: szelíd kanyar
```

---

## 4. Görbület számítás

```
Három egymást követő csúcspont: A, B, C

1. Vektorok: AB = B - A, BC = C - B
2. Szög változás: dθ = angle(AB, BC)  [ívmérték]
3. Ívhossz: ds = |AB|
4. Görbület: κ = dθ / ds  [1/m]
5. Előjel: cross(AB, BC) > 0 → pozitív (bal kanyar)

Simítás: mozgó átlag (5 pont ablak) a zaj csökkentéséhez
```

---

## 5. Szektor határok GPS koordinátái

```
A webes szerkesztőben definiált szektor határok:
  - s-koordináta alapján kijelölve
  - Visszaszámítva GPS koordinátákra (interpoláció)
  - Virtuális vonalpárként definiálva (mint a rajtvonal)

Export: firmware config.py-ba beilleszthető formátum:
  SECTORS = [
    {'name': 'S1', 'lat1': ..., 'lon1': ..., 'lat2': ..., 'lon2': ...},
    {'name': 'S2', ...},
    ...
  ]
```

---

## 6. Események

| Esemény | Következmény |
|---------|-------------|
| Kattintás a térképen | Új csúcspont a középvonalra |
| Csúcspont húzás | Valós idejű polyline frissítés |
| "Close loop" gomb | Polyline zárt hurokká válik |
| "Set as finish line" | Kijelölt szegmens rajtvonalként jelölve |
| Szektor marker húzás | Szektor határ újraszámítás |
| "Calculate curvature" | Görbületi profil számítás + megjelenítés |
| "Save track" | GeoJSON backend-re mentve |
| "Export config" | config.py szintaxis generálva, letölthető |

---

## 7. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M01 GPS & Köridőmérés | **Konfiguráció forrása** — finish_line koordináták |
| M02 Szektorelemzés | **Konfiguráció forrása** — sector koordináták |
| M06 Session Analitika | **Alap geometria** — s-koordináta számításhoz |
| M07 Szinkronizált Replay | **Alap geometria** — pályatérkép megjelenítéshez |
