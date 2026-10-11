"""Audit semantic near duplicates with DashScope text-embedding-v4."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import requests
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings'


def embedding_batch(texts: list[str], key: str) -> list[list[float]]:
    for attempt in range(3):
        try:
            response = requests.post(ENDPOINT, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                                     json={'model': 'text-embedding-v4', 'input': texts}, timeout=90)
            response.raise_for_status()
            data = response.json()['data']
            return [row['embedding'] for row in sorted(data, key=lambda row: row['index'])]
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    return dot / (norm_left * norm_right)


def audit(samples: list[dict], key: str, batch_size: int = 10, threshold: float = 0.92) -> dict:
    texts = ['\n'.join(turn['text'] for turn in row['conversation']) for row in samples]
    batches = [texts[start:start + batch_size] for start in range(0, len(texts), batch_size)]
    vectors = [vector for batch in batches for vector in embedding_batch(batch, key)]
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    similarities = matrix @ matrix.T
    pairs = [{'sample_id': samples[index]['sample_id'], 'other_sample_id': samples[other_index]['sample_id'],
              'cosine': round(float(similarities[index, other_index]), 8)}
             for index in range(len(samples)) for other_index in range(index)
             if similarities[index, other_index] >= threshold]
    nearest = [{'sample_id': samples[index]['sample_id'],
                'nearest_sample_id': samples[int(np.argmax(similarities[index, :index]))]['sample_id'],
                'cosine': round(float(np.max(similarities[index, :index])), 8)}
               for index in range(1, len(samples))]
    return {'status': '阻塞' if pairs else '已完成待验证', 'model': 'text-embedding-v4',
            'sample_count': len(samples), 'threshold': threshold,
            'near_duplicate_pair_count': len(pairs), 'near_duplicate_pairs': pairs,
            'nearest_neighbors': sorted(nearest, key=lambda row: -row['cosine'])[:50]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threshold', type=float, default=0.92)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get('DASHSCOPE_API_KEY')
    if not key:
        raise SystemExit('DASHSCOPE_API_KEY is required')
    samples = [json.loads(line) for line in (ROOT / 'data/evaluation/stage2_samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    result = audit(samples, key, threshold=args.threshold)
    result['api_key_logged'] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'model', 'sample_count', 'threshold', 'near_duplicate_pair_count')}, ensure_ascii=False))
    return 1 if result['status'] == '阻塞' else 0


if __name__ == '__main__':
    raise SystemExit(main())
