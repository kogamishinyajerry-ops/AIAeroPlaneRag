from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from dotenv import load_dotenv

from src.settings import PROCESSED_DATA_DIR

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    return [token for token in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", (text or "").lower()) if token]


def _text_score(text: str, query: str) -> int:
    haystack = (text or "").lower()
    tokens = _tokenize(query)
    score = 0
    for token in tokens:
        if token in haystack:
            score += 2 if len(token) == 1 else 4
    if query and query.lower() in haystack:
        score += 6
    return score


def _normalize_type(entity_type: str) -> str:
    entity_type = (entity_type or "unknown").lower()
    regulation_types = {"chapter", "section", "regulation", "requirement", "clause"}
    component_types = {"component", "rotorpart", "statorpart", "accessory", "module", "system"}
    support_types = {
        "test",
        "material",
        "parameter",
        "failuremode",
        "hazardousengineeffect",
        "lifelimitedpart",
        "compliance",
        "guidance",
    }
    if entity_type in regulation_types:
        return "regulation"
    if entity_type in component_types:
        return "component"
    if entity_type in support_types:
        return "support"
    return "support"


class OntologyGraphStore:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")
        self.driver = None
        self.node_count = 0

        self.fallback_graph = self._load_fallback_graph()
        self.entities_by_id: dict[str, dict[str, Any]] = {}
        self.relationships: list[dict[str, Any]] = []
        self.adjacency: dict[str, set[str]] = defaultdict(set)
        self.edge_lookup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self.relationship_counter: Counter[str] = Counter()

        self._build_fallback_indexes()

        if not GraphDatabase:
            logger.warning("neo4j not installed. Using fallback graph mode.")
            return

        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            self._refresh_graph_state()
            logger.info("Connected to Neo4j.")
        except Exception as exc:
            logger.warning("Neo4j unavailable: %s", exc)
            self.driver = None

    @property
    def has_graph_data(self) -> bool:
        return self.node_count > 0

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def _refresh_graph_state(self) -> None:
        if not self.driver:
            self.node_count = 0
            return
        try:
            with self.driver.session() as session:
                self.node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        except Exception as exc:
            logger.warning("Failed to inspect graph state: %s", exc)
            self.node_count = 0

    def _ensure_connection(self) -> bool:
        """
        检查 Neo4j 连接是否仍然活跃。
        如果连接已断开，尝试重新连接；失败则降级到 fallback 模式。
        返回 True 表示连接正常，False 表示已降级。
        """
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            self._refresh_graph_state()
            return True
        except Exception as exc:
            logger.warning("Neo4j connection lost: %s. Reconnecting...", exc)
            try:
                old_driver = self.driver
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self.driver.verify_connectivity()
                self._refresh_graph_state()
                logger.info("Neo4j reconnected successfully.")
                return True
            except Exception as reconnect_exc:
                logger.warning("Neo4j reconnection failed: %s. Falling back to JSON mode.", reconnect_exc)
                if old_driver:
                    try:
                        old_driver.close()
                    except Exception:
                        pass
                self.driver = None
                self.node_count = 0
                return False

    def _load_fallback_graph(self) -> Dict[str, Any]:
        candidates = [
            Path(PROCESSED_DATA_DIR) / "CCAR-33-R2_professional_graph.json",
            Path(PROCESSED_DATA_DIR) / "CCAR-33_graph.json",
        ]
        for graph_path in candidates:
            if not graph_path.exists():
                continue
            try:
                return json.loads(graph_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load fallback graph JSON %s: %s", graph_path, exc)
        return {"entities": [], "relationships": []}

    def _build_fallback_indexes(self) -> None:
        self.entities_by_id.clear()
        self.relationships.clear()
        self.adjacency.clear()
        self.edge_lookup.clear()
        self.relationship_counter.clear()

        for entity in self.fallback_graph.get("entities", []):
            entity_id = entity.get("id")
            if not entity_id:
                continue
            normalized = {
                "id": entity_id,
                "label": entity.get("name") or entity_id,
                "name": entity.get("name") or entity_id,
                "type": _normalize_type(entity.get("type", "")),
                "rawType": entity.get("type", "unknown"),
                "description": entity.get("description", ""),
            }
            self.entities_by_id[entity_id] = normalized

        for relationship in self.fallback_graph.get("relationships", []):
            source = relationship.get("source")
            target = relationship.get("target")
            if not source or not target:
                continue
            normalized = {
                "source": source,
                "target": target,
                "type": relationship.get("type", "RELATED_TO"),
                "description": relationship.get("description", ""),
            }
            self.relationships.append(normalized)
            self.adjacency[source].add(target)
            self.adjacency[target].add(source)
            self.edge_lookup[(source, target)].append(normalized)
            self.edge_lookup[(target, source)].append(normalized)
            self.relationship_counter[normalized["type"]] += 1

    def query_graph(self, keyword: str) -> List[Dict[str, Any]]:
        if self.driver and self.has_graph_data and self._ensure_connection():
            return self._query_neo4j(keyword)
        return self._query_fallback_graph(keyword)

    def _query_neo4j(self, keyword: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            with self.driver.session() as session:
                records = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE coalesce(a.name, '') CONTAINS $kw
                       OR coalesce(b.name, '') CONTAINS $kw
                       OR coalesce(a.description, '') CONTAINS $kw
                       OR coalesce(b.description, '') CONTAINS $kw
                    RETURN coalesce(a.name, a.id) AS a_name,
                           type(r) AS rel_type,
                           coalesce(r.description, '') AS rel_desc,
                           coalesce(b.name, b.id) AS b_name
                    LIMIT 20
                    """,
                    kw=keyword,
                )
                for record in records:
                    results.append(
                        {
                            "regulation": record["a_name"],
                            "component": record["b_name"],
                            "relationship": record["rel_type"],
                            "parameter": record["rel_desc"],
                            "description": f"{record['a_name']} --[{record['rel_type']}]--> {record['b_name']}",
                        }
                    )
        except Exception as exc:
            logger.error("Graph query failed: %s", exc)
        return results

    def _query_fallback_graph(self, keyword: str) -> List[Dict[str, Any]]:
        keyword_lower = (keyword or "").lower()
        results: List[Dict[str, Any]] = []
        for relationship in self.relationships:
            source = self.entities_by_id.get(relationship["source"], {})
            target = self.entities_by_id.get(relationship["target"], {})
            haystacks = [
                source.get("label", ""),
                source.get("description", ""),
                target.get("label", ""),
                target.get("description", ""),
                relationship.get("description", ""),
            ]
            if not any(keyword_lower in str(value).lower() for value in haystacks):
                continue
            results.append(
                {
                    "regulation": source.get("label", ""),
                    "component": target.get("label", ""),
                    "relationship": relationship.get("type", "RELATED_TO"),
                    "parameter": relationship.get("description", ""),
                    "description": f"{source.get('label', '')} --[{relationship.get('type', 'RELATED_TO')}]--> {target.get('label', '')}",
                }
            )
        return results[:20]

    def get_graph_snapshot(self) -> Dict[str, Any]:
        return self.get_subgraph(limit=18, include_parameters=False)

    def get_subgraph(
        self,
        *,
        query: str = "",
        node_id: Optional[str] = None,
        limit: int = 18,
        include_parameters: bool = False,
    ) -> Dict[str, Any]:
        if self.driver and self.has_graph_data and self._ensure_connection():
            neo4j_result = self._get_neo4j_subgraph(query=query, node_id=node_id, limit=limit)
            if neo4j_result.get("nodes"):
                return neo4j_result
        return self._get_fallback_subgraph(
            query=query,
            node_id=node_id,
            limit=limit,
            include_parameters=include_parameters,
        )

    def _get_neo4j_subgraph(self, *, query: str, node_id: Optional[str], limit: int) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        try:
            with self.driver.session() as session:
                records = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE $node_id IS NULL
                       OR coalesce(a.id, a.name) = $node_id
                       OR coalesce(b.id, b.name) = $node_id
                    RETURN coalesce(a.id, a.name) AS source_id,
                           coalesce(a.name, a.id) AS source_name,
                           toLower(coalesce(a.type, 'unknown')) AS source_type,
                           coalesce(a.description, '') AS source_description,
                           coalesce(b.id, b.name) AS target_id,
                           coalesce(b.name, b.id) AS target_name,
                           toLower(coalesce(b.type, 'unknown')) AS target_type,
                           coalesce(b.description, '') AS target_description,
                           type(r) AS rel_type,
                           coalesce(r.description, '') AS rel_description
                    LIMIT $limit
                    """,
                    node_id=node_id,
                    limit=limit,
                )
                for record in records:
                    source_id = record["source_id"]
                    target_id = record["target_id"]
                    nodes[source_id] = {
                        "id": source_id,
                        "label": record["source_name"],
                        "type": _normalize_type(record["source_type"]),
                        "description": record["source_description"],
                    }
                    nodes[target_id] = {
                        "id": target_id,
                        "label": record["target_name"],
                        "type": _normalize_type(record["target_type"]),
                        "description": record["target_description"],
                    }
                    edges.append(
                        {
                            "source": source_id,
                            "target": target_id,
                            "type": record["rel_type"],
                            "description": record["rel_description"],
                        }
                    )
        except Exception as exc:
            logger.error("Neo4j subgraph query failed: %s", exc)

        return {
            "mode": "neo4j",
            "query": query,
            "focusNodeId": node_id,
            "summary": self._build_summary(query, list(nodes.values()), edges),
            "nodes": self._sort_nodes(list(nodes.values())),
            "edges": edges[: max(limit * 2, 12)],
            "stats": {"nodeCount": len(nodes), "edgeCount": len(edges)},
        }

    def _get_fallback_subgraph(
        self,
        *,
        query: str,
        node_id: Optional[str],
        limit: int,
        include_parameters: bool,
    ) -> Dict[str, Any]:
        if not self.entities_by_id:
            return {
                "mode": "fallback",
                "query": query,
                "focusNodeId": node_id,
                "summary": "No graph data is available.",
                "nodes": [],
                "edges": [],
                "stats": {"nodeCount": 0, "edgeCount": 0},
            }

        seeds = self._select_seed_nodes(query=query, node_id=node_id)
        selected = self._expand_seed_nodes(seeds, limit=limit, include_parameters=include_parameters)
        if not selected:
            selected = self._overview_nodes(limit=limit)

        edges = self._collect_edges(selected)
        nodes = [self.entities_by_id[node_id] | {"degree": len(self.adjacency.get(node_id, []))} for node_id in selected]

        return {
            "mode": "fallback",
            "query": query,
            "focusNodeId": node_id or (seeds[0] if seeds else None),
            "summary": self._build_summary(query, nodes, edges),
            "nodes": self._sort_nodes(nodes),
            "edges": edges,
            "stats": {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "relationshipTypes": dict(self.relationship_counter),
            },
        }

    def _select_seed_nodes(self, *, query: str, node_id: Optional[str]) -> List[str]:
        if node_id and node_id in self.entities_by_id:
            return [node_id]
        if not query:
            return self._overview_nodes(limit=5)

        scored: List[tuple] = []
        for entity_id, entity in self.entities_by_id.items():
            text = " ".join([entity.get("label", ""), entity.get("description", ""), entity.get("rawType", "")])
            score = _text_score(text, query)
            if entity.get("type") == "regulation":
                score += 2
            if score > 0:
                scored.append((score, entity_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entity_id for _, entity_id in scored[:4]]

    def _overview_nodes(self, *, limit: int) -> List[str]:
        ranked = sorted(
            self.entities_by_id.values(),
            key=lambda entity: (
                0 if entity["type"] == "regulation" else 1 if entity["type"] == "component" else 2,
                -len(self.adjacency.get(entity["id"], [])),
                entity["label"],
            ),
        )
        return [entity["id"] for entity in ranked[:limit]]

    def _expand_seed_nodes(self, seeds: list[str], *, limit: int, include_parameters: bool) -> List[str]:
        if not seeds:
            return []

        selected: List[str] = []
        queue = deque(seeds)
        seen = set()

        def priority(entity_id: str) -> tuple[int, int, str]:
            entity = self.entities_by_id[entity_id]
            entity_type = entity.get("type", "support")
            type_rank = {"regulation": 0, "component": 1, "support": 2}.get(entity_type, 3)
            return (type_rank, -len(self.adjacency.get(entity_id, [])), entity.get("label", ""))

        while queue and len(selected) < limit:
            current = queue.popleft()
            if current in seen or current not in self.entities_by_id:
                continue
            seen.add(current)

            entity = self.entities_by_id[current]
            if entity["rawType"].lower() == "parameter" and not include_parameters:
                continue

            selected.append(current)
            neighbors = sorted(self.adjacency.get(current, []), key=priority)
            for neighbor in neighbors:
                if neighbor in seen or neighbor not in self.entities_by_id:
                    continue
                neighbor_entity = self.entities_by_id[neighbor]
                if neighbor_entity["rawType"].lower() == "parameter" and not include_parameters:
                    continue
                queue.append(neighbor)

        return selected[:limit]

    def _collect_edges(self, selected_node_ids: list[str]) -> List[Dict[str, Any]]:
        selected = set(selected_node_ids)
        edges: List[Dict[str, Any]] = []
        seen = set()
        for relationship in self.relationships:
            source = relationship["source"]
            target = relationship["target"]
            if source not in selected or target not in selected:
                continue
            key = (source, target, relationship["type"])
            if key in seen:
                continue
            seen.add(key)
            edges.append(relationship)
        return edges[: max(len(selected_node_ids) * 2, 12)]

    def _sort_nodes(self, nodes: list[dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            nodes,
            key=lambda item: (
                0 if item["type"] == "regulation" else 1 if item["type"] == "component" else 2,
                item["label"],
            ),
        )

    def _build_summary(self, query: str, nodes: list[dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        if not nodes:
            return "当前问题没有匹配到可解释的图谱证据。"

        regulation_count = sum(1 for node in nodes if node["type"] == "regulation")
        component_count = sum(1 for node in nodes if node["type"] == "component")
        support_count = sum(1 for node in nodes if node["type"] == "support")

        focus = f"围绕“{query}”" if query else "当前知识域"
        parts = [
            f"{focus}构建局部解释子图",
            f"{regulation_count} 个法规节点",
            f"{component_count} 个部件节点",
        ]
        if support_count:
            parts.append(f"{support_count} 个支撑节点")
        parts.append(f"{len(edges)} 条关系")
        return " | ".join(parts)
