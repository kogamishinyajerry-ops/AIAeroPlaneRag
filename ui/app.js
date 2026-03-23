const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

const userInput = document.getElementById("userInput");
const answerBlock = document.getElementById("answerBlock");
const evidencePanel = document.getElementById("evidencePanel");
const graphViz = document.getElementById("graphViz");
const graphInspector = document.getElementById("graphInspector");
const graphSummary = document.getElementById("graphSummary");
const guardrailChip = document.getElementById("guardrailChip");
const sourcesTableBody = document.getElementById("sourcesTableBody");

let currentCitations = [];
let currentGraphState = null;
let graphHistory = [];
let graphIncludeParameters = false;
let latestQuery = "";

document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("refreshGraphBtn").addEventListener("click", () => loadGraphSubgraph(latestQuery));
document.getElementById("graphBackBtn").addEventListener("click", stepBackGraph);
document.getElementById("includeParametersToggle").addEventListener("change", event => {
    graphIncludeParameters = event.target.checked;
    loadGraphSubgraph(latestQuery, { resetHistory: true });
});
document.getElementById("layerFilter").addEventListener("change", () => loadSourceCatalog());
document.getElementById("jurisdictionFilter").addEventListener("change", () => loadSourceCatalog());

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

bootstrap();

async function bootstrap() {
    await Promise.all([loadHealth(), loadSourceCatalog(), loadGraphSubgraph("", { resetHistory: true })]);
}

async function loadHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const health = await response.json();
        document.getElementById("metricVersion").textContent = health.app_version || "-";
        document.getElementById("metricKbVersion").textContent = health.knowledge_base_version || "-";
        document.getElementById("graphModeLabel").textContent = health.graph_db || "unknown";

        document.getElementById("systemStatus").innerHTML = `
            <div class="status-row"><span>后端</span><strong>${health.app_mode || "unknown"}</strong></div>
            <div class="status-row"><span>知识库</span><strong>${health.vector_db || "unknown"} / ${health.vector_db_count ?? 0}</strong></div>
            <div class="status-row"><span>图谱</span><strong>${health.graph_db || "unknown"}</strong></div>
            <div class="status-row"><span>Guardrail</span><strong>${health.guardrail || "unknown"}</strong></div>
        `;
    } catch (error) {
        document.getElementById("systemStatus").innerHTML = `
            <div class="status-row error"><span>连接失败</span><strong>${error.message}</strong></div>
        `;
    }
}

async function sendMessage() {
    const query = userInput.value.trim();
    if (!query) {
        return;
    }

    latestQuery = query;
    document.getElementById("currentQueryLabel").textContent = query;
    answerBlock.innerHTML = `<div class="loading-state">正在检索法规、生成结论并准备证据面板...</div>`;
    evidencePanel.innerHTML = `<div class="loading-state">正在装载证据...</div>`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                top_k: 5,
                use_guardrail: true,
                include_graph_subgraph: false,
            }),
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        handleResponse(payload);
        await loadGraphSubgraph(query, { resetHistory: true });
    } catch (error) {
        answerBlock.innerHTML = `<div class="error-state">后端连接失败：${error.message}<br>请确认 FastAPI 正在 ${API_BASE_URL} 运行。</div>`;
        evidencePanel.innerHTML = `<div class="empty-state">本次没有可展示的证据。</div>`;
    }
}

function handleResponse(payload) {
    currentCitations = payload.citations || [];
    document.getElementById("retrievalCountLabel").textContent = String(payload.retrievalCount || 0);
    guardrailChip.textContent = `${payload.guardrail?.status || "UNKNOWN"} · ${payload.responseMode || "unknown"}`;
    guardrailChip.className = `guardrail-chip ${guardrailClass(payload.guardrail?.status)}`;

    const answerHtml = (payload.answer || "暂无回答").replace(/\[(\d+)\]/g, (_, num) => {
        return `<button class="citation-ref" onclick="openCitation(${Number(num)})">${num}</button>`;
    });

    const insightHtml = (payload.graphInsights || [])
        .slice(0, 6)
        .map(item => `<span class="insight-pill">${item.regulation || "?"} → ${item.relationship || "关联"} → ${item.component || "?"}</span>`)
        .join("");

    answerBlock.innerHTML = `
        <div class="answer-text">${answerHtml}</div>
        <div class="answer-meta">
            <div><span>Guardrail 说明</span><strong>${payload.guardrail?.reasoning || "无"}</strong></div>
            <div><span>检索命中</span><strong>${payload.retrievalCount || 0}</strong></div>
            <div><span>知识库版本</span><strong>${payload.knowledgeBaseVersion || "-"}</strong></div>
        </div>
        <div class="insight-strip">${insightHtml || '<span class="muted-inline">当前未返回图谱洞察。</span>'}</div>
    `;

    renderEvidenceList(currentCitations);
}

