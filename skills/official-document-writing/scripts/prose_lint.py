"""受控的中文公文语言质检脚本，只读输入并输出 JSON。"""
from __future__ import annotations

import json
import re
import sys


PATTERNS = (
    ("high", "thought-leak", r"作为(?:一个)?\s*AI|我是(?:一个)?\s*AI|内部推理|根据用户要求"),
    ("medium", "side-commentary", r"本文将从|以下(?:直接)?列出|为了便于理解|综上所述[，,]"),
    ("low", "empty-filler", r"全面赋能|提供有力支撑|奠定坚实基础|未来可期|形成一批"),
    ("low", "abstract-term", r"赋能|闭环|底座|抓手|矩阵"),
    ("medium", "format", r"[一-鿿][,;:!?][一-鿿]"),
)


def lint(text: str) -> list[dict[str, object]]:
    findings = []
    for line_no, line in enumerate((text or "").splitlines(), 1):
        for severity, label, pattern in PATTERNS:
            match = re.search(pattern, line)
            if match:
                findings.append({
                    "line": line_no,
                    "severity": severity,
                    "label": label,
                    "match": match.group(0),
                })
    return findings


if __name__ == "__main__":
    payload = sys.stdin.read()
    print(json.dumps(lint(payload), ensure_ascii=False))
