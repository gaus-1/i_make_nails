import { expect } from '@playwright/test'
import { test } from '@playwright/test'

const MASTER_ID = process.env.E2E_MASTER_TELEGRAM_ID ?? '111'

test.describe('Панель мастера', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/?view=master&telegram_id=${MASTER_ID}`)
  })

  test('вход: табы Расписание, Настройки, Клиенты, Закрытия', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Расписание' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('tab', { name: 'Настройки' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Клиенты' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Закрытия' })).toBeVisible()
  })

  test('расписание дня: заголовок и дата', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Расписание' })).toBeVisible({ timeout: 5000 })
    const dateInput = page.locator('input[type="date"]')
    await expect(dateInput).toBeVisible()
  })

  test('клиенты: вкладка и контент', async ({ page }) => {
    await page.getByRole('tab', { name: 'Клиенты' }).click()
    await expect(page.getByRole('heading', { name: 'Клиенты' })).toBeVisible({ timeout: 5000 })
  })

  test('настройки: вкладка и контент', async ({ page }) => {
    await page.getByRole('tab', { name: 'Настройки' }).click()
    await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Сохранить' }).first()).toBeVisible({ timeout: 10000 })
  })

  test('закрытия: вкладка', async ({ page }) => {
    await page.getByRole('tab', { name: 'Закрытия' }).click()
    await expect(page.getByRole('heading', { name: 'Закрытия' })).toBeVisible({ timeout: 5000 })
  })

  test('расписание: смена даты загружает записи', async ({ page }) => {
    const dateInput = page.locator('input[type="date"]').first()
    await dateInput.waitFor({ state: 'visible', timeout: 5000 })
    await dateInput.fill('2030-02-15')
    await expect(page.getByText('Нет записей.').or(page.locator('.shell__appointment-item'))).toBeVisible({ timeout: 5000 })
  })

  test('закрытия: кнопка Закрыть и поля формы', async ({ page }) => {
    await page.getByRole('tab', { name: 'Закрытия' }).click()
    await expect(page.getByRole('heading', { name: 'Закрытия' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Закрыть' })).toBeVisible()
    await expect(page.locator('input[type="date"]').first()).toBeVisible()
  })
})
