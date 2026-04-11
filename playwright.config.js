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

  // Named project so CI can target --project=chromium
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],

  webServer: {
    // FastAPI backend: runs in offline/mock mode when API keys are absent
    command: 'python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000',
    cwd: REPO_ROOT,
    url: 'http://localhost:8000/',
    reuseExistingServer: !process.env.CI,
    timeout: 90000,
    env: {
      // Propagate PYTHONPATH so uvicorn can find src.*
      PYTHONPATH: REPO_ROOT,
      APP_MODE: process.env.APP_MODE || 'mock',
      OLLAMA_API_KEY: '',
      EMBEDDING_API_KEY: '',
    },
  },

  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'benchmarks/e2e_report.json' }],
  ],
});
