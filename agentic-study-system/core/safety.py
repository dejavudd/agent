"""Safety and hallucination guardrails for generated tutoring content."""
from __future__ import annotations

import re
from dataclasses import dataclass


SENSITIVE_PATTERNS = [
    r"\b(password|api[_ -]?key|secret token|private key)\b",
    r"\b身份证|银行卡|手机号|家庭住址\b",
    r"\b爆炸物|自残|自杀|诈骗|木马|后门\b",
]


@dataclass
class SafetyResult:
    ok: bool
    issues: list[str]

    def to_dict(self) -> dict:
        return {"ok": self.ok, "issues": self.issues}


def check_text(text: str, *, context: str = "") -> SafetyResult:
    issues: list[str] = []
    lower = text.lower()
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            issues.append(f"Potential sensitive or unsafe content matched: {pattern}")
    if _looks_like_unattributed_claim(text, context):
        issues.append(
            "Answer contains numeric or citation-like claims that are not clearly grounded in the supplied context."
        )
    return SafetyResult(ok=not issues, issues=issues)


def build_safety_notice(result: SafetyResult) -> str:
    if result.ok:
        return ""
    lines = [
        "> Safety review warning: this response may need verification before use.",
        "",
    ]
    lines += [f"- {issue}" for issue in result.issues]
    return "\n".join(lines).strip()


def _looks_like_unattributed_claim(text: str, context: str) -> bool:
    if not text.strip() or not context.strip():
        return False
    if re.search(r"\[\d+\]", text):
        return False
    numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    if not numbers:
        return False
    context_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", context))
    has_unsupported_number = any(number not in context_numbers for number in numbers)
    has_source_words = any(word in text.lower() for word in ("according to", "source", "from the material"))
    return has_unsupported_number and not has_source_words

