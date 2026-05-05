import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getTracks, deleteTrack, getTrackFirmwareJsonUrl } from '@/api/client'
import type { TrackListItem } from '@/api/types'
import { fmtDistance } from '@/utils/format'

export default function TracksPage() {
  const [tracks,  setTracks]  = useState<TrackListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    getTracks().then(setTracks).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    if (!confirm('Delete this track?')) return
    await deleteTrack(id)
    load()
  }

  const trackTypeLabel = (type: string) =>
    type === 'stage' ? 'Stage' : 'Circuit'

  const trackTypeBadge = (type: string) =>
    type === 'stage'
      ? 'bg-blue-900/40 text-blue-300 border border-blue-700/40'
      : 'bg-orange-900/40 text-orange-300 border border-orange-700/40'

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <div>
          <h1 className="text-lg font-semibold text-white">Track Explorer</h1>
          <p className="text-xs text-gray-500 mt-0.5">{tracks.length} tracks saved</p>
        </div>
        <button
          onClick={() => navigate('/tracks/new')}
          className="text-xs px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-500 text-white transition-colors"
        >
          + New Track
        </button>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {loading ? (
          <div className="text-gray-500 text-sm py-8 text-center">Loading tracks…</div>
        ) : tracks.length === 0 ? (
          <div className="text-gray-600 text-sm py-16 text-center">
            No tracks yet. Add a track or load demo data on the Sessions page.
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {tracks.map(t => (
              <div
                key={t.id}
                onClick={() => navigate(`/tracks/${t.id}`)}
                className="bg-[#1a1d26] border border-gray-800 rounded-lg p-4 cursor-pointer hover:border-gray-600 transition-colors group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-white group-hover:text-orange-300 transition-colors">
                    {t.name}
                  </h3>
                  <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-all">
                    <a
                      href={getTrackFirmwareJsonUrl(t.id)}
                      download
                      onClick={e => e.stopPropagation()}
                      className="text-gray-600 hover:text-blue-400 text-xs"
                      title="Board track.json letöltése"
                    >
                      ↓ JSON
                    </a>
                    <button
                      onClick={e => handleDelete(e, t.id)}
                      className="text-gray-600 hover:text-red-400 text-xs"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${trackTypeBadge(t.track_type)}`}>
                    {trackTypeLabel(t.track_type)}
                  </span>
                  {t.country && (
                    <span className="text-xs text-gray-500">{t.country}</span>
                  )}
                </div>

                <div className="flex justify-between text-xs text-gray-500">
                  <span>{fmtDistance(t.length_m)}</span>
                  <span>{t.sectors_count} sectors</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
