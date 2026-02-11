/** Точка входа: определение вида (client/master) и рендер оболочки с контентом. */

import './style.css'

import { state } from './state'
import { loadServices, renderClient } from './render-client'
import { initMaster, renderMaster } from './render-master'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Root element #app not found')

function initAppView(): void {
  const params = new URLSearchParams(window.location.search)
  state.appView = params.get('view') === 'master' ? 'master' : 'client'
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
  loadServices(render)
} else {
  initMaster(render)
}
