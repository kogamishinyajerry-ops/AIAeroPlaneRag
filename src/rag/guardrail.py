import logging
import os
from typing import Dict, List

try:
    import openai
except ImportError:
    openai = None

from settings import has_real_value

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class FactCheckingGuardrail:
    """
    Verify that answers are supported by retrieved contexts.
    If the external verifier is unavailable, default to a conservative response.
    """

    def __init__(self):
        self.client = None
        api_key = os.getenv("ZHIPU_API_KEY")
        if openai and has_real_value(api_key):
            self.client = openai.OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
            logger.info("Guardrail initialized with GLM API.")
        else:
            logger.warning("Guardrail verifier is unavailable. Conservative fallback mode enabled.")
        self.has_external_verifier = self.client is not None

    def verify_response(self, query: str, generated_answer: str, retrieved_contexts: List[Dict]) -> Dict:
        if not retrieved_contexts:
            return {
                "status": "NOT_FOUND",
                "reasoning": "没有可用于校验的检索上下文，系统拒绝放行回答。",
                "safe_answer": "当前知识库中没有检索到足够证据，无法给出可靠回答。",
            }

        if not self.client:
            return {
                "status": "UNVERIFIED",
                "reasoning": "Guardrail 外部校验服务不可用，系统返回基于证据的保守摘要，而不是直接放行草稿答案。",
                "safe_answer": self._build_conservative_answer(retrieved_contexts),
            }

        context_str = "\n\n".join(
            [
                f"[Source: {item['metadata'].get('source', '?')} - {item['metadata'].get('section', '?')}]\n{item['text']}"
                for item in retrieved_contexts
            ]
        )

        system_prompt = """You are a strict fact-checking agent for aviation regulations.
Only approve statements fully supported by the provided contexts.

Rules:
1. Unsupported or invented claims => FAIL.
2. Contradictions => FAIL.
3. Supported but incomplete answers => PARTIAL.
4. Fully supported answers => PASS.

Output only:
STATUS: [PASS/PARTIAL/FAIL]
REASONING: [Chinese explanation]
SAFE_ANSWER: [safe Chinese answer]"""

        user_prompt = f"""### User Query
{query}

### Official Contexts
{context_str}

### Draft Answer
{generated_answer}"""

        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            result_text = response.choices[0].message.content
            return self._parse_guardrail_output(result_text, generated_answer, retrieved_contexts)
        except Exception as exc:
            logger.error("Guardrail execution failed: %s", exc)
            return {
                "status": "UNVERIFIED",
                "reasoning": f"Guardrail 外部校验执行失败：{exc}",
                "safe_answer": self._build_conservative_answer(retrieved_contexts),
            }

    def _build_conservative_answer(self, retrieved_contexts: List[Dict]) -> str:
        lines = ["系统当前无法完成外部事实校验，以下仅返回检索证据中的保守摘要："]
        for index, ctx in enumerate(retrieved_contexts[:3], start=1):
            metadata = ctx.get("metadata", {})
            snippet = ctx["text"].split("\n", 1)[-1][:140].strip()
            lines.append(
                f"[{index}] {metadata.get('chapter', '未知章节')} / {metadata.get('section', '未知条款')}: {snippet}"
            )
        return "\n".join(lines)

    def _parse_guardrail_output(self, raw_text: str, original_draft: str, retrieved_contexts: List[Dict]) -> Dict:
        status = "FAIL"
        reasoning = ""
        safe_answer = original_draft

        try:
            for line in raw_text.strip().split("\n"):
                if line.startswith("STATUS:"):
                    status = line.replace("STATUS:", "").strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
                elif line.startswith("SAFE_ANSWER:"):
                    safe_answer = line.replace("SAFE_ANSWER:", "").strip()

            if status not in {"PASS", "PARTIAL", "FAIL"}:
                return {
                    "status": "UNVERIFIED",
                    "reasoning": "Guardrail 返回了非标准状态，系统改为保守返回。",
                    "safe_answer": self._build_conservative_answer(retrieved_contexts),
                }
            return {"status": status, "reasoning": reasoning, "safe_answer": safe_answer}
        except Exception:
            return {
                "status": "UNVERIFIED",
                "reasoning": "无法解析 Guardrail 输出，系统改为保守返回。",
                "safe_answer": self._build_conservative_answer(retrieved_contexts),
            }
