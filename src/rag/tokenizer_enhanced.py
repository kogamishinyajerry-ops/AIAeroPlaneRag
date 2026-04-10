#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型检索分词器
优化策略：
1. 停用词过滤
2. 专业术语整体匹配
3. 英文复合词智能拆分
4. 词干提取
"""

import re
from typing import Set, List
from functools import lru_cache

class QueryTokenizer:
    def __init__(self):
        # 中文停用词表（高频无意义词）
        self.zh_stopwords = {
            '的', '了', '是', '在', '和', '与', '或', '但', '而', '对',
            '中', '上', '下', '内', '外', '前', '后', '有', '无', '不',
            '这', '那', '此', '其', '之', '个', '种', '等', '及', '以'
        }

        # 英文停用词表
        self.en_stopwords = {
            'the', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'on',
            'at', 'from', 'by', 'an', 'as', 'is', 'are', 'was', 'were'
        }

        # 航空专业术语词典（需整体匹配）
        self.technical_terms = {
            '喘振裕度', '失速速度', '起飞距离', '着陆距离', '爬升梯度',
            '巡航性能', '燃油消耗', '排气温度', '高压转子', '低压转子',
            '压气机', '涡轮叶片', '燃烧室', '喷管', '反推装置'
        }

        # 编译正则表达式提升性能
        self.chinese_char_re = re.compile(r'[\u4e00-\u9fff]+')
        self.english_token_re = re.compile(r'[a-zA-Z]+|\d+[\w.]*')
        self.identifier_split_re = re.compile(r'[-_./]')

    @lru_cache(maxsize=1024)
    def _is_technical_term(self, term: str) -> bool:
        """检查是否为专业术语"""
        return term in self.technical_terms

    def _split_compound_identifier(self, token: str) -> List[str]:
        """
        智能拆分英文复合标识符
        例: 'FAA_AC_33.27-1A' -> ['FAA', 'AC', '33', '27', '1A']
        """
        parts = []
        for segment in self.identifier_split_re.split(token):
            # 保留字母+数字组合（如'1A'），拆分纯数字和字母
            if segment:
                if segment.isalpha() or segment.isdigit():
                    parts.append(segment)
                else:
                    # 混合token按字母数字边界拆分
                    sub_parts = re.findall(r'[a-zA-Z]+|\d+[\w.]*', segment)
                    parts.extend(sub_parts)
        return parts if parts else [token]

    def _extract_english_tokens(self, query: str) -> Set[str]:
        """
        提取英文token（含智能拆分）
        优化点：
        1. 复合标识符拆分
        2. 小写归一化
        3. 停用词过滤
        """
        tokens = set()
        # 基础英文/数字token
        for token in re.split(r'[\s,，。？！]+', query):
            token = token.strip()
            if not token or any(c.isalpha() or c.isdigit() for c in token):
                # 尝试智能拆分
                split_parts = self._split_compound_identifier(token.lower())
                for part in split_parts:
                    if len(part) >= 2 and part not in self.en_stopwords:
                        tokens.add(part)
        return tokens

    def _extract_chinese_tokens(self, query: str) -> Set[str]:
        """
        提取中文token（含专业术语保护）
        策略：
        1. 优先匹配专业术语
        2. 未匹配部分采用2-gram（不用3/4-gram减少误匹配）
        """
        tokens = set()
        chinese_segments = self.chinese_char_re.findall(query)

        for seg in chinese_segments:
            # 优先匹配专业术语
            matched = False
            for term_len in range(4, 1, -1):  # 从长到短匹配
                for i in range(len(seg) - term_len + 1):
                    candidate = seg[i:i+term_len]
                    if self._is_technical_term(candidate):
                        tokens.add(candidate)
                        matched = True

            # 未匹配部分使用2-gram
            if not matched:
                for i in range(len(seg) - 1):
                    gram = seg[i:i+2]
                    if gram not in self.zh_stopwords:
                        tokens.add(gram)

            # 添加单字（仅作为兜底）
            for char in seg:
                if char not in self.zh_stopwords:
                    tokens.add(char)

        return tokens

    def tokenize(self, query: str) -> Set[str]:
        """
        主分词函数
        返回: {token1, token2, ...}
        """
        tokens = set()

        # 英文token
        tokens.update(self._extract_english_tokens(query))

        # 中文token
        tokens.update(self._extract_chinese_tokens(query))

        return tokens


# === 原始分词器（用于对比） ===
def _tokenize_query_original(q):
    """原始实现"""
    tokens = set()
    # 英文/数字 token
    for t in re.split(r'[\s,，。？！]+', q):
        t = t.strip()
        if len(t) >= 2:
            tokens.add(t)
    # 中文 ngram (2-4字)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', q)
    for seg in chinese_chars:
        for n in range(2, min(5, len(seg) + 1)):
            for i in range(len(seg) - n + 1):
                tokens.add(seg[i:i+n])
    return tokens


# === 便捷函数 ===
def tokenize_query(query: str) -> Set[str]:
    """
    增强型分词器（推荐使用）
    """
    tokenizer = QueryTokenizer()
    return tokenizer.tokenize(query)


if __name__ == '__main__':
    # 测试用例
    test_cases = [
        "压气机喘振裕度",
        "FAA_AC_33.27-1A compressor stall",
        "发动机排气温度EGT限制",
        "飞机失速速度计算",
        "the compressor stall margin in takeoff"
    ]

    tokenizer = QueryTokenizer()

    print("=== 分词效果对比 ===")
    for query in test_cases:
        original = _tokenize_query_original(query)
        enhanced = tokenizer.tokenize(query)

        print(f"\n查询: {query}")
        print(f"原始 ({len(original)}个): {sorted(original)}")
        print(f"增强 ({len(enhanced)}个): {sorted(enhanced)}")
        print(f"减少: {len(original) - len(enhanced)}个token")
