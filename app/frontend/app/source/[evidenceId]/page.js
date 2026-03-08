import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getEvidenceById } from '../../../lib/evidence';

export default async function EvidenceSourcePage({ params }) {
  const { evidenceId } = await params;
  const evidence = getEvidenceById(evidenceId);
  if (!evidence) notFound();

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-8 md:px-6">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-6 shadow-panel">
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs">
          <span className="rounded-full bg-moss/10 px-3 py-1 font-bold text-moss">{evidence.evidence_id}</span>
          <span className="rounded-full bg-clay/10 px-3 py-1 font-bold text-clay">{evidence.chunk_type}</span>
          <span className="rounded-full bg-black/5 px-3 py-1 text-slate-600">{evidence.item_id}</span>
        </div>
        <h1 className="font-display text-4xl leading-tight text-ink">{evidence.source_title}</h1>
        <p className="mt-3 text-sm leading-7 text-slate-600">此页展示本系统收录的官方摘录和来源信息。</p>
        <section className="mt-6 rounded-[22px] border border-black/10 bg-[#fbf7f0] p-5">
          <h2 className="font-display text-2xl text-ink">摘录内容</h2>
          <p className="mt-3 whitespace-pre-wrap text-[15px] leading-8 text-slate-700">{evidence.content}</p>
        </section>
        <section className="mt-6 grid gap-3 md:grid-cols-2">
          <div className="rounded-[22px] border border-black/10 bg-white p-5">
            <h2 className="font-display text-2xl text-ink">来源信息</h2>
            <div className="mt-3 space-y-2 text-sm leading-7 text-slate-700">
              <div>publish_date: {evidence.publish_date || '未标注'}</div>
              <div>effective_term: {evidence.effective_term || '未标注'}</div>
              <div>audience: {evidence.audience || '未标注'}</div>
              <div>source_type: {evidence.source_type}</div>
              <div>source_level: {evidence.source_level}</div>
              <div>location_hint: {evidence.location_hint || '未标注'}</div>
            </div>
          </div>
          <div className="rounded-[22px] border border-black/10 bg-white p-5">
            <h2 className="font-display text-2xl text-ink">官方地址</h2>
            <p className="mt-3 break-all text-sm leading-7 text-slate-700">{evidence.source_url}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <a href={evidence.source_url} target="_blank" rel="noreferrer" className="rounded-full border border-black/10 bg-black/5 px-4 py-2 text-sm text-ink hover:border-moss/30 hover:text-moss">尝试打开官网原地址</a>
              <Link href={`/source/${evidence.evidence_id}/download`} className="rounded-full bg-moss px-4 py-2 text-sm font-semibold text-white">下载摘录文本</Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
