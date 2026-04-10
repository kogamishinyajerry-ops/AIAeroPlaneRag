#!/usr/bin/env python3
"""
增强元数据提取器

为检索结果补充完整的元数据，提升可用性评分
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedMetadataExtractor:
    """增强元数据提取器"""

    def __init__(self, processed_dir: str):
        self.processed_dir = Path(processed_dir)
        self.metadata_cache = {}

        # 文档版本映射
        self.document_versions = {
            "CCAR-33-R2": "R2",
            "CCAR-25-R4": "R4",
            "CCAR-29-R2": "R2",
            "CCAR-23": "最新",
            "CCAR-36": "最新",
            "CCAR-91": "最新",
            "CCAR-93TM-R2": "R2",
            "FAR-33": "最新",
            "FAR-25": "最新",
            "CS-E": "最新",
            "CS-25": "最新"
        }

        # 文档类型映射
        self.document_types = {
            "CCAR-33-R2": "core_regulations",
            "CCAR-25-R4": "core_regulations",
            "CCAR-29-R2": "core_regulations",
            "CCAR-23": "core_regulations",
            "CCAR-36": "certification_guidance",
            "CCAR-91": "certification_guidance",
            "CCAR-93TM-R2": "certification_guidance",
            "FAR-33": "core_regulations",
            "FAR-25": "core_regulations",
            "CS-E": "core_regulations",
            "CS-25": "core_regulations"
        }

        # 机构映射
        self.agencies = {
            "CCAR": "CAAC",
            "FAR": "FAA",
            "CS": "EASA",
            "EASA": "EASA"
        }

    def enhance_search_result(self, result: Dict) -> Dict[str, Any]:
        """增强单个搜索结果的元数据"""

        metadata = result.get("metadata", {})
        text = result.get("text", "")
        original_text = result.get("original_text", "")

        # 提取章节信息
        chapter, section = self._extract_chapter_section(metadata)

        # 获取文档信息
        doc_name = metadata.get("source", "")
        agency = self._get_agency(doc_name)

        # 构建增强的元数据
        enhanced_metadata = {
            # 保留原有字段
            "node_id": metadata.get("node_id"),
            "title": metadata.get("title"),
            "page": metadata.get("page", 0),
            "score": metadata.get("score", 0),
            "source": doc_name,

            # 新增字段
            "document_id": self._generate_document_id(doc_name),
            "document_version": self.document_versions.get(doc_name, "unknown"),
            "document_type": self.document_types.get(doc_name, "unknown"),
            "agency": agency,

            # 章节信息
            "chapter": chapter,
            "section": section,
            "chapter_section": f"{chapter} > {section}" if chapter and section else section,

            # 文档路径
            "source_path": self._get_source_path(doc_name),

            # 内容分析
            "content_length": len(text),
            "has_requirements": self._has_requirements(text),
            "content_mode": metadata.get("search_method", "unknown"),

            # 时间戳
            "extracted_at": datetime.now().isoformat()
        }

        # 如果原始文本存在，提取更多上下文
        if original_text:
            enhanced_metadata["original_text_length"] = len(original_text)
            enhanced_metadata["original_text_preview"] = original_text[:200] + "..." if len(original_text) > 200 else original_text

        result["metadata"] = enhanced_metadata
        return result

    def _extract_chapter_section(self, metadata: Dict) -> tuple:
        """从标题中提取章节信息"""

        title = metadata.get("title", "")

        # 提取章节号
        chapter_match = re.search(r'([A-Z])[章章]+', title)
        chapter = chapter_match.group(1) + "章" if chapter_match else ""

        # 提取条款号
        section = ""
        patterns = [
            r'第\s*([\d.]+)\s*条',
            r'§\s*([\d.]+)',
            r'(\d+\.\d+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                section = match.group(1)
                break

        # 如果没有明确的章节，尝试从标题推断
        if not chapter:
            if "总则" in title or "General" in title:
                chapter = "A章"
            elif "性能" in title or "Performance" in title:
                chapter = "性能"
            elif "设计与构造" in title or "Design" in title:
                chapter = "设计"

        return chapter, section

    def _get_agency(self, doc_name: str) -> str:
        """获取颁发机构"""
        for prefix, agency in self.agencies.items():
            if doc_name.startswith(prefix):
                return agency
        return "UNKNOWN"

    def _generate_document_id(self, doc_name: str) -> str:
        """生成文档ID"""
        # 使用标准化格式
        doc_id = doc_name.lower().replace("-", "_").replace(".", "_")
        return f"doc_{doc_id}"

    def _get_source_path(self, doc_name: str) -> str:
        """获取文档源路径"""
        # 检查原始文档路径
        raw_dir = self.processed_dir.parent / "data" / "raw"
        if raw_dir.exists():
            # 查找可能的源文件
            for ext in [".pdf", ".md", ".docx"]:
                possible_file = raw_dir / f"{doc_name}{ext}"
                if possible_file.exists():
                    return str(possible_file)

        # 返回结构文件路径作为备选
        structure_file = self.processed_dir / f"{doc_name}_structure.json"
        if structure_file.exists():
            return str(structure_file)

        return f"data/processed/{doc_name}_structure.json"

    def _has_requirements(self, text: str) -> bool:
        """检查是否包含要求性语言"""
        requirement_keywords = [
            "必须", "应当", "应该", "要求", "不得", "需",
            "shall", "must", "should", "require", "need"
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in requirement_keywords)

    def enhance_batch_results(self, results: List[Dict]) -> List[Dict]:
        """批量增强搜索结果"""

        enhanced = []
        for result in results:
            try:
                enhanced.append(self.enhance_search_result(result))
            except Exception as e:
                logger.warning(f"Failed to enhance result: {e}")
                enhanced.append(result)  # 保留原结果

        logger.info(f"Enhanced {len(enhanced)} results with metadata")
        return enhanced

    def generate_citation_info(self, result: Dict) -> Dict[str, str]:
        """生成引用信息"""

        metadata = result.get("metadata", {})
        doc_name = metadata.get("source", "")
        title = metadata.get("title", "")
        page = metadata.get("page", 0)
        section = metadata.get("section", "")
        document_version = metadata.get("document_version", "")

        citation = {
            "standard": doc_name,
            "version": document_version,
            "section": section,
            "title": title,
            "page": page,
            "full_citation": f"{doc_name} {document_version} 第{section}条",
            "short_citation": f"{doc_name} §{section}",
            "url": self._generate_citation_url(doc_name, section, page)
        }

        return citation

    def _generate_citation_url(self, doc_name: str, section: str, page: int) -> str:
        """生成引用URL（指向在线规章）"""

        # 构建在线规章URL
        ccar_urls = {
            "CCAR-33-R2": "https://www.caac.gov.cn/XXGK/XXGK/CCAR-33R2.html",
            "CCAR-25-R4": "https://www.caac.gov.cn/XXGK/XXGK/CCAR-25R4.html",
            "CCAR-29-R2": "https://www.caac.gov.cn/XXGK/XXGK/CCAR-29R2.html"
        }

        base_url = ccar_urls.get(doc_name, "")
        if base_url and section:
            # 添加锚点到具体条款
            return f"{base_url}#section-{section.replace('.', '_')}"

        return base_url

    def extract_compliance_context(self, result: Dict) -> Dict[str, Any]:
        """提取符合性上下文"""

        metadata = result.get("metadata", {})
        text = result.get("text", "")
        original_text = result.get("original_text", "")
        content = original_text or text

        context = {
            "has_test_requirements": False,
            "has_design_requirements": False,
            "has_documentation_requirements": False,
            "requires_analysis": False,
            "requires_test": False,
            "requires_certification": False,
            "keywords_found": []
        }

        # 检测不同类型的要求
        test_keywords = ["试验", "测试", "test", "台架", "持久试车", "校准", "验证"]
        design_keywords = ["设计", "构造", "安装", "材料", "强度", "温度", "压力"]
        doc_keywords = ["文件", "记录", "标识", "说明", "手册"]

        for keyword in test_keywords:
            if keyword.lower() in content.lower():
                context["has_test_requirements"] = True
                context["requires_test"] = True
                context["keywords_found"].append(keyword)
                break

        for keyword in design_keywords:
            if keyword.lower() in content.lower():
                context["has_design_requirements"] = True
                context["keywords_found"].append(keyword)
                break

        for keyword in doc_keywords:
            if keyword.lower() in content.lower():
                context["has_documentation_requirements"] = True
                context["keywords_found"].append(keyword)
                break

        # 检测分析需求
        analysis_keywords = ["分析", "计算", "评定", "评估"]
        for keyword in analysis_keywords:
            if keyword.lower() in content.lower():
                context["requires_analysis"] = True
                break

        return context


__all__ = ['EnhancedMetadataExtractor']
