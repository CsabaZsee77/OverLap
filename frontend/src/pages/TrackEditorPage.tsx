/**
 * TrackEditorPage — Professzionális pálya szerkesztő
 *
 * Funkciók:
 *  - Centerline rajzolás kattintással, gumiszalag preview, dupla klikk → kész
 *  - Finish / start / szektor vonalak: 2 kattintás = vonal
 *  - MINDEN pont húzható (drag-to-move)
 *  - Szektor vonalak törlése, átnevezése
 *  - Circuit / stage mód váltó
 *  - Meglévő pálya betöltése szerkesztésre
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { createTrack, updateTrack, getTrack, getTrackFirmwareJsonUrl } from '@/api/client'
import type { TrackCreate, CenterlinePoint, Sector, TrackType } from '@/api/types'
import { fmtDistance } from '@/utils/format'

// ─── Típusok ────────────────────────────────────────────────────────────────

type DrawMode = 'none' | 'centerline' | 'finish_line' | 'start_line' | 'sector'

interface LineState { lat1: number; lon1: number; lat2: number; lon2: number }

// ─── Konstansok ──────────────────────────────────────────────────────────────

const COLORS = {
  centerline:  '#818cf8',   // indigo
  finish_line: '#f97316',   // orange
  start_line:  '#22c55e',   // green
  sector:      '#a78bfa',   // purple
  preview:     '#fbbf2488', // amber/transparent
}

const MODE_LABELS: Record<DrawMode, string> = {
  none:        '',
  centerline:  'Kattints a centerline pontjaira — dupla klikk a befejezéshez',
  finish_line: 'Kattints az út BAL szélére, majd a JOBB szélére',
  start_line:  'Kattints az út BAL szélére, majd a JOBB szélére',
  sector:      'Kattints az út BAL szélére, majd a JOBB szélére',
}

// ─── Segédfüggvények ─────────────────────────────────────────────────────────

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function clLength(pts: CenterlinePoint[]): number {
  let d = 0
  for (let i = 1; i < pts.length; i++)
    d += haversineM(pts[i-1].lat, pts[i-1].lon, pts[i].lat, pts[i].lon)
  return d
}

const HOLD_MS = 500   // hosszú nyomás küszöb

function divIcon(color: string, label = '', size = 10): L.DivIcon {
  return L.divIcon({
    className: 'mm-marker',
    iconSize:  [size, size],
    iconAnchor:[size / 2, size / 2],
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${color};border:2px solid #fff;
      display:flex;align-items:center;justify-content:center;
      font-size:8px;color:#fff;font-weight:700;
      box-shadow:0 1px 4px #0006;cursor:default;
    ">${label}</div>`,
  })
}

function lineIcon(color: string, size = 12): L.DivIcon {
  return L.divIcon({
    className: 'mm-marker',
    iconSize:  [size, size],
    iconAnchor:[size / 2, size / 2],
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:3px;
      background:${color};border:2px solid #fff;
      box-shadow:0 1px 4px #0006;cursor:default;
    "></div>`,
  })
}

/**
 * Hosszú nyomásra szerkeszthetővé váló marker.
 *
 * Alapból nem húzható (draggable: false).
 * 500ms tartott egérgomb → .mm-holding animáció → szerkesztési mód:
 *   - .mm-editing stílus (narancs ragyogás)
 *   - drag engedélyezve
 *   - dragend után visszaáll normálra és meghívja az onDragEnd callback-et
 *
 * Jobb klikk → onRightClick callback (pl. pont törlés)
 */
