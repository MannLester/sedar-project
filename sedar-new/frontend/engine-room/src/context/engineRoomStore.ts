import { createContext, useContext } from 'react'
import type { ApiReport, ApiTug, QueueItem } from '../api'
import type { EngineLog, EngineTab, WatchLogReviewStatus } from '../types/engineLog'

export type EngineRole = 'Duty Engineer' | 'Chief Engineer'

// The watch log being filled in on this device and not yet submitted, as the other screens see it.
export interface DraftSummary {
  date: string
  watchStart: string
  watchStop: string
  hours: number
  fuelRob: number
  fuelUsed: number
}

export interface EngineRoomContextValue {
  currentRole: EngineRole
  userName: string
  tugs: ApiTug[]
  activeTug: ApiTug | null
  selectTug: (tugId: number) => void
  logKey: string
  draftSummary: DraftSummary | null
  selectLog: (logId: string | null) => void
  date: string
  tabs: EngineTab[]
  logs: EngineLog[]
  updateLog: (updated: EngineLog) => void
  watchStart: string
  watchStop: string
  setWatchStart: (value: string) => void
  setWatchStop: (value: string) => void
  preparedBy: string
  approvedBy: string
  reviewStatus: WatchLogReviewStatus
  returnReason: string
  reports: ApiReport[]
  waitingToSync: boolean
  queue: QueueItem[]
  discardQueued: (clientId: string) => void
  lastSynced: string
  problem: string
  online: boolean
  syncNow: () => void
  submit: () => Promise<string | null>
  approve: () => Promise<string | null>
  returnReport: (reason: string) => Promise<boolean>
  notify: (message: string) => void
  toast: string
  clearToast: () => void
}

export const EngineRoomContext = createContext<EngineRoomContextValue | null>(null)

export function useEngineRoom(): EngineRoomContextValue {
  const context = useContext(EngineRoomContext)
  if (!context) throw new Error('useEngineRoom must be used within EngineRoomProvider')
  return context
}
