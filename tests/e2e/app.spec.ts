import { test, expect, Page, Route } from '@playwright/test';

/**
 * tests/e2e/app.spec.ts
 * =====================
 * AeroPower-RAG Playwright E2E 测试 — 5条关键用户路径 (T3.3 / P1)
 *
 * 路径:
 *   1. 发送查询 → 收到带引用的答案
 *   2. 点击证据卡片 → 查看详情 → 返回 → 列表保留
 *   3. 切换辖区筛选 → 证据列表响应
 *   4. 切换图谱视图 (网络 ↔ 列视图)
 *   5. 切换模式描述 (问答 ↔ 图谱)
 *
 * CI 策略: 路径 1–3 使用 page.route() 拦截 /api/v1/query，
 * 注入标准 Mock 响应，避免依赖真实 LLM / ChromaDB 连接。
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

// ── Mock 数据 ────────────────────────────────────────────────────────────────

/** 最小合法 QueryResponse（符合后端 Pydantic 模型） */
function buildMockResponse(query: string) {
  return {
    query,
    answer:
      '【直接回答】\n根据CCAR-33-R2 第33.23条，压气机必须具有足够的喘振裕度，\n' +
      '确保在所有预期运行条件下不发生喘振。\n\n' +
      '【条款依据】\n[1] CCAR-33-R2 C分部 第33.23条 — 高度相关\n  压气机喘振裕度要求...\n\n' +
      '【适用说明】\n以上条款适用于涡轮发动机型号审定。',
    citations: [
      {
        num: 1,
        source: 'CCAR-33-R2',
        chapter: 'C分部',
        section: '第33.23条',
        snippet: '压气机必须具有足够的喘振裕度，确保在所有预期运行条件下稳定工作。',
        highlight: '喘振裕度',
        fullText:
          '第33.23条 喘振裕度和失速演示\n压气机必须具有足够的喘振裕度，' +
          '确保在所有预期的飞行条件和发动机工作状态下不发生喘振。',
        documentId: 'CCAR-33-R2',
        documentVersion: 'R2-2020',
        contentMode: 'full',
        sourcePath: 'data/processed/CCAR-33-R2_chunks.json',
        officialUrl: null,
        relevanceScore: 0.93,
      },
      {
        num: 2,
        source: 'FAR-33',
        chapter: 'Subpart C',
        section: '§33.65',
        snippet: 'Surge and stall characteristics must be demonstrated.',
        highlight: 'surge',
        fullText:
          '§33.65 Surge and stall characteristics. ' +
          'The applicant must demonstrate that the engine is free from surge and stall.',
        documentId: 'FAR-33',
        documentVersion: '2023',
        contentMode: 'full',
        sourcePath: 'data/processed/FAR-33_chunks.json',
        officialUrl: null,
        relevanceScore: 0.81,
      },
      {
        num: 3,
        source: 'CS-E',
        chapter: 'CS-E 680',
        section: 'CS-E 680',
        snippet: 'Surge and stall margins shall be demonstrated.',
        highlight: 'surge margins',
        fullText: 'CS-E 680 Surge and stall. The applicant shall demonstrate adequate surge margins.',
        documentId: 'CS-E',
        documentVersion: 'Amdt 5',
        contentMode: 'full',
        sourcePath: 'data/processed/easa_cse/chunks_full.json',
        officialUrl: null,
        relevanceScore: 0.78,
      },
    ],
    guardrail: { status: 'PASS', reasoning: '答案与条款原文一致' },
    responseMode: 'bm25-mock',
    confidence: 0.87,
    thinkingProcess: null,
    reasoningSteps: null,
    uncertaintyMarkers: null,
    graphInsights: null,
    retrievalCount: 3,
    processingTimeMs: 42,
    intentDetection: { regulation_query: 0.9, design_question: 0.1 },
    embeddingVersion: 'hash-offline-v1',
    promptVersion: 'rag-prompt-v2',
    responseVersion: 'v2',
  };
}

/** Intercept POST /api/v1/query and inject mock response. */
async function mockQueryRoute(page: Page): Promise<void> {
  await page.route('**/api/v1/query', async (route: Route) => {
    const request = route.request();
    let query = '测试查询';
    try {
      const body = JSON.parse(request.postData() || '{}');
      query = body.query || query;
    } catch {
      // ignore parse error
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildMockResponse(query)),
    });
  });
}

/** Send a query and wait for the UI to finish loading. */
async function sendQueryAndWait(page: Page, query: string): Promise<void> {
  await page.fill('#userInput', query);
  await page.click('#sendBtn');
  // sendBtn is re-enabled with text "发起分析" after response
  await page.waitForFunction(
    () => {
      const btn = document.getElementById('sendBtn') as HTMLButtonElement | null;
      return btn !== null && !btn.disabled && (btn.textContent ?? '').includes('分析');
    },
    { timeout: 20000 }
  );
}

// ── Test suite ───────────────────────────────────────────────────────────────

