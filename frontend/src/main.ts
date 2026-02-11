/** Точка входа: определение вида (client/master) и рендер оболочки с контентом. */

import './style.css'

import { apiGet } from './api'
import { API } from './api'
import { state } from './state'
import { renderClient } from './render-client'
import { initMaster, renderMaster } from './render-master'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Root element #app not found')

function initAppView(): void {
  const params = new URLSearchParams(window.location.search)
  state.appView = params.get('view') === 'master' ? 'master' : 'client'
}

export async function loadMe(scheduleRender: () => void): Promise<void> {
  try {
    const data = await apiGet<{ telegram_id: number; role: string }>(API.me)
    state.userRole = data.role
  } catch {
    state.userRole = null
  }
  scheduleRender()
}

function switchToMasterView(): void {
  const url = new URL(window.location.href)
  url.searchParams.set('view', 'master')
  window.location.href = url.toString()
}

function switchToClientView(): void {
  const url = new URL(window.location.href)
  url.searchParams.delete('view')
  window.location.href = url.toString()
}

function render(): void {
  if (!app) return
  app.innerHTML = ''
  const shell = document.createElement('div')
  shell.className = 'shell'

  const header = document.createElement('header')
  header.className = 'shell__header'
  if (state.appView === 'client') {
    const openBtn = document.createElement('button')
    openBtn.className = 'shell__pill shell__pill--primary'
    openBtn.type = 'button'
    openBtn.textContent = 'Открыть запись'
    openBtn.addEventListener('click', () => {
      state.view = 'booking'
      state.success = null
      state.error = null
      state.rescheduleAppointmentId = null
      const mainEl = document.querySelector('.shell__main')
      mainEl?.scrollIntoView({ behavior: 'smooth' })
      render()
    })
    header.appendChild(openBtn)
    if (state.userRole === 'master' || state.userRole === 'admin') {
      const masterLink = document.createElement('button')
      masterLink.className = 'shell__pill'
      masterLink.type = 'button'
      masterLink.textContent = 'Панель мастера'
      masterLink.addEventListener('click', switchToMasterView)
      header.appendChild(masterLink)
    }
  } else {
    const clientLink = document.createElement('button')
    clientLink.className = 'shell__pill'
    clientLink.type = 'button'
    clientLink.textContent = 'Как клиент'
    clientLink.addEventListener('click', switchToClientView)
    header.appendChild(clientLink)
  }
  shell.appendChild(header)

  if (state.appView === 'master') {
    renderMaster(shell, render)
  } else {
    renderClient(shell, render)
  }

  app.appendChild(shell)
}

initAppView()
render()
if (state.appView === 'client') {
  loadMe(render)
} else {
  initMaster(render)
}
