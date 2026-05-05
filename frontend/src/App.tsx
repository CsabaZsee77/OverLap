import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar              from '@/components/Sidebar'
import SessionsPage         from '@/pages/SessionsPage'
import SessionAnalysisPage  from '@/pages/SessionAnalysisPage'
import TracksPage           from '@/pages/TracksPage'
import TrackEditorPage      from '@/pages/TrackEditorPage'
import LeaderboardPage      from '@/pages/LeaderboardPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-[#0d0e12] text-gray-200 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden flex flex-col">
          <Routes>
            <Route path="/"                  element={<SessionsPage />} />
            <Route path="/session/:id"       element={<SessionAnalysisPage />} />
            <Route path="/tracks"            element={<TracksPage />} />
            <Route path="/tracks/new"        element={<TrackEditorPage />} />
            <Route path="/tracks/:id"        element={<TrackEditorPage />} />
            <Route path="/leaderboard"       element={<LeaderboardPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
