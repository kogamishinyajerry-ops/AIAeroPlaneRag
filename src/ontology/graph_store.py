import json
import logging
import os
from pathlib import Path
from typing import Dict, List

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from dotenv import load_dotenv

from settings import PROCESSED_DATA_DIR


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OntologyGraphStore:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")
        self.driver = None
        self.node_count = 0
        self.fallback_graph = self._load_fallback_graph()

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

    @property
    def has_fallback_data(self) -> bool:
        return bool(self.fallback_graph.get("entities") or self.fallback_graph.get("relationships"))

    def close(self):
        if self.driver:
            self.driver.close()

    def _refresh_graph_state(self):
        if not self.driver:
            self.node_count = 0
            return
        try:
            with self.driver.session() as session:
                self.node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        except Exception as exc:
            logger.warning("Failed to inspect graph state: %s", exc)
            self.node_count = 0

    def _load_fallback_graph(self) -> Dict:
        graph_path = Path(PROCESSED_DATA_DIR) / "CCAR-33_graph.json"
        if not graph_path.exists():
            return {"entities": [], "relationships": []}
        try:
            return json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load fallback graph JSON: %s", exc)
            return {"entities": [], "relationships": []}

    def query_graph(self, keyword: str) -> List[Dict]:
        if not self.driver or not self.has_graph_data:
            if self.has_fallback_data:
                return self._query_fallback_graph(keyword)
            return self._mock_query(keyword)

        results: List[Dict] = []
        try:
            with self.driver.session() as session:
                records = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE exists(a.id) AND exists(b.id)
                      AND (
                           coalesce(a.name, '') CONTAINS $kw
                        OR coalesce(b.name, '') CONTAINS $kw
                        OR coalesce(a.id, '') CONTAINS $kw
                        OR coalesce(b.id, '') CONTAINS $kw
                      )
                    RETURN coalesce(a.id, '') AS a_id,
                           coalesce(a.name, '') AS a_name,
                           coalesce(a.type, '') AS a_type,
                           type(r) AS rel_type,
                           coalesce(r.description, '') AS rel_desc,
                           coalesce(b.id, '') AS b_id,
                           coalesce(b.name, '') AS b_name,
                           coalesce(b.type, '') AS b_type
                    LIMIT 20
                    """,
                    kw=keyword,
                )

                for record in records:
                    results.append(
                        {
                            "regulation": record["a_name"] or record["a_id"],
                            "component": record["b_name"] or record["b_id"],
                            "relationship": record["rel_type"],
                            "parameter": record["rel_desc"] or "",
                            "description": f"{record['a_name'] or record['a_id']} --[{record['rel_type']}]--> {record['b_name'] or record['b_id']}",
                        }
                    )
        except Exception as exc:
            logger.error("Graph query failed: %s", exc)

        return results

    def _query_fallback_graph(self, keyword: str) -> List[Dict]:
        keyword_lower = keyword.lower()
        entities = {entity["id"]: entity for entity in self.fallback_graph.get("entities", [])}
        results: List[Dict] = []

        for relationship in self.fallback_graph.get("relationships", []):
            source = entities.get(relationship.get("source", ""), {})
            target = entities.get(relationship.get("target", ""), {})
            haystacks = [
                source.get("id", ""),
                source.get("name", ""),
                source.get("description", ""),
                target.get("id", ""),
                target.get("name", ""),
                target.get("description", ""),
                relationship.get("description", ""),
            ]
            if not any(keyword_lower in str(value).lower() for value in haystacks):
                continue

            results.append(
                {
                    "regulation": source.get("name") or source.get("id", ""),
                    "component": target.get("name") or target.get("id", ""),
                    "relationship": relationship.get("type", "RELATED_TO"),
                    "parameter": relationship.get("description", ""),
                    "description": f"{source.get('name') or source.get('id', '')} --[{relationship.get('type', 'RELATED_TO')}]--> {target.get('name') or target.get('id', '')}",
                }
            )

        return results[:20]

    def get_graph_snapshot(self) -> Dict:
        if self.driver and self.has_graph_data:
            return {"mode": "neo4j", "nodes": None, "edges": None}

        nodes = []
        edges = []
        for entity in self.fallback_graph.get("entities", []):
            nodes.append(
                {
                    "id": entity.get("id"),
                    "label": entity.get("name") or entity.get("id"),
                    "type": entity.get("type", "Unknown").lower(),
                    "description": entity.get("description", ""),
                }
            )
        for relationship in self.fallback_graph.get("relationships", []):
            edges.append(
                {
                    "source": relationship.get("source"),
                    "target": relationship.get("target"),
                    "type": relationship.get("type", "RELATED_TO"),
                    "description": relationship.get("description", ""),
                }
            )
        return {"mode": "fallback", "nodes": nodes, "edges": edges}

    def _mock_query(self, keyword: str) -> List[Dict]:
        return [
            {
                "regulation": "CCAR-33.21",
                "relationship": "CONSTRAINS",
                "component": keyword,
                "parameter": "",
                "description": f"CCAR-33.21 constrains {keyword}",
            }
        ]
