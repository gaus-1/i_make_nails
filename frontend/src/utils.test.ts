/// <reference types="vitest" />

import {
  addDays,
  formatDateLabel,
  formatSlotTime,
  getWeekStart,
  groupAppointmentsByPeriod,
  statusLabel,
  toYYYYMMDD,
} from './utils'

describe('utils', () => {
  describe('toYYYYMMDD', () => {
    it('formats date as YYYY-MM-DD', () => {
      expect(toYYYYMMDD(new Date(2026, 0, 15))).toBe('2026-01-15')
      expect(toYYYYMMDD(new Date(2026, 11, 1))).toBe('2026-12-01')
    })
  })

  describe('formatSlotTime', () => {
    it('formats ISO time for Russian locale', () => {
      expect(formatSlotTime('2026-02-10T09:00:00+00:00')).toMatch(/\d{1,2}:\d{2}/)
      expect(formatSlotTime('2026-02-10T14:30:00Z')).toMatch(/\d{1,2}:\d{2}/)
    })
  })

  describe('formatDateLabel', () => {
    it('formats YYYY-MM-DD to readable Russian date', () => {
      const s = formatDateLabel('2026-02-15')
      expect(s).toContain('15')
      expect(s).toContain('февраля')
      expect(s.length).toBeGreaterThan(5)
    })
  })

  describe('addDays', () => {
    it('adds n days without mutating', () => {
      const d = new Date(2026, 1, 10)
      const next = addDays(d, 5)
      expect(next.getDate()).toBe(15)
      expect(d.getDate()).toBe(10)
    })
  })

  describe('statusLabel', () => {
    it('returns Russian label for known status', () => {
      expect(statusLabel('confirmed')).toBe('Подтверждена')
      expect(statusLabel('cancelled')).toBe('Отменена')
    })
    it('returns raw status for unknown', () => {
      expect(statusLabel('unknown')).toBe('unknown')
    })
  })

  describe('getWeekStart', () => {
    it('returns Monday for week', () => {
      const wed = new Date(2026, 1, 11)
      const mon = getWeekStart(wed)
      expect(mon.getDay()).toBe(1)
      expect(mon.getDate()).toBe(9)
    })
  })

  describe('groupAppointmentsByPeriod', () => {
    it('day: one group for anchor date', () => {
      const anchor = new Date(2026, 1, 15)
      const groups = groupAppointmentsByPeriod([], 'day', anchor)
      expect(groups).toHaveLength(1)
      expect(groups[0].dateStr).toBe('2026-02-15')
      expect(groups[0].items).toEqual([])
    })
    it('groups by date and sorts by time', () => {
      const anchor = new Date(2026, 1, 15)
      const items = [
        { id: 1, label: 'A', datetime_start_utc: '2026-02-15T10:00:00Z', status: 'confirmed', source: 'x' },
        { id: 2, label: 'B', datetime_start_utc: '2026-02-15T09:00:00Z', status: 'confirmed', source: 'x' },
      ]
      const groups = groupAppointmentsByPeriod(items as any, 'day', anchor)
      expect(groups[0].items).toHaveLength(2)
      expect(groups[0].items[0].label).toBe('B')
      expect(groups[0].items[1].label).toBe('A')
    })
  })
})
