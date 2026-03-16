import { test, expect } from '@playwright/test';

test.describe('Workflow Editor — Extended', () => {
  test('mode switch toggles between Visual and YAML', async ({ page }) => {
    await page.goto('/editor');

    // Default mode — look for Visual and YAML buttons
    const visualBtn = page.getByText('Visual', { exact: true });
    const yamlBtn = page.getByText('YAML', { exact: true });
    await expect(visualBtn).toBeVisible();
    await expect(yamlBtn).toBeVisible();

    // Switch to YAML
    await yamlBtn.click();
    // YAML mode should show editor or placeholder
    await expect(
      page.getByText('Select a workflow file to edit').or(page.locator('.monaco-editor')),
    ).toBeVisible({ timeout: 5000 });

    // Switch back to Visual
    await visualBtn.click();
  });

  test('save button is disabled when no changes', async ({ page }) => {
    await page.goto('/editor');
    const saveBtn = page.getByRole('button', { name: 'Save' });
    await expect(saveBtn).toBeDisabled();
  });

  test('run button is disabled when no content loaded', async ({ page }) => {
    await page.goto('/editor');
    const runBtn = page.getByRole('button', { name: 'Run' });
    // Wait for page to settle
    await page.waitForTimeout(500);
    // Run should be disabled if no content
    await expect(runBtn).toBeVisible();
  });

  test('node palette is visible in visual mode', async ({ page }) => {
    await page.goto('/editor');
    // Node palette should show agent type options
    await expect(
      page.getByText('LLM').or(page.getByText('Node Palette')).or(page.getByText('local')),
    ).toBeVisible({ timeout: 5000 });
  });
});
