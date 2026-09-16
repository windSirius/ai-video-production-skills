#!/usr/bin/env python3
"""Audit a game-lore narration manuscript without rewriting it."""

from __future__ import annotations

import argparse
import hashlib
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

# These are not broad bans on modern Chinese grammar. Each rule is deliberately
# narrow and records a wording/frame the user has already rejected in approved
# script reviews. Canonical dialogue is removed before these rules are applied.
HOUSE_STYLE_REJECTION_RULES = (
    (
        "relationship_as_organization_structure",
        re.compile(r"把(?:这|那)?(?:一)?层?关系写成(?:了)?组织结构"),
        "关系被生硬地改写为抽象结构；改回具体人物、身份与行动",
    ),
    (
        "version_really_asks",
        re.compile(r"真正追问的是"),
        "作者替版本发问，语气生硬；直接说明作品探讨的主题",
    ),
    (
        "narrator_writes_accurately",
        re.compile(r"旁白写得很准"),
        "搭配生硬；按语义改为‘描述得很到位’或‘比喻很恰当’",
    ),
    (
        "tone_only_explains_goal",
        re.compile(r"定调只说清(?:了)?(?:一个)?共同目标"),
        "‘定调—说清’搭配生硬；直接写清人物要共同做到什么",
    ),
    (
        "life_industry_upgrade",
        re.compile(r"生命工业(?:继续)?升级"),
        "抽象标签代替了具体威胁；写清谁制造生命、支配生命以及造成何种后果",
    ),
    (
        "kill_researcher_question",
        re.compile(r"该不该直接杀掉研究者"),
        "把人物的道德困境写成突兀的是非题；改写为抉择、克制与代价",
    ),
    (
        "meta_unknown_order",
        re.compile(r"现有文本没有交代(?:这|两)?(?:件事)?(?:的)?先后"),
        "这类话只是在报告研究边界，并不帮助观众理解剧情；无法判断且不影响主线时应当删去",
    ),
    (
        "voices_no_answer_hard_join",
        re.compile(r"许多声音怎样才能合到一起[，,]她还没有答案"),
        "疑问与结论硬接；先完成设问，再说明人物暂时没有答案",
    ),
    (
        "musicians_hard_transition",
        re.compile(r"三只晴空乐手就在此时诞生"),
        "新事件缺少承接；先说明它为何偏偏在此时出现",
    ),
    (
        "abstract_items_on_table",
        re.compile(
            r"(?:问题|矛盾|真相|议题)(?:被|已经|终于|也)?摆上桌|"
            r"(?:把|将)[^。！？!?\n]{0,30}"
            r"(?:问题|矛盾|真相|议题|方案|筹码|证据|结论|选择|认可|舆论)"
            r"(?:、|，|,|和|与|以及)[^。！？!?\n]{0,30}摆上桌"
        ),
        "把抽象问题说成字面物件；通常应写‘摆上台面’，或直接交代各方如何处理",
    ),
    (
        "generic_life_as_individual",
        re.compile(
            r"(?:替|为|给)生命(?:命名|取名|安排|规定)|"
            r"(?:等|若|如果|一旦)?生命(?:不肯|拒绝)(?:服从|听命)"
        ),
        "‘生命’是抽象泛称，不能代替具体的众生或人物；应写‘众生、生灵’或直接点名",
    ),
    (
        "living_being_assigned_utility",
        re.compile(
            r"(?:替|为|给)(?:生命|众生|生灵|尘灵|人造生命|造物|他们|它们)"
            r"[^。！？!?\n]{0,8}(?:安排|规定)[^。！？!?\n]{0,4}(?:用途|功能)"
        ),
        "‘用途、功能’属于物件或产品；写众生时应改为命运、职责、工作或具体遭遇",
    ),
)

