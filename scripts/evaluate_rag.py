import json
from pathlib import Path

from core.database import create_rag_evaluation
from core.rag_engine import retrieve_policy_context


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "evals" / "rag_eval.jsonl"


def score_case(context: str, sources: list[str], expected_keywords: list[str]) -> dict:
    matched_keywords = [keyword for keyword in expected_keywords if keyword in context]
    keyword_coverage = len(matched_keywords) / max(len(expected_keywords), 1)
    citation_count = len(sources)
    passed = bool(context) and keyword_coverage >= 0.5 and citation_count > 0
    return {
        "passed": passed,
        "matched_keywords": matched_keywords,
        "keyword_coverage": keyword_coverage,
        "citation_count": citation_count,
        "context_chars": len(context),
    }


def evaluate() -> int:
    total = 0
    passed = 0

    for line in DATASET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        item = json.loads(line)
        context, sources = retrieve_policy_context(item["question"])
        expected_keywords = item.get("expected_keywords", [])
        metrics = score_case(context, sources, expected_keywords)
        ok = metrics["passed"]
        passed += int(ok)
        create_rag_evaluation(
            question=item["question"],
            expected_keywords=",".join(expected_keywords),
            retrieved_sources=",".join(sources),
            passed=ok,
        )
        print(
            f"[{'PASS' if ok else 'FAIL'}] {item['question']} "
            f"coverage={metrics['keyword_coverage']:.0%} "
            f"citations={metrics['citation_count']} "
            f"chars={metrics['context_chars']} -> {sources}"
        )

    print(f"RAG eval: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(evaluate())
