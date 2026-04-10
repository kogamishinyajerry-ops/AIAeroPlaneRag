"""
Tool Agent - 执行检索操作
优化版：实现多策略并行检索
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from .base import BaseAgent, AgentRole, AgentMessage, RetrievalResult

logger = logging.getLogger(__name__)


class ToolAgent(BaseAgent):
    """
    Tool Agent 负责：
    1. 执行向量检索（支持多种策略）
    2. 执行图谱查询（可选）
    3. 合并多策略检索结果
    4. 返回结构化检索结果

    优化：实现A∥B → C模式，并行执行多种检索策略后合并
    """

    def __init__(self, vector_engine, graph_store=None):
        super().__init__("RetrievalTool", AgentRole.TOOL)
        self.vector_engine = vector_engine
        self.graph_store = graph_store

    async def process(self, message: AgentMessage) -> AgentMessage:
        """根据计划执行检索"""
        plan_data = message.data.get("plan", {})
        strategy = plan_data.get("retrieval_strategy", "simple")
        query = plan_data.get("query", "")
        top_k = plan_data.get("top_k", 3)
        use_graph = plan_data.get("use_graph", False)
        follow_up_queries = plan_data.get("follow_up_queries", [])

        self.log("info", f"Executing {strategy} retrieval for: {query[:50]}...")

        # 根据策略执行检索（所有搜索操作通过 asyncio.to_thread 卸到线程池）
        if strategy == "multi_source":
            contexts = await self._multi_source_search(query, top_k, follow_up_queries=follow_up_queries)
        elif strategy == "expanded":
            contexts = await self._expanded_search(query, top_k, follow_up_queries=follow_up_queries)
        elif strategy == "graph_first":
            contexts = await self._graph_first_search(query, top_k)
        else:
            contexts = await self._simple_search(query, top_k)

        # 执行图谱查询（如果需要）
        graph_data = None
        if use_graph:
            graph_data = self._execute_graph_search(query, top_k=20)

        result = RetrievalResult(
            contexts=contexts,
            graph_data=graph_data,
            relevance_scores=None,  # 由Checker评估
            success=True,
            error=None
        )

        self.log("info", f"Retrieval complete: {len(contexts)} contexts, "
                        f"graph nodes: {len(graph_data.get('nodes', [])) if graph_data else 0}")

        return AgentMessage(
            role=AgentRole.TOOL,
            content="",
            data={
                "result": {
                    "contexts": result.contexts,
                    "graph_data": result.graph_data,
                    "success": result.success,
                    "error": result.error,
                },
                "plan": plan_data
            },
            metadata={"tool": self.name, "strategy": strategy}
        )

    async def _simple_search(self, query: str, top_k: int) -> list:
        """简单检索策略（async，线程池执行）"""
        try:
            results = await asyncio.to_thread(self.vector_engine.search, query, top_k=top_k)
            return results
        except Exception as e:
            self.log("error", f"Simple search failed: {e}")
            return []

    async def _expanded_search(self, query: str, top_k: int, follow_up_queries: Optional[List[str]] = None) -> list:
        """
        扩展检索策略：同义词扩展 + 原始查询 + 合并去重
        实现多查询并行 → 结果合并
        """
        try:
            from src.rag.vector_engine import expand_synonyms, tokenize_text

            # 生成多种查询变体
            tokens = tokenize_text(query)
            synonyms = expand_synonyms(query)

            # 构建多个查询
            queries = [
                query,  # 原始查询
                " ".join(tokens[:5]),  # 核心词
                " ".join(synonyms[:5]) if synonyms else query,  # 同义词
            ]
            queries.extend(follow_up_queries or [])

            # 去重
            queries = list(dict.fromkeys(q for q in queries if q.strip()))

            # 并行执行多个查询（使用 asyncio.gather 提高并发）
            async def search_one(q: str) -> list:
                return await asyncio.to_thread(self.vector_engine.search, q, top_k=top_k)

            all_search_results = await asyncio.gather(
                *[search_one(q) for q in queries[:3]],
                return_exceptions=True
            )

            # 合并去重
            all_results = []
            seen_ids = set()
            for results in all_search_results:
                if isinstance(results, Exception):
                    continue
                for r in results:
                    chunk_id = r.get("metadata", {}).get("chunk_id", "")
                    if chunk_id and chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        all_results.append(r)

            # 按相关性排序返回
            return all_results[:top_k * 2]

        except Exception as e:
            self.log("error", f"Expanded search failed: {e}")
            return await self._simple_search(query, top_k)

    async def _multi_source_search(self, query: str, top_k: int, follow_up_queries: Optional[List[str]] = None) -> list:
        """
        多来源检索策略：从不同角度检索并合并
        用于比较查询等需要多角度覆盖的场景
        """
        try:
            from src.rag.vector_engine import tokenize_text

            # 提取查询中的关键实体
            tokens = tokenize_text(query)

            # 生成多角度查询
            queries = [query]

            # 如果查询中有"和"/"与"/"vs"等，分割成多个子查询
            separators = ["和", "与", "和/与", "vs", "VS", "Versus", "对比", "比较"]
            for sep in separators:
                if sep in query:
                    parts = query.split(sep)
                    for part in parts:
                        part = part.strip()
                        if part and len(part) > 2:
                            queries.append(part)
                    break

            # 如果没有分割，尝试提取名词短语
            if len(queries) == 1:
                import re
                phrases = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', query)
                phrases = [p for p in phrases if len(p) >= 2]
                for phrase in phrases[-2:]:
                    if phrase != query:
                        queries.append(phrase)

            queries.extend(follow_up_queries or [])

            # 并行执行多查询
            async def search_one(q: str) -> list:
                return await asyncio.to_thread(self.vector_engine.search, q.strip(), top_k=top_k)

            all_search_results = await asyncio.gather(
                *[search_one(q) for q in queries[:4]],
                return_exceptions=True
            )

            # 合并去重
            all_results = []
            seen_ids = set()
            for results in all_search_results:
                if isinstance(results, Exception):
                    continue
                for r in results:
                    chunk_id = r.get("metadata", {}).get("chunk_id", "")
                    if chunk_id and chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        all_results.append(r)

            return all_results[:top_k * 3]

        except Exception as e:
            self.log("error", f"Multi-source search failed: {e}")
            return await self._simple_search(query, top_k)

    async def _graph_first_search(self, query: str, top_k: int) -> list:
        """
        图谱优先检索策略：
        1. 从图谱找到相关节点
        2. 基于节点进行检索
        """
        try:
            # 先用简单检索尝试
            results = await asyncio.to_thread(self.vector_engine.search, query, top_k=top_k * 2)

            # 如果结果充足，直接返回
            if len(results) >= top_k:
                return results

            # 否则尝试扩展检索
            return await self._expanded_search(query, top_k)

        except Exception as e:
            self.log("error", f"Graph-first search failed: {e}")
            return await self._simple_search(query, top_k)

    def _execute_graph_search(self, query: str, top_k: int = 20) -> Optional[Dict[str, Any]]:
        """执行图谱查询"""
        try:
            if self.graph_store and hasattr(self.graph_store, "get_subgraph"):
                graph_data = self.graph_store.get_subgraph(query=query, limit=top_k)
                if graph_data:
                    return graph_data

            from src.core.config import PROCESSED_DATA_DIR
            import json

            graph_path = PROCESSED_DATA_DIR / "knowledge_graph" / "graph.json"
            if not graph_path.exists():
                return None

            with open(graph_path, encoding="utf-8") as f:
                data = json.load(f)

            nodes = data.get("nodes", {})
            edges = data.get("edges", [])

            # 简单过滤：返回包含查询词的节点
            query_lower = query.lower()
            filtered_nodes = {
                nid: n for nid, n in nodes.items()
                if query_lower in f"{n.get('title', '')} {n.get('label', '')}".lower()
            }

            # 如果过滤结果太少，返回随机节点
            if len(filtered_nodes) < 5:
                filtered_nodes = dict(list(nodes.items())[:top_k])

            node_ids = set(filtered_nodes.keys())
            filtered_edges = [
                e for e in edges
                if e["source"] in node_ids and e["target"] in node_ids
            ]

            return {
                "nodes": [{"id": nid, **n} for nid, n in list(filtered_nodes.items())[:top_k]],
                "edges": filtered_edges[:top_k * 3]
            }
        except Exception as e:
            self.log("error", f"Graph search failed: {e}")
            return None
