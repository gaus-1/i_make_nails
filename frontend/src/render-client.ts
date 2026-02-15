/** Рендер клиентского UI: запись и мои записи. */

import {
  API,
  apiGet,
  apiPost,
  getTelegramUser,
  type Appointment,
  type Slot,
} from './api'
import { state } from './state'
import {
  addDays,
  formatDateLabel,
  formatSlotTime,
  getWeekStart,
  groupAppointmentsByPeriod,
  statusLabel,
  toYYYYMMDD,
} from './utils'

export async function loadSlots(dateStr: string, scheduleRender: () => void): Promise<void> {
  state.loading = true
  state.error = null
  scheduleRender()
  try {
    const data = await apiGet<{ date: string; slots: Slot[]; slot_duration_minutes: number }>(
      API.slots(dateStr)
    )
    if (state.selectedDate !== dateStr) return
    state.slots = data.slots
    state.slotDurationMinutes = data.slot_duration_minutes ?? null
  } catch {
    if (state.selectedDate !== dateStr) return
    state.slots = []
    state.slotDurationMinutes = null
  } finally {
    state.loading = false
    scheduleRender()
  }
}

export async function loadMyAppointments(scheduleRender: () => void): Promise<void> {
  state.loading = true
  scheduleRender()
  try {
    const data = await apiGet<{ appointments: Appointment[] }>(API.myAppointments)
    state.appointments = data.appointments
  } catch {
    state.appointments = []
  }
  state.loading = false
  scheduleRender()
}

function renderMyAppointments(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section'
  const titleRow = document.createElement('div')
  titleRow.className = 'shell__my-header'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Мои записи'
  const refreshBtn = document.createElement('button')
  refreshBtn.className = 'shell__pill'
  refreshBtn.type = 'button'
  refreshBtn.textContent = 'Обновить'
  refreshBtn.addEventListener('click', () => loadMyAppointments(scheduleRender))
  titleRow.appendChild(title)
  titleRow.appendChild(refreshBtn)
  card.appendChild(titleRow)

  const periodTabs = document.createElement('div')
  periodTabs.className = 'shell__period-tabs'
  const periods: { key: 'day' | 'week' | 'month'; label: string }[] = [
    { key: 'day', label: 'День' },
    { key: 'week', label: 'Неделя' },
    { key: 'month', label: 'Месяц' },
  ]
  for (const p of periods) {
    const btn = document.createElement('button')
    btn.className = 'shell__period-tab' + (state.myPeriod === p.key ? ' shell__period-tab--active' : '')
    btn.type = 'button'
    btn.textContent = p.label
    btn.addEventListener('click', () => {
      state.myPeriod = p.key
      state.myPeriodAnchor = new Date()
      scheduleRender()
    })
    periodTabs.appendChild(btn)
  }
  card.appendChild(periodTabs)

  const periodNav = document.createElement('div')
  periodNav.className = 'shell__calendar-header'
  const periodLabel = document.createElement('span')
  if (state.myPeriod === 'day') {
    periodLabel.textContent = formatDateLabel(toYYYYMMDD(state.myPeriodAnchor))
  } else if (state.myPeriod === 'week') {
    const ws = getWeekStart(state.myPeriodAnchor)
    periodLabel.textContent = `${ws.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} – ${addDays(ws, 6).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}`
  } else {
    periodLabel.textContent = state.myPeriodAnchor.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  }
  const navDiv = document.createElement('div')
  navDiv.className = 'shell__calendar-nav'
  const prevNav = document.createElement('button')
  prevNav.type = 'button'
  prevNav.setAttribute('aria-label', 'Назад')
  prevNav.textContent = '‹'
  prevNav.addEventListener('click', () => {
    const d = new Date(state.myPeriodAnchor)
    if (state.myPeriod === 'day') d.setDate(d.getDate() - 1)
    else if (state.myPeriod === 'week') d.setDate(d.getDate() - 7)
    else d.setMonth(d.getMonth() - 1)
    state.myPeriodAnchor = d
    scheduleRender()
  })
  const nextNav = document.createElement('button')
  nextNav.type = 'button'
  nextNav.setAttribute('aria-label', 'Вперёд')
  nextNav.textContent = '›'
  nextNav.addEventListener('click', () => {
    const d = new Date(state.myPeriodAnchor)
    if (state.myPeriod === 'day') d.setDate(d.getDate() + 1)
    else if (state.myPeriod === 'week') d.setDate(d.getDate() + 7)
    else d.setMonth(d.getMonth() + 1)
    state.myPeriodAnchor = d
    scheduleRender()
  })
  navDiv.appendChild(prevNav)
  navDiv.appendChild(nextNav)
  periodNav.appendChild(periodLabel)
  periodNav.appendChild(navDiv)
  card.appendChild(periodNav)

  if (state.loading) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else if (state.appointments.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Нет записей за последние 30 дней.'
    card.appendChild(p)
  } else {
    const groups = groupAppointmentsByPeriod(
      state.appointments,
      state.myPeriod,
      state.myPeriodAnchor
    )
    const list = document.createElement('div')
    list.className = 'shell__appointments-list'
    for (const g of groups) {
      const dayHeader = document.createElement('div')
      dayHeader.className = 'shell__day-header'
      dayHeader.textContent = formatDateLabel(g.dateStr)
      list.appendChild(dayHeader)
      if (g.items.length === 0) {
        const empty = document.createElement('p')
        empty.className = 'shell__section-caption shell__day-empty'
        empty.textContent = 'Нет записей'
        list.appendChild(empty)
      } else {
        for (const a of g.items) {
          const item = document.createElement('div')
          item.className = 'shell__appointment-item'
          const name = document.createElement('div')
          name.className = 'shell__appointment-name'
          name.textContent = a.label
          const meta = document.createElement('div')
          meta.className = 'shell__appointment-meta'
          const dt = new Date(a.datetime_start_utc)
          const dateStr = dt.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
          const timeStr = dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
          meta.textContent = `${dateStr}, ${timeStr} · ${statusLabel(a.status)}`
          item.appendChild(name)
          item.appendChild(meta)
          if (a.status === 'confirmed' && new Date(a.datetime_start_utc) > new Date()) {
            const cancelBtn = document.createElement('button')
            cancelBtn.className = 'shell__pill'
            cancelBtn.type = 'button'
            cancelBtn.textContent = 'Отменить'
            cancelBtn.addEventListener('click', async () => {
              try {
                await apiPost(API.cancelAppointment(a.id))
                state.success = 'Запись отменена.'
                await loadMyAppointments(scheduleRender)
                scheduleRender()
              } catch {
                scheduleRender()
              }
            })
            item.appendChild(cancelBtn)
            const rescheduleBtn = document.createElement('button')
            rescheduleBtn.className = 'shell__pill'
            rescheduleBtn.type = 'button'
            rescheduleBtn.textContent = 'Перенести'
            rescheduleBtn.addEventListener('click', () => {
              state.rescheduleAppointmentId = a.id
              state.view = 'booking'
              const apptDate = new Date(a.datetime_start_utc)
              state.selectedDate = toYYYYMMDD(apptDate)
              state.calendarMonth = new Date(apptDate.getFullYear(), apptDate.getMonth(), 1)
              state.selectedSlotUtc = null
              state.slots = []
              loadSlots(state.selectedDate, scheduleRender)
              scheduleRender()
            })
            item.appendChild(rescheduleBtn)
          }
          list.appendChild(item)
        }
      }
    }
    card.appendChild(list)
  }
  main.appendChild(card)
}

