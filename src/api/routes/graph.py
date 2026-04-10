"""
Graph Routes - 知识图谱API端点
整合了密集网络和标准图谱逻辑
"""
import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.auth import require_auth
from src.api.dependencies.deps import services
from src.core.config import (
    EMBEDDING_VERSION,
    PROCESSED_DATA_DIR,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])

# 机构文档映射
AGENCY_DOCS = {
    "CAAC": ["CCAR-25-R4", "CCAR-33-R2", "CCAR-29-R2", "CCAR-23", "CCAR-36", "CCAR-91", "CCAR-93TM-R2"],
    "FAA": ["FAR-25", "FAR-33"],
    "EASA": ["CS-25", "CS-E"]
}

def _get_agency(doc_name: str) -> str:
    """根据文档名推断机构"""
    for a, docs in AGENCY_DOCS.items():
        if any(d in doc_name for d in docs):
            return a
    return "UNKNOWN"

def _get_agency_color(agency: str) -> str:
    """获取机构对应的颜色"""
    colors = {
        "CAAC": "#e63946",  # Red
        "FAA": "#3498db",   # Blue
        "EASA": "#2ecc71",  # Green
        "UNKNOWN": "#95a5a6"  # Gray
    }
    return colors.get(agency.upper(), "#95a5a5")

def _infer_agency_from_id(node_id: str, node: dict, edges: list, all_nodes: list) -> str:
    """通过节点ID、标签或连接关系推断其所属机构"""
    # 1. 从节点ID中推断
    nid = node_id.upper()
    for agency, doc_prefixes in AGENCY_DOCS.items():
        for prefix in doc_prefixes:
            if prefix.replace("-", "_").replace(".", "_").upper() in nid:
                return agency

    # 2. 从节点标签中推断
    label = (node.get('label', '') or '').upper()
    for agency, doc_prefixes in AGENCY_DOCS.items():
        for prefix in doc_prefixes:
            if prefix in label:
                return agency

    # 3. 查找连接的文档节点
    node_map = {n['id']: n for n in all_nodes}
    raw_id = node.get('id', '')
    for edge in edges:
        peer_id = None
        if edge.get('source') == raw_id:
            peer_id = edge.get('target')
        elif edge.get('target') == raw_id:
            peer_id = edge.get('source')

        if peer_id:
            peer = node_map.get(peer_id, {})
            if peer.get('type') == 'document':
                peer_label = peer.get('label', '')
                for agency, doc_prefixes in AGENCY_DOCS.items():
                    for prefix in doc_prefixes:
                        if prefix in peer_label:
                            return agency
    return "UNKNOWN"


def load_knowledge_graph_fallback() -> tuple[dict, list]:
    """旧版逻辑：加载知识图谱（支持多种格式的 fallback）"""
    candidates = [
        PROCESSED_DATA_DIR / "CCAR-33-R2_professional_graph.json",
        PROCESSED_DATA_DIR / "CCAR-33_graph.json",
        PROCESSED_DATA_DIR / "knowledge_graph" / "graph.json",
    ]

    for graph_path in candidates:
        if not graph_path.exists():
            continue
        try:
            with open(graph_path, encoding="utf-8") as f:
                data = json.load(f)

            raw_nodes = data.get("nodes", {})
            raw_edges = data.get("edges", [])

            if isinstance(raw_nodes, dict) and raw_nodes:
                return raw_nodes, raw_edges

            raw_entities = data.get("entities", [])
            raw_rels = data.get("relationships", [])

            if raw_entities and isinstance(raw_entities, list):
                nodes = {}
                for n in raw_entities:
                    nid = n.get("id") or n.get("name")
                    if nid:
                        nodes[nid] = n
                if nodes:
                    edges = []
                    for r in raw_rels:
                        src = r.get("source") or r.get("src")
                        tgt = r.get("target") or r.get("dst")
                        if src and tgt:
                            edges.append({
                                "source": src,
                                "target": tgt,
                                "type": r.get("type", "RELATED_TO"),
                            })
                    return nodes, edges
        except Exception:
            continue
    return {}, []


@router.get("/nodes")
async def get_graph_nodes(
    api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    """获取图谱节点"""
    nodes, edges = load_knowledge_graph_fallback()
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values())[:100],
    }


