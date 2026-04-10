# AeroPower-RAG 开发计划 v1.0

> 基于 `docs/REQUIREMENTS.md` 制定 | 2026-03-26

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

### T1.1 建立测试目录结构
```
tests/
├── unit/
│   ├── test_tokenize.py
│   ├── test_synonym_expansion.py
│   ├── test_bm25.py
│   ├── test_intent_detection.py
│   └── test_infer_agency.py
├── integration/
│   ├── test_hybrid_retrieval.py
│   ├── test_multi_agent_flow.py
│   └── test_api_query.py
└── e2e/
    └── test_ui_workflow.py
```

**验收：**
- [ ] `pytest tests/unit/test_tokenize.py::test_chinese_bigram` 通过
- [ ] `pytest tests/` 在 CI 中可执行（无 ImportError）

### T1.2 补全 tokenize_for_bm25 单元测试
**目标：** 覆盖率 100%

**用例：**
| 用例 | 输入 | 期望输出 |
|------|------|---------|
| 纯中文 | `"压气机喘振"` | `["压","气","机","喘","振","压气","气机","机喘","喘振"]` |
| 纯英文 | `"engine test"` | `["engine","test"]` |
| 混合 | `"压气机engine"` | 含中文二字组 + 英文单词 |
| 空字符串 | `""` | `[]` |
| 全标点 | `"！？，"` | `[]` |

### T1.3 补全 expand_synonyms 单元测试
**用例：**
| 用例 | 输入 | 期望 |
|------|------|------|
| 中文→英 | `"喘振裕度"` | 含 `"surge margin"`、`"stall margin"` |
| 英文→中 | `"engine"` | 含 `"发动机"` |
| 无同义词 | `"foobar"` | 返回原词 |
| 链式扩展 | `"涡轮"`（有二级同义词） | 扩展至二级 |

### T1.4 补全 inferAgency 单元测试
**用例：**
| 用例 | 输入 | 期望 |
|------|------|------|
| CCAR 前缀 | `{"document": "CCAR-33-R2"}` | `"CAAC"` |
| FAR 前缀 | `{"document": "FAR-25"}` | `"FAA"` |
| CS 前缀 | `{"document": "CS-E"}` | `"EASA"` |
| group 优先 | `{"group": "FAA", "document": "CCAR-33"}` | `"FAA"` |
| 无匹配 | `{"id": "node-1"}` | `""` |

### T1.5 建立意图分类测试集
**样本：** 6 类各 5 题 = 30 题，放入 `evaluation/intent_classification_set.json`

**验收：** 分类准确率 ≥ 80%（当前规则匹配，需评估）

---

## 第二阶段：质量达标（P0 修复）

### T2.1 Guardrail 核查通过率提升（P0）
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

### T2.2 意图检测准确率评估与优化（P0）
**问题：** 当前规则匹配，真实准确率未知

**行动：**
1. 用 `evaluation/intent_classification_set.json` 跑一遍，得出 baseline 准确率
2. 若 < 80%：引入 LLM-based 意图分类（轻量 prompt）

**验收：**
- [ ] 意图分类准确率 ≥ 80%（30 题测试集）

### T2.3 BM25 同义词扩展效果验证（P0）
**验证方法：**
1. 准备 10 对中↔英 查询对（如 "发动机" ↔ "engine"）
2. 分别用中/英文查询，验证召回率
3. 中→英 recall@3 ≥ 0.6

**验收：**
- [ ] 跨语言召回测试集通过率 ≥ 70%

### T2.4 API `/health` 完整性检查
**修复项：**
- [ ] `vector_db` 显示 `connected`/`disconnected` 正确
- [ ] `llm` 显示 `connected`/`disconnected` 正确
- [ ] `vector_db_count` 显示实际索引文档数

---

## 第三阶段：自动化闭环

### T3.1 黄金回归测试集（Golden Set）扩展
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

### T3.4 CI 流水线
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

---

## 第四阶段：持续优化（ongoing）

### P1 级

#### T4.1 同义词词典扩展至 200+ 条
**当前：** ~120 条
**目标：** ≥ 200 条

**扩充方向：**
- 涡轮冷却系统术语
- 材料缺陷术语
- 维修工艺术语
- 噪声与排放术语

#### T4.2 图谱节点缺失 document 字段监控
**问题：** graph API 某些节点缺少 `document` 字段，导致 `inferAgency()` 返回灰色

**行动：**
- 在 `graph-enhancements.js` 中增加降级日志
- 分析缺失来源：是数据问题还是提取逻辑问题

#### T4.3 PageIndex 树检索落地
**状态：** 代码存在，未充分测试

**验收：**
- [ ] `/api/v1/query/pageindex` 端点可调用
- [ ] 返回结构化树形检索结果

### P2 级

#### T5.1 置信度评分 7 维度量化
**当前：** 简单加权平均

**实现：**
- 来源覆盖（0-1）：引用来源种类数
- 引用密度（0-1）：答案中引用段落占比
- 术语精确度（0-1）：专业术语出现频率
- 交叉验证（0-1）：CAAC/FAA/EASA 多来源验证
- 数值特异性（0-1）：答案含具体数值/限值
- 权威权重（0-1）：CCAR/FAA/EASA 加权
- 一致性（0-1）：Guardrail PASS 则为 1，否则按比例

#### T5.2 Neo4j 图数据库真实接入
**状态：** 当前 graph_store 为 mock

**行动：**
- 验证 Neo4j 连接（`scripts/test_neo4j_direct.py`）
- 将 `knowledge_links` 数据加载至 Neo4j
- 替换 mock graph_store 为真实实现

#### T5.3 多语言 Query 增强
**目标：** 支持中英混合查询（如 "compressor 压气机 喘振"）

**实现：**
- 分别对中文部分和英文部分进行分词
- 合并去重后构建扩展查询
- BM25 + 向量检索同步支持

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

## 下一步行动（Next Sprint）

**建议优先执行（T1 + T2 交叉进行）：**

```
Week 1:
  Day 1-2: T1.2 + T1.3（tokenize + synonyms 单元测试）
  Day 3:   T1.4 + T1.5（inferAgency + 意图分类测试集）
  Day 4-5: T3.1（黄金集扩展至 20 题）

Week 2:
  Day 1-2: T2.1（Guardrail 通过率提升）
  Day 3:   T2.2（意图检测准确率评估）
  Day 4:   T2.3（BM25 跨语言召回验证）
  Day 5:   T3.2 + T3.3（性能基准 + Playwright 基建）
```

**立即可做（不需要等待）：**
1. `pytest tests/unit/test_tokenize.py` 验证 bigram 分词
2. 用 Postman/curl 手动跑一遍 `/api/v1/query` 观察日志输出
3. 用浏览器 DevTools 验证图谱节点着色
