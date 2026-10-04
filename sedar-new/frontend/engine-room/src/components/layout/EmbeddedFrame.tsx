import type { ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEngineRoom } from '../../context/engineRoomStore'
import { Toast } from '../ui/Toast'
import { Banners } from './Banners'

const TABS = [
  { label: 'Dashboard', path: '/', end: true },
  { label: 'Daily Engine Log', path: '/monitoring', end: true },
  { label: 'Daily Logs History', path: '/monitoring/history', end: true },
]

// Inside Odoo the navbar and sidebar already exist, so only a slim toolbar is drawn above Ed's pages.
export function EmbeddedFrame({ children }: { children: ReactNode }) {
  const { currentRole, userName, tugs, activeTug, selectTug, online, queue, lastSynced, syncNow, toast, clearToast } = useEngineRoom()
  const waiting = queue.filter((item) => !item.error).length
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <div className="embedded-frame">
      <div className="embedded-toolbar">
        <nav className="flex gap-1" aria-label="Engine room navigation">
          {TABS.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              end={tab.end}
              className={({ isActive }) =>
                `rounded-md px-4 py-2 text-xs font-extrabold uppercase tracking-wider transition ${isActive ? 'bg-[#082342] text-white' : 'text-[#315d82] hover:bg-slate-100'}`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          {tugs.length > 1 && (
            <label className="flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-wider text-[#5f6873]">
              Tugboat
              <select
                value={activeTug?.id ?? ''}
                onChange={(event) => {
                  selectTug(Number(event.target.value))
                  navigate(pathname)
                }}
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-bold normal-case tracking-normal text-slate-900"
              >
                {tugs.map((tug) => (
                  <option key={tug.id} value={tug.id}>{tug.name}</option>
                ))}
              </select>
            </label>
          )}
          <span className="text-xs text-slate-500" title={lastSynced ? `Data from ${lastSynced} UTC` : 'Not synced yet'}>
            {userName} · {currentRole} · {online ? 'Online' : 'Offline'}
            {waiting ? ` · ${waiting} waiting` : ''}
          </span>
          <button type="button" className="button button-secondary" aria-label="Sync now" onClick={syncNow}>
            <RefreshCw size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="embedded-body">
        <Banners />
        <main className="technical-dashboard">{children}</main>
      </div>
      {toast && <Toast message={toast} onClose={clearToast} />}
    </div>
  )
}
