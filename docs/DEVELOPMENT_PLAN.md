# AeroPower-RAG 开发计划 v1.0

> 基于 `docs/REQUIREMENTS.md` 制定 | 2026-03-26 | 最后同步: 2026-04-12 (v0.4)

---

## 阶段划分

```
第一阶段：测试基建（1-2天）     ← 让所有已有功能可测试、可观测
第二阶段：质量达标（2-3天）     ← P0 问题修复，确保发布门槛通过
第三阶段：自动化闭环（2-3天）   ← E2E + 黄金集 + 性能基准
第四阶段：持续优化（ongoing）   ← P1/P2 功能深化
```

---

## 第一阶段：测试基建

### T1.1 建立测试目录结构 ✅ DONE
```
tests/
├── unit/
│   ├── test_tokenize.py              ✅
│   ├── test_synonym_expansion.py     ✅
│   ├── test_bm25.py                  ✅
│   ├── test_intent_detection.py      ✅
│   ├── test_infer_agency.py          ✅
│   ├── test_pageindex_engine.py      ✅ (29 tests)
│   ├── test_chunk_ingestion.py       ✅ (14 tests, v0.3)
│   ├── test_far33_ingestion.py       ✅ (11 tests, v0.3)
│   └── test_graph_virtualization.js  ✅ (41 tests, v0.3)
├── integration/
│   ├── test_hybrid_retrieval.py
│   ├── test_multi_agent_flow.py
│   └── test_api_query.py
└── e2e/
    └── test_ui_workflow.py
```

**验收：**
- [x] `pytest tests/unit/test_tokenize.py::test_chinese_bigram` 通过
- [x] `pytest tests/` 在 CI 中可执行（无 ImportError）

### T1.2 补全 tokenize_for_bm25 单元测试 ✅ DONE
**目标：** 覆盖率 100%

**用例：**
| 用例 | 输入 | 期望输出 |
|------|------|---------|
| 纯中文 | `"压气机喘振"` | `["压","气","机","喘","振","压气","气机","机喘","喘振"]` |
| 纯英文 | `"engine test"` | `["engine","test"]` |
| 混合 | `"压气机engine"` | 含中文二字组 + 英文单词 |
| 空字符串 | `""` | `[]` |
| 全标点 | `"！？，"` | `[]` |

### T1.3 补全 expand_synonyms 单元测试 ✅ DONE
**用例：**
| 用例 | 输入 | 期望 |
|------|------|------|
| 中文→英 | `"喘振裕度"` | 含 `"surge margin"`、`"stall margin"` |
| 英文→中 | `"engine"` | 含 `"发动机"` |
| 无同义词 | `"foobar"` | 返回原词 |
| 链式扩展 | `"涡轮"`（有二级同义词） | 扩展至二级 |

### T1.4 补全 inferAgency 单元测试 ✅ DONE
**用例：**
| 用例 | 输入 | 期望 |
|------|------|------|
| CCAR 前缀 | `{"document": "CCAR-33-R2"}` | `"CAAC"` |
| FAR 前缀 | `{"document": "FAR-25"}` | `"FAA"` |
| CS 前缀 | `{"document": "CS-E"}` | `"EASA"` |
| group 优先 | `{"group": "FAA", "document": "CCAR-33"}` | `"FAA"` |
| 无匹配 | `{"id": "node-1"}` | `""` |

### T1.5 建立意图分类测试集 ✅ DONE
**样本：** 6 类各 5 题 = 30 题，放入 `evaluation/intent_classification_set.json`

**验收：** ✅ 分类准确率 100%（30 题测试集）

---

## 第二阶段：质量达标（P0 修复）

### T2.1 Guardrail 核查通过率提升（P0）⚠️ 待验证
**问题：** PARTIAL 比例过高

**根因分析：**
1. 当前 Checker 输出 JSON 解析失败率高
2. `safe_answer_builder` 过度保守

