import re
import json
import logging
from typing import Any, Dict, List, Optional
from src.api.models import Citation, GraphInsight

logger = logging.getLogger(__name__)
def _build_context_block(contexts: List[Dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            f"[Source: {item['metadata'].get('source', '?')} > {item['metadata'].get('chapter', '?')} > {item['metadata'].get('section', '?')}]\n{item['text']}"
            for item in contexts
        ]
    )



def _fallback_answer(contexts: List[Dict[str, Any]]) -> str:
    """生成高质量的保守回答（不使用LLM）"""
    if not contexts:
        return "当前知识库中没有检索到与问题直接相关的条款证据，暂时无法给出可靠回答。建议缩小查询范围或使用更具体的条款号进行查询。"

    # 提取关键信息
    answer_parts = []
    answer_parts.append("根据检索到的法规资料，相关要求如下：\n")

    # 按来源组织答案
    for idx, ctx in enumerate(contexts[:5], 1):
        if not isinstance(ctx, dict):
            continue
        metadata = ctx.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        title = metadata.get("title", "") or ""
        source = metadata.get("source", "").replace(".md", "") if metadata.get("source") else ""
        text = ctx.get("text", "") or ""
        original_text = ctx.get("original_text", "") or ""

        # 优先使用original_text
        content = original_text if original_text else text

        # 提取条款号
        section_num = ""
        if title:
            try:
                section_match = re.search(r'[§§]\s*([\d.]+[a-z]?)|第\s*([\d.]+)\s*条', title)
                if section_match:
                    section_num = section_match.group(1) or section_match.group(2) or ""
            except Exception:
                pass

        # 格式化内容
        formatted_content = _format_content(content)

        # 添加到答案
        if section_num:
            answer_parts.append(f"**{source} §{section_num}**")
        else:
            answer_parts.append(f"**{source}**")

        if title and "§" not in title and "条" not in title:
            # 如果标题没有条款号，添加简化标题
            short_title = title.split(">")[-1][:50]
            answer_parts.append(f"（{short_title}）")

        answer_parts.append(formatted_content)
        answer_parts.append("")

    # 添加说明
    answer_parts.append("注：以上内容基于现有知识库自动提取，如需准确解读请核对原文。")

    return "\n".join(answer_parts)



def _generate_thinking_process(query: str, contexts: list) -> str:
    """生成LLM思考过程描述"""
    if not contexts:
        return "思考：未检索到直接相关的法规条款，无法给出明确答案。"

    # 提取关键信息
    sources = set()
    keywords_found = []
    for ctx in contexts[:5]:
        metadata = ctx.get("metadata", {})
        source = metadata.get("source", "")
        if source:
            sources.add(source.replace(".md", ""))
        # 提取关键词匹配
        text = ctx.get("text", "")
        query_lower = query.lower()
        for kw in ["喘振", "裕度", "超转", "试验", "要求", "必须", "应当"]:
            if kw in query_lower and kw in text:
                keywords_found.append(kw)

    thinking_parts = [
        f"问题分析：用户询问关于「{query}」的要求",
        f"证据评估：检索到{len(contexts)}条相关条款",
        f"来源范围：{', '.join(sorted(sources))}" if sources else "来源：知识库",
    ]

    if keywords_found:
        thinking_parts.append(f"关键术语匹配：{', '.join(set(keywords_found))}")

    return " | ".join(thinking_parts)



def _extract_reasoning_steps(query: str, contexts: list) -> list[str]:
    """提取推理步骤"""
    steps = [
        f"1. 分析问题：识别查询中的关键术语（如'要求'、'规定'等）"
    ]

    if contexts:
        steps.append(f"2. 检索证据：在知识库中找到{len(contexts)}条相关条款")
        steps.append("3. 条款分析：逐条比对检索结果，提取具体要求")
        steps.append("4. 回答组织：按结构化格式组织答案，标注条款来源")
    else:
        steps.append("2. 检索结果：未找到直接相关条款")
        steps.append("3. 保守回答：基于证据不足原则，建议用户核对原文")

    return steps