function renderEvidenceList(citations) {
    if (!citations.length) {
        evidencePanel.innerHTML = `<div class="empty-state">本次回答没有返回可展示的证据条目。</div>`;
        return;
    }

    evidencePanel.innerHTML = citations
        .map(
            item => `
                <article class="evidence-card" data-citation="${item.num}">
                    <div class="evidence-head">
                        <span class="evidence-index">[${item.num}]</span>
                        <button class="link-btn" onclick="openCitation(${item.num})">查看全文</button>
                    </div>
                    <h3>${escapeHtml(item.section || "未知条款")}</h3>
                    <div class="evidence-path">${escapeHtml(item.chapter || "")} · ${escapeHtml(item.source || "")}</div>
                    <p>${escapeHtml(item.snippet || "")}</p>
                </article>
            `,
        )
        .join("");
}

function openCitation(num) {
    const citation = currentCitations.find(item => item.num === num);
    if (!citation) {
        return;
    }

    evidencePanel.innerHTML = `
        <article class="evidence-card active">
            <div class="evidence-head">
                <span class="evidence-index">[${citation.num}]</span>
                <span class="evidence-tag">${escapeHtml(citation.documentVersion || "unknown")}</span>
            </div>
            <h3>${escapeHtml(citation.section || "未知条款")}</h3>
            <div class="evidence-path">${escapeHtml(citation.chapter || "")} · ${escapeHtml(citation.source || "")}</div>
            <p>${escapeHtml(citation.fullText || citation.snippet || "").replace(/\n/g, "<br>")}</p>
            <div class="evidence-foot">${escapeHtml(citation.sourcePath || "")}</div>
        </article>
    `;
}

async function loadSourceCatalog() {
    const layer = document.getElementById("layerFilter").value;
    const jurisdiction = document.getElementById("jurisdictionFilter").value;
    const params = new URLSearchParams();
    if (layer) {
        params.set("layer", layer);
    }
    if (jurisdiction) {
        params.set("jurisdiction", jurisdiction);
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/sources?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        const sources = payload.sources || [];
        if (!sources.length) {
            sourcesTableBody.innerHTML = `<tr><td colspan="4" class="table-empty">没有匹配到知识源。</td></tr>`;
            return;
        }

        sourcesTableBody.innerHTML = sources
            .map(
                source => `
                    <tr>
                        <td>
                            <div class="source-title">${escapeHtml(source.title)}</div>
                            <div class="source-summary">${escapeHtml(source.summary || "")}</div>
                        </td>
                        <td>${escapeHtml(source.jurisdiction)} / ${escapeHtml(source.authority)}</td>
                        <td>${layerLabel(source.layer)}</td>
                        <td><span class="status-badge">${escapeHtml(source.status)}</span></td>
                    </tr>
                `,
            )
            .join("");
    } catch (error) {
        sourcesTableBody.innerHTML = `<tr><td colspan="4" class="table-empty error">知识源加载失败：${escapeHtml(error.message)}</td></tr>`;
    }
}

async function loadGraphSubgraph(query = "", options = {}) {
    const { nodeId = null, resetHistory = false } = options;
    const params = new URLSearchParams();
    if (query) {
        params.set("query", query);
    }
    if (nodeId) {
        params.set("node_id", nodeId);
    }
    params.set("max_nodes", "16");
    params.set("include_parameters", graphIncludeParameters ? "true" : "false");

    graphViz.innerHTML = `<div class="loading-state">正在生成局部解释子图...</div>`;
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/graph/subgraph?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        if (resetHistory) {
            graphHistory = [];
        }
        renderGraphSubgraph(payload, { pushHistory: true });
    } catch (error) {
        graphViz.innerHTML = `<div class="error-state">子图加载失败：${escapeHtml(error.message)}</div>`;
    }
}

