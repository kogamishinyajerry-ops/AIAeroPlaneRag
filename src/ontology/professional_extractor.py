"""
Professional CCAR-33-R2 Knowledge Graph Builder

Builds a professional aviation engine regulation knowledge graph with expanded
entity types and relationships based on real CCAR-33-R2 content.
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    id: str
    type: str
    name: str
    description: str = ""
    properties: Dict = field(default_factory=dict)


@dataclass
class Relationship:
    source: str
    target: str
    type: str
    description: str = ""
    properties: Dict = field(default_factory=dict)


# Professional entity types for CCAR-33-R2
ENTITY_TYPES = {
    # Regulations
    "Regulation": "法规条款",
    "Section": "章节",
    "Subsection": "分条款",

    # Engine Components
    "Component": "发动机部件",
    "RotorPart": "转子部件",
    "StatorPart": "静子部件",
    "LifeLimitedPart": "限寿件",
    "Accessory": "附件",

    # Tests & Inspections
    "Test": "试验",
    "Inspection": "检查",
    "Calibration": "校准",

    # Parameters & Requirements
    "Parameter": "参数",
    "Limit": "限制值",
    "Rating": "额定值",

    # Failure & Safety
    "FailureMode": "失效模式",
    "FailureEffect": "失效后果",
    "SafetyObjective": "安全目标",

    # Documents & References
    "Document": "文件",
    "Standard": "标准",
    "AdvisoryCircular": "咨询通告",
}

# Professional relationship types
RELATIONSHIP_TYPES = {
    # Regulatory relationships
    "CONSTRAINS": "约束",
    "REQUIRES": "要求",
    "REFERS_TO": "引用",
    "DEFINES": "定义",
    "EXEMPTS": "豁免",

    # Structural relationships
    "PART_OF": "属于",
    "CONTAINS": "包含",
    "CONNECTED_TO": "连接到",

    # Test relationships
    "TESTED_BY": "通过...验证",
    "VALIDATES": "验证",
    "REQUIRES_TEST": "要求试验",

    # Parameter relationships
    "LIMITS": "限制",
    "SPECIFIES": "规定",
    "MEASURES": "测量",

    # Failure relationships
    "CAUSES": "导致",
    "PREVENTS": "防止",
    "MITIGATES": "缓解",
    "DETECTS": "检测",

    # Compliance
    "COMPLIES_WITH": "符合",
    "DEMONSTRATES": "证明",
}


class CCAR33KnowledgeGraphBuilder:
    """
    Builds a professional knowledge graph from CCAR-33-R2 regulation text.
    """

    # Professional component patterns
    COMPONENT_PATTERNS = [
        # Rotor parts
        r"(压气机盘|涡轮盘|风扇盘|整体叶盘)",
        r"(压气机转子|涡轮转子|风扇转子)",
        r"(高压转子|低压转子|中压转子)",
        r"(转子叶片|静子叶片|导向叶片)",
        r"(涡轮叶片|压气机叶片|风扇叶片)",
        r"(隔圈|轮毂|轴|转子轴)",

        # Stator parts
        r"(机匣|压气机机匣|涡轮机匣|燃烧室机匣)",
        r"(燃烧室|火焰筒|燃油喷嘴)",
        r"(进气道|整流罩|扩压器)",

        # Accessories
        r"(附件齿轮箱|附件传动|安装构件)",
        r"(燃油控制器|燃油泵|滑油泵)",
        r"(点火器|点火系统)",
        r"(轴承|密封件)",

        # General
        r"(发动机|涡轮发动机|活塞发动机)",
        r"(螺旋桨|反推装置|加力燃烧室)",
    ]

    # Test patterns
    TEST_PATTERNS = [
        r"(超转试验|超温试验|超扭试验)",
        r"(持久试验|150小时持久试验)",
        r"(校准试验|振动试验)",
        r"(吞鸟试验|吸鸟试验|吸冰试验|吸雹试验|吸雨试验)",
        r"(包容性试验|叶片包容性试验)",
        r"(起动试验|工作试验)",
        r"(分解检查|初始维修检查)",
        r"(转子锁定试验)",
        r"(假起动)",
    ]

    # Failure mode patterns
    FAILURE_MODE_PATTERNS = [
        r"(喘振|失速)",
        r"(非包容的高能碎片|叶片脱落)",
        r"(不可控火情|着火)",
        r"(失去推力控制|LOTC|LOPC)",
        r"(空中停车)",
        r"(转子不平衡|振动)",
        r"(外物损伤|FOD)",
        r"(低循环疲劳|LCF|高循环疲劳|HCF)",
        r"(蠕变|氧化|热机械疲劳)",
    ]

    # Limit/parameter patterns
    PARAMETER_PATTERNS = [
        r"(\d+[%％][\s]*以上|不低于[\s]*\d+[%％]|大于[\s]*\d+[%％]|≥[\s]*\d+[%％])",
        r"(\d+[\s]*分钟|\d+[\s]*小时|\d+[\s]*次)",
        r"(\d+\.?\d*[\s]*°C|\d+\.?\d*[\s]*°F)",
        r"(\d+\.?\d*[\s]*kPa|\d+\.?\d*[\s]*p\.s\.i\.|bar|psi)",
        r"(120[%％]|115[%％]|105[%％]|103[%％]|100[%％]|90[%％]|80[%％]|75[%％])",
        r"(最大连续|起飞|OEI|一台发动机不工作)",
        r"(限制温度|限制压力|最大转速)",
    ]

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.current_section = None

    def parse_regulation_header(self, line: str) -> Tuple[str, str, str]:
        """Parse regulation section headers and return (id, type, name)."""
        # Pattern: ## 第XX条 条款名称
        h2_match = re.match(r'^##\s+第(\d+[\.您期点]*)\s*条\s+(.+)', line)
        if h2_match:
            section_num = h2_match.group(1)
            name = h2_match.group(2).strip()
            return f"sec_33.{section_num}", "Section", f"第33.{section_num}条 {name}"

        # Pattern: ### 子条款名称
        h3_match = re.match(r'^###\s+([（\(]?[a-z][）\)]?[\d]*)?\s*(.+)', line)
        if h3_match:
            return None, "Subsection", h3_match.group(2).strip()

        # Pattern: # 章节名称
        h1_match = re.match(r'^#\s+(.+)', line)
        if h1_match:
            name = h1_match.group(1).strip()
            # Extract chapter letter
            chapter_match = re.search(r'([A-Z])章', name)
            if chapter_match:
                return f"ch_{chapter_match.group(1)}", "Chapter", name
            return f"ch_{name[:5]}", "Chapter", name

        return None, None, None

    def extract_components(self, text: str, source_id: str) -> List[Entity]:
        """Extract component entities from text."""
        components = []

        for pattern in self.COMPONENT_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                comp_name = match
                # Normalize name
                if "盘" in comp_name:
                    comp_type = "LifeLimitedPart"
                elif "转子" in comp_name or "叶片" in comp_name:
                    comp_type = "RotorPart"
                elif "机匣" in comp_name or "燃烧室" in comp_name:
                    comp_type = "StatorPart"
                elif "附件" in comp_name or "泵" in comp_name or "控制器" in comp_name:
                    comp_type = "Accessory"
                else:
                    comp_type = "Component"

                comp_id = f"comp_{comp_name}"
                if comp_id not in self.entities:
                    entity = Entity(
                        id=comp_id,
                        type=comp_type,
                        name=comp_name,
                        description=f"发动机部件: {comp_name}",
                        properties={"chinese_name": comp_name}
                    )
                    self.entities[comp_id] = entity
                    components.append(entity)

        return components

    def extract_tests(self, text: str, source_id: str) -> List[Entity]:
        """Extract test entities from text."""
        tests = []

        for pattern in self.TEST_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                test_name = match
                test_id = f"test_{test_name}"
                if test_id not in self.entities:
                    entity = Entity(
                        id=test_id,
                        type="Test",
                        name=test_name,
                        description=f"试验: {test_name}",
                        properties={"chinese_name": test_name}
                    )
                    self.entities[test_id] = entity
                    tests.append(entity)

        return tests

    def extract_parameters(self, text: str, source_id: str) -> List[Entity]:
        """Extract parameter/limit entities from text."""
        params = []

        # Extract specific numeric requirements
        for pattern in self.PARAMETER_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                param_value = match
                # Try to find context
                context_match = re.search(r'.{0,20}' + re.escape(param_value) + r'.{0,20}', text)
                if context_match:
                    context = context_match.group(0).strip()
                    param_id = f"param_{abs(hash(param_value)) % 1000000}"
                    if param_id not in self.entities:
                        entity = Entity(
                            id=param_id,
                            type="Parameter",
                            name=f"参数: {param_value}",
                            description=context,
                            properties={"value": param_value, "context": context}
                        )
                        self.entities[param_id] = entity
                        params.append(entity)

        return params

    def extract_regulations(self, text: str) -> List[Entity]:
        """Extract regulation section entities."""
        regulations = []
        lines = text.split('\n')

        current_reg_id = None
        current_reg_name = None

        for line in lines:
            reg_id, reg_type, reg_name = self.parse_regulation_header(line)
            if reg_id:
                if reg_id not in self.entities:
                    entity = Entity(
                        id=reg_id,
                        type=reg_type,
                        name=reg_name,
                        description=f"CCAR-33条款: {reg_name}"
                    )
                    self.entities[reg_id] = entity
                    self.current_section = reg_id
                    regulations.append(entity)
            elif line.strip().startswith('##') or line.strip().startswith('#'):
                self.current_section = reg_id

        return regulations

    def extract_failure_concepts(self, text: str) -> List[Entity]:
        """Extract failure mode and effect concepts."""
        failures = []

        # Hazardous engine effects (from 33.75)
        hazardous_effects = [
            ("非包容的高能碎片", "HazardousEngineEffect"),
            ("客舱引气中有毒物质", "HazardousEngineEffect"),
            ("与驾驶员命令相反的推力", "HazardousEngineEffect"),
            ("不可控火情", "HazardousEngineEffect"),
            ("发动机安装系统失效", "HazardousEngineEffect"),
            ("螺旋桨脱开", "HazardousEngineEffect"),
            ("完全失去停车能力", "HazardousEngineEffect"),
        ]

        for effect_name, effect_type in hazardous_effects:
            if effect_name in text:
                effect_id = f"failure_{effect_name[:4]}"
                if effect_id not in self.entities:
                    entity = Entity(
                        id=effect_id,
                        type=effect_type,
                        name=effect_name,
                        description=f"危害性发动机后果: {effect_name}"
                    )
                    self.entities[effect_id] = entity
                    failures.append(entity)

        # Failure modes
        for pattern in self.FAILURE_MODE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                failure_id = f"fail_{match[:4]}"
                if failure_id not in self.entities:
                    entity = Entity(
                        id=failure_id,
                        type="FailureMode",
                        name=match,
                        description=f"失效模式: {match}"
                    )
                    self.entities[failure_id] = entity
                    failures.append(entity)

        return failures

    def build_relationships(self, text: str, source_id: str = None):
        """Build relationships based on text analysis."""
        lines = text.split('\n')
        current_source = source_id or self.current_section

        for line in lines:
            # Check for section header
            reg_id, _, _ = self.parse_regulation_header(line)
            if reg_id:
                current_source = reg_id
                continue

            if not current_source:
                continue

            # Extract relationships
            # Component constraints
            for comp_pattern in self.COMPONENT_PATTERNS:
                matches = re.findall(comp_pattern, line)
                for match in matches:
                    comp_id = f"comp_{match}"
                    if comp_id in self.entities:
                        rel = Relationship(
                            source=current_source,
                            target=comp_id,
                            type="CONSTRAINS",
                            description=f"{current_source} 约束 {match} 的设计"
                        )
                        self.relationships.append(rel)

            # Test requirements
            for test_pattern in self.TEST_PATTERNS:
                matches = re.findall(test_pattern, line)
                for match in matches:
                    test_id = f"test_{match}"
                    if test_id in self.entities:
                        rel = Relationship(
                            source=current_source,
                            target=test_id,
                            type="REQUIRES_TEST",
                            description=f"{current_source} 要求 {match}"
                        )
                        self.relationships.append(rel)

            # Regulation references
            if "第33." in line or "CCAR-" in line or "CCAR-" in line:
                ref_match = re.search(r'第(\d+[\.您期点]*)\s*条', line)
                if ref_match:
                    ref_id = f"sec_33.{ref_match.group(1)}"
                    if ref_id in self.entities and ref_id != current_source:
                        rel = Relationship(
                            source=current_source,
                            target=ref_id,
                            type="REFERS_TO",
                            description=line.strip()
                        )
                        self.relationships.append(rel)

    def process_chapter_file(self, filepath: Path) -> Dict:
        """Process a single CCAR-33 chapter file."""
        logger.info(f"Processing {filepath.name}...")

        content = filepath.read_text(encoding="utf-8")

        # Extract all entities
        self.extract_regulations(content)
        self.extract_components(content, filepath.stem)
        self.extract_tests(content, filepath.stem)
        self.extract_parameters(content, filepath.stem)
        self.extract_failure_concepts(content)

        # Build relationships
        self.build_relationships(content)

        return {
            "entities": len(self.entities),
            "relationships": len(self.relationships)
        }

    def process_all_chapters(self, chapters_dir: Path) -> Dict:
        """Process all CCAR-33-R2 chapter files."""
        chapter_files = [
            "A-总则.md",
            "B-设计与构造总则.md",
            "C-设计与构造活塞发动机.md",
            "D-台架试验活塞发动机.md",
            "E-设计与构造涡轮发动机.md",
            "F-台架试验涡轮发动机.md",
            "G-ETOPS专用要求.md",
        ]

        results = {"files": {}, "total_entities": 0, "total_relationships": 0}

        for filename in chapter_files:
            filepath = chapters_dir / filename
            if filepath.exists():
                file_result = self.process_chapter_file(filepath)
                results["files"][filename] = file_result
                logger.info(f"  -> {filename}: {file_result['entities']} entities")

        results["total_entities"] = len(self.entities)
        results["total_relationships"] = len(self.relationships)

        return results

    def to_graph_dict(self) -> Dict:
        """Convert to graph dictionary format."""
        return {
            "entities": [
                {
                    "id": e.id,
                    "type": e.type,
                    "name": e.name,
                    "description": e.description,
                    **e.properties
                }
                for e in self.entities.values()
            ],
            "relationships": [
                {
                    "source": r.source,
                    "target": r.target,
                    "type": r.type,
                    "description": r.description,
                    **r.properties
                }
                for r in self.relationships
            ]
        }

    def save_graph(self, output_path: Path):
        """Save graph to JSON file."""
        graph_data = self.to_graph_dict()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved graph with {len(graph_data['entities'])} entities "
                   f"and {len(graph_data['relationships'])} relationships to {output_path}")

        # Print statistics
        entity_types = {}
        for e in graph_data["entities"]:
            entity_types[e["type"]] = entity_types.get(e["type"], 0) + 1

        rel_types = {}
        for r in graph_data["relationships"]:
            rel_types[r["type"]] = rel_types.get(r["type"], 0) + 1

        logger.info(f"Entity types: {entity_types}")
        logger.info(f"Relationship types: {rel_types}")

        return graph_data


def main():
    """Main entry point for knowledge graph building."""
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from settings import PROCESSED_DATA_DIR

    print("=" * 60)
    print(" CCAR-33-R2 Professional Knowledge Graph Builder")
    print("=" * 60)

    chapters_dir = PROCESSED_DATA_DIR / "CCAR-33-R2_chapters"
    if not chapters_dir.exists():
        print(f"[ERROR] Chapters directory not found: {chapters_dir}")
        return

    # Build graph
    builder = CCAR33KnowledgeGraphBuilder()
    results = builder.process_all_chapters(chapters_dir)

    print("\n" + "=" * 60)
    print(" BUILD RESULTS")
    print("=" * 60)
    print(f"Total entities: {results['total_entities']}")
    print(f"Total relationships: {results['total_relationships']}")

    # Save graph
    output_path = PROCESSED_DATA_DIR / "CCAR-33-R2_professional_graph.json"
    builder.save_graph(output_path)

    print(f"\n[DONE] Graph saved to: {output_path}")


if __name__ == "__main__":
    main()
