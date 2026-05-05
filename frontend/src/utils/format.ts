// format.ts — number / time formatting helpers

/** 63400 ms  →  "1:03.400" */
export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '--:--.---'
  const sign = ms < 0 ? '-' : ''
  const abs  = Math.abs(ms)
  const min  = Math.floor(abs / 60_000)
  const sec  = Math.floor((abs % 60_000) / 1000)
  const milli = abs % 1000
  return `${sign}${min}:${String(sec).padStart(2, '0')}.${String(milli).padStart(3, '0')}`
}

/** delta ms → "+1.234" or "-0.456" */
export function fmtDelta(ms: number | null | undefined): string {
  if (ms == null) return ''
  const sign = ms > 0 ? '+' : ''
  const abs  = Math.abs(ms)
  const sec  = (abs / 1000).toFixed(3)
  return `${sign}${ms < 0 ? '-' : ''}${sec}`
}

/** delta color class */
export function deltaClass(ms: number | null | undefined): string {
  if (ms == null) return 'text-gray-400'
  if (ms < 0)    return 'text-green-400'
  if (ms > 0)    return 'text-red-400'
  return 'text-gray-400'
}

/** 1050.0 → "1.05 km" or "850 m" */
export function fmtDistance(m: number | null | undefined): string {
  if (m == null) return '–'
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`
}

/** ISO datetime → "2025-04-24 10:30" */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '–'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Consistency score color */
export function consistencyColor(score: number | null | undefined): string {
  if (score == null) return '#6b7280'
  if (score >= 90)   return '#22c55e'
  if (score >= 75)   return '#eab308'
  return '#ef4444'
}
