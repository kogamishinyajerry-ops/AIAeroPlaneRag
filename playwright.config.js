const { defineConfig } = require('@playwright/test');
const path = require('path');

// Resolve project root regardless of cwd (local dev or CI)
const REPO_ROOT = process.env.REPO_ROOT || path.resolve(__dirname);

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: process.env.CI ? 2 : 1,
  use: {
    headless: true,
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
  },
  webServer: {
    command: 'python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000',
    cwd: REPO_ROOT,
    url: 'http://localhost:8000/',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
  reporter: [
    ['list'],
    ['json', { outputFile: 'benchmarks/e2e_report.json' }],
  ],
});
