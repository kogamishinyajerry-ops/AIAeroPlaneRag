# AeroPower-RAG

航空发动机适航法规智能问答系统（RAG + Multi-Agent）

## 项目目标

为航空发动机审定工程师提供 CCAR-33-R2 / FAR-33 / CS-E 三大适航体系的法规检索、问答与合规性验证能力。

## 架构

```
用户提问
  → Query Expansion (同义词扩展 中↔英, 意图检测)
  → Hybrid Retrieval (ChromaDB向量 + BM25 bigram + RRF融合)
  → Multi-Agent Flow (Planner → Tool → Checker → Answer Generator)
  → Guardrail (幻觉检测 + 事实核查)
  → 答案 + 引用 + 图谱洞察 + 质量评分
```

## 技术栈

- **后端**: FastAPI (Python 3.12+)
- **向量库**: ChromaDB + Ollama nomic-embed-text (768维)
- **图数据库**: Neo4j 5 社区版 (当前 mock)
- **文档处理**: llama-parse + unstructured
- **大模型**: Anthropic Claude (主) + OpenAI fallback
- **前端**: 原生 HTML5 + JS (无框架)
- **E2E**: Playwright

## 开发命令

```bash
# 启动后端
cd ~/AIAeroPlaneRag && uvicorn src.main:app --reload --port 8000

# 启动 Neo4j (docker)
docker-compose up -d

# 运行测试
pytest tests/ -v

# E2E 测试
npx playwright test
```

## 当前分支

`codex/v0.1.0-initial-release` — v0.1.0 已发布，v0.2 硬化中

## 当前进度 (2026-03-28)

### 已完成
- [x] v0.1.0 初版发布 (2026-03-26)
- [x] 测试基建 (unit/integration/e2e/benchmarks 目录)
- [x] BM25 bigram + 同义词扩展 (recall@3=100%, 25题)
- [x] 意图分类 (准确率100%, 30题)
- [x] 跨语言召回 ZH→EN 100% / EN→ZH 80%
- [x] 多代理系统 27 模块实现
- [x] 民航术语词典 150+ 术语
- [x] 条款全文提取 650 条
- [x] 查询性能提升 +97%

### 待完成
- [ ] **P0**: Guardrail JSON 解析失败率 < 5%
- [ ] **P0**: 意图检测准确率 >= 80% 基准验证
- [ ] **P0**: BM25 跨语言召回验证 (中→英 recall@3 >= 0.6)
- [ ] **P0**: API /health 完整性修复
- [ ] **P1**: 黄金集扩展至 >= 20 题
- [ ] **P1**: 性能基准自动化 (P95<2000ms)
- [ ] **P1**: UI E2E 完整覆盖 (5条关键路径)
- [ ] **P2**: Neo4j 真实接入
- [ ] **P2**: 置信度评分 7 维度量化
- [ ] **Phase 3**: 图谱虚拟化 (视口裁剪 + LOD三级标签)

## 关键文件

| 文件 | 说明 |
|------|------|
| `src/main.py` | FastAPI 主应用 (84KB) |
| `src/rag/vector_engine.py` | 向量检索引擎 |
| `src/rag/guardrail.py` | 事实核查护栏 |
| `src/rag/aviation_terminology.py` | 民航术语词典 (未提交) |
| `src/multi_agent/` | 27 模块多代理系统 (未提交) |
| `src/ontology/graph_store.py` | 本体图存储 (mock) |
| `src/api/routes/` | 模块化 API 路由 (未提交) |
| `docs/DEVELOPMENT_PLAN.md` | 4 阶段开发计划 |
| `evaluation/golden_set_sample.json` | 黄金集测试用例 |

## 风险与注意事项

1. **89 个未追踪文件** — 含完整多代理系统，需立即 commit
2. **Guardrail 脆弱** — LLM JSON 解析失败率高
3. **Neo4j 为 mock** — graph_store.py 未接入真实数据
4. **文档与代码有偏差** — DEVELOPMENT_PLAN.md (3/26) 滞后于代码
5. **向量嵌入依赖** — Ollama nomic-embed-text 需本地可用

---

*更新时间: 2026-03-28*
