#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CCAR-33-R2 知识库全面测试脚本
测试向量库、图数据库和API服务
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import traceback

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("警告: chromadb 未安装")
    chromadb = None

try:
    from neo4j import GraphDatabase
except ImportError:
    print("警告: neo4j 未安装")
    GraphDatabase = None

try:
    import requests
except ImportError:
    print("警告: requests 未安装")
    requests = None


class KnowledgeBaseTester:
    """知识库测试器"""

    def __init__(self):
        self.chroma_path = "D:/AIAeroPlaneRag/data/processed/chroma_db"
        self.neo4j_uri = "bolt://localhost:7687"
        self.api_base = "http://127.0.0.1:8001"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {}
        }

    def test_chromadb(self) -> Dict[str, Any]:
        """测试ChromaDB向量库"""
        print("\n" + "="*60)
        print("1. 测试ChromaDB向量库")
        print("="*60)

        if chromadb is None:
            return {"status": "error", "message": "chromadb未安装"}

        try:
            client = chromadb.PersistentClient(path=self.chroma_path)
            collections = client.list_collections()

            result = {
                "status": "success",
                "total_collections": len(collections),
                "collections": [],
                "total_chunks": 0,
                "chapter_coverage": {},
                "section_coverage": {},
                "sample_chunks": []
            }

            for col in collections:
                count = col.count()
                result["total_chunks"] += count

                col_info = {
                    "name": col.name,
                    "count": count,
                    "metadata": col.metadata
                }
                result["collections"].append(col_info)

                # 获取样本文档
                if count > 0:
                    samples = col.get(limit=10, include=['documents', 'metadatas'])

                    # 分析章节覆盖
                    for meta in samples.get('metadatas', []):
                        chapter = meta.get('chapter', '')
                        section = meta.get('section', '')

                        if chapter:
                            result["chapter_coverage"][chapter] = \
                                result["chapter_coverage"].get(chapter, 0) + 1
                        if section:
                            result["section_coverage"][section] = \
                                result["section_coverage"].get(section, 0) + 1

                    # 保存样本
                    for i, (doc, meta) in enumerate(zip(
                        samples.get('documents', [])[:3],
                        samples.get('metadatas', [])[:3]
                    )):
                        result["sample_chunks"].append({
                            "content": doc[:200] + "..." if len(doc) > 200 else doc,
                            "metadata": {k: v for k, v in meta.items()
                                       if k not in ['document_id', 'embedding']}
                        })

            print(f"  集合数量: {result['total_collections']}")
            print(f"  总chunk数: {result['total_chunks']}")

            print(f"\n  章节覆盖:")
            for ch, cnt in sorted(result["chapter_coverage"].items()):
                print(f"    {ch}: {cnt} chunks")

            print(f"\n  条款覆盖数: {len(result['section_coverage'])}")

            self.results["tests"]["chromadb"] = result
            return result

        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            self.results["tests"]["chromadb"] = error_result
            print(f"  错误: {e}")
            traceback.print_exc()
            return error_result

    def test_neo4j(self) -> Dict[str, Any]:
        """测试Neo4j图数据库"""
        print("\n" + "="*60)
        print("2. 测试Neo4j图数据库")
        print("="*60)

        if GraphDatabase is None:
            return {"status": "error", "message": "neo4j未安装"}

        try:
            # 尝试从环境变量读取凭据
            driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=("neo4j", "ccar33knowledgegraph")
            )

            result = {
                "status": "success",
                "node_types": {},
                "relationship_types": {},
                "total_nodes": 0,
                "total_relationships": 0,
                "sample_queries": []
            }

            with driver.session() as session:
                # 获取节点类型和数量
                node_query = """
                MATCH (n)
                RETURN labels(n) as labels, count(n) as count
                ORDER BY count DESC
                """
                nodes = session.run(node_query)
                for record in nodes:
                    labels = record["labels"]
                    if labels:
                        label = labels[0]
                        result["node_types"][label] = record["count"]
                        result["total_nodes"] += record["count"]

                # 获取关系类型
                rel_query = """
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
                """
                rels = session.run(rel_query)
                for record in rels:
                    result["relationship_types"][record["type"]] = record["count"]
                    result["total_relationships"] += record["count"]

                # 查询所有条款
                section_query = """
                MATCH (s:Section)
                RETURN s.number as number, s.title as title
                ORDER BY s.number
                """
                sections = session.run(section_query)
                result["sections"] = [dict(record) for record in sections]

                # 查询所有参数
                param_query = """
                MATCH (p:Parameter)
                RETURN p.name as name, p.value as value, p.unit as unit
                LIMIT 20
                """
                params = session.run(param_query)
                result["sample_parameters"] = [dict(record) for record in params]

            print(f"  总节点数: {result['total_nodes']}")
            print(f"  总关系数: {result['total_relationships']}")

            print(f"\n  节点类型:")
            for label, count in sorted(result["node_types"].items()):
                print(f"    {label}: {count}")

            print(f"\n  关系类型:")
            for rel_type, count in sorted(result["relationship_types"].items()):
                print(f"    {rel_type}: {count}")

            print(f"\n  条款数量: {len(result.get('sections', []))}")

            driver.close()
            self.results["tests"]["neo4j"] = result
            return result

        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            self.results["tests"]["neo4j"] = error_result
            print(f"  错误: {e}")
            traceback.print_exc()
            return error_result

    def test_api(self) -> Dict[str, Any]:
        """测试API服务"""
        print("\n" + "="*60)
        print("3. 测试API服务")
        print("="*60)

        if requests is None:
            return {"status": "error", "message": "requests未安装"}

        result = {
            "status": "success",
            "endpoints": {},
            "query_tests": []
        }

        try:
            # 测试health端点
            resp = requests.get(f"{self.api_base}/api/v1/health", timeout=5)
            result["endpoints"]["health"] = {
                "status_code": resp.status_code,
                "response": resp.json() if resp.status_code == 200 else resp.text
            }
            print(f"  Health: {resp.status_code}")

            # 测试sources端点
            resp = requests.get(f"{self.api_base}/api/v1/sources", timeout=5)
            result["endpoints"]["sources"] = {
                "status_code": resp.status_code,
                "response": resp.json() if resp.status_code == 200 else resp.text
            }
            print(f"  Sources: {resp.status_code}")

            # 测试graph nodes端点
            resp = requests.get(f"{self.api_base}/api/v1/graph/nodes", timeout=5)
            result["endpoints"]["graph_nodes"] = {
                "status_code": resp.status_code,
                "response": resp.json() if resp.status_code == 200 else resp.text
            }
            print(f"  Graph Nodes: {resp.status_code}")

            self.results["tests"]["api"] = result
            return result

        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            self.results["tests"]["api"] = error_result
            print(f"  错误: {e}")
            traceback.print_exc()
            return error_result

    def run_retrieval_tests(self) -> Dict[str, Any]:
        """运行检索测试"""
        print("\n" + "="*60)
        print("4. 运行检索准确性测试")
        print("="*60)

        if requests is None:
            return {"status": "error", "message": "requests未安装"}

        test_cases = [
            # 条款检索测试
            {"query": "第33.27条转子超转试验", "category": "条款检索",
             "expected_keywords": ["超转", "120%", "转子"]},
            {"query": "第33.28条叶片包容性试验", "category": "条款检索",
             "expected_keywords": ["包容性", "叶片", "断裂"]},
            {"query": "第33.29条持久试验", "category": "条款检索",
             "expected_keywords": ["持久", "150小时", "试验"]},

            # 参数检索测试
            {"query": "超转试验转速要求", "category": "参数检索",
             "expected_keywords": ["120%", "最大允许转速"]},
            {"query": "持久试验持续时间", "category": "参数检索",
             "expected_keywords": ["150小时"]},
            {"query": "吸鸟试验的鸟重", "category": "参数检索",
             "expected_keywords": ["1.15公斤", "2.5公斤", "鸟"]},

            # 试验条件测试
            {"query": "150小时持久试验的具体要求", "category": "试验条件",
             "expected_keywords": ["150小时", "循环", "温度"]},
            {"query": "吸鸟试验如何进行", "category": "试验条件",
             "expected_keywords": ["吸入", "鸟", "速度", "高度"]},
            {"query": "燃油系统防火试验", "category": "试验条件",
             "expected_keywords": ["防火", "火焰", "1500度"]},

            # 定义测试
            {"query": "什么是限寿件", "category": "定义",
             "expected_keywords": ["限寿件", "寿命", "安全"]},
            {"query": "危害性后果包括哪些", "category": "定义",
             "expected_keywords": ["危害性", "后果", "火灾", "爆炸"]},

            # 综合查询
            {"query": "压气机喘振裕度的要求是什么", "category": "综合查询",
             "expected_keywords": ["喘振", "裕度", "压气机"]},
            {"query": "涡轮盘的包容性试验如何进行", "category": "综合查询",
             "expected_keywords": ["涡轮盘", "包容性", "试验"]},
            {"query": "限寿件包括哪些部件", "category": "综合查询",
             "expected_keywords": ["限寿件", "轮盘", "叶片", "轴"]},
            {"query": "吸鸟试验的验收标准是什么", "category": "综合查询",
             "expected_keywords": ["吸鸟", "验收", "标准"]},
        ]

        result = {
            "status": "success",
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "tests": []
        }

        for i, test in enumerate(test_cases, 1):
            print(f"\n  测试 {i}/{len(test_cases)}: {test['query']}")
            try:
                resp = requests.post(
                    f"{self.api_base}/api/v1/query",
                    json={"query": test["query"], "top_k": 5},
                    timeout=30
                )

                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("answer", "")
                    citations = data.get("citations", [])

                    # 检查是否包含期望关键词
                    found_keywords = []
                    for kw in test["expected_keywords"]:
                        if kw in answer:
                            found_keywords.append(kw)

                    passed = len(found_keywords) >= len(test["expected_keywords"]) * 0.5

                    test_result = {
                        "query": test["query"],
                        "category": test["category"],
                        "passed": passed,
                        "answer": answer[:300] + "..." if len(answer) > 300 else answer,
                        "citations_count": len(citations),
                        "expected_keywords": test["expected_keywords"],
                        "found_keywords": found_keywords
                    }

                    if passed:
                        result["passed"] += 1
                        print(f"    通过 - 找到关键词: {found_keywords}")
                    else:
                        result["failed"] += 1
                        print(f"    失败 - 只找到关键词: {found_keywords}")

                    result["tests"].append(test_result)

                else:
                    result["failed"] += 1
                    print(f"    错误 - HTTP {resp.status_code}")
                    result["tests"].append({
                        "query": test["query"],
                        "category": test["category"],
                        "passed": False,
                        "error": f"HTTP {resp.status_code}"
                    })

            except Exception as e:
                result["failed"] += 1
                print(f"    异常: {e}")
                result["tests"].append({
                    "query": test["query"],
                    "category": test["category"],
                    "passed": False,
                    "error": str(e)
                })

        print(f"\n  检索测试: {result['passed']}/{result['total_tests']} 通过")

        self.results["tests"]["retrieval"] = result
        return result

    def generate_report(self) -> str:
        """生成测试报告"""
        print("\n" + "="*60)
        print("5. 生成测试报告")
        print("="*60)

        report_lines = [
            "# CCAR-33-R2 知识库质量测试报告",
            "",
            f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**测试人**: Claude (AI Assistant)",
            "",
            "---",
            "",
            "## 1. 测试概览",
            ""
        ]

        # 测试概览
        for test_name, test_result in self.results.get("tests", {}).items():
            status = test_result.get("status", "unknown")
            status_icon = "通过" if status == "success" else "失败"
            report_lines.append(f"- **{test_name}**: {status_icon}")

        report_lines.extend(["", "---", ""])

        # ChromaDB详情
        if "chromadb" in self.results.get("tests", {}):
            chroma_result = self.results["tests"]["chromadb"]
            report_lines.extend([
                "## 2. 向量库测试结果 (ChromaDB)",
                "",
                f"- **集合数量**: {chroma_result.get('total_collections', 0)}",
                f"- **总Chunk数**: {chroma_result.get('total_chunks', 0)}",
                "",
                "### 2.1 集合列表"
            ])

            for col in chroma_result.get("collections", []):
                report_lines.append(f"- `{col['name']}`: {col['count']} chunks")

            report_lines.extend(["", "### 2.2 章节覆盖"])

            for ch, cnt in sorted(chroma_result.get("chapter_coverage", {}).items()):
                report_lines.append(f"- **{ch}**: {cnt} chunks")

            report_lines.extend(["", "### 2.3 条款覆盖"])
            report_lines.append(f"- 已覆盖条款数: **{len(chroma_result.get('section_coverage', {}))}**")

            report_lines.extend(["", "---", ""])

        # Neo4j详情
        if "neo4j" in self.results.get("tests", {}):
            neo4j_result = self.results["tests"]["neo4j"]
            report_lines.extend([
                "## 3. 图数据库测试结果 (Neo4j)",
                "",
                f"- **总节点数**: {neo4j_result.get('total_nodes', 0)}",
                f"- **总关系数**: {neo4j_result.get('total_relationships', 0)}",
                "",
                "### 3.1 节点类型"
            ])

            for label, count in sorted(neo4j_result.get("node_types", {}).items()):
                report_lines.append(f"- **{label}**: {count}")

            report_lines.extend(["", "### 3.2 关系类型"])

            for rel_type, count in sorted(neo4j_result.get("relationship_types", {}).items()):
                report_lines.append(f"- **{rel_type}**: {count}")

            report_lines.extend(["", "### 3.3 条款节点"])
            sections = neo4j_result.get("sections", [])
            report_lines.append(f"- 条款节点数: **{len(sections)}**")

            if sections:
                report_lines.append("\n部分条款列表:")
                for s in sections[:10]:
                    report_lines.append(f"  - {s.get('number', '')}: {s.get('title', '')}")

            report_lines.extend(["", "---", ""])

        # API测试详情
        if "api" in self.results.get("tests", {}):
            api_result = self.results["tests"]["api"]
            report_lines.extend([
                "## 4. API服务测试结果",
                ""
            ])

            for endpoint, data in api_result.get("endpoints", {}).items():
                status_code = data.get("status_code", 0)
                status = "OK" if status_code == 200 else "FAIL"
                report_lines.append(f"- **{endpoint}**: {status} (HTTP {status_code})")

            report_lines.extend(["", "---", ""])

        # 检索测试详情
        if "retrieval" in self.results.get("tests", {}):
            retrieval_result = self.results["tests"]["retrieval"]
            report_lines.extend([
                "## 5. 检索准确性测试结果",
                "",
                f"- **总测试数**: {retrieval_result.get('total_tests', 0)}",
                f"- **通过数**: {retrieval_result.get('passed', 0)}",
                f"- **失败数**: {retrieval_result.get('failed', 0)}",
                f"- **通过率**: **{retrieval_result.get('passed', 0) / max(retrieval_result.get('total_tests', 1), 1) * 100:.1f}%**",
                "",
                "### 5.1 详细测试结果"
            ])

            # 按类别分组
            by_category = {}
            for test in retrieval_result.get("tests", []):
                cat = test.get("category", "其他")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(test)

            for category, tests in by_category.items():
                passed = sum(1 for t in tests if t.get("passed", False))
                total = len(tests)
                report_lines.append(f"\n#### {category} ({passed}/{total})")

                for test in tests:
                    status = "通过" if test.get("passed", False) else "失败"
                    report_lines.append(f"\n- **{test['query']}**: {status}")

                    if "answer" in test:
                        report_lines.append(f"  - 回答: {test['answer'][:100]}...")

                    keywords = test.get("found_keywords", [])
                    expected = test.get("expected_keywords", [])
                    report_lines.append(f"  - 关键词: {keywords} / {expected}")

            report_lines.extend(["", "---", ""])

        # 结论
        report_lines.extend([
            "## 6. 测试结论",
            "",
            "### 6.1 总体评估",
            ""
        ])

        # 计算总体评分
        scores = []
        if "chromadb" in self.results.get("tests", {}):
            chroma = self.results["tests"]["chromadb"]
            if chroma.get("status") == "success":
                scores.append("向量库: 通过")
            else:
                scores.append("向量库: 失败")

        if "neo4j" in self.results.get("tests", {}):
            neo4j = self.results["tests"]["neo4j"]
            if neo4j.get("status") == "success":
                scores.append("图数据库: 通过")
            else:
                scores.append("图数据库: 失败")

        if "api" in self.results.get("tests", {}):
            api = self.results["tests"]["api"]
            if api.get("status") == "success":
                scores.append("API服务: 通过")
            else:
                scores.append("API服务: 失败")

        if "retrieval" in self.results.get("tests", {}):
            retrieval = self.results["tests"]["retrieval"]
            pass_rate = retrieval.get("passed", 0) / max(retrieval.get("total_tests", 1), 1)
            scores.append(f"检索准确率: {pass_rate*100:.1f}%")

        for score in scores:
            report_lines.append(f"- {score}")

        report_lines.extend([
            "",
            "### 6.2 建议",
            "",
            "1. **数据完整性**: 确保所有8章和64条条款都已完整录入",
            "2. **图谱完善**: 补充缺失的节点和关系",
            "3. **查询优化**: 根据测试结果优化检索策略",
            "4. **API稳定性**: 确保API服务稳定运行",
            "",
            "---",
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(report_lines)


def main():
    """主函数"""
    tester = KnowledgeBaseTester()

    print("="*60)
    print("CCAR-33-R2 知识库质量测试")
    print("="*60)

    # 运行各项测试
    tester.test_chromadb()
    tester.test_neo4j()
    tester.test_api()
    tester.run_retrieval_tests()

    # 生成并保存报告
    report = tester.generate_report()

    # 确保输出目录存在
    output_dir = Path("D:/AIAeroPlaneRag/evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "CCAR-33_R2_test_report.md"
    output_path.write_text(report, encoding="utf-8")

    print(f"\n报告已保存至: {output_path}")

    # 同时保存JSON格式的详细结果
    json_path = output_dir / "CCAR-33_R2_test_results.json"
    json_path.write_text(
        json.dumps(tester.results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"详细结果已保存至: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
