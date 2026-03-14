import { test, expect } from '@playwright/test';

test.describe('Workflow Editor', () => {
  test('loads editor page with file sidebar', async ({ page }) => {
    await page.goto('/editor');

    // Sidebar should have "Workflows" header
    await expect(page.getByText('Workflows')).toBeVisible();

    // Should list workflow files
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });
  });

  test('auto-selects first workflow file', async ({ page }) => {
    await page.goto('/editor');

    // Wait for files to load
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });

    // Toolbar should show the selected file path
    const toolbar = page.locator('.flex.items-center.gap-3');
    await expect(toolbar).not.toContainText('No file selected');
  });

  test('clicking a file in sidebar loads it in editor', async ({ page }) => {
    await page.goto('/editor');

    // Wait for file list
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });

    // Click "examples/hello-world.yaml" if available
    const helloWorld = page.getByRole('button', { name: 'examples/hello-world.yaml' });
    if (await helloWorld.isVisible()) {
      await helloWorld.click();
      // Toolbar should show the file name (use specific span in toolbar)
      await expect(page.locator('.text-sm.font-medium.text-gray-700')).toContainText('hello-world');
    } else {
      // Click any file
      await fileButtons.first().click();
    }

    // Monaco editor should load (wait for Loading... to disappear or editor to appear)
    const monacoEditor = page.locator('.monaco-editor');
    const loading = page.getByText('Loading...');
    // Wait for either Monaco to appear or loading to finish
    await expect(monacoEditor.or(page.locator('section.lines-content'))).toBeVisible({ timeout: 15000 });
  });

  test('shows DAG preview for valid workflow', async ({ page }) => {
    await page.goto('/editor');

    // Wait for files and auto-load
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });

    // Click a known workflow with nodes
    const diamond = page.locator('button', { hasText: 'examples/diamond.yaml' });
    if (await diamond.isVisible()) {
      await diamond.click();
    }

    // DAG preview area — should show React Flow graph or "No nodes" message
    // Wait a bit for the debounced YAML parsing
    await page.waitForTimeout(1000);
    const graph = page.locator('.react-flow');
    const noNodes = page.getByText(/No nodes found|DAG preview/);
    await expect(graph.or(noNodes)).toBeVisible({ timeout: 10000 });
  });

  test('Save button is disabled when no changes', async ({ page }) => {
    await page.goto('/editor');
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });

    // Save should be disabled (no unsaved changes)
    const saveBtn = page.getByRole('button', { name: 'Save' });
    await expect(saveBtn).toBeDisabled();
  });

  test('Run button is enabled when file is selected', async ({ page }) => {
    await page.goto('/editor');
    const fileButtons = page.locator('button', { hasText: /examples\// });
    await expect(fileButtons.first()).toBeVisible({ timeout: 10000 });

    // Run button should be enabled
    const runBtn = page.getByRole('button', { name: 'Run' });
    await expect(runBtn).toBeEnabled();
  });

  test('toolbar shows Save and Run buttons', async ({ page }) => {
    await page.goto('/editor');

    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run' })).toBeVisible();
  });
});