**修复方案：**
- 增加 JSON 容错：支持带 markdown 包裹的 JSON 解析
- 改进 prompt：要求 Checker 只返回符合格式的输出
- 增加重试直到格式正确或达到最大次数

**验收：**
- [ ] `golden_set_sample.json` 中 80% 答案达到 PARTIAL 以上
- [ ] JSON 解析失败率 < 5%

### T2.2 意图检测准确率评估与优化（P0）✅ DONE
**结果：** 基于规则匹配，准确率 100%（30/30 题）

**验收：**
- [x] 意图分类准确率 ≥ 80%（30 题测试集）— 实际 100%

### T2.3 BM25 同义词扩展效果验证（P0）✅ DONE
**结果：**
- 中英混合 recall@3 = 100%（25/25 题），`benchmarks/multilingual_mixed_bench.py`
- 跨语言召回 ZH→EN 100% / EN→ZH 80%

**验收：**
- [x] 跨语言召回测试集通过率 ≥ 70% — 实际 100%

### T2.4 API `/health` 完整性检查 ⚠️ 待完成
**修复项：**
- [ ] `vector_db` 显示 `connected`/`disconnected` 正确
- [ ] `llm` 显示 `connected`/`disconnected` 正确
- [ ] `vector_db_count` 显示实际索引文档数

---

## 第三阶段：自动化闭环

### T3.1 黄金回归测试集（Golden Set）扩展 ⚠️ 待完成
**当前：** 5 题（`golden_set_sample.json`）
**目标：** ≥ 20 题，覆盖：

| 类别 | 题数 | 示例 |
|------|------|------|
| 法规要求 | 5 | "CCAR-33 对喘振裕度的要求" |
| 方法步骤 | 3 | "如何进行压气机效率测试" |
| 定义解释 | 3 | "什么是喘振裕度" |
| 数值查询 | 3 | "喘振裕度的最小限值" |
| 对比分析 | 3 | "FAR-33 与 CS-E 的差异" |
| 交叉引用 | 3 | "CCAR-33 与 CCAR-25 的关系" |

**评估指标：** recall@3 ≥ 0.7

### T3.2 性能基准自动化
**指标：**
| 指标 | 目标 | 测量方式 |
|------|------|---------|
| P95 首次检索延迟 | < 2000ms | `pytest --benchmark` |
| 缓存命中延迟 | < 100ms | 第二次相同查询 |
| BM25 索引构建 | < 30s（万条文档） | 日志时间戳差 |

**工具：** `pytest-benchmark` + 自定义性能钩子

### T3.3 UI E2E 测试（Playwright）
**关键路径（必须覆盖）：**
1. [ ] 发送查询 → 收到答案 → 答案包含引用
2. [ ] 点击证据卡片 → 查看详情 → 点击返回 → 列表保留
3. [ ] 切换辖区筛选 → 证据列表即时更新
4. [ ] 切换图谱视图 → 全图加载（节点着色正确）
5. [ ] 切换模式描述 → 文案正确更新

### T3.4 CI 流水线 🔄 In Progress (v0.3)
```
PR 触发：
  1. pytest tests/unit/ + tests/integration/
  2. Python syntax check
  3. lint（可选）

Main/Merge 触发：
  1. 以上全部
  2. Golden Set recall@3 评估
  3. 性能基准测试
```

**当前进展 (v0.3):**
- `scripts/run_all_benchmarks.sh` — 正在实现
- GitHub Actions workflow `.github/workflows/ci.yml` — 正在实现

---

## 第四阶段：持续优化（ongoing）

### P1 级

#### T4.1 同义词词典扩展至 200+ 条 ✅ DONE (v0.4)
**结果：** 71 → 205 个 key，699 个同义词条目

