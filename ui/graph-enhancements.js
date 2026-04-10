// =====================================================
// AeroPower-RAG - Graph Visualization Enhancements
// =====================================================

/**
 * Graph Enhancement Module
 * Provides advanced interactions for the network graph:
 * - Multi-select with shift+click and lasso selection
 * - Node pinning/freeze functionality
 * - Enhanced zoom controls with fit-to-view
 * - Connected node highlighting on hover
 * - Layout controls (re-layout, cluster toggle)
 */

// =====================================================
// State
// =====================================================

let selectedNodes = new Set();
let pinnedNodes = new Map();  // nodeId -> {x, y}
let isLassoSelecting = false;
let lassoStart = null;
let lassoEnd = null;
let lassoOverlay = null;
let hoverHighlightEnabled = true;

// =====================================================
// Multi-Select Functions
// =====================================================

/**
 * Toggle node selection (add/remove from selection)
 * @param {Object} node - D3 node data
 * @param {boolean} addToSelection - If true, add to selection; if false, toggle
 */
function toggleNodeSelection(node, addToSelection = false) {
    if (!addToSelection) {
        // Clear previous selection
        clearNodeSelection();
    }

    if (selectedNodes.has(node.id)) {
        selectedNodes.delete(node.id);
    } else {
        selectedNodes.add(node.id);
    }

    updateSelectionVisuals();
}

/**
 * Clear all selected nodes
 */
function clearNodeSelection() {
    selectedNodes.clear();
    updateSelectionVisuals();
}

/**
 * Update visual state of selected nodes
 */
function updateSelectionVisuals() {
    if (typeof d3 === "undefined") return;

    d3.selectAll(".network-node")
        .classed("selected", d => selectedNodes.has(d.id))
        .classed("dimmed", d => selectedNodes.size > 0 && !selectedNodes.has(d.id));

    // Update selection info panel
    updateSelectionInfo();
}

/**
 * Update the selection info display
 */
function updateSelectionInfo() {
    let infoEl = document.getElementById("selectionInfo");
    if (!infoEl) return;

    if (selectedNodes.size === 0) {
        infoEl.style.display = "none";
    } else {
        infoEl.style.display = "flex";
        const countEl = document.getElementById("selectionCount");
        if (countEl) {
            countEl.textContent = selectedNodes.size;
        }
    }
}

/**
 * Handle shift+click for multi-select
 */
function setupMultiSelect(svg, g) {
    svg.on("click", (event) => {
        if (event.shiftKey) {
            event.preventDefault();
            // Find node under cursor if any
            const node = findNodeAtPoint(event);
            if (node) {
                toggleNodeSelection(node, true);  // Add to selection
            }
        } else if (!event.target.closest(".network-node") && !lassoOverlay) {
            // Click on empty space with no modifier
            if (!event.shiftKey) {
                clearNodeSelection();
            }
        }
    });
}

/**
 * Find node at given mouse point
 */
function findNodeAtPoint(event) {
    const [mx, my] = d3.pointer(event, g.node());
    let found = null;

    d3.selectAll(".network-node").each(function(d) {
        const dx = d.x - mx;
        const dy = d.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const radius = getNodeRadius(d) + 5;  // Add tolerance

        if (dist < radius) {
            found = d;
        }
    });

    return found;
}

// =====================================================
// Lasso Selection
// =====================================================

/**
 * Enable lasso selection on the graph
 */
