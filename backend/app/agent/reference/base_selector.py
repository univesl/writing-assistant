from __future__ import annotations

import re
from typing import Any


_CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def material_content_by_id(source_materials: list[dict[str, Any]]) -> dict[int, str]:
    return {
        int(item.get("file_id") or 0): str(item.get("content") or "")
        for item in source_materials
        if item.get("file_id")
    }


def select_reference_base_material(
    requirements: str,
    source_materials: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not source_materials:
        return None
    target_edition = target_edition_number(requirements)
    scored = []
    for index, material in enumerate(source_materials):
        filename = str(material.get("filename") or "")
        edition = edition_number(filename)
        if edition is None:
            score = 0
        elif target_edition is not None and edition < target_edition:
            score = 1000 + edition
        elif target_edition is None:
            score = 500 + edition
        else:
            score = 100
        if "第三十五届" in filename:
            score += 50
        scored.append((score, -index, material))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return scored[0][2]


def edition_number(value: Any) -> int | None:
    match = re.search(r"第([一二三四五六七八九十百两0-9]+)届", str(value or ""))
    return chinese_number_to_int(match.group(1)) if match else None


def target_edition_number(value: Any) -> int | None:
    label = target_edition_label(value)
    return chinese_number_to_int(label) if label else None


def edition_label(value: Any) -> str | None:
    match = re.search(r"第([一二三四五六七八九十百两0-9]+)届", str(value or ""))
    return match.group(1) if match else None


def target_edition_label(value: Any) -> str | None:
    matches = re.findall(r"第([一二三四五六七八九十百两0-9]+)届", str(value or ""))
    if not matches:
        return None
    scored = [(chinese_number_to_int(label) or -1, index, label) for index, label in enumerate(matches)]
    return max(scored, key=lambda item: (item[0], item[1]))[2]


def date_label(value: Any) -> str | None:
    match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", str(value or ""))
    return match.group(1) if match else None


def chinese_number_to_int(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = 0
    current = 0
    for char in text:
        if char == "百":
            current = max(current, 1) * 100
            total += current
            current = 0
        elif char == "十":
            current = max(current, 1) * 10
            total += current
            current = 0
        elif char in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[char]
        else:
            return None
    return total + current