ABSTRACT_TERMS = (
    "可能", "选择", "规则", "意义", "问题", "答案", "世界", "未来", "权力", "生命",
    "社会", "国家", "族群", "结果", "结构", "系统", "技术", "形式", "秩序", "身份",
    "自由", "幸福", "意志", "动机", "祝福", "诅咒",
)
NAVIGATION_LEAD = re.compile(
    r"^(?:我们(?:先|再|来|继续|最后|终于|现在)|先(?:别|来|看)|接下来|下面|现在|回到|"
    r"这里(?:先|再|也|就)?|再看|至于|所以(?:我们)?|换句话说|也就是说|又或者说|"
    r"这(?:也|就)?(?:解释了|意味着|说明)|真正(?:要|的)|讲到这里|说到这里|到这里)"
)
ORAL_CONNECTORS = ("换句话说", "也就是说", "又或者说", "用人话翻译", "这也解释了", "真正的问题")
QUOTE_RE = re.compile(r"[「『“]([^」』”]*)[」』”]")
HAN_RE = re.compile(r"[一-龥]")
TRADITIONAL_CHINESE_PROFILE = "traditional_chinese_v2"
SYNTAX_DIMENSIONS = (
    "clause_trunk",
    "semantic_referent",
    "narrative_viewpoint_register",
    "word_choice_collocation",
    "modifier_order",
    "subject_pronoun_reference",
    "sentence_connection",
    "paragraph_progression",
    "oral_breath",
)
METAPHOR_TERMS = (
    "烙印", "接口", "中继站", "签名", "通道", "钉进", "铺开", "占满道路", "枯死",
    "果壳", "齿轮", "拼图", "钥匙", "宫殿", "留一盏灯", "竖起一道门",
)
SUSPECT_COLLOCATION_PATTERNS = (
    re.compile(r"(?:接口|流程|结构|系统).{0,8}(?:执行|作证|签名)"),
    re.compile(r"(?:世界|地图).{0,8}(?:承认|作证|签名)"),
    re.compile(r"(?:传播|钉进|铺开|占满).{0,8}(?:结果|可能性|选择|道路)"),
    re.compile(r"(?:结果|可能性|选择|规则).{0,8}(?:写得|装上身体|占满道路|枯死|压回去)"),
    re.compile(r"(?:凝造|行为|选择).{0,8}(?:跨过世界|越过世界)"),
    re.compile(r"把[^。！？!?\n]{0,18}凌驾于"),
    re.compile(r"编号、身份和工作.{0,12}强加"),
)
SEMANTIC_REGISTER_PATTERNS = (
    (
        re.compile(
            r"(?:生命|众生|生灵|尘灵|人造生命|造物).{0,10}"
            r"(?:用途|功能|规格|产品|报废|销毁)"
        ),
        "众生与产品用语并置；确认这是机构故意物化众生的口吻，而不是旁白无意沿用",
    ),
    (
        re.compile(
            r"交付矛盾|完成(?:了)?(?:地点|场景)交接|推动答案|"
            r"价值主轴(?:变薄|变厚)|让.{0,8}意象承担价值|"
            r"(?:具体)?画面.{0,8}替.{0,8}(?:抽象)?概念承重|"
            r"公司不出成本|装着.{0,8}知识的(?:头颅|脑袋)|"
            r"(?:都|全)?在.{0,8}权限之内|一项完整推进"
        ),
        "管理、工程或内容行业用语进入人物叙事；改用自然汉语说明具体关系",
    ),
    (
        re.compile(
            r"替(?:他们|众生|生灵|人造生命).{0,4}安排一生|"
            r"决定(?:这些|那些)?(?:生灵|众生|人造生命)应当是谁|"
            r"为(?:这些|那些)?(?:生灵|众生|人造生命).{0,6}争回.{0,12}的机会"
        ),
        "句子虽然可以猜懂，却仍套用了生硬的身份或权利表达；直接写清谁在替众生决定身份与命运",
    ),
)
PRONOUNS = ("它", "这", "这个", "这份", "这条", "这套", "这些", "那套", "前者", "后者", "其中")


