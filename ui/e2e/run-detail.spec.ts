import { test, expect } from '@playwright/test';

test.describe('Run Detail', () => {
  // Navigate to a completed run via Dashboard (client-side routing works)
  async function navigateToCompletedRun(page: import('@playwright/test').Page) {
    await page.goto('/');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    // Filter by completed
    await page.getByLabel('Filter by status').selectOption('completed');
    await expect(page.locator('tbody tr').first()).toBeVisible({ timeout: 5000 });

    // Click first completed run
    const link = page.locator('tbody tr:first-child td:first-child a');
    const runId = await link.textContent();
    await link.click();

    // Wait for run detail to load
    await expect(page.getByText('Run ID')).toBeVisible({ timeout: 10000 });
    return runId!;
  }

  test('shows run header with status, nodes, cost', async ({ page }) => {
    await navigateToCompletedRun(page);

    // Breadcrumb
    await expect(page.locator('a[href="/"]').filter({ hasText: 'Dashboard' })).toBeVisible();

    // Run header info
    await expect(page.getByText('Nodes')).toBeVisible();
    await expect(page.getByText('Duration')).toBeVisible();
    await expect(page.getByText('Total Cost')).toBeVisible();

    // Status badge
    await expect(page.locator('text=completed').first()).toBeVisible();
  });

  test('shows execution records or empty state', async ({ page }) => {
    await navigateToCompletedRun(page);

    // Should have React Flow graph or "No execution records" message
    const graphOrEmpty = page.locator('.react-flow').or(page.getByText('No execution records yet'));
    await expect(graphOrEmpty).toBeVisible({ timeout: 10000 });
  });

  test('has Artifacts and Costs tabs', async ({ page }) => {
    await navigateToCompletedRun(page);

    await expect(page.getByRole('button', { name: 'Artifacts' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Costs' })).toBeVisible();

    // Default tab should be Artifacts (active styling)
    await expect(page.getByRole('button', { name: 'Artifacts' })).toHaveClass(/border-blue-600/);
  });

  test('switching to Costs tab shows cost data', async ({ page }) => {
    await navigateToCompletedRun(page);

    // Click Costs tab
    await page.getByRole('button', { name: 'Costs' }).click();

    // Should show cost content — either a table or "No cost records"
    const noCosts = page.getByText('No cost records');
    const totalCost = page.getByText('Total:');
    await expect(noCosts.or(totalCost)).toBeVisible({ timeout: 5000 });
  });

  test('breadcrumb Dashboard link navigates back', async ({ page }) => {
    await navigateToCompletedRun(page);

    // Click the breadcrumb Dashboard link
    await page.locator('a[href="/"]').filter({ hasText: 'Dashboard' }).click();
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('non-existent run shows error or not found', async ({ page }) => {
    await page.goto('/');
    // Navigate directly via URL change
    await page.evaluate(() => window.history.pushState({}, '', '/runs/nonexistent_run_12345'));
    await page.goto('/runs/nonexistent_run_12345');

    // Should show error or "not found" or "Run not found"
    const error = page.getByText(/not found|Failed to load/i);
    await expect(error).toBeVisible({ timeout: 10000 });
  });
});
