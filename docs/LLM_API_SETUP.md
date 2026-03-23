# LLM API 配置指南

## 支持的 LLM 提供商

| 提供商 | 用途 | 获取方式 |
|--------|------|----------|
| **智谱 GLM** | 主要 LLM (生成+校验) | https://open.bigmodel.cn/ |
| **OpenAI** | Embeddings (可选) | https://platform.openai.com/ |

---

## 快速配置步骤

### 1. 获取智谱 GLM API Key

1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册/登录账号
3. 进入 API Keys 页面创建新的 API Key
4. 复制 API Key (格式类似 `xxxxxxxxxxxxxxxxxxxxx.xxxxxxxx`)

### 2. 配置 .env 文件

在项目根目录创建 `.env` 文件：

```bash
# 复制示例配置
copy .env.example .env
```

然后编辑 `.env` 文件，填入您的 API Key：

```env
# 智谱 GLM API Key (主要 LLM)
ZHIPU_API_KEY=你的智谱API密钥

# 可选：OpenAI API (用于更好的 embeddings)
OPENAI_API_KEY=你的OpenAI密钥

# 应用模式改为 real
APP_MODE=real

# 更新文档版本标识
DOCUMENT_VERSION=CCAR-33-R2-2016-real
```

### 3. 验证配置

运行验证脚本：

```bash
.venv/Scripts/python.exe scripts/verify_llm_config.py
```

---

## API 使用说明

### GLM-4-Flash 模型

系统使用 **GLM-4-Flash** 模型，特点：
- 响应速度快
- 成本低 (约 ¥0.1/1M tokens)
- 适合 RAG 场景

### 预估用量

单次查询消耗：
- 输入: ~2000 tokens (上下文)
- 输出: ~500 tokens (回答)
- 成本: ~¥0.0001/次

1000次查询预估成本：**~¥0.1**

---

## 故障排除

### 问题：LLM 仍然显示 mock

检查 `.env` 文件中 `ZHIPU_API_KEY` 是否为真实值（不是 `your_zhipu_api_key_here`）

### 问题：API 调用失败

1. 检查网络连接
2. 确认 API Key 余额充足
3. 查看日志：`logs/backend.err.log`

### 问题：回答质量不理想

考虑升级到 GLM-4 模型（需修改代码中的 model 参数）
