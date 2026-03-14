import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('loads and shows runs table', async ({ page }) => {
    await page.goto('/');
    // Navigation should be visible
    await expect(page.locator('nav')).toContainText('Binex');
    await expect(page.locator('nav')).toContainText('Dashboard');
    await expect(page.locator('nav')).toContainText('Editor');

    // Dashboard heading
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Runs table should load with data
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
    // Should have at least one row
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
  });

  test('status filter narrows results', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    // Count all rows
    const allRows = await page.locator('tbody tr').count();
    expect(allRows).toBeGreaterThan(0);

    // Filter by "completed"
    await page.getByLabel('Filter by status').selectOption('completed');
    // All visible status badges should be "completed"
    const badges = page.locator('tbody tr td:nth-child(3)');
    const count = await badges.count();
    for (let i = 0; i < count; i++) {
      await expect(badges.nth(i)).toContainText(/completed/i);
    }

    // Filter by "failed"
    await page.getByLabel('Filter by status').selectOption('failed');
    const failedBadges = page.locator('tbody tr td:nth-child(3)');
    const failedCount = await failedBadges.count();
    if (failedCount > 0) {
      for (let i = 0; i < failedCount; i++) {
        await expect(failedBadges.nth(i)).toContainText(/failed/i);
      }
    }
  });

  test('search by run ID filters table', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    // Get the first run ID text
    const firstRunLink = page.locator('tbody tr:first-child td:first-child a');
    const runId = await firstRunLink.textContent();
    expect(runId).toBeTruthy();

    // Search for a partial ID
    const partialId = runId!.slice(4, 12); // e.g. "28c7e331"
    await page.getByLabel('Search by run ID').fill(partialId);

    // Should still show matching rows
    const rows = page.locator('tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
    // First result should contain the search term
    await expect(rows.first().locator('td:first-child a')).toContainText(partialId);
  });

  test('search with no match shows empty state', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    // Search for a nonexistent run
    await page.getByLabel('Search by run ID').fill('zzzzzz_nonexistent');
    await expect(page.getByText('No runs found')).toBeVisible();
  });

  test('click run ID navigates to run detail', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    // Find a completed run to click (avoid running runs that redirect to live)
    await page.getByLabel('Filter by status').selectOption('completed');
    const firstLink = page.locator('tbody tr:first-child td:first-child a');
    await expect(firstLink).toBeVisible({ timeout: 5000 });
    const runId = await firstLink.textContent();

    await firstLink.click();

    // Should navigate to run detail page
    await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
    // Run detail should show run info (Run ID label in header)
    await expect(page.getByText('Run ID')).toBeVisible({ timeout: 10000 });
  });

  test('New Run button opens modal', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Click New Run
    await page.getByRole('button', { name: 'New Run' }).click();

    // Modal should appear
    await expect(page.getByRole('heading', { name: 'New Run' })).toBeVisible();
    await expect(page.getByLabel('Select workflow')).toBeVisible();
    await expect(page.getByLabel('Variables')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start Run' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
  });

  test('New Run modal requires workflow selection', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'New Run' }).click();
    await expect(page.getByRole('heading', { name: 'New Run' })).toBeVisible();

    // Click Start Run without selecting workflow
    await page.getByRole('button', { name: 'Start Run' }).click();

    // Should show error
    await expect(page.getByText('Please select a workflow')).toBeVisible();
  });

  test('New Run modal cancel closes it', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'New Run' }).click();
    await expect(page.getByRole('heading', { name: 'New Run' })).toBeVisible();

    // Click Cancel
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'New Run' })).not.toBeVisible();
  });

  test('New Run modal lists workflows', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'New Run' }).click();

    // Wait for workflows to load in the select
    const select = page.getByLabel('Select workflow');
    await expect(select).toBeVisible();

    // Should have options beyond the default "--Select--"
    const options = select.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThan(1); // First is placeholder
  });
});
