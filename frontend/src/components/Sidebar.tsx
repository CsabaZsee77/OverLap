import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/',            label: 'Sessions',       icon: '📋' },
  { to: '/live',        label: 'Live GPS',       icon: '📡' },
  { to: '/tracks',      label: 'Track Explorer', icon: '🗺️' },
  { to: '/leaderboard', label: 'Leaderboard',    icon: '🏆' },
]

interface Props {
  onClose?: () => void
}

export default function Sidebar({ onClose }: Props) {
  return (
    <aside className="w-52 h-full shrink-0 bg-[#13151e] border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-orange-500 font-bold text-lg tracking-widest">7A</span>
          <div>
            <div className="text-white font-semibold text-sm leading-none">TRACK ANALYZER</div>
            <div className="text-gray-500 text-xs mt-0.5">OverLAP v1.2</div>
          </div>
        </div>
        {/* Bezárás gomb — csak mobilon látható */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden text-gray-500 hover:text-white text-lg leading-none ml-2"
            aria-label="Bezárás"
          >
            ✕
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-orange-500/15 text-orange-400 font-medium'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        Phase A · Batch upload
      </div>
    </aside>
  )
}
