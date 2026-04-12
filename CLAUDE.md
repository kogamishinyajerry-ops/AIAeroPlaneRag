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

`codex/v0.1.0-initial-release` — v0.2 Done，v0.3 Done，v0.4 Done，v0.5 Done，v0.6 Done，v0.7 Done，**Backlog 清空**

## 当前进度 (2026-04-12)

### 已完成
- [x] v0.1.0 初版发布 (2026-03-26)
- [x] 测试基建 (unit/integration/e2e/benchmarks 目录)
- [x] BM25 bigram + 同义词扩展 (recall@3=100%, 25题)
- [x] 意图分类 (准确率100%, 30题)
- [x] 跨语言召回 ZH→EN 100% / EN→ZH 80%
- [x] 多代理系统 27 模块实现
- [x] 民航术语词典 150+ 术语
- [x] 条款全文提取 675 条 (含 FAR-33 69条)
- [x] 查询性能提升 +97%
- [x] **v0.3** Graph LOD 三级标签 + 视口裁剪 (41 JS单元测试)
- [x] **v0.3** PageIndex 树内容填充 (52/53 叶节点, `scripts/enrich_pageindex.py`)
- [x] **v0.3** AC 预处理块接入向量索引 (675 chunks, 14 单元测试)
- [x] **v0.3** 中英混合 BM25 基准 (recall@3=100%, `benchmarks/multilingual_mixed_bench.py`)
- [x] **v0.3** FAR-33 全文结构化接入 (69 条款, `data/processed/FAR-33_chunks.json`)
- [x] **P0** Guardrail JSON 解析硬化 (4层策略 + 41测试)
- [x] **P0** API /health 完整性修复 (status标准化 + 磁盘块计数fallback + 22测试)
- [x] **P1** 黄金集扩展至 30题 (CCAR-33/FAR-33/CS-E/cross + 中英双语)
- [x] **P1** 性能基准自动化 P95<2000ms (`benchmarks/performance_bench.py`, 6测试)
- [x] **P1** UI E2E 完整覆盖 5条关键路径 (page.route() mock CI + `tests/e2e/app.spec.ts`)
- [x] **P2** 回归测试 CI 脚本 (`scripts/run_all_benchmarks.sh` + `.github/workflows/ci.yml`)
- [x] **P2** 置信度评分 7 维度量化 (`src/rag/confidence.py` + QueryResponse.confidenceBreakdown)
- [x] **P2** Neo4j 真实接入 — schema/constraints/indexes (`scripts/neo4j/setup_schema.py`, 25测试)
- [x] **v0.4** CS-E EASA chunks 接入验收测试 (`tests/unit/test_cse_ingestion.py`, 16测试)
- [x] **v0.4** 同义词词典扩展至 205+ 条 (T4.1) — 新增7类航空术语 (涡轮冷却/材料缺陷/维修工艺/噪声排放/气动性能/燃烧室/符合性方法)
- [x] **v0.4** Hybrid Retrieval 集成测试 (`tests/integration/test_hybrid_retrieval.py`, 19测试) — RRF+BM25+跨语言
- [x] **v0.4** Multi-Agent Flow 集成测试 (`tests/integration/test_multi_agent_flow.py`, 15测试) — Planner→Tool→Checker→Answer
- [x] **v0.5** CI pipeline 加入 integration + root-level API 测试步骤 (`.github/workflows/ci.yml`)
- [x] **v0.5** 黄金集 BM25 自动评估脚本 (`benchmarks/golden_set_bm25_bench.py`) — recall@3=90%, recall@5=93.3% ✅ PASS
- [x] **v0.5** graph 404 响应结构化 (`src/api/routes/graph.py` → `{"code":"node_not_found",...}`)
- [x] **v0.5** `tests/test_main_api.py` 修复 health 字段名 (vector_db, graph_db)
- [x] **v0.6** E2E API smoke test 23测试 (`tests/integration/test_api_smoke.py`) — 真实BM25+mocked LLM
- [x] **v0.6** `scripts/run_all_benchmarks.sh` 加入黄金集BM25评估步骤 (全6项通过)
- [x] **v0.7** `expand_mixed_query` n-gram滑动窗口提取 (核心机/FADEC长句召回修复)
- [x] **v0.7** `data/processed/aviation_definitions_chunks.json` 5条定义语料块
- [x] **v0.7** `src/rag/aviation_terminology.py` GENERAL_CONCEPT_TERMS 词典
- [x] **v0.7** `tests/unit/test_definitions_ingestion.py` 20测试
- [x] **v0.7** `tests/integration/test_pageindex_load.py` 15测试 (PageIndex负载+吞吐量)
- [x] **v0.7** 黄金集 recall@3=96.7%, recall@5=100% (general类: 33%→100%)

