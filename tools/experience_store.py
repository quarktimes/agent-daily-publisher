"""
Experience Store — Self-evolution for the Write Agent.

Records every article generation attempt with its Judge score and feedback.
Before each new article, queries past high-scoring examples to inject as
few-shot context into the Write Agent's prompt.

This is the "memory" layer that allows the system to improve over time —
the more articles it generates, the better context it has for what "good" looks like.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExperienceStore:
    """Records and retrieves article generation experiences."""

    def __init__(self, store_dir: str | None = None):
        self.store_dir = store_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "experience"
        )
        Path(self.store_dir).mkdir(parents=True, exist_ok=True)
        self._cache: list[dict] | None = None

    def record(
        self,
        date: str,
        tags: list[str],
        score: int,
        dimensions: dict,
        feedback: list[str],
        verdict: str,
        article_title: str,
        article_snippet: str,
        iteration: int = 1,
    ):
        """Record a single article generation attempt."""
        entry = {
            "date": date,
            "timestamp": datetime.now().isoformat(),
            "tags": tags,
            "score": score,
            "dimensions": dimensions,
            "feedback": feedback,
            "verdict": verdict,
            "article_title": article_title,
            "article_snippet": article_snippet[:500],  # Store first 500 chars
            "iteration": iteration,
            "passed": verdict == "pass" and score >= 80,
        }
        filepath = os.path.join(self.store_dir, "experience.jsonl")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._cache = None  # Invalidate cache
        logger.debug(f"Experience recorded: score={score}, tags={tags}")

    def get_best_examples(self, top_n: int = 3, min_score: int = 85) -> list[dict]:
        """Get the highest-scoring articles as few-shot examples."""
        history = self._load_all()
        passed = [h for h in history if h.get("score", 0) >= min_score]
        passed.sort(key=lambda h: h["score"], reverse=True)
        return passed[:top_n]

    def get_failure_patterns(self, top_n: int = 3) -> list[str]:
        """Get common feedback patterns from low-scoring articles."""
        history = self._load_all()
        failed = [h for h in history if h.get("score", 0) < 80]
        feedback_items = []
        for f in failed:
            feedback_items.extend(f.get("feedback", []))
        # Find most common feedback patterns
        from collections import Counter
        common = Counter(feedback_items).most_common(top_n)
        return [item for item, count in common]

    def get_recent_improvement(self, n: int = 5) -> str | None:
        """Get the trend — are scores improving over time?"""
        history = self._load_all()
        if len(history) < 3:
            return None
        recent = history[-n:]
        scores = [h.get("score", 0) for h in recent]
        avg = sum(scores) / len(scores)
        if len(scores) >= 2:
            trend = scores[-1] - scores[0]
            if trend > 5:
                return f"upward (last {n} avg: {avg:.0f}, +{trend} pts)"
            elif trend < -5:
                return f"downward (last {n} avg: {avg:.0f}, {trend} pts)"
            else:
                return f"stable (last {n} avg: {avg:.0f})"
        return None

    def get_context_for_writer(self) -> str:
        """Build a context string for the Write Agent's system prompt.

        Includes:
          - Recent score trend
          - Top-performing article patterns
          - Common failure patterns to avoid
        """
        parts = []

        # Score trend
        trend = self.get_recent_improvement()
        if trend:
            parts.append(f"📈 Generation quality trend: {trend}")

        # Best examples
        best = self.get_best_examples(top_n=2, min_score=85)
        if best:
            parts.append("\n🏆 Previous high-scoring articles (reference patterns):")
            for i, b in enumerate(best, 1):
                dims = b.get("dimensions", {})
                dim_str = ", ".join(f"{k}={v}" for k, v in dims.items())
                parts.append(f"  {i}. [{b['date']}] Score={b['score']} ({dim_str})")
                parts.append(f"     Title: {b['article_title']}")
                if b.get("feedback"):
                    parts.append(f"     What worked: {'; '.join(b['feedback'][:2])}")

        # Failure patterns
        failures = self.get_failure_patterns(top_n=3)
        if failures:
            parts.append("\n⚠️  Common issues from low-scoring articles (avoid these):")
            for f in failures:
                parts.append(f"  - {f}")

        context = "\n".join(parts)
        return context

    def _load_all(self) -> list[dict]:
        """Load all experiences from disk."""
        if self._cache is not None:
            return self._cache

        filepath = os.path.join(self.store_dir, "experience.jsonl")
        if not os.path.exists(filepath):
            self._cache = []
            return self._cache

        entries = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        self._cache = entries
        return entries
