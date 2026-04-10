# 开发工作流 - 强制多Agent质量保证

## 🛡️ 核心原则

**所有开发变更必须通过多Agent验证，否则质量不足。**

---

## 📋 开发流程

### 添加新规章

```bash
# 使用 build.py 添加（自动触发Agent验证）
python src/build.py add --file data/raw/FAR-29.pdf --expected 500

# 系统会自动：
# 1. 解析文档
# 2. 运行5个质量门禁检查
# 3. 不通过则阻止继续
# 4. 通过后运行优化周期
```

### 质量门禁

| **门禁** | **说明** | **是否强制** | **阈值** |
|----------|----------|--------------|--------|
| 解析质量 | 解析结果质量是否达标 | ✅ 是 | 0.7 |
| 内容完整性 | 节点是否有内容摘要 | ✅ 是 | 0.8 |
| 术语收录 | 专业术语是否被识别 | ❌ 否 | 0.5 |
| 跨文档关联 | 是否建立与其他规章的关联 | ❌ 否 | 0.3 |
| 查询效果 | 查询是否能返回结果 | ❌ 否 | 0.6 |

### 强制模式

```python
from quality_assurance import mandatory_agent_validation

# 必须通过才能继续
passed = await mandatory_agent_validation("data/raw/FAR-29.pdf", expected_sections=500)
if not passed:
    raise Exception("质量检查未通过，无法继续")
```

---

## 🤖 多Agent优化周期

### 自动触发时机

1. **添加新文档后**
2. **修改核心代码后**
3. **定期维护时**

### 手动运行

```bash
# 方式1: 使用build.py
python src/build.py optimize

# 方式2: 直接运行钩子
python src/dev_hooks.py --optimize

# 方式3: 在代码中调用
from dev_hooks import run_agent_optimization_cycle
run_agent_optimization_cycle()
```

### Agent执行的任务

| **Agent** | **任务** | **输出** |
|----------|----------|--------|
| TerminologyAgent | 发现新术语、验证术语 | 术语收录建议 |
| QualityAgent | 内容完整性检查、缺口检测 | 问题列表 |
| LinkageAgent | 发现跨规章关联、主题聚类 | 关联网络 |
| QueryAgent | 分析查询模式、检测低分查询 | 优化建议 |
| DocumentAgent | 检测新文档、验证解析 | 文档状态 |

---

## 🚨 开发规范

### ✅ DO - 必须做

1. **所有新文档添加必须通过 build.py**
   ```bash
   python src/build.py add --file data/raw/NewReg.pdf
   ```

2. **代码修改后运行优化**
   ```bash
   python src/build.py optimize
   ```

3. **提交前验证**
   ```bash
   python src/build.py validate
   ```

### ❌ DON'T - 禁止

1. ❌ 直接修改解析后的JSON而不运行Agent检查
2. ❌ 跳过质量门禁继续开发
3. ❌ 忽略Agent的建议和警告
4. ❌ 禁用强制模式 (mandatory_mode=False)

---

## 📁 文件结构

```
src/
├── quality_assurance.py    # 质量保证系统（强制验证）
├── dev_hooks.py             # 开发钩子（自动触发）
├── build.py                 # 构建系统（主入口）
│
├── multi_agent/
│   ├── agent_base.py        # Agent基础框架
│   ├── specialized_agents.py # 专业Agent实现
│   ├── expansion_workflow.py # 扩展工作流
│   └── orchestrator.py      # 编排器
│
└── rag/
    ├── enhanced_knowledge_base.py  # 增强知识库
    └── aviation_terminology.py   # 术语系统
```

---

## 🔧 集成到开发流程

### Makefile 集成

```makefile
# Makefile
.PHONY: add validate optimize

add:
	@echo "📦 添加新规章..."
	python3 src/build.py add --file $(FILE)

validate:
	@echo "🔍 验证知识库..."
	python3 src/build.py validate

optimize:
	@echo "🤖 运行Agent优化..."
	python3 src/build.py optimize

pre-commit:
	@echo "🔍 预提交检查..."
	python3 src/dev_hooks.py pre-commit --check
```

使用:
```bash
make add FILE=data/raw/FAR-29.pdf
make validate
make optimize
```

### Git Hook 集成

```bash
# .git/hooks/pre-commit
#!/bin/bash
python3 src/dev_hooks.py pre-commit --check
```

---

## 📊 质量报告

所有质量报告保存在：
```
data/reports/qa/qa_YYYYMMDD_HHMMSS.json
```

报告包含：
- 各门禁的通过/失败状态
- 具体问题和建议
- 修复指导

---

## ⚠️ 强制模式说明

当 `mandatory_mode=True` 时：

- ✅ 质量不通过会**阻止操作继续**
- ✅ 必须修复问题才能重试
- ✅ 适用于生产环境的关键变更

当 `mandatory_mode=False` 时：

- ⚠️ 质量不通过仅**记录警告**
- ⚠️ 允许继续（但建议修复）
- ⚠️ 适用于开发环境的快速迭代

---

## 🎯 最佳实践

1. **开发时**: 使用非强制模式快速迭代
2. **发布前**: 切换到强制模式严格验证
3. **定期**: 每天运行一次完整优化周期
4. **持续**: 监控Agent的建议，不断改进

---

**版本**: 2.0
**最后更新**: 2024-03-24
**状态**: 🟢 强制多Agent架构已启用
