"""
LLM-Powered Entity Extraction Pipeline for Aviation Knowledge Graph.

Uses Claude to automatically extract entities (Regulations, Components, Parameters)
and relationships (CONSTRAINS, PART_OF, REFERS_TO) from parsed CCAR-33 regulations,
then seeds them into Neo4j.
"""
import os
import json
import logging
import re
from pathlib import Path
from typing import List, Dict

try:
    import openai
except ImportError:
    openai = None

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an expert aviation regulation analyst. Your task is to extract structured entities and relationships from Chinese civil aviation regulations (CCAR-33).

Extract the following entity types:
1. **Regulation** - A specific clause/article (e.g., "第 33.23 条 喘振裕度")
2. **Component** - A physical engine part (e.g., "压气机", "涡轮盘", "燃烧室")
3. **Parameter** - A measurable design parameter with constraints (e.g., "喘振裕度 > 15%", "燃烧效率 ≥ 99%")
4. **Test** - A required test procedure (e.g., "超转试验", "吞鸟试验")
5. **Material** - Material requirements (e.g., "耐火材料")

Extract the following relationship types:
1. **CONSTRAINS** - A regulation constrains a component's design
2. **REQUIRES_PARAMETER** - A regulation requires a specific parameter value
3. **REQUIRES_TEST** - A regulation requires a specific test
4. **PART_OF** - A component is part of a larger system
5. **REFERS_TO** - One regulation refers to another