@router.get("/network")
async def get_graph_network(
    query: str = Query(default="", max_length=200),
    max_nodes: int = Query(default=100, ge=10, le=1000),
    include_inter_doc: bool = Query(default=True),
    api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    """
    获取网络图数据 - 密集网络优先版本
    """
    try:
        # 优先尝试从 fully_connected_graph.json 加载
        graph_file = PROCESSED_DATA_DIR / "knowledge_graph" / "fully_connected_graph.json"
        if graph_file.exists():
            with open(graph_file, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)

            all_nodes = []
            all_edges = []
            seen_ids = set()

            for node in graph_data['nodes']:
                node_id = node['id'].replace('-', '_').replace('.', '_')
                if node_id not in seen_ids:
                    new_node = {
                        'id': node_id,
                        'label': node.get('label', node['id']),
                        'type': node.get('type', 'unknown'),
                        'group': node.get('group', 0),
                        'size': node.get('size', 5),
                        'doc_name': node.get('document', ''),
                        'title': node.get('title', ''),
                    }
                    if new_node['doc_name']:
                        new_node['group'] = _get_agency(new_node['doc_name'])
                        new_node['color'] = _get_agency_color(new_node['group'])
                    elif node.get('type') == 'document':
                        new_node['group'] = _get_agency(new_node['label'])
                        new_node['color'] = _get_agency_color(new_node['group'])
                        new_node['size'] = 50
                    else:
                        inferred_agency = _infer_agency_from_id(node_id, node, graph_data.get('edges', []), graph_data.get('nodes', []))
                        new_node['group'] = inferred_agency
                        new_node['color'] = _get_agency_color(inferred_agency)
                    all_nodes.append(new_node)
                    seen_ids.add(node_id)

            for edge in graph_data['edges']:
                src = edge['source'].replace('-', '_').replace('.', '_')
                tgt = edge['target'].replace('-', '_').replace('.', '_')
                if src in seen_ids and tgt in seen_ids:
                    all_edges.append({
                        'source': src,
                        'target': tgt,
                        'type': edge.get('type', 'unknown'),
                        'weight': edge.get('weight', 0.5),
                        'opacity': min(0.8, edge.get('weight', 0.5))
                    })

            # 过滤逻辑 (缩减版，针对性能优化)
            if query:
                from src.rag.tokenizer_enhanced import tokenize_query
                tokens = tokenize_query(query.lower()) or {query.lower()}
                
                filtered_nodes = []
                related_ids = set()
                for node in all_nodes:
                    searchable = f"{node.get('label', '')} {node.get('doc_name', '')} {node.get('title', '')}".lower()
                    if any(t in searchable for t in tokens):
                        filtered_nodes.append(node)
                        related_ids.add(node['id'])
                
                # 添加一阶邻居
                for edge in all_edges:
                    if edge['source'] in related_ids: related_ids.add(edge['target'])
                    elif edge['target'] in related_ids: related_ids.add(edge['source'])
                
                final_nodes = [n for n in all_nodes if n['id'] in related_ids]
                final_edges = [e for e in all_edges if e['source'] in related_ids and e['target'] in related_ids]
                
                return {
                    "status": "ok",
                    "nodes": final_nodes[:max_nodes],
                    "edges": final_edges[:max_nodes * 3],
                    "query": query,
                    "total_nodes": len(final_nodes),
                    "total_edges": len(final_edges)
                }

            return {
                "status": "ok",
                "nodes": all_nodes[:max_nodes],
                "edges": all_edges[:max_nodes * 3],
                "query": query,
                "total_nodes": len(all_nodes),
                "total_edges": len(all_edges)
            }
    except Exception as e:
        logger.warning(f"Dense graph load failed, falling back: {e}")

    # 回退到原有结构扫描逻辑
    nodes, edges = load_knowledge_graph_fallback()
    if not nodes:
        raise HTTPException(status_code=404, detail="Graph data not found")
        
    return {
        "status": "ok",
        "nodes": [{"id": nid, **n} for nid, n in list(nodes.items())[:max_nodes]],
        "edges": edges[:max_nodes * 3],
        "query": query,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }


@router.get("/subgraph")
async def get_graph_subgraph(
    center_node: str = Query(..., min_length=1),
    depth: int = Query(default=2, ge=1, le=5),
    api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    """获取以某节点为中心的子图"""
    nodes, edges = load_knowledge_graph_fallback()

    # 尝试多种 ID 格式匹配 (UI 使用 'doc:ID', 后端倾向于使用 'doc_ID' 或 'sec_ID')
    target_id = center_node
    if target_id not in nodes:
        # 1. 转换分隔符 ( : -> _ )
        alt_id = target_id.replace(":", "_").replace("-", "_")
        if alt_id in nodes:
            target_id = alt_id
        else:
            # 2. 移除 doc: 前缀尝试
            if target_id.startswith("doc:"):
                alt_id = target_id[4:]
                if alt_id in nodes:
                    target_id = alt_id
            
            # 3. 终极模糊搜索
            if target_id not in nodes:
                for nid in nodes:
                    if target_id.lower() in nid.lower() or nid.lower() in target_id.lower():
                        target_id = nid
                        break

    if target_id not in nodes:
        raise HTTPException(status_code=404, detail=f"Node '{center_node}' not found in knowledge graph")

    visited = {target_id}
    current_level = {target_id}

    for _ in range(depth):
        next_level = set()
        for e in edges:
            if e["source"] in current_level and e["target"] not in visited:
                next_level.add(e["target"])
            elif e["target"] in current_level and e["source"] not in visited:
                next_level.add(e["source"])
        visited.update(next_level)
        current_level = next_level

    subgraph_nodes = [{"id": nid, **nodes[nid]} for nid in visited if nid in nodes]
    subgraph_edges = [e for e in edges if e["source"] in visited and e["target"] in visited]

    return {
        "nodes": subgraph_nodes,
        "edges": subgraph_edges,
        "node_count": len(subgraph_nodes),
        "center_node": target_id
    }
