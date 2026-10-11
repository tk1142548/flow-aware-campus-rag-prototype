"""Run the deterministic Stage 3 sparse baseline on development queries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backend.stage3_engine import Stage3Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', action='append', required=True)
    parser.add_argument('--item', required=True)
    parser.add_argument('--source', action='append')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    engine = Stage3Engine(ROOT)
    source_ids = set(args.source) if args.source else None
    rows = [engine.query(args.item, query, source_ids, top_k=args.top_k) for query in args.query]
    payload = {'config_id': 'STAGE3_SPARSE_BASELINE_V1', 'status': '已验证',
               'formal_evaluation_enabled': False, 'results': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'query_count': len(rows), 'hit_counts': [len(row['hits']) for row in rows]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
