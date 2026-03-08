import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd().includes(`${path.sep}app${path.sep}frontend`)
  ? path.resolve(process.cwd(), '..', '..')
  : process.cwd();

const evidencePath = path.join(root, 'data', 'evidence', 'evidence_units.jsonl');

let cache = null;

export function loadEvidenceMap() {
  if (cache) return cache;
  const raw = fs.readFileSync(evidencePath, 'utf8');
  const map = new Map();
  raw.split(/\r?\n/).filter(Boolean).forEach((line) => {
    const row = JSON.parse(line);
    map.set(row.evidence_id, row);
  });
  cache = map;
  return map;
}

export function getEvidenceById(evidenceId) {
  return loadEvidenceMap().get(evidenceId) || null;
}
