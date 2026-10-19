import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd().includes(`${path.sep}app${path.sep}frontend`)
  ? path.resolve(process.cwd(), '..', '..')
  : process.cwd();

const researchDir = path.join(root, 'data', 'research');

let cache = null;

function readJsonl(file) {
  return fs.readFileSync(path.join(researchDir, file), 'utf8')
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

// Flatten an evidence unit and its source record into the fields the source page shows.
function toCard(row, source) {
  const publication = source?.publication || {};
  return {
    evidence_id: row.evidence_id,
    item_id: row.item_id,
    chunk_type: row.claim_type,
    content: row.verbatim_text,
    source_title: source?.title || '',
    source_url: source?.canonical_url || '',
    publish_date: publication.date || '',
    effective_term: source?.version?.label || row.applicability?.term_label || '',
    audience: (row.audience || []).join('、'),
    source_type: source?.content_format || '',
    source_level: source?.authority_level || '',
    location_hint: row.source_locator?.section || '',
  };
}

export function loadEvidenceMap() {
  if (cache) return cache;
  const sources = new Map(readJsonl('source_records.jsonl').map((row) => [row.source_id, row]));
  const map = new Map();
  readJsonl('evidence_units.jsonl').forEach((row) => {
    map.set(row.evidence_id, toCard(row, sources.get(row.source_id)));
  });
  cache = map;
  return map;
}

export function getEvidenceById(evidenceId) {
  return loadEvidenceMap().get(evidenceId) || null;
}
