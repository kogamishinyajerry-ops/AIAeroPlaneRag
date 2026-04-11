/**
 * Graph Virtualization Unit Tests
 * ================================
 * Phase 3 验收: 视口裁剪 + LOD 三级标签
 *
 * 测试范围:
 *   1. getLodLevel(scale)           — 三级 LOD 阈值逻辑
 *   2. getViewportBounds(t, w, h)   — 屏幕坐标 → 数据坐标转换
 *   3. isNodeInViewport(d, bounds)  — 节点视口裁剪判断
 *   4. Edge culling helpers         — 边随端点隐藏
 *
 * 运行:
 *   node tests/unit/test_graph_virtualization.js
 */

"use strict";

// ── Paste-in copies of the functions under test (pure logic only) ─────────────
// These are extracted from ui/app.js so we can test without a DOM.

const LOD_HIGH_THRESHOLD = 1.5;
const LOD_LOW_THRESHOLD  = 0.5;
const VIEWPORT_PADDING   = 60;

/**
 * @param {number} scale  current D3 zoom k
 * @returns {'low'|'medium'|'high'}
 */
function getLodLevel(scale) {
    if (scale >= LOD_HIGH_THRESHOLD) return "high";
    if (scale <= LOD_LOW_THRESHOLD)  return "low";
    return "medium";
}

/**
 * Convert screen viewport corners to data coordinates.
 * Mirrors the formula in app.js getViewportBounds().
 *
 * @param {{x: number, y: number, k: number}} t  D3 zoom transform
 * @param {number} width   SVG canvas pixel width
 * @param {number} height  SVG canvas pixel height
 * @returns {{xMin: number, xMax: number, yMin: number, yMax: number}}
 */
function getViewportBounds(t, width, height) {
    const xMin = -t.x / t.k - VIEWPORT_PADDING;
    const xMax = (-t.x + width) / t.k + VIEWPORT_PADDING;
    const yMin = -t.y / t.k - VIEWPORT_PADDING;
    const yMax = (-t.y + height) / t.k + VIEWPORT_PADDING;
    return { xMin, xMax, yMin, yMax };
}

/**
 * Returns true when a node's (x, y) falls inside the given bounds.
 *
 * @param {{x: number, y: number}} d       node datum
 * @param {{xMin, xMax, yMin, yMax}} bounds
 * @returns {boolean}
 */
function isNodeInViewport(d, bounds) {
    return (
        d.x >= bounds.xMin && d.x <= bounds.xMax &&
        d.y >= bounds.yMin && d.y <= bounds.yMax
    );
}

/**
 * A link should be hidden only when BOTH endpoints are outside the viewport.
 *
 * @param {{id: string}} src
 * @param {{id: string}} tgt
 * @param {Set<string>} hiddenNodeIds
 * @returns {boolean}
 */
function shouldHideEdge(src, tgt, hiddenNodeIds) {
    return hiddenNodeIds.has(src.id) && hiddenNodeIds.has(tgt.id);
}


// ── Micro test framework ───────────────────────────────────────────────────────
let passed = 0;
let failed = 0;

function assertEqual(actual, expected, testName) {
    if (actual === expected) {
        console.log(`  ✓ ${testName}`);
        passed++;
    } else {
        console.error(`  ✗ ${testName}`);
        console.error(`    Expected: ${JSON.stringify(expected)}, Got: ${JSON.stringify(actual)}`);
        failed++;
    }
}

function assertApprox(actual, expected, testName, eps = 1e-9) {
    if (Math.abs(actual - expected) <= eps) {
        console.log(`  ✓ ${testName}`);
        passed++;
    } else {
        console.error(`  ✗ ${testName}`);
        console.error(`    Expected ~${expected}, Got ${actual}`);
        failed++;
    }
}

function assertTrue(cond, testName) {
    if (cond) {
        console.log(`  ✓ ${testName}`);
        passed++;
    } else {
        console.error(`  ✗ ${testName}`);
        console.error(`    Expected truthy, got: ${cond}`);
        failed++;
    }
}

function assertFalse(cond, testName) {
    assertTrue(!cond, testName);
}


// ── Section 1: getLodLevel ─────────────────────────────────────────────────────
console.log("\n=== getLodLevel — 三级 LOD 阈值 ===\n");

assertEqual(getLodLevel(2.0),  "high",   "scale=2.0 → high");
assertEqual(getLodLevel(1.5),  "high",   "scale=1.5 (exactly HIGH threshold) → high");
assertEqual(getLodLevel(1.51), "high",   "scale=1.51 → high");
assertEqual(getLodLevel(1.0),  "medium", "scale=1.0 → medium");
assertEqual(getLodLevel(0.75), "medium", "scale=0.75 → medium");
assertEqual(getLodLevel(0.51), "medium", "scale=0.51 → medium");
assertEqual(getLodLevel(0.5),  "low",    "scale=0.5 (exactly LOW threshold) → low");
assertEqual(getLodLevel(0.3),  "low",    "scale=0.3 → low");
assertEqual(getLodLevel(0.1),  "low",    "scale=0.1 → low");


// ── Section 2: getViewportBounds — coordinate transform ──────────────────────
console.log("\n=== getViewportBounds — 数据坐标转换 ===\n");

