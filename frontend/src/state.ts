/** Глобальное состояние мини-аппа. */

import type { Appointment, Slot } from './api'
import { toYYYYMMDD } from './utils'

export type MasterAppointment = {
  id: number
  client_name: string
  client_phone: string | null
  client_telegram_id: number | null
  service_name: string
  datetime_local: string
  status: string
}

export type MasterClient = {
  id: number
  name: string
  phone: string | null
  telegram_id: number | null
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
  slot_duration_minutes: number
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
  userRole: null as string | null,
  view: 'booking' as 'booking' | 'my',
  selectedDate: null as string | null,
  slots: [] as Slot[],
  slotDurationMinutes: null as number | null,
  selectedSlotUtc: null as string | null,
  appointments: [] as Appointment[],
  loading: false,
  error: null as string | null,
  success: null as string | null,
  calendarMonth: new Date(),
  myPeriod: 'week' as 'day' | 'week' | 'month',
  myPeriodAnchor: new Date(),
  rescheduleAppointmentId: null as number | null,
  bookingPhone: '' as string,
  masterTab: 'schedule' as 'schedule' | 'clients' | 'settings' | 'blocked',
  masterScheduleDate: toYYYYMMDD(new Date()),
  masterScheduleView: 'day' as 'day' | 'week' | 'month',
  masterAppointments: [] as MasterAppointment[],
  masterSlots: [] as Slot[],
  masterSlotsByDate: {} as Record<string, Slot[]>,
  masterSlotDurationMinutes: null as number | null,
  masterClients: [] as MasterClient[],
  masterSettings: null as MasterSettings | null,
  masterBlockedSlots: [] as BlockedSlotItem[],
  masterLoading: false,
  masterError: null as string | null,
  submitting: false,
  masterSavingDay: null as number | null,
  masterBlockedSubmitting: false,
  masterRescheduleAppointmentId: null as number | null,
  masterRescheduleDate: null as string | null,
  masterRescheduleSlots: [] as Slot[],
}