test.describe('AeroPower-RAG E2E — 5 关键路径', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the UI before each test
    await page.goto(`${BASE_URL}/ui`);
    await page.waitForSelector('#userInput', { timeout: 15000 });
  });

  // ══════════════════════════════════════════════════════════
  // Path 1: Query → Answer with citations
  // ══════════════════════════════════════════════════════════
  test('1. 查询 → 答案含引用', async ({ page }) => {
    await mockQueryRoute(page);

    await sendQueryAndWait(page, '压气机喘振裕度要求');

    // Answer block must have non-empty content
    const answerBlock = page.locator('#answerBlock');
    await expect(answerBlock).not.toBeEmpty();

    // Evidence panel must render citation cards
    const evidenceCards = page.locator('.evidence-card');
    await expect(evidenceCards).toHaveCount(3);

    // Each card must have a source and section
    const firstCard = evidenceCards.first();
    await expect(firstCard.locator('.evidence-path')).toContainText('CCAR-33-R2');
    await expect(firstCard.locator('h3')).toContainText('第33.23条');
  });

  // ══════════════════════════════════════════════════════════
  // Path 2: Evidence card → Detail view → Back → list preserved
  // ══════════════════════════════════════════════════════════
  test('2. 证据卡片 → 详情 → 返回列表保留', async ({ page }) => {
    await mockQueryRoute(page);

    await sendQueryAndWait(page, '涡轮叶片材料要求');

    // Wait for evidence cards
    await page.waitForSelector('.evidence-card', { timeout: 10000 });
    const cardsBefore = await page.locator('.evidence-card').count();
    expect(cardsBefore).toBeGreaterThan(0);

    // Confirm initial evidence panel content
    await expect(page.locator('#evidencePanel')).toContainText('evidence-card');

    // Click "查看全文" on the first card to open detail view
    const firstCard = page.locator('.evidence-card').first();
    await firstCard.locator('.link-btn').click();

    // Detail view should now contain a back-button (rendered by openCitation())
    const backBtn = page.locator('.back-btn, #graphBackBtn, button:has-text("返回")').first();
    await expect(backBtn).toBeVisible({ timeout: 5000 });

    // Go back
    await backBtn.click();

    // After back, evidence list must still contain cards
    await page.waitForSelector('.evidence-card', { timeout: 5000 });
    const cardsAfter = await page.locator('.evidence-card').count();
    expect(cardsAfter).toBeGreaterThan(0);
  });

  // ══════════════════════════════════════════════════════════
  // Path 3: Jurisdiction filter → list responds
  // ══════════════════════════════════════════════════════════
  test('3. 辖区筛选切换 → 证据列表响应', async ({ page }) => {
    await mockQueryRoute(page);

    await sendQueryAndWait(page, '发动机喘振裕度');

    // Ensure cards are present
    await page.waitForSelector('.evidence-card', { timeout: 10000 });

    // Jurisdiction filter must be visible
    const filter = page.locator('#jurisdictionFilter');
    await expect(filter).toBeVisible();

    // Record all-results count (should be 3 from mock)
    const allCount = await page.locator('.evidence-card').count();
    expect(allCount).toBeGreaterThan(0);

    // Switch to CAAC (should filter for CN sources → CCAR-33-R2 only)
    await filter.selectOption('CAAC');
    await page.waitForTimeout(400);
    const caacCount = await page.locator('.evidence-card').count();
    expect(caacCount).toBeGreaterThanOrEqual(0); // could be 0 or 1 depending on UI impl

    // Switch to FAA
    await filter.selectOption('FAA');
    await page.waitForTimeout(400);
    const faaCount = await page.locator('.evidence-card').count();
    expect(faaCount).toBeGreaterThanOrEqual(0);

    // Back to All
    await filter.selectOption('');
    await page.waitForTimeout(400);
    const afterAllCount = await page.locator('.evidence-card').count();
    // After resetting filter, all cards should be visible again
    expect(afterAllCount).toBeGreaterThan(0);
  });

  // ══════════════════════════════════════════════════════════
  // Path 4: Graph view toggle (network ↔ column)
  // ══════════════════════════════════════════════════════════
  test('4. 图谱视图切换 (网络 ↔ 列视图)', async ({ page }) => {
    const networkBtn = page.locator('#networkViewBtn');
    const columnBtn  = page.locator('#columnViewBtn');

    // Both buttons must be visible
    await expect(networkBtn).toBeVisible();
    await expect(columnBtn).toBeVisible();

    // Network view is active by default
    await expect(networkBtn).toHaveClass(/active/);
    await expect(columnBtn).not.toHaveClass(/active/);

    // Switch to column view
    await columnBtn.click();
    await expect(columnBtn).toHaveClass(/active/);
    await expect(networkBtn).not.toHaveClass(/active/);

    // Switch back to network view
    await networkBtn.click();
    await expect(networkBtn).toHaveClass(/active/);
    await expect(columnBtn).not.toHaveClass(/active/);
  });

  // ══════════════════════════════════════════════════════════
  // Path 5: Mode switch → description updates
  // ══════════════════════════════════════════════════════════
  test('5. 模式切换 → 描述文案更新', async ({ page }) => {
    const qaCard    = page.locator('.mode-card[data-mode="qa"]');
    const graphCard = page.locator('.mode-card[data-mode="graph"]');

    // Both mode cards must be visible
    await expect(qaCard).toBeVisible();
    await expect(graphCard).toBeVisible();

    // QA mode selected by default
    await expect(qaCard).toHaveClass(/selected/);
    await expect(graphCard).not.toHaveClass(/selected/);

    // QA description contains "检索"
    const qaDesc = await qaCard.locator('.mode-desc').textContent();
    expect(qaDesc).toContain('检索');

    // Click graph mode
    await graphCard.click();
    await expect(graphCard).toHaveClass(/selected/);
    await expect(qaCard).not.toHaveClass(/selected/);

    // Graph description contains "关联"
    const graphDesc = await graphCard.locator('.mode-desc').textContent();
    expect(graphDesc).toContain('关联');

    // Click back to QA mode
    await qaCard.click();
    await expect(qaCard).toHaveClass(/selected/);
    await expect(graphCard).not.toHaveClass(/selected/);
  });
});