// Identity transform: t = {x:0, y:0, k:1}, canvas 800×550
{
    const t = { x: 0, y: 0, k: 1 };
    const b = getViewportBounds(t, 800, 550);
    assertApprox(b.xMin, -VIEWPORT_PADDING,      "identity: xMin = -PADDING");
    assertApprox(b.xMax, 800 + VIEWPORT_PADDING, "identity: xMax = width + PADDING");
    assertApprox(b.yMin, -VIEWPORT_PADDING,      "identity: yMin = -PADDING");
    assertApprox(b.yMax, 550 + VIEWPORT_PADDING, "identity: yMax = height + PADDING");
}

// Zoomed in 2× at origin
{
    const t = { x: 0, y: 0, k: 2 };
    const b = getViewportBounds(t, 800, 550);
    // Data coords shown on screen = [0, width/k] = [0, 400]
    assertApprox(b.xMin, -VIEWPORT_PADDING,           "zoom2x@origin: xMin");
    assertApprox(b.xMax, 800 / 2 + VIEWPORT_PADDING,  "zoom2x@origin: xMax = 400 + PADDING");
    assertApprox(b.yMin, -VIEWPORT_PADDING,           "zoom2x@origin: yMin");
    assertApprox(b.yMax, 550 / 2 + VIEWPORT_PADDING,  "zoom2x@origin: yMax = 275 + PADDING");
}

// Panned right by 200px, scale=1
{
    const t = { x: -200, y: 0, k: 1 };
    const b = getViewportBounds(t, 800, 550);
    // xMin = -(-200)/1 - PAD = 200 - 60 = 140
    assertApprox(b.xMin, 200 - VIEWPORT_PADDING,        "pan-right: xMin = 200 - PADDING");
    assertApprox(b.xMax, (200 + 800) + VIEWPORT_PADDING,"pan-right: xMax = 1000 + PADDING");
}

// Zoomed out to 0.5× at origin
{
    const t = { x: 0, y: 0, k: 0.5 };
    const b = getViewportBounds(t, 800, 550);
    assertApprox(b.xMax, 800 / 0.5 + VIEWPORT_PADDING, "zoom0.5x: xMax = 1600 + PADDING");
}

// Bounds xMin < xMax and yMin < yMax always
{
    const transforms = [
        { x: 0,    y: 0,    k: 1   },
        { x: -100, y: -80,  k: 1.5 },
        { x: 300,  y: 200,  k: 0.3 },
    ];
    for (const t of transforms) {
        const b = getViewportBounds(t, 800, 550);
        assertTrue(b.xMin < b.xMax, `xMin<xMax for t=${JSON.stringify(t)}`);
        assertTrue(b.yMin < b.yMax, `yMin<yMax for t=${JSON.stringify(t)}`);
    }
}


// ── Section 3: isNodeInViewport — node culling ────────────────────────────────
console.log("\n=== isNodeInViewport — 节点视口裁剪 ===\n");

const sampleBounds = { xMin: 0, xMax: 800, yMin: 0, yMax: 550 };

assertTrue( isNodeInViewport({ x: 400, y: 275 }, sampleBounds), "center node in view");
assertTrue( isNodeInViewport({ x: 0,   y: 0   }, sampleBounds), "top-left corner in view");
assertTrue( isNodeInViewport({ x: 800, y: 550 }, sampleBounds), "bottom-right corner in view");
assertFalse(isNodeInViewport({ x: -1,  y: 275 }, sampleBounds), "x just left of xMin → culled");
assertFalse(isNodeInViewport({ x: 801, y: 275 }, sampleBounds), "x just right of xMax → culled");
assertFalse(isNodeInViewport({ x: 400, y: -1  }, sampleBounds), "y above yMin → culled");
assertFalse(isNodeInViewport({ x: 400, y: 551 }, sampleBounds), "y below yMax → culled");
assertFalse(isNodeInViewport({ x: -999, y: -999 }, sampleBounds), "far off-screen → culled");

// Bounds from panned transform — only nodes in [200-PAD, 1000+PAD] are visible
{
    const t = { x: -200, y: 0, k: 1 };
    const b = getViewportBounds(t, 800, 550);
    assertTrue( isNodeInViewport({ x: 600, y: 100 }, b), "panned: x=600 in view");
    assertFalse(isNodeInViewport({ x: 50,  y: 100 }, b), "panned: x=50 out of view");
}


// ── Section 4: shouldHideEdge — edge culling ─────────────────────────────────
console.log("\n=== shouldHideEdge — 边随端点裁剪 ===\n");

const hiddenSet = new Set(["n3", "n4"]);

assertFalse(shouldHideEdge({ id: "n1" }, { id: "n2" }, hiddenSet), "both visible → show edge");
assertFalse(shouldHideEdge({ id: "n1" }, { id: "n3" }, hiddenSet), "one hidden → still show");
assertFalse(shouldHideEdge({ id: "n3" }, { id: "n1" }, hiddenSet), "one hidden (reversed) → still show");
assertTrue( shouldHideEdge({ id: "n3" }, { id: "n4" }, hiddenSet), "both hidden → hide edge");
assertTrue( shouldHideEdge({ id: "n4" }, { id: "n3" }, hiddenSet), "both hidden reversed → hide edge");


// ── Summary ───────────────────────────────────────────────────────────────────
console.log(`\n${"=".repeat(45)}`);
const total = passed + failed;
console.log(`Graph Virtualization Tests: ${passed}/${total} passed`);
if (failed > 0) {
    console.error(`❌ ${failed} test(s) FAILED`);
    process.exit(1);
} else {
    console.log("✅ All graph virtualization tests passed");
    process.exit(0);
}
