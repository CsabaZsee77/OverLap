import { useEffect, useState } from 'react'
import { getTracks, getLeaderboard } from '@/api/client'
import type { TrackListItem, Leaderboard } from '@/api/types'

const PERIODS = [
  { value: 'all',   label: 'All Time' },
  { value: 'month', label: 'Month' },
  { value: 'week',  label: 'Week' },
  { value: 'today', label: 'Today' },
]

export default function LeaderboardPage() {
  const [tracks,      setTracks]      = useState<TrackListItem[]>([])
  const [selTrack,    setSelTrack]    = useState<number | null>(null)
  const [period,      setPeriod]      = useState('all')
  const [leaderboard, setLeaderboard] = useState<Leaderboard | null>(null)
  const [loading,     setLoading]     = useState(false)

  useEffect(() => {
    getTracks().then(ts => {
      setTracks(ts)
      if (ts.length) setSelTrack(ts[0].id)
    })
  }, [])

  useEffect(() => {
    if (!selTrack) return
    setLoading(true)
    getLeaderboard(selTrack, period)
      .then(setLeaderboard)
      .finally(() => setLoading(false))
  }, [selTrack, period])

  const medalColor = (rank: number) => {
    if (rank === 1) return 'text-yellow-400'
    if (rank === 2) return 'text-gray-300'
    if (rank === 3) return 'text-amber-600'
    return 'text-gray-600'
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <div>
          <h1 className="text-lg font-semibold text-white">Leaderboard</h1>
          <p className="text-xs text-gray-500 mt-0.5">Best lap times by track</p>
        </div>
      </div>

      <div className="flex gap-4 px-6 py-3 border-b border-gray-800">
        {/* Track selector */}
        <select
          value={selTrack ?? ''}
          onChange={e => setSelTrack(Number(e.target.value))}
          className="bg-[#1a1d26] border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500"
        >
          {tracks.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>

        {/* Period */}
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                period === p.value
                  ? 'bg-orange-500/20 border-orange-500 text-orange-300'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {loading ? (
          <div className="text-gray-500 text-sm py-8 text-center">Loading…</div>
        ) : !leaderboard || leaderboard.entries.length === 0 ? (
          <div className="text-gray-600 text-sm py-16 text-center">No data for this period.</div>
        ) : (
          <table className="w-full text-sm max-w-2xl">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left px-3 py-2 w-10">#</th>
                <th className="text-left px-3 py-2">Rider</th>
                <th className="text-left px-3 py-2">Device</th>
                <th className="text-right px-3 py-2">Best Lap</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.entries.map(e => (
                <tr key={e.rank} className="border-b border-gray-800/40 hover:bg-gray-800/30">
                  <td className={`px-3 py-2.5 font-bold text-lg ${medalColor(e.rank)}`}>
                    {e.rank <= 3 ? ['🥇','🥈','🥉'][e.rank - 1] : e.rank}
                  </td>
                  <td className="px-3 py-2.5 text-white font-medium">{e.rider_name}</td>
                  <td className="px-3 py-2.5 text-gray-500 font-mono text-xs">{e.device_id}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-orange-300 font-semibold">
                    {e.best_lap_fmt}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
