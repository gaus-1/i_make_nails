import { expect } from '@playwright/test'
import { test } from '@playwright/test'

const MASTER_ID = process.env.E2E_MASTER_TELEGRAM_ID ?? '111'

test.describe('Панель мастера', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/?view=master&telegram_id=${MASTER_ID}`)
  })

  test('вход: табы Расписание, Клиенты, Настройки, Закрытые даты', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Расписание' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Клиенты' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Настройки' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Закрытые даты' })).toBeVisible()
  })

  test('расписание дня: заголовок и дата', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Расписание дня' })).toBeVisible({ timeout: 5000 })
    const dateInput = page.locator('input[type="date"]')
    await expect(dateInput).toBeVisible()
  })

  test('клиенты: вкладка и контент', async ({ page }) => {
    await page.getByRole('button', { name: 'Клиенты' }).click()
    await expect(page.getByRole('heading', { name: 'Клиенты' })).toBeVisible({ timeout: 5000 })
  })

  test('настройки: вкладка и контент', async ({ page }) => {
    await page.getByRole('button', { name: 'Настройки' }).click()
    await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Сохранить' })).toBeVisible()
  })

  test('закрытые даты: вкладка', async ({ page }) => {
    await page.getByRole('button', { name: 'Закрытые даты' }).click()
    await expect(page.getByRole('heading', { name: 'Закрытые даты' })).toBeVisible({ timeout: 5000 })
  })
})
