import { test, expect } from '@playwright/test';

test.describe('Navigation & API Health', () => {
  test('API health endpoint returns ok', async ({ page }) => {
    const resp = await page.request.get('/api/v1/health');
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.status).toBe('ok');
  });

  test('runs API returns data', async ({ page }) => {
    const resp = await page.request.get('/api/v1/runs');
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.runs).toBeDefined();
    expect(Array.isArray(data.runs)).toBeTruthy();
  });

  test('workflows API returns only workflow files', async ({ page }) => {
    const resp = await page.request.get('/api/v1/workflows');
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.workflows).toBeDefined();
    // Should not contain non-workflow files
    for (const w of data.workflows) {
      expect(w).not.toContain('node_modules');
      expect(w).not.toContain('tea.yaml');
      expect(w).not.toMatch(/^docker\//);
      expect(w).not.toMatch(/^src\//);
    }
  });

  test('nav Dashboard link goes to /', async ({ page }) => {
    await page.goto('/editor');
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL('/');
  });

  test('nav Editor link goes to /editor', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Editor' }).click();
    await expect(page).toHaveURL('/editor');
  });

  test('SPA fallback: unknown routes serve the app', async ({ page }) => {
    await page.goto('/some/unknown/path');
    // Should render the React app (nav should be present)
    await expect(page.locator('nav')).toContainText('Binex');
  });

  test('static assets load correctly', async ({ page }) => {
    const resp = await page.goto('/');
    expect(resp?.ok()).toBeTruthy();
    // Check that CSS loaded (page should have styled elements)
    await expect(page.locator('nav')).toBeVisible();
  });
});
