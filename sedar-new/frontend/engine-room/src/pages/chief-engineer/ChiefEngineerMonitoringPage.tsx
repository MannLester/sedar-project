import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CircleCheckBig, Eye, Loader2, Send, Undo2 } from 'lucide-react'
import { DailyEngineMonitorCard } from '../../components/chief-engineer/DailyEngineMonitorCard'
import { DailyLogSummary } from '../../components/chief-engineer/DailyLogSummary'
import { PrintableLog } from '../../components/chief-engineer/PrintableLog'
import { useEngineRoom } from '../../context/engineRoomStore'
import type { EngineId } from '../../types/engineLog'

type ViewMode = 'edit' | 'review'

const DISABLED_CLS = 'disabled:cursor-not-allowed disabled:opacity-60'
const consoleTitle = 'Engine Room Console'

export function ChiefEngineerMonitoringPage() {
  const {
    currentRole, activeTug, date, selectLog, tabs, logs, updateLog, watchStart, watchStop, preparedBy, approvedBy,
    reviewStatus, returnReason, waitingToSync, submit, approve, returnReport, notify,
  } = useEngineRoom()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [selectedEngine, setSelectedEngine] = useState<EngineId>('')
  const [isWorking, setIsWorking] = useState(false)
  const [stopError, setStopError] = useState(false)
  const [returning, setReturning] = useState(false)
  const [reason, setReason] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('edit')
  const requestedLog = params.get('log')

  useEffect(() => selectLog(requestedLog), [requestedLog, selectLog])

  // A new watch log gets its identity when it is submitted or approved; the address follows it.
  const follow = async (action: () => Promise<string | null>) => {
    const logId = await action()
    if (logId) navigate(`/monitoring?log=${logId}`, { replace: true })
    return Boolean(logId)
  }

  const log = logs.find((item) => item.engineId === selectedEngine) ?? logs[0]
  const isChief = currentRole === 'Chief Engineer'
  const isReadOnly = reviewStatus === 'pending' || reviewStatus === 'approved'
  const isReviewing = viewMode === 'review' || reviewStatus === 'approved'
  const isEditable = reviewStatus === 'draft' || reviewStatus === 'returned'
  const vesselName = activeTug?.name ?? 'No tugboat'

  const runAction = async (action: () => Promise<boolean>, onDone?: () => void) => {
    if (isWorking) return
    setIsWorking(true)
    const done = await action()
    setIsWorking(false)
    if (done) onDone?.()
  }

  // Validation gate: an open-ended log cannot enter Review mode — WATCH STOP (cut-off) is mandatory.
  const handleReview = () => {
    if (!watchStop) {
      setStopError(true)
      notify('Watch stop (cut-off) time is required before opening the review.')
      return
    }
    setStopError(false)
    setViewMode('review')
  }

  const handleConfirmAndSubmit = () => {
    if (!watchStop) {
      setStopError(true)
      setViewMode('edit')
      notify('Watch stop (cut-off) time is required before submitting the log.')
      return
    }
    void runAction(() => follow(submit), () => setViewMode('edit'))
  }

  const handleApprove = () => void runAction(() => follow(approve), () => setViewMode('edit'))

  // "Approve, Save & Print": once the approval is saved, the A4 watch log opens in the print dialog.
  const handleApproveAndPrint = () =>
    void runAction(() => follow(approve), () => {
      setViewMode('edit')
      window.setTimeout(() => window.print(), 400)
    })

  const handleReturn = () => {
    if (!reason.trim()) {
      notify('Say what needs correcting before returning the log.')
      return
    }
    void runAction(() => returnReport(reason.trim()), () => {
      setReturning(false)
      setReason('')
    })
  }

  let primaryAction: React.ReactNode
  if (isReviewing) {
    primaryAction = (
      <>
        {reviewStatus !== 'approved' && (
          <button
            type="button"
            className="button button-secondary button-lg"
            onClick={() => setViewMode('edit')}
            title="Return to the form to fix mistakes"
          >
            <ArrowLeft size={15} aria-hidden="true" /> BACK TO EDIT
          </button>
        )}
        {isEditable && isChief && (
          <button
            type="button"
            onClick={handleApproveAndPrint}
            disabled={isWorking}
            aria-live="polite"
            title="Approve the log and post its hours to the engine meters"
            className={`button button-success button-lg ${DISABLED_CLS} ${isWorking ? 'cursor-wait opacity-80' : ''}`}
          >
            {isWorking ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <CircleCheckBig size={15} strokeWidth={2.5} aria-hidden="true" />}
            {isWorking ? 'APPROVING…' : 'APPROVE, SAVE & PRINT'}
          </button>
        )}
        {isEditable && !isChief && (
          <button
            type="button"
            onClick={handleConfirmAndSubmit}
            disabled={isWorking}
            aria-live="polite"
            title="Confirm this log and submit it to the Chief Engineer"
            className={`button button-primary button-lg ${DISABLED_CLS} ${isWorking ? 'cursor-wait opacity-80' : ''}`}
          >
            {isWorking ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Send size={15} strokeWidth={2.5} aria-hidden="true" />}
            {isWorking ? 'SUBMITTING…' : 'CONFIRM & SUBMIT TO CHIEF'}
          </button>
        )}
        {reviewStatus === 'approved' && (
          <button type="button" disabled className={`button button-success button-lg ${DISABLED_CLS}`} aria-live="polite">
            <CircleCheckBig size={15} strokeWidth={2.5} aria-hidden="true" /> APPROVED ✓
          </button>
        )}
      </>
    )
  } else if (isEditable) {
    primaryAction = (
      <button
        type="button"
        onClick={handleReview}
        title="Review all entries before final submission"
        className="button button-review button-lg"
      >
        <Eye size={15} aria-hidden="true" /> REVIEW LOG
      </button>
    )
  } else if (isChief && reviewStatus === 'pending' && !waitingToSync) {
    primaryAction = (
      <>
        <button
          type="button"
          onClick={handleApprove}
          disabled={isWorking}
          aria-live="polite"
          title="Approve the watch log submitted by the Duty Engineer"
          className={`button button-success button-lg ${DISABLED_CLS}`}
        >
          <CircleCheckBig size={15} strokeWidth={2.5} aria-hidden="true" /> APPROVE
        </button>
        <button
          type="button"
          onClick={() => setReturning((open) => !open)}
          disabled={isWorking}
          aria-expanded={returning}
          title="Return the log to the Duty Engineer for correction"
          className={`button button-danger-outline button-lg ${DISABLED_CLS}`}
        >
          <Undo2 size={15} strokeWidth={2.5} aria-hidden="true" /> RETURN FOR CORRECTION
        </button>
      </>
    )
  } else if (reviewStatus === 'pending') {
    primaryAction = (
      <button type="button" disabled className={`button button-primary button-lg ${DISABLED_CLS}`} aria-live="polite">
        <CircleCheckBig size={15} strokeWidth={2.5} aria-hidden="true" /> SUBMITTED ✓
      </button>
    )
  } else {
    primaryAction = (
      <button type="button" disabled className={`button button-success button-lg ${DISABLED_CLS}`} aria-live="polite">
        <CircleCheckBig size={15} strokeWidth={2.5} aria-hidden="true" /> APPROVED ✓
      </button>
    )
  }

  const showNotice = reviewStatus === 'returned' || waitingToSync || returning
  const notice = (
    <>
      {reviewStatus === 'returned' && (
    <div role="alert" className="rounded-[10px] border border-red-300 bg-red-50 px-5 py-4 text-sm text-red-900">
      <strong className="block text-xs font-black uppercase tracking-wide">Returned for correction</strong>
      {returnReason}
    </div>
  )}
  {waitingToSync && (
    <div role="status" className="rounded-[10px] border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-900">
      <strong className="block text-xs font-black uppercase tracking-wide">Waiting to sync</strong>
      Saved on this device. It reaches the Chief Engineer as soon as there is a connection.
    </div>
  )}
  {returning && (
    <section aria-label="Return for correction" className="grid gap-3 rounded-[10px] border border-slate-200 bg-white p-5">
      <label htmlFor="return-reason" className="text-xs font-bold uppercase tracking-wider text-slate-500">
        What needs correcting?
      </label>
      <textarea
        id="return-reason"
        rows={3}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        className="rounded-md border border-slate-200 p-3 text-sm text-slate-900 outline-none focus:border-[#315d82]"
      />
      <div className="flex justify-end gap-3">
        <button type="button" className="button button-secondary button-lg" onClick={() => setReturning(false)}>CANCEL</button>
        <button type="button" className="button button-danger-outline button-lg" disabled={isWorking} onClick={handleReturn}>
          <Undo2 size={15} strokeWidth={2.5} aria-hidden="true" /> RETURN LOG
        </button>
      </div>
    </section>
  )}
    </>
  )

  return (
    <>
      <div className="tech-dashboard-header tech-header-centered sticky top-0 z-20 bg-white">
        <div className="tech-header-text">
          <span className="tech-header-kicker">
            {consoleTitle} · {currentRole} · {isReviewing ? 'Review & Confirmation' : 'Daily Operations'}
          </span>
          <h1>{isReviewing ? 'Review & Confirmation' : 'Daily Engine Monitoring'}</h1>
          <p>
            {vesselName} · {new Date(`${date}T00:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} ·{' '}
            {isReviewing ? 'Verify all entries for typos before final submission.' : 'Capture running hour meter readings and watch parameters.'}
          </p>
        </div>
        <div className="tech-header-actions">
          {primaryAction}
        </div>
      </div>

      {!log ? (
        <section className="tech-panel p-6 text-sm text-slate-600">
          {activeTug
            ? 'This tugboat has no engines with running hours yet.'
            : 'Nothing downloaded yet. Open this page once with a connection and it will keep working offline.'}
        </section>
      ) : isReviewing ? (
        <DailyLogSummary logs={logs} vesselName={vesselName} now={new Date(`${date}T00:00:00`)} watchStart={watchStart} watchStop={watchStop} />
      ) : (
        <DailyEngineMonitorCard
          log={log}
          tabs={tabs}
          notice={showNotice ? notice : null}
          onEngineChange={setSelectedEngine}
          onUpdate={updateLog}
          readOnly={isReadOnly}
          stopError={stopError}
        />
      )}
      {log && (
        <PrintableLog
          vesselName={vesselName}
          date={date}
          logs={logs}
          watchStart={watchStart}
          watchStop={watchStop}
          preparedBy={preparedBy}
          approvedBy={approvedBy}
          status={reviewStatus}
        />
      )}
    </>
  )
}
