import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getSessionAnalysis, getLapDetail, compareLaps, getSession,
} from '@/api/client'
import type {
  SessionAnalysis, LapDetail, LapCompare, LapAnalysisRow, TraceMetric,
} from '@/api/types'
import { fmtMs, fmtDelta, deltaClass, consistencyColor } from '@/utils/format'
import StatCard    from '@/components/StatCard'
import LapTable    from '@/components/LapTable'
import SpeedChart  from '@/components/SpeedChart'
import DeltaChart  from '@/components/DeltaChart'
import TraceMap    from '@/components/TraceMap'
import KammCircle  from '@/components/KammCircle'
import LeanHorizon from '@/components/LeanHorizon'

export default function SessionAnalysisPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate  = useNavigate()

  const [analysis,  setAnalysis]  = useState<SessionAnalysis | null>(null)
  const [lapDetail, setLapDetail] = useState<LapDetail | null>(null)
  const [compare,   setCompare]   = useState<LapCompare | null>(null)
  const [selLap,    setSelLap]    = useState<LapAnalysisRow | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)

  // ── Replay állapot ────────────────────────────────────────────────────────
  const [playing,     setPlaying]     = useState(false)
  const [playheadMs,  setPlayheadMs]  = useState(0)
  const [playSpeed,   setPlaySpeed]   = useState(5)
  const [metric,      setMetric]      = useState<TraceMetric>('speed')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const selectLap = useCallback(async (
    currentAnalysis: SessionAnalysis,
    row: LapAnalysisRow
  ) => {
    setSelLap(row)
    try {
      const session = await getSession(sessionId)
      const lap = session.laps.find(l => l.lap_number === row.lap_number)
      if (!lap) return

      const detail = await getLapDetail(lap.id)
      setLapDetail(detail)

      const bestRow = currentAnalysis.laps.find(l => l.is_best)
      if (bestRow && bestRow.lap_number !== row.lap_number) {
        const bestLap = session.laps.find(l => l.lap_number === bestRow.lap_number)
        if (bestLap) {
          const cmp = await compareLaps(bestLap.id, lap.id)
          setCompare(cmp)
        }
      } else {
        setCompare(null)
      }
    } catch (e) {
      console.error('Failed to load lap detail', e)
    }
  }, [sessionId])

  // ── Lejátszási pozíció kiszámítása (bináris keresés) ─────────────────────
  const playheadIdx = useMemo(() => {
    const t = lapDetail?.gps_trace
    if (!t?.length) return 0
    let lo = 0, hi = t.length - 1
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1
      if (t[mid].ts_ms <= playheadMs) lo = mid
      else hi = mid - 1
    }
    return lo
  }, [lapDetail?.gps_trace, playheadMs])

  const playMaxMs = lapDetail?.gps_trace?.length
    ? lapDetail.gps_trace[lapDetail.gps_trace.length - 1].ts_ms
    : 0

  const currentSpeed = lapDetail?.gps_trace[playheadIdx]?.speed_kmh ?? 0

  // ── Lejátszási animáció ───────────────────────────────────────────────────
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (!playing || !lapDetail?.gps_trace?.length) return
    intervalRef.current = setInterval(() => {
      setPlayheadMs(prev => {
        const next = prev + 100 * playSpeed
        if (next >= playMaxMs) {
          setPlaying(false)
          return playMaxMs
        }
        return next
      })
    }, 100)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [playing, playSpeed, lapDetail, playMaxMs])

  // Kör váltáskor reset
  useEffect(() => {
    setPlaying(false)
    setPlayheadMs(0)
  }, [lapDetail])

  useEffect(() => {
    setLoading(true)
    getSessionAnalysis(sessionId)
      .then((data: SessionAnalysis) => {
        setAnalysis(data)
        const best = data.laps.find((l: LapAnalysisRow) => l.is_best) ?? data.laps[0]
        if (best) selectLap(data, best)
      })
      .catch(() => setError('Session not found or backend unreachable.'))
      .finally(() => setLoading(false))
  }, [sessionId, selectLap])

  if (loading) return (
    <div className="flex-1 flex items-center justify-center text-gray-500">Loading…</div>
  )
  if (error || !analysis) return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3">
      <div className="text-red-400">{error ?? 'Unknown error'}</div>
      <button onClick={() => navigate('/')} className="text-sm text-gray-500 hover:text-gray-300">
        ← Back to sessions
      </button>
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-gray-800">
        <button onClick={() => navigate('/')} className="text-gray-500 hover:text-gray-300 text-sm">
          ← Sessions
        </button>
        <div>
          <h1 className="text-lg font-semibold text-white">
            {analysis.track_name ?? 'Unknown Track'}
          </h1>
          <p className="text-xs text-gray-500">Session #{sessionId} · {analysis.lap_count} valid laps</p>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6">
        {/* Stat cards */}
        <div className="grid grid-cols-4 gap-3">
          <StatCard
            label="Best Lap"
            value={fmtMs(analysis.best_lap_ms)}
            accent
          />
          <StatCard
            label="Theoretical Best"
            value={fmtMs(analysis.theoretical_best_ms)}
            sub={analysis.best_lap_ms != null && analysis.theoretical_best_ms != null
              ? `Δ ${fmtDelta(analysis.best_lap_ms - analysis.theoretical_best_ms)}`
              : undefined}
          />
          <StatCard
            label="Consistency"
            value={analysis.consistency_score != null
              ? `${analysis.consistency_score.toFixed(1)}%`
              : '–'}
            color={consistencyColor(analysis.consistency_score)}
          />
          <StatCard
            label="Laps"
            value={analysis.lap_count}
          />
        </div>

        {/* Sector bests */}
        {analysis.sector_bests.length > 0 && (
          <div>
            <h2 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Best Sector Times</h2>
            <div className="flex gap-2 flex-wrap">
              {analysis.sector_bests.map(sb => (
                <div key={sb.name} className="bg-[#1a1d26] border border-gray-800 rounded-lg px-3 py-2 text-center min-w-[90px]">
                  <div className="text-xs text-gray-500">{sb.name}</div>
                  <div className="font-mono text-sm text-purple-300">{fmtMs(sb.time_ms)}</div>
                  <div className="text-xs text-gray-600">Lap {sb.lap_number}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main area: map + charts + lap table */}
        <div className="grid grid-cols-[1fr_1fr] gap-4">
          {/* Left column */}
          <div className="space-y-4">
            {/* GPS trace map */}
            <div className="bg-[#1a1d26] border border-gray-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">GPS Trace</span>
                  {selLap && (
                    <span className="text-xs text-gray-400">· Lap {selLap.lap_number} · {fmtMs(selLap.lap_time_ms)}</span>
                  )}
                </div>
                {/* Metrika választó */}
                <div className="flex gap-1">
                  {(['speed', 'lean', 'lat_g', 'lon_g'] as TraceMetric[]).map(m => (
                    <button key={m} onClick={() => setMetric(m)}
                      className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                        metric === m
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-800 text-gray-500 hover:text-gray-300'
                      }`}>
                      {m === 'speed' ? 'km/h' : m === 'lean' ? 'dőlés' : m === 'lat_g' ? 'lat G' : 'lon G'}
                    </button>
                  ))}
                </div>
              </div>
              <TraceMap
                trace={lapDetail?.gps_trace ?? []}
                height={260}
                playheadIdx={playing || playheadMs > 0 ? playheadIdx : undefined}
                metric={metric}
              />

              {/* Replay vezérlők */}
              {(lapDetail?.gps_trace?.length ?? 0) > 0 && (
                <div className="px-4 py-3 border-t border-gray-800 space-y-2">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        if (playheadMs >= playMaxMs) setPlayheadMs(0)
                        setPlaying(p => !p)
                      }}
                      className="w-7 h-7 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-600 text-white text-sm transition-colors shrink-0"
                    >
                      {playing ? '⏸' : '▶'}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={playMaxMs}
                      value={playheadMs}
                      onChange={e => { setPlaying(false); setPlayheadMs(Number(e.target.value)) }}
                      className="flex-1 h-1 accent-orange-500 cursor-pointer"
                    />
                    <span className="text-xs font-mono text-gray-400 shrink-0 w-20 text-right">
                      {fmtMs(playheadMs)} / {fmtMs(playMaxMs)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-gray-600">Sebesség:</span>
                      {([1, 2, 5, 10] as const).map(s => (
                        <button
                          key={s}
                          onClick={() => setPlaySpeed(s)}
                          className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                            playSpeed === s
                              ? 'bg-orange-600 text-white'
                              : 'bg-gray-800 text-gray-500 hover:text-gray-300'
                          }`}
                        >
                          {s}×
                        </button>
                      ))}
                    </div>
                    {(playing || playheadMs > 0) && (
                      <div className="flex items-center gap-3 font-mono text-sm">
                        <span className="text-orange-400">{currentSpeed.toFixed(0)} km/h</span>
                        {lapDetail?.gps_trace[playheadIdx]?.lean != null && (
                          <span className="text-cyan-400">
                            {(lapDetail.gps_trace[playheadIdx].lean! >= 0 ? '+' : '')}
                            {lapDetail.gps_trace[playheadIdx].lean!.toFixed(1)}°
                          </span>
                        )}
                        {lapDetail?.gps_trace[playheadIdx]?.lat_g != null && (
                          <span className="text-purple-400">
                            {Math.abs(lapDetail.gps_trace[playheadIdx].lat_g!).toFixed(2)}G
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* IMU műszerek */}
            <div className="bg-[#1a1d26] border border-gray-800 rounded-lg">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500">
                IMU csúcsértékek
                {selLap && <span className="ml-1 text-gray-600">· Lap {selLap.lap_number}</span>}
              </div>
              <div className="flex items-center justify-around py-3 px-2">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] text-gray-600 uppercase tracking-wider">Kamm-kör</span>
                  <KammCircle
                    peakG={selLap?.peak_kamm_g ?? null}
                    peakAngle={selLap?.peak_kamm_angle ?? null}
                  />
                </div>
                <div className="w-px h-32 bg-gray-800" />
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[10px] text-gray-600 uppercase tracking-wider">Max dőlés</span>
                  <LeanHorizon
                    leanRight={selLap?.max_lean_right ?? null}
                    leanLeft={selLap?.max_lean_left ?? null}
                  />
                </div>
              </div>
            </div>

            {/* Speed curve */}
            <div className="bg-[#1a1d26] border border-gray-800 rounded-lg">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-800 text-xs text-gray-500">
                Speed Profile (s-coordinate)
              </div>
              <div className="p-3">
                <SpeedChart data={lapDetail?.speed_curve ?? []} />
              </div>
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-4">
            {/* Delta chart */}
            <div className="bg-[#1a1d26] border border-gray-800 rounded-lg">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500">
                Delta vs Best Lap
                {selLap && !selLap.is_best && (
                  <span className={`ml-2 font-mono ${deltaClass(selLap.delta_ms)}`}>
                    {fmtDelta(selLap.delta_ms)}s
                  </span>
                )}
              </div>
              <div className="p-3">
                {compare ? (
                  <DeltaChart data={compare.delta_curve} />
                ) : (
                  <div className="h-28 flex items-center justify-center text-gray-600 text-sm">
                    {selLap?.is_best ? 'This is the best lap' : 'Select a lap to compare'}
                  </div>
                )}
              </div>
            </div>

            {/* Lap table */}
            <div className="bg-[#1a1d26] border border-gray-800 rounded-lg">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500">
                Lap Times
              </div>
              <LapTable
                laps={analysis.laps}
                selectedLapNumber={selLap?.lap_number}
                onSelect={(num: number) => {
                  const row = analysis.laps.find((l: LapAnalysisRow) => l.lap_number === num)
                  if (row) selectLap(analysis, row)
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