### 测试覆盖汇总 (689 Python测试, 41 JS测试)
| 模块 | 文件 | 测试数 |
|------|------|--------|
| BM25/向量检索 | test_bm25_tokenize, test_cross_language_recall | 多 |
| Guardrail解析 | test_guardrail_parsing.py | 41 |
| Health端点 | test_health_endpoint.py | 22 |
| 性能基准 | test_performance_benchmarks.py | 6 |
| 置信度7维 | test_confidence_7dim.py + test_confidence_integration.py | 41 |
| Neo4j接入 | test_neo4j_fallback.py + test_neo4j_real_connection.py | 52 |
| CS-E接入 (v0.4) | test_cse_ingestion.py | 16 |
| Hybrid Retrieval (v0.4) | tests/integration/test_hybrid_retrieval.py | 19 |
| Multi-Agent (v0.4) | tests/integration/test_multi_agent_flow.py | 15 |
| E2E (Playwright) | tests/e2e/app.spec.ts | 5 |

### 待完成 (无 Notion Backlog)
全部计划任务已完成。下一轮迭代待用户规划。

## 关键文件

| 文件 | 说明 |
|------|------|
| `src/main.py` | FastAPI 主应用 |
| `src/rag/vector_engine.py` | 向量检索引擎 + BM25 + collect_indexable_chunks |
| `src/rag/guardrail.py` | 事实核查护栏 |
| `src/rag/pageindex_engine.py` | PageIndex 树结构推理检索 |
| `src/rag/aviation_terminology.py` | 民航术语词典 205+ 条 (v0.4 扩展) |
| `src/multi_agent/` | 27 模块多代理系统 |
| `src/ontology/graph_store.py` | 本体图存储 (mock) |
| `scripts/enrich_pageindex.py` | CCAR-33-R2 树节点内容填充 |
| `scripts/notion/sync.py` | Notion ↔ GitHub GSD 同步工具 |
| `docs/DEVELOPMENT_PLAN.md` | 4 阶段开发计划 (已同步至 v0.3) |
| `data/processed/FAR-33_chunks.json` | FAR-33 69条款预处理块 |
| `data/processed/FAR-33_Full.md` | FAR-33 全文 Markdown (来自PDF) |
| `data/processed/CCAR-33-R2_structure.json` | CCAR-33-R2 层级树 (52节点有text) |
| `evaluation/golden_set_sample.json` | 黄金集测试用例 |
| `benchmarks/multilingual_mixed_bench.py` | 中英混合召回基准 (recall@3=100%) |
| `tests/unit/test_chunk_ingestion.py` | AC块接入验收测试 (14测试) |
| `tests/unit/test_far33_ingestion.py` | FAR-33接入验收测试 (11测试) |
| `tests/unit/test_graph_virtualization.js` | LOD+视口裁剪JS测试 (41测试) |

## 风险与注意事项

1. **Guardrail 脆弱** — LLM JSON 解析失败率高，是最高 P0 风险
2. **Neo4j 为 mock** — `graph_store.py` 未接入真实数据
3. **向量嵌入依赖** — ChromaDB + Ollama nomic-embed-text 需本地可用
4. **Bash 沙箱网络限制** — 外部 API 调用需通过 Agent 子进程 (已知限制)
5. **CI 覆盖** — GitHub Actions 已覆盖 unit + integration + root-level API 测试

---

*更新时间: 2026-04-12 (v0.7)*
