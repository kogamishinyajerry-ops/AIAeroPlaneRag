from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_step(name: str, command: list[str]) -> None:
    print(f"[quality-gate] Running {name}: {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT_DIR, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def summarize_golden_set(path: Path) -> None:
    output = subprocess.check_output(
        [PYTHON, "evaluation/evaluate_golden_set.py", "--golden-set", str(path)],
        cwd=ROOT_DIR,
        text=True,
    )
    payload = json.loads(output)
    summary = payload["summary"]
    print("[quality-gate] Golden set summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    run_step("py_compile", [PYTHON, "-m", "py_compile", "src/main.py", "src/ontology/graph_store.py"])
    run_step("pytest", [PYTHON, "-m", "pytest", "tests", "-q"])
    summarize_golden_set(ROOT_DIR / "evaluation" / "golden_set_sample.json")
    print("[quality-gate] All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
