interface Props {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  color?: string
}

export default function StatCard({ label, value, sub, accent, color }: Props) {
  return (
    <div className={`rounded-lg px-4 py-3 ${accent ? 'bg-orange-500/10 border border-orange-500/30' : 'bg-[#1a1d26] border border-gray-800'}`}>
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div
        className="font-mono text-xl font-semibold leading-none"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}
