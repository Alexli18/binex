import { test, expect } from '@playwright/test';

test.describe('Trace Page', () => {
  test('trace page renders timeline or empty state', async ({ page }) => {
    await page.goto('/');
    const runLink = page.locator('a[href*="/runs/"]').first();

    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await runLink.getAttribute('href');
      await page.goto(`${href}/trace`);

      // Should show timeline header or loading/empty state
      await expect(
        page.getByText('Trace Timeline').or(page.getByText('Loading')).or(page.getByText('No timeline')),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('trace page shows legend', async ({ page }) => {
    await page.goto('/');
    const runLink = page.locator('a[href*="/runs/"]').first();

    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await runLink.getAttribute('href');
      await page.goto(`${href}/trace`);

      // Legend items should be visible
      await expect(
        page.getByText('Completed').or(page.getByText('Failed')),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('trace page has navigation links', async ({ page }) => {
    await page.goto('/');
    const runLink = page.locator('a[href*="/runs/"]').first();

    if (await runLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await runLink.getAttribute('href');
      await page.goto(`${href}/trace`);

      // Should have Debug and Diagnose links
      await expect(
        page.getByText('Debug').or(page.getByText('Diagnose')),
      ).toBeVisible({ timeout: 5000 });
    }
  });
});
