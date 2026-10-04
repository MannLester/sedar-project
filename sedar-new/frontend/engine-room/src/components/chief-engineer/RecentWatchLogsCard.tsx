import { Link } from 'react-router-dom'
import { ArrowRight, ChevronRight } from 'lucide-react'
import type { ApiReport } from '../../api'
import { timeRangeOf } from '../../utils/reportMapping'

interface RecentWatchLogsCardProps {
  reports: ApiReport[]
}

type LogStatus = 'draft' | 'returned' | 'pending' | 'approved'

const statusStyles: Record<LogStatus, string> = {
  draft: 'bg-slate-200 text-slate-950',
  returned: 'bg-[#ff8b77] text-slate-950',
  pending: 'bg-[#fbbf24] text-slate-950',
  approved: 'bg-[#39ff14] text-slate-950',
}

const statusLabels: Record<LogStatus, string> = {
  draft: 'Draft',
  returned: 'Returned',
  pending: 'Pending Verification',
  approved: 'Verified',
}

function statusOf(report: ApiReport): LogStatus {
  if (report.state === 'posted') return 'approved'
  if (report.state === 'submitted') return 'pending'
  return report.return_reason ? 'returned' : 'draft'
}

function formatDate(dateISO: string): string {
  return new Date(`${dateISO}T00:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function RecentWatchLogsCard({ reports }: RecentWatchLogsCardProps) {
  return (
    <section
      aria-labelledby="recent-watch-logs-title"
      className="rounded-[10px] border-2 border-slate-950 bg-slate-900 p-5 text-white"
    >
      <header className="flex items-center justify-between gap-3">
        <h2 id="recent-watch-logs-title" className="text-lg font-bold">
          Recent Watch Logs
        </h2>
        <div className="flex shrink-0 items-center gap-3">
          <span className="rounded-full border border-slate-600 px-3 py-1 text-xs font-bold text-slate-300">
            {reports.length} entries
          </span>
          <Link
            to="/monitoring/history"
            className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-slate-300 transition hover:text-white"
          >
            View all
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
      </header>

      <ul className="mt-4 max-h-[340px] overflow-y-auto divide-y-2 divide-slate-800 pr-1">
        {reports.map((report) => {
          const status = statusOf(report)
          return (
            <li key={report.id}>
              <Link
                to={`/monitoring?log=${report.log_id}`}
                className="group flex items-center gap-3 rounded-md px-2 py-3.5 transition hover:bg-slate-800 active:bg-slate-700"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">
                    {formatDate(report.date)}
                    <span className="font-medium text-slate-400">{`, ${timeRangeOf(report.watch_start, report.watch_stop)}`}</span>
                  </p>
                  <p className="mt-1 truncate text-xs text-slate-400">
                    Prepared By: <span className="font-bold text-white">{report.prepared_by}</span>
                  </p>
                </div>

                <span
                  className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wide ${statusStyles[status]}`}
                >
                  {statusLabels[status]}
                </span>

                <ChevronRight
                  size={26}
                  strokeWidth={2.5}
                  aria-hidden="true"
                  className="shrink-0 text-slate-400 transition group-hover:translate-x-1 group-hover:text-white"
                />
              </Link>
            </li>
          )
        })}
        {reports.length === 0 && <li className="px-2 py-6 text-sm text-slate-400">No daily engine reports for this tugboat yet.</li>}
      </ul>
    </section>
  )
}
