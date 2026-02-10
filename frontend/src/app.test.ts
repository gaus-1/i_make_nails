import { screen, within } from '@testing-library/dom'

import './main'

describe('mini-app shell', () => {
  it('renders master name and primary action', () => {
    const name = screen.getByText('Екатерина Савина')
    const cta = screen.getByRole('button', { name: /открыть запись/i })

    expect(name).toBeInTheDocument()
    expect(cta).toBeInTheDocument()
  })

  it('shows booking summary section', () => {
    const summarySection = document.querySelector('.shell__summary')
    expect(summarySection).toBeInTheDocument()
    const summaryTitle = within(summarySection!).getByText('Классический обрезной маникюр')
    expect(summaryTitle).toBeInTheDocument()
  })
})