function renderGraphSubgraph(payload, options = {}) {
    const { pushHistory = false } = options;
    currentGraphState = payload;
    document.getElementById("graphModeLabel").textContent = payload.mode || "fallback";
    graphSummary.textContent = payload.summary || "当前没有图谱摘要。";

    if (pushHistory) {
        const last = graphHistory[graphHistory.length - 1];
        if (!last || JSON.stringify(last) !== JSON.stringify(payload)) {
            graphHistory.push(payload);
        }
    }

    if (!payload.nodes || !payload.nodes.length) {
        graphViz.innerHTML = `<div class="empty-state">当前没有可展示的图谱节点。</div>`;
        return;
    }

    const lanes = {
        regulation: [],
        component: [],
        support: [],
    };
    payload.nodes.forEach(node => {
        if (lanes[node.type]) {
            lanes[node.type].push(node);
        } else {
            lanes.support.push(node);
        }
    });

    const columns = [
        { key: "regulation", title: "法规 / 条款" },
        { key: "component", title: "部件 / 子系统" },
        { key: "support", title: "支撑节点" },
    ];

    graphViz.innerHTML = columns
        .map(
            column => `
                <section class="graph-lane">
                    <header>${column.title}</header>
                    <div class="graph-node-stack">
                        ${
                            lanes[column.key].length
                                ? lanes[column.key]
                                      .map(node => renderNodeCard(node, payload.edges || []))
                                      .join("")
                                : '<div class="graph-empty-mini">无节点</div>'
                        }
                    </div>
                </section>
            `,
        )
        .join("");

    graphViz.querySelectorAll(".graph-node").forEach(node => {
        node.addEventListener("click", () => {
            const nodeId = node.dataset.nodeId;
            const detail = payload.nodes.find(item => item.id === nodeId);
            if (!detail) {
                return;
            }
            renderNodeInspector(detail, payload.edges || [], payload.nodes || []);
        });
    });

    graphViz.querySelectorAll(".graph-expand").forEach(button => {
        button.addEventListener("click", event => {
            event.stopPropagation();
            loadGraphSubgraph(latestQuery, { nodeId: button.dataset.nodeId, resetHistory: false });
        });
    });
}

function renderNodeCard(node, edges) {
    const edgeCount = edges.filter(edge => edge.source === node.id || edge.target === node.id).length;
    return `
        <article class="graph-node ${node.type}" data-node-id="${escapeHtml(node.id)}">
            <div class="graph-node-head">
                <span class="node-type">${typeLabel(node.type)}</span>
                <button class="graph-expand" data-node-id="${escapeHtml(node.id)}">展开</button>
            </div>
            <h3>${escapeHtml(node.label)}</h3>
            <p>${escapeHtml(node.description || "暂无描述")}</p>
            <div class="node-meta">${edgeCount} 条关系</div>
        </article>
    `;
}

function renderNodeInspector(node, edges, nodes) {
    const related = edges
        .filter(edge => edge.source === node.id || edge.target === node.id)
        .slice(0, 8)
        .map(edge => {
            const peerId = edge.source === node.id ? edge.target : edge.source;
            const peer = nodes.find(item => item.id === peerId);
            return `
                <li>
                    <strong>${escapeHtml(edge.type)}</strong>
                    <span>${escapeHtml(peer?.label || peerId)}</span>
                </li>
            `;
        })
        .join("");

    graphInspector.innerHTML = `
        <div class="inspector-node-type">${typeLabel(node.type)}</div>
        <h3>${escapeHtml(node.label)}</h3>
        <p>${escapeHtml(node.description || "暂无描述")}</p>
        <div class="inspector-subtitle">相邻关系</div>
        <ul class="relation-list">
            ${related || "<li>当前节点没有可展示的相邻关系。</li>"}
        </ul>
    `;
}

function stepBackGraph() {
    if (graphHistory.length <= 1) {
        return;
    }
    graphHistory.pop();
    const previous = graphHistory[graphHistory.length - 1];
    renderGraphSubgraph(previous, { pushHistory: false });
}

function guardrailClass(status) {
    if (status === "PASS") {
        return "ok";
    }
    if (status === "PARTIAL" || status === "UNVERIFIED") {
        return "warn";
    }
    return "risk";
}

function layerLabel(layer) {
    const mapping = {
        core_regulations: "核心法规",
        certification_guidance: "审定指导",
        environment_and_lifecycle: "环境与全生命周期",
    };
    return mapping[layer] || layer || "-";
}

function typeLabel(type) {
    const mapping = {
        regulation: "法规",
        component: "部件",
        support: "支撑",
    };
    return mapping[type] || type || "节点";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}
