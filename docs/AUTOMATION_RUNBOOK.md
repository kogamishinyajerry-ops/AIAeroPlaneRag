# AIAeroPlaneRag — 全自动开发链路 Runbook

> 目标：除了"在 Notion 里向 Opus 4.6 提问 / 裁决 Open Decisions"之外，所有开发动作都由 GSD 架构驱动自动跑。

---

## 1. 角色分工

| 角色 | 职责 | 触发方式 |
|------|------|---------|
| **你 (Human)** | 在 Notion 里让 Opus 4.6 写 Tasks / 裁决 Open Decisions / rotate tokens | 手动, Notion UI |
| **Autopilot (Cowork 定时任务)** | 每 4 小时扫一次 Tasks, 找 P0 Ready → 执行 → commit → push → 回写 Notion | Cowork Scheduled Task |
| **GH Actions: session-log** | 每次 push 自动 append Session 行 | GitHub 原生 webhook |
| **GH Actions: issue-close** | 关 Issue 时把对应 Task 置 Done | GitHub 原生 webhook |
| **GH Actions: nightly-sync** | 每天凌晨把新的 Ready 任务推成 GH Issue | cron |

---

## 2. 一次性手动设置 (必做)

### 2.1 把控制塔 share 给 Integration ❗

你移动页面到 workspace 根之后，集成的访问权限会掉。必须重新绑定：

1. 打开新移动后的 **AIAeroPlaneRag 控制塔** 根页面
2. 右上角 `···` → **Connections** → **Connect to** → 选 **Claude Dev Workflow**
3. 确认. 权限会递归到所有子页和数据库.

**验证**:
```bash
cd ~/AIAeroPlaneRag
python scripts/notion/sync.py status
# 应该能看到 phases/tasks 列表
```

### 2.2 跑 GSD Cockpit bootstrap

```bash
python scripts/notion/bootstrap_gsd_cockpit.py
```

会在根页面下新增 **GSD Development Cockpit** 和 **Automation Runbook** 两个子页。

### 2.3 配 GitHub repo secrets

打开 https://github.com/kogamishinyajerry-ops/AIAeroPlaneRag/settings/secrets/actions → New repository secret:

| Name | Value |
|------|-------|
| `NOTION_API_KEY` | 同 `.env` 里的那串 (以 `ntn_` 开头) |

`GITHUB_TOKEN` 会由 Actions 自动注入，不用手动配。

### 2.4 Rotate tokens ⚠️

对话历史里粘过明文 token，现在就去轮换：
- Notion: Settings → Connections → Claude Dev Workflow → Regenerate secret
- GitHub: Settings → Developer settings → Personal access tokens → regenerate

把新值写回 `.env` 和 GitHub secret。

---

## 3. 数据流图

```
 ┌────────────┐   human ask Opus 4.6     ┌─────────────────┐
 │   You      │ ───────────────────────▶ │  Notion Tasks   │
 └────────────┘                          │   (Ready)       │
                                         └────────┬────────┘
                                                  │ pick-task
                                                  ▼
┌───────────────────┐  4h cron   ┌──────────────────────────┐
│ Cowork Scheduler  │ ─────────▶ │  Autopilot Claude Agent  │
└───────────────────┘            │  read → code → test      │
                                 │  commit → push           │
                                 └──────┬───────────┬───────┘
                                        │           │
                                ┌───────▼──┐   ┌────▼────────┐
                                │  GitHub  │   │  Notion     │
                                │  Actions │   │  complete   │
                                └───┬──┬───┘   │  -task      │
                                    │  │       └─────────────┘
                  session-log ◀─────┘  └─▶ issue-close
                       │                       │
                       ▼                       ▼
                ┌──────────────┐        ┌──────────────┐
                │Notion Sessions│       │Notion Tasks  │
                │  (append)     │       │   → Done     │
                └──────────────┘        └──────────────┘
```

---

## 4. 日常使用

### 4.1 你要做的

1. 打开 Notion → AIAeroPlaneRag 控制塔 → GSD Development Cockpit
2. 看 "今日焦点" 和 "Autopilot 日志" 了解昨晚跑了什么
3. **只在 Open Decisions 里有 Incident 时介入** — 裁决 + 把 Task 重新置 Ready
4. 想加新任务：在 Notion 里 @Opus 4.6 写 prompt，让它补充到 Tasks 库（记得填 Acceptance）

### 4.2 Autopilot 自己做的

- Preflight: `sync.py status`
- Pick: 拉一条 P0 Ready
- Start: 置 In Progress
- Implement: 按 Acceptance 改代码、跑测试
- Commit & Push: 新分支 `auto/YYYYMMDD-HHMM-...`
- Success → `complete-task`，失败 → `block-task` + 建 Incident

### 4.3 GitHub Actions 自己做的

- push 事件 → `sync.py log-session` → Sessions 追加
- issue close → `sync.py close-issue` → Task 置 Done
- 每天 02:00 UTC → `sync.py push-tasks` → Ready → Issue

---

## 5. 安全不变量

1. **Notion 隔离**: sync.py 只读写 `control_tower_ids.json` 里列出的 DB，永远不碰 AI-Harness v1/v2。
2. **GitHub 隔离**: 所有 Action 的 `GITHUB_REPO` 环境变量锁死 `AIAeroPlaneRag`。
3. **Token 隔离**: `.env` 不入 git（`.gitignore` 已生效），Actions 用 repo secret。
4. **写入边界**: 单次 autopilot 改动 ≤ 15 文件；超过必须 block-task。
5. **In Progress 单并发**: 同时最多 1 条 In Progress。
6. **Decision append-only**: Incident 只追加，不覆盖。

违反任何一条 → Autopilot 自检时立即 block 并建 Incident。

---

## 6. 排障

| 症状 | 排查 |
|------|------|
| `sync.py status` 返回 404 | 检查 Notion 集成是否 share 到根页（见 2.1） |
| `sync.py status` 返回 401 | `.env` 里的 `NOTION_API_KEY` 过期了，去 rotate |
| GH Actions 报 `NOTION_API_KEY secret not set` | 按 2.3 配 secret |
| Autopilot 建的 Incident 堆积 | 任务描述太模糊；到 Tasks 表给 Acceptance 补细节 |
| `push-tasks` 报 403 | GitHub Token 缺 `issues:write` scope，rotate 时勾上 |

---

## 7. 扩展点 (v0.2+)

- `sync.py review-pr <url>` — 调用 engineering:code-review skill 写 review 到 PR comment
- `sync.py retro --week` — 汇总一周 Sessions 生成 retrospective，写进 Docs 表
- GH Action `adr-sync` — 把 Decisions=Decided 的行导出成 `docs/adr/NNN-xxx.md` 并开 PR
- Cowork Scheduled Task `daily-standup` — 每天早上 9 点把昨晚 Autopilot 结果用 engineering:standup skill 格式化后发到 Slack / 邮件

这些我已经准备好框架；告诉我优先级我往 sync.py 里加。
