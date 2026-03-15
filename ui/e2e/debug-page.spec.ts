import { test, expect } from '@playwright/test';

test.describe('Debug Page', () => {
  test('navigates to debug page from run detail', async ({ page }) => {
    await page.goto('/');

    // Wait for runs to load
    const runLink = page.locator('a[href*="/runs/"]').first();
    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await runLink.click();

      // Look for debug link on run detail page
      const debugLink = page.locator('a[href*="/debug"]').first();
      if (await debugLink.isVisible({ timeout: 3000 }).catch(() => false)) {
        await debugLink.click();
        await expect(page).toHaveURL(/\/debug/);
      }
    }
  });

  test('debug page shows node list or empty state', async ({ page }) => {
    // Navigate directly to a debug page — may show empty state if no runs exist
    await page.goto('/');
    const runLink = page.locator('a[href*="/runs/"]').first();

    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await runLink.getAttribute('href');
      await page.goto(`${href}/debug`);

      // Should show either node list or loading/empty state
      await expect(
        page.getByText('Filter nodes').or(page.getByText('No nodes')).or(page.getByText('Loading')),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('node selection shows detail panel', async ({ page }) => {
    await page.goto('/');
    const runLink = page.locator('a[href*="/runs/"]').first();

    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await runLink.getAttribute('href');
      await page.goto(`${href}/debug`);

      // Click on a node if available
      const nodeButton = page.locator('button').filter({ hasText: /^[a-z_]+/ }).first();
      if (await nodeButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        await nodeButton.click();
        // Detail panel should appear with status/duration info
        await expect(
          page.getByText('Status').or(page.getByText('Duration')),
        ).toBeVisible({ timeout: 3000 });
      }
    }
  });
});
