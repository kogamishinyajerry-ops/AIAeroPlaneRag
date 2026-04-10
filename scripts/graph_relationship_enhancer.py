#!/usr/bin/env python3
"""
graph_relationship_enhancer.py
AIAeroPlaneRag Knowledge Graph Enhancement Script v2.0

Operations:
1. Expand relationship type taxonomy
2. Add CCAR-33 ↔ CS-E equivalence edges
3. Identify and fix isolated nodes
4. Add cross-document semantic links
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. RELATIONSHIP TYPE TAXONOMY
# ==============================================================================

ENHANCED_RELATIONSHIP_TYPES = {
    # --- Structural (existing) ---
    "belongs_to":       {"direction": "unidirectional", "domain": "structural"},
    "next":             {"direction": "unidirectional", "domain": "structural"},
    "child_of":         {"direction": "unidirectional", "domain": "structural"},

    # --- Semantic (new/enhanced) ---
    "equivalent_to":    {
        "direction": "bidirectional",
        "domain": "cross_regulatory",
        "description": "Functionally identical clause across regulatory frameworks",
        "symmetric_alias": "equivalent_to",
    },
    "subject_to":       {
        "direction": "unidirectional",
        "domain": "regulatory_hierarchy",
        "description": "Clause A is subject to clause B's requirements",
    },
    "derived_from":     {
        "direction": "unidirectional",
        "domain": "regulatory_drafting",
        "description": "Clause A was drafted based on clause B",
    },
    "cross_references": {
        "direction": "bidirectional",
        "domain": "cross_document",
        "description": "Explicit/implicit reference in regulatory text",
        "symmetric_alias": "cross_references",
    },
    "parallels":        {
        "direction": "bidirectional",
        "domain": "cross_regulatory",
        "description": "Same topic in different frameworks, not equivalent",
        "symmetric_alias": "parallels",
    },
    "implements":       {
        "direction": "unidirectional",
        "domain": "regulatory_implementation",
        "description": "National implementation of international standard",
    },
    "supersedes":       {
        "direction": "unidirectional",
        "domain": "regulatory_history",
        "description": "Newer clause replaces older within same framework",
    },
    "verifies":         {
        "direction": "unidirectional",
        "domain": "compliance_verification",
        "description": "Test clause verifies requirement clause",
    },
    "conflicts_with":   {
        "direction": "bidirectional",
        "domain": "quality_assurance",
        "description": "Contradictory requirements — QA flag",
        "symmetric_alias": "conflicts_with",
    },
    "regulatory_history": {
        "direction": "unidirectional",
        "domain": "regulatory_drafting",
        "description": "Historical regulatory lineage",
    },

    # --- Legacy (mapped) ---
    "RELATED_TO":       {"mapped_to": "cross_references"},
    "related":          {"mapped_to": "cross_references"},
    "equivalent":       {"mapped_to": "equivalent_to"},
    "similar_试验":      {"mapped_to": "parallels"},
    "similar_发动机":    {"mapped_to": "parallels"},
    "similar_防火":     {"mapped_to": "equivalent_to"},
    "similar_转子":      {"mapped_to": "parallels"},
    "center":           {"mapped_to": "belongs_to"},
}


# ==============================================================================
# 2. CCAR-33-R2 ↔ CS-E EQUIVALENCE MAPPING
# ==============================================================================

CCAR33_CSE_EQUIVALENCES = [
    ("33.1",   "E.10",   0.95, "substantially_equivalent"),
    ("33.3",   "E.10",   0.85, "substantially_equivalent"),
    ("33.4",   "E.25",   0.98, "identical"),
    ("33.5",   "E.20",   0.92, "substantially_equivalent"),
    ("33.11",  "E.10",   0.85, "technical_equivalent"),
    ("33.15",  "E.70",   0.96, "identical"),
    ("33.17",  "E.130",  0.97, "identical"),
    ("33.23",  "E.20",   0.90, "substantially_equivalent"),
    ("33.25",  "E.80",   0.85, "technical_equivalent"),
    ("33.27",  "E.400",  0.88, "technical_equivalent"),
    ("33.28",  "E.50",   0.93, "substantially_equivalent"),
    ("33.29",  "E.60",   0.95, "identical"),
    ("33.31",  "E.10",   0.85, "technical_equivalent"),
    ("33.35",  "E.250",  0.96, "identical"),
    ("33.37",  "E.240",  0.95, "identical"),
    ("33.39",  "E.270",  0.97, "identical"),
    ("33.43",  "E.340",  0.95, "identical"),
    ("33.45",  "E.350",  0.96, "identical"),
    ("33.49",  "E.440",  0.94, "substantially_equivalent"),
    ("33.51",  "E.500",  0.95, "identical"),
    ("33.53",  "E.170",  0.87, "technical_equivalent"),
    ("33.55",  "E.440",  0.90, "substantially_equivalent"),
    ("33.61",  "E.10",   0.85, "technical_equivalent"),
    ("33.62",  "E.520",  0.88, "technical_equivalent"),
    ("33.63",  "E.340",  0.95, "identical"),
    ("33.65",  "E.390",  0.86, "technical_equivalent"),
    ("33.66",  "E.580",  0.87, "technical_equivalent"),
    ("33.67",  "E.560",  0.96, "identical"),
    ("33.69",  "E.450",  0.94, "identical"),
    ("33.70",  "E.515",  0.85, "technical_equivalent"),
    ("33.71",  "E.570",  0.97, "identical"),
    ("33.73",  "E.620",  0.82, "technical_equivalent"),
    ("33.74",  "E.525",  0.93, "identical"),
    ("33.75",  "E.510",  0.91, "substantially_equivalent"),
    ("33.77",  "E.780",  0.84, "technical_equivalent"),
    ("33.83",  "E.650",  0.95, "identical"),
    ("33.84",  "E.820",  0.96, "identical"),
    ("33.85",  "E.730",  0.95, "identical"),
    ("33.88",  "E.860",  0.94, "identical"),
    ("33.89",  "E.740",  0.92, "substantially_equivalent"),
    ("33.92",  "E.710",  0.95, "identical"),
    ("33.94",  "E.810",  0.96, "identical"),
    ("33.97",  "E.890",  0.93, "identical"),
]

CROSS_DOC_KEYWORDS = {
    "防火":          {"links_to": ["fire", "flame", "combustion"], "rel_type": "equivalent_to"},
    "发动机控制":    {"links_to": ["engine control", "FADEC", "ECU"], "rel_type": "equivalent_to"},
    "超转试验":      {"links_to": ["over-speed", "overspeed"], "rel_type": "equivalent_to"},
    "喘振":          {"links_to": ["surge", "stall"], "rel_type": "equivalent_to"},
    "振动":          {"links_to": ["vibration"], "rel_type": "equivalent_to"},
    "燃油系统":      {"links_to": ["fuel system"], "rel_type": "equivalent_to"},
    "润滑系统":      {"links_to": ["lubrication", "oil system"], "rel_type": "equivalent_to"},
    "安全分析":      {"links_to": ["safety analysis", "FMEA", "FHA"], "rel_type": "equivalent_to"},
    "持久试验":      {"links_to": ["endurance test", "150hr"], "rel_type": "equivalent_to"},
    "校准试验":      {"links_to": ["calibration"], "rel_type": "equivalent_to"},
    "材料":          {"links_to": ["material"], "rel_type": "equivalent_to"},
    "安装":          {"links_to": ["installation", "mounting"], "rel_type": "cross_references"},
    "仪表":          {"links_to": ["instrument", "indication"], "rel_type": "cross_references"},
    "涡轮":          {"links_to": ["turbine"], "rel_type": "parallels"},
    "压气机":        {"links_to": ["compressor"], "rel_type": "parallels"},
}


class GraphRelationshipEnhancer:
    """Enhances the knowledge graph with richer relationship types and cross-links."""

    def __init__(self, graph_path: str | Path):
        self.graph_path = Path(graph_path)
        self.graph: dict[str, Any] = {}
        self.nodes_by_id: dict[str, dict[str, Any]] = {}
        self.nodes_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.edges: list[dict[str, Any]] = []
        self.stats: dict[str, int] = {}

    def load(self) -> None:
        logger.info("Loading graph from %s", self.graph_path)
        with open(self.graph_path, encoding="utf-8") as f:
            self.graph = json.load(f)

        # 兼容两种格式: list或dict
        nodes_data = self.graph.get("nodes", {})
        if isinstance(nodes_data, dict):
            # 新格式: {node_id: node_data}
            self.nodes_by_id = dict(nodes_data)
        else:
            # 旧格式: [node_list]
            self.nodes_by_id = {n["id"]: n for n in nodes_data}

        for n in self.nodes_by_id.values():
            doc = self._get_doc_id(n["id"]) if isinstance(n, dict) else self._get_doc_id(n)
            if doc:
                self.nodes_by_doc[doc].append(n)
        self.edges = list(self.graph.get("edges", []))
        logger.info("Loaded %d nodes, %d edges", len(self.nodes_by_id), len(self.edges))

    def save(self, output_path: str | Path | None = None) -> None:
        out = output_path or self.graph_path
        # 保存为dict格式 (新格式)
        self.graph["nodes"] = dict(self.nodes_by_id)
        self.graph["edges"] = self.edges
        self.graph["enhancement_metadata"] = {
            "enhanced_at": "2026-03-25",
            "new_edge_count": len(self.edges),
            "stats": self.stats,
            "relationship_types": list(ENHANCED_RELATIONSHIP_TYPES.keys()),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.graph, f, ensure_ascii=False, indent=2)
        logger.info("Saved enhanced graph to %s", out)

    def run_all_enhancements(self) -> None:
        self._normalize_legacy_relationships()
        self._add_ccar_cse_equivalences()
        self._add_cross_document_links()
        self._fix_isolated_nodes()
        self._add_subject_to_relationships()
        self._add_verifies_relationships()
        self._compute_stats()

    def _normalize_legacy_relationships(self) -> int:
        legacy_map = {k: v["mapped_to"] for k, v in ENHANCED_RELATIONSHIP_TYPES.items() if "mapped_to" in v}
        count = 0
        for edge in self.edges:
            old_type = edge.get("type", "")
            if old_type in legacy_map:
                new_type = legacy_map[old_type]
                edge["type"] = new_type
                edge["relationship_normalized"] = True
                count += 1
        logger.info("Normalized %d legacy relationships", count)
        self.stats["legacy_normalized"] = count
        return count

    def _add_ccar_cse_equivalences(self) -> int:
        added = 0
        for ccar_clause, cse_section, confidence, equiv_type in CCAR33_CSE_EQUIVALENCES:
            ccar_nodes = self._find_nodes_matching("CCAR-33", ccar_clause)
            cse_nodes = self._find_nodes_matching("CS-E", cse_section.lstrip("E").lstrip("."))
            for cn in ccar_nodes:
                for en in cse_nodes:
                    if not self._edge_exists(cn["id"], en["id"], "equivalent_to"):
                        self.edges.append({
                            "source": cn["id"],
                            "target": en["id"],
                            "type": "equivalent_to",
                            "direction": "bidirectional",
                            "equivalence_type": equiv_type,
                            "confidence": confidence,
                            "regulatory_frameworks": ["CCAR-33-R2", "CS-E Amendment 5"],
                            "mapping_source": "CCAR-33-R2_to_CS-E_Amendment5_mapping_v1.0",
                        })
                        added += 1
        logger.info("Added %d CCAR↔CS-E equivalence edges", added)
        self.stats["ccar_cse_equivalences_added"] = added
        return added

    def _add_cross_document_links(self) -> int:
        added = 0
        docs_to_cross_link = ["CCAR-33-R2", "CCAR-25-R4", "CCAR-91", "CS-E", "FAR-25", "FAR-33"]
        for kw, rule in CROSS_DOC_KEYWORDS.items():
            matching_nodes: list[tuple[str, dict]] = []
            for doc in docs_to_cross_link:
                for n in self.nodes_by_doc.get(doc, []):
                    if self._node_matches_keyword(n, kw):
                        matching_nodes.append((doc, n))
            if len(matching_nodes) < 2:
                continue
            for i, (doc_a, node_a) in enumerate(matching_nodes):
                for doc_b, node_b in matching_nodes[i + 1:]:
                    if doc_a == doc_b:
                        continue
                    if not self._edge_exists(node_a["id"], node_b["id"], rule["rel_type"]):
                        self.edges.append({
                            "source": node_a["id"],
                            "target": node_b["id"],
                            "type": rule["rel_type"],
                            "direction": "bidirectional",
                            "shared_concept": kw,
                            "link_trigger": "cross_document_keyword",
                        })
                        added += 1
        logger.info("Added %d cross-document semantic links", added)
        self.stats["cross_doc_links_added"] = added
        return added

    def _fix_isolated_nodes(self) -> int:
        adj: dict[str, set[str]] = defaultdict(set)
        for e in self.edges:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
        isolated_ids = [nid for nid, neighs in adj.items() if len(neighs) == 0]
        connected = 0
        for iso_id in isolated_ids:
            iso_node = self.nodes_by_id.get(iso_id)
            if not iso_node:
                continue
            candidates: list[tuple[int, str]] = []
            for nid, node in self.nodes_by_id.items():
                if nid == iso_id:
                    continue
                score = self._compute_connection_score(iso_node, node)
                if score > 0:
                    candidates.append((score, nid))
            candidates.sort(key=lambda x: -x[0])
            top_candidates = [t for _, t in candidates[:3]]
            for target_id in top_candidates:
                rel_type = self._infer_relationship_type(iso_node, self.nodes_by_id[target_id])
                if not self._edge_exists(iso_id, target_id, rel_type):
                    self.edges.append({
                        "source": iso_id,
                        "target": target_id,
                        "type": rel_type,
                        "direction": "unidirectional",
                        "connection_reason": "isolated_node_fix",
                    })
                    connected += 1
            if len(adj[iso_id]) == 0:
                doc_hub = self._find_document_hub(self._get_doc_id(iso_id))
                if doc_hub and not self._edge_exists(iso_id, doc_hub, "belongs_to"):
                    self.edges.append({
                        "source": iso_id,
                        "target": doc_hub,
                        "type": "belongs_to",
                        "direction": "unidirectional",
                        "connection_reason": "isolated_node_fix",
                    })
                    connected += 1
        logger.info("Fixed %d isolated node connections", connected)
        self.stats["isolated_nodes_fixed"] = connected
        return connected

    def _add_subject_to_relationships(self) -> int:
        subject_to_rules = [
            ("33.27", "33.83", "rotor structural integrity subject to vibration test"),
            ("33.27", "33.84", "rotor subject to over-torque test"),
            ("33.28", "33.53", "engine control subject to component verification"),
            ("33.65", "33.89", "surge/stall margin subject to endurance test"),
            ("33.75", "33.89", "safety analysis subject to endurance test verification"),
            ("33.75", "33.49", "safety analysis subject to endurance test"),
            ("33.70", "33.93", "critical parts subject to teardown inspection"),
            ("E.510", "E.440", "safety analysis subject to endurance test"),
            ("E.510", "E.650", "safety analysis subject to vibration survey"),
            ("E.400", "E.340", "over-speed test subject to vibration test"),
        ]
        added = 0
        for req_pat, test_pat, desc in subject_to_rules:
            req_nodes = self._find_nodes_matching("CCAR-33", req_pat) + self._find_nodes_matching("CS-E", req_pat)
            test_nodes = self._find_nodes_matching("CCAR-33", test_pat) + self._find_nodes_matching("CS-E", test_pat)
            for rn in req_nodes:
                for tn in test_nodes:
                    if not self._edge_exists(rn["id"], tn["id"], "subject_to"):
                        self.edges.append({
                            "source": rn["id"],
                            "target": tn["id"],
                            "type": "subject_to",
                            "direction": "unidirectional",
                            "description": desc,
                            "rule": "regulatory_test_requirement",
                        })
                        added += 1
        logger.info("Added %d subject_to relationships", added)
        self.stats["subject_to_added"] = added
        return added

    def _add_verifies_relationships(self) -> int:
        verifies_rules = [
            ("33.83", "33.27", "vibration test verifies rotor integrity"),
            ("33.84", "33.27", "over-torque test verifies rotor strength"),
            ("33.85", "33.51", "calibration test verifies engine performance"),
            ("33.88", "33.28", "over-temp test verifies engine control protection"),
            ("33.89", "33.75", "endurance test verifies safety analysis"),
            ("33.92", "33.27", "rotor locking test verifies rotor integrity"),
            ("33.94", "33.27", "blade containment test verifies rotor integrity"),
            ("E.340", "E.520", "vibration test verifies strength analysis"),
            ("E.440", "E.510", "endurance test verifies safety analysis"),
            ("E.650", "E.340", "vibration survey extends vibration test"),
            ("E.820", "E.520", "over-torque test verifies strength"),
        ]
        added = 0
        for test_pat, req_pat, desc in verifies_rules:
            test_nodes = self._find_nodes_matching("CCAR-33", test_pat) + self._find_nodes_matching("CS-E", test_pat)
            req_nodes = self._find_nodes_matching("CCAR-33", req_pat) + self._find_nodes_matching("CS-E", req_pat)
            for tn in test_nodes:
                for rn in req_nodes:
                    if not self._edge_exists(tn["id"], rn["id"], "verifies"):
                        self.edges.append({
                            "source": tn["id"],
                            "target": rn["id"],
                            "type": "verifies",
                            "direction": "unidirectional",
                            "description": desc,
                            "rule": "test_verifies_requirement",
                        })
                        added += 1
        logger.info("Added %d verifies relationships", added)
        self.stats["verifies_added"] = added
        return added

    def _compute_stats(self) -> None:
        rel_counts: dict[str, int] = defaultdict(int)
        for e in self.edges:
            rel_counts[e.get("type", "unknown")] += 1
        adj: dict[str, set[str]] = defaultdict(set)
        for e in self.edges:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
        isolated = sum(1 for neighs in adj.values() if len(neighs) == 0)
        self.stats.update({
            "total_nodes": len(self.nodes_by_id),
            "total_edges": len(self.edges),
            "isolated_nodes_remaining": isolated,
            "relationship_type_counts": dict(rel_counts),
        })
        logger.info("Final stats: %s", self.stats)

    # 文档ID别名映射 (短名 -> 长名)
    DOC_ALIASES = {
        "CCAR-33": "CCAR-33-R2",
        "FAR-33": "FAR-33",
        "CS-E": "CS-E",
        "CCAR-25": "CCAR-25-R4",
    }

    def _get_doc_id(self, node_id: str) -> str:
        for doc in ["CCAR-33-R2", "CCAR-25-R4", "CCAR-91", "CCAR-93TM-R2", "CS-E", "FAR-25", "FAR-33", "CCAR-23"]:
            if doc in node_id:
                return doc
        return "unknown"

    def _resolve_doc(self, doc: str) -> str:
        """解析文档ID，支持别名"""
        return self.DOC_ALIASES.get(doc, doc)

    def _find_nodes_matching(self, doc: str, clause: str) -> list[dict[str, Any]]:
        results = []
        clause_digits = re.sub(r"\D", "", clause)
        resolved_doc = self._resolve_doc(doc)
        for n in self.nodes_by_doc.get(resolved_doc, []):
            nid = n["id"]
            if clause_digits and clause_digits in re.sub(r"\D", "", nid):
                results.append(n)
        return results

    def _node_matches_keyword(self, node: dict[str, Any], keyword: str) -> bool:
        nid = node.get("id", "")
        lbl = node.get("label", "")
        desc = node.get("description", "")
        combined = f"{nid} {lbl} {desc}".lower()
        return keyword.lower() in combined

    def _edge_exists(self, src: str, tgt: str, rel_type: str) -> bool:
        for e in self.edges:
            if e.get("type") == rel_type:
                s, t = e.get("source", ""), e.get("target", "")
                if (s == src and t == tgt) or (s == tgt and t == src):
                    return True
        return False

    def _compute_connection_score(self, node_a: dict, node_b: dict) -> int:
        score = 0
        a_text = f"{node_a.get('label','')} {node_a.get('description','')}".lower()
        b_text = f"{node_b.get('label','')} {node_b.get('description','')}".lower()
        if self._get_doc_id(node_a["id"]) == self._get_doc_id(node_b["id"]):
            score += 5
        a_words = set(a_text.split())
        b_words = set(b_text.split())
        shared = a_words & b_words
        score += len(shared) * 2
        if node_a.get("type") == node_b.get("type"):
            score += 3
        return score

    def _infer_relationship_type(self, node_a: dict, node_b: dict) -> str:
        a_type = node_a.get("type", "")
        b_type = node_b.get("type", "")
        if a_type == "section" and b_type == "document":
            return "belongs_to"
        if a_type == "section" and b_type == "section":
            return "cross_references"
        if a_type == "keyword":
            return "related_to"
        return "cross_references"

    def _find_document_hub(self, doc: str) -> str | None:
        for n in self.nodes_by_doc.get(doc, []):
            if "hub" in n.get("id", "").lower() or n.get("type") == "document":
                return n["id"]
        nodes = self.nodes_by_doc.get(doc, [])
        return nodes[0]["id"] if nodes else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enhance AIAeroPlaneRag knowledge graph")
    parser.add_argument("--input", "-i", required=True, help="Input graph JSON path")
    parser.add_argument("--output", "-o", help="Output path (default: in-place)")
    parser.add_argument("--stats-only", action="store_true", help="Only print stats without modifying")
    args = parser.parse_args()

    enhancer = GraphRelationshipEnhancer(args.input)
    enhancer.load()

    if args.stats_only:
        rel_counts: dict[str, int] = defaultdict(int)
        for e in enhancer.edges:
            rel_counts[e.get("type", "unknown")] += 1
        adj = defaultdict(set)
        for e in enhancer.edges:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
        isolated = sum(1 for neighs in adj.values() if len(neighs) == 0)
        print(f"=== Current Graph Stats ===")
        print(f"Nodes: {len(enhancer.nodes_by_id)}")
        print(f"Edges: {len(enhancer.edges)}")
        print(f"Isolated nodes: {isolated}")
        print(f"\nRelationship types:")
        for t, c in sorted(rel_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        return

    logger.info("Starting all enhancements...")
    enhancer.run_all_enhancements()
    enhancer.save(args.output)
    print(json.dumps(enhancer.stats, indent=2))


if __name__ == "__main__":
    main()
