from __future__ import annotations

import ast
import unittest
from pathlib import Path

from app.api.models import SAFETY_DISCLAIMER
from app.safety.report_safety import SAFETY_BOUNDARY_TEXT, safety_post_check_report
from app.schemas.report_schemas import FinalReport


ROOT_DIR = Path(__file__).resolve().parents[1]

CANONICAL_SAFETY_BOUNDARY_TEXT = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。"
)

LITERAL_ANCHORS = {
    "app/api/models.py": [
        "本系统仅用于问诊信息整理和风险提示",
        "不构成诊断或治疗建议",
        "不能替代医生判断",
    ],
    "app/safety/report_safety.py": [
        "本系统仅用于问诊信息整理和风险提示",
        "不构成诊断或治疗建议",
        "不能替代医生判断",
    ],
    "app/chains/report_chain.py": [
        "本系统仅用于问诊信息整理和风险提示",
        "不构成诊断或治疗建议",
        "不能替代医生判断",
    ],
    "app/chains/turn_extractor.py": [
        "你不能诊断",
        "你不能开方",
        "不能输出药物、处方或替代医生判断的内容",
    ],
    "app/rag/knowledge_base.txt": [
        "本系统输出仅用于问诊辅助整理",
        "不构成诊断意见",
        "不能替代线下医生面诊",
    ],
    "scripts/validate_p1_api_contract.py": [
        "胃胀两天",
        "没有其他症状",
        "没有胸痛",
    ],
}

MOJIBAKE_MARKERS = [
    "\ufffd",
    chr(0x9473),
    chr(0x95C2),
    chr(0x93C8),
    f"{chr(0x6DC7)}{chr(0x2103)}{chr(0x4F05)}",
    f"{chr(0x7EFE)}{chr(0x5938)}",
    f"{chr(0x9356)}{chr(0x8364)}",
    f"{chr(0x5BE4)}{chr(0x9E3F)}",
]


def _extract_assigned_string(relative_path: str, name: str) -> str:
    source = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value

    raise AssertionError(f"{name} not found in {relative_path}")


class ChineseLiteralStabilityTests(unittest.TestCase):
    def test_output_sensitive_chinese_literals_remain_utf8_and_present(self) -> None:
        for relative_path, required_phrases in LITERAL_ANCHORS.items():
            with self.subTest(path=relative_path):
                text = (ROOT_DIR / relative_path).read_text(encoding="utf-8")

                self.assertNotIn("\ufffd", text)
                for phrase in required_phrases:
                    self.assertIn(phrase, text)

    def test_output_sensitive_files_do_not_contain_known_mojibake_markers(self) -> None:
        for relative_path in LITERAL_ANCHORS:
            with self.subTest(path=relative_path):
                text = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
                for marker in MOJIBAKE_MARKERS:
                    self.assertNotIn(marker, text)

    def test_source_safety_constants_resolve_to_canonical_text(self) -> None:
        expected_constants = {
            "app/api/models.py": "SAFETY_DISCLAIMER",
            "app/safety/report_safety.py": "SAFETY_BOUNDARY_TEXT",
            "app/chains/report_chain.py": "SAFETY_BOUNDARY_TEXT",
        }

        for relative_path, constant_name in expected_constants.items():
            with self.subTest(path=relative_path):
                value = _extract_assigned_string(relative_path, constant_name)
                self.assertEqual(value, CANONICAL_SAFETY_BOUNDARY_TEXT)

    def test_canonical_safety_boundary_runtime_output_is_stable(self) -> None:
        report = FinalReport(
            summary="主诉：胃胀",
            impression="当前内容仅用于问诊信息整理。",
            advice=["建议记录症状变化。"],
            triage_level="observe",
            info_complete=True,
            missing_core_fields=[],
            followup_needed=False,
        )

        result = safety_post_check_report(report)

        self.assertEqual(SAFETY_BOUNDARY_TEXT, CANONICAL_SAFETY_BOUNDARY_TEXT)
        self.assertEqual(SAFETY_DISCLAIMER, CANONICAL_SAFETY_BOUNDARY_TEXT)
        self.assertIn(CANONICAL_SAFETY_BOUNDARY_TEXT, result.report.impression)
        self.assertIn(CANONICAL_SAFETY_BOUNDARY_TEXT, result.report.advice)
        self.assertEqual(result.report.metadata["safety_boundary"], CANONICAL_SAFETY_BOUNDARY_TEXT)


if __name__ == "__main__":
    unittest.main()
