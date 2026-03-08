'use client';

import { useState } from 'react';

const createSessionId = () => (globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`);

const DEMO_QUESTIONS = [
  '我是本科生，想打印在学证明，需要去哪里？',
  '本科生办理休学要怎么做，需要准备什么材料？',
  '我复学是不是开学第二周前都可以提交申请？',
  '我想打证明。',
];

const STATUS_TEXT = {
  answer: '正常回答',
  follow_up: '追问',
  refuse: '拒答',
};

const statusClass = {
  answer: 'border-moss/20 bg-moss/10 text-moss',
  follow_up: 'border-amber-700/20 bg-amber-500/10 text-amber',
  refuse: 'border-danger/20 bg-danger/10 text-danger',
};

const emptyResult = {
  item_id: 'UG_PROOF_PRINT',
  slots: {},
  action: 'answer',
  evidence_cards: [],
  official_links: [],
  flow_skeleton: null,
  assertions: [],
  final_answer: '',
};

function Bubble({ role, label, text }) {
  const isUser = role === 'user';
  return (
    <div className={`max-w-[92%] rounded-[24px] border px-5 py-4 ${isUser ? 'ml-auto border-moss/10 bg-gradient-to-br from-moss to-[#0f4d39] text-stone-50' : 'border-black/10 bg-white/75'}`}>
      <div className={`mb-2 text-[11px] uppercase tracking-[0.16em] ${isUser ? 'text-stone-200' : 'text-slate-500'}`}>{label}</div>
      <p className="whitespace-pre-wrap text-[15px] leading-7">{text}</p>
    </div>
  );
}

function SectionCard({ title, children }) {
  return (
    <div className="rounded-[22px] border border-black/10 bg-white/80 p-4 shadow-panel">
      <h3 className="mb-3 font-display text-xl text-ink">{title}</h3>
      {children}
    </div>
  );
}

export default function Page() {
  const [query, setQuery] = useState('');
  const [pending, setPending] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'system', label: 'System', text: '请输入问题，或直接点击 4 个固定演示问题。' },
  ]);
  const [result, setResult] = useState(emptyResult);
  const [sessionId] = useState(createSessionId);

  async function runQuery(nextQuery) {
    const text = nextQuery.trim();
    if (!text) return;

    setPending(true);
    setMessages((prev) => [...prev, { role: 'user', label: 'User', text }]);

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, session_id: sessionId }),
      });
      const raw = await response.text();
      let data;
      try {
        data = raw ? JSON.parse(raw) : null;
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(data?.error || `请求失败（${response.status}）`);
      }
      if (!data) {
        throw new Error('服务返回了空响应');
      }

      setResult(data);
      setMessages((prev) => [...prev, { role: 'assistant', label: 'Assistant', text: data.final_answer }]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', label: 'Assistant', text: `请求失败：${error.message}` }]);
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    const text = query;
    setQuery('');
    runQuery(text);
  }

  const flow = result.flow_skeleton;
  const slotEntries = Object.entries(result.slots || {}).filter(([, value]) => value);

  return (
    <main className="mx-auto min-h-screen max-w-[1500px] px-4 py-6 md:px-7">
      <header className="mb-6 flex flex-col justify-between gap-6 rounded-[32px] border border-black/10 bg-gradient-to-br from-[#fffaf1] to-[#f6ecde] p-6 shadow-panel lg:flex-row lg:items-start">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-moss">Flow-Aware Campus RAG</p>
          <h1 className="font-display text-4xl leading-tight md:text-5xl">流程感知校园办事原型台</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600 md:text-base">
            两个受控事项、本地证据包、证据约束流程骨架、断言核验。
          </p>
        </div>
        <div className="max-w-md rounded-[24px] border border-black/10 bg-white/70 p-4">
          <div className={`inline-flex rounded-full border px-4 py-2 text-sm font-semibold ${statusClass[result.action] || statusClass.answer}`}>
            {STATUS_TEXT[result.action] || result.action}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            当前会话会保留必要上下文，追问后的补充信息会继续完成同一事项。
          </p>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-[30px] border border-black/10 bg-white/70 pb-5 shadow-panel">
          <div className="flex flex-col gap-4 px-6 pt-6 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-moss">Left / Chat</p>
              <h2 className="font-display text-3xl">对话与控制台</h2>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-700">
              {['Rule First', 'Hybrid Retrieval', 'LLM Constrained', 'Assertion Check'].map((chip) => (
                <span key={chip} className="rounded-full border border-black/10 bg-white/80 px-3 py-2">
                  {chip}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3 px-6 pt-5">
            {DEMO_QUESTIONS.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => runQuery(question)}
                className="rounded-full border border-black/10 bg-white/80 px-4 py-3 text-left text-sm transition hover:-translate-y-0.5 hover:border-moss/30 hover:shadow-panel"
              >
                {question}
              </button>
            ))}
          </div>

          <div className="mx-6 mt-5 flex max-h-[640px] min-h-[540px] flex-col gap-3 overflow-auto rounded-[24px] border border-black/10 bg-[#fbf7f0]/85 p-4 lg:min-h-[620px]">
            {messages.map((message, index) => (
              <Bubble key={`${message.role}-${index}`} role={message.role === 'assistant' ? 'assistant' : message.role} label={message.label} text={message.text} />
            ))}
          </div>

          <form onSubmit={onSubmit} className="px-6 pt-4">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={4}
              placeholder="例如：本科生办理休学需要几步？因病休学要填什么？"
              className="w-full rounded-[24px] border border-black/10 bg-white/85 px-5 py-4 text-[15px] outline-none ring-0 placeholder:text-slate-400 focus:border-moss/30"
            />
            <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <button
                type="submit"
                disabled={pending}
                className="rounded-full bg-gradient-to-br from-moss to-[#0f4d39] px-5 py-3 text-sm font-semibold text-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {pending ? '处理中...' : '提交查询'}
              </button>
            </div>
          </form>
        </section>

        <section className="grid gap-5">
          <article className="rounded-[30px] border border-black/10 bg-white/70 pb-5 shadow-panel">
            <div className="flex flex-col gap-4 px-6 pt-6 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-moss">Right / Package</p>
                <h2 className="font-display text-3xl">事项证据包</h2>
              </div>
              <span className="rounded-full border border-moss/20 bg-moss/10 px-3 py-2 text-xs font-bold text-moss">{result.item_id || '-'}</span>
            </div>

            <div className="flex flex-wrap gap-2 px-6 pt-5">
              {slotEntries.length ? slotEntries.map(([key, value]) => (
                <span key={key} className="rounded-full border border-black/10 bg-black/5 px-3 py-2 text-xs text-slate-700">
                  {key}: {String(value)}
                </span>
              )) : <div className="rounded-[20px] border border-dashed border-black/15 px-4 py-4 text-sm text-slate-500">当前未抽取到稳定槽位。</div>}
            </div>

            <div className="px-6 pt-5">
              <SectionCard title="官方入口与下载">
                {(result.official_links || []).length ? (
                  <div className="grid gap-3">
                    {result.official_links.map((link) => (
                      <a
                        key={`${link.url}-${link.label}`}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-[18px] border border-black/10 bg-white/90 px-4 py-3 text-sm leading-6 text-slate-700 transition hover:border-moss/30 hover:text-moss"
                      >
                        <div className="font-semibold text-ink">{link.label}</div>
                        <div className="text-xs text-slate-500">{link.source_title}</div>
                        <div className="mt-1 break-all text-xs text-moss">{link.url}</div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">当前问题没有可直接展示的官方入口。</div>
                )}
              </SectionCard>
            </div>

            <div className="grid gap-3 px-6 pt-5">
              {(result.evidence_cards || []).map((card) => (
                <div key={card.evidence_id} className="rounded-[22px] border border-black/10 bg-white/85 p-4">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-moss/10 px-2.5 py-1 font-bold text-moss">{card.evidence_id}</span>
                    <span className="rounded-full bg-clay/10 px-2.5 py-1 font-bold text-clay">{card.chunk_type}</span>
                    <span className="rounded-full bg-black/5 px-2.5 py-1 font-bold text-slate-600">score {card.score}</span>
                  </div>
                  <h3 className="mt-3 font-display text-xl">{card.source_title}</h3>
                  <p className="mt-2 text-sm leading-7 text-slate-700">{card.content}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                    {(card.keywords || []).slice(0, 5).map((tag) => (
                      <span key={tag} className="rounded-full bg-black/5 px-2.5 py-1">{tag}</span>
                    ))}
                  </div>
                  <div className="mt-3 text-xs leading-6 text-slate-500">
                    audience: {card.audience || '-'} · publish: {card.publish_date || '未标注'} · source: {card.source_type}
                  </div>
                  <a href={card.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-semibold text-moss hover:underline">
                    打开原文
                  </a>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-[30px] border border-black/10 bg-white/70 pb-5 shadow-panel">
            <div className="px-6 pt-6">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-moss">Right / Skeleton</p>
              <h2 className="font-display text-3xl">流程骨架</h2>
            </div>
            <div className="grid gap-3 px-6 pt-5">
              {flow ? [
                ['适用对象', flow.applicable_audience],
                ['前置条件', flow.preconditions],
                ['步骤', flow.steps],
                ['材料', flow.materials],
                ['时间约束', flow.time_constraints],
                ['入口', flow.entry],
                ['办理位置', flow.service_location],
                ['备注', flow.notes],
                ['冲突提示', flow.conflicts],
              ].map(([title, value]) => (
                <SectionCard key={title} title={title}>
                  {Array.isArray(value) ? (
                    <ol className="space-y-2 pl-5 text-sm leading-7 text-slate-700">
                      {value.map((entry, index) => (
                        <li key={`${title}-${index}`}>
                          {entry.text}
                          <div className="text-xs text-slate-500">[{(entry.evidence_ids || []).join(', ') || 'no-evidence'}]</div>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <>
                      <p className="text-sm leading-7 text-slate-700">{value?.text}</p>
                      <div className="mt-2 text-xs text-slate-500">[{(value?.evidence_ids || []).join(', ') || 'no-evidence'}]</div>
                    </>
                  )}
                </SectionCard>
              )) : <div className="rounded-[22px] border border-dashed border-black/15 px-4 py-5 text-sm text-slate-500">提交问题后显示流程骨架。</div>}
            </div>
          </article>

          <article className="rounded-[30px] border border-black/10 bg-white/70 pb-5 shadow-panel">
            <div className="px-6 pt-6">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-moss">Right / Verification</p>
              <h2 className="font-display text-3xl">断言核验</h2>
            </div>
            <div className="grid gap-3 px-6 pt-5">
              {(result.assertions || []).map((assertion) => (
                <div key={assertion.assertion_id} className="rounded-[22px] border border-black/10 bg-white/85 p-4">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-moss/10 px-2.5 py-1 font-bold text-moss">{assertion.assertion_id}</span>
                    <span className="rounded-full bg-black/5 px-2.5 py-1 font-bold text-slate-600">{assertion.field}</span>
                    <span className={`rounded-full px-2.5 py-1 font-bold ${assertion.status === 'supported' ? 'bg-moss/10 text-moss' : assertion.status === 'insufficient' ? 'bg-amber-500/10 text-amber' : 'bg-danger/10 text-danger'}`}>
                      {assertion.status}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-xl">{assertion.text}</h3>
                  <p className="mt-2 text-sm leading-7 text-slate-700">{assertion.reason}</p>
                  <div className="mt-3 text-xs text-slate-500">evidence: {(assertion.evidence_ids || []).join(', ') || 'none'}</div>
                </div>
              ))}
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
