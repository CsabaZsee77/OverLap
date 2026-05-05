import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts'
import type { LapDeltaPoint } from '@/api/types'

interface Props { data: LapDeltaPoint[] }

interface TooltipProps { active?: boolean; payload?: { payload: LapDeltaPoint }[] }
const CustomTooltip = ({ active, payload }: TooltipProps) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as LapDeltaPoint
  const ms = d.delta_ms
  const color = ms < 0 ? '#4ade80' : ms > 0 ? '#f87171' : '#9ca3af'
  return (
    <div className="bg-[#1e2130] border border-gray-700 rounded px-2 py-1 text-xs">
      <div className="text-gray-400">s = {(d.s * 100).toFixed(1)}%</div>
      <div className="font-mono" style={{ color }}>
        {ms > 0 ? '+' : ''}{(ms / 1000).toFixed(3)}s
      </div>
    </div>
  )
}

export default function DeltaChart({ data }: Props) {
  if (!data.length) return (
    <div className="h-32 flex items-center justify-center text-gray-600 text-sm">
      No delta data
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={120}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 38 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="s"
          tickFormatter={v => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: '#6b7280', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={v => `${(v / 1000).toFixed(2)}s`}
          tick={{ fill: '#6b7280', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 2" />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="delta_ms"
          stroke="#818cf8"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
