import type { LapAnalysisRow } from '@/api/types'
import { fmtMs, fmtDelta, deltaClass } from '@/utils/format'

interface Props {
  laps: LapAnalysisRow[]
  selectedLapNumber?: number
  onSelect?: (lapNumber: number) => void
}

export default function LapTable({ laps, selectedLapNumber, onSelect }: Props) {
  // Sector names from first lap
  const sectorNames = laps[0]?.sector_times.map(s => s.name) ?? []

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
            <th className="text-left px-3 py-2 w-10">#</th>
            <th className="text-right px-3 py-2">Lap Time</th>
            <th className="text-right px-3 py-2">Delta</th>
            {sectorNames.map(s => (
              <th key={s} className="text-right px-3 py-2">{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {laps.map(lap => (
            <tr
              key={lap.lap_number}
              onClick={() => onSelect?.(lap.lap_number)}
              className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
                lap.is_best
                  ? 'bg-purple-900/20'
                  : selectedLapNumber === lap.lap_number
                  ? 'bg-orange-500/10'
                  : 'hover:bg-gray-800/40'
              }`}
            >
              <td className="px-3 py-2 text-gray-500">
                {lap.lap_number}
                {lap.is_best && (
                  <span className="ml-1 text-purple-400 text-xs">★</span>
                )}
              </td>
              <td className={`px-3 py-2 font-mono text-right ${lap.is_best ? 'text-purple-300 font-semibold' : 'text-gray-200'}`}>
                {fmtMs(lap.lap_time_ms)}
              </td>
              <td className={`px-3 py-2 font-mono text-right text-xs ${deltaClass(lap.delta_ms)}`}>
                {lap.is_best ? '—' : fmtDelta(lap.delta_ms)}
              </td>
              {lap.sector_times.map(st => (
                <td key={st.name} className="px-3 py-2 font-mono text-right text-xs text-gray-400">
                  {fmtMs(st.time_ms)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
