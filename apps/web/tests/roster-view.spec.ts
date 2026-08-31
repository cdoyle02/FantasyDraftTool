import { expect, test } from '@playwright/test'

test.describe('team roster view', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Opening your local draft room…')).toBeHidden({ timeout: 30_000 })
    await expect(page.getByTestId('snake-board')).toBeVisible()
  })

  test('board and team views show live picks', async ({ page }) => {
    const search = page.getByLabel('Search available players')
    await search.fill('Justin Jefferson')
    await search.press('Enter')
    await expect(page.getByTestId('snake-board')).toContainText('Justin Jefferson')

    await page.getByTestId('roster-view-team').click()
    await page.getByTestId('roster-team-chip-1').click()
    await expect(page.getByTestId('roster-slot-WR-0')).toContainText('Justin Jefferson')
    await expect(page.getByTestId('roster-slot-QB-0')).toContainText('—')
    await expect(page.getByTestId('team-lineup')).toContainText('FLEX')

    await page.getByTestId('roster-view-board').click()
    await expect(page.getByTestId('roster-team-1')).toBeVisible()
  })

  test('view roster button opens team detail', async ({ page }) => {
    const search = page.getByLabel('Search available players')
    await search.fill('Lamar Jackson')
    await search.press('Enter')

    await page.getByTestId('view-team-1').click()
    await expect(page.getByTestId('roster-view-team')).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByTestId('roster-slot-QB-0')).toContainText('Lamar Jackson')
  })

  test('team chips scroll on narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByTestId('roster-view-team').click()
    await expect(page.getByTestId('roster-team-chip-12')).toBeVisible()
    await page.getByTestId('roster-team-chip-12').click()
    await expect(page.getByTestId('roster-team-detail-12')).toBeVisible()
  })
})
