import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ExternalLink, Maximize2, Minimize2, Network, RefreshCw } from 'lucide-react';
import { apiGet, artifactContentUrl } from './api';
import { t } from './i18n';
import { usePageQuery } from './pageState';

// Research maps are maintained by hand by research agents (bbox map / SDK / API).
// This module only renders them. Structure and narrative come from the map; evidence
// (metrics, quality gate, artifacts, decision notes) is read from the bound entity by the API.

export const FAMILIES = {
  active: { label: 'In progress', color: 'var(--map-blue)', soft: 'color-mix(in srgb, var(--map-blue) 14%, var(--raised))', hint: 'Idea to validation, undecided' },
  accepted: { label: 'Accepted', color: 'var(--map-mint)', soft: 'color-mix(in srgb, var(--map-mint) 14%, var(--raised))', hint: 'Accepted: validation / tracking / simulation / live' },
  kept: { label: 'Kept', color: 'var(--map-lilac)', soft: 'color-mix(in srgb, var(--map-lilac) 14%, var(--raised))', hint: 'Not on the mainline, kept as a lead' },
  ended: { label: 'Ended', color: 'var(--map-rose)', soft: 'color-mix(in srgb, var(--map-rose) 14%, var(--raised))', hint: 'Rejected / superseded / retired' },
};
export const STAGES = ['idea', 'hypothesis', 'experiment', 'validation', 'tracking', 'simulation', 'live', 'retired'];
const STAGE_LABEL = { idea: 'Idea', hypothesis: 'Hypothesis', experiment: 'Experiment', validation: 'Validation', tracking: 'Tracking', simulation: 'Simulation', live: 'Live', retired: 'Retired' };
const DECISION_LABEL = { pending: 'Pending', kept: 'Kept', accepted: 'Accepted', rejected: 'Rejected', superseded: 'Superseded' };
const METRICS = [
  { k: 'annual_return', l: 'Annual return', pct: true },
  { k: 'sharpe', l: 'Sharpe', pct: false },
  { k: 'max_drawdown', l: 'Max drawdown', pct: true },
  { k: 'calmar', l: 'Calmar', pct: false },
];
const COLW = 258;
const ROWH = 56;
const NW = 224;
const NH = 40;

const familyOf = (node) => FAMILIES[node.family] || FAMILIES.active;
const stageLabel = (node) => t(STAGE_LABEL[node.stage] || node.stage);
const decisionLabel = (node) => (node.decision ? t(DECISION_LABEL[node.decision] || node.decision) : null);
const fmtPct = (v) => (v === null || v === undefined ? '--' : `${Number(v).toFixed(2)}%`);
const fmtNum = (v, d = 2) => (v === null || v === undefined ? '--' : Number(v).toFixed(d));
const clip = (s, n) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '');
const runOf = (node) => (node?.binding && node.binding.run) || null;
const metricsOf = (node) => { const run = runOf(node); return run && run.metrics ? run.metrics : null; };

function mapDate(value) {
  const text = String(value);
  return new Date(/^\d{4}-\d\d-\d\dT/.test(text) && !/(?:Z|[+-]\d\d:\d\d)$/i.test(text) ? `${text}Z` : text);
}

