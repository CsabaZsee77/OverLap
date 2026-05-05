import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSessions, seedDemoData } from '@/api/client'
import type { SessionListItem } from '@/api/types'
import { fmtMs, fmtDateTime } from '@/utils/format'

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [loading,  setLoading]  = useState(true)
  const [seeding,  setSeeding]  = useState(false)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    getSessions({ limit: 100 })
      .then(setSessions)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSeed = async () => {
    setSeeding(true)
    try {
      const res = await seedDemoData()
      if (res.status === 'skipped') {
        alert('Demo data already exists.')
      } else {
        load()
      }
    } catch (e) {
      alert('Seed failed — is the backend running?')
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <div>
          <h1 className="text-lg font-semibold text-white">Sessions</h1>
          <p className="text-xs text-gray-500 mt-0.5">{sessions.length} recorded sessions</p>
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="text-xs px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white transition-colors"
        >
          {seeding ? 'Loading…' : '+ Load Demo Data'}
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {loading ? (
          <div className="text-gray-500 text-sm py-8 text-center">Loading sessions…</div>
        ) : sessions.length === 0 ? (
          <div className="text-gray-600 text-sm py-16 text-center">
            No sessions yet.<br />
            <span className="text-gray-700">Click "Load Demo Data" to add sample data.</span>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left px-3 py-2">Track</th>
                <th className="text-left px-3 py-2">Rider</th>
                <th className="text-left px-3 py-2">Device</th>
                <th className="text-left px-3 py-2">Date</th>
                <th className="text-right px-3 py-2">Laps</th>
                <th className="text-right px-3 py-2">Best Lap</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr
                  key={s.id}
                  onClick={() => navigate(`/session/${s.id}`)}
                  className="border-b border-gray-800/40 hover:bg-gray-800/40 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2.5 text-white font-medium">
                    {s.track_name ?? <span className="text-gray-600">No track</span>}
                  </td>
                  <td className="px-3 py-2.5 text-gray-300">{s.rider_name ?? s.device_id}</td>
                  <td className="px-3 py-2.5 text-gray-500 font-mono text-xs">{s.device_id}</td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs">{fmtDateTime(s.started_at)}</td>
                  <td className="px-3 py-2.5 text-right text-gray-300">{s.lap_count}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-orange-300">
                    {fmtMs(s.best_lap_ms)}
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
