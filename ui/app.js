// =====================================================
// AeroPower-RAG - Main Application Script
// =====================================================

// Check if D3.js is loaded
if (typeof d3 === "undefined") {
    console.error("[Init] D3.js not loaded! Graph visualization will not work.");
}

const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:${window.location.port}`;

// --- JWT Token Auth ---
// API key for token exchange (used once to get JWT, then discarded from memory)
const STATIC_API_KEY = "test-api-key-12345";  // Only used to obtain JWT

// In-memory JWT token (not stored in localStorage for security)
let _accessToken = null;

// Acquire JWT token on first use
async function _ensureToken() {
    if (_accessToken) return _accessToken;
    try {
        const resp = await fetch(`${API_BASE_URL}/api/v1/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: STATIC_API_KEY }),
        });
        if (!resp.ok) throw new Error(`Token error: ${resp.status}`);
        const data = await resp.json();
        _accessToken = data.access_token;
        return _accessToken;
    } catch (err) {
        console.error("[Auth] Failed to get token:", err);
        // Fallback: return static key so the app can still function
        return STATIC_API_KEY;
    }
}

// Helper function for API calls with JWT Bearer authentication
async function apiFetch(url, options = {}) {
    const token = await _ensureToken();
    const headers = {
        ...options.headers,
        "Authorization": `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
}

// DOM Elements
const userInput = document.getElementById("userInput");
const answerBlock = document.getElementById("answerBlock");
const evidencePanel = document.getElementById("evidencePanel");
const graphViz = document.getElementById("graphViz");
const networkGraphViz = document.getElementById("networkGraphViz");
const graphInspector = document.getElementById("graphInspector");
const graphSummary = document.getElementById("graphSummary");
const guardrailChip = document.getElementById("guardrailChip");
const sourcesTableBody = document.getElementById("sourcesTableBody");
const feedbackPanel = document.getElementById("feedbackPanel");
const feedbackStatus = document.getElementById("feedbackStatus");

// State
let currentCitations = [];
let lastEvidenceListHtml = "";  // 保存证据列表，用于返回
let currentGraphState = null;
let graphHistory = [];
let graphIncludeParameters = false;
let fullGraphMode = false;
let currentGraphView = "network";  // "network" or "column" - display mode
let currentGraphDataType = "full";  // "full" or "subgraph" - data type
let latestQuery = "";
let networkSimulation = null;
let networkZoom = null;
let currentQueryId = null;  // For feedback tracking
let currentFeedback = null;  // Track user's feedback on current answer
let dashboardRefreshInterval = null;  // Dashboard auto-refresh timer

// =====================================================
// Event Listeners
// =====================================================

document.getElementById("sendBtn").addEventListener("click", sendMessage);

// Feedback button handlers
document.querySelectorAll(".feedback-btn").forEach(btn => {
    btn.addEventListener("click", () => handleFeedback(btn.dataset.type));
});

// Event delegation for citation buttons in answer text
answerBlock.addEventListener("click", (event) => {
    const btn = event.target.closest(".citation-ref");
    if (btn) {
        const num = parseInt(btn.textContent, 10);
        if (!isNaN(num)) {
            openCitation(num);
        }
    }
});
document.getElementById("refreshGraphBtn").addEventListener("click", () => loadGraphData(latestQuery));
document.getElementById("graphBackBtn").addEventListener("click", stepBackGraph);
document.getElementById("includeParametersToggle").addEventListener("change", event => {
    graphIncludeParameters = event.target.checked;
    loadGraphData(latestQuery, { resetHistory: true });
});
document.getElementById("fullGraphToggle").addEventListener("change", event => {
    fullGraphMode = event.target.checked;
    loadGraphData(latestQuery, { resetHistory: true });
});
document.getElementById("loadFullGraphBtn").addEventListener("click", loadFullGraph);
document.getElementById("networkViewBtn").addEventListener("click", () => switchGraphView("network"));
document.getElementById("columnViewBtn").addEventListener("click", () => switchGraphView("column"));
document.getElementById("layerFilter").addEventListener("change", () => loadSourceCatalog());
document.getElementById("jurisdictionFilter").addEventListener("change", () => loadSourceCatalog());
document.getElementById("toggleDashboardBtn").addEventListener("click", toggleDashboard);

// Mode card switching - Add click handlers
document.querySelectorAll(".mode-card").forEach(card => {
    card.addEventListener("click", () => {
        // Remove selected from all cards
        document.querySelectorAll(".mode-card").forEach(c => c.classList.remove("selected"));
        // Add selected to clicked card
        card.classList.add("selected");
    });
});

document.querySelectorAll(".quick").forEach(button => {
    button.addEventListener("click", () => {
        userInput.value = button.dataset.prompt || "";
        sendMessage();
    });
});

userInput.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

window.openCitation = openCitation;
window.closeCitationDetail = closeCitationDetail;

// =====================================================
// Bootstrap
// =====================================================

// Wait for D3.js and DOM to be ready
function initApp() {
    if (typeof d3 === "undefined") {
        console.log("[Init] Waiting for D3.js to load...");
        setTimeout(initApp, 100);
        return;
    }
    console.log("[Init] D3.js loaded, initializing application...");
    bootstrap();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    // Small delay to ensure D3.js is ready
    setTimeout(initApp, 100);
}

async function bootstrap() {
    // Initialize view state - sync with HTML defaults
    switchGraphView(currentGraphView);
    console.log("[Bootstrap] Initializing AeroPower-Rag...");
    await Promise.all([
        loadHealth(),
        loadSourceCatalog(),
        loadGraphData("", { resetHistory: true }),
        loadDashboard()  // Load performance dashboard
    ]);
    console.log("[Bootstrap] Complete");
}

// =====================================================
// Health & Stats
// =====================================================

async function loadHealth() {
    try {
        const response = await apiFetch(`${API_BASE_URL}/api/v1/health`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const health = await response.json();

        document.getElementById("metricVersion").textContent = health.app_version || "-";
        document.getElementById("metricKbVersion").textContent = health.knowledge_base_version || "-";
        document.getElementById("graphModeLabel").textContent = health.graph_db || "network";

        document.getElementById("systemStatus").innerHTML = `
            <div class="status-row"><span>后端</span><strong>${health.app_mode || "running"}</strong></div>
            <div class="status-row"><span>知识库</span><strong>${health.vector_db || "chroma"} / ${health.vector_db_count ?? 0}</strong></div>
            <div class="status-row"><span>图谱</span><strong>${health.graph_db || "network"}</strong></div>
            <div class="status-row"><span>Guardrail</span><strong>${health.guardrail || "available"}</strong></div>
        `;
    } catch (error) {
        console.error("Health check failed:", error);
        document.getElementById("systemStatus").innerHTML = `
            <div class="status-row error"><span>连接失败</span><strong>${error.message}</strong></div>
        `;
    }
}

async function loadSourceCatalog() {
    const layer = document.getElementById("layerFilter").value;
    const jurisdiction = document.getElementById("jurisdictionFilter").value;
    const params = new URLSearchParams();
    if (layer) params.set("layer", layer);
    if (jurisdiction) params.set("jurisdiction", jurisdiction);

    try {
        const response = await apiFetch(`${API_BASE_URL}/api/v1/sources?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        const sources = payload.sources || [];

        if (!sources.length) {
            sourcesTableBody.innerHTML = `<tr><td colspan="4" class="table-empty">没有匹配到知识源。</td></tr>`;
            return;
        }

        sourcesTableBody.innerHTML = sources.map(source => `
            <tr>
                <td>
                    <div class="source-title">${escapeHtml(source.title)}</div>
                    <div class="source-summary">${escapeHtml(source.summary || "")}</div>
                </td>
                <td>${escapeHtml(source.authority)}</td>
                <td>${layerLabel(source.layer)}</td>
                <td><span class="status-badge">${escapeHtml(source.status)}</span></td>
            </tr>
        `).join("");
    } catch (error) {
        console.error("Source catalog failed:", error);
        sourcesTableBody.innerHTML = `<tr><td colspan="4" class="table-empty error">知识源加载失败：${escapeHtml(error.message)}</td></tr>`;
    }
}

