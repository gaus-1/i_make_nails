/** Глобальное состояние мини-аппа. */

import type { Appointment, Service, Slot } from './api'

export type MasterAppointment = {
  id: number
  client_name: string
  client_phone: string | null
  service_name: string
  datetime_local: string
  status: string
}

export type MasterClient = {
  id: number
  name: string
  phone: string | null
  booking_allowed: boolean
  future_appointments_count: number
}

export type WorkScheduleItem = {
  id: number
  day_of_week: number
  time_start: string
  time_end: string
}

export type MasterSettings = {
  booking_enabled: boolean
  timezone: string
  work_schedule: WorkScheduleItem[]
}

export type BlockedSlotItem = {
  id: number
  date_start: string
  date_end: string
  reason: string | null
}

export const state = {
  appView: 'client' as 'client' | 'master',
  view: 'booking' as 'booking' | 'my',
  services: [] as Service[],
  selectedServiceId: null as number | null,
  selectedDate: null as string | null,
  slots: [] as Slot[],
  selectedSlotUtc: null as string | null,
  appointments: [] as Appointment[],
  loading: false,
  error: null as string | null,
  success: null as string | null,
  calendarMonth: new Date(),
  myPeriod: 'week' as 'day' | 'week' | 'month',
  myPeriodAnchor: new Date(),
  rescheduleAppointmentId: null as number | null,
  masterTab: 'schedule' as 'schedule' | 'clients' | 'settings' | 'blocked',
  masterScheduleDate: toDateStr(),
  masterAppointments: [] as MasterAppointment[],
  masterClients: [] as MasterClient[],
  masterSettings: null as MasterSettings | null,
  masterBlockedSlots: [] as BlockedSlotItem[],
  masterLoading: false,
  masterError: null as string | null,
}

function toDateStr(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
