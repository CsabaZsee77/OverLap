import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar              from '@/components/Sidebar'
import SessionsPage         from '@/pages/SessionsPage'
import SessionAnalysisPage  from '@/pages/SessionAnalysisPage'
import TracksPage           from '@/pages/TracksPage'
import TrackEditorPage      from '@/pages/TrackEditorPage'
import LeaderboardPage      from '@/pages/LeaderboardPage'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-[#0d0e12] text-gray-200 overflow-hidden">

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="md:hidden fixed inset-0 bg-black/60 z-40"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar — mobilon fix overlay, desktopon normál */}
        <div className={`
          fixed md:relative z-50 md:z-auto h-full
          transition-transform duration-200
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}>
          <Sidebar onClose={() => setSidebarOpen(false)} />
        </div>

        {/* Fő tartalom */}
        <main className="flex-1 overflow-hidden flex flex-col min-w-0">
          {/* Mobil fejléc */}
          <div className="md:hidden flex items-center gap-3 px-4 py-3 bg-[#13151e] border-b border-gray-800 shrink-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-gray-400 hover:text-white text-xl leading-none"
              aria-label="Menü"
            >
              ☰
            </button>
            <span className="text-orange-400 font-bold tracking-widest text-sm">OverLAP</span>
          </div>

          <div className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/"                  element={<SessionsPage />} />
              <Route path="/session/:id"       element={<SessionAnalysisPage />} />
              <Route path="/tracks"            element={<TracksPage />} />
              <Route path="/tracks/new"        element={<TrackEditorPage />} />
              <Route path="/tracks/:id"        element={<TrackEditorPage />} />
              <Route path="/leaderboard"       element={<LeaderboardPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
