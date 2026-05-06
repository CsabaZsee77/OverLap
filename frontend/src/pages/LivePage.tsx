import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getLiveDevices, getLiveState } from '@/api/client'
import type { LiveDevice, LiveState } from '@/api/client'

const POLL_MS = 2000

function speedColor(kmh: number): string {
  const t = Math.min(kmh / 140, 1)
  if (t < 0.5) {
    const s = t * 2
    return `rgb(${Math.round(50 + 205 * s)},${Math.round(200)},${Math.round(255 - 225 * s)})`
  }
  const s = (t - 0.5) * 2
  return `rgb(255,${Math.round(200 - 160 * s)},${Math.round(30 - 30 * s)})`
}

const TILES = {
  dark: {
    url:  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 20 },
  },
  satellite: {
    url:  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    opts: { maxZoom: 19 },
  },
}

export default function LivePage() {
  const [devices,   setDevices]   = useState<LiveDevice[]>([])
  const [selected,  setSelected]  = useState<string | null>(null)
  const [liveState, setLiveState] = useState<LiveState | null>(null)
  const [tileStyle, setTileStyle] = useState<'dark' | 'satellite'>('dark')

  const containerRef  = useRef<HTMLDivElement>(null)
  const mapRef        = useRef<L.Map | null>(null)
  const traceLayerRef = useRef<L.LayerGroup | null>(null)
  const headLayerRef  = useRef<L.LayerGroup | null>(null)
  const darkTileRef   = useRef<L.TileLayer | null>(null)
  const satTileRef    = useRef<L.TileLayer | null>(null)

  // Térkép init
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = L.map(containerRef.current, { attributionControl: false, zoomControl: true })

    const dark = L.tileLayer(TILES.dark.url, TILES.dark.opts).addTo(map)
    const sat  = L.tileLayer(TILES.satellite.url, TILES.satellite.opts)
    darkTileRef.current = dark
    satTileRef.current  = sat

    traceLayerRef.current = L.layerGroup().addTo(map)
    headLayerRef.current  = L.layerGroup().addTo(map)
    map.setView([47.089, 19.283], 15)
    mapRef.current = map

    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Rétegváltás
  useEffect(() => {
    const map  = mapRef.current
    const dark = darkTileRef.current
    const sat  = satTileRef.current
    if (!map || !dark || !sat) return
    if (tileStyle === 'dark') {
      map.removeLayer(sat)
      if (!map.hasLayer(dark)) dark.addTo(map)
    } else {
      map.removeLayer(dark)
      if (!map.hasLayer(sat)) sat.addTo(map)
    }
  }, [tileStyle])

  // Eszközlista polling
  useEffect(() => {
    const poll = async () => {
      try {
        const devs = await getLiveDevices()
        setDevices(devs)
        if (devs.length === 1 && !selected) setSelected(devs[0].device_id)
      } catch { /* silent */ }
    }
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => clearInterval(id)
  }, [selected])

  // Live state polling
  useEffect(() => {
    if (!selected) return
    const poll = async () => {
      try { setLiveState(await getLiveState(selected)) }
      catch { /* silent */ }
    }
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => clearInterval(id)
  }, [selected])

  // Térkép frissítés
  useEffect(() => {
    const map   = mapRef.current
    const trace = traceLayerRef.current
    const head  = headLayerRef.current
    if (!map || !trace || !head || !liveState?.points.length) return

    trace.clearLayers()
    head.clearLayers()

    const pts = liveState.points
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1]
      L.polyline([[a.lat, a.lon], [b.lat, b.lon]], {
        color: speedColor(a.speed_kmh), weight: 4, opacity: 0.9,
      }).addTo(trace)
    }

    const last = pts[pts.length - 1]
    L.circleMarker([last.lat, last.lon], {
      radius: 8, color: '#f97316', fillColor: '#f97316', fillOpacity: 1, weight: 2,
    }).addTo(head)

    if (pts.length < 5) map.setView([last.lat, last.lon], 17)
  }, [liveState])

  const last  = liveState?.points?.[liveState.points.length - 1]
  const stale = liveState?.stale ?? true

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-white">Live GPS</h1>
          <p className="text-xs text-gray-500">Valós idejű helyzet · frissül 2 s-onként</p>
        </div>
        <div className="flex items-center gap-2">
          {devices.length === 0
            ? <span className="text-xs text-gray-600">Nincs aktív eszköz</span>
            : devices.map(d => (
              <button key={d.device_id} onClick={() => setSelected(d.device_id)}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  selected === d.device_id
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:text-gray-200'
                }`}>
                {d.device_id.replace('mm_', '')}
              </button>
            ))
          }
        </div>
      </div>

      <div className="flex-1 relative overflow-hidden">
        <div ref={containerRef} className="w-full h-full bg-[#0d0f18]" />

        {/* Státusz */}
        <div className="absolute top-3 left-3 z-[1000]">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium ${
            stale ? 'bg-gray-900/90 text-gray-500' : 'bg-green-900/90 text-green-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${stale ? 'bg-gray-600' : 'bg-green-400 animate-pulse'}`} />
            {stale ? 'Nincs jel' : 'Élő'}
          </div>
        </div>

        {/* Rétegváltó */}
        <button
          onClick={() => setTileStyle(s => s === 'dark' ? 'satellite' : 'dark')}
          className="absolute top-3 right-3 z-[1000] bg-gray-900/85 border border-gray-700 rounded px-2.5 py-1 text-xs text-gray-300 hover:text-white transition-colors backdrop-blur-sm shadow-lg"
        >
          {tileStyle === 'dark' ? '🛰 Műhold' : '🌑 Térkép'}
        </button>

        {/* Telemetria overlay */}
        {last && !stale && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] flex gap-3">
            <div className="bg-black/80 rounded-lg px-4 py-2 text-center">
              <div className="text-xs text-gray-500">Sebesség</div>
              <div className="text-2xl font-mono font-bold text-orange-400">
                {last.speed_kmh.toFixed(0)}<span className="text-sm text-gray-500 ml-1">km/h</span>
              </div>
            </div>
            {last.lean_deg != null && (
              <div className="bg-black/80 rounded-lg px-4 py-2 text-center">
                <div className="text-xs text-gray-500">Dőlés</div>
                <div className="text-2xl font-mono font-bold text-cyan-400">
                  {last.lean_deg >= 0 ? '+' : ''}{last.lean_deg.toFixed(1)}<span className="text-sm text-gray-500 ml-1">°</span>
                </div>
              </div>
            )}
            {last.lat_g != null && (
              <div className="bg-black/80 rounded-lg px-4 py-2 text-center">
                <div className="text-xs text-gray-500">Lat G</div>
                <div className="text-2xl font-mono font-bold text-purple-400">
                  {last.lat_g.toFixed(2)}<span className="text-sm text-gray-500 ml-1">G</span>
                </div>
              </div>
            )}
            {liveState?.lap_number != null && (
              <div className="bg-black/80 rounded-lg px-4 py-2 text-center">
                <div className="text-xs text-gray-500">Kör</div>
                <div className="text-2xl font-mono font-bold text-white">{liveState.lap_number}</div>
              </div>
            )}
          </div>
        )}

        {/* Placeholder */}
        {!selected && (
          <div className="absolute inset-0 flex items-center justify-center z-[500]">
            <div className="bg-[#1a1d26]/90 rounded-xl px-8 py-6 text-center">
              <div className="text-3xl mb-2">📡</div>
              <div className="text-gray-400 text-sm">Várakozás az eszközre…</div>
              <div className="text-gray-600 text-xs mt-1">A board 2 s-onként küld GPS adatot</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
