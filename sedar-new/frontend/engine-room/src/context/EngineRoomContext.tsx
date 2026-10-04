import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  RpcError,
  fetchSnapshot,
  readStored,
  reviewReport,
  syncQueue,
  writeStored,
  type QueueItem,
  type ReviewRequest,
  type Snapshot,
  type SyncResult,
} from '../api'
import type { EngineLog, WatchLogReviewStatus, WatchWindowLogs } from '../types/engineLog'
import { currentClockTime, runStateOf, todayISO } from '../utils/engineLog'
import { blankWindow, engineTabs, refreshDraft, toPayload, windowFromReport, withDerivedMeters } from '../utils/reportMapping'
import { EngineRoomContext, type DraftSummary, type EngineRoomContextValue } from './engineRoomStore'

const SYNC_RETRY_MS = 30000
const mountClock = currentClockTime()

interface Draft {
  date: string
  window: WatchWindowLogs
}

const newClientId = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

// Once the server holds a submitted or posted report for a watch log, the local draft of it is obsolete.
function pruneDrafts(drafts: Record<string, Draft>, snapshot: Snapshot): Record<string, Draft> {
  const reports = snapshot.tugs.flatMap((tug) => tug.reports)
  const kept = Object.fromEntries(
    Object.entries(drafts).filter(([key]) => {
      const report = reports.find((candidate) => candidate.log_id === key)
      return !report || report.state === 'draft'
    }),
  )
  return Object.keys(kept).length === Object.keys(drafts).length ? drafts : kept
}

function applyResults(queue: QueueItem[], results: SyncResult[]): QueueItem[] {
  return queue.flatMap((item) => {
    const result = results.find((candidate) => candidate.client_id === item.client_id)
    if (!result) return [item]
    return result.ok ? [] : [{ ...item, error: result.message }]
  })
}

