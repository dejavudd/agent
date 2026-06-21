"""Validation helpers for Chinese learning-resource generation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Sequence

Validator = Callable[[str], tuple[bool, str]]

_HANGUL = re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
_MOJIBAKE = re.compile(r"(鈥|鞚|頃|韱|氩||�)")
_GRADING_EN = re.compile(
    r"(?<![a-zA-Z])(correct|incorrect|wrong|right answer|that's correct|well done|good job)(?![a-zA-Z])",
    re.IGNORECASE,
)
_GRADING_ZH = re.compile(r"正确|错误|完全正确|答错了|打分|得分")
_EXAMPLE_HDR = re.compile(
    r"^#+.*(示例导入|案例导入|例题导入|worked example)",
    re.IGNORECASE | re.MULTILINE,
)
_RULES_HDR = re.compile(
    r"^#+.*(核心知识|概念解释|定义|原理|理论|abstract rule|definition|theory)",
    re.IGNORECASE | re.MULTILINE,
)

QUIZ_TYPES = {"mcq", "cloze", "short", "essay"}
_TIER_TO_COUNT = {
    "Beginner": "beginner",
    "Intermediate": "intermediate",
    "Interleaved": "interleaved",
    "Advanced": "essays",
}


@dataclass
class ValidationResult:
    ok: bool
    failures: list[str]


def run_validators(text: str, validators: Sequence[Validator]) -> ValidationResult:
    failures = [msg for v in validators for ok, msg in [v(text)] if not ok]
    return ValidationResult(ok=not failures, failures=failures)


def _strip_code_blocks(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def no_korean_or_mojibake(text: str) -> tuple[bool, str]:
    prose = _strip_code_blocks(text)
    if _HANGUL.search(prose) or _MOJIBAKE.search(prose):
        return False, (
            "语言要求违规：请只使用简体中文输出，不要包含韩文、乱码或无关外语。"
            "必要英文专业术语可以保留，但必须配中文解释。"
        )
    return True, ""


def has_mermaid_block(text: str) -> tuple[bool, str]:
    if re.search(r"```mermaid\b", text):
        return True, ""
    return False, "图文结合要求：请至少加入一个 ```mermaid 代码块，用图示表达知识结构或流程。"


def no_binary_grading(text: str) -> tuple[bool, str]:
    prose = _strip_code_blocks(text)
    hits = {m.group(0) for m in _GRADING_EN.finditer(prose)} | {m.group(0) for m in _GRADING_ZH.finditer(prose)}
    if hits:
        return False, (
            "学习诊断不要只给简单判定或分数，请改为分析学生思路、指出缺口并给出改进路径。"
            f"需要替换的表达：{sorted(hits)}"
        )
    return True, ""


def chinese_example_before_rules(text: str) -> tuple[bool, str]:
    ex = _EXAMPLE_HDR.search(text)
    if not ex:
        return False, "先例后理要求：请添加 `## 示例导入` 小节，并在抽象概念或定义之前给出完整例子。"
    rule = _RULES_HDR.search(text)
    if rule and rule.start() < ex.start():
        return False, "`## 示例导入` 必须出现在核心知识、定义或原理说明之前，请调整顺序。"
    return True, ""


def parse_quiz_json(text: str) -> dict | None:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.DOTALL)
    if fence:
        t = fence.group(1)
    else:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            t = t[start:end + 1]
    try:
        data = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def valid_quiz_json(expected: dict, interleave_enabled: bool) -> Validator:
    def _check(text: str) -> tuple[bool, str]:
        data = parse_quiz_json(text)
        if data is None:
            return False, '测评题库必须是一个合法 JSON 对象：{"week":..., "questions":[...]}。'
        questions = data.get("questions")
        if not isinstance(questions, list) or not questions:
            return False, 'JSON 中必须包含非空的 "questions" 数组。'

        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                return False, f"questions[{i}] 必须是 JSON 对象。"
            qtype = q.get("type")
            ident = q.get("id", i)
            if qtype not in QUIZ_TYPES:
                return False, f'questions[{i}].type 必须是 {sorted(QUIZ_TYPES)} 之一。'
            if not str(q.get("prompt", "")).strip():
                return False, f'题目 {ident} 缺少非空 "prompt"。'
            if qtype == "mcq" and (not q.get("options") or not str(q.get("answer", "")).strip()):
                return False, f'单选题 {ident} 需要 "options" 和正确答案 "answer"。'
            if qtype == "cloze" and not q.get("answers"):
                return False, f'填空题 {ident} 需要非空 "answers" 列表。'
            if qtype == "short" and not str(q.get("answer", "")).strip():
                return False, f'简答题 {ident} 需要参考答案 "answer"。'

        counts: dict[str, int] = {}
        for q in questions:
            counts[q.get("tier")] = counts.get(q.get("tier"), 0) + 1

        for tier, key in _TIER_TO_COUNT.items():
            if key == "interleaved" and not interleave_enabled:
                continue
            want = int(expected.get(key, 0) or 0)
            if want <= 0:
                continue
            floor = max(1, int(want * 0.6))
            got = counts.get(tier, 0)
            if got < floor:
                return False, f"{tier} 层级只有 {got} 题，请生成约 {want} 题，至少 {floor} 题。"

        if interleave_enabled and counts.get("Interleaved", 0) == 0:
            return False, '请加入 "tier":"Interleaved" 的跨周复习题。'
        return True, ""

    return _check


SYNTHESIS_RULES: list[Validator] = [
    no_korean_or_mojibake,
    has_mermaid_block,
    chinese_example_before_rules,
]
QUIZ_RULES: list[Validator] = [no_korean_or_mojibake]
GRADER_RULES: list[Validator] = [no_binary_grading, no_korean_or_mojibake]
SOCRATIC_RULES: list[Validator] = GRADER_RULES
FEYNMAN_RULES: list[Validator] = [no_binary_grading]
