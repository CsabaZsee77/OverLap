import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { GpsPoint, TraceMetric } from '@/api/types'

interface Props {
  trace:        GpsPoint[]
  height?:      number
  playheadIdx?: number
  metric?:      TraceMetric
}

// ── Szín segédek ─────────────────────────────────────────────────────────────

function lerp(a: number, b: number, t: number) { return a + (b - a) * t }

function lerpColor(
  r1: number, g1: number, b1: number,
  r2: number, g2: number, b2: number,
  t: number
): string {
  return `rgb(${Math.round(lerp(r1,r2,t))},${Math.round(lerp(g1,g2,t))},${Math.round(lerp(b1,b2,t))})`
}

/** cyan → sárga → piros (0–1) */
function scaleColor(t: number): string {
  const s = Math.max(0, Math.min(1, t))
  return s < 0.5
    ? lerpColor(50, 200, 255,  255, 200, 30, s * 2)
    : lerpColor(255, 200, 30,  255,  40,  0, (s - 0.5) * 2)
}

/** kék (−1) → szürke (0) → piros (+1) */
function bipolarColor(t: number): string {
  const s = Math.max(-1, Math.min(1, t))
  return s < 0
    ? lerpColor(110, 110, 110,  50, 130, 255, -s)
    : lerpColor(110, 110, 110, 255,  50,  50,  s)
}

// ── Metrika konfiguráció ──────────────────────────────────────────────────────

const METRICS: Record<TraceMetric, { label: string; unit: string; max: number; bipolar: boolean }> = {
  speed: { label: 'Sebesség',   unit: 'km/h', max: 140, bipolar: false },
  lean:  { label: 'Dőlésszög', unit: '°',    max:  55, bipolar: true  },
  lat_g: { label: 'Oldalsó G', unit: 'G',    max: 1.2, bipolar: true  },
  lon_g: { label: 'Hossz. G',  unit: 'G',    max: 1.0, bipolar: true  },
}

function getValue(pt: GpsPoint, m: TraceMetric): number | null {
  switch (m) {
    case 'speed': return pt.speed_kmh
    case 'lean':  return pt.lean ?? pt.lean_deg ?? null
    case 'lat_g': return pt.lat_g ?? null
    case 'lon_g': return pt.lon_g ?? null
  }
}

function segColor(a: GpsPoint, _b: GpsPoint, m: TraceMetric): string {
  const v = getValue(a, m)
  if (v === null) return '#666'
  const cfg = METRICS[m]
  const t = v / cfg.max
  return cfg.bipolar ? bipolarColor(t) : scaleColor(t)
}

// ── Komponens ─────────────────────────────────────────────────────────────────

export default function TraceMap({
  trace, height = 300, playheadIdx, metric = 'speed',
}: Props) {
  const containerRef      = useRef<HTMLDivElement>(null)
  const mapRef            = useRef<L.Map | null>(null)
  const layerRef          = useRef<L.LayerGroup | null>(null)
  const playheadLayerRef  = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    mapRef.current = L.map(containerRef.current, {
      attributionControl: false,
      zoomControl: true,
    })
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd', maxZoom: 20,
    }).addTo(mapRef.current)
    layerRef.current        = L.layerGroup().addTo(mapRef.current)
    playheadLayerRef.current = L.layerGroup().addTo(mapRef.current)
    return () => { mapRef.current?.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const map   = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    if (!trace.length) return

    for (let i = 0; i < trace.length - 1; i++) {
      const a = trace[i], b = trace[i + 1]
      L.polyline([[a.lat, a.lon], [b.lat, b.lon]], {
        color: segColor(a, b, metric), weight: 4, opacity: 0.92,
      }).addTo(layer)
    }
    L.circleMarker([trace[0].lat, trace[0].lon], {
      radius: 6, color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1, weight: 2,
    }).bindTooltip('Start').addTo(layer)
    const last = trace[trace.length - 1]
    L.circleMarker([last.lat, last.lon], {
      radius: 6, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 1, weight: 2,
    }).bindTooltip('Finish').addTo(layer)

    map.fitBounds(
      L.latLngBounds(trace.map(p => [p.lat, p.lon] as L.LatLngTuple)),
      { padding: [24, 24] }
    )
  }, [trace, metric])

  useEffect(() => {
    const layer = playheadLayerRef.current
    if (!layer) return
    layer.clearLayers()
    if (playheadIdx == null || !trace[playheadIdx]) return
    const pt = trace[playheadIdx]
    L.circleMarker([pt.lat, pt.lon], {
      radius: 9, color: '#f97316', fillColor: '#f97316', fillOpacity: 0.9, weight: 2,
    }).addTo(layer)
  }, [playheadIdx, trace])

  const cfg = METRICS[metric]

  return (
    <div className="relative">
      <div
        ref={containerRef}
        style={{ height, borderRadius: 8, overflow: 'hidden' }}
        className="bg-[#1a1d26]"
      />
      {/* Legenda */}
      <div className="absolute bottom-2 left-2 z-[1000] bg-black/75 rounded px-2 py-1 text-[11px] text-gray-300 pointer-events-none">
        <div className="mb-1 font-medium">{cfg.label} ({cfg.unit})</div>
        {cfg.bipolar ? (
          <div className="flex items-center gap-1 text-[10px]">
            <span className="text-blue-400">−</span>
            <div className="w-16 h-1.5 rounded" style={{
              background: 'linear-gradient(to right,rgb(50,130,255),rgb(110,110,110),rgb(255,50,50))'
            }} />
            <span className="text-red-400">+</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-[10px]">
            <span className="text-cyan-400">0</span>
            <div className="w-16 h-1.5 rounded" style={{
              background: 'linear-gradient(to right,rgb(50,200,255),rgb(255,200,30),rgb(255,40,0))'
            }} />
            <span className="text-red-400">{cfg.max}{cfg.unit}</span>
          </div>
        )}
      </div>
    </div>
  )
}
