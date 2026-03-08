import { getEvidenceById } from '../../../../lib/evidence';

export async function GET(_request, { params }) {
  const { evidenceId } = await params;
  const evidence = getEvidenceById(evidenceId);
  if (!evidence) {
    return new Response('Not found', { status: 404 });
  }

  const content = [
    `evidence_id: ${evidence.evidence_id}`,
    `source_title: ${evidence.source_title}`,
    `source_url: ${evidence.source_url}`,
    `publish_date: ${evidence.publish_date || '未标注'}`,
    `effective_term: ${evidence.effective_term || '未标注'}`,
    `audience: ${evidence.audience || '未标注'}`,
    `source_type: ${evidence.source_type}`,
    `source_level: ${evidence.source_level}`,
    `chunk_type: ${evidence.chunk_type}`,
    '',
    evidence.content,
  ].join('\n');

  return new Response(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="${evidence.evidence_id}.txt"`,
    },
  });
}