function makeEditableMarker(opts: {
  latlng:       L.LatLngTuple
  icon:         L.DivIcon
  layer:        L.LayerGroup
  onDragEnd:    (ll: L.LatLng) => void
  onRightClick?: () => void
}): L.Marker {
  const { latlng, icon, layer, onDragEnd, onRightClick } = opts

  // addTo() ELŐTT regisztráljuk az 'add' eventet — mert addTo() szinkron tüzeli!
  const m = L.marker(latlng, { icon, draggable: false })
  let holdTimer: ReturnType<typeof setTimeout> | null = null

  const setCursor = (cur: string) => {
    const el = m.getElement()
    if (!el) return
    el.style.cursor = cur
    // belső <div>-re is, hogy ne örökölje a pointert
    ;(el.querySelector('div') as HTMLElement | null)?.style.setProperty('cursor', cur)
  }

  // 'add' event: addTo() hívja, szinkron — ezt ELŐTTE kell regisztrálni
  m.on('add', () => {
    setCursor('default')
    // rAF: Leaflet esetenként a layout után állít inline stílust
    requestAnimationFrame(() => setCursor('default'))
  })

  m.addTo(layer)
  setCursor('default')

  // ── Hosszú nyomás indítása ─────────────────────────────────────
  m.on('mousedown', (e: L.LeafletMouseEvent) => {
    if ((e.originalEvent as MouseEvent).button !== 0) return

    m.getElement()?.classList.add('mm-holding')

    holdTimer = setTimeout(() => {
      holdTimer = null
      const el = m.getElement()
      el?.classList.remove('mm-holding')
      el?.classList.add('mm-editing')
      el && (el.style.cursor = 'move')
      m.dragging?.enable()
    }, HOLD_MS)
  })

  // ── Nyomás elengedése vagy elhagyás → töröl timert ─────────────
  const cancelHold = () => {
    if (holdTimer) {
      clearTimeout(holdTimer)
      holdTimer = null
      m.getElement()?.classList.remove('mm-holding')
    }
  }
  m.on('mouseup',  cancelHold)
  m.on('mouseout', cancelHold)

  // ── Drag befejezése → kilép szerkesztési módból ─────────────────
  m.on('dragend', () => {
    const el = m.getElement()
    el?.classList.remove('mm-editing')
    el && (el.style.cursor = 'default')
    m.dragging?.disable()
    onDragEnd(m.getLatLng())
  })

  // ── Jobb klikk ──────────────────────────────────────────────────
  if (onRightClick) {
    m.on('contextmenu', (e: L.LeafletMouseEvent) => {
      L.DomEvent.stop(e)
      onRightClick()
    })
  }

  return m
}

// ─── Fő komponens ─────────────────────────────────────────────────────────────