// =====================================================
// Query & Answer
// =====================================================

// Track search state
let isSearching = false;
let searchStartTime = 0;
const MIN_SEARCH_DURATION = 600; // Minimum display time for loading state (ms)

async function sendMessage() {
    const query = userInput.value.trim();
    if (!query || isSearching) return;

    // Start searching state
    isSearching = true;
    searchStartTime = Date.now();

    // Disable input and button
    const sendBtn = document.getElementById("sendBtn");
    userInput.disabled = true;
    sendBtn.disabled = true;
    sendBtn.textContent = "搜索中...";
    sendBtn.classList.add("loading");

    console.log("[Query] Sending:", query);
    latestQuery = query;
    document.getElementById("currentQueryLabel").textContent = query;

    // Show loading state with spinner
    answerBlock.innerHTML = `
        <div class="loading-state">
            <div class="search-loading">
                <div class="loading-spinner"></div>
                <div>正在检索法规知识库...</div>
                <div class="loading-subtext">分析相关条款和证据</div>
            </div>
        </div>
    `;
    evidencePanel.innerHTML = `
        <div class="loading-state">
            <div class="loading-spinner"></div>
            <div>正在装载证据...</div>
        </div>
    `;

    try {
        const response = await apiFetch(`${API_BASE_URL}/api/v1/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                top_k: 5,
                use_guardrail: true,
                include_graph_subgraph: false,
            }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();

        console.log("[Query] Response received:", {
            hasAnswer: !!payload.answer,
            citationCount: payload.citations?.length || 0,
            retrievalCount: payload.retrievalCount
        });

        // Ensure minimum display time for better UX
        const elapsed = Date.now() - searchStartTime;
        if (elapsed < MIN_SEARCH_DURATION) {
            await new Promise(resolve => setTimeout(resolve, MIN_SEARCH_DURATION - elapsed));
        }

        handleResponse(payload);
        // Extract key nodes from citations for subgraph
        const keyNode = extractKeyNodeFromCitations(payload.citations);
        // Reset fullGraphMode so subgraph can be used if centerNode is available
        fullGraphMode = false;
        await loadGraphData(query, { resetHistory: true, centerNode: keyNode });
    } catch (error) {
        console.error("[Query] Failed:", error);
        answerBlock.innerHTML = `<div class="error-state">查询失败：${escapeHtml(error.message)}</div>`;
        evidencePanel.innerHTML = `<div class="empty-state">本次没有可展示的证据。</div>`;
    } finally {
        // Re-enable input and button
        isSearching = false;
        userInput.disabled = false;
        sendBtn.disabled = false;
        sendBtn.textContent = "发起分析";
        sendBtn.classList.remove("loading");
    }
}

function handleResponse(payload) {
    console.log("[handleResponse] Called with:", {
        hasAnswer: !!payload.answer,
        citationCount: payload.citations?.length || 0,
        retrievalCount: payload.retrievalCount
    });

    currentCitations = payload.citations || [];
    document.getElementById("retrievalCountLabel").textContent = String(payload.retrievalCount || 0);

    const guardrailStatus = payload.guardrail?.status || "UNKNOWN";
    guardrailChip.textContent = `${guardrailStatus} · ${payload.responseMode || "enhanced"}`;
    guardrailChip.className = `guardrail-chip ${guardrailClass(guardrailStatus)}`;

    // 解析结构化答案并渲染
    const answerText = payload.answer || "暂无回答";

    // 处理答案中的特殊标记
    let formattedAnswer = answerText
        .replace(/【([^】]+)】\n?/g, '<div class="section-title">$1</div>')
        .replace(/\n\n/g, '</div><div class="section-content">')
        .replace(/\[(\d+)\]/g, (_, num) => {
            return `<button class="citation-ref" onclick="openCitation(${Number(num)})">${num}</button>`;
        });

    // 如果没有section标记，包裹在answer-text中
    const answerHtml = formattedAnswer.includes('section-title')
        ? formattedAnswer
        : `<div class="direct-answer">${formattedAnswer}</div>`;

    const insightHtml = (payload.graphInsights || [])
        .slice(0, 6)
        .map(item => {
            if (item.type === "node_distribution") {
                const dist = item.data || {};
                return `<span class="insight-pill">节点分布: ${Object.entries(dist).map(([k,v]) => `${k}:${v}`).join(", ")}</span>`;
            } else if (item.type === "sample_relations") {
                return `<span class="insight-pill">示例关系: ${(item.data || []).join(", ")}</span>`;
            }
            return `<span class="insight-pill">${item.type || "洞察"}</span>`;
        })
        .join("");

    console.log("[handleResponse] Rendering answer, answerBlock exists:", !!answerBlock);

    // Build thinking process display
    let thinkingHtml = "";
    if (payload.thinkingProcess) {
        thinkingHtml = `
            <div class="thinking-process">
                <div class="thinking-header">
                    <span class="thinking-icon">🧠</span>
                    <span class="thinking-title">AI思考过程</span>
                    <span class="thinking-provider">${payload.llmProvider || "unknown"} / ${payload.llmModel || "unknown"}</span>
                </div>
                <div class="thinking-content">${escapeHtml(payload.thinkingProcess)}</div>
                ${payload.reasoningSteps && payload.reasoningSteps.length ? `
                    <div class="reasoning-steps">
                        ${payload.reasoningSteps.map(step => `<div class="step">${escapeHtml(step)}</div>`).join("")}
                    </div>
                ` : ""}
            </div>
        `;
    }

    // Build confidence display with diagnostics
    const confScore = payload.confidence ?? 0;
    const confPct = (confScore * 100).toFixed(0);
    const confClass = confScore >= 0.7 ? "high" : confScore >= 0.4 ? "medium" : "low";

    let uncertaintyHtml = "";
    if (payload.uncertaintyMarkers && payload.uncertaintyMarkers.length > 0) {
        uncertaintyHtml = `
            <div class="confidence-diagnostics ${confClass}">
                <div class="diag-header">
                    <span class="diag-icon">${confScore >= 0.7 ? "✅" : confScore >= 0.4 ? "⚠️" : "🔍"}</span>
                    <span>置信度分析 (${confPct}%)</span>
                </div>
                <ul class="diag-list">
                    ${payload.uncertaintyMarkers.map(m => `<li>${escapeHtml(m)}</li>`).join("")}
                </ul>
            </div>
        `;
    }

    answerBlock.innerHTML = `
        ${thinkingHtml}
        <div class="answer-text">${answerHtml}</div>
        ${uncertaintyHtml}
        <div class="answer-meta">
            <div><span>Guardrail</span><strong>${escapeHtml(payload.guardrail?.reasoning || "无")}</strong></div>
            <div><span>检索命中</span><strong>${payload.retrievalCount || 0}</strong></div>
            <div><span>置信度</span><strong class="conf-${confClass}">${confPct}%</strong></div>
        </div>
        <div class="insight-strip">${insightHtml || '<span class="muted-inline">当前未返回图谱洞察。</span>'}</div>
    `;

    // Show feedback panel
    if (feedbackPanel) {
        feedbackPanel.style.display = "block";
        // Reset feedback buttons
        document.querySelectorAll(".feedback-btn").forEach(btn => btn.classList.remove("active"));
        currentFeedback = null;
    }

    // Generate query ID for feedback tracking
    currentQueryId = `q_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    console.log("[handleResponse] Rendering evidence list");
    renderEvidenceList(currentCitations);
}

// =====================================================
// Feedback Handling
// =====================================================

async function handleFeedback(type) {
    const btn = document.querySelector(`.feedback-btn[data-type="${type}"]`);
    if (!btn) return;

    // Toggle active state for thumbs up/down
    if (type === "thumbs_up" || type === "thumbs_down") {
        const isActive = btn.classList.contains("active");

        // Remove active from both thumbs buttons
        document.querySelector('.feedback-btn[data-type="thumbs_up"]')?.classList.remove("active");
        document.querySelector('.feedback-btn[data-type="thumbs_down"]')?.classList.remove("active");

        if (!isActive) {
            btn.classList.add("active");
            currentFeedback = { type, queryId: currentQueryId, query: latestQuery };

            // Show feedback status
            showFeedbackStatus(type === "thumbs_up" ? "感谢您的反馈！" : "感谢反馈，我们会继续改进", "success");
        } else {
            currentFeedback = null;
            hideFeedbackStatus();
        }
    } else if (type === "correct") {
        // For correction, show a prompt
        const correction = prompt("请提供正确的答案或指出错误：");
        if (correction && correction.trim()) {
            currentFeedback = {
                type: "correction",
                queryId: currentQueryId,
                query: latestQuery,
                correction: correction.trim()
            };
            btn.classList.add("active");
            showFeedbackStatus("感谢您的纠正，我们会审核并改进知识库", "success");
            // In production, send this to backend
            console.log("[Feedback] Correction:", currentFeedback);
        }
    }

    // Log feedback (in production, send to backend)
    console.log("[Feedback] User feedback:", currentFeedback);
}

function showFeedbackStatus(message, statusClass = "") {
    if (feedbackStatus) {
        feedbackStatus.textContent = message;
        feedbackStatus.className = `feedback-status show ${statusClass}`;
        // Auto-hide after 3 seconds
        setTimeout(() => {
            hideFeedbackStatus();
        }, 3000);
    }
}

function hideFeedbackStatus() {
    if (feedbackStatus) {
        feedbackStatus.classList.remove("show");
    }
}

function renderEvidenceList(citations) {
    if (!citations.length) {
        evidencePanel.innerHTML = `<div class="empty-state">本次回答没有返回可展示的证据条目。</div>`;
        lastEvidenceListHtml = "";
        return;
    }

    // 保存列表HTML，供openCitation返回时使用
    const listHtml = citations.map(item => {
        const relScore = item.relevanceScore;
        const relClass = relScore !== null && relScore !== undefined
            ? (relScore >= 0.8 ? "high" : relScore >= 0.5 ? "medium" : "low")
            : "";
        const relLabel = relScore !== null && relScore !== undefined
            ? (relScore >= 0.8 ? "✔️高度" : relScore >= 0.5 ? "⚠️中度" : "○低")
            : "";

        return `
        <article class="evidence-card" data-citation="${item.num}">
            <div class="evidence-head">
                <span class="evidence-index">[${item.num}]</span>
                ${relScore !== null && relScore !== undefined ? `<span class="rel-badge ${relClass}">${relLabel} (${(relScore * 100).toFixed(0)}%)</span>` : ""}
                <button class="link-btn" onclick="openCitation(${item.num})">查看全文</button>
            </div>
            <h3>${escapeHtml(item.section || "未知条款")}</h3>
            <div class="evidence-path">${escapeHtml(item.chapter || "")} · ${escapeHtml(item.source || "")}</div>
            <p>${escapeHtml(item.snippet || "")}</p>
        </article>
    `}).join("");

    lastEvidenceListHtml = listHtml;
    evidencePanel.innerHTML = listHtml;
}

function openCitation(num) {
    const citation = currentCitations.find(item => item.num === num);
    if (!citation) return;

    // Relevance score display
    const relScore = citation.relevanceScore;
    const relLabel = relScore !== null && relScore !== undefined
        ? (relScore >= 0.8 ? "✔️高度相关" : relScore >= 0.5 ? "⚠️中度相关" : "○低相关")
        : "";

    // Official URL as clickable link
    const urlHtml = citation.officialUrl
        ? `<a href="${escapeHtml(citation.officialUrl)}" target="_blank" class="official-link">🔗 访问官方原文</a>`
        : `<span class="muted-inline">（无官方链接）</span>`;

    evidencePanel.innerHTML = `
        <article class="evidence-card active">
            <div class="evidence-head">
                <button class="back-btn" onclick="closeCitationDetail()">← 返回证据列表</button>
                <span class="evidence-index">[${citation.num}]</span>
                <span class="evidence-tag">${escapeHtml(citation.documentVersion || "unknown")}</span>
                ${relScore !== null && relScore !== undefined ? `<span class="relevance-tag ${relScore >= 0.8 ? 'high' : relScore >= 0.5 ? 'medium' : 'low'}">${relLabel} (${(relScore * 100).toFixed(0)}%)</span>` : ""}
            </div>
            <h3>${escapeHtml(citation.section || "未知条款")}</h3>
            <div class="evidence-path">${escapeHtml(citation.chapter || "")} · ${escapeHtml(citation.source || "")}</div>
            <p>${escapeHtml((citation.fullText || citation.snippet || "").replace(/\n/g, "<br>"))}</p>
            <div class="evidence-foot">
                <div class="source-url-row">
                    ${urlHtml}
                </div>
                <div class="source-ref">文档路径: ${escapeHtml(citation.sourcePath || citation.source || "")}</div>
            </div>
        </article>
    `;
}

function closeCitationDetail() {
    if (lastEvidenceListHtml) {
        evidencePanel.innerHTML = lastEvidenceListHtml;
    }
}

// =====================================================
// Graph Loading & Rendering
// =====================================================

function extractKeyNodeFromCitations(citations) {
    // Extract a key node ID from citations for subgraph generation
    if (!citations || citations.length === 0) return null;

    // Try to find a document node from the first citation's source
    const firstCitation = citations[0];
    if (firstCitation && firstCitation.source) {
        // Convert source like "CCAR-33-R2_chapters/B-设计与构造总则.md" to node ID format
        let source = firstCitation.source;
        // Remove .md extension
        source = source.replace('.md', '');
        // Extract document prefix (before _chapters)
        const docMatch = source.match(/^([^_]+)/);
        if (docMatch) {
            const docId = "doc:" + docMatch[1];
            console.log("[extractKeyNodeFromCitations] Extracted node ID:", docId);
            return docId;
        }
    }
    return null;
}

async function loadGraphData(query = "", options = {}) {
    const { nodeId = null, resetHistory = false, forceFullGraph = false, centerNode = null } = options;

    // Determine data type based on query and mode
    // centerNode takes priority: if provided, always use subgraph
    const useFullGraph = centerNode ? false : (fullGraphMode || forceFullGraph || (query === "" && !centerNode));

    // Use subgraph endpoint if we have a center node
    let endpoint = "/api/v1/graph/network";
    let params = new URLSearchParams();

    if (centerNode && !useFullGraph) {
        // Use subgraph endpoint for centered subgraph
        endpoint = "/api/v1/graph/subgraph";
        params.set("center_node", centerNode);
        params.set("depth", "2");
        currentGraphDataType = "subgraph";
    } else {
        // Use network endpoint
        if (query && query !== "") {
            params.set("query", query);
        }
        params.set("max_nodes", String(useFullGraph ? 50 : 30));
        params.set("include_inter_doc", "true");
        currentGraphDataType = useFullGraph ? "full" : "subgraph";
    }

    // Auto-switch to column view when loading subgraph data
    if (!useFullGraph && currentGraphView !== "column") {
        console.log("[loadGraphData] Auto-switching to column view for subgraph");
        currentGraphView = "column";
        // Update button states
        document.getElementById("networkViewBtn").classList.remove("active");
        document.getElementById("columnViewBtn").classList.add("active");
        // Switch container visibility
        graphViz.style.display = "flex";
        networkGraphViz.style.display = "none";
    }

    const loadingMsg = useFullGraph ? "正在加载完整知识图谱..." : "正在生成局部解释子图...";

    console.log("[loadGraphData] Loading graph:", {
        query,
        dataType: currentGraphDataType,
        centerNode,
        useFullGraph
    });

    // Show loading in both containers
    graphViz.innerHTML = `<div class="loading-state"><div class="loading-spinner"></div><div>${loadingMsg}</div></div>`;
    networkGraphViz.innerHTML = `<div class="loading-state"><div class="loading-spinner"></div><div>${loadingMsg}</div></div>`;

    try {
        const response = await apiFetch(`${API_BASE_URL}${endpoint}?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const payload = await response.json();

        // Graph API returns nodes/edges directly, status field may not be present
        if (!payload.nodes && !payload.edges) {
            throw new Error(payload.detail || payload.error || "Graph load failed");
        }

        if (resetHistory) {
            graphHistory = [];
        }

        // Store data type in payload for tracking
        payload.dataType = currentGraphDataType;
        payload.query = query;

        currentGraphState = payload;
        renderGraphSubgraph(payload, { pushHistory: true });
    } catch (error) {
        console.error("[loadGraphData] Failed:", error);
        const errorMsg = `<div class="error-state">图谱加载失败：${escapeHtml(error.message)}</div>`;
        graphViz.innerHTML = errorMsg;
        networkGraphViz.innerHTML = errorMsg;
    }
}

function renderGraphSubgraph(payload, options = {}) {
    const { pushHistory = false } = options;

    currentGraphState = payload;
    document.getElementById("graphModeLabel").textContent = payload.mode || "network";
    graphSummary.textContent = `图谱包含 ${payload.nodes?.length || 0} 个节点，${payload.edges?.length || 0} 条关系。`;

    if (pushHistory) {
        const last = graphHistory[graphHistory.length - 1];
        if (!last || JSON.stringify(last) !== JSON.stringify(payload)) {
            graphHistory.push(payload);
        }
    }

    // Validate payload
    if (!payload.nodes || !payload.nodes.length) {
        const emptyMsg = `<div class="empty-state">当前没有可展示的图谱节点。</div>`;
        graphViz.innerHTML = emptyMsg;
        networkGraphViz.innerHTML = emptyMsg;
        return;
    }

    // Render based on current view
    if (currentGraphView === "network") {
        renderNetworkGraph(payload);
    } else {
        renderColumnGraph(payload);
    }
}

function renderNetworkGraph(payload) {
    console.log("[Graph] renderNetworkGraph called with", payload.nodes?.length || 0, "nodes");

    if (!payload.nodes || !payload.nodes.length) {
        networkGraphViz.innerHTML = `<div class="empty-state">当前没有可展示的图谱节点。</div>`;
        return;
    }

    if (!networkGraphViz) {
        console.error("[Graph] networkGraphViz element not found!");
        return;
    }

    if (typeof d3 === "undefined") {
        console.error("[Graph] D3.js not loaded!");
        networkGraphViz.innerHTML = `<div class="error-state">D3.js 库未加载，无法渲染图谱。</div>`;
        return;
    }

    // Stop previous simulation if exists
    if (networkSimulation) {
        console.log("[Graph] Stopping previous simulation");
        networkSimulation.stop();
        networkSimulation = null;
    }

    // Reset virtualization cache on new graph
    resetVirtualizationCache();

    const width = networkGraphViz.clientWidth || 800;
    const height = 550;

    console.log(`[Graph] Canvas: ${width}x${height}, Nodes: ${payload.nodes.length}`);

    // Clear previous graph
    networkGraphViz.innerHTML = "";

    // Create main container and append to DOM FIRST
    const container = document.createElement("div");
    container.id = "networkGraphContainer";
    container.style.cssText = "width: 100%; height: " + height + "px; position: relative;";
    networkGraphViz.appendChild(container);  // Append BEFORE d3.select

    // Create SVG - now the element is in the DOM
    const svg = d3.select("#networkGraphContainer")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    // SVG defs: radial gradients for agency nodes, glow filters, arrow marker
    const defs = svg.append("defs");

    // CAAC radial gradient (red with highlight offset for 3D feel)
    const gradCAAC = defs.append("radialGradient")
        .attr("id", "gradCAAC")
        .attr("cx", "30%").attr("cy", "30%").attr("r", "70%");
    gradCAAC.append("stop").attr("offset", "0%").attr("stop-color", "#ff6b6b");
    gradCAAC.append("stop").attr("offset", "100%").attr("stop-color", "#c0392b");

    // FAA radial gradient (blue)
    const gradFAA = defs.append("radialGradient")
        .attr("id", "gradFAA")
        .attr("cx", "30%").attr("cy", "30%").attr("r", "70%");
    gradFAA.append("stop").attr("offset", "0%").attr("stop-color", "#5dade2");
    gradFAA.append("stop").attr("offset", "100%").attr("stop-color", "#2471a3");

    // EASA radial gradient (green)
    const gradEASA = defs.append("radialGradient")
        .attr("id", "gradEASA")
        .attr("cx", "30%").attr("cy", "30%").attr("r", "70%");
    gradEASA.append("stop").attr("offset", "0%").attr("stop-color", "#58d68d");
    gradEASA.append("stop").attr("offset", "100%").attr("stop-color", "#1e8449");

    // Default node gradient (gray)
    const gradDefault = defs.append("radialGradient")
        .attr("id", "gradDefault")
        .attr("cx", "30%").attr("cy", "30%").attr("r", "70%");
    gradDefault.append("stop").attr("offset", "0%").attr("stop-color", "#95a5a6");
    gradDefault.append("stop").attr("offset", "100%").attr("stop-color", "#5d6d7e");

    // Glow filter for hover
    const glow = defs.append("filter").attr("id", "glow").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    glow.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "coloredBlur");
    const glowMerge = glow.append("feMerge");
    glowMerge.append("feMergeNode").attr("in", "coloredBlur");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Strong glow for selected nodes
    const glowStrong = defs.append("filter").attr("id", "glowStrong").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    glowStrong.append("feGaussianBlur").attr("stdDeviation", "6").attr("result", "coloredBlur");
    const glowStrongMerge = glowStrong.append("feMerge");
    glowStrongMerge.append("feMergeNode").attr("in", "coloredBlur");
    glowStrongMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Direction arrow marker for edges
    defs.append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "#4a5f7f");

    // Add zoom controls
    const controls = document.createElement("div");
    controls.className = "graph-zoom-controls";
    controls.innerHTML = `
        <button class="zoom-btn" id="zoomInBtn">+</button>
        <button class="zoom-btn" id="zoomOutBtn">−</button>
        <button class="zoom-btn" id="zoomResetBtn">⟲</button>
    `;
    container.appendChild(controls);

    // Add stats display
    const stats = document.createElement("div");
    stats.className = "graph-stats";
    stats.style.cssText = "position: absolute; bottom: 10px; left: 10px; padding: 8px 12px; background: rgba(0,0,0,0.7); border-radius: 6px; font-size: 12px; color: #98a8bc; pointer-events: none;";
    stats.innerHTML = `节点: ${payload.nodes.length} | 连接: ${payload.edges?.length || 0}`;
    container.appendChild(stats);

    // Add legend with node counts per agency
    const agencyCounts = { CAAC: 0, FAA: 0, EASA: 0 };
    payload.nodes.forEach(n => {
        const a = inferAgency(n);
        if (a in agencyCounts) agencyCounts[a]++;
    });
    const legend = document.createElement("div");
    legend.className = "graph-legend";
    legend.innerHTML = `
        <div class="legend-item"><div class="legend-color" style="background: #e63946;"></div><span>CAAC</span><span class="legend-count">${agencyCounts.CAAC}</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #3498db;"></div><span>FAA</span><span class="legend-count">${agencyCounts.FAA}</span></div>
        <div class="legend-item"><div class="legend-color" style="background: #2ecc71;"></div><span>EASA</span><span class="legend-count">${agencyCounts.EASA}</span></div>
    `;
    container.appendChild(legend);

    // Create group for zoom
    const g = svg.append("g");

    // Setup zoom
    networkZoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
            scheduleVirtualizationUpdate();
        });

    svg.call(networkZoom);

    // Process data - filter valid edges
    const nodeMap = new Map(payload.nodes.map(n => [n.id, n]));
    const validEdges = (payload.edges || []).filter(e =>
        nodeMap.has(e.source) && nodeMap.has(e.target)
    );

    // Edge type to color mapping
    function getEdgeColor(edge) {
        const t = (edge.type || "").toLowerCase();
        if (t.includes("reference") || t.includes("cite")) return "#5c7aea";
        if (t.includes("certif") || t.includes("approv")) return "#2ecc71";
        if (t.includes("govern") || t.includes("require")) return "#e74c3c";
        if (t.includes("part") || t.includes("compon")) return "#f39c12";
        if (t.includes("relat") || t.includes("connect")) return "#253244";
        return "#4a5f7f";
    }

    // Draw links with curved paths, D3 join animations, directional arrows
    const link = g.append("g")
        .attr("class", "links")
        .selectAll("path")
        .data(validEdges)
        .join(
            enter => {
                const p = enter.append("path")
                    .attr("class", "network-link")
                    .attr("fill", "none")
                    .attr("stroke", d => getEdgeColor(d))
                    .attr("stroke-opacity", 0)
                    .attr("stroke-width", d => Math.sqrt((d.weight || 0.5) * 2) + 0.5)
                    .attr("marker-end", "url(#arrow)")
                    .attr("d", d => {
                        const sx = d.source.x || 0, sy = d.source.y || 0;
                        const tx = d.target.x || 0, ty = d.target.y || 0;
                        return d3.linkHorizontal()({ source: [sx, sy], target: [tx, ty] });
                    });
                p.transition().duration(600).attr("stroke-opacity", 0.55);
                return p;
            },
            update => {
                update
                    .attr("stroke", d => getEdgeColor(d))
                    .attr("stroke-width", d => Math.sqrt((d.weight || 0.5) * 2) + 0.5)
                    .attr("marker-end", "url(#arrow)")
                    .attr("d", d => {
                        const sx = d.source.x || 0, sy = d.source.y || 0;
                        const tx = d.target.x || 0, ty = d.target.y || 0;
                        return d3.linkHorizontal()({ source: [sx, sy], target: [tx, ty] });
                    });
                return update;
            },
            exit => exit.transition().duration(300).attr("stroke-opacity", 0).remove()
        );

    // Draw nodes with D3 join enter/exit animations
    const node = g.append("g")
        .attr("class", "nodes")
        .selectAll(".network-node")
        .data(payload.nodes)
        .join(
            enter => {
                const n = enter.append("g")
                    .attr("class", d => `network-node ${getNodeGroupClass(d)}`)
                    .attr("opacity", 0)
                    .call(d3.drag()
                        .on("start", dragstarted)
                        .on("drag", dragged)
                        .on("end", dragended))
                    .on("click", (event, d) => {
                        event.stopPropagation();
                        renderNodeInspector(d, validEdges, payload.nodes);
                    });

                // Enter animation: circle grows from 0
                n.append("circle")
                    .attr("r", 0)
                    .attr("fill", d => getNodeGradient(d))
                    .attr("fill-opacity", 0.85)
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1.5)
                    .transition().duration(500).ease(d3.easeCubicOut)
                    .attr("r", d => getNodeRadius(d));

                // Enter animation: label fades in
                n.append("text")
                    .attr("dy", d => -getNodeRadius(d) - 5)
                    .attr("text-anchor", "middle")
                    .style("font-size", "10px")
                    .style("fill", "#edf3fb")
                    .style("pointer-events", "none")
                    .attr("opacity", 0)
                    .text(d => {
                        const label = d.label || d.id || "";
                        return label.length > 15 ? label.substring(0, 12) + "..." : label;
                    })
                    .transition().delay(200).duration(300)
                    .attr("opacity", 1);

                return n;
            },
            update => {
                // Update circle fill (agency may have changed) and animate size
                update.select("circle")
                    .transition().duration(300)
                    .attr("r", d => getNodeRadius(d))
                    .attr("fill", d => getNodeGradient(d));
                // Update label dy
                update.select("text")
                    .attr("dy", d => -getNodeRadius(d) - 5)
                    .text(d => {
                        const label = d.label || d.id || "";
                        return label.length > 15 ? label.substring(0, 12) + "..." : label;
                    });
                return update;
            },
            exit => {
                exit.select("circle")
                    .transition().duration(300)
                    .attr("r", 0).remove();
                exit.select("text")
                    .transition().duration(200)
                    .attr("opacity", 0);
                return exit.transition().duration(300).attr("opacity", 0).remove();
            }
        );

    // Setup force simulation - improved for better separation and smoother layout
    const simulation = d3.forceSimulation(payload.nodes)
        .force("link", d3.forceLink(validEdges)
            .id(d => d.id)
            .distance(60)
            .strength(0.2))
        .force("charge", d3.forceManyBody()
            .strength(d => -120 * Math.sqrt((d.size || 5) / 5))
            .distanceMax(200))
        .force("center", d3.forceCenter(width / 2, height / 2).strength(0.08))
        .force("collision", d3.forceCollide()
            .radius(d => 5 + Math.sqrt(d.size || 5))
            .strength(0.7)
            .iterations(2))
        .alphaDecay(0.025)  // Slower decay for finer layout
        .velocityDecay(0.45);  // Dampen velocity

    networkSimulation = simulation;

    // Throttled tick updates for better performance
    let tickCount = 0;
    simulation.on("tick", () => {
        tickCount++;
        // Update every 2nd tick for performance
        if (tickCount % 2 === 0) {
            link.attr("d", d => {
                const sx = d.source.x || 0, sy = d.source.y || 0;
                const tx = d.target.x || 0, ty = d.target.y || 0;
                return d3.linkHorizontal()({ source: [sx, sy], target: [tx, ty] });
            });

            node.attr("transform", d => `translate(${d.x},${d.y})`);
        }
        // Schedule virtualization update (throttled to RAF)
        scheduleVirtualizationUpdate();
    });

    // Zoom button handlers
    document.getElementById("zoomInBtn").addEventListener("click", () => {
        svg.transition().call(networkZoom.scaleBy, 1.3);
    });
    document.getElementById("zoomOutBtn").addEventListener("click", () => {
        svg.transition().call(networkZoom.scaleBy, 0.7);
    });
    document.getElementById("zoomResetBtn").addEventListener("click", () => {
        svg.transition().call(networkZoom.transform, d3.zoomIdentity);
    });

    // Initialize graph enhancements (multi-select, lasso, hover highlight, etc.)
    if (typeof initGraphEnhancements === "function") {
        initGraphEnhancements(svg, g, simulation, validEdges, payload.nodes);
    }

    // Drag functions
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}

function renderColumnGraph(payload) {
    console.log("[renderColumnGraph] Rendering with", payload.nodes?.length || 0, "nodes");

    const lanes = {
        regulation: [],
        component: [],
        support: [],
    };

    // Classify nodes by their semantic type, not by agency
    payload.nodes.forEach(node => {
        const lane = getNodeLane(node);
        if (lanes[lane]) {
            lanes[lane].push(node);
        } else {
            lanes.support.push(node);
        }
    });

    console.log("[renderColumnGraph] Lane counts:", {
        regulation: lanes.regulation.length,
        component: lanes.component.length,
        support: lanes.support.length
    });

    const columns = [
        { key: "regulation", title: "法规 / 条款" },
        { key: "component", title: "部件 / 子系统" },
        { key: "support", title: "支撑节点" },
    ];

    graphViz.innerHTML = columns.map(column => `
        <section class="graph-lane">
            <header>${column.title} (${lanes[column.key].length})</header>
            <div class="graph-node-stack">
                ${lanes[column.key].length
                    ? lanes[column.key]
                        .map(node => renderNodeCard(node, payload.edges || []))
                        .join("")
                    : '<div class="graph-empty-mini">暂无节点</div>'
                }
            </div>
        </section>
    `).join("");

    // Add click handlers
    graphViz.querySelectorAll(".graph-node").forEach(nodeEl => {
        nodeEl.addEventListener("click", () => {
            const nodeId = nodeEl.dataset.nodeId;
            const detail = payload.nodes.find(n => n.id === nodeId);
            if (detail) {
                renderNodeInspector(detail, payload.edges || [], payload.nodes || []);
            }
        });
    });
}

function renderNodeCard(node, edges) {
    const edgeCount = edges.filter(e =>
        e.source === node.id || e.target === node.id ||
        (e.source.id === node.id || e.target.id === node.id)
    ).length;

    // Use title if available (for section nodes), otherwise label
    const displayTitle = node.title || node.label || node.id;
    const displayDesc = node.description || node.doc_name || node.type || "";

    return `
        <article class="graph-node ${getNodeGroupClass(node)}" data-node-id="${escapeHtml(node.id)}">
            <div class="graph-node-head">
                <span class="node-type">${typeLabel(node)}</span>
                <span class="node-group">${escapeHtml(typeof node.group === 'string' ? node.group : '')}</span>
            </div>
            <h3>${escapeHtml(displayTitle)}</h3>
            <p>${escapeHtml(displayDesc)}</p>
            <div class="node-meta">${edgeCount} 条关系</div>
        </article>
    `;
}

function renderNodeInspector(node, edges, nodes) {
    const related = edges
        .filter(edge => edge.source === node.id || edge.target === node.id ||
            (edge.source && edge.source.id === node.id) ||
            (edge.target && edge.target.id === node.id))
        .slice(0, 10)
        .map(edge => {
            const peerId = edge.source === node.id || (edge.source && edge.source.id === node.id)
                ? edge.target || (edge.target && edge.target.id)
                : edge.source || (edge.source && edge.source.id);
            const peer = nodes.find(n => n.id === peerId);
            return `
                <li>
                    <strong>${escapeHtml(edge.type || "related")}</strong>
                    <span>${escapeHtml(peer?.label || peer?.id || peerId)}</span>
                </li>
            `;
        })
        .join("");

    graphInspector.innerHTML = `
        <div class="inspector-node-type">${typeLabel(node)}</div>
        <h3>${escapeHtml(node.label || node.id)}</h3>
        <p>${escapeHtml(node.description || node.type || "暂无描述")}</p>
        <div class="inspector-subtitle">相邻关系</div>
        <ul class="relation-list">
            ${related || "<li>当前节点没有可展示的相邻关系。</li>"}
        </ul>
    `;
}

function switchGraphView(view) {
    console.log("[switchGraphView] Switching to", view);
    currentGraphView = view;
    document.getElementById("networkViewBtn").classList.toggle("active", view === "network");
    document.getElementById("columnViewBtn").classList.toggle("active", view === "column");

    if (view === "network") {
        graphViz.style.display = "none";
        networkGraphViz.style.display = "block";
        console.log("[switchGraphView] networkGraphViz display:", networkGraphViz.style.display);

        if (currentGraphState) {
            // If current data is subgraph, auto-switch to full graph for network view
            if (currentGraphState.dataType === "subgraph") {
                console.log("[switchGraphView] Current data is subgraph, auto-loading full graph for network view");
                fullGraphMode = true;
                document.getElementById("fullGraphToggle").checked = true;
                loadFullGraph();
                return;
            }
            console.log("[switchGraphView] Rendering network graph with", currentGraphState.nodes?.length || 0, "nodes");
            renderNetworkGraph(currentGraphState);
        }
    } else {
        graphViz.style.display = "flex";
        networkGraphViz.style.display = "none";
        console.log("[switchGraphView] graphViz display:", graphViz.style.display);
        if (currentGraphState) {
            renderColumnGraph(currentGraphState);
        }
    }
}

/**
 * Load the full knowledge graph
 */
async function loadFullGraph() {
    console.log("[loadFullGraph] Loading full knowledge graph");
    fullGraphMode = true;
    await loadGraphData("", { resetHistory: true, forceFullGraph: true });
}

function stepBackGraph() {
    if (graphHistory.length <= 1) return;
    graphHistory.pop();
    const previous = graphHistory[graphHistory.length - 1];
    renderGraphSubgraph(previous, { pushHistory: false });
}

// =====================================================
// Helper Functions
// =====================================================

/**
 * Get node lane for column view - based on semantic type
 */
function getNodeLane(node) {
    // First check the node type field
    const nodeType = (node.type || "").toLowerCase();

    // Regulation/document types
    if (nodeType === "document" || nodeType === "section" || nodeType === "regulation") {
        return "regulation";
    }

    // Component/system types
    if (nodeType === "component" || nodeType === "system" || nodeType === "part") {
        return "component";
    }

    // Keyword and concept nodes → classify by context
    if (nodeType === "keyword" || nodeType === "concept" || nodeType === "topic_center") {
        // Keywords that sound like components
        const label = (node.label || "").toLowerCase();
        const componentWords = ["压气机", "涡轮", "燃烧室", "转子", "叶片", "机匣", "轴承",
            "齿轮", "密封", "管路", "传感器", "控制器", "泵", "阀", "喷嘴",
            "系统", "部件", "装置", "组件", "总成"];
        if (componentWords.some(w => label.includes(w))) {
            return "component";
        }
        // Keywords that sound like regulations
        const regWords = ["法规", "条款", "规章", "标准", "适航", "审定", "认证"];
        if (regWords.some(w => label.includes(w))) {
            return "regulation";
        }
        // Generic keywords → support
        return "support";
    }

    // Parameter nodes
    if (nodeType === "parameter" || nodeType === "test_method") {
        return "component";
    }

    // Check ID patterns for classification
    const id = (node.id || "").toLowerCase();
    if (id.startsWith("doc_") || id.startsWith("sec_") || id.includes("ccar") || id.includes("far_") || id.includes("cs_")) {
        return "regulation";
    }
    if (id.startsWith("comp_") || id.startsWith("kw_")) {
        // kw_ nodes: check label for component hints
        const label = (node.label || "").toLowerCase();
        const componentWords = ["压气机", "涡轮", "燃烧室", "转子", "叶片", "发动机"];
        if (componentWords.some(w => label.includes(w))) {
            return "component";
        }
        return "support";
    }

    // Default to support
    return "support";
}

/**
 * Infer agency from document ID or node ID
 */
function inferAgency(node) {
    // First check explicit group field
    const group = node.group || "";
    if (group === "CAAC" || group === "FAA" || group === "EASA") {
        return group;
    }
    // Infer from document field (e.g., "CCAR-33-R2", "FAR-33", "CS-E")
    // Strip known agency prefixes first (e.g., "caac-ccar-33-r2" → "CCAR-33-R2")
    const raw = (node.document || node.id || "").toUpperCase();

    // Log nodes missing document field for monitoring
    if (!node.document && !node.group) {
        console.warn("[inferAgency] Node missing document field, falling back to id:", node.id || "(no id)");
    }

    const doc = raw
        .replace(/^CAAC-/, "")
        .replace(/^FAA-/, "")
        .replace(/^EASA-/, "");
    if (doc.startsWith("CCAR-") || doc.startsWith("AP-") || doc.startsWith("AC-")) {
        return "CAAC";
    }
    if (doc.startsWith("FAR-")) {
        return "FAA";
    }
    if (doc.startsWith("CS-")) {
        return "EASA";
    }
    return "";
}

/**
 * Get node group class for CSS styling - based on agency (for colors)
 */
function getNodeGroupClass(node) {
    const agency = inferAgency(node);
    if (agency === "CAAC") return "regulation";
    if (agency === "FAA" || agency === "EASA") return "component";
    return "support";
}

/**
 * Get node gradient URL - based on agency for 3D radial gradient effect
 */
function getNodeGradient(node) {
    const agency = inferAgency(node);
    if (agency === "CAAC") return "url(#gradCAAC)";
    if (agency === "FAA") return "url(#gradFAA)";
    if (agency === "EASA") return "url(#gradEASA)";
    if (node.color) return node.color;
    return "url(#gradDefault)";
}

/**
 * Get node color - based on agency
 */
function getNodeColor(node) {
    const agency = inferAgency(node);
    if (agency === "CAAC") return "#e63946";
    if (agency === "FAA") return "#3498db";
    if (agency === "EASA") return "#2ecc71";
    if (node.color) return node.color;
    return "#6f8095";
}

function getNodeRadius(node) {
    const size = node.size || 5;
    const agency = inferAgency(node);
    if (agency) {
        return Math.sqrt(size) * 3;
    }
    return 5 + Math.sqrt(size) * 1.5;
}

function typeLabel(node) {
    const agency = inferAgency(node);
    if (agency) return agency;
    return node.type || "节点";
}

function jurisdictionLabel(jurisdiction) {
    const mapping = {
        "CN": "CAAC",
        "US": "FAA",
        "EU": "EASA",
    };
    return mapping[jurisdiction] || jurisdiction || "-";
}

function layerLabel(layer) {
    const mapping = {
        core_regulations: "核心法规",
        certification_guidance: "审定指导",
        environment_and_lifecycle: "环境与全生命周期",
    };
    return mapping[layer] || layer || "-";
}

function guardrailClass(status) {
    if (status === "PASS" || status === "PASSED") return "ok";
    if (status === "PARTIAL" || status === "UNVERIFIED") return "warn";
    return "risk";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/**
 * Toggle dashboard visibility
 */
function toggleDashboard() {
    const panel = document.getElementById("dashboardPanel");
    const btn = document.getElementById("toggleDashboardBtn");
    if (!panel || !btn) return;

    const isVisible = panel.style.display !== "none";
    panel.style.display = isVisible ? "none" : "block";
    btn.textContent = isVisible ? "显示仪表盘" : "隐藏仪表盘";

    if (!isVisible) {
        // Loading dashboard for the first time or resuming
        loadDashboard();
        startDashboardAutoRefresh();
    } else {
        stopDashboardAutoRefresh();
    }
}

// =====================================================
// Graph Virtualization (P2-10)
// =====================================================

// Virtualization state
let _virtFrameId = null;
let _lastVirtScale = -1;
let _cachedViewportBounds = null;

const LOD_HIGH_THRESHOLD = 1.5;   // Show full labels above this zoom
const LOD_LOW_THRESHOLD = 0.5;   // Below this: simplified nodes
const VIEWPORT_PADDING = 60;     // Extra px outside viewport to still render

/**
 * Compute the visible viewport bounds in data coordinates.
 * Returns { xMin, xMax, yMin, yMax } or null if no zoom transform.
 */
function getViewportBounds(svgEl, width, height) {
    if (!networkZoom) return null;
    const t = d3.zoomTransform(svgEl);
    if (!t) return null;

    // Convert screen corners to data coords
    const xMin = -t.x / t.k - VIEWPORT_PADDING;
    const xMax = (-t.x + width) / t.k + VIEWPORT_PADDING;
    const yMin = -t.y / t.k - VIEWPORT_PADDING;
    const yMax = (-t.y + height) / t.k + VIEWPORT_PADDING;
    return { xMin, xMax, yMin, yMax };
}

/**
 * Get LOD level based on zoom scale.
 * 'low': highly simplified (tiny circles, no labels)
 * 'medium': normal with abbreviated labels
 * 'high': full detail
 */
function getLodLevel(scale) {
    if (scale >= LOD_HIGH_THRESHOLD) return "high";
    if (scale <= LOD_LOW_THRESHOLD) return "low";
    return "medium";
}

/**
 * Apply virtualization: viewport culling + LOD.
 * Called on every tick (throttled) and on zoom.
 */
function applyVirtualization() {
    if (!networkSimulation || !networkGraphViz) return;

    const svgEl = networkGraphViz.querySelector("svg");
    if (!svgEl) return;
    const containerWidth = svgEl.clientWidth || 800;
    const containerHeight = svgEl.clientHeight || 550;

    const bounds = getViewportBounds(svgEl, containerWidth, containerHeight);
    const t = d3.zoomTransform(svgEl);
    const scale = t ? t.k : 1;
    const lod = getLodLevel(scale);

    // Cache viewport bounds for external use
    _cachedViewportBounds = bounds;

    // Counters for stats
    let renderedCount = 0;
    let culledCount = 0;

    // Process nodes
    d3.selectAll(".network-node").each(function(d) {
        const inView = bounds
            ? (d.x >= bounds.xMin && d.x <= bounds.xMax &&
               d.y >= bounds.yMin && d.y <= bounds.yMax)
            : true;

        const el = this;
        if (!inView) {
            el.style.display = "none";
            culledCount++;
            return;
        }

        el.style.display = "";
        renderedCount++;

        const circle = d3.select(this).select("circle");
        const text = d3.select(this).select("text");

        if (lod === "low") {
            // Simplified: small dot, no label
            circle.attr("r", d => Math.max(3, getNodeRadius(d) * 0.4));
            text.style("display", "none");
        } else if (lod === "medium") {
            // Medium: slightly smaller, abbreviated label
            circle.attr("r", d => getNodeRadius(d) * 0.8);
            text.style("display", null)
                .style("font-size", "9px")
                .text(d => {
                    const label = d.label || d.id || "";
                    return label.length > 10 ? label.substring(0, 8) + ".." : label;
                });
        } else {
            // High: full detail
            circle.attr("r", d => getNodeRadius(d));
            text.style("display", null)
                .style("font-size", "10px")
                .text(d => {
                    const label = d.label || d.id || "";
                    return label.length > 15 ? label.substring(0, 12) + "..." : label;
                });
        }
    });

    // Process edges — hide edges where both endpoints are culled
    const hiddenNodes = new Set();
    d3.selectAll(".network-node").each(function(d) {
        if (bounds && (d.x < bounds.xMin || d.x > bounds.xMax ||
            d.y < bounds.yMin || d.y > bounds.yMax)) {
            hiddenNodes.add(d.id);
        }
    });

    d3.selectAll(".network-link").each(function(d) {
        const srcId = d.source.id || d.source;
        const tgtId = d.target.id || d.target;
        const bothHidden = hiddenNodes.has(srcId) && hiddenNodes.has(tgtId);
        this.style.display = bothHidden ? "none" : "";
    });

    // Update virtualization stats (add to existing graph-stats)
    let virtEl = document.getElementById("virtStats");
    if (!virtEl) {
        virtEl = document.createElement("div");
        virtEl.id = "virtStats";
        virtEl.style.cssText = "position: absolute; bottom: 36px; left: 10px; padding: 8px 12px; background: rgba(0,0,0,0.7); border-radius: 6px; font-size: 11px; color: #98a8bc; pointer-events: none;";
        networkGraphViz.appendChild(virtEl);
    }
    const totalNodes = (currentGraphState?.nodes?.length || 0);
    virtEl.innerHTML = `可见: ${renderedCount}/${totalNodes} | 缩放: ${Math.round(scale * 100)}% | LOD: ${lod}`;
}

/**
 * Throttled virtualization update — max once per animation frame.
 */
function scheduleVirtualizationUpdate() {
    if (_virtFrameId !== null) return;
    _virtFrameId = requestAnimationFrame(() => {
        _virtFrameId = null;
        applyVirtualization();
    });
}

/**
 * Reset virtualization cache when graph is rebuilt.
 */
function resetVirtualizationCache() {
    _lastVirtScale = -1;
    _cachedViewportBounds = null;
    if (_virtFrameId !== null) {
        cancelAnimationFrame(_virtFrameId);
        _virtFrameId = null;
    }
}

// =====================================================
// Performance Dashboard
// =====================================================

/**
 * Load and render performance dashboard
 */
async function loadDashboard() {
    try {
        const response = await apiFetch(`${API_BASE_URL}/api/v1/dashboard/stats`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        renderDashboardMetrics(data);
        renderDashboardCharts(data);
    } catch (error) {
        console.error("[Dashboard] Failed to load:", error);
        showDashboardError(error.message);
    }
}

/**
 * Render dashboard metric cards
 */
function renderDashboardMetrics(data) {
    const perf = data.performance || data;
    const metricsEl = document.getElementById("dashboardMetrics");
    if (!metricsEl) return;

    // Response time metrics
    const rtP50 = perf.response_time_p50 || 0;
    const rtP95 = perf.response_time_p95 || 0;
    const rtP99 = perf.response_time_p99 || 0;

    // Confidence distribution
    const confDist = perf.confidence_distribution || { high: 0, medium: 0, low: 0 };

    // Source coverage
    const sourceCov = perf.source_coverage || { CAAC: 0, FAA: 0, EASA: 0, OTHER: 0 };
    const totalSource = sourceCov.CAAC + sourceCov.FAA + sourceCov.EASA + sourceCov.OTHER || 1;

    // Query count
    const queryCount = perf.query_count || 0;

    metricsEl.innerHTML = `
        <div class="dashboard-metric-card">
            <div class="metric-icon">⏱️</div>
            <div class="metric-value">${rtP50.toFixed(0)}ms</div>
            <div class="metric-label">响应时间 P50</div>
            <div class="metric-sub">P95: ${rtP95.toFixed(0)}ms | P99: ${rtP99.toFixed(0)}ms</div>
        </div>
        <div class="dashboard-metric-card">
            <div class="metric-icon">🎯</div>
            <div class="metric-value">${queryCount}</div>
            <div class="metric-label">总查询次数</div>
            <div class="metric-sub">实时统计</div>
        </div>
        <div class="dashboard-metric-card confidence-card">
            <div class="metric-icon">📊</div>
            <div class="metric-value conf-high">${confDist.high.toFixed(0)}%</div>
            <div class="metric-label">高置信度</div>
            <div class="confidence-bar">
                <div class="conf-segment high" style="width: ${confDist.high}%"></div>
                <div class="conf-segment medium" style="width: ${confDist.medium}%"></div>
                <div class="conf-segment low" style="width: ${confDist.low}%"></div>
            </div>
            <div class="conf-legend">
                <span class="conf-high">高 ${confDist.high.toFixed(0)}%</span>
                <span class="conf-medium">中 ${confDist.medium.toFixed(0)}%</span>
                <span class="conf-low">低 ${confDist.low.toFixed(0)}%</span>
            </div>
        </div>
        <div class="dashboard-metric-card">
            <div class="metric-icon">🌍</div>
            <div class="metric-value">${perf.avg_confidence ? (perf.avg_confidence * 100).toFixed(0) : 0}%</div>
            <div class="metric-label">平均置信度</div>
            <div class="metric-sub">综合评分</div>
        </div>
    `;
}

/**
 * Render dashboard charts using D3.js
 */
function renderDashboardCharts(data) {
    const perf = data.performance || data;

    // Source coverage pie chart
    renderSourceCoveragePie(perf.source_coverage || { CAAC: 0, FAA: 0, EASA: 0, OTHER: 0 });

    // Top sources bar chart
    renderTopSourcesBar(perf.top_sources || []);
}

/**
 * Render source coverage pie chart
 */
function renderSourceCoveragePie(sourceCov) {
    const container = document.getElementById("sourceCoverageChart");
    if (!container) return;

    const width = 200;
    const height = 200;
    const radius = Math.min(width, height) / 2;

    // Clear previous
    container.innerHTML = "";

    const data = [
        { agency: "CAAC", count: sourceCov.CAAC || 0, color: "#e63946" },
        { agency: "FAA", count: sourceCov.FAA || 0, color: "#3498db" },
        { agency: "EASA", count: sourceCov.EASA || 0, color: "#2ecc71" },
        { agency: "OTHER", count: sourceCov.OTHER || 0, color: "#95a5a6" }
    ].filter(d => d.count > 0);

    if (data.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无来源数据</div>';
        return;
    }

    const svg = d3.select(container)
        .append("svg")
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${width / 2}, ${height / 2})`);

    const pie = d3.pie()
        .value(d => d.count)
        .sort(null);

    const arc = d3.arc()
        .innerRadius(radius * 0.5)
        .outerRadius(radius - 10);

    const arcs = svg.selectAll("arc")
        .data(pie(data))
        .enter()
        .append("g");

    arcs.append("path")
        .attr("d", arc)
        .attr("fill", d => d.data.color)
        .attr("stroke", "#0f1520")
        .attr("stroke-width", 2)
        .style("opacity", 0.9);

    // Labels
    arcs.append("text")
        .attr("transform", d => `translate(${arc.centroid(d)})`)
        .attr("text-anchor", "middle")
        .attr("fill", "#fff")
        .attr("font-size", "11px")
        .attr("font-weight", "600")
        .text(d => d.data.count > 0 ? d.data.agency : "");

    // Legend
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    legend.innerHTML = data.map(d => `
        <div class="legend-item">
            <div class="legend-color" style="background: ${d.color}"></div>
            <span>${d.agency}: ${d.count}</span>
        </div>
    `).join("");
    container.appendChild(legend);
}

/**
 * Render top sources horizontal bar chart
 */
function renderTopSourcesBar(topSources) {
    const container = document.getElementById("topSourcesChart");
    if (!container) return;

    // Clear previous
    container.innerHTML = "";

    if (!topSources || topSources.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无来源统计</div>';
        return;
    }

    const width = 280;
    const barHeight = 24;
    const height = Math.max(topSources.length * barHeight + 20, 100);

    const svg = d3.select(container)
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const maxCount = Math.max(...topSources.map(s => s.count), 1);

    const x = d3.scaleLinear()
        .domain([0, maxCount])
        .range([0, width - 80]);

    const g = svg.append("g");

    g.selectAll("rect")
        .data(topSources.slice(0, 8))
        .enter()
        .append("rect")
        .attr("x", 0)
        .attr("y", (d, i) => i * barHeight + 5)
        .attr("width", d => x(d.count))
        .attr("height", barHeight - 4)
        .attr("fill", "#667eea")
        .attr("rx", 3)
        .style("opacity", 0.8);

    g.selectAll("text")
        .data(topSources.slice(0, 8))
        .enter()
        .append("text")
        .attr("x", d => x(d.count) + 5)
        .attr("y", (d, i) => i * barHeight + 5 + barHeight / 2)
        .attr("dy", "0.35em")
        .attr("fill", "#94a3b8")
        .attr("font-size", "11px")
        .text(d => `${d.source.substring(0, 15)} (${d.count})`);
}

/**
 * Show dashboard error state
 */
function showDashboardError(message) {
    const metricsEl = document.getElementById("dashboardMetrics");
    if (metricsEl) {
        metricsEl.innerHTML = `
            <div class="error-state" style="grid-column: 1 / -1;">
                仪表盘加载失败: ${escapeHtml(message)}
            </div>
        `;
    }
}

/**
 * Start dashboard auto-refresh (every 30 seconds)
 */
function startDashboardAutoRefresh() {
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
    }
    loadDashboard();  // Initial load
    dashboardRefreshInterval = setInterval(loadDashboard, 30000);
}

/**
 * Stop dashboard auto-refresh
 */
function stopDashboardAutoRefresh() {
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
}
