#!/usr/bin/env bash
# =============================================================================
# scripts/run_all_benchmarks.sh
# AeroPower-RAG 回归基准一键运行脚本
# =============================================================================
# 用途: 在本地或 CI 中运行所有基准测试并生成汇总 JSON 报告
#
# 运行:
#   bash scripts/run_all_benchmarks.sh
#   bash scripts/run_all_benchmarks.sh --unit-only        # 仅单元测试
#   bash scripts/run_all_benchmarks.sh --benchmarks-only  # 仅基准测试
#
# 输出:
#   benchmarks/summary_report.json   — 汇总报告
#   Exit 0 = 全部通过; Exit 1 = 有失败
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── 参数解析 ──────────────────────────────────────────────────────────────────
RUN_UNIT=true
RUN_BENCHMARKS=true

for arg in "$@"; do
  case $arg in
    --unit-only)        RUN_BENCHMARKS=false ;;
    --benchmarks-only)  RUN_UNIT=false ;;
    --help|-h)
      echo "Usage: $0 [--unit-only | --benchmarks-only]"
      exit 0
      ;;
  esac
done

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${BLUE}ℹ  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠  $*${NC}"; }

SUMMARY_FILE="$REPO_ROOT/benchmarks/summary_report.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OVERALL_PASS=true
RESULTS=()

echo "============================================================"
echo "  AeroPower-RAG 回归基准  |  $(date)"
echo "============================================================"

# ── 辅助: 记录结果 ───────────────────────────────────────────────────────────
record() {
  local name="$1" passed="$2" detail="${3:-}"
  RESULTS+=("{\"name\":\"$name\",\"passed\":$passed,\"detail\":\"$detail\"}")
  if [ "$passed" = "true" ]; then
    ok "$name"
  else
    fail "$name"
    OVERALL_PASS=false
  fi
}

# ── 1. 单元测试 (pytest) ──────────────────────────────────────────────────────
if [ "$RUN_UNIT" = "true" ]; then
  echo ""
  echo "── 1. 单元测试 (pytest tests/unit/) ────────────────────────"

  if python3 -m pytest tests/unit/ -v --tb=short -q \
      --ignore=tests/unit/test_graph_virtualization.js \
      2>&1 | tee /tmp/pytest_unit.log; then
    UNIT_COUNT=$(grep -c "PASSED\|passed" /tmp/pytest_unit.log 2>/dev/null || echo "?")
    record "unit_tests_python" "true" "${UNIT_COUNT} passed"
  else
    FAIL_COUNT=$(grep -c "FAILED\|failed" /tmp/pytest_unit.log 2>/dev/null || echo "?")
    record "unit_tests_python" "false" "${FAIL_COUNT} failed — see /tmp/pytest_unit.log"
  fi

  # JS 单元测试 (Node)
  if command -v node >/dev/null 2>&1; then
    if node tests/unit/test_graph_virtualization.js 2>&1 | tee /tmp/node_unit.log; then
      JS_PASS=$(grep -c "PASS\|passed\|ok" /tmp/node_unit.log 2>/dev/null || echo "?")
      record "unit_tests_js" "true" "${JS_PASS} JS tests passed"
    else
      record "unit_tests_js" "false" "JS tests failed — see /tmp/node_unit.log"
    fi
  else
    warn "node not found — skipping JS unit tests"
    record "unit_tests_js" "true" "skipped (node not available)"
  fi
fi

# ── 2. 中英混合 BM25 基准 ─────────────────────────────────────────────────────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 2. 中英混合 BM25 基准 (T5.3) ────────────────────────────"

  if PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 benchmarks/multilingual_mixed_bench.py 2>&1 | tee /tmp/multilingual_bench.log; then
    RECALL=$(grep "recall@3:" /tmp/multilingual_bench.log | grep -oP '\d+\.\d+%' | head -1 || echo "?")
    record "multilingual_mixed_recall3" "true" "recall@3=${RECALL}"
  else
    record "multilingual_mixed_recall3" "false" "recall@3 below threshold (0.60)"
  fi
fi

# ── 2b. 性能基准 (BM25 P95 + Golden Set recall@3) ────────────────────────────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 2b. 性能基准 (BM25 P95 + Golden Set recall@3) ───────────"

  if PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 benchmarks/performance_bench.py 2>&1 | tee /tmp/performance_bench.log; then
    P95=$(grep -oP 'P95=\K[\d.]+ms' /tmp/performance_bench.log | head -1 || echo "?")
    RECALL=$(grep -oP 'recall@3=\K[\d.]+%' /tmp/performance_bench.log | head -1 || echo "?")
    record "performance_bm25_p95" "true" "P95=${P95} recall@3=${RECALL}"
  else
    record "performance_bm25_p95" "false" "see /tmp/performance_bench.log"
  fi
fi

