import { expect, test } from '@playwright/test'

test.describe('player pool ADP source', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Opening your local draft room…')).toBeHidden({ timeout: 30_000 })
    await expect(page.getByText('Player pool')).toBeVisible()
  })

  test('keeps one ADP column and can switch sources from the header', async ({ page }) => {
    const firstRow = page.locator('section', { hasText: 'Player pool' }).locator('tbody tr').first()
    await expect(firstRow).toContainText("Ja'Marr Chase")
    await expect(firstRow).toContainText('1.4')

    await page.getByRole('button', { name: 'ADP source, FantasyPros' }).click()
    await expect(page.getByRole('menu', { name: 'ADP source' })).toBeVisible()
    await page.getByRole('menuitemradio', { name: 'ESPN' }).click()
    await expect(page.getByRole('button', { name: 'ADP source, ESPN' })).toBeVisible()
    const espnFirst = page.locator('section', { hasText: 'Player pool' }).locator('tbody tr').first()
    await expect(espnFirst).toContainText('Jahmyr Gibbs')
    await expect(espnFirst).toContainText('1.35')

    await page.getByRole('button', { name: 'ADP source, ESPN' }).click()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('menu', { name: 'ADP source' })).toHaveCount(0)
  })

  test('ADP header still fits on a narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByRole('button', { name: 'ADP source, FantasyPros' })).toBeVisible()
    const pool = page.locator('section', { hasText: 'Player pool' })
    await expect(pool).not.toHaveCSS('overflow-x', 'scroll')
  })
})
