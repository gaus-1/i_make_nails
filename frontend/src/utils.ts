/** Форматирование дат, слотов, группировка записей. */

import type { Appointment } from './api'

export const MONTHS_RU = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]

export function formatSlotTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

/** Формат даты для отображения (YYYY-MM-DD трактуется как локальная дата). */
export function formatDateLabel(dateStr: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr)
  const d = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(dateStr + 'Z')
  const day = d.getDate()
  const month = MONTHS_RU[d.getMonth()]
  const weekday = d.toLocaleDateString('ru-RU', { weekday: 'short' })
  return `${day} ${month}, ${weekday}`
}

export function toYYYYMMDD(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function addDays(d: Date, n: number): Date {
  const out = new Date(d)
  out.setDate(out.getDate() + n)
  return out
}

export const STATUS_RU: Record<string, string> = {
  confirmed: 'Подтверждена',
  completed: 'Состоялась',
  cancelled: 'Отменена',
  no_show: 'Не пришёл',
}

export function statusLabel(status: string): string {
  return STATUS_RU[status] ?? status
}

function toDateStrLocal(iso: string): string {
  const d = new Date(iso)
  return toYYYYMMDD(d)
}

export function getWeekStart(d: Date): Date {
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const out = new Date(d)
  out.setDate(d.getDate() + diff)
  out.setHours(0, 0, 0, 0)
  return out
}

export function groupAppointmentsByPeriod(
  appointments: Appointment[],
  period: 'day' | 'week' | 'month',
  anchor: Date
): { dateStr: string; items: Appointment[] }[] {
  const byDate = new Map<string, Appointment[]>()
  for (const a of appointments) {
    const dateStr = toDateStrLocal(a.datetime_start_utc)
    if (!byDate.has(dateStr)) byDate.set(dateStr, [])
    byDate.get(dateStr)!.push(a)
  }
  for (const arr of byDate.values())
    arr.sort((a, b) => a.datetime_start_utc.localeCompare(b.datetime_start_utc))

  const anchorDate = new Date(anchor)
  anchorDate.setHours(0, 0, 0, 0)

  if (period === 'day') {
    const dateStr = toYYYYMMDD(anchorDate)
    return [{ dateStr, items: byDate.get(dateStr) ?? [] }]
  }

  let start: Date
  let end: Date
  if (period === 'week') {
    const day = anchorDate.getDay()
    const diff = day === 0 ? -6 : 1 - day
    start = new Date(anchorDate)
    start.setDate(anchorDate.getDate() + diff)
    end = addDays(start, 7)
  } else {
    start = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1)
    end = new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 1)
  }

  const result: { dateStr: string; items: Appointment[] }[] = []
  const cur = new Date(start)
  while (cur < end) {
    const dateStr = toYYYYMMDD(cur)
    result.push({ dateStr, items: byDate.get(dateStr) ?? [] })
    cur.setDate(cur.getDate() + 1)
  }
  if (period === 'month') return result.filter((g) => g.items.length > 0)
  return result
}
