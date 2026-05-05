import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { GpsPoint } from '@/api/types'

interface Props {
  trace: GpsPoint[]
  height?: number
  playheadIdx?: number
}

function speedColor(speed: number): string {
  const t = Math.min(speed / 120, 1)
  if (t < 0.5) {
    const u = t * 2
    return `rgb(${Math.round(50 + 205 * u)}, ${Math.round(100 + 100 * (1 - u))}, 255)`
  } else {
    const u = (t - 0.5) * 2
    return `rgb(255, ${Math.round(200 - 150 * u)}, ${Math.round(30 * (1 - u))})`
  }
}

export default function TraceMap({ trace, height = 300, playheadIdx }: Props) {
  const containerRef    = useRef<HTMLDivElement>(null)
  const mapRef          = useRef<L.Map | null>(null)
  const layerRef        = useRef<L.LayerGroup | null>(null)
  const playheadLayerRef = useRef<L.LayerGroup | null>(null)

  // ── Térkép inicializálás ─────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    if (!mapRef.current) {
      mapRef.current = L.map(containerRef.current, {
        attributionControl: false,
        zoomControl: true,
      })
      L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        { subdomains: 'abcd', maxZoom: 20 }
      ).addTo(mapRef.current)
      layerRef.current        = L.layerGroup().addTo(mapRef.current)
      playheadLayerRef.current = L.layerGroup().addTo(mapRef.current)
    }
  }, [])

  // ── GPS nyomvonal rajzolás ────────────────────────────────────────────────
  useEffect(() => {
    const map   = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    if (!trace.length) return

    for (let i = 0; i < trace.length - 1; i++) {
      const a = trace[i], b = trace[i + 1]
      L.polyline([[a.lat, a.lon], [b.lat, b.lon]], {
        color:   speedColor((a.speed_kmh + b.speed_kmh) / 2),
        weight:  3,
        opacity: 0.9,
      }).addTo(layer)
    }

    const first = trace[0]
    const last  = trace[trace.length - 1]
    L.circleMarker([first.lat, first.lon], { radius: 5, color: '#22c55e', fillOpacity: 1 })
      .bindTooltip('Start').addTo(layer)
    L.circleMarker([last.lat, last.lon], { radius: 5, color: '#ef4444', fillOpacity: 1 })
      .bindTooltip('Finish').addTo(layer)

    const bounds = L.latLngBounds(trace.map(p => [p.lat, p.lon] as L.LatLngTuple))
    map.fitBounds(bounds, { padding: [20, 20] })
  }, [trace])

  // ── Lejátszási pozíció marker ─────────────────────────────────────────────
  useEffect(() => {
    const layer = playheadLayerRef.current
    if (!layer) return
    layer.clearLayers()
    if (playheadIdx == null || playheadIdx < 0 || !trace[playheadIdx]) return
    const pt = trace[playheadIdx]
    L.circleMarker([pt.lat, pt.lon], {
      radius:      8,
      color:       '#f97316',
      fillColor:   '#f97316',
      fillOpacity: 0.9,
      weight:      2,
    }).addTo(layer)
  }, [playheadIdx, trace])

  // ── Cleanup ───────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ height, borderRadius: 8, overflow: 'hidden' }}
      className="bg-[#1a1d26]"
    />
  )
}
