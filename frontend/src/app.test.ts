/// <reference types="vitest" />

import { screen, within } from '@testing-library/dom'

import './main'

describe('mini-app shell', () => {
  it('renders primary action and hero text', () => {
    const cta = screen.getByRole('button', { name: /открыть запись/i })
    const hero = screen.getByText(/Выберите услугу, время и подтвердите запись/)
    expect(cta).toBeInTheDocument()
    expect(hero).toBeInTheDocument()
  })

  it('shows booking summary section', () => {
    const summarySection = document.querySelector<HTMLElement>('.shell__summary')
    expect(summarySection).toBeInTheDocument()
    expect(summarySection!.querySelector('.shell__summary-title')).toBeInTheDocument()
    expect(within(summarySection!).getByRole('button', { name: /подтвердить запись/i })).toBeInTheDocument()
  })
})
