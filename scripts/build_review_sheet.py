"""Build the human review sheet for the confirmation-set draft.

Each row shows the question, the proposed response mode, the proposed key points
resolved to text, and the official evidence text the points rest on. The reviewer
answers five questions per row that can each be checked against that text.

Usage:
    python scripts/build_review_sheet.py --pilot 10     # a stratified pilot
    python scripts/build_review_sheet.py                # every remaining draft
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.research_data import ResearchRepository

DRAFT = ROOT / "data/evaluation/confirm-draft.jsonl"
OUT_DIR = ROOT / "data/evaluation/review"

MODE_LABEL = {
    "answer": "直接回答", "conversation_resolution": "直接回答（多轮）",
    "scoped_correction": "纠正", "clarification": "追问",
    "version_qualified": "按版本作答", "abstention": "拒答",
}

COLUMNS = [
    "样本号", "学生的话", "建议的应答方式", "建议的追问", "建议的要点（编号：内容）",
    "相关官方原文（编号：原文）",
    "Q1 问句自然吗（是/否）", "Q2 前提成立吗（是/否）",
    "Q3 应答方式（直接回答/纠正/追问/按版本作答/拒答）",
    "Q4 无原文依据、应划掉的要点编号（用逗号分隔，没有就空着）",
    "Q5 缺少的必须要点（写一句话并注明证据编号，没有就空着）",
    "备注（标准哪里说不清、题目哪里别扭）",
]


def key_points(repository, sample) -> list[tuple[str, str]]:
    gold = sample["gold"]
    process = repository.processes.get(sample["process_id"]) if sample["process_id"] else None
    if not process:
        return []
    claims = {c["claim_id"]: c["text"] for c in process["allowed_claims"]}
    steps = {s["step_id"]: f"{s.get('actor', '')}{s['action']}" for s in process["steps"]}
    materials = {m["material_id"]: m["name"] for m in process.get("materials", [])}
    points = [(f"步骤{i}", steps[sid]) for i, sid in enumerate(gold["ordered_step_ids"], 1)
              if sid in steps]
    points += [(f"材料{i}", materials[mid]) for i, mid in enumerate(gold["material_ids"], 1)
               if mid in materials]
    points += [(f"要点{i}", claims[cid]) for i, cid in enumerate(gold["allowed_claim_ids"], 1)
               if cid in claims]
    return points


def related_evidence(repository, sample) -> list[tuple[str, str]]:
    """Evidence behind the gold, plus the rest of the process's evidence for context."""
    ids = list(sample["gold"]["supporting_evidence_ids"])
    process = repository.processes.get(sample["process_id"]) if sample["process_id"] else None
    if process:
        for identity in process["evidence_snapshot"]["evidence_ids"]:
            if identity not in ids:
                ids.append(identity)
    seen_text: set[str] = set()
    rows = []
    for identity in ids:
        row = repository.evidence.get(identity)
        if not row or row["verbatim_text"] in seen_text:
            continue
        seen_text.add(row["verbatim_text"])
        rows.append((identity, row["verbatim_text"]))
    return rows


def sheet_row(repository, sample) -> dict:
    gold = sample["gold"]
    speaker = {"user": "学生", "assistant": "助手"}
    dialogue = "\n".join(f"{speaker[t['role']]}：{t['text']}" for t in sample["conversation"])
    points = key_points(repository, sample)
    evidence = related_evidence(repository, sample)
    return {
        "样本号": sample["sample_id"],
        "学生的话": dialogue,
        "建议的应答方式": MODE_LABEL[gold["response_mode"]],
        "建议的追问": gold["follow_up_question"] or "",
        "建议的要点（编号：内容）": "\n".join(f"{k}：{v}" for k, v in points) or "（无）",
        "相关官方原文（编号：原文）": "\n".join(f"[{k}] {v}" for k, v in evidence)
                                     or "（现有官方材料不涉及）",
        **{column: "" for column in COLUMNS[6:]},
    }


def pilot(samples: list[dict], n: int) -> list[dict]:
    """One per kind first, then fill from the largest kinds, deterministically."""
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        by_kind[sample["leakage_control"]["notes"].split("；")[0]].append(sample)
    rng = random.Random(20261019)
    for group in by_kind.values():
        rng.shuffle(group)
    chosen = [group.pop() for _, group in sorted(by_kind.items())]
    while len(chosen) < n:
        kind = max(by_kind, key=lambda k: len(by_kind[k]))
        chosen.append(by_kind[kind].pop())
    return chosen[:n]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=int, default=0)
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    samples = [json.loads(line) for line in DRAFT.read_text(encoding="utf-8").splitlines() if line]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.pilot:
        chosen = pilot(samples, args.pilot)
        path = OUT_DIR / "task1-pilot.csv"
    else:
        done = set()
        pilot_path = OUT_DIR / "task1-pilot.csv"
        if pilot_path.exists():
            with pilot_path.open(encoding="utf-8-sig") as handle:
                done = {row["样本号"] for row in csv.DictReader(handle)}
        chosen = [s for s in samples if s["sample_id"] not in done]
        path = OUT_DIR / "task2-review.csv"

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for sample in chosen:
            writer.writerow(sheet_row(repository, sample))
    print(f"{len(chosen)} 条 -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
