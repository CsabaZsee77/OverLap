// client.ts — Axios-based API client for MotoMeter backend
import axios from 'axios'
import type {
  TrackListItem, TrackResponse, TrackCreate,
  SessionListItem, SessionResponse,
  SessionAnalysis, LapDetail, LapCompare,
  Leaderboard,
} from './types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10_000,
})

// ── Tracks ───────────────────────────────────────────────────────────────────

export const getTracks = () =>
  api.get<TrackListItem[]>('/tracks/').then(r => r.data)

export const getTrack = (id: number) =>
  api.get<TrackResponse>(`/tracks/${id}`).then(r => r.data)

export const createTrack = (payload: TrackCreate) =>
  api.post<TrackResponse>('/tracks/', payload).then(r => r.data)

export const updateTrack = (id: number, payload: TrackCreate) =>
  api.put<TrackResponse>(`/tracks/${id}`, payload).then(r => r.data)

export const deleteTrack = (id: number) =>
  api.delete(`/tracks/${id}`)

export const getTrackCurvature = (id: number) =>
  api.get<{ track_id: number; curvature: { s: number; curvature: number }[] }>(
    `/tracks/${id}/curvature`
  ).then(r => r.data)

// ── Sessions ─────────────────────────────────────────────────────────────────

export const getSessions = (params?: { track_id?: number; device_id?: string; limit?: number }) =>
  api.get<SessionListItem[]>('/sessions/', { params }).then(r => r.data)

export const getSession = (id: number) =>
  api.get<SessionResponse>(`/sessions/${id}`).then(r => r.data)

export const deleteSession = (id: number) =>
  api.delete(`/sessions/${id}`)

export const getLapTrace = (sessionId: number, lapId: number) =>
  api.get(`/sessions/${sessionId}/laps/${lapId}/trace`).then(r => r.data)

// ── Analysis ─────────────────────────────────────────────────────────────────

export const getSessionAnalysis = (sessionId: number) =>
  api.get<SessionAnalysis>(`/analysis/session/${sessionId}`).then(r => r.data)

export const getLapDetail = (lapId: number) =>
  api.get<LapDetail>(`/analysis/lap/${lapId}`).then(r => r.data)

export const compareLaps = (lapA: number, lapB: number) =>
  api.get<LapCompare>('/analysis/compare', { params: { lap_a: lapA, lap_b: lapB } }).then(r => r.data)

export const getLeaderboard = (trackId: number, period = 'all', limit = 20) =>
  api.get<Leaderboard>(`/analysis/leaderboard/${trackId}`, {
    params: { period, limit },
  }).then(r => r.data)

export const getTrackFirmwareJsonUrl = (id: number): string =>
  `/api/tracks/${id}/firmware-json`

// ── Live GPS ─────────────────────────────────────────────────────────────────

export interface LiveDevice {
  device_id:   string
  lap_number:  number | null
  updated_at:  number
  point_count: number
}

export interface LiveState {
  device_id:  string
  lap_number: number | null
  points:     { lat: number; lon: number; speed_kmh: number; ts_ms: number; lean_deg?: number; lat_g?: number; lon_g?: number }[]
  updated_at: number
  stale:      boolean
}

export const getLiveDevices = () =>
  api.get<LiveDevice[]>('/live/').then(r => r.data)

export const getLiveState = (deviceId: string) =>
  api.get<LiveState>(`/live/${deviceId}`).then(r => r.data)

// ── Dev ───────────────────────────────────────────────────────────────────────

export const seedDemoData = () =>
  api.post('/dev/seed').then(r => r.data)

export const healthCheck = () =>
  api.get<{ status: string; service: string }>('/health').then(r => r.data)
