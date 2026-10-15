"""Preflight probe for the three endpoints used by every experiment.

Checks that generation, embedding and rerank all answer before a long run
starts. A run that begins while the endpoint is down silently turns transport
failures into empty answers, so this must pass first.

Usage:
    python scripts/probe_endpoints.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient

PROBE_DOCS = ["成绩单可在自助打印系统打印", "休学需要提交申请表与家长意见"]


def main() -> int:
    client = ApiClient(ROOT / "data/cache")
    print(f"接口：{client.base_url}")
    print(f"生成模型：{client.chat_model}　嵌入：{client.embed_model}　重排：{client.rerank_model}")
    print(f"密钥已配置：{client.enabled}")
    failures = 0

    try:
        text = client.chat([{"role": "user", "content": "回复两个字：正常"}], max_tokens=8)
        print(f"生成：正常 -> {text.strip()[:40]}")
    except Exception as error:  # noqa: BLE001 - reported, not swallowed
        failures += 1
        print(f"生成：失败 -> {type(error).__name__}: {str(error)[:300]}")

    try:
        vectors = client.embed(["测试文本"])
        print(f"嵌入：正常 -> 维度 {len(vectors[0])}")
    except Exception as error:  # noqa: BLE001
        failures += 1
        print(f"嵌入：失败 -> {type(error).__name__}: {str(error)[:300]}")

    try:
        ranked = client.rerank("成绩单怎么打印", PROBE_DOCS)
        print(f"重排：正常 -> {ranked}")
    except Exception as error:  # noqa: BLE001
        failures += 1
        print(f"重排：失败 -> {type(error).__name__}: {str(error)[:300]}")

    print(f"探活失败项：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