**实现：**
- [x] 涡轮冷却系统术语 (20 条): TBC、气膜冷却、涡轮进口温度等
- [x] 材料缺陷与失效术语 (22 条): LCF/HCF、蠕变、热腐蚀等
- [x] 维修工艺术语 (20 条): LLP、翻修周期、孔探检查等
- [x] 噪声与排放术语 (15 条): EPNL、NOx、CAEP 等
- [x] 压气机气动性能术语 (22 条): 喘振裕度、特性图、坎贝尔图等
- [x] 燃烧室燃油系统术语 (17 条): 当量比、热斑、出口温度分布等
- [x] 适航符合性验证方法术语 (18 条): MOC、符合性方法、型号合格证等

#### T4.2 图谱节点缺失 document 字段监控 ✅ DONE (v0.3)
**结果：** `tests/unit/test_graph_document_monitor.py` (93 行，覆盖 inferAgency 降级行为)

#### T4.3 PageIndex 树检索落地 ✅ DONE (v0.3)
**结果：**
- [x] `/api/v1/query/pageindex` 端点可调用 (`src/api/routes/query_pageindex.py`)
- [x] PageIndex 树节点内容填充完成 (52/53 叶节点)

### P2 级

#### T5.1 置信度评分 7 维度量化 ✅ DONE (v0.3)
**结果：** `src/rag/confidence.py` + `QueryResponse.confidenceBreakdown`，41 个测试

#### T5.2 Neo4j 图数据库真实接入 ✅ DONE (v0.3)
**结果：** `scripts/neo4j/setup_schema.py` schema 脚本；52 个单元测试（全 mock）

#### T5.3 多语言 Query 增强 ✅ DONE (v0.3)
**结果：** 中英混合查询 recall@3 = 100%（25/25 题）

**实现：**
- [x] `expand_query_multilingual()` 支持纯中文、纯英文、中英混合
- [x] `tokenize_for_bm25()` bigram 分词支持双语
- [x] BM25 同义词扩展覆盖 205+ 航空术语 (v0.4 扩展)

---

## 第五阶段：v0.4 Sprint 新增 (2026-04-12)

### 已完成
- [x] **CS-E EASA chunks 接入验收测试** — `tests/unit/test_cse_ingestion.py` (16测试)
- [x] **Hybrid Retrieval 集成测试** — `tests/integration/test_hybrid_retrieval.py` (19测试)，RRF数学验证+BM25跨语言
- [x] **Multi-Agent Flow 集成测试** — `tests/integration/test_multi_agent_flow.py` (15测试)，Planner→Tool→Checker→Answer
- [x] **P0 测试修复** — graph 404 结构化 detail；health 字段名规范化；EN→ZH 测试去 flaky
- [x] **CI pipeline 扩展** — ci.yml 加入 integration tests + root-level API tests

---

## 任务优先级矩阵

```
         紧急度
          高    低
       ┌──────┬──────┐
  高   │ T2.1 │ T4.1 │
  重   │ T2.2 │ T4.3 │
  要   │ T2.3 │ T5.1 │
  度   │ T3.1 │      │
       ├──────┼──────┤
  低   │ T1.x │ T5.2 │
       │ T3.2 │ T5.3 │
       │ T3.3 │      │
       │ T2.4 │      │
       └──────┴──────┘
```

---

## 下一步行动（Next Sprint — v0.5 建议）

**当前状态 (2026-04-12):** 527 Python 测试 + 41 JS 测试，全部通过。

**建议 v0.5 优先执行：**
```
P1: 黄金集 BM25 自动评估 (benchmarks/golden_set_bm25_bench.py)
P1: 实时 RAG 端到端 smoke test (无 LLM mock)
P2: PageIndex 端点压力测试
P2: 图谱知识链接数据加载至 Neo4j
```

**立即可运行验证：**
```bash
pytest tests/unit/ tests/integration/ -q        # 527 Python tests
pytest tests/ --ignore=tests/e2e -q             # 627 tests (含 root-level)
node tests/unit/test_graph_virtualization.js    # 41 JS tests
```
