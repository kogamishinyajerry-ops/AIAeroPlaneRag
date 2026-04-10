#!/usr/bin/env python3
"""
知识图谱构建Agent

专注于构建航空法规知识图谱，支持智能关联和推理
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict, Counter
from datetime import datetime

from .agent_base import BaseAgent, AgentTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeGraphAgent(BaseAgent):
    """
    知识图谱构建Agent

    核心功能：
    1. 实体提取（规章、条款、术语、数值）
    2. 关系发现（引用、依赖、等效、冲突）
    3. 图谱存储（Neo4j格式、NetworkX格式）
    4. 图谱查询（路径查找、邻居发现、子图提取）
    """

    # 航空领域核心实体类型
    ENTITY_TYPES = {
        "regulation": "规章",      # CCAR-25-R4
        "section": "条款",         # 25.1
        "requirement": "要求",     # 防火墙必须...
        "term": "术语",           # APU、防火墙
        "component": "部件",       # 发动机、液压系统
        "condition": "条件",       # OEI、单发失效
        "value": "数值",          # 30分钟、115%
        "test_method": "测试方法",  # 台架测试、飞行测试
        "document": "文档"         # 适航规章、咨询通告
    }

    # 关系类型
    RELATION_TYPES = {
        "contains": "包含",           # 规章包含条款
        "references": "引用",         # 条款A引用条款B
        "equivalent": "等效于",       # CCAR等效于FAR
        "depends_on": "依赖于",       # 要求A依赖要求B
        "conflicts_with": "冲突于",   # 两个要求冲突
        "refines": "细化",           # 条款细化某要求
        "defines": "定义",           # 条款定义术语
        "applies_to": "适用于",      # 要求适用于部件
        "tested_by": "测试于",       # 要求通过某方法测试
        "exempts": "豁免",           # 某条件豁免某要求
        "modifies": "修改"           # 修订版修改原版
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("KnowledgeGraphAgent", knowledge_base_path)

        # 图谱数据
        self.nodes: Dict[str, Dict] = {}  # node_id -> node_data
        self.edges: List[Dict] = []       # edge_data
        self.indexes: Dict[str, Set[str]] = defaultdict(set)  # entity_type -> node_ids

        # 实体提取模式
        self.patterns = {
            "section_number": re.compile(r'§\s*(\d+\.\d+[a-z]*)'),
            "ccar_reference": re.compile(r'(?:CCAR|FAR|CS)[- ]?(\d+)[-R]?(\d*)'),
            "apu": re.compile(r'(?:APU|辅助动力装置|Auxiliary Power Unit)', re.IGNORECASE),
            "oei": re.compile(r'(?:OEI|One.?Engine.?Inoperative|单发失效)', re.IGNORECASE),
            "percentage": re.compile(r'(\d+(?:\.\d+)?)\s*%'),
            "time_duration": re.compile(r'(\d+)\s*(?:分钟|minutes?|min|小时|hours?)'),
            "must_shall": re.compile(r'(?:必须|应当|shall|must|required)', re.IGNORECASE),
            "fire_protection": re.compile(r'(?:防火|fire.?protection|防火墙|firewall)', re.IGNORECASE),
            "hydraulic": re.compile(r'(?:液压|hydraulic)', re.IGNORECASE),
            "engine": re.compile(r'(?:发动机|engine|动力装置|powerplant)', re.IGNORECASE),
            "landing_gear": re.compile(r'(?:起落架|landing.?gear)', re.IGNORECASE),
        }

    def get_capabilities(self) -> List[str]:
        return [
            "extract_entities",
            "discover_relations",
            "build_graph",
            "query_neighbors",
            "find_paths",
            "export_formats",
            "analyze_clusters",
            "graph_insights"
        ]

    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        action = task.action

        if action == "extract_entities":
            return await self._extract_entities(task.params)
        elif action == "discover_relations":
            return await self._discover_relations(task.params)
        elif action == "build_graph":
            return await self._build_graph(task.params)
        elif action == "query_neighbors":
            return await self._query_neighbors(task.params)
        elif action == "find_paths":
            return await self._find_paths(task.params)
        elif action == "export_formats":
            return await self._export_formats(task.params)
        elif action == "analyze_clusters":
            return await self._analyze_clusters(task.params)
        elif action == "graph_insights":
            return await self._graph_insights(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _build_graph(self, params: Dict) -> Dict:
        """构建完整知识图谱"""
        improvements = []

        # 1. 提取所有实体
        logger.info("开始提取实体...")
        entity_result = await self._extract_entities({"max_docs": 10})
        improvements.extend(entity_result.get("improvements", []))

        # 2. 发现关系
        logger.info("开始发现关系...")
        relation_result = await self._discover_relations({})
        improvements.extend(relation_result.get("improvements", []))

        # 3. 保存图谱
        logger.info("保存图谱数据...")
        graph_dir = self.kb_path / "knowledge_graph"
        graph_dir.mkdir(exist_ok=True)

        # 保存为多种格式
        await self._export_formats({"formats": ["json", "gexf", "cypher"]})

        improvements.append(f"构建了包含 {len(self.nodes)} 个节点和 {len(self.edges)} 条边的知识图谱")

        return {
            "improvements": improvements,
            "metrics": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "entity_types": len(self.indexes)
            }
        }

    async def _extract_entities(self, params: Dict) -> Dict:
        """提取所有实体"""
        improvements = []
        max_docs = params.get("max_docs", 20)

        # 遍历结构文件
        for structure_file in list(self.kb_path.glob("*_structure.json"))[:max_docs]:
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                # 添加文档节点
                doc_id = self._add_node(
                    node_id=doc_name,
                    node_type="document",
                    label=doc_name,
                    properties={"source_file": str(structure_file)}
                )

                # 递归提取实体
                extracted = await self._extract_from_structure(data, doc_name)
                improvements.append(f"{doc_name}: 提取了 {extracted['nodes']} 个节点, {extracted['relations']} 个关系")

            except Exception as e:
                logger.warning(f"提取实体失败 {structure_file}: {e}")

        return {
            "improvements": improvements,
            "metrics": {"total_nodes": len(self.nodes)}
        }

    async def _extract_from_structure(self, data: Dict, doc_name: str) -> Dict:
        """从结构数据中提取实体"""
        node_count = 0
        relation_count = 0

        def process_nodes(nodes, parent_id=None, path=""):
            nonlocal node_count, relation_count

            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                summary = node.get("summary", "")
                content = " ".join(node.get("content_parts", []))
                full_text = f"{title} {summary} {content}"

                # 提取条款号
                section_match = re.search(r'§\s*(\d+\.\d+[a-z]*)', title)
                if section_match:
                    section_num = section_match.group(1)
                    section_id = f"{doc_name}:§{section_num}"

                    # 添加条款节点
                    self._add_node(
                        node_id=section_id,
                        node_type="section",
                        label=f"§{section_num}",
                        properties={
                            "document": doc_name,
                            "title": title,
                            "summary": summary[:200],
                            "content": content[:500]
                        }
                    )
                    node_count += 1

                    # 文档->条款关系
                    self._add_edge(doc_name, section_id, "contains")
                    relation_count += 1

                    # 提取要求（must/shall语句）
                    if self.patterns["must_shall"].search(full_text):
                        req_id = f"{section_id}:req"
                        self._add_node(
                            node_id=req_id,
                            node_type="requirement",
                            label=f"要求: {section_num}",
                            properties={"clause": section_id, "text": summary[:200]}
                        )
                        self._add_edge(section_id, req_id, "defines")
                        node_count += 1
                        relation_count += 1

                    # 提取部件实体
                    for pattern_name, pattern in [
                        ("engine", self.patterns["engine"]),
                        ("apu", self.patterns["apu"]),
                        ("hydraulic", self.patterns["hydraulic"]),
                        ("landing_gear", self.patterns["landing_gear"]),
                        ("fire_protection", self.patterns["fire_protection"]),
                    ]:
                        if pattern.search(full_text):
                            comp_id = f"component:{pattern_name}"
                            if comp_id not in self.nodes:
                                self._add_node(
                                    node_id=comp_id,
                                    node_type="component",
                                    label=self.ENTITY_TYPES.get(pattern_name, pattern_name),
                                    properties={"category": pattern_name}
                                )
                                node_count += 1

                            # 条款->部件关系
                            self._add_edge(section_id, comp_id, "applies_to")
                            relation_count += 1

                    # 提取数值
                    percentages = self.patterns["percentage"].findall(full_text)
                    for pct in percentages[:3]:  # 限制数量
                        val_id = f"{section_id}:val_{pct}"
                        self._add_node(
                            node_id=val_id,
                            node_type="value",
                            label=f"{pct}%",
                            properties={"value": float(pct), "unit": "percent", "clause": section_id}
                        )
                        self._add_edge(section_id, val_id, "contains")
                        node_count += 1
                        relation_count += 1

                    # 提取时间
                    times = self.patterns["time_duration"].findall(full_text)
                    for t in times[:2]:
                        val_id = f"{section_id}:time_{t}"
                        self._add_node(
                            node_id=val_id,
                            node_type="value",
                            label=f"{t}分钟",
                            properties={"value": int(t), "unit": "minutes", "clause": section_id}
                        )
                        self._add_edge(section_id, val_id, "contains")
                        node_count += 1
                        relation_count += 1

                    # 提取条件（OEI等）
                    if self.patterns["oei"].search(full_text):
                        cond_id = "condition:OEI"
                        if cond_id not in self.nodes:
                            self._add_node(
                                node_id=cond_id,
                                node_type="condition",
                                label="单发失效(OEI)",
                                properties={"synonyms": ["OEI", "One Engine Inoperative", "单发失效"]}
                            )
                            node_count += 1
                        self._add_edge(section_id, cond_id, "applies_to")
                        relation_count += 1

                    # 提取引用
                    refs = self.patterns["ccar_reference"].findall(full_text)
                    for ref in refs[:3]:
                        ref_doc = f"{ref[0]}-{ref[1]}" if ref[1] else ref[0]
                        target_id = f"regulation:{ref_doc}"
                        if target_id not in self.nodes:
                            self._add_node(
                                node_id=target_id,
                                node_type="regulation",
                                label=ref_doc,
                                properties={"regulation_type": ref[0]}
                            )
                            node_count += 1
                        self._add_edge(section_id, target_id, "references")
                        relation_count += 1

                # 递归处理子节点
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    current_path = f"{path}/{title[:30]}" if path else title[:30]
                    process_nodes(children, section_id if section_match else parent_id, current_path)

        # 处理结构
        structure = data.get("structure", [])
        if isinstance(structure, list):
            process_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            process_nodes(structure["chapters"])

        return {"nodes": node_count, "relations": relation_count}

    async def _discover_relations(self, params: Dict) -> Dict:
        """发现实体间的关系"""
        improvements = []

        # 1. 发现等效条款
        equivalent_pairs = self._find_equivalent_clauses()
        for source, target in equivalent_pairs:
            if source in self.nodes and target in self.nodes:
                self._add_edge(source, target, "equivalent", {"confidence": 0.9})
        improvements.append(f"发现 {len(equivalent_pairs)} 对等效条款")

        # 2. 发现主题聚类
        clusters = self._find_topic_clusters()
        improvements.append(f"发现 {len(clusters)} 个主题聚类")

        # 3. 发现依赖关系
        dependencies = self._find_dependencies()
        improvements.append(f"发现 {len(dependencies)} 个依赖关系")

        return {
            "improvements": improvements,
            "metrics": {
                "equivalent_pairs": len(equivalent_pairs),
                "clusters": len(clusters),
                "dependencies": len(dependencies)
            }
        }

    def _find_equivalent_clauses(self) -> List[Tuple[str, str]]:
        """查找等效条款"""
        equivalents = []

        # 已知的等效关系
        known_equivalents = [
            ("CCAR-25-R4:§25.1", "FAR-25:§25.1"),
            ("CCAR-25-R4:§25.831", "FAR-25:§25.831"),
            ("CCAR-33-R2:§33.5", "FAR-33:§33.5"),
            ("CCAR-29-R2:§29.1", "FAR-29:§29.1"),
        ]

        # 查找相同条款号的跨规章条款
        section_groups = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.get("type") == "section":
                # 提取条款号
                match = re.search(r'§(\d+\.\d+)', node.get("label", ""))
                if match:
                    section_num = match.group(1)
                    section_groups[section_num].append(node_id)

        # 为相同条款号的跨规章条款添加等效关系
        for section_num, nodes in section_groups.items():
            if len(nodes) > 1:
                for i in range(len(nodes)):
                    for j in range(i + 1, len(nodes)):
                        doc_i = nodes[i].split(":")[0] if ":" in nodes[i] else ""
                        doc_j = nodes[j].split(":")[0] if ":" in nodes[j] else ""
                        # 不同规章的相同条款号视为等效
                        if doc_i != doc_j:
                            equivalents.append((nodes[i], nodes[j]))

        return equivalents

    def _find_topic_clusters(self) -> List[Dict]:
        """查找主题聚类"""
        clusters = []

        # 按部件聚类
        component_clusters = defaultdict(list)
        for edge in self.edges:
            if edge.get("relation") == "applies_to":
                source = edge.get("source")
                target = edge.get("target")
                if target.startswith("component:"):
                    component_clusters[target].append(source)

        for comp_id, clauses in component_clusters.items():
            if len(clauses) >= 2:
                comp_name = self.nodes.get(comp_id, {}).get("label", comp_id)
                clusters.append({
                    "type": "component_cluster",
                    "name": comp_name,
                    "members": clauses,
                    "size": len(clauses)
                })

        return clusters

    def _find_dependencies(self) -> List[Tuple[str, str]]:
        """查找依赖关系"""
        dependencies = []

        # 基于引用关系推断依赖
        for edge in self.edges:
            if edge.get("relation") == "references":
                source = edge.get("source")
                target = edge.get("target")
                # 被引用的条款可能是依赖
                dependencies.append((source, target))

        return dependencies

    async def _query_neighbors(self, params: Dict) -> Dict:
        """查询邻居节点"""
        node_id = params.get("node_id")
        depth = params.get("depth", 1)

        if not node_id or node_id not in self.nodes:
            return {"neighbors": [], "count": 0}

        neighbors = set()
        current_level = {node_id}

        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                # 找出边
                for edge in self.edges:
                    if edge.get("source") == nid:
                        target = edge.get("target")
                        if target != node_id:
                            neighbors.add(target)
                            next_level.add(target)
                    elif edge.get("target") == nid:
                        source = edge.get("source")
                        if source != node_id:
                            neighbors.add(source)
                            next_level.add(source)
            current_level = next_level

        return {
            "neighbors": [
                {"id": nid, **self.nodes.get(nid, {})}
                for nid in neighbors
            ],
            "count": len(neighbors)
        }

    async def _find_paths(self, params: Dict) -> Dict:
        """查找节点间路径"""
        source = params.get("source")
        target = params.get("target")
        max_length = params.get("max_length", 4)

        if source not in self.nodes or target not in self.nodes:
            return {"paths": []}

        # BFS查找路径
        paths = []
        queue = [(source, [source])]

        while queue and len(paths) < 10:  # 限制路径数量
            current, path = queue.pop(0)

            if current == target and len(path) <= max_length:
                paths.append(path)
                continue

            if len(path) >= max_length:
                continue

            # 找邻居
            neighbors = set()
            for edge in self.edges:
                if edge.get("source") == current:
                    neighbors.add(edge.get("target"))
                elif edge.get("target") == current:
                    neighbors.add(edge.get("source"))

            for neighbor in neighbors:
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))

        return {
            "paths": paths,
            "count": len(paths)
        }

    async def _export_formats(self, params: Dict) -> Dict:
        """导出多种格式"""
        formats = params.get("formats", ["json"])
        improvements = []
        graph_dir = self.kb_path / "knowledge_graph"
        graph_dir.mkdir(exist_ok=True)

        # JSON格式
        if "json" in formats:
            json_data = {
                "nodes": self.nodes,
                "edges": self.edges,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "node_count": len(self.nodes),
                    "edge_count": len(self.edges)
                }
            }
            with open(graph_dir / "graph.json", 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            improvements.append("导出JSON格式")

        # GEXF格式（Gephi）
        if "gexf" in formats:
            gexf_content = self._generate_gexf()
            with open(graph_dir / "graph.gexf", 'w', encoding='utf-8') as f:
                f.write(gexf_content)
            improvements.append("导出GEXF格式（Gephi）")

        # Cypher格式（Neo4j）
        if "cypher" in formats:
            cypher_content = self._generate_cypher()
            with open(graph_dir / "import.cypher", 'w', encoding='utf-8') as f:
                f.write(cypher_content)
            improvements.append("导出Cypher格式（Neo4j）")

        # 统计摘要
        if "summary" in formats:
            summary = self._generate_summary()
            with open(graph_dir / "summary.json", 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            improvements.append("生成图谱摘要")

        return {"improvements": improvements}

    def _generate_gexf(self) -> str:
        """生成GEXF格式"""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">')
        lines.append('  <graph mode="static" defaultedgetype="directed">')

        # 节点
        lines.append('    <nodes>')
        for node_id, node in self.nodes.items():
            label = node.get("label", node_id).replace('"', '&quot;')
            node_type = node.get("type", "unknown")
            lines.append(f'      <node id="{node_id}" label="{label}">')
            lines.append(f'        <attvalues>')
            lines.append(f'          <attvalue for="type" value="{node_type}"/>')
            lines.append(f'        </attvalues>')
            lines.append(f'      </node>')
        lines.append('    </nodes>')

        # 边
        lines.append('    <edges>')
        for i, edge in enumerate(self.edges):
            source = edge.get("source", "").replace('"', '&quot;')
            target = edge.get("target", "").replace('"', '&quot;')
            relation = edge.get("relation", "relates")
            lines.append(f'      <edge id="{i}" source="{source}" target="{target}" label="{relation}"/>')
        lines.append('    </edges>')

        lines.append('  </graph>')
        lines.append('</gexf>')

        return '\n'.join(lines)

    def _generate_cypher(self) -> str:
        """生成Cypher格式"""
        lines = []

        # 创建节点
        lines.append("// 创建节点")
        for node_id, node in self.nodes.items():
            label = node.get("label", "").replace("'", "\\'")
            node_type = node.get("type", "Node")
            props = json.dumps(node, ensure_ascii=False)
            lines.append(f"CREATE (:{node_type} {{id: '{node_id}', label: '{label}', properties: '{props}'}});")

        lines.append("\n// 创建关系")
        for edge in self.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            relation = edge.get("relation", "RELATES_TO")
            lines.append(f"MATCH (s {{id: '{source}'}}), (t {{id: '{target}'}})")
            lines.append(f"CREATE (s)-[:{relation}]->(t);")

        return '\n'.join(lines)

    def _generate_summary(self) -> Dict:
        """生成图谱摘要"""
        # 统计各类实体
        type_counts = Counter()
        for node in self.nodes.values():
            type_counts[node.get("type", "unknown")] += 1

        # 统计各类关系
        rel_counts = Counter()
        for edge in self.edges:
            rel_counts[edge.get("relation", "unknown")] += 1

        # 统计入度和出度
        in_degree = Counter()
        out_degree = Counter()
        for edge in self.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            out_degree[source] += 1
            in_degree[target] += 1

        # 找出枢纽节点
        top_nodes = sorted(
            [(nid, in_degree[nid] + out_degree[nid]) for nid in self.nodes.keys()],
            key=lambda x: x[1],
            reverse=True
        )[:20]

        return {
            "entity_types": dict(type_counts),
            "relation_types": dict(rel_counts),
            "top_nodes": [{"id": nid, "degree": deg} for nid, deg in top_nodes],
            "metadata": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "generated_at": datetime.now().isoformat()
            }
        }

    async def _analyze_clusters(self, params: Dict) -> Dict:
        """分析图谱聚类"""
        improvements = []

        # 按文档聚类
        doc_clusters = defaultdict(set)
        for node_id, node in self.nodes.items():
            doc = node.get("properties", {}).get("document", "")
            if doc:
                doc_clusters[doc].add(node_id)

        improvements.append(f"发现 {len(doc_clusters)} 个文档聚类")

        # 按类型聚类
        type_clusters = defaultdict(set)
        for node_id, node in self.nodes.items():
            node_type = node.get("type", "unknown")
            type_clusters[node_type].add(node_id)

        improvements.append(f"发现 {len(type_clusters)} 个类型聚类")

        # 保存聚类结果
        graph_dir = self.kb_path / "knowledge_graph"
        graph_dir.mkdir(exist_ok=True)

        with open(graph_dir / "clusters.json", 'w', encoding='utf-8') as f:
            json.dump({
                "by_document": {k: list(v) for k, v in doc_clusters.items()},
                "by_type": {k: list(v) for k, v in type_clusters.items()}
            }, f, ensure_ascii=False, indent=2)

        return {
            "improvements": improvements,
            "clusters": {
                "by_document": len(doc_clusters),
                "by_type": len(type_clusters)
            }
        }

    async def _graph_insights(self, params: Dict) -> Dict:
        """生成图谱洞察"""
        insights = []

        # 1. 最常用的要求
        req_nodes = [
            (nid, node)
            for nid, node in self.nodes.items()
            if node.get("type") == "requirement"
        ]
        insights.append(f"图谱包含 {len(req_nodes)} 个要求节点")

        # 2. 最复杂的部件
        component_complexity = defaultdict(int)
        for edge in self.edges:
            if edge.get("relation") == "applies_to":
                target = edge.get("target")
                if target.startswith("component:"):
                    component_complexity[target] += 1

        top_components = sorted(component_complexity.items(), key=lambda x: x[1], reverse=True)[:5]
        insights.append(f"最复杂的部件: {[(self.nodes.get(k, {}).get('label', k), v) for k, v in top_components]}")

        # 3. 跨规章引用
        cross_refs = 0
        for edge in self.edges:
            if edge.get("relation") == "references":
                source_doc = edge.get("source", "").split(":")[0] if ":" in edge.get("source", "") else ""
                target_doc = edge.get("target", "").split(":")[0] if ":" in edge.get("target", "") else ""
                if source_doc and target_doc and source_doc != target_doc:
                    cross_refs += 1
        insights.append(f"发现 {cross_refs} 个跨规章引用")

        # 4. 关键条款
        clause_importance = defaultdict(int)
        for edge in self.edges:
            source = edge.get("source", "")
            if ":" in source:
                clause_importance[source] += 1

        top_clauses = sorted(clause_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        insights.append(f"关键条款: {top_clauses}")

        return {
            "insights": insights,
            "summary": {
                "total_requirements": len(req_nodes),
                "cross_references": cross_refs,
                "top_component": top_components[0] if top_components else None
            }
        }

    def _add_node(self, node_id: str, node_type: str, label: str,
                  properties: Dict = None) -> str:
        """添加节点"""
        self.nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "properties": properties or {}
        }
        self.indexes[node_type].add(node_id)
        return node_id

    def _add_edge(self, source: str, target: str, relation: str,
                  properties: Dict = None) -> str:
        """添加边"""
        edge_id = f"{source}->{target}"
        edge = {
            "source": source,
            "target": target,
            "relation": relation,
            "properties": properties or {}
        }
        self.edges.append(edge)
        return edge_id


__all__ = ['KnowledgeGraphAgent']
