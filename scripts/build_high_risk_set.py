"""Build the high-risk set: version conflict / audience mismatch / missing
information / expired entry.

Three of the four categories already exist in the dev set and are selected as-is.
The fourth, 过期入口, had **no samples at all** because source availability
(HTTP 410/403, authentication redirects) is recorded in `source_records` but
never entered the retrievable evidence layer. The samples authored here work
around that by asking about *document-version validity* using evidence that does
exist, and each carries a narrow single-claim gold so the score stays meaningful.

The file is separate from `stage2_samples.jsonl` on purpose: that file is
hash-frozen and must not change.

Usage:
    python scripts/build_high_risk_set.py [--output PATH]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RISK_BY_SCENARIO = {
    "version_conflict": "版本冲突",
    "object_mismatch": "对象错配",
    "condition_missing": "信息缺失",
}

# (sample_id, item, process, claim_id, evidence_id, question, boundary)
AUTHORED_EXPIRED_ENTRY = [
    (
        "HRE-EXP-001", "UG_WITHDRAWAL", "PROC_UG_WITHDRAWAL_V003", "CLM_009", "UGW062",
        "2011 年那张退学申请表上写着集中受理是期末第 13 到第 16 周，现在还是这个时间吗？",
        "该时段出自 2011 年 11 月版历史表格；来源未声明与其他版本的替代关系，"
        "只能说明该版本自身的受理时段，不得断言其现仍统一适用。",
    ),
    (
        "HRE-EXP-002", "UG_WITHDRAWAL", "PROC_UG_WITHDRAWAL_V005", "CLM_021", "UGW095",
        "清退材料是每年 4 月 10 日下午 5 点前交吗？",
        "该报送期限出自 2026 年春季清退通知，属该学期时限；不得推广到其他学期。",
    ),
    (
        "HRE-EXP-003", "UG_STUDENT_CARD_REISSUE", "PROC_UG_STUDENT_CARD_V001", "CLM_006",
        "UGT006",
        "学生证补办要去石牌校区行政办公楼 827 交 3 元工本费，这个入口现在还有效吗？",
        "该地点与费用出自更新于 2019-04-18 的页面；地点、费用属易变信息，"
        "须绑定来源更新时间与快照日期，不得断言当前仍然有效。",
    ),
    (
        "HRE-EXP-004", "UG_WITHDRAWAL", "PROC_UG_WITHDRAWAL_V001", "CLM_002", "UGW003",
        "退学还是把书面申请交给学院教务秘书处吗？我在 2019 年的流程页上看到的。",
        "该步骤出自更新于 2019-04-18 的流程页；须说明依据的来源版本，"
        "未获证据支持的现行版本不能确认为事实。",
    ),
]


def select_existing(samples: list[dict]) -> list[dict]:
    selected = []
    for sample in samples:
        risk = RISK_BY_SCENARIO.get(sample["scenario_type"])
        if not risk:
            continue
        selected.append({
            "sample_id": sample["sample_id"],
            "origin": "dev_set_selection",
            "risk_category": risk,
            "scenario_type": sample["scenario_type"],
            "item_id": sample["item_id"],
            "process_id": sample["process_id"],
            "difficulty": sample["difficulty"],
            "version_risk": sample["version_risk"],
            "conversation": sample["conversation"],
            "gold": sample["gold"],
            "input_context": sample["input_context"],
        })
    return selected


def author_expired_entry(repository) -> list[dict]:
    authored = []
    for sample_id, item_id, process_id, claim_id, evidence_id, question, boundary in AUTHORED_EXPIRED_ENTRY:
        process = repository.processes[process_id]
        claim = next(c for c in process["allowed_claims"] if c["claim_id"] == claim_id)
        if evidence_id not in process["evidence_snapshot"]["evidence_ids"]:
            raise ValueError(f"{sample_id}: {evidence_id} not in {process_id} snapshot")
        if claim["evidence_ids"] != [evidence_id]:
            raise ValueError(f"{sample_id}: claim {claim_id} does not bind {evidence_id}")
        authored.append({
            "sample_id": sample_id,
            "origin": "authored_2026-10-14",
            "risk_category": "过期入口",
            "scenario_type": "version_conflict",
            "item_id": item_id,
            "process_id": process_id,
            "difficulty": "hard",
            "version_risk": "version_sensitive",
            "conversation": [{"turn_id": "T01", "role": "user", "text": question}],
            "input_context": {"provided_slots": [], "requested_as_of": None,
                              "source_version_ids": []},
            "gold": {
                "response_mode": "version_qualified",
                "target_item_id": item_id,
                "required_slot_ids": [],
                "missing_slot_ids": [],
                "follow_up_question": None,
                "ordered_step_ids": [],
                "material_ids": [],
                "allowed_claim_ids": [claim_id],
                "supporting_evidence_ids": [evidence_id],
                "prohibited_claims": ["把该版本的条件断言为现行统一规则",
                                      "对未获来源支持的新版本作确定性表述"],
                "answer_boundary": boundary,
            },
        })
    return authored


def main() -> int:
    import sys
    sys.path.insert(0, str(ROOT))
    from app.backend.research_data import ResearchRepository

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/evaluation/high-risk-set.jsonl")
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    dev = [json.loads(line) for line in
           (ROOT / "data/evaluation/stage2_samples.jsonl").read_text(encoding="utf-8").splitlines()
           if line]

    selected = select_existing(dev)
    authored = author_expired_entry(repository)
    records = selected + authored

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records) + "\n",
        encoding="utf-8", newline="\n",
    )

    counts = Counter(r["risk_category"] for r in records)
    print(f"高风险集: {len(records)} 条 -> {args.output.name}")
    print(f"  选自开发集: {len(selected)}")
    print(f"  新编过期入口: {len(authored)}")
    for name, count in counts.most_common():
        print(f"  {name:8s} {count}")
    print(f"  built_at {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