function formatWhen(value) {
  if (!value) return '--';
  const date = mapDate(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function ago(value) {
  if (!value) return '--';
  const ms = Date.now() - mapDate(value).getTime();
  if (!Number.isFinite(ms)) return String(value);
  const m = Math.round(ms / 60000);
  if (m < 1) return t('just now');
  if (m < 60) return `${m} ${t('min ago')}`;
  if (m < 60 * 24) return `${Math.round(m / 60)} ${t('h ago')}`;
  return `${Math.round(m / 1440)} ${t('d ago')}`;
}
const actorLabel = (type, id) => (id ? String(id) : type || '--');
function subLine(node) {
  const head = node.decision === 'rejected' || node.decision === 'superseded' ? decisionLabel(node) : node.decision === 'pending' ? t('Pending') : stageLabel(node);
  return node.date_label ? `${head} · ${node.date_label}` : head;
}
function fileHref(file, settings) {
  const base = settings?.file_base_url;
  if (!base) return null;
  return `${String(base).replace(/\/+$/, '')}/${String(file).split('/').map(encodeURIComponent).join('/')}`;
}
const qualityLabel = (sev) => ({ ok: t('passed'), warning: t('warning'), error: t('failed'), pending: t('pending run') }[sev] || sev || '--');
function metricLabel(path) {
  const key = String(path || '').split('.').pop();
  return { sharpe: 'Sharpe', calmar: 'Calmar', sortino: 'Sortino', annual_return: t('Annual'), max_drawdown: t('MDD') }[key] || key;
}

// ---------------------------------------------------------------------------
// Index + layout
// ---------------------------------------------------------------------------

export function buildIndex(map) {
  const nodes = (map?.nodes || []).map((n) => ({ ...n, children: [] }));
  const byKey = {};
  nodes.forEach((n) => { byKey[n.key] = n; });
  const roots = [];
  nodes.forEach((n) => {
    const parent = n.parent_key ? byKey[n.parent_key] : null;
    if (parent) { parent.children.push(n); n.parentNode = parent; } else { n.parentNode = null; roots.push(n); }
  });
  const sortSiblings = (list) => list.sort((a, b) => (a.position - b.position) || String(a.created_at).localeCompare(String(b.created_at)) || a.key.localeCompare(b.key));
  sortSiblings(roots);
  nodes.forEach((n) => sortSiblings(n.children));
  const depth = (list, d) => list.forEach((n) => { n.depth = d; depth(n.children, d + 1); });
  depth(roots, 0);
  const baseline = map?.baseline_node_key ? byKey[map.baseline_node_key] || null : null;
  const mainSet = new Set(map?.mainline_keys || []);
  return { nodes, roots, byKey, baseline, mainSet };
}

function layoutTree(roots, collapsed) {
  let row = 0;
  const visible = [];
  const place = (n) => {
    n.x = n.depth * COLW;
    const kids = collapsed.has(n.key) ? [] : n.children;
    if (!kids.length) { n.y = row * ROWH; row += 1; } else { kids.forEach(place); n.y = (kids[0].y + kids[kids.length - 1].y) / 2; }
    visible.push(n);
  };
  roots.forEach(place);
  return visible;
}
const countDesc = (n) => { let c = 0; (function walk(x) { x.children.forEach((k) => { c += 1; walk(k); }); })(n); return c; };

// ---------------------------------------------------------------------------
// Tree canvas (SVG)
// ---------------------------------------------------------------------------

export const TreeCanvas = forwardRef(function TreeCanvas({ index, collapsed, onToggleCollapse, selectedKey, onSelect, hiddenFamilies, hiddenStages, query, density, className = '', hint = true }, ref) {
  const canvasRef = useRef(null);
  const dragRef = useRef(null);
  const [view, setView] = useState({ tx: 30, ty: 30, k: 0.9 });
  const visible = useMemo(() => layoutTree(index.roots, collapsed), [index, collapsed]);
  const visibleSet = useMemo(() => new Set(visible), [visible]);
  const visibleRef = useRef(visible);
  visibleRef.current = visible;

  const fit = useCallback(() => {
    const canvas = canvasRef.current; const vis = visibleRef.current;
    if (!canvas || !vis.length) return;
    const maxX = Math.max(...vis.map((n) => n.x)) + NW + 40;
    const maxY = Math.max(...vis.map((n) => n.y)) + NH;
    const rect = canvas.getBoundingClientRect();
    const k = Math.max(0.25, Math.min(1.15, (rect.width - 60) / maxX, (rect.height - 70) / maxY));
    setView({ k, tx: Math.max(24, (rect.width - maxX * k) / 2), ty: Math.max(24, (rect.height - maxY * k) / 2) });
  }, []);
  const focus = useCallback((key) => {
    const canvas = canvasRef.current; const node = index.byKey[key];
    if (!canvas || !node || !visibleRef.current.includes(node)) return;
    const rect = canvas.getBoundingClientRect();
    setView((current) => { const k = Math.max(current.k, 0.9); return { k, tx: rect.width * 0.42 - (node.x + NW / 2) * k, ty: rect.height / 2 - (node.y + NH / 2) * k }; });
  }, [index]);
  useImperativeHandle(ref, () => ({ fit, focus }), [fit, focus]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let previous = canvas.getBoundingClientRect();
    const observer = new ResizeObserver(() => {
      const next = canvas.getBoundingClientRect();
      const dx = (next.width - previous.width) / 2;
      const dy = (next.height - previous.height) / 2;
      previous = next;
      if (dx || dy) setView((current) => ({ ...current, tx: current.tx + dx, ty: current.ty + dy }));
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const onWheel = (event) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const px = event.clientX - rect.left; const py = event.clientY - rect.top;
      const factor = Math.exp(-event.deltaY * 0.0012);
      setView((current) => { const nk = Math.min(2.5, Math.max(0.25, current.k * factor)); return { k: nk, tx: px - (px - current.tx) * (nk / current.k), ty: py - (py - current.ty) * (nk / current.k) }; });
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, []);

  const onPointerDown = (event) => {
    if (event.target.closest('.rmap-node')) return;
    dragRef.current = { x: event.clientX, y: event.clientY, tx: view.tx, ty: view.ty };
    event.currentTarget.classList.add('rmap-dragging');
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event) => {
    const drag = dragRef.current; if (!drag) return;
    setView((current) => ({ ...current, tx: drag.tx + (event.clientX - drag.x), ty: drag.ty + (event.clientY - drag.y) }));
  };
  const onPointerUp = (event) => { dragRef.current = null; event.currentTarget.classList.remove('rmap-dragging'); };
  const q = (query || '').trim().toLowerCase();
  const isDim = (n) => hiddenFamilies.has(n.family) || hiddenStages.has(n.stage);
  const isHit = (n) => q && ((n.title || '').toLowerCase().includes(q) || (n.key || '').toLowerCase().includes(q));

  return (
    <div className={`rmap-canvas ${className}`} ref={canvasRef} tabIndex={0} role="region" aria-label="研究树画布：方向键平移，加减缩放，Home 适应窗口" onKeyDown={event => {
      if (event.target !== event.currentTarget) return;
      const shifts = {ArrowLeft:[40,0], ArrowRight:[-40,0], ArrowUp:[0,40], ArrowDown:[0,-40]};
      if (shifts[event.key]) { event.preventDefault(); const [dx,dy] = shifts[event.key]; setView(current => ({...current,tx:current.tx+dx,ty:current.ty+dy})); }
      if (['+','=','-'].includes(event.key)) { event.preventDefault(); setView(current => ({...current,k:Math.min(2.5,Math.max(.25,current.k*(event.key==='-' ? .85 : 1.15)))})); }
      if (event.key==='Home') { event.preventDefault(); fit(); }
    }} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
      <svg className="block h-full w-full" role="img" aria-label={t('Research tree')}>
        <g transform={`translate(${view.tx},${view.ty}) scale(${view.k})`}>
          <g>
            {visible.map((n) => {
              if (!n.parentNode || !visibleSet.has(n.parentNode)) return null;
              const p = n.parentNode;
              const x1 = p.x + NW; const y1 = p.y + NH / 2; const x2 = n.x; const y2 = n.y + NH / 2; const mx = (x1 + x2) / 2;
              const main = index.mainSet.has(n.key) && index.mainSet.has(p.key);
              return <path className={`rmap-link${main ? ' main' : ''}${isDim(n) ? ' dim' : ''}`} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} key={`l-${n.id}`} />;
            })}
          </g>
          <g>
            {visible.map((n) => {
              const fam = familyOf(n);
              const metrics = density === 'metric' ? metricsOf(n) : null;
              const primary = metrics && metrics.primary && metrics.primary.value !== null && metrics.primary.value !== undefined ? metrics.primary : null;
              const classes = ['rmap-node', `fam-${n.family}`, `stage-${n.stage}`];
              if (n.is_baseline) classes.push('baseline');
              if (index.mainSet.has(n.key)) classes.push('main');
              if (selectedKey === n.key) classes.push('selected');
              if (isDim(n)) classes.push('dim');
              if (isHit(n)) classes.push('hit');
              if (!n.decision && (n.stage === 'idea' || n.stage === 'hypothesis')) classes.push('dashed');
              const isCollapsed = collapsed.has(n.key);
              return (
                <g className={classes.join(' ')} key={n.id} transform={`translate(${n.x},${n.y})`} style={{ '--c': fam.color }} tabIndex={0} role="button" aria-label={n.title}
                  onClick={() => onSelect(n.key)} onKeyDown={(e) => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); if (n.children.length && (e.key === 'ArrowLeft' ? !isCollapsed : isCollapsed)) onToggleCollapse(n.key); } if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(n.key); } }}>
                  <rect className="box" width={NW} height={NH} rx={3} />
                  <rect className="tag" x={0} y={0} width={5} height={NH} />
                  <text className="t" x={12} y={17}>{(n.is_baseline ? '★ ' : '') + clip(n.title, primary ? 13 : 16)}</text>
                  <text className="d" x={12} y={31}>{clip(subLine(n), primary ? 18 : 24)}</text>
                  {primary ? <><text className="m" x={NW - 10} y={17}>{fmtNum(primary.value)}</text><text className="ml" x={NW - 10} y={31}>{metricLabel(primary.metric)}</text></> : (n.binding && density === 'metric' ? <text className="ml" x={NW - 10} y={31}>{n.binding.kind === 'compare_set' ? 'compare' : n.binding.kind}</text> : null)}
                  {n.flags?.includes('ready') ? <circle className="ready" cx={NW - 6} cy={6} r={4} /> : null}
                  {n.children.length ? (
                    <g className="tog" transform={`translate(${NW},${NH / 2})`} onClick={(e) => { e.stopPropagation(); onToggleCollapse(n.key); }}>
                      <circle r={8} /><text>{isCollapsed ? '+' : '−'}</text>
                      {isCollapsed ? <text className="cnt" x={12} y={-10}>{countDesc(n)}</text> : null}
                    </g>
                  ) : null}
                </g>
              );
            })}
          </g>
        </g>
      </svg>
      {hint ? <div className="rmap-hint">{t('Drag to pan · scroll to zoom · click a node for details · click ± to collapse · thick lines mark the mainline to the baseline')}</div> : null}
    </div>
  );
});