export default function TrackEditorPage() {
  const { id }  = useParams<{ id: string }>()
  const isEdit  = id !== 'new' && id !== undefined
  const trackId = isEdit ? Number(id) : null
  const navigate = useNavigate()

  // ── Form állapot ──────────────────────────────────────────────────────────
  const [name,           setName]       = useState('')
  const [nameHadAccent,  setNameHadAccent] = useState(false)
  const [country,    setCountry]    = useState('HU')
  const [trackType,  setTrackType]  = useState<TrackType>('circuit')
  const [centerline, setCenterline] = useState<CenterlinePoint[]>([])
  const [finishLine, setFinishLine] = useState<LineState | null>(null)
  const [startLine,  setStartLine]  = useState<LineState | null>(null)
  const [sectors,    setSectors]    = useState<Sector[]>([])
  const [drawMode,   setDrawMode]   = useState<DrawMode>('none')
  const [lineP1,     setLineP1]     = useState<L.LatLng | null>(null)
  const [sectorName, setSectorName] = useState('S1')
  const [saving,     setSaving]     = useState(false)
  const [savedId,    setSavedId]    = useState<number | null>(isEdit ? trackId : null)
  const [tileStyle,  setTileStyle]  = useState<'dark' | 'satellite'>('dark')
  const [panelOpen,  setPanelOpen]  = useState(true)

  // ── Refs ──────────────────────────────────────────────────────────────────
  const mapContRef   = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<L.Map | null>(null)
  const dataLayerRef = useRef<L.LayerGroup | null>(null)   // rajzolt elemek
  const uiLayerRef   = useRef<L.LayerGroup | null>(null)   // preview / temp
  const rubberRef    = useRef<L.Polyline | null>(null)      // gumiszalag vonal
  const p1MarkerRef  = useRef<L.Marker | null>(null)        // első kattintás pontja

  const darkLayerRef = useRef<L.TileLayer | null>(null)
  const satLayerRef  = useRef<L.TileLayer | null>(null)

  // Ref-ek a callback-ekhez (nem triggerelnek re-rendert)
  const drawModeRef   = useRef(drawMode)
  const centerlineRef = useRef(centerline)
  const lineP1Ref     = useRef(lineP1)
  const sectorNameRef = useRef(sectorName)
  const trackTypeRef  = useRef(trackType)

  useEffect(() => { drawModeRef.current = drawMode },    [drawMode])
  useEffect(() => { centerlineRef.current = centerline },[centerline])
  useEffect(() => { lineP1Ref.current = lineP1 },        [lineP1])
  useEffect(() => { sectorNameRef.current = sectorName },[sectorName])
  useEffect(() => { trackTypeRef.current = trackType },  [trackType])

  // ── Meglévő pálya betöltése ────────────────────────────────────────────────
  useEffect(() => {
    if (!isEdit || !trackId) return
    getTrack(trackId).then(t => {
      const stripped = t.name.replace(/[^\x00-\x7F]/g, '')
      setNameHadAccent(stripped !== t.name)
      setName(stripped)
      setCountry(t.country ?? 'HU')
      setTrackType(t.track_type)
      setCenterline(t.centerline)
      setFinishLine(t.finish_line)
      setStartLine(t.start_line ?? null)
      setSectors(t.sectors)
    })
  }, [isEdit, trackId])

  // ── Térkép inicializálása ─────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContRef.current || mapRef.current) return

    const map = L.map(mapContRef.current, {
      center: [47.09, 19.28],
      zoom: 15,
      attributionControl: false,
      doubleClickZoom: false,   // dupla klikk a rajzoláshoz kell
    })
    const darkTile = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { subdomains: 'abcd', maxZoom: 20 }
    ).addTo(map)
    darkLayerRef.current = darkTile

    const satTile = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19 }
    )
    satLayerRef.current = satTile

    dataLayerRef.current = L.layerGroup().addTo(map)
    uiLayerRef.current   = L.layerGroup().addTo(map)
    mapRef.current = map

    // ── Kattintás kezelő ────────────────────────────────────────────────────
    map.on('click', (e: L.LeafletMouseEvent) => {
      const mode = drawModeRef.current
      const pt   = e.latlng

      if (mode === 'centerline') {
        const np: CenterlinePoint = { lat: pt.lat, lon: pt.lng }
        setCenterline(prev => [...prev, np])
        return
      }

      if (mode === 'finish_line' || mode === 'start_line' || mode === 'sector') {
        if (!lineP1Ref.current) {
          // Első pont → marker
          setLineP1(pt)
          const m = L.marker(pt, {
            icon: lineIcon(
              mode === 'finish_line' ? COLORS.finish_line :
              mode === 'start_line'  ? COLORS.start_line  : COLORS.sector
            ),
          }).addTo(uiLayerRef.current!)
          p1MarkerRef.current = m
        } else {
          // Második pont → vonal mentés
          const p1 = lineP1Ref.current
          const line: LineState = { lat1: p1.lat, lon1: p1.lng, lat2: pt.lat, lon2: pt.lng }

          if (mode === 'finish_line') setFinishLine(line)
          if (mode === 'start_line')  setStartLine(line)
          if (mode === 'sector') {
            const sn = sectorNameRef.current
            setSectors(prev => {
              const rest = prev.filter(s => s.name !== sn)
              return [...rest, { name: sn, ...line }]
            })
            setSectorName(prev => `S${(parseInt(prev.replace(/\D/g, ''), 10) || 0) + 1}`)
          }

          // Cleanup
          uiLayerRef.current?.clearLayers()
          p1MarkerRef.current = null
          rubberRef.current = null
          setLineP1(null)
          setDrawMode('none')
        }
      }
    })

    // ── Dupla klikk → centerline befejezése ─────────────────────────────────
    map.on('dblclick', () => {
      if (drawModeRef.current === 'centerline') {
        setDrawMode('none')
      }
    })

    // ── Egér mozgás → gumiszalag vonal ──────────────────────────────────────
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      const mode = drawModeRef.current
      const ui   = uiLayerRef.current
      if (!ui) return

      if (mode === 'centerline') {
        const cl = centerlineRef.current
        if (cl.length === 0) return
        const last = cl[cl.length - 1]
        const coords: L.LatLngTuple[] = [[last.lat, last.lon], [e.latlng.lat, e.latlng.lng]]
        if (rubberRef.current) {
          rubberRef.current.setLatLngs(coords)
        } else {
          rubberRef.current = L.polyline(coords, {
            color: COLORS.centerline, weight: 2, dashArray: '6 4', opacity: 0.7,
          }).addTo(ui)
        }
        return
      }

      if ((mode === 'finish_line' || mode === 'start_line' || mode === 'sector')
          && lineP1Ref.current) {
        const p1 = lineP1Ref.current
        const coords: L.LatLngTuple[] = [[p1.lat, p1.lng], [e.latlng.lat, e.latlng.lng]]
        if (rubberRef.current) {
          rubberRef.current.setLatLngs(coords)
        } else {
          const color = mode === 'finish_line' ? COLORS.finish_line :
                        mode === 'start_line'  ? COLORS.start_line  : COLORS.sector
          rubberRef.current = L.polyline(coords, {
            color, weight: 2, dashArray: '6 4', opacity: 0.8,
          }).addTo(ui)
        }
      }
    })

    // ── Escape → rajzolás megszakítása ───────────────────────────────────────
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') {
        setDrawMode('none')
        setLineP1(null)
        uiLayerRef.current?.clearLayers()
        rubberRef.current = null
        p1MarkerRef.current = null
      }
    }
    window.addEventListener('keydown', onKey)

    return () => {
      window.removeEventListener('keydown', onKey)
      map.remove()
      mapRef.current = null
    }
  }, [])

  // ── Rétegek újrarajzolása állapotváltozáskor ──────────────────────────────
  const redraw = useCallback(() => {
    const layer = dataLayerRef.current
    if (!layer) return
    layer.clearLayers()

    // Centerline
    if (centerline.length > 0) {
      const latlngs = centerline.map(p => [p.lat, p.lon] as L.LatLngTuple)
      L.polyline(latlngs, { color: COLORS.centerline, weight: 3, dashArray: '8 4', opacity: 0.85 }).addTo(layer)

      centerline.forEach((pt, i) => {
        const isEndpoint = i === 0 || i === centerline.length - 1
        makeEditableMarker({
          latlng:  [pt.lat, pt.lon],
          icon:    divIcon(COLORS.centerline, String(i + 1), isEndpoint ? 14 : 10),
          layer,
          onDragEnd: (ll) => setCenterline(prev =>
            prev.map((p, idx) => idx === i ? { lat: ll.lat, lon: ll.lng } : p)
          ),
          onRightClick: () => setCenterline(prev => prev.filter((_, idx) => idx !== i)),
        })
      })
    }

    // Célvonal
    if (finishLine) drawEditableLine(layer, finishLine, COLORS.finish_line, 'Cél', setFinishLine)

    // Startvonal (stage)
    if (trackType === 'stage' && startLine)
      drawEditableLine(layer, startLine, COLORS.start_line, 'Start', setStartLine)

    // Szektorok
    sectors.forEach((s, si) => {
      drawEditableLine(
        layer,
        { lat1: s.lat1, lon1: s.lon1, lat2: s.lat2, lon2: s.lon2 },
        COLORS.sector,
        s.name,
        (updated) => updated
          ? setSectors(prev => prev.map((x, xi) => xi === si ? { ...x, ...updated } : x))
          : setSectors(prev => prev.filter((_, xi) => xi !== si))
      )
    })
  }, [centerline, finishLine, startLine, sectors, trackType])

  useEffect(() => { redraw() }, [redraw])

  // ── Tile réteg váltó ─────────────────────────────────────────────────────
  useEffect(() => {
    const map  = mapRef.current
    const dark = darkLayerRef.current
    const sat  = satLayerRef.current
    if (!map || !dark || !sat) return
    if (tileStyle === 'dark') {
      map.removeLayer(sat)
      if (!map.hasLayer(dark)) dark.addTo(map)
    } else {
      map.removeLayer(dark)
      if (!map.hasLayer(sat)) sat.addTo(map)
    }
  }, [tileStyle])

  // ── Térkép középre igazítása betöltéskor ─────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || centerline.length < 2) return
    const bounds = L.latLngBounds(centerline.map(p => [p.lat, p.lon] as L.LatLngTuple))
    mapRef.current.fitBounds(bounds, { padding: [40, 40] })
  }, [centerline.length > 1 ? 'loaded' : 'empty'])  // eslint-disable-line

  // ── Board JSON export (helyi letöltés, mentés nélkül is működik) ─────────
  const handleBoardExport = () => {
    if (!finishLine) { alert('Rajzold meg a célvonalat'); return }
    const data: Record<string, unknown> = {
      name:        name.trim() || 'Névtelen pálya',
      track_type:  trackType,
      finish_line: finishLine,
    }
    if (trackType === 'stage' && startLine) data.start_line = startLine
    data.sectors = sectors
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = 'track.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Mentés ────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!name.trim())        { alert('Adj meg pályanevet'); return }
    if (/[^\x00-\x7F]/.test(name)) { alert('A pályanév csak ASCII karaktereket tartalmazhat (ékezetek nem megengedettek)'); return }
    if (!finishLine)         { alert('Rajzold meg a célvonalat'); return }
    if (trackType === 'stage' && !startLine) { alert('Stage módhoz startvonal is kell'); return }
    if (centerline.length < 2) { alert('Rajzolj legalább 2 centerline pontot'); return }

    const payload: TrackCreate = {
      name, country, track_type: trackType,
      finish_line: finishLine,
      start_line: trackType === 'stage' ? startLine : null,
      sectors,
      centerline,
    }
    setSaving(true)
    try {
      const result = isEdit && trackId
        ? await updateTrack(trackId, payload)
        : await createTrack(payload)
      setSavedId(result.id)
      navigate('/tracks')
    } catch {
      alert('Mentés sikertelen — fut a backend?')
    } finally {
      setSaving(false)
    }
  }

  // ── Rajzolás gomb ─────────────────────────────────────────────────────────
  const toggleMode = (mode: DrawMode) => {
    if (drawMode === mode) {
      setDrawMode('none')
    } else {
      setDrawMode(mode)
    }
    setLineP1(null)
    uiLayerRef.current?.clearLayers()
    rubberRef.current = null
    p1MarkerRef.current = null
  }

  const modeActive = (mode: DrawMode) => drawMode === mode

  return (
    <div className="flex h-full overflow-hidden relative">

      {/* ── Bal panel ────────────────────────────────────────────────────── */}
      <div className={`
        shrink-0 bg-[#13151e] border-r border-gray-800 flex flex-col overflow-y-auto
        transition-all duration-200
        ${panelOpen ? 'w-64' : 'w-0 overflow-hidden border-r-0'}
      `}>

        {/* Fejléc */}
        <div className="px-4 py-3 border-b border-gray-800">
          <button onClick={() => navigate('/tracks')}
            className="text-xs text-gray-500 hover:text-gray-300 mb-2 block">
            ← Vissza
          </button>
          <h2 className="text-sm font-semibold text-white">
            {isEdit ? 'Pálya szerkesztés' : 'Új pálya'}
          </h2>
        </div>

        <div className="flex-1 p-4 space-y-5">

          {/* Alap adatok */}
          <section>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Alap adatok</p>
            <div className="space-y-2">
              <input value={name}
                onChange={e => {
                  const raw = e.target.value
                  const stripped = raw.replace(/[^\x00-\x7F]/g, '')
                  setNameHadAccent(stripped !== raw)
                  setName(stripped)
                }}
                placeholder="Palya neve (ASCII only)"
                className={`w-full bg-[#1a1d26] border rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-orange-500 ${nameHadAccent ? 'border-yellow-500' : 'border-gray-700'}`} />
              {nameHadAccent && (
                <p className="text-xs text-yellow-500 -mt-1">Ékezetes karakterek eltávolítva (board nem támogatja)</p>
              )}
              <div className="flex gap-2">
                <input value={country} onChange={e => setCountry(e.target.value.toUpperCase())}
                  maxLength={3} placeholder="HU"
                  className="w-16 bg-[#1a1d26] border border-gray-700 rounded px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500" />
                <div className="flex gap-1 flex-1">
                  {(['circuit', 'stage'] as TrackType[]).map(t => (
                    <button key={t} onClick={() => setTrackType(t)}
                      className={`flex-1 text-xs py-1.5 rounded border capitalize transition-colors ${
                        trackType === t
                          ? 'bg-orange-600 border-orange-500 text-white'
                          : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                      }`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              {trackType === 'stage' && (
                <p className="text-xs text-blue-400">Stage: külön start + célvonal</p>
              )}
            </div>
          </section>

          {/* Rajzolás eszközök */}
          <section>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Rajzolás</p>
            <div className="space-y-1.5">

              {/* Centerline */}
              <div className="flex gap-1.5">
                <button onClick={() => toggleMode('centerline')}
                  className={`flex-1 text-left text-xs px-2.5 py-2 rounded border transition-colors ${
                    modeActive('centerline')
                      ? 'bg-indigo-500/20 border-indigo-500 text-indigo-300'
                      : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                  }`}>
                  <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 mr-1.5" />
                  {modeActive('centerline') ? '⏎ dupla klikk = kész' : 'Centerline rajzolás'}
                </button>
                {centerline.length > 0 && (
                  <button onClick={() => setCenterline([])}
                    className="px-2 text-xs text-gray-600 hover:text-red-400 bg-gray-800 border border-gray-700 rounded transition-colors"
                    title="Törlés">
                    ✕
                  </button>
                )}
              </div>
              {centerline.length > 0 && (
                <p className="text-xs text-gray-600 pl-1">
                  {centerline.length} pont · {fmtDistance(clLength(centerline))}
                  <span className="text-gray-700 ml-1">(jobb klikk = pont töröl)</span>
                </p>
              )}

              {/* Célvonal */}
              <div className="flex gap-1.5">
                <button onClick={() => toggleMode('finish_line')}
                  className={`flex-1 text-left text-xs px-2.5 py-2 rounded border transition-colors ${
                    modeActive('finish_line')
                      ? 'bg-orange-500/20 border-orange-500 text-orange-300'
                      : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                  }`}>
                  <span className="inline-block w-2 h-2 rounded bg-orange-400 mr-1.5" />
                  Célvonal
                  {finishLine && <span className="ml-1 text-green-400">✓</span>}
                </button>
                {finishLine && (
                  <button onClick={() => setFinishLine(null)}
                    className="px-2 text-xs text-gray-600 hover:text-red-400 bg-gray-800 border border-gray-700 rounded transition-colors"
                    title="Törlés">
                    ✕
                  </button>
                )}
              </div>

              {/* Startvonal (stage) */}
              {trackType === 'stage' && (
                <div className="flex gap-1.5">
                  <button onClick={() => toggleMode('start_line')}
                    className={`flex-1 text-left text-xs px-2.5 py-2 rounded border transition-colors ${
                      modeActive('start_line')
                        ? 'bg-green-500/20 border-green-500 text-green-300'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                    }`}>
                    <span className="inline-block w-2 h-2 rounded bg-green-400 mr-1.5" />
                    Startvonal
                    {startLine && <span className="ml-1 text-green-400">✓</span>}
                  </button>
                  {startLine && (
                    <button onClick={() => setStartLine(null)}
                      className="px-2 text-xs text-gray-600 hover:text-red-400 bg-gray-800 border border-gray-700 rounded transition-colors"
                      title="Törlés">
                      ✕
                    </button>
                  )}
                </div>
              )}

              {/* Szektor */}
              <div>
                <div className="flex gap-1.5 mb-1">
                  <input value={sectorName} onChange={e => setSectorName(e.target.value)}
                    className="w-14 bg-[#1a1d26] border border-gray-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-purple-500" />
                  <button onClick={() => toggleMode('sector')}
                    className={`flex-1 text-left text-xs px-2.5 py-1 rounded border transition-colors ${
                      modeActive('sector')
                        ? 'bg-purple-500/20 border-purple-500 text-purple-300'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                    }`}>
                    <span className="inline-block w-2 h-2 rounded-full bg-purple-400 mr-1.5" />
                    {modeActive('sector') ? '2. pontot kell...' : 'Szektor hozzáadás'}
                  </button>
                </div>

                {/* Szektor lista */}
                {sectors.map((s, i) => (
                  <div key={s.name + i}
                    className="flex items-center justify-between text-xs text-gray-400 py-0.5 pl-1">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                      <input
                        value={s.name}
                        onChange={e => setSectors(prev =>
                          prev.map((x, xi) => xi === i ? { ...x, name: e.target.value } : x)
                        )}
                        className="bg-transparent w-10 text-purple-300 focus:outline-none focus:border-b focus:border-purple-400"
                      />
                    </div>
                    <button onClick={() => setSectors(prev => prev.filter((_, xi) => xi !== i))}
                      className="text-gray-600 hover:text-red-400 transition-colors">✕</button>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Aktív mód jelzés */}
          {drawMode !== 'none' && (
            <div className="text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-700/40 rounded px-3 py-2 leading-relaxed">
              {MODE_LABELS[drawMode]}
              <div className="text-yellow-600 mt-0.5">ESC = mégse</div>
            </div>
          )}

          {/* Legenda */}
          <section className="border-t border-gray-800 pt-4">
            <p className="text-xs text-gray-600 mb-2 uppercase tracking-wider">Legenda</p>
            <div className="space-y-1 text-xs">
              {[
                { color: COLORS.centerline, label: 'Centerline' },
                { color: COLORS.finish_line, label: 'Célvonal' },
                ...(trackType === 'stage' ? [{ color: COLORS.start_line, label: 'Startvonal' }] : []),
                { color: COLORS.sector, label: 'Szektorzónák' },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-2 text-gray-400">
                  <span className="w-3 h-0.5 rounded-full shrink-0" style={{ background: item.color }} />
                  {item.label}
                </div>
              ))}
              <div className="text-gray-600 mt-1">Minden pont húzható</div>
            </div>
          </section>
        </div>

        {/* Mentés + Board JSON */}
        <div className="p-4 border-t border-gray-800 space-y-2">
          {finishLine && (
            <button onClick={handleBoardExport}
              className="w-full py-1.5 rounded border border-blue-700 text-blue-400 hover:text-blue-300 hover:border-blue-500 text-xs transition-colors">
              ↓ Board JSON letöltése
            </button>
          )}
          {savedId && (
            <a href={getTrackFirmwareJsonUrl(savedId)} download
              className="block w-full py-1.5 text-center rounded bg-blue-800 hover:bg-blue-700 text-blue-200 text-xs transition-colors">
              ↓ Board JSON (mentett, szerverről)
            </a>
          )}
          <button onClick={handleSave} disabled={saving}
            className="w-full py-2 rounded bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white text-sm font-medium transition-colors">
            {saving ? 'Mentés...' : isEdit ? 'Frissítés' : 'Pálya mentése'}
          </button>
        </div>
      </div>

      {/* ── Térkép ───────────────────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <div ref={mapContRef} className="w-full h-full" />

        {/* Panel toggle gomb */}
        <button
          onClick={() => setPanelOpen(o => !o)}
          className="absolute top-1/2 -translate-y-1/2 left-0 z-[1000]
            bg-gray-900/90 border border-gray-700 border-l-0 rounded-r
            px-1 py-3 text-gray-400 hover:text-white transition-colors shadow-lg"
          title={panelOpen ? 'Panel bezárása' : 'Panel megnyitása'}
        >
          {panelOpen ? '◀' : '▶'}
        </button>

        {/* Tile réteg választó */}
        <button
          onClick={() => setTileStyle(s => s === 'dark' ? 'satellite' : 'dark')}
          className="absolute top-3 right-3 z-[1000] bg-gray-900/85 border border-gray-700 rounded px-2.5 py-1 text-xs text-gray-300 hover:text-white transition-colors backdrop-blur-sm shadow-lg"
        >
          {tileStyle === 'dark' ? '🛰 Műhold' : '🌑 Térkép'}
        </button>

        {/* Mód overlay a térképen */}
        {drawMode !== 'none' && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000]
            bg-gray-900/90 border border-yellow-600/60 rounded-lg px-4 py-2
            text-xs text-yellow-300 backdrop-blur-sm pointer-events-none shadow-xl">
            ✏️ {MODE_LABELS[drawMode]}
          </div>
        )}

        {/* Pont számláló overlay */}
        {drawMode === 'centerline' && centerline.length > 0 && (
          <div className="absolute bottom-6 right-4 z-[1000]
            bg-gray-900/80 rounded px-2.5 py-1 text-xs text-indigo-300">
            {centerline.length} pont · {fmtDistance(clLength(centerline))}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Húzható vonalszerkesztő segéd ──────────────────────────────────────────

function drawEditableLine(
  layer: L.LayerGroup,
  line: LineState,
  color: string,
  label: string,
  onChange: (updated: LineState | null) => void
) {
  const latlngs: L.LatLngTuple[] = [[line.lat1, line.lon1], [line.lat2, line.lon2]]

  // Vonal (nem interaktív, csak vizuális)
  L.polyline(latlngs, { color, weight: 4, opacity: 0.9, interactive: false })
    .addTo(layer)

  // Bal végpont — hosszú nyomásra húzható
  makeEditableMarker({
    latlng:  [line.lat1, line.lon1],
    icon:    lineIcon(color, 12),
    layer,
    onDragEnd: (ll) => onChange({ lat1: ll.lat, lon1: ll.lng, lat2: line.lat2, lon2: line.lon2 }),
  })

  // Jobb végpont — hosszú nyomásra húzható
  makeEditableMarker({
    latlng:  [line.lat2, line.lon2],
    icon:    lineIcon(color, 12),
    layer,
    onDragEnd: (ll) => onChange({ lat1: line.lat1, lon1: line.lon1, lat2: ll.lat, lon2: ll.lng }),
  })

  // Középső marker — egész vonalat tolja, jobb klikk = töröl
  const dLat = line.lat2 - line.lat1
  const dLon = line.lon2 - line.lon1
  const midLat = (line.lat1 + line.lat2) / 2
  const midLon = (line.lon1 + line.lon2) / 2

  makeEditableMarker({
    latlng:  [midLat, midLon],
    icon:    divIcon(color, label.substring(0, 3), 16),
    layer,
    onDragEnd: (ll) => onChange({
      lat1: ll.lat - dLat / 2, lon1: ll.lng - dLon / 2,
      lat2: ll.lat + dLat / 2, lon2: ll.lng + dLon / 2,
    }),
    onRightClick: () => onChange(null),
  })
}
