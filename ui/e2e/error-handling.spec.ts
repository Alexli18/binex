import { test, expect } from '@playwright/test';

test.describe('Error Handling', () => {
  test('404 page for unknown routes', async ({ page }) => {
    await page.goto('/this-page-does-not-exist');

    // Should show 404 or "not found" message
    await expect(
      page.getByText('404').or(page.getByText('Not Found')).or(page.getByText('not found')),
    ).toBeVisible({ timeout: 5000 });
  });

  test('invalid run ID shows error or empty state', async ({ page }) => {
    await page.goto('/runs/non-existent-run-id-12345');

    // Should show error state or not found
    await expect(
      page
        .getByText('error')
        .or(page.getByText('not found'))
        .or(page.getByText('Something went wrong'))
        .or(page.getByText('Loading')),
    ).toBeVisible({ timeout: 5000 });
  });

  test('app does not crash on invalid run debug page', async ({ page }) => {
    await page.goto('/runs/invalid-id/debug');

    // Page should render something — either error state or loading
    await expect(
      page.locator('body'),
    ).not.toBeEmpty();
  });

  test('navigation works after error', async ({ page }) => {
    // Visit invalid page
    await page.goto('/runs/invalid-id');
    await page.waitForTimeout(500);

    // Navigate to home
    await page.goto('/');

    // Home should load correctly
    await expect(
      page.getByText('Runs').or(page.getByText('Dashboard')).or(page.getByText('Binex')),
    ).toBeVisible({ timeout: 5000 });
  });
});
