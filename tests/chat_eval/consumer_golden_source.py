"""Lossless adapter from the approved Consumer/PixVerse Markdown to source rows.

The output is intentionally fed into the existing approved Golden Case workflow;
this module does not define a second ingestion or evaluation contract.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_QUESTION = re.compile(r"^Q[：:]\s*(?P<body>.+?)\s*$")
_ANSWER = re.compile(r"^A[：:]\s*(?P<body>.*)$")
_BARE_ANSWER = re.compile(r"^\s*[：:]\s*(?P<body>.*)$")
_VARIABLE = re.compile(r"【(?P<name>[^【】]+)】")
_SUBHEADING = re.compile(r"^[一二三四五六七八九十]+、")
_BUG_NOTE = "这个目前测试的时候，找不到地方点击回查看兑换码"

_REDEMPTION_AREAS = {
    **{number: "consumer_redemption_overview" for number in range(1, 7)},
    **{number: "consumer_mint" for number in range(7, 12)},
    **{number: "consumer_redemption_code" for number in range(12, 22)},
    **{number: "consumer_refund" for number in range(22, 28)},
    **{number: "consumer_funds_and_value" for number in range(28, 39)},
    **{number: "consumer_activity_and_state" for number in range(39, 45)},
    **{number: "consumer_safety_and_support" for number in range(45, 49)},
}
_PIXVERSE_AREAS = {
    **{number: "pixverse_brand" for number in range(1, 5)},
    **{number: "pixverse_benefit" for number in range(5, 14)},
    **{number: "pixverse_boundaries" for number in range(14, 19)},
}

_REDEMPTION_FACT_TERMS = {
    1: [["合约"], ["权益"], ["份额"], ["兑换码"], ["退回本金", "赎回本金"]],
    2: [["合约"], ["兑换成码之前", "兑换之前"], ["取回"]],
    3: [["换取权益", "兑换权益"], ["升值预期", "升值"], ["兑换什么", "兑换权益"]],
    4: [["ERC-20", "ERC20"], ["可分割"], ["收藏品"]],
    5: [["钱包"], ["结算代币"], ["份额"], ["换码", "兑换码"]],
    6: [["连接钱包"], ["Mint 区", "Mint"], ["提交申请"], ["结算完成"], ["可领取"], ["My Shares"]],
    7: [["兑换码"], ["份额"], ["持有"], ["赎回"], ["换不了码", "无法兑换"]],
    8: [["份额"], ["My Shares"], ["主动兑换"]],
    9: [["费率"], ["确认之前", "确认前"], ["页面"]],
    10: [["部署时就固定", "部署时固定"], ["不能更改", "不可更改"]],
    11: [["一种结算代币"], ["合约层面固定", "合约固定"]],
    12: [["我的份额", "My Shares"], ["去兑换"], ["弹窗"], ["选择数量"], ["生成兑换码"], ["复制"]],
    13: [["份额"]],
    14: [["兑换成功"], ["份额会被回收", "份额被回收"], ["不再持有"]],
    15: [["选择兑换数量", "兑换一部分"], ["没兑换的份额", "未兑换的份额"], ["继续持有"], ["Refund", "赎回"]],
    19: [["兑换页"], ["显示", "为准"]],
    20: [["兑换成功"], ["去消费"], ["跳转按钮"], ["使用入口"]],
    21: [["份额已扣"], ["码没生成", "兑换码没生成"], ["记录异常"], ["重试"], ["官方支持"], ["不会让你损失份额", "不损失份额"]],
    22: [["未兑换的份额"], ["赎回"], ["本金"], ["退回"]],
    23: [["未兑换的份额"], ["兑换码"], ["份额已经被回收", "份额被回收"], ["无法再赎回"]],
    26: [["提交申请"], ["Pending"], ["Claimable"], ["领取"]],
    27: [["没有", "无"], ["多次赎回", "分多次赎回"]],
    28: [["智能合约", "合约"], ["Moss"]],
    29: [["合约限制"], ["运营"], ["本金"]],
    30: [["合约限制"]],
    31: [["门槛"], ["费率"], ["不会改变", "不能改变"], ["合约不提供"]],
    32: [["本金"], ["合约"], ["赎回不受影响"], ["兑换码"], ["履约"]],
    33: [["ERC-20", "ERC20"], ["流通"], ["Moss"], ["Refund", "赎回"]],
    34: [["合约"], ["兑换率"], ["兑换权益"], ["价格波动"]],
    37: [["铸造"], ["赎回"], ["兑换本身不收费", "兑换不收费"], ["操作前", "确认前"]],
    39: [["当前持有"], ["数量"], ["换成码", "兑换码"], ["不会出现在这里"]],
    40: [["铸造活动"], ["操作记录"], ["兑换码活动"], ["生成记录"], ["地址"], ["脱敏"]],
    41: [["没持有份额", "未持有份额"], ["暂停"], ["提示"]],
    42: [["发行方"], ["暂停"], ["铸造"], ["赎回"], ["已持有的份额"], ["不受影响"]],
    43: [["兑换"], ["消耗份额"], ["无法再赎回"], ["选择"]],
    44: [["主动发起"], ["兑换"]],
    45: [["实际价值"], ["扣除费用"], ["固定金额", "固定金额的承诺"]],
    46: [["没有", "无"], ["收益产品"], ["兑换权益"]],
    47: [["兑换码使用问题"], ["铸造"], ["赎回"], ["份额问题"], ["Moss"]],
    48: [["提问"], ["联系"]],
}
_PIXVERSE_FACT_TERMS = {
    1: [["AI 视频生成公司"], ["自研"], ["视频基础模型"], ["文生视频"], ["图生视频"], ["Agent 对话式创作"], ["Marketing Hub"], ["Canvas"], ["CLI"]],
    2: [["2026 年 4 月 2 日"], ["PixVerse V6"], ["Artificial Analysis"], ["image-to-video"], ["第一"], ["ELO 1,343"], ["$4.80/分钟"], ["VEO 3.1"], ["1,246"], ["$24.00/分钟"], ["Sora 2 Pro"], ["1,195.5"], ["$18.00/分钟"], ["榜单会更新"], ["最新"]],
    3: [["模式"], ["本来就想买"], ["177 个国家"], ["Freepik"], ["fal"], ["Replicate"]],
    4: [["AI 公司"], ["模型"], ["链上结算"], ["付费方式"]],
    5: [["权益", "credits", "分钟生成时长", "订阅"]],
    6: [["份额"]],
    7: [["PixVerse 官网"], ["定价", "价格"]],
    8: [["价格"], ["兑换之前"], ["本金"], ["退回"]],
    9: [["PixVerse"], ["兑换成功"], ["弹窗"], ["跳转按钮"]],
    10: [["PixVerse 账号"], ["使用"]],
    11: [],
    12: [["通用额度", "功能", "限定"]],
    13: [["PixVerse"], ["企业方案"], ["需求量大"], ["联系"]],
    14: [["合作关系"], ["PixVerse"], ["权益"], ["Moss"], ["发行"], ["结算"], ["本金"], ["合约"], ["碰不到"]],
    15: [["兑换码"], ["地址"], ["对应"], ["除此之外"], ["不涉及"]],
    16: [["本金"], ["合约"], ["赎回不受影响"], ["兑换码"], ["服务条款"]],
    17: [["没有 PixVerse 的代币", "不是 PixVerse 发币"], ["agent 的份额", "Agent 的份额"], ["PixVerse 的权益"]],
    18: [["兑换的权益", "兑换权益"], ["股权"], ["估值"]],
}

_DYNAMIC_RULES = {
    ("redemption", 1): ["consumer_brand_name"],
    ("redemption", 2): ["consumer_brand_name"],
    ("redemption", 7): ["consumer_minimum_mint_amount", "consumer_redemption_threshold"],
    ("redemption", 9): ["consumer_mint_fee"],
    ("redemption", 10): ["consumer_accept_token"],
    ("redemption", 13): ["consumer_redemption_threshold"],
    ("redemption", 19): ["consumer_redemption_code_expiry", "consumer_brand_name"],
    ("redemption", 20): ["consumer_brand_name"],
    ("redemption", 28): ["consumer_brand_name"],
    ("redemption", 29): ["consumer_brand_name"],
    ("redemption", 31): ["consumer_brand_name"],
    ("redemption", 32): ["consumer_brand_name"],
    ("redemption", 37): ["consumer_mint_fee", "consumer_refund_fee"],
    ("redemption", 47): ["consumer_official_support_channel", "consumer_brand_name"],
    ("redemption", 48): ["consumer_official_community_link", "consumer_support_email"],
    ("pixverse", 5): ["consumer_redemption_benefit"],
    ("pixverse", 6): ["consumer_redemption_threshold"],
    ("pixverse", 7): ["consumer_redemption_code_value"],
    ("pixverse", 8): ["consumer_price_comparison"],
    ("pixverse", 9): ["consumer_redemption_entry"],
    ("pixverse", 11): ["consumer_redemption_code_expiry"],
    ("pixverse", 12): ["consumer_feature_scope"],
    ("pixverse", 13): ["consumer_enterprise_eligibility"],
}

_FORBIDDEN = {
    ("redemption", 3): ["这是投资产品", "份额是投资产品"],
    ("redemption", 4): ["这是 NFT", "份额是 NFT"],
    ("redemption", 8): ["mint 直接给兑换码", "mint 后直接获得兑换码"],
    ("redemption", 10): ["可以更改结算代币"],
    ("redemption", 11): ["可以使用其他结算代币"],
    ("redemption", 23): ["已兑换份额可以赎回"],
    ("redemption", 27): ["赎回有次数限制"],
    ("redemption", 28): ["品牌方可以动用本金", "Moss 可以动用本金"],
    ("redemption", 29): ["品牌方可以动用本金"],
    ("redemption", 30): ["Moss 可以动用本金"],
    ("redemption", 43): ["已兑换份额可以赎回"],
    ("redemption", 44): ["持有份额会自动获得兑换码"],
    ("redemption", 45): ["保证固定本金", "保证固定金额"],
    ("redemption", 46): ["该产品有年化收益", "提供年化收益"],
    ("pixverse", 4): ["PixVerse 是加密项目"],
    ("pixverse", 14): ["PixVerse 可以动用本金", "Moss 可以动用本金"],
    ("pixverse", 17): ["PixVerse 发币", "存在 PixVerse 代币"],
    ("pixverse", 18): ["份额是 PixVerse 股权", "份额代表 PixVerse 估值"],
}

_CRITICAL_REDEMPTION = {3, 7, 9, 10, 21, 22, 23, 26, 28, 29, 30, 31, 32, 34, 37, 43, 45, 46}
_HIGH_REDEMPTION = {1, 2, 4, 5, 8, 11, 13, 14, 19, 20, 27, 33, 42, 44, 47, 48}
_CRITICAL_PIXVERSE = {2, 5, 6, 7, 8, 11, 12, 13, 14, 16, 17, 18}


@dataclass(frozen=True)
class ParsedConsumerGoldenSource:
    rows: list[dict[str, Any]]
    blockers: list[str]


def parse_consumer_golden_markdown(path: Path) -> ParsedConsumerGoldenSource:
    """Parse the approved Chinese Q&A blocks without rewriting their text."""
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    part: str | None = None
    counters = {"redemption": 0, "pixverse": 0}
    current: tuple[str, int, str] | None = None
    answer_chunks: list[str] | None = None

    def finish() -> None:
        nonlocal current, answer_chunks
        if current is None:
            return
        current_part, number, question = current
        answer = "\n".join(answer_chunks or []).strip()
        if not answer:
            blockers.append(f"{question}: excluded: ideal answer is empty")
        elif answer == _BUG_NOTE:
            blockers.append(
                f"{question}: excluded: source answer is a tester bug note, not an approved ideal answer"
            )
        else:
            row = _build_row(current_part, number, question, answer)
            if row is None:
                blockers.append(
                    f"{question}: case metadata or dynamic fact mapping is missing"
                )
            else:
                rows.append(row)
        current = None
        answer_chunks = None

    for line in lines:
        if line.startswith("第一部分："):
            finish()
            part = "redemption"
            continue
        if line.startswith("第二部分："):
            finish()
            part = "pixverse"
            continue
        if line.strip() == "---" or _SUBHEADING.match(line):
            finish()
            continue
        question_match = _QUESTION.match(line)
        if question_match:
            finish()
            if part is None:
                blockers.append(
                    f"{question_match.group('body')}: question appears before a recognized section"
                )
                continue
            counters[part] += 1
            current = (part, counters[part], question_match.group("body"))
            answer_chunks = None
            continue
        if current is None:
            continue
        answer_match = _ANSWER.match(line)
        if answer_match is None and answer_chunks is None:
            answer_match = _BARE_ANSWER.match(line)
        if answer_match:
            answer_chunks = [answer_match.group("body")]
        elif answer_chunks is not None:
            answer_chunks.append(line)
    finish()
    return ParsedConsumerGoldenSource(rows=rows, blockers=blockers)


def _build_row(
    part: str,
    number: int,
    question: str,
    answer: str,
) -> dict[str, Any] | None:
    area_map = _REDEMPTION_AREAS if part == "redemption" else _PIXVERSE_AREAS
    term_map = (
        _REDEMPTION_FACT_TERMS if part == "redemption" else _PIXVERSE_FACT_TERMS
    )
    if number not in area_map or number not in term_map:
        return None
    variables = list(
        dict.fromkeys(
            match.group("name")
            for match in _VARIABLE.finditer(question + "\n" + answer)
        )
    )
    rules = _DYNAMIC_RULES.get((part, number), [])
    if len(rules) != len(variables):
        return None
    prefix = "consumer_redemption" if part == "redemption" else "pixverse"
    tags = ["consumer", "redemption", area_map[number], "zh"]
    if part == "pixverse":
        tags.extend(["pixverse", "brand:pixverse"])
    row: dict[str, Any] = {
        "id": f"{prefix}_q{number:02d}_zh",
        "source_question_id": f"{part}-Q{number}",
        "question": question,
        "ideal_answer": answer,
        "locale": "zh",
        "area": area_map[number],
        "required_fact_groups": term_map[number],
        "forbidden_claims": _FORBIDDEN.get((part, number), []),
        "requires_rag": True,
        "requires_tool": (
            "marketplace_agent_context" if variables or part == "pixverse" else None
        ),
        "risk_level": _risk_level(part, number),
        "quality_axes": [
            "correctness",
            "completeness",
            "data_faithfulness",
            "language_consistency",
        ],
        "applicable_agent_types": ["consumer"],
        "tags": tags,
    }
    if variables:
        row["dynamic_fact_variables"] = variables
        row["dynamic_fact_rules"] = rules
    if part == "pixverse":
        row["applicable_agent_brands"] = ["pixverse"]
    return row


def _risk_level(part: str, number: int) -> str:
    if part == "redemption":
        if number in _CRITICAL_REDEMPTION:
            return "critical"
        if number in _HIGH_REDEMPTION:
            return "high"
        return "medium"
    return "critical" if number in _CRITICAL_PIXVERSE else "high"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parsed = parse_consumer_golden_markdown(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in parsed.rows
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"rows": len(parsed.rows), "blockers": parsed.blockers},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if parsed.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
