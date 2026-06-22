from __future__ import annotations

from typing import List

from app.memory.schemas import L4ExperienceItem


class ExperienceStore:
    """P7 L4 read-only retrieval over knowledge and anonymized evaluation items."""

    def retrieve(self, query: str, *, limit: int = 3) -> List[L4ExperienceItem]:
        items = [
            L4ExperienceItem(
                item_id="p6-policy-boundary",
                item_type="knowledge",
                title="P6 approved safety boundary knowledge",
                metadata={"query_terms_present": bool(query), "source": "approved_knowledge_index"},
            ),
            L4ExperienceItem(
                item_id="synthetic-eval-negation",
                item_type="synthetic_eval_case",
                title="Synthetic negated risk eval pattern",
                metadata={"contains_real_patient_text": False},
            ),
        ]
        return items[: max(0, int(limit))]
