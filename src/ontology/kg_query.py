import json
import logging
from src.settings import PROCESSED_DATA_DIR
logger = logging.getLogger(__name__)

def load_knowledge_graph() -> tuple[dict, dict]:
    """加载知识图谱数据"""
    graph_dir = PROCESSED_DATA_DIR / "knowledge_graph"
    try:
        graph_file = graph_dir / "graph.json"
        if graph_file.exists():
            with open(graph_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("nodes", {}), data.get("edges", [])
    except Exception as e:
        logger.warning(f"Loading knowledge graph failed: {e}")
    return {}, []



def query_knowledge_graph_nodes(query: str, nodes: dict, limit: int = 10) -> list[dict]:
    """根据查询关键词查找相关节点"""
    query_lower = query.lower()
    keywords = set(query_lower.split())

    results = []
    for node_id, node in nodes.items():
        score = 0
        label = node.get("label", "").lower()
        node_type = node.get("type", "")

        # 完全匹配
        if query_lower in label:
            score += 10

        # 关键词匹配
        for keyword in keywords:
            if len(keyword) >= 2 and keyword in label:
                score += 3

        # 类型加分
        if node_type in ["section", "requirement", "component"]:
            score += 1

        if score > 0:
            results.append({
                "id": node_id,
                "label": node.get("label", ""),
                "type": node_type,
                "score": score,
                "properties": node.get("properties", {})
            })

    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]



def get_node_neighbors(node_id: str, edges: list, depth: int = 1) -> list[dict]:
    """获取节点的邻居"""
    neighbors = set()
    current_level = {node_id}

    for _ in range(depth):
        next_level = set()
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source in current_level:
                neighbors.add(target)
                next_level.add(target)
            if target in current_level:
                neighbors.add(source)
                next_level.add(source)
        current_level = next_level

    return list(neighbors)



def find_semantic_relations(query: str, nodes: dict, edges: list) -> list[dict]:
    """查找与查询相关的语义关系"""
    matched_nodes = query_knowledge_graph_nodes(query, nodes, limit=5)
    relations = []

    for node in matched_nodes:
        node_id = node["id"]
        # 查找与该节点相关的边
        for edge in edges:
            if edge.get("source") == node_id or edge.get("target") == node_id:
                source_id = edge.get("source")
                target_id = edge.get("target")
                source = nodes.get(source_id, {})
                target = nodes.get(target_id, {})

                relations.append({
                    "source": source.get("label", source_id),
                    "target": target.get("label", target_id),
                    "relation": edge.get("relation", "relates"),
                    "score": node["score"]
                })

    return relations[:20]


# 术语库查询功能

def load_terminology() -> dict:
    """加载术语库"""
    term_dir = PROCESSED_DATA_DIR / "terminology"
    try:
        term_file = term_dir / "comprehensive_terms.json"
        if term_file.exists():
            with open(term_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("terms", {})
    except Exception as e:
        logger.warning(f"Loading terminology failed: {e}")
    return {}



def load_abbreviations() -> dict:
    """加载缩写映射"""
    term_dir = PROCESSED_DATA_DIR / "terminology"
    try:
        abbr_file = term_dir / "abbreviations.json"
        if abbr_file.exists():
            with open(abbr_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Loading abbreviations failed: {e}")
    return {}



