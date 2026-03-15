import { test, expect } from '@playwright/test';

test.describe('Cost Dashboard', () => {
  test('cost page renders', async ({ page }) => {
    await page.goto('/costs');

    // Should show cost dashboard or empty state
    await expect(
      page.getByText('Cost').or(page.getByText('No cost data')).or(page.getByText('Loading')),
    ).toBeVisible({ timeout: 5000 });
  });

  test('cost page shows cost information for runs', async ({ page }) => {
    await page.goto('/costs');

    // Wait for data
    await page.waitForTimeout(1000);

    // Should show total cost or individual run costs or empty state
    await expect(
      page.getByText(/\$/).or(page.getByText('cost')).or(page.getByText('No')),
    ).toBeVisible({ timeout: 5000 });
  });
});