function renderBooking(main: HTMLElement, scheduleRender: () => void): void {
  const todayStr = toYYYYMMDD(new Date())
  const layout = document.createElement('section')
  layout.className = 'shell__layout'

  const sectionSlot = document.createElement('section')
  sectionSlot.className = 'shell__card shell__section'
  const h2Slot = document.createElement('h2')
  h2Slot.className = 'shell__section-title'
  h2Slot.textContent = 'Дата и время'
  const capSlot = document.createElement('p')
  capSlot.className = 'shell__section-caption'
  capSlot.textContent = 'Выберите день — под календарём появятся свободные слоты.'
  sectionSlot.appendChild(h2Slot)
  sectionSlot.appendChild(capSlot)

  const calendarWrap = document.createElement('div')
  calendarWrap.className = 'shell__calendar-wrap'
  {
    const calMonth = state.calendarMonth
    const y = calMonth.getFullYear()
    const m = calMonth.getMonth()
    const firstDay = new Date(y, m, 1)
    const monFirst = (firstDay.getDay() + 6) % 7
    const daysInMonth = new Date(y, m + 1, 0).getDate()
    const totalCells = 42
    const headerCal = document.createElement('div')
    headerCal.className = 'shell__calendar-header'
    const monthLabel = document.createElement('span')
    monthLabel.textContent = firstDay.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
    const nav = document.createElement('div')
    nav.className = 'shell__calendar-nav'
    const prevBtn = document.createElement('button')
    prevBtn.type = 'button'
    prevBtn.setAttribute('aria-label', 'Предыдущий месяц')
    prevBtn.textContent = '‹'
    prevBtn.addEventListener('click', () => {
      state.calendarMonth = new Date(y, m - 1, 1)
      state.selectedDate = null
      state.slots = []
      state.selectedSlotUtc = null
      scheduleRender()
    })
    const nextBtn = document.createElement('button')
    nextBtn.type = 'button'
    nextBtn.setAttribute('aria-label', 'Следующий месяц')
    nextBtn.textContent = '›'
    const today = new Date()
    const maxCalendarDate = addDays(today, 31)
    const nextMonthDate = new Date(y, m + 1, 1)
    const isNextDisabled = nextMonthDate > maxCalendarDate
    nextBtn.disabled = isNextDisabled
    if (isNextDisabled) nextBtn.setAttribute('aria-disabled', 'true')
    nextBtn.addEventListener('click', () => {
      if (isNextDisabled) return
      state.calendarMonth = new Date(y, m + 1, 1)
      state.selectedDate = null
      state.slots = []
      state.selectedSlotUtc = null
      scheduleRender()
    })
    nav.appendChild(prevBtn)
    nav.appendChild(nextBtn)
    headerCal.appendChild(monthLabel)
    headerCal.appendChild(nav)
    calendarWrap.appendChild(headerCal)

    const weekdaysRow = document.createElement('div')
    weekdaysRow.className = 'shell__cal-weekdays'
    for (const wd of ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']) {
      const cell = document.createElement('span')
      cell.className = 'shell__cal-weekday'
      cell.textContent = wd
      weekdaysRow.appendChild(cell)
    }
    calendarWrap.appendChild(weekdaysRow)

    const grid = document.createElement('div')
    grid.className = 'shell__cal-grid'
    for (let i = 0; i < totalCells; i++) {
      let cellDate: Date
      let isOtherMonth: boolean
      if (i < monFirst) {
        cellDate = new Date(y, m, 1 - (monFirst - i))
        isOtherMonth = true
      } else if (i < monFirst + daysInMonth) {
        cellDate = new Date(y, m, i - monFirst + 1)
        isOtherMonth = false
      } else {
        cellDate = new Date(y, m + 1, i - monFirst - daysInMonth + 1)
        isOtherMonth = true
      }
      const dateStr = toYYYYMMDD(cellDate)
      const isPast = dateStr < todayStr
      const cell = document.createElement('button')
      cell.type = 'button'
      cell.className = 'shell__cal-cell'
      if (isOtherMonth) cell.classList.add('shell__cal-cell--other')
      if (isPast) cell.classList.add('shell__cal-cell--past')
      if (state.selectedDate === dateStr) cell.classList.add('shell__cal-cell--active')
      cell.textContent = String(cellDate.getDate())
      cell.dataset.date = dateStr
      cell.disabled = isPast
      if (!isPast) {
        cell.addEventListener('click', () => {
          state.selectedDate = dateStr
          state.selectedSlotUtc = null
          scheduleRender()
          loadSlots(dateStr, scheduleRender)
        })
      }
      grid.appendChild(cell)
    }
    calendarWrap.appendChild(grid)

    if (state.selectedDate) {
      const selectedDatePast = state.selectedDate < todayStr
      if (selectedDatePast) {
        const pastHint = document.createElement('p')
        pastHint.className = 'shell__hint'
        pastHint.textContent = 'Выберите дату сегодня или в будущем.'
        calendarWrap.appendChild(pastHint)
      } else if (state.loading) {
        const loadHint = document.createElement('p')
        loadHint.className = 'shell__hint'
        loadHint.textContent = 'Загрузка слотов…'
        calendarWrap.appendChild(loadHint)
      } else {
        const slotsRow = document.createElement('div')
        slotsRow.className = 'shell__slots-row'
        if (state.slots.length === 0) {
          const noSlots = document.createElement('p')
          noSlots.className = 'shell__hint'
          noSlots.textContent = 'Нет свободных слотов на эту дату.'
          calendarWrap.appendChild(noSlots)
        } else {
          for (const slot of state.slots) {
            const slotBtn = document.createElement('button')
            slotBtn.className =
              'slot' + (state.selectedSlotUtc === slot.start_utc_iso ? ' slot--active' : '')
            slotBtn.type = 'button'
            slotBtn.textContent = formatSlotTime(slot.start_utc_iso)
            slotBtn.dataset.slot = slot.start_utc_iso
            slotBtn.addEventListener('click', () => {
              state.selectedSlotUtc = slot.start_utc_iso
              scheduleRender()
            })
            slotsRow.appendChild(slotBtn)
          }
          calendarWrap.appendChild(slotsRow)
        }
      }
    }
  }
  sectionSlot.appendChild(calendarWrap)
  layout.appendChild(sectionSlot)
  main.appendChild(layout)

  const summary = document.createElement('section')
  summary.className = 'shell__card shell__summary'
  const summaryTitle = document.createElement('div')
  summaryTitle.className = 'shell__summary-title'
  summaryTitle.textContent = 'Запись'
  const summaryMeta = document.createElement('div')
  summaryMeta.className = 'shell__summary-meta'
  if (state.selectedDate && state.selectedSlotUtc) {
    summaryMeta.textContent = `${formatDateLabel(state.selectedDate)} · ${formatSlotTime(state.selectedSlotUtc)}`
  } else {
    summaryMeta.textContent = 'Выберите дату и время'
  }
  const summaryDiv = document.createElement('div')
  summaryDiv.appendChild(summaryTitle)
  summaryDiv.appendChild(summaryMeta)
  summary.appendChild(summaryDiv)
  const isReschedule = state.rescheduleAppointmentId !== null
  const confirmBtn = document.createElement('button')
  confirmBtn.className = 'shell__pill shell__pill--primary'
  confirmBtn.type = 'button'
  const canConfirm =
    state.selectedSlotUtc &&
    !state.loading &&
    !state.submitting &&
    state.selectedDate !== null &&
    state.selectedDate >= todayStr
  confirmBtn.disabled = !canConfirm
  confirmBtn.textContent = state.submitting
    ? 'Подождите…'
    : isReschedule
      ? 'Перенести запись'
      : 'Подтвердить запись'
  confirmBtn.addEventListener('click', async () => {
    if (!state.selectedSlotUtc) return
    const user = getTelegramUser()
    state.submitting = true
    state.error = null
    scheduleRender()
    try {
      if (isReschedule) {
        await apiPost(API.rescheduleAppointment(state.rescheduleAppointmentId!), {
          slot_start_utc: state.selectedSlotUtc,
        })
        state.success = 'Запись перенесена.'
        state.rescheduleAppointmentId = null
        await loadMyAppointments(scheduleRender)
      } else {
        await apiPost(API.createAppointment, {
          telegram_id: user?.id ?? 0,
          name: user?.name ?? 'Клиент',
          phone: null,
          slot_start_utc: state.selectedSlotUtc,
        })
        state.success = 'Запись создана. Ждём вас!'
        state.selectedSlotUtc = null
        state.slots = []
        state.selectedDate = null
      }
      scheduleRender()
    } catch (err) {
      state.error = err instanceof Error ? err.message : 'Не удалось отправить запись.'
      scheduleRender()
    } finally {
      state.submitting = false
      scheduleRender()
    }
  })
  summary.appendChild(confirmBtn)
  main.appendChild(summary)
}