function enableLassoSelection(container, svg, g) {
    // Create overlay for lasso drawing
    lassoOverlay = document.createElement("div");
    lassoOverlay.className = "lasso-overlay";
    lassoOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
        z-index: 10;
    `;
    container.appendChild(lassoOverlay);

    let lassoRect = null;

    svg.on("mousedown", (event) => {
        if (event.button !== 0 || event.shiftKey) return;  // Left click only
        if (event.target.closest(".network-node")) return;

        const rect = container.getBoundingClientRect();
        lassoStart = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };
        isLassoSelecting = true;

        // Clear previous selection if not holding shift
        if (!event.shiftKey) {
            clearNodeSelection();
        }

        // Create lasso rectangle
        lassoOverlay.innerHTML = "";
        lassoRect = document.createElement("div");
        lassoRect.className = "lasso-rect";
        lassoOverlay.appendChild(lassoRect);
    });

    svg.on("mousemove", (event) => {
        if (!isLassoSelecting || !lassoStart) return;

        const rect = container.getBoundingClientRect();
        lassoEnd = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };

        const x = Math.min(lassoStart.x, lassoEnd.x);
        const y = Math.min(lassoStart.y, lassoEnd.y);
        const width = Math.abs(lassoEnd.x - lassoStart.x);
        const height = Math.abs(lassoEnd.y - lassoStart.y);

        lassoRect.style.cssText = `
            position: absolute;
            left: ${x}px;
            top: ${y}px;
            width: ${width}px;
            height: ${height}px;
            border: 2px dashed var(--accent);
            background: rgba(102, 126, 234, 0.1);
            border-radius: 4px;
            pointer-events: none;
        `;
    });

    svg.on("mouseup", (event) => {
        if (!isLassoSelecting) return;
        isLassoSelecting = false;

        if (lassoStart && lassoEnd) {
            // Select nodes within lasso rectangle
            selectNodesInRect(lassoStart, lassoEnd);
        }

        lassoStart = null;
        lassoEnd = null;
        if (lassoRect) {
            lassoRect.remove();
            lassoRect = null;
        }
    });
}

/**
 * Select all nodes within a rectangle
 */
function selectNodesInRect(start, end) {
    const minX = Math.min(start.x, end.x);
    const maxX = Math.max(start.x, end.x);
    const minY = Math.min(start.y, end.y);
    const maxY = Math.max(start.y, end.y);

    d3.selectAll(".network-node").each(function(d) {
        const nodeX = d.x;
        const nodeY = d.y;

        if (nodeX >= minX && nodeX <= maxX && nodeY >= minY && nodeY <= maxY) {
            selectedNodes.add(d.id);
        }
    });

    updateSelectionVisuals();
}

// =====================================================
// Node Pinning
// =====================================================

/**
 * Pin a node to its current position
 */
function pinNode(node) {
    pinnedNodes.set(node.id, { x: node.x, y: node.y });
    node.fx = node.x;
    node.fy = node.y;
    updatePinnedVisuals();
}

/**
 * Unpin a node and let it move freely
 */
function unpinNode(node) {
    pinnedNodes.delete(node.id);
    node.fx = null;
    node.fy = null;
    updatePinnedVisuals();
}

/**
 * Toggle pin state of a node
 */
function togglePinNode(node) {
    if (pinnedNodes.has(node.id)) {
        unpinNode(node);
    } else {
        pinNode(node);
    }
}

/**
 * Update visual state of pinned nodes
 */
function updatePinnedVisuals() {
    if (typeof d3 === "undefined") return;

    d3.selectAll(".network-node")
        .classed("pinned", d => pinnedNodes.has(d.id));
}

/**
 * Restore pinned positions after simulation tick
 */
function applyPinnedPositions() {
    pinnedNodes.forEach((pos, nodeId) => {
        const node = currentGraphState?.nodes.find(n => n.id === nodeId);
        if (node) {
            node.fx = pos.x;
            node.fy = pos.y;
        }
    });
}

// =====================================================
// Enhanced Hover Highlighting
// =====================================================

/**
 * Setup hover highlighting for connected nodes
 */
function setupHoverHighlight(g, validEdges) {
    g.selectAll(".network-node")
        .on("mouseenter", function(event, d) {
            if (!hoverHighlightEnabled) return;

            // Find connected nodes
            const connectedIds = new Set();
            connectedIds.add(d.id);

            validEdges.forEach(edge => {
                const sourceId = edge.source.id || edge.source;
                const targetId = edge.target.id || edge.target;

                if (sourceId === d.id) connectedIds.add(targetId);
                if (targetId === d.id) connectedIds.add(sourceId);
            });

            // Dim non-connected nodes
            d3.selectAll(".network-node")
                .classed("dimmed", node => !connectedIds.has(node.id));

            // Highlight connected edges
            d3.selectAll(".network-link")
                .classed("highlighted", edge => {
                    const sourceId = edge.source.id || edge.source;
                    const targetId = edge.target.id || edge.target;
                    return sourceId === d.id || targetId === d.id;
                })
                .classed("dimmed-edge", edge => {
                    const sourceId = edge.source.id || edge.source;
                    const targetId = edge.target.id || edge.target;
                    return sourceId !== d.id && targetId !== d.id;
                });
        })
        .on("mouseleave", function() {
            // Reset all highlighting
            d3.selectAll(".network-node").classed("dimmed", false);
            d3.selectAll(".network-link")
                .classed("highlighted", false)
                .classed("dimmed-edge", false);
        });

    // Edge type tooltip on hover
    let edgeTooltipEl = null;
    g.selectAll(".network-link")
        .on("mouseenter", function(event, d) {
            if (!hoverHighlightEnabled) return;
            const edgeType = d.type || "RELATED_TO";
            edgeTooltipEl = document.createElement("div");
            edgeTooltipEl.className = "edge-tooltip";
            const span = document.createElement("span");
            span.className = "edge-tooltip-type";
            span.textContent = edgeType;
            edgeTooltipEl.appendChild(span);
            document.body.appendChild(edgeTooltipEl);
            const rect = this.getBoundingClientRect();
            edgeTooltipEl.style.left = (rect.left + rect.width / 2 - edgeTooltipEl.offsetWidth / 2) + "px";
            edgeTooltipEl.style.top = (rect.top - 28) + "px";
        })
        .on("mousemove", function(event) {
            if (edgeTooltipEl) {
                edgeTooltipEl.style.left = (event.clientX + 12) + "px";
                edgeTooltipEl.style.top = (event.clientY - 28) + "px";
            }
        })
        .on("mouseleave", function() {
            if (edgeTooltipEl) {
                edgeTooltipEl.remove();
                edgeTooltipEl = null;
            }
        });
}

// =====================================================
// Enhanced Zoom Controls
// =====================================================

/**
 * Add enhanced zoom controls to the container
 */
function addEnhancedZoomControls(container, svg, zoom) {
    const controls = container.querySelector(".graph-zoom-controls");
    if (!controls) return;

    // Add fit-to-view button
    const fitBtn = document.createElement("button");
    fitBtn.className = "zoom-btn";
    fitBtn.id = "zoomFitBtn";
    fitBtn.innerHTML = "\u229E";
    fitBtn.title = "适应视图";
    fitBtn.addEventListener("click", () => fitGraphToView(svg, zoom));
    controls.appendChild(fitBtn);

    // Add zoom level indicator
    const zoomLevel = document.createElement("div");
    zoomLevel.className = "zoom-level";
    zoomLevel.id = "zoomLevel";
    zoomLevel.textContent = "100%";
    zoomLevel.style.cssText = `
        padding: 0 8px;
        font-size: 11px;
        color: var(--text-muted);
        display: flex;
        align-items: center;
    `;
    controls.insertBefore(zoomLevel, controls.firstChild);

    // Update zoom level on zoom
    zoom.on("zoom", (event) => {
        const scale = event.transform.k;
        const pct = Math.round(scale * 100);
        const levelEl = document.getElementById("zoomLevel");
        if (levelEl) {
            levelEl.textContent = pct + "%";
        }
    });

    // Add selection controls
    addSelectionControls(container);
}

/**
 * Fit graph to view
 */
function fitGraphToView(svg, zoom) {
    const svgNode = svg.node();
    const g = svgNode.querySelector("g");
    if (!g) return;

    const bounds = g.getBBox();
    const parent = svgNode.parentElement;
    const width = parent.clientWidth || 800;
    const height = parent.clientHeight || 550;

    const dx = bounds.width;
    const dy = bounds.height;
    const x = bounds.x + dx / 2;
    const y = bounds.y + dy / 2;

    const scale = Math.min(0.9 * width / dx, 0.9 * height / dy, 2);
    const translate = [width / 2 - scale * x, height / 2 - scale * y];

    svg.transition()
        .duration(750)
        .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
}

/**
 * Add selection controls
 */
function addSelectionControls(container) {
    const controls = document.createElement("div");
    controls.className = "selection-controls";
    controls.innerHTML = `
        <button class="selection-btn" id="selectAllBtn" title="全选">&#9744;</button>
        <button class="selection-btn" id="clearSelectionBtn" title="清除选择">&#9745;</button>
        <button class="selection-btn" id="pinSelectedBtn" title="锁定选中">&#128204;</button>
        <button class="selection-btn" id="unpinAllBtn" title="解锁全部">&#128205;</button>
    `;
    controls.style.cssText = `
        position: absolute;
        top: 50px;
        right: 10px;
        display: flex;
        gap: 5px;
    `;

    container.appendChild(controls);

    // Event handlers
    document.getElementById("selectAllBtn")?.addEventListener("click", selectAllNodes);
    document.getElementById("clearSelectionBtn")?.addEventListener("click", clearNodeSelection);
    document.getElementById("pinSelectedBtn")?.addEventListener("click", pinSelectedNodes);
    document.getElementById("unpinAllBtn")?.addEventListener("click", unpinAllNodes);
}

/**
 * Select all nodes
 */
function selectAllNodes() {
    if (typeof d3 === "undefined") return;
    d3.selectAll(".network-node").each(function(d) {
        selectedNodes.add(d.id);
    });
    updateSelectionVisuals();
}

/**
 * Pin all selected nodes
 */
function pinSelectedNodes() {
    if (selectedNodes.size === 0) return;

    selectedNodes.forEach(nodeId => {
        const node = currentGraphState?.nodes.find(n => n.id === nodeId);
        if (node) {
            pinnedNodes.set(nodeId, { x: node.x, y: node.y });
            node.fx = node.x;
            node.fy = node.y;
        }
    });

    updatePinnedVisuals();
    showNotification("已锁定 " + selectedNodes.size + " 个节点");
}

/**
 * Unpin all nodes
 */
function unpinAllNodes() {
    if (pinnedNodes.size === 0) return;

    pinnedNodes.forEach((pos, nodeId) => {
        const node = currentGraphState?.nodes.find(n => n.id === nodeId);
        if (node) {
            node.fx = null;
            node.fy = null;
        }
    });

    pinnedNodes.clear();
    updatePinnedVisuals();
    showNotification("已解锁全部节点");
}

// =====================================================
// Layout Controls
// =====================================================

/**
 * Add layout control buttons
 */
function addLayoutControls(container, simulation) {
    const controls = document.createElement("div");
    controls.className = "layout-controls";
    controls.innerHTML = `
        <button class="layout-btn" id="relayoutBtn" title="重新布局">&#8635;</button>
    `;
    controls.style.cssText = `
        position: absolute;
        top: 100px;
        right: 10px;
        display: flex;
        flex-direction: column;
        gap: 5px;
    `;

    container.appendChild(controls);

    document.getElementById("relayoutBtn")?.addEventListener("click", () => {
        reheatSimulation(simulation);
        showNotification("正在重新计算布局...");
    });
}

/**
 * Reheat and restart simulation
 */
function reheatSimulation(simulation) {
    if (!simulation) return;
    simulation.alpha(1).restart();
}

// =====================================================
// Notification System
// =====================================================

/**
 * Show a temporary notification
 */
function showNotification(message, duration) {
    if (duration === undefined) duration = 2000;
    let notif = document.getElementById("graphNotification");
    if (!notif) {
        notif = document.createElement("div");
        notif.id = "graphNotification";
        notif.style.cssText = [
            "position: fixed;",
            "bottom: 20px;",
            "left: 50%;",
            "transform: translateX(-50%);",
            "padding: 10px 20px;",
            "background: var(--bg-panel);",
            "border: 1px solid var(--accent);",
            "border-radius: 6px;",
            "color: var(--text-primary);",
            "font-size: 13px;",
            "z-index: 9999;",
            "opacity: 0;",
            "transition: opacity 0.3s ease;"
        ].join(" ");
        document.body.appendChild(notif);
    }

    notif.textContent = message;
    notif.style.opacity = "1";

    setTimeout(function() {
        notif.style.opacity = "0";
    }, duration);
}

// =====================================================
// Keyboard Shortcuts
// =====================================================

/**
 * Setup keyboard shortcuts for graph interactions
 */
function setupKeyboardShortcuts(simulation) {
    document.addEventListener("keydown", function(event) {
        // Only work when graph container is focused or no input is focused
        const activeEl = document.activeElement;
        if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA")) {
            return;
        }

        switch (event.key) {
            case "Escape":
                clearNodeSelection();
                break;
            case "f":
            case "F":
                // Fit to view - handled by zoom controls
                const fitBtn = document.getElementById("zoomFitBtn");
                if (fitBtn) fitBtn.click();
                break;
            case "r":
            case "R":
                // Re-layout
                reheatSimulation(simulation);
                break;
            case "a":
            case "A":
                if (event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    selectAllNodes();
                }
                break;
        }
    });
}

// =====================================================
// Integration Helper
// =====================================================

/**
 * Initialize all graph enhancements
 * Call this after renderNetworkGraph() in app.js
 */
function initGraphEnhancements(svg, g, simulation, validEdges, nodes) {
    const container = svg.node()?.parentElement;
    if (!container) return;

    // Setup multi-select with shift+click
    setupMultiSelect(svg, g);

    // Enable lasso selection
    enableLassoSelection(container, svg, g);

    // Setup hover highlighting
    setupHoverHighlight(g, validEdges);

    // Add enhanced zoom controls
    addEnhancedZoomControls(container, svg, networkZoom);

    // Add layout controls
    addLayoutControls(container, simulation);

    // Setup keyboard shortcuts
    setupKeyboardShortcuts(simulation);

    // Apply any previously pinned positions
    applyPinnedPositions();

    console.log("[Graph Enhancements] Initialized");
}

// =====================================================
// Export for use in app.js
// =====================================================

window.GraphEnhancements = {
    init: initGraphEnhancements,
    toggleNodeSelection: toggleNodeSelection,
    clearNodeSelection: clearNodeSelection,
    selectAllNodes: selectAllNodes,
    pinSelectedNodes: pinSelectedNodes,
    unpinAllNodes: unpinAllNodes,
    reheatSimulation: reheatSimulation,
    showNotification: showNotification
};
