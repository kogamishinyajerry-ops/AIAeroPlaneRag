# AIAeroPlaneRag — Notion 控制塔使用手册

> 目的：把 Notion 变成 AIAeroPlaneRag 的开发中枢，解决"每次开会话都要重新复制长提示词 / 手动同步状态"的痛点。
> 架构思路借鉴 [AI-Harness 控制塔 v2] 的 repo-first / control-plane 理念，与 v1/v2 完全隔离。

---

## 1. 顶层架构

```
AIAeroPlaneRag 控制塔 (父页面,临时挂在 v1 下, 请手动移到 workspace 根)
├── AeroPower RAG OS          ← 每天从这里进入
│   ├── Phases DB
│   ├── Sessions DB
│   ├── Tasks DB
│   ├── Decisions DB
│   ├── Pinned Canonical Docs DB
│   └── Prompts Library DB       ← 解决"重复复制提示词"的核心
├── Automation Operations        ← 写入前检查清单
├── Isolation Governance Rules   ← 与 v1/v2 的隔离边界
├── Automation Scope Registry    ← 所有允许写入的目标白名单
└── History - Bootstrap Log
```

**Repo 是真相源，Notion 是控制面。** 代码、契约、canonical 文档不进 Notion，只存摘要 + GitHub 链接。

---

## 2. 一次性手动操作（❗ 必做）

1. 打开 Notion → 找到 **"AI-Harness 控制塔 v1"** → 展开 → 看到新建的 **"AIAeroPlaneRag 控制塔 (移动到 workspace 根)"** 子页面。
2. 把它拖到 **workspace 根目录**（或任意与 v1/v2 同级的独立位置）。
3. 把标题里的 "(移动到 workspace 根)" 后缀去掉。
4. 完成。所有 ID 保持不变，脚本继续工作。

**为什么要手动移动？** Notion Integration 不能创建顶层页面，必须挂在某个已存在的页面下；我选了 v1 (v2 已把它标为 reference-only) 作为最不干扰的临时宿主。

---

## 3. 日常工作流（核心）

### 3.1 开启一个新会话（不再复制长提示词！）

```bash
cd ~/AIAeroPlaneRag
python scripts/notion/sync.py restore
```

这会打印一段 **启动简报**，内容包括：
- 当前 Active Phase 的 Context Pack + Exit Criteria
- 上次会话的 Handoff Summary + Touched Files
- 前 5 条 P0 任务及其 Acceptance
- 所有 Open Decisions

把这段贴进新的 Claude 会话作为第一条消息的补充上下文，再配上 **Prompts Library → "Fixed Startup — 每次会话第一条"** 那条固定提示词即可。

### 3.2 收尾一个会话

```bash
python scripts/notion/sync.py log-session \
    --title "2026-04-10 Guardrail JSON Fix" \
    --type Implement \
    --handoff "把 guardrail.py 的 JSON 解析改成容错模式，失败率从 18% 降到 3%" \
    --files "src/rag/guardrail.py; tests/unit/test_guardrail.py" \
    --commit https://github.com/kogamishinyajerry-ops/AIAeroPlaneRag/commit/<sha>
```

### 3.3 把 Notion 任务推成 GitHub Issue

```bash
python scripts/notion/sync.py push-tasks
```

只处理 Status∈{Ready,In Progress} 且还没有 GitHub Issue URL 的任务，自动打 priority/p0 area/... 标签，Issue URL 写回 Notion。

### 3.4 查状态

```bash
python scripts/notion/sync.py status
```

---

## 4. 六个数据库的职责

| 数据库 | 写入时机 | 关键字段 |
|--------|---------|---------|
| **Phases** | 每个阶段启动前先建行、Exit 达成后置 Done | Context Pack (300-500字)、Exit Criteria、Priority (P0/P1/P2/Phase3+) |
| **Sessions** | 每次 Claude 会话结束后 append 一行 | Entry Prompt、Handoff Summary、Touched Files、Commit URL |
| **Tasks** | 任何一条"要干的事"都落这里 | Acceptance、Area、GitHub Issue、Commit/PR |
| **Decisions** | 任何跨会话的技术决策或事故都记一条 ADR | Context / Decision / Consequences |
| **Pinned Canonical Docs** | 只存摘要和 repo URL，**绝不复制全文** | Repo Path、GitHub URL、Summary |
| **Prompts Library** | 复用的提示词模板 | Scenario、Body、Use Count |

---

## 5. Prompts Library — 解决你最痛的那个点

已预置 6 条模板：
1. **Fixed Startup — 每次会话第一条** — 永远不再手写恢复上下文的指令
2. **Plan Next Phase** — 规划下一阶段时的标准指令
3. **Implement Task** — 执行单个任务时的标准指令
4. **Debug Incident** — 出 bug 时的调试指令
5. **Benchmark Run** — 跑基准的标准指令
6. **Docs Writing** — 更新文档的标准指令

**使用方式**：打开 Prompts Library → 复制 Body → 替换占位符（如 `<TASK_NAME>`）→ 粘贴到 Claude。

---

## 6. 安全 & 隔离

### 6.1 与 AI-Harness v1/v2 的隔离

- 本子树的数据库与 v1/v2 **完全无 relation**
- sync.py 只读写 `control_tower_ids.json` 里列出的 ID
- Isolation Governance Rules 页已明确写入"禁止跨子树 relation / 读 v1/v2 作为上下文"
- 任何违规写入必须先建一条 Incident Decision

### 6.2 凭证安全 ⚠️

**你在本次会话里粘贴的两个 token (NOTION_API_KEY / GITHUB_TOKEN) 已写入 `.env`，`.env` 已在 `.gitignore` 里，不会进 git。**
**但是：** 这两个 token 的明文已经出现在本次对话的历史里。强烈建议：
1. **功能调通后立即轮换**：
   - Notion：设置 → Connections → Claude Dev Workflow → 重新生成 Secret
   - GitHub：Settings → Developer settings → Personal access tokens → Regenerate
2. 轮换后只需更新 `.env` 里的对应值，其它都不用动。

---

## 7. 文件清单

| 文件 | 作用 |
|------|------|
| `scripts/notion/bootstrap_control_tower.py` | 一次性建塔脚本（可重跑，但会重复创建页面，谨慎） |
| `scripts/notion/sync.py` | 日常 CLI：status / restore / push-tasks / log-session |
| `scripts/notion/control_tower_ids.json` | 所有 page_id / db_id，sync.py 依赖这个文件 |
| `docs/NOTION_CONTROL_TOWER.md` | 本文档 |
| `.env` | NOTION_API_KEY / GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO |

---

## 8. 下一步可选扩展

1. **GitHub Actions 自动写 Session** — 每次 push 到 codex 分支自动追加 Session 行，commit sha 填进去。
2. **双向 Issue 同步** — GitHub Issue 关闭时自动把对应 Notion Task 置 Done。
3. **周度归档** — 每周把 Done 的 Tasks 和 Sessions 折叠到 History 页面，保持主表面干净。
4. **Decisions → ADR .md 导出** — 每月把 Decisions 表导出到 `docs/adr/` 便于 PR review。

如果要做这些，告诉我哪一条优先，我在 sync.py 里加子命令。