export function EngineRoomProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(() => readStored('snapshot-v3', null))
  const [queue, setQueue] = useState<QueueItem[]>(() => readStored('queue-v3', []))
  const [tugId, setTugId] = useState<number | null>(() => readStored('tug', null))
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() => readStored('drafts-v4', {}))
  const [requestedLog, setRequestedLog] = useState<string | null>(null)
  const [problem, setProblem] = useState('')
  const [toast, setToast] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const queueRef = useRef(queue)
  const syncing = useRef(false)

  const updateQueue = useCallback((change: (current: QueueItem[]) => QueueItem[]) => {
    queueRef.current = change(queueRef.current)
    setQueue(queueRef.current)
  }, [])

  useEffect(() => writeStored('snapshot-v3', snapshot), [snapshot])
  useEffect(() => writeStored('queue-v3', queue), [queue])
  useEffect(() => writeStored('tug', tugId), [tugId])
  useEffect(() => writeStored('drafts-v4', drafts), [drafts])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 3500)
    return () => window.clearTimeout(timer)
  }, [toast])

  const notify = useCallback((message: string) => setToast(message), [])
  const clearToast = useCallback(() => setToast(''), [])

  const showProblem = useCallback((error: unknown) => {
    if (error instanceof RpcError && error.unreachable) {
      setOnline(false)
      return
    }
    setProblem(
      error instanceof RpcError && error.expired
        ? 'Your Odoo session expired. Log in again to send what is waiting; nothing is lost.'
        : `Could not sync: ${error instanceof Error ? error.message : String(error)}`,
    )
  }, [])

  const refresh = useCallback(async () => {
    try {
      const next = await fetchSnapshot()
      setSnapshot(next)
      setDrafts((current) => pruneDrafts(current, next))
      setProblem('')
      setOnline(true)
    } catch (error) {
      showProblem(error)
    }
  }, [showProblem])

  const sync = useCallback(async () => {
    if (syncing.current) return
    syncing.current = true
    try {
      const waiting = queueRef.current.filter((item) => !item.error)
      if (waiting.length) {
        const results = await syncQueue(waiting)
        updateQueue((current) => applyResults(current, results))
        const sent = results.filter((result) => result.ok).length
        if (sent) notify(`${sent} watch log${sent > 1 ? 's' : ''} sent to the Chief Engineer.`)
      }
      await refresh()
    } catch (error) {
      showProblem(error)
    } finally {
      syncing.current = false
    }
  }, [notify, refresh, showProblem, updateQueue])

  useEffect(() => {
    const onOnline = () => {
      setOnline(true)
      void sync()
    }
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    const retry = window.setInterval(() => {
      if (queueRef.current.some((item) => !item.error)) void sync()
    }, SYNC_RETRY_MS)
    void sync()
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
      window.clearInterval(retry)
    }
  }, [sync])

  const activeTug = snapshot?.tugs.find((tug) => tug.id === tugId) ?? snapshot?.tugs[0] ?? null
  const reports = useMemo(() => activeTug?.reports ?? [], [activeTug])
  // A returned report is the log still open for the crew; otherwise a fresh watch log is ready to be filled in.
  const returned = reports.find((report) => report.state === 'draft')
  const logKey = requestedLog ?? returned?.log_id ?? `new:${activeTug?.id}`
  const serverReport = reports.find((report) => report.log_id === logKey)
  const queued = queue.find((item) => item.log_id === logKey && !item.error)
  const rejection = queue.find((item) => item.log_id === logKey && item.error)?.error ?? ''
  const draft = drafts[logKey]
  const date = serverReport?.date ?? draft?.date ?? todayISO()

  let reviewStatus: WatchLogReviewStatus = 'draft'
  if (serverReport?.state === 'posted') reviewStatus = 'approved'
  else if (serverReport?.state === 'submitted' || queued) reviewStatus = 'pending'
  else if (serverReport?.return_reason) reviewStatus = 'returned'

  const baseWindow = useMemo<WatchWindowLogs | null>(() => {
    if (!activeTug) return null
    if (serverReport && serverReport.state !== 'draft') return windowFromReport(activeTug, serverReport)
    if (draft) return refreshDraft(activeTug, draft.date, draft.window)
    if (serverReport) return windowFromReport(activeTug, serverReport)
    return { ...blankWindow(activeTug, date), watchStart: mountClock }
  }, [activeTug, date, draft, serverReport])

  const working = useMemo(() => (baseWindow ? withDerivedMeters(baseWindow) : null), [baseWindow])

  const blankDraft = activeTug ? drafts[`new:${activeTug.id}`] : undefined
  const draftSummary = useMemo<DraftSummary | null>(() => {
    if (!activeTug || !blankDraft) return null
    const derived = withDerivedMeters(refreshDraft(activeTug, blankDraft.date, blankDraft.window))
    const ran = derived.logs.find((log) => runStateOf(log) === 'operated')
    return {
      date: blankDraft.date,
      watchStart: derived.watchStart,
      watchStop: derived.watchStop,
      hours: ran ? Math.max(0, ran.meterCurrent - ran.meterPrevious) : 0,
      fuelRob: (ran ?? derived.logs[0])?.fuelRobStop ?? 0,
      fuelUsed: ran ? Math.max(0, ran.fuelRobStart - ran.fuelRobStop) : 0,
    }
  }, [activeTug, blankDraft])

  const changeWindow = useCallback(
    (change: (window: WatchWindowLogs) => WatchWindowLogs) => {
      if (!baseWindow) return
      setDrafts((current) => ({ ...current, [logKey]: { date, window: change(current[logKey]?.window ?? baseWindow) } }))
    },
    [baseWindow, date, logKey],
  )

  // Forms send the whole log they rendered; only the fields they changed are applied, so two quick edits never undo each other.
  const updateLog = useCallback<EngineRoomContextValue['updateLog']>(
    (updated) => {
      const rendered = working?.logs.find((log) => log.engineId === updated.engineId)
      const changed = Object.fromEntries(
        Object.entries(updated).filter(([key, value]) => !rendered || JSON.stringify(value) !== JSON.stringify(rendered[key as keyof EngineLog])),
      )
      changeWindow((window) => ({ ...window, logs: window.logs.map((log) => (log.engineId === updated.engineId ? { ...log, ...changed } : log)) }))
    },
    [changeWindow, working],
  )
  const setWatchStart = useCallback((value: string) => changeWindow((window) => ({ ...window, watchStart: value })), [changeWindow])
  const setWatchStop = useCallback((value: string) => changeWindow((window) => ({ ...window, watchStop: value })), [changeWindow])

  const selectTug = useCallback((id: number) => {
    setTugId(id)
    setRequestedLog(null)
  }, [])

  // A new watch log gets its permanent identifier when it leaves the device; its draft moves under that identifier.
  const adopt = useCallback(
    (logId: string) => {
      if (!baseWindow) return
      setDrafts((current) => {
        const next = { ...current, [logId]: { date, window: baseWindow } }
        if (logId !== logKey) delete next[logKey]
        return next
      })
    },
    [baseWindow, date, logKey],
  )

  const submit = useCallback(async () => {
    if (!activeTug || !baseWindow) return null
    const logId = logKey.startsWith('new:') ? newClientId() : logKey
    const item: QueueItem = {
      client_id: newClientId(),
      kind: 'report',
      label: `Watch log ${activeTug.name} ${date}`,
      ...toPayload(activeTug, date, baseWindow, logId),
    }
    adopt(logId)
    updateQueue((current) => [...current.filter((waiting) => waiting.log_id !== logId), item])
    notify(online ? 'Submitting to the Chief Engineer…' : 'Saved on this device; it will be sent when you are back online.')
    void sync()
    return logId
  }, [activeTug, adopt, baseWindow, date, logKey, notify, online, sync, updateQueue])

  const review = useCallback(
    async (request: ReviewRequest, done: string) => {
      try {
        await reviewReport(request)
        notify(done)
        await refresh()
        return true
      } catch (error) {
        if (error instanceof RpcError && error.unreachable) notify('This needs a connection to Odoo. Try again when you are back online.')
        else notify(error instanceof Error ? error.message : String(error))
        return false
      }
    },
    [notify, refresh],
  )

  const approve = useCallback(async () => {
    if (!activeTug || !baseWindow) return null
    const logId = logKey.startsWith('new:') ? newClientId() : logKey
    const request: ReviewRequest =
      serverReport?.state === 'submitted'
        ? { action: 'approve', log_id: logId }
        : { action: 'approve', ...toPayload(activeTug, date, baseWindow, logId) }
    const done = await review(request, 'Watch log approved and posted to the engine hour meters.')
    if (!done) return null
    setDrafts((current) => {
      const next = { ...current }
      delete next[logKey]
      return next
    })
    return logId
  }, [activeTug, baseWindow, date, logKey, review, serverReport])

  const returnReport = useCallback(
    async (reason: string) => {
      if (serverReport?.state !== 'submitted') return false
      return review({ action: 'return', log_id: logKey, reason }, 'Watch log returned for correction.')
    },
    [logKey, review, serverReport],
  )

  const value = useMemo<EngineRoomContextValue>(
    () => ({
      currentRole: snapshot?.can_approve ? 'Chief Engineer' : 'Duty Engineer',
      userName: snapshot?.user ?? '',
      tugs: snapshot?.tugs ?? [],
      activeTug,
      selectTug,
      logKey,
      draftSummary,
      selectLog: setRequestedLog,
      date,
      tabs: activeTug ? engineTabs(activeTug) : [],
      logs: working?.logs ?? [],
      updateLog,
      watchStart: working?.watchStart ?? '',
      watchStop: working?.watchStop ?? '',
      setWatchStart,
      setWatchStop,
      preparedBy: serverReport?.prepared_by || snapshot?.user || '',
      approvedBy: serverReport?.approved_by ?? '',
      reviewStatus,
      returnReason: serverReport?.return_reason ?? '',
      reports,
      waitingToSync: Boolean(queued),
      rejection,
      queue,
      discardQueued: (clientId) => updateQueue((current) => current.filter((item) => item.client_id !== clientId)),
      lastSynced: snapshot?.generated_at ?? '',
      problem,
      online,
      syncNow: () => void sync(),
      submit,
      approve,
      returnReport,
      notify,
      toast,
      clearToast,
    }),
    [snapshot, activeTug, selectTug, logKey, draftSummary, date, working, updateLog, setWatchStart, setWatchStop, serverReport, reviewStatus, reports, queued, rejection, queue, problem, online, sync, submit, approve, returnReport, notify, toast, clearToast, updateQueue],
  )

  return <EngineRoomContext.Provider value={value}>{children}</EngineRoomContext.Provider>
}
