import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import type { SpeedPoint } from '@/api/types'

interface Props {
  data: SpeedPoint[]
  color?: string
}

interface TooltipProps { active?: boolean; payload?: { payload: SpeedPoint }[] }
const CustomTooltip = ({ active, payload }: TooltipProps) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as SpeedPoint
  return (
    <div className="bg-[#1e2130] border border-gray-700 rounded px-2 py-1 text-xs">
      <div className="text-gray-400">s = {(d.s * 100).toFixed(1)}%</div>
      <div className="text-orange-300 font-mono">{d.speed_kmh.toFixed(1)} km/h</div>
    </div>
  )
}

export default function SpeedChart({ data, color = '#f97316' }: Props) {
  if (!data.length) return (
    <div className="h-32 flex items-center justify-center text-gray-600 text-sm">
      No speed data
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={130}>
      <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 32 }}>
        <defs>
          <linearGradient id="speedGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="s"
          tickFormatter={v => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: '#6b7280', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#6b7280', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          unit=" km/h"
          width={52}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="speed_kmh"
          stroke={color}
          strokeWidth={2}
          fill="url(#speedGrad)"
          dot={false}
          activeDot={{ r: 3, fill: color }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
