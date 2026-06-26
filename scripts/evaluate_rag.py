import json
from pathlib import Path

from core.database import create_rag_evaluation
from core.security import EMAIL_RE, ID_CARD_RE, PHONE_RE


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "evals" / "rag_eval.jsonl"


def score_case(
    context: str,
    sources: list[str],
    expected_keywords: list[str],
    expected_sources: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
) -> dict:
    expected_sources = expected_sources or []
    forbidden_terms = forbidden_terms or []
    matched_keywords = [keyword for keyword in expected_keywords if keyword in context]
    keyword_coverage = len(matched_keywords) / max(len(expected_keywords), 1)
    citation_count = len(sources)
    matched_sources = [source for source in expected_sources if any(source in actual for actual in sources)]
    citation_correctness = len(matched_sources) / max(len(expected_sources), 1) if expected_sources else 1.0
    pii_leakage = bool(PHONE_RE.search(context) or EMAIL_RE.search(context) or ID_CARD_RE.search(context))
    forbidden_hits = [term for term in forbidden_terms if term in context]
    passed = (
        bool(context)
        and keyword_coverage >= 0.5
        and citation_count > 0
        and citation_correctness >= 0.8
        and not pii_leakage
        and not forbidden_hits
    )
    return {
        "passed": passed,
        "matched_keywords": matched_keywords,
        "keyword_coverage": keyword_coverage,
        "citation_count": citation_count,
        "citation_correctness": citation_correctness,
        "matched_sources": matched_sources,
        "pii_leakage": pii_leakage,
        "forbidden_hits": forbidden_hits,
        "context_chars": len(context),
    }


def evaluate() -> int:
    from core.rag_engine import retrieve_policy_context

    total = 0
    passed = 0

    for line in DATASET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        item = json.loads(line)
        context, sources = retrieve_policy_context(item["question"])
        expected_keywords = item.get("expected_keywords", [])
        metrics = score_case(
            context,
            sources,
            expected_keywords,
            expected_sources=item.get("expected_sources", []),
            forbidden_terms=item.get("forbidden_terms", []),
        )
        ok = metrics["passed"]
        passed += int(ok)
        create_rag_evaluation(
            question=item["question"],
            expected_keywords=",".join(expected_keywords),
            retrieved_sources=",".join(sources),
            passed=ok,
            metrics=metrics,
        )
        print(
            f"[{'PASS' if ok else 'FAIL'}] {item['question']} "
            f"coverage={metrics['keyword_coverage']:.0%} "
            f"citations={metrics['citation_count']} "
            f"citation_correctness={metrics['citation_correctness']:.0%} "
            f"pii_leakage={metrics['pii_leakage']} "
            f"forbidden_hits={len(metrics['forbidden_hits'])} "
            f"chars={metrics['context_chars']} -> {sources}"
        )

    print(f"RAG eval: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(evaluate())
