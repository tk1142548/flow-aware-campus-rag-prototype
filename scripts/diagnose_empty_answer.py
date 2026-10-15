"""Diagnose why a configuration produced no answer.

Reproduces a single (sample, configuration) run and prints the raw model reply,
the parsed keys and the finish reason, so a missing answer can be told apart from
a slow endpoint, a quota failure and a reply that was cut off mid-JSON.

Usage:
    python scripts/diagnose_empty_answer.py --sample ISE-CR-011 --mode ablation_no_verify
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from app.backend import systems
from app.backend.api_client import ApiClient
from app.backend.flow_extractor import extract as extract_flow
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_stack import RetrievalStack
from scripts.run_baselines import CONFIGS, USES_SKELETON, question_of


def raw_chat(client: ApiClient, messages, max_tokens: int) -> tuple[str, str]:
    payload = {"model": client.chat_model, "messages": list(messages),
               "temperature": 0.0, "max_tokens": max_tokens}
    response = httpx.post(f"{client.base_url}/chat/completions",
                          headers=client._headers(), json=payload, timeout=client.timeout)
    data = response.json()
    choice = data["choices"][0]
    return choice["message"]["content"], choice.get("finish_reason", "?")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--dataset", type=Path,
                        default=ROOT / "data/evaluation/independent-set.jsonl")
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    samples = [json.loads(line) for line in
               args.dataset.read_text(encoding="utf-8").splitlines() if line]
    sample = next(s for s in samples if s["sample_id"] == args.sample)
    question = question_of(sample)
    stack = RetrievalStack(repository.all_verified_evidence(), client, alpha=0.5)
    spec = CONFIGS[args.mode]
    rows = stack.retrieve(question, strategy=spec["strategy"], k=spec["k"])

    print(f"样本 {args.sample}　配置 {args.mode}　扫描 {len(rows)} 条证据")
    if args.mode in USES_SKELETON:
        skeleton = extract_flow(client, question, rows)
        print(f"流程骨架要素数：{ {k: len(v) for k, v in skeleton.items() if isinstance(v, list)} }")
    else:
        skeleton = None

    if args.mode == "ablation_no_verify":
        system, user, budget = systems.METHOD_SYSTEM, systems.METHOD_USER.format(
            skeleton=systems._skeleton_text(skeleton),
            evidence=systems.evidence_block(rows), question=question,
            mode_guide=systems.MODE_GUIDE), 2000
    elif args.mode == "ablation_no_skeleton":
        system, user, budget = systems.METHOD_SYSTEM, systems.METHOD_USER.format(
            skeleton=systems._skeleton_text(None), evidence=systems.evidence_block(rows),
            question=question, mode_guide=systems.MODE_GUIDE), 2000
    else:
        raise SystemExit("该诊断脚本目前只覆盖 _method_pass 路径的配置")

    text, finish = raw_chat(client, [{"role": "system", "content": system},
                                     {"role": "user", "content": user}], budget)
    print(f"max_tokens={budget}　finish_reason={finish}　回复字符数={len(text)}")
    print("---- 回复尾部 ----")
    print(text[-400:])
    try:
        parsed = systems.__dict__["_json_or_empty"](client, system, user, budget)
        print(f"---- 解析结果 keys={list(parsed)} answer 长度="
              f"{len(str(parsed.get('answer') or ''))}")
    except Exception as error:  # noqa: BLE001
        print(f"解析抛错：{type(error).__name__}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
