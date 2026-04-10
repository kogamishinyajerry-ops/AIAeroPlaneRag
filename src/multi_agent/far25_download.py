#!/usr/bin/env python3
"""
FAA FAR Part 25 文档获取和处理
第一阶段：添加 FAR-25 (运输类飞机适航标准)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_agent import KnowledgeBaseExpander, print_expansion_status


async def phase1_far25_workflow():
    """
    第一阶段工作流程：FAR-25

    步骤：
    1. 获取 FAR-25 文档
    2. 解析和结构化
    3. Agent 质量检查
    4. 与 CCAR-25 对比验证
    5. 专家评审
    6. 通过后加入知识库
    """

    print("="*70)
    print("第一阶段：添加 FAA FAR-25")
    print("="*70)
    print()
    print("📋 FAR-25 信息:")
    print("   名称: Airworthiness Standards: Transport Category Airplanes")
    print("   机构: FAA (Federal Aviation Administration)")
    print("   对应: CCAR-25-R4 (便于对比验证)")
    print("   预计条款: ~350 条")
    print()
    print("📥 获取方式:")
    print("   1. 官方网站: https://www.ecfr.gov/current/title-14/chapter-I/part-25")
    print("   2. 下载为 PDF 或 TXT 格式")
    print("   3. 放入 data/raw/ 目录")
    print()

    # 初始化扩展器
    expander = KnowledgeBaseExpander('/Users/Zhuanz/AIAeroPlaneRag/data/processed')

    # 检查是否有文档
    print("="*70)
    print("步骤 1/6: 检查文档...")
    print("="*70)

    raw_dir = Path('/Users/Zhuanz/AIAeroPlaneRag/data/raw')

    # 检查可能的文件名
    possible_names = [
        'FAR-25.pdf',
        'far25.pdf',
        '14CFR25.pdf',
        'FAR25.txt',
        'part25.pdf'
    ]

    found_file = None
    for name in possible_names:
        file_path = raw_dir / name
        if file_path.exists():
            found_file = str(file_path)
            print(f"✅ 找到文档: {name}")
            break

    if not found_file:
        print("❌ 未找到 FAR-25 文档")
        print()
        print("📝 请按以下步骤操作:")
        print()
        print("   方法1 - 手动下载:")
        print("   1. 访问: https://www.ecfr.gov/current/title-14/chapter-I/part-25")
        print("   2. 点击 'PDF' 下载完整文档")
        print("   3. 保存为: data/raw/FAR-25.pdf")
        print()
        print("   方法2 - 使用 curl 下载:")
        print("   cd data/raw/")
        print("   curl -o FAR-25.pdf 'https://www.ecfr.gov/api/renderer/v1/content/title-14/chapter-I/part-25'")
        print()
        print("   下载完成后，运行:")
        print("   python3 -m multi_agent.phase1_far25_process")
        print()
        return {
            "status": "waiting_for_document",
            "message": "请先下载 FAR-25 文档"
        }

    # 如果找到文档，继续处理
    print()
    print("="*70)
    print("步骤 2/6: 解析文档...")
    print("="*70)

    # 这里应该调用解析器
    print(f"📄 正在解析: {found_file}")

    # 检查是否已有解析结果
    processed_dir = Path('/Users/Zhuanz/AIAeroPlaneRag/data/processed')
    structure_file = processed_dir / 'FAR-25_structure.json'

    if structure_file.exists():
        print(f"✅ 已存在解析结果")
    else:
        print(f"⏳ 需要解析...")
        print()
        print("运行解析命令:")
        print(f"  python3 -c \"")
        print(f"    import sys")
        print(f"    sys.path.insert(0, 'src')")
        print(f"    from ccar_robust_parser import EnhancedCCARParser")
        print(f"    parser = EnhancedCCARParser('{found_file}', use_ocr=False)")
        print(f"    parser.save('{processed_dir}/FAR-25_structure.json')")
        print(f"  \"")

    print()
    print("="*70)
    print("后续步骤...")
    print("="*70)
    print("3️⃣ Agent 质量检查")
    print("4️⃣ 与 CCAR-25 对比")
    print("5️⃣ 专家评审")
    print("6️⃣ 加入知识库")

    return {
        "status": "document_found",
        "file": found_file,
        "next_action": "parse_document"
    }


def show_download_instructions():
    """显示下载说明"""
    print()
    print("="*70)
    print("FAR-25 下载指南")
    print("="*70)
    print()
    print("🌐 FAA 官方来源:")
    print("   https://www.ecfr.gov/current/title-14/chapter-I/part-25")
    print()
    print("📥 直接下载链接:")
    print("   PDF: https://www.govinfo.gov/content/pkg/CFR-2024-title14-vol1/pdf/CFR-2024-title14-vol1-part25.pdf")
    print()
    print("💾 保存位置:")
    print("   /Users/Zhuanz/AIAeroPlaneRag/data/raw/FAR-25.pdf")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FAR-25 扩展工作流程")
    parser.add_argument("--download", action="store_true", help="显示下载说明")
    parser.add_argument("--status", action="store_true", help="查看扩展状态")

    args = parser.parse_args()

    if args.download:
        show_download_instructions()
    elif args.status:
        expander = KnowledgeBaseExpander('/Users/Zhuanz/AIAeroPlaneRag/data/processed')
        print_expansion_status(expander.get_expansion_status())
    else:
        asyncio.run(phase1_far25_workflow())
