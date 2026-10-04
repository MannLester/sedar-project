import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, History } from 'lucide-react'
import type { ApiReport } from '../../api'
import { useEngineRoom } from '../../context/engineRoomStore'
import { timeRangeOf } from '../../utils/reportMapping'

type HistoryStatus = 'draft' | 'returned' | 'pending' | 'approved'

interface HistoryRow {
  key: string
  logId: string
  date: string
  timeRange: string
  preparedBy: string
  hours: number
  fuel: number
  status: HistoryStatus
  waiting: boolean
  rejected: boolean
}

function formatDisplayDate(dateISO: string): string {
  return new Date(`${dateISO}T00:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const STATUS_LABELS: Record<HistoryStatus, string> = {
  draft: 'Draft',
  returned: 'Returned',
  pending: 'Pending Verification',
  approved: 'Verified',
}

const STATUS_STYLES: Record<HistoryStatus, string> = {
  draft: 'bg-slate-200 text-slate-900',
  returned: 'bg-[#ff8b77] text-slate-900',
  pending: 'bg-[#fbbf24] text-slate-900',
  approved: 'bg-[#39ff14] text-slate-900',
}

const CONTROL_CLS =
  'h-12 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-[#315d82] focus:ring-2 focus:ring-[#315d82]/10 placeholder:text-slate-400'

const LABEL_CLS = 'text-xs font-semibold uppercase tracking-wider text-slate-500'

function statusOf(report: ApiReport): HistoryStatus {
  if (report.state === 'posted') return 'approved'
  if (report.state === 'submitted') return 'pending'
  return report.return_reason ? 'returned' : 'draft'
}

export function DailyEngineLogHistory() {
  const { activeTug, reports, queue, draftSummary } = useEngineRoom()
  const navigate = useNavigate()

  const [searchQuery, setSearchQuery] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'' | HistoryStatus>('')

  const filtersActive = Boolean(searchQuery || dateFilter || statusFilter)

  const clearFilters = () => {
    setSearchQuery('')
    setDateFilter('')
    setStatusFilter('')
  }

  const rows = useMemo<HistoryRow[]>(() => {
    const saved = reports.map((report) => ({
      key: `report-${report.id}`,
      logId: report.log_id,
      date: report.date,
      timeRange: timeRangeOf(report.watch_start, report.watch_stop),
      preparedBy: report.prepared_by,
      hours: report.hours,
      fuel: report.fuel,
      status: statusOf(report),
      waiting: false,
      rejected: false,
    }))
    const waiting = queue
      .filter((item) => item.tugboat_id === activeTug?.id && !reports.some((report) => report.log_id === item.log_id && report.state !== 'draft'))
      .map((item) => ({
        key: item.client_id,
        logId: item.log_id,
        date: item.report_date,
        timeRange: timeRangeOf(item.watch_start, item.watch_stop),
        preparedBy: 'You',
        hours: item.lines.some((line) => line.engine_status === 'operated') ? ((item.watch_stop - item.watch_start + 24) % 24) : 0,
        fuel: item.lines.reduce((sum, line) => (line.engine_status === 'operated' ? sum + Math.max(0, line.fuel_rob_start - line.fuel_rob_stop) : sum), 0),
        status: item.error ? ('returned' as const) : ('pending' as const),
        waiting: !item.error,
        rejected: Boolean(item.error),
      }))
    const inProgress: HistoryRow[] = draftSummary
      ? [{
          key: 'in-progress',
          logId: '',
          date: draftSummary.date,
          timeRange: `${draftSummary.watchStart || '—'} - ${draftSummary.watchStop || '…'}`,
          preparedBy: 'You',
          hours: draftSummary.hours,
          fuel: draftSummary.fuelUsed,
          status: 'draft',
          waiting: false,
          rejected: false,
        }]
      : []
    return [...inProgress, ...waiting, ...saved.filter((row) => !waiting.some((entry) => entry.logId === row.logId))]
  }, [activeTug, draftSummary, queue, reports])

  const filtered = useMemo(
    () =>
      rows.filter((entry) => {
        if (dateFilter && entry.date !== dateFilter) return false
        if (statusFilter && entry.status !== statusFilter) return false
        if (searchQuery) {
          const haystack = [entry.preparedBy, formatDisplayDate(entry.date), entry.timeRange, STATUS_LABELS[entry.status]].join(' ').toLowerCase()
          if (!haystack.includes(searchQuery.trim().toLowerCase())) return false
        }
        return true
      }),
    [rows, searchQuery, dateFilter, statusFilter],
  )

  const openLog = (logId: string) => navigate(logId ? `/monitoring?log=${logId}` : '/monitoring')

  return (
    <>
      <div className="tech-dashboard-header">
        <div className="tech-header-text">
          <span className="tech-header-kicker">{activeTug?.name ?? 'No tugboat'}</span>
          <h1>Daily Engine Monitoring History</h1>
        </div>
      </div>

      <section aria-label="Daily engine report records" className="overflow-hidden rounded-[10px] border border-slate-200 bg-white">
        <div className="flex flex-wrap items-end gap-6 border-b border-slate-200 px-5 py-4">
          <input
            type="text"
            aria-label="Search logs"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className={`w-64 ${CONTROL_CLS}`}
          />

          <div className="ml-auto flex flex-wrap items-end gap-6">
            <div className="grid gap-1.5">
              <label htmlFor="wlh-date" className={LABEL_CLS}>
                Select Date
              </label>
              <input id="wlh-date" type="date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} className={CONTROL_CLS} />
            </div>

            <div className="grid gap-1.5">
              <label htmlFor="wlh-status" className={LABEL_CLS}>
                Status
              </label>
              <select
                id="wlh-status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as '' | HistoryStatus)}
                className={`min-w-52 ${CONTROL_CLS}`}
              >
                <option value="">All</option>
                {(Object.keys(STATUS_LABELS) as HistoryStatus[]).map((status) => (
                  <option key={status} value={status}>
                    {STATUS_LABELS[status]}
                  </option>
                ))}
              </select>
            </div>

            {filtersActive && (
              <button type="button" className="button button-secondary button-lg" onClick={clearFilters}>
                Clear Filters
              </button>
            )}
          </div>
        </div>

        {filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left">
              <thead>
                <tr className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-5 py-4">Watch Date &amp; Time</th>
                  <th scope="col" className="px-5 py-4">Prepared By</th>
                  <th scope="col" className="px-5 py-4">Total Running Hours</th>
                  <th scope="col" className="px-5 py-4">Fuel Consumed (Litres)</th>
                  <th scope="col" className="px-5 py-4">Status</th>
                  <th scope="col" className="px-5 py-4 text-right">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((entry) => (
                  <tr
                    key={entry.key}
                    onClick={() => openLog(entry.logId)}
                    className="group cursor-pointer border-t border-slate-200 transition hover:bg-slate-50"
                  >
                    <td className="px-5 py-4 text-sm font-bold text-slate-900">
                      {formatDisplayDate(entry.date)}
                      {entry.timeRange && `, ${entry.timeRange}`}
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{entry.preparedBy}</td>
                    <td className="px-5 py-4 text-sm tabular-nums text-slate-900">{entry.hours.toFixed(1)} hrs</td>
                    <td className="px-5 py-4 text-sm tabular-nums text-slate-900">{entry.fuel.toLocaleString()} L</td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wide ${STATUS_STYLES[entry.status]}`}>
                        {entry.rejected ? 'Not accepted' : entry.waiting ? 'Waiting to sync' : STATUS_LABELS[entry.status]}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        type="button"
                        aria-label={`View log from ${formatDisplayDate(entry.date)}${entry.timeRange && `, ${entry.timeRange}`}`}
                        onClick={(event) => {
                          event.stopPropagation()
                          openLog(entry.logId)
                        }}
                        className="inline-grid size-9 place-items-center rounded-full bg-slate-100 text-slate-500 transition group-hover:bg-[#ff4d2f] group-hover:text-white"
                      >
                        <ChevronRight size={20} strokeWidth={2.5} aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 px-5 py-16 text-center">
            <History size={32} className="text-slate-400" aria-hidden="true" />
            <strong className="text-sm text-slate-900">
              {rows.length ? 'No logs match the selected filters.' : 'No daily engine reports for this tugboat yet.'}
            </strong>
            {filtersActive && (
              <button type="button" className="button button-secondary button-lg" onClick={clearFilters}>
                Clear Filters
              </button>
            )}
          </div>
        )}

        <footer className="border-t border-slate-200 px-5 py-3 text-sm text-slate-600">
          Showing {filtered.length} of {rows.length} logs
        </footer>
      </section>
    </>
  )
}
