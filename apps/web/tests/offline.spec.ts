import { expect, test } from '@playwright/test'

test('draft remains usable after the app goes offline', async ({ page, context }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Recommended now' })).toBeVisible()
  await expect(page.getByTestId('offline-status')).toHaveAttribute('data-ready', 'true', { timeout: 60_000 })
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.reload()

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByTestId('offline-status')).toHaveAttribute('data-ready', 'true')

  const search = page.getByLabel('Search available players')
  const mockRound = [
    'CeeDee Lamb',
    'Tyreek Hill',
    'Breece Hall',
    'Bijan Robinson',
    'Amon-Ra St. Brown',
    'Justin Jefferson',
    'A.J. Brown',
    'Jahmyr Gibbs',
    'Puka Nacua',
    'Jonathan Taylor',
    'Saquon Barkley',
    'Garrett Wilson'
  ]
  const entryTimes: number[] = []
  for (const name of mockRound) {
    const started = Date.now()
    await search.fill(name)
    await search.press('Enter')
    await expect(page.getByText(name).last()).toBeVisible()
    entryTimes.push(Date.now() - started)
  }

  await expect(page.getByRole('heading', { name: 'Pick history' })).toBeVisible()
  expect(Math.max(...entryTimes)).toBeLessThan(2_000)
  await page.getByRole('button', { name: '↶ Undo last' }).click()
  const history = page.getByRole('heading', { name: 'Pick history' }).locator('xpath=ancestor::section[1]')
  await expect(history.locator('ol > li')).toHaveCount(11)
})