// ---------------------------------------------------------------------------
// Node detail (structured slots)
// ---------------------------------------------------------------------------

function nearestWithMetrics(node, me) {
  for (let p = node.parentNode; p; p = p.parentNode) {
    const m = metricsOf(p); const run = runOf(p);
    if (m && !(me && run && me.run && run.id === me.run.id)) return { node: p, metrics: m };
  }
  return null;
}
function DeltaCell({ m, a, b }) {
  if (a === null || a === undefined || b === null || b === undefined) return <td className="d"><span className="dl eq">--</span></td>;
  const d = a - b;
  const abs = <small>{m.pct ? fmtPct(b) : fmtNum(b)}</small>;
  if (Math.abs(d) < 0.005) return <td className="d"><span className="dl eq">{t('flat')}</span>{abs}</td>;
  const txt = (d > 0 ? '+' : '−') + (m.pct ? `${Math.abs(d).toFixed(1)} pp` : Math.abs(d).toFixed(2));
  return <td className="d"><span className={`dl ${d > 0 ? 'good' : 'bad'}`}>{txt}</span>{abs}</td>;
}

export function NodeDetail({ node, index, map, onSelectNode, nav }) {
  if (!node) return <div className="rmap-empty">{t('Click a node to see its verdict, comparison, changes, and evidence.')}</div>;
  const fam = familyOf(node);
  const run = runOf(node);
  const me = metricsOf(node) ? { run, metrics: metricsOf(node) } : null;
  const decision = run && run.notes ? run.notes.find((n) => n.kind === 'decision') : null;
  const ready = node.flags?.includes('ready');
  const baseline = index.baseline && index.baseline.key !== node.key && metricsOf(index.baseline) ? { node: index.baseline, metrics: metricsOf(index.baseline), run: runOf(index.baseline) } : null;
  const par = me ? nearestWithMetrics(node, me) : null;
  const cols = [];
  if (me && baseline) cols.push({ h: t('vs baseline'), node: baseline.node, metrics: baseline.metrics });
  if (me && par && (!baseline || !baseline.run || !runOf(par.node) || runOf(par.node).id !== baseline.run.id)) cols.push({ h: par.node === node.parentNode ? t('vs parent') : t('vs ancestor'), node: par.node, metrics: par.metrics });
  const hintText = node.stage === 'idea' ? t('Idea stage, not started yet.') : node.stage === 'hypothesis' ? t('Registered, no experiment result yet.') : ready ? t('Results are in, waiting for a verdict.') : node.decision === 'pending' ? t('Pending: results reviewed, no verdict yet.') : t('In progress, the bound run has not completed.');
  const binding = node.binding;
  const openRef = (ref) => {
    const handlers = { run: nav.selectRun, branch: nav.selectBranch, research: nav.selectResearch, project: nav.selectProject, compare_set: nav.selectCompareSet };
    if (handlers[ref.kind] && ref.id) { handlers[ref.kind](ref.id); return; }
    if (ref.kind === 'artifact' && ref.id) { window.open(artifactContentUrl(ref.id), '_blank', 'noopener'); return; }
    const href = ref.href || (ref.kind === 'file' ? fileHref(ref.id || '', map.settings_json) : null);
    if (href) window.open(href, '_blank', 'noopener');
  };
  return (
    <div className="rmap-detail">
      <div className="hd">
        <div className="hdrow">
          <span className="pill" style={{ '--c': fam.color, '--cs': fam.soft }}><i />{stageLabel(node)}</span>
          {node.decision ? <span className="pill dec" style={{ '--c': fam.color }}>{decisionLabel(node)}</span> : null}
          {node.is_baseline ? <span className="pill" style={{ '--c': 'rgb(var(--c-accentInk))', '--cs': 'rgb(var(--c-accent))' }}>★ {t('Current baseline')}</span> : null}
          {node.is_mainline && !node.is_baseline ? <span className="tag">{t('Mainline')}</span> : null}
          {node.parentNode ? <button className="parent" type="button" title={t('Jump to parent')} onClick={() => onSelectNode(node.parentNode.key)}><small>{t('Parent')}</small>{node.parentNode.title}</button> : null}
        </div>
        <h2>{node.full_title || node.title}</h2>
        {node.hypothesis ? <p className="hyp">{node.hypothesis}</p> : null}
      </div>
      <section className={`vd${node.verdict ? '' : ready ? ' ready' : ' none'}`} style={{ '--c': fam.color, '--cs': fam.soft }}>
        {node.verdict ? (
          <>
            <p className="vtext">{node.verdict}</p>
            <div className="vfoot">
              <span>{decision ? `${actorLabel(decision.author_type, decision.author_id)} · ${formatWhen(decision.created_at)}` : `${actorLabel(node.updated_by_type, node.updated_by_id)} · ${formatWhen(node.updated_at)}`}</span>
              {decision ? <span className="sync" title={t('This verdict was also written as a decision note on the bound run')}>✓ {t('run note written')}</span> : null}
            </div>
          </>
        ) : <p className="vtext muted">{hintText}</p>}
      </section>
      {me ? (
        <section className="sec">
          <h4>{t('Comparison')}</h4>
          <table className="cmp2">
            <thead><tr><th /><th className="me">{t('This node')}</th>{cols.map((c) => <th key={c.h}>{c.h}</th>)}</tr></thead>
            <tbody>
              {METRICS.map((m) => (
                <tr key={m.k}>
                  <td className="l">{t(m.l)}</td>
                  <td className="me">{m.pct ? fmtPct(me.metrics[m.k]) : fmtNum(me.metrics[m.k])}</td>
                  {cols.map((c) => <DeltaCell key={c.h} m={m} a={me.metrics[m.k]} b={c.metrics[m.k]} />)}
                </tr>
              ))}
            </tbody>
          </table>
          {cols.length ? <div className="cmpnote">{cols.map((c) => `${c.h.replace(/^vs /, '').replace(/^对比/, '')}：${c.node.title}`).join(' · ')}</div> : null}
        </section>
      ) : null}
      {node.change?.length ? (
        <section className="sec">
          <h4>{t('Changes')}{node.binding?.kind === 'run' && node.parentNode?.binding?.kind === 'run' ? <button className="lnk" type="button" onClick={() => nav.selectRun(node.binding.id)}>{t('Config diff')}</button> : null}</h4>
          <ul className="chg">
            {node.change.map((c, i) => (typeof c === 'string' ? <li key={i}>{c}</li> : <li key={i}><b>{c.what}</b>{c.to}{c.from ? <span className="from">{t('Was')}：{c.from}</span> : null}</li>))}
          </ul>
        </section>
      ) : null}
      {node.reading?.length ? <section className="sec"><h4>{t('Reading')}</h4><ul>{node.reading.map((r, i) => <li key={i}>{r}</li>)}</ul></section> : null}
      {node.caveats?.length ? <section className="sec cav"><h4>{t('Caveats')}</h4><ul>{node.caveats.map((r, i) => <li key={i}>{r}</li>)}</ul></section> : null}
      {node.next ? <section className="sec"><h4>{t('Next step')}</h4><p className="next">{node.next}</p></section> : null}
      {binding ? <EvidenceSection binding={binding} nav={nav} /> : null}
      {node.refs?.length ? (
        <section className="sec"><h4>{t('Refs')}</h4><ul className="refs">{node.refs.map((r, i) => {
          const linkable = r.href || (r.kind !== 'file' && r.id) || (r.kind === 'file' && map.settings_json?.file_base_url);
          const label = r.label || r.id || r.href;
          return <li key={i}><span className="rk">{r.kind}</span>{linkable ? <button type="button" title={label} onClick={() => openRef(r)}><ExternalLink className="mr-1 inline h-3 w-3" />{label}</button> : <span title={label}>{label}</span>}</li>;
        })}</ul></section>
      ) : null}
      {node.children.length ? <section className="sec"><h4>{t('Branches from here')} {node.children.length}</h4><div className="kids">{node.children.map((c) => <button key={c.id} type="button" style={{ '--c': familyOf(c).color }} onClick={() => onSelectNode(c.key)}>{c.title}</button>)}</div></section> : null}
      <footer className="ft">
        <span className="mono">{node.key}</span>
        {binding ? <span className="mono">{binding.kind} {binding.label || binding.id}</span> : <span>{t('Unbound')}</span>}
        <span>{t('Updated')} {ago(node.updated_at)} · {actorLabel(node.updated_by_type, node.updated_by_id)}</span>
        <RevisionList mapId={map.id} nodeKey={node.key} />
      </footer>
    </div>
  );
}

