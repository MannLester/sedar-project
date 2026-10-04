export type EngineId = string

export type EngineClass = 'main' | 'auxiliary'

export interface EngineTab {
  id: EngineId
  label: string
  className: EngineClass
}

export interface NextPm {
  name: string
  intervalHours: number
  remainingHours: number
}

export interface EngineLog {
  id: string
  engineId: EngineId
  engineClass: EngineClass
  label: string
  date: string
  timeStart: string | null
  timeStop: string | null
  rpm: number
  oilPressure: number
  waterTemp: number
  fuelRobStart: number
  fuelRobStop: number
  meterPrevious: number
  meterCurrent: number
  nextPm: NextPm | null
}

export type WatchLogReviewStatus = 'draft' | 'pending' | 'approved' | 'returned'

export interface WatchWindowLogs {
  watchStart: string
  watchStop: string
  logs: EngineLog[]
}
