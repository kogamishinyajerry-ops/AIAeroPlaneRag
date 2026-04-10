const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 1,
  use: {
    headless: true,
    baseURL: 'http://localhost:8000',
  },
  webServer: {
    command: 'cd /Users/Zhuanz/AIAeroPlaneRag && python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000',
    url: 'http://localhost:8000/',
    reuseExistingServer: true,
    timeout: 30000,
  },
  reporter: [['list']],
});