def find_house_style_rejections(text: str) -> list[dict]:
    """Find narrow, user-confirmed anti-patterns in narration-only text."""

    findings: list[dict] = []
    for rule_id, pattern, reason in HOUSE_STYLE_REJECTION_RULES:
        for match in pattern.finditer(text):
            left = max(match.start() - 18, 0)
            right = min(match.end() + 18, len(text))
            findings.append(
                {
                    "rule_id": rule_id,
                    "match": match.group(0),
                    "excerpt": text[left:right].replace("\n", " "),
                    "start": match.start(),
                    "reason": reason,
                }
            )
    return sorted(findings, key=lambda row: (int(row["start"]), str(row["rule_id"])))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sentence_records(paragraphs: list[str]) -> list[dict]:
    records: list[dict] = []
    sentence_index = 0
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        chunks = [
            match.group(0).strip()
            for match in re.finditer(r".+?(?:[。！？!?；;]+|$)", paragraph, flags=re.S)
            if match.group(0).strip()
        ]
        for chunk in chunks:
            sentence_index += 1
            records.append(
                {
                    "sentence_index": sentence_index,
                    "paragraph_index": paragraph_index,
                    "text": chunk,
                }
            )
    return records


def syntax_risk_id(category: str, paragraph_index: int, text: str) -> str:
    payload = f"{category}\0{paragraph_index}\0{text}".encode("utf-8")
    return f"TC-{hashlib.sha256(payload).hexdigest()[:12]}"


def traditional_chinese_diagnostic(paragraphs: list[str]) -> dict:
    # Strip complete quotations before sentence splitting; otherwise punctuation
    # inside a quote can split off the closing quote and defeat sentence-level
    # exclusion.
    records = sentence_records([remove_quoted_speech(paragraph) for paragraph in paragraphs])
    risk_items: list[dict] = []
    seen: set[tuple[str, int]] = set()

    def add(record: dict, category: str, severity: str, reason: str) -> None:
        key = (category, int(record["sentence_index"]))
        if key in seen:
            return
        seen.add(key)
        risk_items.append(
            {
                "risk_id": syntax_risk_id(category, int(record["paragraph_index"]), str(record["text"])),
                "category": category,
                "severity": severity,
                "sentence_index": record["sentence_index"],
                "paragraph_index": record["paragraph_index"],
                "text": record["text"],
                "reason": reason,
            }
        )

    for record in records:
        sentence = str(record["text"])
        han = len(HAN_RE.findall(sentence))
        if not han:
            continue
        if any(pattern.search(sentence) for pattern in SUSPECT_COLLOCATION_PATTERNS):
            add(
                record,
                "word_choice_collocation",
                "review",
                "搭配可能抽象或带有拟人；结合语境确认是否自然，不能仅凭词表判错",
            )
        for pattern, reason in SEMANTIC_REGISTER_PATTERNS:
            if pattern.search(sentence):
                add(
                    record,
                    "semantic_referent_register",
                    "review",
                    reason,
                )
                break
        if re.search(r"让[^。！？!?]{0,16}给|被[^。！？!?]{0,16}所(?:[一-龥])", sentence):
            add(
                record,
                "passive_tangle",
                "review",
                "使役或被动关系较长；朗读确认施事者、承受者和焦点都清楚",
            )
        if han >= 52 or sentence.count("，") + sentence.count("；") >= 5:
            add(
                record,
                "sentence_overload",
                "review",
                "一句话塞进太多分句；朗读时确认主要意思只有一个，而且无需回读",
            )
        if sentence.count("的") >= 3 or re.search(r"[一-龥]{9,}的[一-龥]{2,5}(?=，|。|；|$)", sentence):
            add(
                record,
                "modifier_stack",
                "review",
                "前置修饰或‘的’字链较长；优先先说主干，再把细节放到后面",
            )
        abstract_count = sum(sentence.count(term) for term in ABSTRACT_TERMS)
        if abstract_count >= 4:
            add(
                record,
                "abstract_noun_stack",
                "review",
                "抽象名词连续出现；确认句中仍有具体人物、动作、原文或后果",
            )
        pronoun_count = sum(sentence.count(term) for term in PRONOUNS)
        if pronoun_count >= 3 or (
            re.match(r"^(?:它|这份|这条|这套|这些|那套|前者|后者|其中)", sentence)
            and pronoun_count >= 2
        ):
            add(
                record,
                "pronoun_handoff",
                "review",
                "代词连续出现，或者句中更换了主语；确认每个代词只能指向一个对象",
            )
        if NAVIGATION_LEAD.search(sentence):
            add(
                record,
                "transition_scaffold",
                "review",
                "句子以过渡语起头；确认它确实承接上一段的人物、事件或因果，而不只是宣布接下来讲什么",
            )
        metaphor_count = sum(term in sentence for term in METAPHOR_TERMS)
        if metaphor_count >= 2:
            add(
                record,
                "metaphor_stack",
                "review",
                "同一句叠加多组比喻；只保留一组能稳定对应事实的意象",
            )
        if re.search(
            r"(?:真正的.{0,16}是|本质上是|核心在于|在.{1,10}层面|从.{1,10}角度来看|对于.{1,10}而言)",
            sentence,
        ):
            add(
                record,
                "nominal_frame",
                "review",
                "这句话套用了空泛的判断句式；确认直接写人物做了什么是否更清楚",
            )

    risk_items.sort(key=lambda row: (int(row["sentence_index"]), str(row["category"])))
    counts: dict[str, int] = {}
    for row in risk_items:
        counts[str(row["category"])] = counts.get(str(row["category"]), 0) + 1
    blocker_ids = [row["risk_id"] for row in risk_items if row["severity"] == "blocker"]
    return {
        "profile": TRADITIONAL_CHINESE_PROFILE,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(records),
        "risk_count": len(risk_items),
        "blocker_count": len(blocker_ids),
        "blocker_risk_ids": blocker_ids,
        "risk_counts": counts,
        "risk_items": risk_items,
    }


