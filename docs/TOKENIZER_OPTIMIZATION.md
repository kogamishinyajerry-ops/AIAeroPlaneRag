# 检索分词器优化方案

## 问题诊断

### 当前实现缺陷（main.py 1896-1935行）
1. **N-gram爆炸**：4字术语生成7个token（2+2+3=7），如"压气机" → `压气,气机,压气机`
2. **术语破坏**：专业术语被拆解导致无法精准匹配（"喘振裕度" → `喘振,裕度,振裕`）
3. **英文处理粗糙**：复合标识符未拆分（`FAA_AC_33`整体匹配而非`FAA,AC,33`）
4. **无停用词过滤**：无效token（的、是、the）占用索引空间

## 优化方案

### 核心改进
```python
# 1. 专业术语优先匹配
technical_terms = {'喘振裕度', '压气机', '失速速度', ...}
# 2. 英文复合词智能拆分
FAA_AC_33.27-1A → ['FAA', 'AC', '33', '27', '1A']
# 3. 中文仅用2-gram（取消3-4gram减少冗余）
# 4. 停用词过滤
zh_stopwords = {'的', '是', '在', ...}
en_stopwords = {'the', 'and', 'of', ...}
```

### 性能对比
| 指标 | 原始 | 优化 | 变化 |
|-----|------|------|------|
| Token数（压气机喘振裕度） | 16个 | 10个 | **-37.5%** |
| 英文标识符拆分 | 1个 | 5个 | **+400%** |
| 召回率 | 100% | 100% | 持平 |
| 执行时间（1000次） | 6.04ms | 12.99ms | +115% |

**性能分析**：
- 绝对耗时：6ms → 13ms（单次0.007ms，可忽略）
- 实际影响：索引阶段可接受，查询阶段需监控
- 优化空间：LRU缓存已启用，热查询无性能损失

## 实施步骤

### 1. 代码替换
```python
# main.py 1896行
from tokenizer_enhanced import tokenize_query

# 替换原函数
def _tokenize_query(q):
    return tokenize_query(q)
```

### 2. 数据迁移
```bash
# 重建索引（必需）
python main.py --rebuild-index

# 验证召回率
python tokenizer_test.py
```

### 3. 监控指标
- 查询响应时间（P99 < 100ms）
- Top10结果相关性（人工评估）
- 无匹配率（应<5%）

## 风险控制

### 回滚方案
```python
# 保留原始函数作为后备
def _tokenize_query_fallback(q):
    return _tokenize_query_original(q)
```

### 灰度发布
1. 首日10%流量使用新分词器
2. 监控无匹配率是否突增
3. 逐步提升至50% → 100%

## 后续优化方向

1. **动态词典**：从高频查询中学习新术语
2. **同义词扩展**：`发动机` → `motor, engine, 引擎`
3. **拼写纠错**：`压气机` ← `压汽机`（编辑距离1）
4. **词干提取**：`compressors` → `compressor`（需NLTK库）

## 文件清单

- `/Users/Zhuanz/tokenizer_enhanced.py` - 增强分词器实现
- `/Users/Zhuanz/tokenizer_test.py` - 测试套件
- `/Users/Zhuanz/tokenizer_test_results.txt` - 测试结果
- `/Users/Zhuanz/TOKENIZER_OPTIMIZATION.md` - 本文档

## 预期收益

- **精度提升**：减少37.5%的无效token，提高匹配准确度
- **召回保障**：专业术语整体匹配，避免漏检
- **维护性**：词典驱动架构，易于扩展新术语

---

*生成时间: 2026-03-25*
*测试覆盖: 4个典型案例 + 性能基准测试*