def _format_content(content: str) -> str:
    """格式化内容，提取关键要求"""
    if not content:
        return ""

    # 移除多余空白
    content = re.sub(r'\s+', ' ', content.strip())

    # 按句子分割
    sentences = re.split(r'[。；;]', content)

    # 提取关键句子（包含"必须"、"应当"、"要求"等关键词）
    key_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 5:
            continue
        if any(kw in sentence for kw in ["必须", "应当", "要求", "不得", "禁止", "需要", "应"]):
            key_sentences.append(f"• {sentence}。")

    # 如果没有关键句子，返回前几句
    if not key_sentences:
        key_sentences = [f"• {s}。" for s in sentences[:3] if s.strip()]

    return "\n".join(key_sentences[:8])  # 限制数量



def generate_answer_with_glm(query: str, contexts: List[Dict[str, Any]], graph_insights: List[Dict[str, Any]]) -> str:
    from src.api.dependencies.deps import services
    glm_client = services.glm_client
    
    if not glm_client:
        return _fallback_answer(contexts)

    # 构建图谱证据
    graph_text = ""
    if graph_insights:
        graph_text = "\n\n知识图谱证据:\n" + "\n".join(
            [
                f"- {item.get('regulation', '?')} --[{item.get('relationship', '?')}]--> {item.get('component', '?')}"
                for item in graph_insights[:6] if item.get('regulation') or item.get('component')
            ]
        )

    # 系统提示 - 专业航空法规助手（增强版）
    system_prompt = """你是一位专业的民航法规咨询专家。

## 核心原则
1. **严格依据提供的法规内容回答** - 只使用检索到的法规条款，不编造信息
2. **引用具体条款号** - 回答中必须包含具体的条款编号（如 §25.1、第33.5条）
3. **结构化回答** - 按照要求类型分点陈述，清晰明了
4. **标注不确定性** - 如果检索证据不足，明确说明"根据现有资料无法确定"
5. **使用中文回答** - 专业、准确、简洁

## 回答结构
请按以下结构组织回答：

### 【直接回答】
用1-2句话直接回答核心问题

### 【条款依据】
逐条列出相关条款，格式：
- **[来源X 条款号]** 具体要求描述
- **[来源X 条款号]** 具体要求描述

### 【适用说明】
说明适用范围和限制条件

### 【相关条款】
如有等效或关联条款（CAAC/FAA/EASA），列出对比

## 思考要求
在回答前，请先进行以下分析：
1. **问题类型判断**：这是数值要求、试验方法、还是设计标准？
2. **证据匹配**：检索结果中有哪些直接相关的条款？
3. **跨规章关联**：是否有CAAC/FAA/EASA的等效条款？
4. **不确定性评估**：哪些信息是明确的，哪些是不确定的？"""

    # 构建用户提示
    context_blocks = []
    for i, ctx in enumerate(contexts[:5], 1):
        text = ctx.get("text", "")
        metadata = ctx.get("metadata", {})
        title = metadata.get("title", "")
        source = metadata.get("source", "").replace(".md", "")

        context_blocks.append(f"[来源{i}: {source} - {title}]\n{text}")

    user_prompt = f"""用户问题：{query}

检索到的法规内容：
{chr(10).join(context_blocks)}{graph_text}

## 参考示例

示例1：
问：喘振裕度的要求是什么？
答：
### 【直接回答】
喘振裕度要求在发动机所有工作包线内不低于15%。

### 【条款依据】
- **[CCAR-33-R2 §33.65(a)]** 在所有工作包线内，喘振裕度不低于15%
- **[FAR-33 §33.65(a)]** 等效要求：喘振裕度不低于15%

### 【适用说明】
适用于所有航空发动机型号审定。

---

现在请基于以上法规内容，按照上述结构给出专业、准确的回答。"""

    try:
        # 根据API类型选择模型
        minimax_key = os.getenv("MINIMAX_API_KEY")
        model = "abab6.5s-chat" if minimax_key else "glm-4-flash"

        response = glm_client.chat.completions.create(
            model=model,
            temperature=0.2,  # 降低随机性，提高准确性
            max_tokens=1500,
            timeout=30,  # 30秒超时保护
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"[LLM] Generated {len(answer)} chars answer using {model}")
        return answer
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return _fallback_answer(contexts)