export function renderClient(shell: HTMLElement, scheduleRender: () => void): void {
  const main = document.createElement('main')
  main.className = 'shell__main'

  const tabs = document.createElement('section')
  tabs.className = 'shell__tabs'
  tabs.setAttribute('role', 'tablist')
  tabs.setAttribute('aria-label', 'Разделы')
  const tabBook = document.createElement('button')
  tabBook.className = 'shell__tab' + (state.view === 'booking' ? ' shell__tab--active' : '')
  tabBook.type = 'button'
  tabBook.textContent = 'Записаться'
  tabBook.setAttribute('role', 'tab')
  tabBook.setAttribute('aria-selected', String(state.view === 'booking'))
  tabBook.id = 'client-tab-booking'
  tabBook.setAttribute('aria-controls', 'client-panel-booking')
  tabBook.addEventListener('click', () => {
    state.view = 'booking'
    state.error = null
    state.success = null
    scheduleRender()
  })
  const tabMy = document.createElement('button')
  tabMy.className = 'shell__tab' + (state.view === 'my' ? ' shell__tab--active' : '')
  tabMy.type = 'button'
  tabMy.textContent = 'Мои записи'
  tabMy.setAttribute('role', 'tab')
  tabMy.setAttribute('aria-selected', String(state.view === 'my'))
  tabMy.id = 'client-tab-my'
  tabMy.setAttribute('aria-controls', 'client-panel-my')
  tabMy.addEventListener('click', async () => {
    state.view = 'my'
    state.error = null
    state.success = null
    scheduleRender()
    await loadMyAppointments(scheduleRender)
  })
  tabs.appendChild(tabBook)
  tabs.appendChild(tabMy)
  main.appendChild(tabs)

  const messagesZone = document.createElement('div')
  messagesZone.className = 'shell__messages'
  messagesZone.setAttribute('aria-live', 'polite')
  messagesZone.setAttribute('aria-atomic', 'true')
  if (state.success) {
    const ok = document.createElement('p')
    ok.className = 'shell__success'
    ok.textContent = state.success
    messagesZone.appendChild(ok)
  }
  main.appendChild(messagesZone)

  const panel = document.createElement('div')
  panel.className = 'shell__tabpanel'
  panel.setAttribute('role', 'tabpanel')
  panel.id = state.view === 'my' ? 'client-panel-my' : 'client-panel-booking'
  panel.setAttribute('aria-labelledby', state.view === 'my' ? 'client-tab-my' : 'client-tab-booking')
  if (state.view === 'my') {
    renderMyAppointments(panel, scheduleRender)
  } else {
    renderBooking(panel, scheduleRender)
  }
  main.appendChild(panel)

  shell.appendChild(main)
}