Output ONLY valid JSON with this exact structure:
{
  "entities": [
    {"id": "unique_id", "type": "Regulation|Component|Parameter|Test|Material", "name": "entity name", "description": "brief description"}
  ],
  "relationships": [
    {"source": "source_entity_id", "target": "target_entity_id", "type": "CONSTRAINS|REQUIRES_PARAMETER|REQUIRES_TEST|PART_OF|REFERS_TO", "description": "brief description"}
  ]
}"""

class LLMEntityExtractor:
    """
    Uses Claude to extract aviation ontology entities and relationships from
    regulation text chunks, then loads them into Neo4j.
    """
    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY")
        self.client = None

        if not self.api_key:
            logger.warning("ZHIPU_API_KEY not set. Extractor will use fallback mock data.")
        elif not openai:
            logger.warning("openai library not installed. Run: pip install openai")
        else:
            self.client = openai.OpenAI(
                api_key=self.api_key, 
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )
            logger.info("GLM API client initialized for entity extraction.")

        # Neo4j connection
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_pass = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")
        self.driver = None

        if GraphDatabase:
            try:
                self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_pass))
                self.driver.verify_connectivity()
                logger.info("Connected to Neo4j.")
            except Exception as e:
                logger.warning(f"Neo4j not available: {e}. Will export to JSON fallback.")
                self.driver = None

    def extract_from_chunk(self, chunk_text: str) -> Dict:
        """Use Claude to extract entities and relationships from a text chunk."""
        if not self.client:
            logger.info("No Claude client. Using mock extraction.")
            return self._mock_extract(chunk_text)

        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"请从以下航空发动机适航规定文本中提取实体和关系：\n\n{chunk_text}"}
                ]
            )

            raw = response.choices[0].message.content
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
            if json_match:
                raw = json_match.group(1)
            
            result = json.loads(raw.strip())
            entity_count = len(result.get("entities", []))
            rel_count = len(result.get("relationships", []))
            logger.info(f"Extracted {entity_count} entities and {rel_count} relationships from chunk.")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude JSON: {e}")
            logger.debug(f"Raw output: {raw[:500]}")
            logger.info("Falling back to regex-based extraction.")
            return self._mock_extract(chunk_text)
        except Exception as e:
            logger.error(f"GLM extraction error: {e}")
            logger.info("Falling back to regex-based extraction.")
            return self._mock_extract(chunk_text)

    def extract_from_document(self, md_filepath: str, chunk_size: int = 3000) -> Dict:
        """Process an entire markdown document by splitting into chunks."""
        filepath = Path(md_filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return {"entities": [], "relationships": []}

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by ## headers to get chapter-level chunks
        sections = re.split(r'(?=^## )', content, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        all_entities = []
        all_relationships = []
        seen_entity_ids = set()

        logger.info(f"Processing {len(sections)} sections from {filepath.name}...")

        for i, section in enumerate(sections):
            logger.info(f"[{i+1}/{len(sections)}] Extracting from section: {section[:60]}...")
            result = self.extract_from_chunk(section)

            for entity in result.get("entities", []):
                if entity["id"] not in seen_entity_ids:
                    all_entities.append(entity)
                    seen_entity_ids.add(entity["id"])

            all_relationships.extend(result.get("relationships", []))

        combined = {"entities": all_entities, "relationships": all_relationships}
        logger.info(f"Total: {len(all_entities)} entities, {len(all_relationships)} relationships extracted.")

        # Save to JSON for inspection
        output_path = filepath.parent / (filepath.stem + "_graph.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved extraction results to {output_path}")

        return combined

    def load_to_neo4j(self, graph_data: Dict):
        """Load extracted entities and relationships into Neo4j."""
        if not self.driver:
            logger.warning("Neo4j not available. Skipping graph loading.")
            return

        entities = graph_data.get("entities", [])
        relationships = graph_data.get("relationships", [])

        with self.driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing Neo4j data.")

            # Create entities
            for entity in entities:
                cypher = f"""
                MERGE (n:{entity['type']} {{id: $id}})
                SET n.name = $name, n.description = $description, n.type = $type
                """
                session.run(cypher, id=entity["id"], name=entity["name"],
                           description=entity.get("description", ""), type=entity["type"])

            logger.info(f"Created {len(entities)} entity nodes in Neo4j.")

            # Create relationships
            for rel in relationships:
                cypher = f"""
                MATCH (a {{id: $source}})
                MATCH (b {{id: $target}})
                MERGE (a)-[r:{rel['type']}]->(b)
                SET r.description = $description
                """
                try:
                    session.run(cypher, source=rel["source"], target=rel["target"],
                               description=rel.get("description", ""))
                except Exception as e:
                    logger.warning(f"Failed to create relationship {rel}: {e}")

            logger.info(f"Created {len(relationships)} relationships in Neo4j.")

    def _mock_extract(self, chunk_text: str) -> Dict:
        """Fallback mock extractor for when Claude is unavailable."""
        # Parse headers to create basic entities
        entities = []
        relationships = []

        lines = chunk_text.split('\n')
        current_reg = None

        for line in lines:
            line = line.strip()
            h3_match = re.match(r'^### 第 (\S+) 条\s+(.+)', line)
            if h3_match:
                reg_id = f"CCAR-{h3_match.group(1)}"
                reg_name = h3_match.group(2)
                current_reg = reg_id
                entities.append({
                    "id": reg_id,
                    "type": "Regulation",
                    "name": f"第 {h3_match.group(1)} 条 {reg_name}",
                    "description": reg_name
                })

            # Simple component detection
            for comp_name in ["压气机", "涡轮", "燃烧室", "轴", "轴承", "叶片", "涡轮盘", "压气机盘"]:
                if comp_name in line and current_reg:
                    comp_id = f"comp_{comp_name}"
                    if comp_id not in [e["id"] for e in entities]:
                        entities.append({
                            "id": comp_id,
                            "type": "Component",
                            "name": comp_name,
                            "description": f"发动机部件: {comp_name}"
                        })
                    relationships.append({
                        "source": current_reg,
                        "target": comp_id,
                        "type": "CONSTRAINS",
                        "description": f"{current_reg} 约束了 {comp_name} 的设计"
                    })

            # Simple parameter detection
            pct_match = re.search(r'(\S+)\s*(?:不低于|大于|不得低于|≥|>)\s*(\d+[%°C]?\S*)', line)
            if pct_match and current_reg:
                param_name = f"{pct_match.group(1)} ≥ {pct_match.group(2)}"
                param_id = f"param_{param_name.replace(' ', '_')}"
                if param_id not in [e["id"] for e in entities]:
                    entities.append({
                        "id": param_id,
                        "type": "Parameter",
                        "name": param_name,
                        "description": f"设计参数要求: {param_name}"
                    })
                relationships.append({
                    "source": current_reg,
                    "target": param_id,
                    "type": "REQUIRES_PARAMETER",
                    "description": f"{current_reg} 要求参数 {param_name}"
                })

            # Simple test detection
            for test_name in ["超转试验", "吞鸟试验", "吞冰试验", "持久试验", "超温试验", "包容性试验", "低循环疲劳试验"]:
                if test_name in line and current_reg:
                    test_id = f"test_{test_name}"
                    if test_id not in [e["id"] for e in entities]:
                        entities.append({
                            "id": test_id,
                            "type": "Test",
                            "name": test_name,
                            "description": f"试验要求: {test_name}"
                        })
                    relationships.append({
                        "source": current_reg,
                        "target": test_id,
                        "type": "REQUIRES_TEST",
                        "description": f"{current_reg} 要求进行 {test_name}"
                    })

        return {"entities": entities, "relationships": relationships}

    def close(self):
        if self.driver:
            self.driver.close()


if __name__ == "__main__":
    extractor = LLMEntityExtractor()

    # Extract from enriched CCAR-33
    processed_dir = Path(__file__).parent.parent.parent / "data" / "processed"
    ccar33_path = processed_dir / "CCAR-33.md"

    if ccar33_path.exists():
        graph_data = extractor.extract_from_document(str(ccar33_path))
        print(f"\n{'='*60}")
        print(f" Extraction Complete: {len(graph_data['entities'])} entities, {len(graph_data['relationships'])} relationships")
        print(f"{'='*60}")

        # Attempt to load into Neo4j
        extractor.load_to_neo4j(graph_data)
    else:
        print(f"CCAR-33.md not found at {ccar33_path}")

    extractor.close()