def resolve_review_path(review_path: Path, value: object, manuscript: Path) -> Path:
    raw = Path(str(value or "")).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    candidates = (
        review_path.parent / raw,
        review_path.parent.parent / raw,
        manuscript.parent / raw,
        Path.cwd() / raw,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def validate_traditional_chinese_review(
    review_path: Path | None,
    manuscript: Path,
    manuscript_sha256: str,
    diagnostic: dict,
) -> tuple[list[str], dict]:
    failures: list[str] = []
    summary = {"review_path": str(review_path.resolve()) if review_path else None, "status": "missing"}
    if review_path is None or not review_path.is_file():
        return ["缺少传统中文逐句审校收据"], summary
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["传统中文逐句审校收据无法读取"], {**summary, "status": "invalid"}
    if not isinstance(review, dict):
        return ["传统中文逐句审校收据必须是JSON对象"], {**summary, "status": "invalid"}
    if str(review.get("profile", "")).strip() != TRADITIONAL_CHINESE_PROFILE:
        failures.append("traditional_chinese_review.profile")
    if str(review.get("status", "")).strip().lower() != "pass":
        failures.append("traditional_chinese_review.status")
    review_script = resolve_review_path(review_path, review.get("script_path", ""), manuscript)
    if (
        not review_script.is_file()
        or review_script.resolve() != manuscript.resolve()
        or str(review.get("script_sha256", "")).lower() != manuscript_sha256
        or sha256_file(review_script) != manuscript_sha256
    ):
        failures.append("traditional_chinese_review.script_binding")
    diagnostic_path = resolve_review_path(review_path, review.get("diagnostic_path", ""), manuscript)
    diagnostic_sha = str(review.get("diagnostic_sha256", "")).lower()
    bound_diagnostic: dict = {}
    if not diagnostic_path.is_file() or not diagnostic_sha or sha256_file(diagnostic_path) != diagnostic_sha:
        failures.append("traditional_chinese_review.diagnostic_binding")
    else:
        try:
            loaded = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            bound_diagnostic = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            failures.append("traditional_chinese_review.diagnostic_json")
    current_ids = [str(row["risk_id"]) for row in diagnostic["risk_items"]]
    bound_ids = [
        str(row.get("risk_id", ""))
        for row in bound_diagnostic.get("traditional_chinese", {}).get("risk_items", [])
        if isinstance(row, dict)
    ]
    if bound_ids != current_ids:
        failures.append("traditional_chinese_review.diagnostic_risk_set")
    if diagnostic["blocker_count"]:
        failures.append("traditional_chinese_review.blockers_must_be_rewritten")
    if review.get("full_sentence_reviewed") is not True:
        failures.append("traditional_chinese_review.full_sentence_reviewed")
    if review.get("full_referent_register_reviewed") is not True:
        failures.append("traditional_chinese_review.full_referent_register_reviewed")
    if review.get("full_paragraph_transition_reviewed") is not True:
        failures.append("traditional_chinese_review.full_paragraph_transition_reviewed")
    if review.get("full_speed_1x_read") is not True:
        failures.append("traditional_chinese_review.full_speed_1x_read")
    if review.get("sentence_count") != diagnostic["sentence_count"]:
        failures.append("traditional_chinese_review.sentence_count")
    if review.get("paragraph_count") != diagnostic["paragraph_count"]:
        failures.append("traditional_chinese_review.paragraph_count")
    dimensions = review.get("dimensions")
    if not isinstance(dimensions, dict):
        failures.append("traditional_chinese_review.dimensions")
    else:
        for field in SYNTAX_DIMENSIONS:
            if str(dimensions.get(field, "")).strip().lower() != "pass":
                failures.append(f"traditional_chinese_review.dimensions.{field}")
    resolutions = review.get("risk_resolutions")
    resolved: dict[str, dict] = {}
    if not isinstance(resolutions, list):
        failures.append("traditional_chinese_review.risk_resolutions")
    else:
        for row in resolutions:
            if not isinstance(row, dict) or not str(row.get("risk_id", "")).strip():
                failures.append("traditional_chinese_review.risk_resolution_row")
                continue
            risk_id = str(row["risk_id"])
            if risk_id in resolved:
                failures.append("traditional_chinese_review.duplicate_risk_id")
            resolved[risk_id] = row
        if set(resolved) != set(current_ids):
            failures.append("traditional_chinese_review.risk_resolution_set")
        for risk_id, row in resolved.items():
            if str(row.get("disposition", "")).strip().lower() != "accepted_with_reason":
                failures.append(f"traditional_chinese_review.risk_resolution.{risk_id}.disposition")
            if not str(row.get("reason", "")).strip() or not str(row.get("final_excerpt", "")).strip():
                failures.append(f"traditional_chinese_review.risk_resolution.{risk_id}.evidence")
    transitions = review.get("transition_review")
    expected_transitions = max(int(diagnostic["paragraph_count"]) - 1, 0)
    if not isinstance(transitions, dict):
        failures.append("traditional_chinese_review.transition_review")
    else:
        if str(transitions.get("status", "")).strip().lower() != "pass":
            failures.append("traditional_chinese_review.transition_review.status")
        if transitions.get("expected_transition_count") != expected_transitions:
            failures.append("traditional_chinese_review.transition_review.expected_transition_count")
        if transitions.get("reviewed_transition_count") != expected_transitions:
            failures.append("traditional_chinese_review.transition_review.reviewed_transition_count")
        for field in ("dangling_transition_count", "ambiguous_subject_handoff_count"):
            if transitions.get(field) != 0:
                failures.append(f"traditional_chinese_review.transition_review.{field}")
    if review.get("open_issue_count") != 0:
        failures.append("traditional_chinese_review.open_issue_count")
    if not str(review.get("reviewer", "")).strip() or not str(review.get("reviewed_at", "")).strip():
        failures.append("traditional_chinese_review.reviewer/reviewed_at")
    return failures, {
        "review_path": str(review_path.resolve()),
        "review_sha256": sha256_file(review_path),
        "status": "pass" if not failures else "fail",
        "failure_count": len(failures),
    }


def body_section(text: str) -> str:
    if BODY_START in text:
        text = text.split(BODY_START, 1)[1]
    if BODY_END in text:
        text = text.split(BODY_END, 1)[0]
    return text


def clean_spoken_line(raw: str) -> str | None:
    line = raw.strip()
    if not line or line.startswith(("〔", "|", "---", "#", ">")):
        return None
    if re.fullmatch(r"（[^）]*）", line):
        return None
    return re.sub(r"〔[^〕]*〕|（停[^）]*）|[*`]", "", line)


def spoken_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in body_section(text).splitlines():
        if not raw.strip():
            if current:
                paragraphs.append("\n".join(current))
                current = []
            continue
        line = clean_spoken_line(raw)
        if line:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def spoken_lines(text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in spoken_paragraphs(text):
        lines.extend(paragraph.splitlines())
    return lines


def spoken_body(text: str) -> str:
    return "\n".join(spoken_lines(text))


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def remove_quoted_speech(text: str) -> str:
    return re.sub(r"[「『“][^」』”]*[」』”]", "", text)


def split_opening_core_question(paragraphs: list[str]) -> tuple[str, str]:
    """Return the first question sentence and all remaining narration.

    The hook exception is sentence-scoped. A later casual ``你看`` in the same
    paragraph is still body narration and therefore remains a blocker.
    """

    if not paragraphs:
        return "", ""
    cleaned = [remove_quoted_speech(paragraph) for paragraph in paragraphs]
    first = cleaned[0]
    first_sentence = re.match(r"^\s*(.*?[。！？!?；;])", first, flags=re.S)
    if first_sentence and first_sentence.group(1).rstrip().endswith(("？", "?")):
        question = first_sentence.group(1)
        remainder = first[first_sentence.end() :]
    else:
        question = ""
        remainder = first
    body_parts = [remainder, *cleaned[1:]]
    return question, "\n".join(part for part in body_parts if part)


def audit(
    path: Path,
    canonical: Path | None,
    *,
    style_profile: str = "author_voice_v1",
    syntax_profile: str = TRADITIONAL_CHINESE_PROFILE,
    syntax_review: Path | None = None,
    target_min_han: int | None = None,
    target_max_han: int | None = None,
    second_person_policy: str = "hook_only",
    hook_paragraphs: int = 1,
) -> dict:
    text = path.read_text(encoding="utf-8")
    manuscript_sha256 = sha256_file(path)
    lines = spoken_lines(text)
    paragraphs = spoken_paragraphs(text)
    body = "\n".join(lines)
    compact = re.sub(r"\s+", "", body)
    narration_lines = [remove_quoted_speech(line) for line in lines]
    narration_paragraphs = [remove_quoted_speech(paragraph) for paragraph in paragraphs]
    narration_only = "\n".join(narration_lines)
    house_style_rejections = find_house_style_rejections(narration_only)
    opening_core_question, body_narration = split_opening_core_question(paragraphs)
    hook_narration = opening_core_question if hook_paragraphs else ""
    if not hook_paragraphs:
        body_narration = "\n".join(narration_paragraphs)
    findings = {name: len(re.findall(pattern, narration_only)) for name, pattern in EURO_PATTERNS.items()}
    findings["钩子第二人称"] = len(re.findall(r"你(?:们)?", hook_narration))
    findings["正文第二人称"] = len(re.findall(r"你(?:们)?", body_narration))
    findings["叙述层你"] = findings["钩子第二人称"] + findings["正文第二人称"]
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
    han_count = len(HAN_RE.findall(body))
    quote_han = sum(len(HAN_RE.findall(match)) for match in QUOTE_RE.findall(body))
    abstract_count = sum(body.count(term) for term in ABSTRACT_TERMS)
    navigation_lines = [line for line in non_quote_lines if NAVIGATION_LEAD.search(line)]
    connector_count = sum(narration_only.count(term) for term in ORAL_CONNECTORS)
    author_voice = {
        "profile": style_profile,
        "han_characters": han_count,
        "paragraphs": len(non_quote_lines),
        "question_marks": len(re.findall(r"[？?]", body)),
        "direct_quote_han": quote_han,
        "direct_quote_han_ratio": round(quote_han / max(han_count, 1), 4),
        "abstract_term_count": abstract_count,
        "abstract_terms_per_1000_han": round(abstract_count / max(han_count, 1) * 1000, 3),
        "navigation_led_paragraphs": len(navigation_lines),
        "navigation_led_paragraph_ratio": round(len(navigation_lines) / max(len(non_quote_lines), 1), 4),
        "navigation_led_samples": navigation_lines[:8],
        "oral_connector_count": connector_count,
        "oral_connectors_per_1000_han": round(connector_count / max(han_count, 1) * 1000, 3),
        "真正_count": narration_only.count("真正"),
        "fixed_if_opening": bool(non_quote_lines and re.match(r"^如果", non_quote_lines[0])),
    }
    errors: list[str] = []
    warnings: list[str] = []
    if house_style_rejections:
        rule_ids = ", ".join(sorted({str(row["rule_id"]) for row in house_style_rejections}))
        errors.append(f"命中用户已明确否定的措词或叙事框架：{rule_ids}")
    if findings["对比模板"]:
        warnings.append("存在对比模板句；只在机械重复或掩盖判断时修改")
    if second_person_policy == "hook_only":
        if findings["正文第二人称"]:
            errors.append("hook_only 模式下正文存在第二人称")
        if findings["钩子第二人称"] > 2:
            warnings.append("钩子第二人称偏多，请确认不是反复称呼观众")
    elif second_person_policy == "none" and findings["叙述层你"]:
        errors.append("none 模式下叙述层存在第二人称")
    elif second_person_policy != "free":
        if second_person_policy not in {"hook_only", "none"}:
            raise ValueError(f"unknown second-person policy: {second_person_policy}")
    if findings["东西"]:
        warnings.append("存在‘东西’，请确认指代是否具体；自然用法不要求机械清零")
    if first_principle["的字至少3的句"]:
        warnings.append("存在单句三个或以上‘的’，请朗读确认主干；自然句不要求机械清零")
    if first_principle["判断框"]:
        warnings.append("存在判断框，请确认它比直接动词句更自然")
    if first_principle["冗余框架"]:
        warnings.append("存在冗余框架，请确认删掉后是否无损")
    if first_principle["9字以上前置定语"]:
        warnings.append("存在九字以上前置定语，请朗读确认一次能懂")
    if first_principle["的字密度百分比"] > 3.0:
        warnings.append("‘的’字密度超过3.0%，只在听感确实名词化时重写")
    if style_profile == "author_voice_v1":
        author_voice["target_min_han"] = target_min_han
        author_voice["target_max_han"] = target_max_han
        if target_min_han is not None and han_count < target_min_han:
            errors.append(f"口播汉字数低于作者声音目标下限 {target_min_han}")
        if target_max_han is not None and han_count > target_max_han:
            errors.append(f"口播汉字数超过作者声音目标上限 {target_max_han}")
        if han_count >= 800 and author_voice["abstract_terms_per_1000_han"] > 24:
            warnings.append("抽象词密度偏高，逐段检查是否缺少人物、动作、原文或后果")
        elif han_count >= 800 and author_voice["abstract_terms_per_1000_han"] > 18:
            warnings.append("抽象词密度超过18/千汉字，逐段检查是否在重复解释")
        if len(non_quote_lines) >= 12 and author_voice["navigation_led_paragraph_ratio"] > 0.25:
            warnings.append("以过渡语开头的段落偏多，检查这些段落是否真的推进了事实或判断")
        elif len(non_quote_lines) >= 12 and author_voice["navigation_led_paragraph_ratio"] > 0.15:
            warnings.append("以过渡语开头的段落超过15%，检查‘下面、这里、换句话说’之后是否真的有新内容")
        if han_count >= 800 and author_voice["direct_quote_han_ratio"] < 0.06:
            warnings.append("直接引用的原文低于6%，确认关键判断是否仍有明确的原文依据")
        if han_count >= 800 and author_voice["oral_connectors_per_1000_han"] > 3:
            warnings.append("口语连接语偏多，检查是否只是在换一种说法重复同一判断")
        if author_voice["fixed_if_opening"]:
            warnings.append("开头仍使用‘如果……’结构；与近三期钩子比对后再决定是否保留")
    elif style_profile != "legacy":
        raise ValueError(f"unknown style profile: {style_profile}")
    canonical_match = None
    if canonical:
        canonical_match = normalize(body) == normalize(spoken_body(canonical.read_text(encoding="utf-8")))
        if not canonical_match:
            errors.append("正文与正典纯文本不一致")
    else:
        errors.append("缺少正典口播纯文本，无法验证逐字一致")
    traditional_chinese = traditional_chinese_diagnostic(paragraphs)
    traditional_chinese["review"] = {"status": "not_required", "review_path": None}
    if syntax_profile == TRADITIONAL_CHINESE_PROFILE:
        if traditional_chinese["blocker_count"]:
            errors.append("传统中文诊断仍有严重问题，必须改写后重新检查")
        syntax_failures, review_summary = validate_traditional_chinese_review(
            syntax_review,
            path,
            manuscript_sha256,
            traditional_chinese,
        )
        traditional_chinese["review"] = review_summary
        traditional_chinese["review_failures"] = syntax_failures
        errors.extend(syntax_failures)
    elif syntax_profile != "legacy":
        raise ValueError(f"unknown syntax profile: {syntax_profile}")
    return {
        "status": "pass" if not errors else "fail",
        "path": str(path.resolve()),
        "manuscript_sha256": manuscript_sha256,
        "spoken_characters": len(compact),
        "estimated_minutes_350_cpm": round(len(compact) / 350, 2),
        "estimated_minutes_400_cpm": round(len(compact) / 400, 2),
        "findings": findings,
        "first_principle": first_principle,
        "author_voice": author_voice,
        "second_person": {
            "policy": second_person_policy,
            "hook_paragraphs": hook_paragraphs,
            "opening_core_question": opening_core_question,
            "hook_count": findings["钩子第二人称"],
            "body_count": findings["正文第二人称"],
        },
        "traditional_chinese": traditional_chinese,
        "house_style_rejections": house_style_rejections,
        "canonical_match": canonical_match,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--style-profile", choices=("legacy", "author_voice_v1"), default="author_voice_v1")
    parser.add_argument(
        "--syntax-profile",
        choices=("legacy", TRADITIONAL_CHINESE_PROFILE),
        default=TRADITIONAL_CHINESE_PROFILE,
    )
    parser.add_argument("--syntax-review", type=Path)
    parser.add_argument("--target-min-han", type=int)
    parser.add_argument("--target-max-han", type=int)
    parser.add_argument(
        "--second-person-policy",
        choices=("hook_only", "none", "free"),
        default="hook_only",
    )
    parser.add_argument("--hook-paragraphs", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.target_min_han is not None and args.target_max_han is not None:
        if args.target_min_han > args.target_max_han:
            parser.error("--target-min-han cannot exceed --target-max-han")
    if args.hook_paragraphs < 0:
        parser.error("--hook-paragraphs must be non-negative")
    result = audit(
        args.manuscript,
        args.canonical,
        style_profile=args.style_profile,
        syntax_profile=args.syntax_profile,
        syntax_review=args.syntax_review,
        target_min_han=args.target_min_han,
        target_max_han=args.target_max_han,
        second_person_policy=args.second_person_policy,
        hook_paragraphs=args.hook_paragraphs,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status'].upper()} spoken={result['spoken_characters']} findings={result['findings']}")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
