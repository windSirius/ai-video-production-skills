#!/usr/bin/env python3
"""Audit a game-lore narration manuscript without rewriting it."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BODY_START = "## 三、口播稿正文"
BODY_END = "## 四、标题池"
EURO_PATTERNS = {
    "名词化框架": r"进行(?:了)?|作出(?:了)?|实现(?:了)?|提供(?:了)?",
    "判断框": r"真正的.{0,16}是|核心在于|本质上是",
    "对比模板": r"不是.{1,14}而是|不是.{1,12}，是|与其说.{1,18}不如说",
    "空泛比喻": r"尺子|按钮|开关|钥匙|拼图|齿轮|扣子",
}


def spoken_lines(text: str) -> list[str]:
    if BODY_START in text:
        text = text.split(BODY_START, 1)[1]
    if BODY_END in text:
        text = text.split(BODY_END, 1)[0]
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("〔", "|", "---", "#", ">")):
            continue
        if re.fullmatch(r"（[^）]*）", line):
            continue
        line = re.sub(r"〔[^〕]*〕|（停[^）]*）|[*`]", "", line)
        lines.append(line)
    return lines


def spoken_body(text: str) -> str:
    return "\n".join(spoken_lines(text))


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def audit(path: Path, canonical: Path | None) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = spoken_lines(text)
    body = "\n".join(lines)
    compact = re.sub(r"\s+", "", body)
    narration_only = re.sub(r"[「『“][^」』”]*[」』”]", "", body)
    findings = {name: len(re.findall(pattern, narration_only)) for name, pattern in EURO_PATTERNS.items()}
    findings["叙述层你"] = len(re.findall(r"你", narration_only))
    findings["东西"] = len(re.findall(r"东西", narration_only))
    non_quote_lines = [line for line in lines if not line.startswith(("「", "『", "“"))]
    joined = "".join(non_quote_lines)
    first_principle = {
        "的字至少3的句": sum(line.count("的") >= 3 for line in non_quote_lines),
        "判断框": len(re.findall(r"是(一种|一个|一件|一场|整个)|的第一件事，?是|本身就是一", joined)),
        "冗余框架": len(re.findall(r"的地方|的事情|值得[一-龥]{0,2}说|这个[一-龥]{1,3}本身|各位玩家", joined)),
        "9字以上前置定语": len(re.findall(r"[一-龥]{9,}的[一-龥]{2,4}(?=，|。|$)", joined)),
        "的字密度百分比": round(joined.count("的") / max(len(joined), 1) * 100, 3),
    }
    errors: list[str] = []
    if findings["对比模板"]:
        errors.append("存在对比模板句")
    if findings["叙述层你"]:
        errors.append("存在需人工确认的‘你’")
    if findings["东西"]:
        errors.append("存在口语占位词‘东西’")
    if first_principle["的字至少3的句"]:
        errors.append("存在单句三个或以上‘的’")
    if first_principle["判断框"]:
        errors.append("存在第一原则判断框")
    if first_principle["冗余框架"]:
        errors.append("存在冗余框架")
    if first_principle["9字以上前置定语"]:
        errors.append("存在九字以上前置定语")
    if first_principle["的字密度百分比"] > 3.0:
        errors.append("‘的’字密度超过3.0%")
    canonical_match = None
    if canonical:
        canonical_match = normalize(body) == normalize(spoken_body(canonical.read_text(encoding="utf-8")))
        if not canonical_match:
            errors.append("正文与正典纯文本不一致")
    return {
        "status": "pass" if not errors else "fail",
        "path": str(path.resolve()),
        "spoken_characters": len(compact),
        "estimated_minutes_350_cpm": round(len(compact) / 350, 2),
        "estimated_minutes_400_cpm": round(len(compact) / 400, 2),
        "findings": findings,
        "first_principle": first_principle,
        "canonical_match": canonical_match,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--canonical", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(args.manuscript, args.canonical)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status'].upper()} spoken={result['spoken_characters']} findings={result['findings']}")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