function EvidenceSection({ binding, nav }) {
  if (!binding.exists) return <section className="sec"><h4>{t('Evidence')}</h4><div className="text-xs text-negative">{t('Bound entity no longer exists')}: {binding.kind} {binding.id}</div></section>;
  if (binding.kind === 'research') return <section className="sec"><h4>{t('Evidence')}<button className="lnk" type="button" onClick={() => nav.selectResearch(binding.id)}>{t('Open research')} →</button></h4><div className="ev"><span className="name">{binding.research.key}</span><span className="badge ok">{binding.research.status}</span></div></section>;
  if (binding.kind === 'compare_set') {
    return (
      <section className="sec"><h4>{t('Evidence')}<button className="lnk" type="button" onClick={() => nav.selectCompareSet(binding.id)}>{t('Open compare set')} →</button></h4>
        <div className="ev"><span className="name">{binding.compare_set.name}</span></div>
        <div className="evrows">{(binding.runs || []).map((r) => <div key={r.id}><span className="mono">{r.name}</span><span>Sharpe {fmtNum(r.metrics?.sharpe)}</span><span>MDD {fmtPct(r.metrics?.max_drawdown)}</span></div>)}</div>
      </section>
    );
  }
  const run = binding.run;
  const br = binding.branch;
  if (!run) return <section className="sec"><h4>{t('Evidence')}{br ? <button className="lnk" type="button" onClick={() => nav.selectBranch(br.id)}>{t('Open branch')} →</button> : null}</h4><div className="text-xs text-subtle">{t('No runs on this branch yet')}</div></section>;
  const q = run.status === 'running' ? <span className="badge run">● {t('running')}</span> : run.status !== 'completed' ? <span className="badge warn">{run.status}</span> : run.quality?.severity === 'ok' ? <span className="badge ok">✓ {t('quality gate')} {qualityLabel('ok')}</span> : run.quality?.severity === 'warning' ? <span className="badge warn">! {t('quality gate')} {qualityLabel('warning')}</span> : <span className="badge err">✕ {t('quality gate')} {qualityLabel('error')}</span>;
  return (
    <section className="sec">
      <h4>{t('Evidence')}<button className="lnk" type="button" onClick={() => nav.selectRun(run.id)}>{t('Open run')} →</button></h4>
      <div className="ev"><span className="name">{run.name}</span>{q}{run.mode && run.mode !== 'backtest' ? <span className="tag mono">{run.mode}</span> : null}{br ? <span className="sub">{t('branch')} {br.key} · {t('best of')} {br.run_count}</span> : null}</div>
      <div className="evmeta">
        <span>{run.started_at ? formatWhen(run.started_at).slice(0, 10) : '--'} → {run.ended_at ? formatWhen(run.ended_at).slice(0, 10) : '—'}</span>
        {run.metrics ? (run.metrics.periods_per_year ? <span>{run.metrics.periods_per_year}/{t('yr')}</span> : null) : <span>{t('No performance metrics yet')}</span>}
        {(run.artifacts || []).map((a) => <span className="art" key={a.id}>{a.kind}</span>)}
      </div>
    </section>
  );
}

