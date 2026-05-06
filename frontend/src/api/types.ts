// types.ts — API response types matching backend schemas

export type TrackType = 'circuit' | 'stage'

export interface GpsPoint {
  lat: number
  lon: number
  speed_kmh: number
  ts_ms: number
  lean?:       number   // dőlésszög fokban (lap.py)
  lean_deg?:   number   // alternatív (gps_task replace)
  lat_g?:      number   // lateral G
  lon_g?:      number   // longitudinal G
  kamm_angle?: number   // irányvektor szöge
}

export type TraceMetric = 'speed' | 'lean' | 'lat_g' | 'lon_g'

export interface SectorTime {
  name: string
  time_ms: number
}

export interface FinishLine {
  lat1: number; lon1: number
  lat2: number; lon2: number
}

export interface StartLine {
  lat1: number; lon1: number
  lat2: number; lon2: number
}

export interface Sector {
  name: string
  lat1: number; lon1: number
  lat2: number; lon2: number
}

export interface CenterlinePoint {
  lat: number
  lon: number
}

// ── Tracks ──────────────────────────────────────────────────────────────────

export interface TrackListItem {
  id: number
  name: string
  country: string | null
  length_m: number | null
  sectors_count: number
  track_type: TrackType
}

export interface TrackResponse {
  id: number
  name: string
  country: string | null
  created_at: string
  track_type: TrackType
  finish_line: FinishLine
  start_line: StartLine | null
  sectors: Sector[]
  centerline: CenterlinePoint[]
  length_m: number
}

export interface TrackCreate {
  name: string
  country: string
  track_type: TrackType
  finish_line: FinishLine
  start_line?: StartLine | null
  sectors: Sector[]
  centerline: CenterlinePoint[]
}

// ── Sessions ─────────────────────────────────────────────────────────────────

export interface LapResponse {
  id: number
  lap_number: number
  lap_time_ms: number
  is_valid: boolean
  sector_times: SectorTime[]
  has_trace: boolean
}

export interface SessionResponse {
  id: number
  device_id: string
  rider_name: string | null
  track_id: number | null
  started_at: string
  ended_at: string | null
  lap_count: number
  best_lap_ms: number | null
  laps: LapResponse[]
}

export interface SessionListItem {
  id: number
  device_id: string
  rider_name: string | null
  track_id: number | null
  track_name: string | null
  started_at: string
  lap_count: number
  best_lap_ms: number | null
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export interface SectorBest {
  name: string
  time_ms: number
  lap_number: number
}

export interface LapAnalysisRow {
  lap_number:     number
  lap_time_ms:    number
  is_best:        boolean
  delta_ms:       number | null
  sector_times:   SectorTime[]
  max_lean_right:  number | null
  max_lean_left:   number | null
  peak_kamm_g:     number | null
  peak_kamm_angle: number | null
}

export interface SessionAnalysis {
  session_id: number
  track_name: string | null
  lap_count: number
  best_lap_ms: number | null
  theoretical_best_ms: number | null
  consistency_score: number | null
  sector_bests: SectorBest[]
  laps: LapAnalysisRow[]
}

export interface SpeedPoint {
  s: number
  speed_kmh: number
}

export interface LapDetail {
  lap_id: number
  lap_number: number
  lap_time_ms: number
  gps_trace: GpsPoint[]
  speed_curve: SpeedPoint[]
}

export interface LapDeltaPoint {
  s: number
  delta_ms: number
}

export interface LapCompare {
  lap_a_id: number
  lap_b_id: number
  delta_curve: LapDeltaPoint[]
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

export interface LeaderboardEntry {
  rank: number
  device_id: string
  rider_name: string
  session_id: number
  best_lap_ms: number
  best_lap_fmt: string
}

export interface Leaderboard {
  track_id: number
  track_name: string
  period: string
  entries: LeaderboardEntry[]
}