# ── 2c. 黄金集 BM25 recall 自动评估 (30题, recall@3≥70%, recall@5≥80%) ──────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 2c. 黄金集 BM25 recall@30 (T3.1) ────────────────────────"

  if PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" python3 benchmarks/golden_set_bm25_bench.py \
      --output /tmp/golden_set_bench_result.json \
      2>&1 | tee /tmp/golden_set_bench.log; then
    RECALL3=$(python3 -c "import json; d=json.load(open('/tmp/golden_set_bench_result.json')); print(f\"{d['keyword_recall_at_3']:.1%}\")" 2>/dev/null || grep -oP 'Keyword recall@3:\s+\K[\d.]+%' /tmp/golden_set_bench.log | head -1 || echo "?")
    RECALL5=$(python3 -c "import json; d=json.load(open('/tmp/golden_set_bench_result.json')); print(f\"{d.get('keyword_recall_at_5',d.get('keyword_recall_at_5',0)):.1%}\")" 2>/dev/null || echo "?")
    record "golden_set_bm25_recall" "true" "recall@3=${RECALL3} recall@5=${RECALL5}"
  else
    record "golden_set_bm25_recall" "false" "below threshold — see /tmp/golden_set_bench.log"
  fi
fi

# ── 3. 块索引量验证 ───────────────────────────────────────────────────────────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 3. 块索引量验证 ──────────────────────────────────────────"

  CHUNK_COUNT=$(python3 -c "
import json
from pathlib import Path
d = Path('data/processed')
chunks = []
for f in sorted(d.glob('*_chunks.json')):
    chunks.extend(json.load(open(f)))
easa = d / 'easa_cse/chunks_full.json'
if easa.exists():
    chunks.extend(json.load(open(easa)))
print(len(chunks))
" 2>/dev/null || echo "0")

  if [ "$CHUNK_COUNT" -ge 500 ] 2>/dev/null; then
    record "chunk_index_volume" "true" "${CHUNK_COUNT} total chunks (>= 500)"
  else
    record "chunk_index_volume" "false" "${CHUNK_COUNT} total chunks (< 500 threshold)"
  fi
fi

# ── 4. PageIndex 节点覆盖率 ──────────────────────────────────────────────────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 4. PageIndex 叶节点覆盖率 ────────────────────────────────"

  LEAF_RESULT=$(python3 -c "
import json
from pathlib import Path

def flatten(nodes):
    result = []
    for n in nodes:
        result.append(n)
        result.extend(flatten(n.get('nodes', [])))
    return result

path = Path('data/processed/CCAR-33-R2_structure.json')
if not path.exists():
    print('0/0')
else:
    data = json.loads(path.read_text(encoding='utf-8'))
    nodes = flatten(data.get('structure', []))
    leaves = [n for n in nodes if not n.get('nodes')]
    with_text = sum(1 for n in leaves if n.get('text','').strip())
    print(f'{with_text}/{len(leaves)}')
" 2>/dev/null || echo "0/0")

  WITH_TEXT=$(echo "$LEAF_RESULT" | cut -d/ -f1)
  TOTAL_LEAF=$(echo "$LEAF_RESULT" | cut -d/ -f2)

  if [ "${WITH_TEXT:-0}" -ge 40 ] 2>/dev/null; then
    record "pageindex_leaf_coverage" "true" "${LEAF_RESULT} leaf nodes with text (>= 40)"
  else
    record "pageindex_leaf_coverage" "false" "${LEAF_RESULT} leaf nodes (< 40 threshold)"
  fi
fi

# ── 5. FAR-33 条款覆盖 ────────────────────────────────────────────────────────
if [ "$RUN_BENCHMARKS" = "true" ]; then
  echo ""
  echo "── 5. FAR-33 条款覆盖验证 ───────────────────────────────────"

  FAR33_COUNT=$(python3 -c "
import json
from pathlib import Path
f = Path('data/processed/FAR-33_chunks.json')
if f.exists():
    print(len(json.load(open(f))))
else:
    print(0)
" 2>/dev/null || echo "0")

  if [ "$FAR33_COUNT" -ge 60 ] 2>/dev/null; then
    record "far33_chunks" "true" "${FAR33_COUNT} FAR-33 chunks (>= 60)"
  else
    record "far33_chunks" "false" "${FAR33_COUNT} FAR-33 chunks (< 60 threshold)"
  fi
fi

# ── 汇总报告 ──────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  汇总"
echo "============================================================"

# 构建 JSON
RESULTS_JSON=$(IFS=','; echo "[${RESULTS[*]}]")
PASSED_COUNT=$(echo "$RESULTS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(sum(1 for r in data if r['passed']))
" 2>/dev/null || echo "?")
TOTAL_COUNT="${#RESULTS[@]}"

cat > "$SUMMARY_FILE" << JSONEOF
{
  "timestamp": "$TIMESTAMP",
  "overall_passed": $( [ "$OVERALL_PASS" = "true" ] && echo "true" || echo "false" ),
  "passed": $PASSED_COUNT,
  "total": $TOTAL_COUNT,
  "results": $RESULTS_JSON
}
JSONEOF

if [ "$OVERALL_PASS" = "true" ]; then
  ok "全部基准通过 ($PASSED_COUNT/$TOTAL_COUNT)"
  echo ""
  info "报告保存至: $SUMMARY_FILE"
  exit 0
else
  fail "部分基准未通过 ($PASSED_COUNT/$TOTAL_COUNT)"
  echo ""
  info "报告保存至: $SUMMARY_FILE"
  exit 1
fi