function RevisionList({ mapId, nodeKey }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(null);
  useEffect(() => { setOpen(false); setRows(null); }, [mapId, nodeKey]);
  useEffect(() => {
    if (!open || rows) return undefined;
    let cancelled = false;
    apiGet(`/api/v1/research-maps/${mapId}/revisions?node_key=${encodeURIComponent(nodeKey)}&limit=20`).then((data) => { if (!cancelled) setRows(data); }).catch(() => { if (!cancelled) setRows([]); });
    return () => { cancelled = true; };
  }, [open, rows, mapId, nodeKey]);
  return (
    <details open={open} onToggle={(e) => setOpen(e.target.open)}>
      <summary>{t('Revisions')}</summary>
      {rows === null ? <div className="rev"><span className="t">…</span></div> : rows.length ? <div className="rev">{rows.map((r) => <React.Fragment key={r.id}><span className="t">{formatWhen(r.created_at).slice(5)} · {actorLabel(r.by_type, r.by_id)}</span><span className="w">{r.summary}</span></React.Fragment>)}</div> : <div className="rev"><span className="w">{t('No revisions')}</span></div>}
    </details>
  );
}

// ---------------------------------------------------------------------------
// Map view (page + embedded)
// ---------------------------------------------------------------------------

export function ResearchMapView({ map, embedded = false, nav, locate, onOpenPage, headerExtra }) {
  const index = useMemo(() => buildIndex(map), [map]);
  const settings = map.settings_json || {};
  const canvasRef = useRef(null);
  const scope = embedded ? `/researches/${map.research_id}` : `/maps/${map.id}`;
  const [nodeKey, setNodeKey] = usePageQuery(scope, `node-${map.id}`, '');
  const selectedKey = nodeKey || index.baseline?.key || index.roots[0]?.key || null;
  const setSelectedKey = key => setNodeKey(key || '');
  const [tab, setTab] = usePageQuery(scope, `mapTab-${map.id}`, 'overview');
  const [collapsed, setCollapsed] = useState(() => new Set());
  const [hiddenFamilies, setHiddenFamilies] = useState(() => new Set());
  const [hiddenStages, setHiddenStages] = useState(() => new Set());
  const [query, setQuery] = usePageQuery(scope, `mapQuery-${map.id}`, '');
  const [density, setDensity] = useState('metric');
  const [fullscreen, setFullscreen] = useState(false);
  const initializedFor = useRef(null);
  const pendingFocus = useRef(null);

  useEffect(() => {
    if (initializedFor.current === map.id) return;
    initializedFor.current = map.id;
    setCollapsed(new Set((settings.collapsed || []).filter((k) => index.byKey[k])));
    setHiddenFamilies(new Set()); setHiddenStages(new Set());
    const initial = selectedKey;
    pendingFocus.current = initial ? { key: initial } : { fit: true };
  }, [map.id, index, settings.collapsed]);
  useEffect(() => { if (selectedKey && !index.byKey[selectedKey]) setSelectedKey(index.roots[0]?.key || null); }, [index, selectedKey]);
  useEffect(() => {
    if (!pendingFocus.current) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const p = pendingFocus.current; pendingFocus.current = null;
      if (!p || !canvasRef.current) return;
      if (p.key) canvasRef.current.focus(p.key); else canvasRef.current.fit();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [collapsed, index, fullscreen, selectedKey]);

  const reveal = useCallback((key) => {
    const node = index.byKey[key]; if (!node) return;
    setCollapsed((current) => { const next = new Set(current); for (let p = node.parentNode; p; p = p.parentNode) next.delete(p.key); next.delete(key); return next; });
    setSelectedKey(key);
    setTab('node');
    pendingFocus.current = { key };
  }, [index]);
  const pick = (key) => { setSelectedKey(key); setTab('node'); };
  const handledLocate = useRef(null);
  useEffect(() => {
    if (!locate?.key) return;
    const request = JSON.stringify([map.id, locate.key, locate.nonce]);
    if (handledLocate.current === request || !index.byKey[locate.key]) return;
    handledLocate.current = request;
    reveal(locate.key);
  }, [map.id, locate?.key, locate?.nonce, index, reveal]);
  useEffect(() => {
    if (!fullscreen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { setFullscreen(false); pendingFocus.current = { fit: true }; } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fullscreen]);

  const mainlineOnly = () => { const next = new Set(); index.nodes.forEach((n) => { if (!index.mainSet.has(n.key)) next.add(n.key); }); if (index.baseline) next.delete(index.baseline.key); setCollapsed(next); pendingFocus.current = { fit: true }; };
  const expandAll = () => { setCollapsed(new Set()); pendingFocus.current = { fit: true }; };
  const toggleIn = (setter) => (key) => setter((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  const selected = selectedKey ? index.byKey[selectedKey] : null;

  const toolbar = (
    <div className="rmap-toolbar">
      {embedded ? <div className="flex min-w-0 items-center gap-2"><Network className="h-4 w-4 text-muted" /><span className="text-sm font-semibold text-ink">{t('Research Map')}</span><span className="truncate text-xs text-muted">{map.title}</span>{headerExtra}</div> : <div className="flex min-w-0 items-center gap-2"><Network className="h-4 w-4 text-muted" /><span className="truncate text-sm font-semibold text-ink">{map.title}</span></div>}
      <div className="flex flex-wrap items-center gap-2">
        <input className="form-control" style={{ width: 150, height: 30 }} type="search" placeholder={t('Search nodes…')} aria-label={t('Search nodes…')} value={query} onChange={(e) => { setQuery(e.target.value); const q = e.target.value.trim().toLowerCase(); if (q) { const hit = index.nodes.find((n) => (n.title || '').toLowerCase().includes(q)); if (hit) reveal(hit.key); } }} />
        <div className="rmap-seg" role="group" aria-label={t('Card density')}><button type="button" className={density === 'compact' ? 'on' : ''} onClick={() => setDensity('compact')}>{t('Compact')}</button><button type="button" className={density === 'metric' ? 'on' : ''} onClick={() => setDensity('metric')}>{t('With metric')}</button></div>
        <button className="secondary-button" type="button" onClick={mainlineOnly}>{t('Mainline only')}</button>
        <button className="secondary-button" type="button" onClick={expandAll}>{t('Expand all')}</button>
        <button className="secondary-button" type="button" onClick={() => { setQuery(''); setHiddenFamilies(new Set()); setHiddenStages(new Set()); }}>清除高亮条件</button>
        <button className="secondary-button" type="button" onClick={() => canvasRef.current?.fit()}><Maximize2 className="h-4 w-4" />{t('Fit')}</button>
        {embedded ? <button className="secondary-button" type="button" onClick={() => { setFullscreen((f) => !f); pendingFocus.current = { fit: true }; }}>{fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}{fullscreen ? t('Exit fullscreen') : t('Fullscreen')}</button> : null}
        {embedded && onOpenPage ? <button className="secondary-button" type="button" onClick={onOpenPage}>{t('Open map page')} →</button> : null}
      </div>
    </div>
  );
  const canvas = (
    <TreeCanvas ref={canvasRef} index={index} collapsed={collapsed} onToggleCollapse={toggleIn(setCollapsed)} selectedKey={selectedKey} onSelect={pick} hiddenFamilies={hiddenFamilies} hiddenStages={hiddenStages} query={query} density={density} hint={!embedded || fullscreen} className="rmap-fill" />
  );
  const right = (
    <aside className="rmap-right">
      <div className="rmap-tabs" role="group" aria-label="地图详情视图">
        <button className={`rmap-tab ${tab === 'overview' ? 'on' : ''}`} aria-pressed={tab === 'overview'} type="button" onClick={() => setTab('overview')}>{t('Overview')}</button>
        <button className={`rmap-tab ${tab === 'node' ? 'on' : ''}`} aria-pressed={tab === 'node'} type="button" onClick={() => setTab('node')}>{t('Node')}{selected ? <span className="rmap-tab-sub">{selected.title}</span> : null}</button>
      </div>
      <div className="rmap-tabbody">
        {tab === 'overview'
          ? <MapOverview map={map} index={index} nav={nav} reveal={reveal} hiddenFamilies={hiddenFamilies} hiddenStages={hiddenStages} toggleFamily={toggleIn(setHiddenFamilies)} toggleStage={toggleIn(setHiddenStages)} />
          : <NodeDetail node={selected} index={index} map={map} onSelectNode={reveal} nav={nav} />}
      </div>
    </aside>
  );
  const shellClass = embedded ? (fullscreen ? 'rmap-shell rmap-shell-full' : 'rmap-shell rmap-shell-embed') : 'rmap-shell rmap-shell-page';
  const panel = (
    <section className={`bento-panel overflow-hidden ${fullscreen ? 'rmap-fullscreen' : ''}`}>
      <div className={shellClass}>
        <div className="rmap-left">{toolbar}{canvas}</div>
        {right}
      </div>
    </section>
  );
  return fullscreen ? createPortal(panel, document.body) : panel;
}

function MapOverview({ map, index, nav, reveal, hiddenFamilies, hiddenStages, toggleFamily, toggleStage }) {
  const counts = map.counts || { families: {}, stages: {}, undecided: 0 };
  const baseline = map.baseline;
  const baseRun = baseline && baseline.run;
  const baseMetrics = baseRun && baseRun.metrics;
  const flagged = (flag) => index.nodes.filter((n) => n.flags?.includes(flag));
  const ready = flagged('ready'); const stale = flagged('stale'); const notAdvanced = flagged('not_advanced');
  const recent = (map.recent || []).filter((r) => index.byKey[r.key]);
  const hint = (label, list) => list.length ? (
    <li><span className="rl">{label}</span><span className="kids">{list.slice(0, 4).map((n) => <button key={n.key} type="button" style={{ '--c': familyOf(n).color }} onClick={() => reveal(n.key)}>{n.title}</button>)}{list.length > 4 ? <span className="text-subtle">+{list.length - 4}</span> : null}</span></li>
  ) : null;
  return (
    <div className="rmap-overview">
      <h2>{map.title}</h2>
      {map.subtitle ? <p className="sub">{map.subtitle}</p> : null}
      {map.description ? <p className="desc">{map.description}</p> : null}
      <dl className="meta">
        <dt>{t('Project')}</dt><dd><button type="button" onClick={() => nav.selectProject(map.project_id)}>{map.project_key || map.project_id}</button></dd>
        <dt>{t('Research')}</dt><dd>{map.research_id ? <button type="button" onClick={() => nav.selectResearch(map.research_id)}>{map.research_key || map.research_id}</button> : <span className="text-subtle">—</span>}</dd>
        <dt>{t('Nodes')}</dt><dd>{map.node_count} · {counts.undecided ?? 0} {t('undecided')}</dd>
        <dt>{t('Mainline')}</dt><dd>{index.mainSet.size} · {t('derived from root to baseline')}</dd>
        <dt>{t('primary metric')}</dt><dd>{metricLabel(map.primary_metric)}</dd>
        <dt>{t('Updated')}</dt><dd>{ago(map.last_updated_at)} · {formatWhen(map.last_updated_at)}</dd>
        <dt>{t('Key')}</dt><dd className="mono">{map.key}</dd>
      </dl>
      <section className="sec">
        <h4>{t('Current baseline')}</h4>
        {baseline ? (
          <button className="rmap-baseline" type="button" onClick={() => reveal(baseline.key)} title={t('Jump to the baseline node')}>
            <span className="k">★ {baseline.title}</span>
            {baseMetrics ? <>
              <span className="m"><small>{t('Annual')}</small>{fmtPct(baseMetrics.annual_return)}</span>
              <span className="m"><small>Sharpe</small>{fmtNum(baseMetrics.sharpe)}</span>
              <span className="m"><small>{t('MDD')}</small>{fmtPct(baseMetrics.max_drawdown)}</span>
              <span className="m"><small>Calmar</small>{fmtNum(baseMetrics.calmar)}</span>
            </> : <span className="m"><small>{t('No bound run metrics')}</small></span>}
            {baseRun ? <span className="m"><small>{t('quality gate')}</small>{qualityLabel(baseRun.quality?.severity)}</span> : null}
          </button>
        ) : <div className="text-xs text-subtle">{t('No baseline')}</div>}
      </section>
      <section className="sec">
        <h4>{t('Decision')}<span className="src">点击淡化 / 恢复，保留树结构</span></h4>
        <div className="rmap-legend">
          {Object.entries(FAMILIES).map(([k, f]) => <button className="rmap-chip" key={k} type="button" aria-pressed={!hiddenFamilies.has(k)} title={t(f.hint)} style={{ '--c': f.color }} onClick={() => toggleFamily(k)}><i />{t(f.label)}<b>{counts.families?.[k] || 0}</b></button>)}
        </div>
        <h4 className="mt-3">{t('Stage')}</h4>
        <div className="rmap-legend">
          {STAGES.filter((st) => counts.stages?.[st]).map((st) => <button className="rmap-chip stage" key={st} type="button" aria-pressed={!hiddenStages.has(st)} onClick={() => toggleStage(st)}>{t(STAGE_LABEL[st])}<b>{counts.stages[st]}</b></button>)}
        </div>
      </section>
      {(ready.length || stale.length || notAdvanced.length) ? (
        <section className="sec"><h4>{t('Needs attention')}</h4><ul className="hints">{hint(t('Results without a verdict'), ready)}{hint(t('Stale'), stale)}{hint(t('Accepted, not advanced'), notAdvanced)}</ul></section>
      ) : null}
      {recent.length ? (
        <section className="sec"><h4>{t('Recent updates')}</h4><ul className="recent">{recent.map((r) => <li key={r.key}><button type="button" style={{ '--c': (FAMILIES[r.family] || FAMILIES.active).color }} onClick={() => reveal(r.key)}>{r.title}</button><span>{ago(r.updated_at)} · {actorLabel(r.updated_by_type, r.updated_by_id)}</span></li>)}</ul></section>
      ) : null}
      <p className="foot">{t('Maintained by research agents through bbox map; the WebUI is read-only.')}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pages and panels
// ---------------------------------------------------------------------------

function useMap(mapId, refreshToken) {
  const [map, setMap] = useState(null);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    setError(null);
    if (!mapId) { setMap(null); return undefined; }
    let cancelled = false;
    apiGet(`/api/v1/research-maps/${mapId}`).then((payload) => { if (!cancelled) { setMap(current => JSON.stringify(current) === JSON.stringify(payload) ? current : payload); setError(null); } }).catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [mapId, refreshToken, retry]);
  return { map: map?.id === mapId ? map : null, error, reload: () => setRetry(value => value + 1) };
}

export function ResearchMapsPage({ data, selectedMapId, selectMap, selectProject, selectResearch, selectBranch, selectRun, selectCompareSet }) {
  const nav = { selectProject, selectResearch, selectBranch, selectRun, selectCompareSet };
  const { map, error, reload } = useMap(selectedMapId, data);
  if (selectedMapId) {
    if (error && !map) return <div className="space-y-3"><button className="secondary-button" type="button" onClick={() => selectMap(null)}>{t('All research maps')}</button><div className="rounded-md bg-negativeSoft px-3 py-2 text-xs font-semibold text-negative">{error}</div><button className="secondary-button" onClick={reload} type="button">重试加载地图</button></div>;
    if (!map) return <div className="flex items-center gap-2 px-2 py-6 text-sm text-muted"><RefreshCw className="h-4 w-4 animate-spin" />{t('Loading')}</div>;
    return <ResearchMapView key={map.id} map={map} nav={nav} headerExtra={error ? <button className="secondary-button text-negative" onClick={reload} title={error}>更新失败，点击重试</button> : null} />;
  }
  return <ResearchMapList refreshToken={data} onSelectMap={selectMap} selectProject={selectProject} selectResearch={selectResearch} />;
}

function ResearchMapList({ refreshToken, onSelectMap, selectProject, selectResearch }) {
  const [maps, setMaps] = useState(null);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = usePageQuery('/maps', 'query', '');
  useEffect(() => {
    let cancelled = false;
    apiGet('/api/v1/research-maps?include_evidence=false').then((payload) => { if (!cancelled) { setMaps(payload); setError(null); } }).catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [refreshToken, retry]);
  const rows = (maps || []).filter(map => [map.title,map.key,map.project_key,map.research_key].join(' ').toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <div className="space-y-4">
      <section className="bento-panel p-4">
        <div className="mb-1 text-xs font-semibold uppercase text-muted">{t('Research Map')}</div>
        <h1 className="text-2xl font-semibold text-ink md:text-3xl">{t('Research Maps')}</h1>
        <p className="mt-2 max-w-4xl text-sm leading-5 text-muted">{t('Research maps are maintained by research agents by hand. Structure and narrative are written; evidence is read from the bound run, branch, or compare set.')}</p>
      </section>
      <input className="form-control" type="search" aria-label="搜索地图" placeholder="搜索地图、项目、研究线" value={query} onChange={event => setQuery(event.target.value)} />
      {error ? <div className="rounded-md bg-negativeSoft px-3 py-2 text-xs font-semibold text-negative">{error}<button className="secondary-button ml-3" type="button" onClick={() => setRetry(value => value + 1)}>重试</button></div> : null}
      <section className="bento-panel overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3"><h2 className="text-sm font-semibold text-ink">{t('Research Maps')}</h2><span className="text-xs text-muted">{rows.length}</span></div>
        {error ? <p className="p-4 text-sm text-muted">地图加载失败，当前数量未知。</p> : maps === null ? <div className="flex items-center gap-2 px-4 py-6 text-sm text-muted"><RefreshCw className="h-4 w-4 animate-spin" />{t('Loading')}</div> : rows.length === 0 ? (
          <div className="space-y-3 px-4 py-6 text-sm text-muted">
            <p>{maps?.length ? '当前条件无匹配，请清除搜索。' : '当前范围尚无研究地图。'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse">
              <thead className="table-head"><tr>{['Title', 'Key', 'Project', 'Research', 'Nodes', 'Baseline', 'Undecided', 'Status', 'Updated'].map((l) => <th className="px-3 py-2" key={l}>{t(l)}</th>)}</tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr className="cursor-pointer hover:bg-white/45" key={row.id} onClick={() => onSelectMap(row.id)}>
                    <td className="table-cell font-semibold text-ink"><button type="button" onClick={event => { event.stopPropagation(); onSelectMap(row.id); }}>{row.title}</button></td>
                    <td className="table-cell font-mono text-xs text-muted">{row.key}</td>
                    <td className="table-cell"><button className="font-semibold text-info hover:underline" type="button" onClick={(e) => { e.stopPropagation(); selectProject(row.project_id); }}>{row.project_key || row.project_id}</button></td>
                    <td className="table-cell">{row.research_id ? <button className="font-semibold text-info hover:underline" type="button" onClick={(e) => { e.stopPropagation(); selectResearch(row.research_id); }}>{row.research_key || row.research_id}</button> : <span className="text-muted">--</span>}</td>
                    <td className="table-cell">{row.node_count}</td>
                    <td className="table-cell">{row.baseline ? `${row.baseline.title}${row.baseline.run?.metrics?.primary?.value != null ? ` · ${fmtNum(row.baseline.run.metrics.primary.value)}` : ''}` : '--'}</td>
                    <td className="table-cell">{row.counts?.undecided ?? 0}</td>
                    <td className="table-cell"><span className={`text-xs font-semibold ${row.status === 'archived' ? 'text-muted' : 'text-positive'}`}>{t(row.status)}</span></td>
                    <td className="table-cell text-xs text-muted">{formatWhen(row.last_updated_at || row.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export function ScopedResearchMapsPanel({ scope, scopeId, refreshToken, onSelectMap }) {
  const [maps, setMaps] = useState(null);
  const [listError, setListError] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!scopeId) { setMaps(null); return undefined; }
    let cancelled = false;
    apiGet(`/api/v1/${scope === 'research' ? 'researches' : 'projects'}/${scopeId}/research-maps?include_evidence=false`).then((payload) => { if (!cancelled) { setMaps(payload); setListError(null); } }).catch(err => { if (!cancelled) setListError(err.message); });
    return () => { cancelled = true; };
  }, [scope, scopeId, refreshToken, retry]);
  const rows = maps || [];
  return (
    <section className="bento-panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3"><div className="flex items-center gap-2"><Network className="h-4 w-4 text-muted" /><h2 className="text-sm font-semibold text-ink">{t('Research Maps')}</h2></div><span className="text-xs text-muted">{rows.length}</span></div>
      {listError ? <div className="p-4 text-sm text-negative">地图加载失败：{listError}<button className="secondary-button ml-3" onClick={() => setRetry(value => value + 1)}>重试</button></div> : maps === null ? <p className="p-4">加载地图中…</p> : rows.length === 0 ? <div className="px-4 py-4 text-sm text-muted">{t('No research map for this scope yet. Agents maintain maps with bbox map.')}</div> : (
        <ul className="divide-y divide-line/70">
          {rows.map((row) => (
            <li className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5" key={row.id}>
              <div className="min-w-0">
                <button className="truncate text-sm font-semibold text-ink hover:text-info" type="button" onClick={() => onSelectMap(row.id)}>{row.title}</button>
                <div className="text-xs text-muted"><span className="font-mono">{row.key}</span> · {row.node_count} {t('nodes')} · {row.counts?.undecided ?? 0} {t('undecided')}{row.baseline ? ` · ${t('Baseline')} ${row.baseline.title}` : ''} · {ago(row.last_updated_at)}</div>
              </div>
              <button className="secondary-button" type="button" onClick={() => onSelectMap(row.id)}>{t('Open')}</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Embedded map for the Research page. Reports an entity→nodes index so tables can show the map-node column. */
export function ResearchMapEmbed({ researchId, refreshToken, nav, onIndex, locate, selectMap }) {
  const [maps, setMaps] = useState(null);
  const [listError, setListError] = useState(null);
  const [retry, setRetry] = useState(0);
  const [mapId, setMapId] = useState(null);
  useEffect(() => {
    if (!researchId) { setMaps(null); setMapId(null); return undefined; }
    let cancelled = false;
    apiGet(`/api/v1/researches/${researchId}/research-maps?include_evidence=false`).then((payload) => { if (!cancelled) { setListError(null); setMaps(payload); setMapId((current) => (payload.some((m) => m.id === current) ? current : payload[0]?.id || null)); } }).catch(err => { if (!cancelled) setListError(err.message); });
    return () => { cancelled = true; };
  }, [researchId, refreshToken, retry]);
  const { map, error: mapError, reload } = useMap(mapId, refreshToken);
  useEffect(() => {
    if (!onIndex) return;
    if (!map) { onIndex({ byRun: {}, byBranch: {}, mapId: null }); return; }
    const byRun = {}; const byBranch = {};
    (map.nodes || []).forEach((n) => {
      if (!n.binding) return;
      if (n.binding.kind === 'run') (byRun[n.binding.id] = byRun[n.binding.id] || []).push(n);
      if (n.binding.kind === 'branch') (byBranch[n.binding.id] = byBranch[n.binding.id] || []).push(n);
      else if (n.binding.run && n.binding.run.branch_id) (byBranch[n.binding.run.branch_id] = byBranch[n.binding.run.branch_id] || []).push(n);
    });
    onIndex({ byRun, byBranch, mapId: map.id });
  }, [map, onIndex]);
  if ((listError || mapError) && !map) return <section className="bento-panel p-4 text-sm text-negative">地图加载失败：{listError || mapError}<button className="secondary-button ml-3" onClick={() => { setRetry(value => value + 1); reload(); }}>重试</button></section>;
  if (maps === null) return <p className="text-sm text-muted">加载地图中…</p>;
  if (!maps.length) {
    return (
      <section className="bento-panel px-4 py-3 text-sm text-muted">
        <div className="flex flex-wrap items-center gap-2"><Network className="h-4 w-4" /><span className="font-semibold text-ink">{t('Research Map')}</span><span>· {t('No research map for this research yet. Agents maintain maps with bbox map.')}</span></div>
      </section>
    );
  }
  const switcher = maps.length > 1 ? (
    <select className="form-control" style={{ width: 'auto', height: 28 }} value={mapId || ''} onChange={(e) => setMapId(e.target.value)} aria-label={t('Research Map')}>
      {maps.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
    </select>
  ) : null;
  if (!map) return <section className="bento-panel px-4 py-3 text-sm text-muted"><RefreshCw className="inline h-4 w-4 animate-spin" /> {t('Loading')}</section>;
  return <ResearchMapView key={map.id} map={map} embedded nav={nav} locate={locate} onOpenPage={() => selectMap(map.id)} headerExtra={<>{switcher}{listError || mapError ? <button className="secondary-button text-negative" title={listError || mapError} onClick={() => { setRetry(value => value + 1); reload(); }}>更新失败，点击重试</button> : null}</>} />;
}

/** Table cell: which map nodes bind this entity. */
export function MapNodeCell({ nodes, onLocate }) {
  if (!nodes || !nodes.length) return <span className="text-muted">—</span>;
  const first = nodes[0];
  const fam = familyOf(first);
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-xs">
      <span className="pill" style={{ '--c': fam.color, '--cs': fam.soft }}>{stageLabel(first)}{first.decision ? ` · ${decisionLabel(first)}` : ''}</span>
      <span className="font-semibold text-ink">{first.title}</span>
      {nodes.length > 1 ? <span className="text-subtle">+{nodes.length - 1}</span> : null}
      {onLocate ? <button className="font-semibold text-info hover:underline" type="button" onClick={(e) => { e.stopPropagation(); onLocate(first.key); }}>{t('Locate')}</button> : null}
    </span>
  );
}
