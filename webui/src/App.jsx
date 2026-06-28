import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  Boxes,
  CheckCircle2,
  ChevronDown,
  Database,
  Download,
  ExternalLink,
  FileText,
  GitBranch,
  Image as ImageIcon,
  Layers3,
  LineChart,
  ListTree,
  Maximize2,
  Pencil,
  PlusCircle,
  RefreshCw,
  Search,
  Send,
  TableProperties,
  Trophy,
  XCircle,
} from 'lucide-react';
import './index.css';
import { apiGet, apiPatch, apiPost, apiUpload, artifactContentUrl, formatMetric, metricValue, websocketUrl } from './api';
import { t, tStatus, tx } from './i18n';

const SHOW_SWEEPS = false;

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: Boxes },
  { id: 'project', label: 'Project', icon: Database },
  { id: 'research', label: 'Research', icon: ListTree },
  { id: 'branch', label: 'Branch', icon: GitBranch },
  { id: 'runs', label: 'Runs', icon: LineChart },
  { id: 'compare', label: 'Compare', icon: Layers3 },
  SHOW_SWEEPS ? { id: 'sweep', label: 'Sweep', icon: Trophy } : null,
  { id: 'search', label: 'Search', icon: Search },
  { id: 'management', label: 'Manage', icon: BarChart3 },
].filter(Boolean);

const branchStatuses = ['active', 'paused', 'accepted', 'rejected', 'archived'];
const artifactKinds = [
  'report_html',
  'image_png',
  'chart_json',
  'table_parquet',
  'table_csv',
  'notebook_ipynb',
  'config_yaml',
  'returns_series_parquet',
  'trade_log_parquet',
  'position_log_parquet',
  'factor_values_parquet',
  'risk_report_json',
  'code_patch_txt',
  'other',
];

function Badge({ children, tone = 'neutral' }) {
  const colorClass = {
    positive: 'text-positive',
    negative: 'text-negative',
    warning: 'text-warning',
    info: 'text-info',
    neutral: 'text-muted',
  }[tone] || 'text-muted';
  return <span className={`inline-flex whitespace-nowrap text-xs font-semibold ${colorClass}`}>{children}</span>;
}

function Panel({ className = '', children }) {
  return <section className={`bento-panel ${className}`}>{children}</section>;
}

function PanelHeader({ title, action }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
      <h2 className="text-base font-semibold text-ink">{tx(title)}</h2>
      {action}
    </div>
  );
}

const createActions = [
  { id: 'workspace', label: 'Workspace', description: 'Add a research workspace.' },
  { id: 'project', label: 'Project', description: 'Create a project under a workspace.' },
  { id: 'research', label: 'Research', description: 'Start a research thread.' },
  { id: 'branch', label: 'Branch', description: 'Fork or register an idea branch.' },
  { id: 'run', label: 'Run', description: 'Start a run on a branch.' },
  SHOW_SWEEPS ? { id: 'sweep', label: 'Sweep', description: 'Create a parameter sweep.' } : null,
  { id: 'compare-set', label: 'Compare Set', description: 'Save a reusable run comparison.' },
  { id: 'search-view', label: 'Search View', description: 'Save reusable search filters.' },
].filter(Boolean);

function TopBar({ data, onCreated, onOpenSearch }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [createKind, setCreateKind] = useState(null);
  const menuRef = useRef(null);
  const openCreate = (kind) => {
    setCreateKind(kind);
    setMenuOpen(false);
  };
  useEffect(() => {
    if (!menuOpen) return undefined;
    const handlePointerDown = (event) => {
      if (!menuRef.current?.contains(event.target)) setMenuOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);
  return (
    <header className="fixed left-0 right-0 top-0 z-40 flex h-14 items-center justify-between border-b border-line bg-panel/90 px-4 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <span className="text-lg font-semibold text-ink">Blackbox</span>
      </div>
      <div className="flex items-center gap-2">
        <button className="secondary-button hidden w-[180px] justify-between px-3 sm:inline-flex" type="button" onClick={onOpenSearch} aria-label={t('Open search')} title="Ctrl+K">
          <span>{t('Search')}</span>
          <kbd className="rounded border border-line bg-panel2 px-1.5 py-0.5 text-[11px] font-semibold text-muted">Ctrl K</kbd>
        </button>
        <button className="icon-button sm:hidden" type="button" onClick={onOpenSearch} aria-label={t('Open search')} title="Ctrl+K">
          <Search className="h-4 w-4" />
        </button>
        <div className="relative" ref={menuRef}>
          <button className="primary-button" type="button" onClick={() => setMenuOpen((current) => !current)}>
            <PlusCircle className="h-4 w-4" />
            {t('New')}
          </button>
          {menuOpen ? (
            <div className="absolute right-0 top-11 z-50 w-64 overflow-hidden rounded-md border border-line bg-panel shadow-lg">
              {createActions.map((item) => (
                <button className="block w-full px-4 py-3 text-left transition hover:bg-white/55" key={item.id} type="button" onClick={() => openCreate(item.id)}>
                  <div className="text-sm font-semibold text-ink">{t(item.label)}</div>
                  <div className="mt-1 text-xs text-muted">{t(item.description)}</div>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
      {createKind ? <CreateModal kind={createKind} data={data} onClose={() => setCreateKind(null)} onCreated={onCreated} /> : null}
    </header>
  );
}

function Sidebar({ active, onSelect }) {
  return (
    <aside className="fixed bottom-0 left-0 top-14 z-30 hidden w-64 border-r border-line bg-[#f6f6f2] p-4 md:flex md:flex-col">
      <nav className="flex flex-1 flex-col gap-1">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            className={`flex items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-semibold transition ${
              isNavItemActive(active, id) ? 'bg-white text-ink' : 'text-muted hover:bg-white/45 hover:text-ink'
            }`}
            key={id}
            onClick={() => onSelect(id)}
          >
            <Icon className="h-4 w-4" />
            {t(label)}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function Shell({ active, onSelect, data, onCreated, onOpenSearch, contextNav, children }) {
  return (
    <div className="min-h-screen">
      <TopBar data={data} onCreated={onCreated} onOpenSearch={onOpenSearch} />
      <Sidebar active={active} onSelect={onSelect} />
      <main className="pt-14 md:pl-64">
        <div className="mx-auto max-w-[1560px] p-4 pb-24 md:p-6 lg:p-8">
          {contextNav}
          {children}
        </div>
      </main>
      <div className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-3 border-t border-line bg-panel/95 p-2 backdrop-blur sm:grid-cols-6 md:hidden">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button className={`flex flex-col items-center gap-1 rounded-md py-2 text-[11px] font-semibold ${isNavItemActive(active, id) ? 'bg-white text-ink' : 'text-muted'}`} key={id} onClick={() => onSelect(id)}>
            <Icon className="h-4 w-4" />
            {t(label)}
          </button>
        ))}
      </div>
    </div>
  );
}

function QuickRunSearchModal({ open, data, onClose, onSelectRun }) {
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const runs = data?.runs || [];
  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return sortRunsByRecentActivity(runs)
      .filter((run) => !normalized || runBoardSearchText(run).includes(normalized))
      .slice(0, 10);
  }, [query, runs]);
  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActiveIndex(0);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);
  if (!open) return null;
  const selectResult = (run) => {
    if (!run) return;
    onSelectRun(run.id);
    onClose();
  };
  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((current) => Math.min(results.length - 1, current + 1));
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => Math.max(0, current - 1));
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      selectResult(results[activeIndex] || results[0]);
    }
  };
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-ink/18 px-4 py-8 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={t('Search')}>
      <button className="absolute inset-0 h-full w-full cursor-default" type="button" aria-label={t('Close search')} onClick={onClose} />
      <div className="relative mx-auto w-full max-w-2xl overflow-hidden rounded-bento border border-lineStrong bg-panel shadow-2xl">
        <div className="border-b border-line bg-white/75 p-3">
          <div className="flex items-center gap-3">
            <input
              ref={inputRef}
              className="h-10 min-w-0 flex-1 bg-transparent px-1 text-base font-semibold text-ink outline-none placeholder:text-muted/60"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('Search runs')}
              aria-label={t('Search runs')}
            />
            <kbd className="hidden rounded border border-line bg-panel2 px-2 py-1 text-xs font-semibold text-muted sm:inline-flex">Esc</kbd>
          </div>
        </div>
        <div className="max-h-[430px] overflow-y-auto p-2">
          {results.length ? results.map((run, index) => {
            const activeResult = index === activeIndex;
            return (
              <button
                className={`block w-full rounded-md px-3 py-3 text-left transition ${activeResult ? 'bg-infoSoft text-ink' : 'text-ink hover:bg-white/65'}`}
                key={run.id}
                type="button"
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectResult(run)}
              >
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{run.name || run.title || run.id}</div>
                    <div className="mt-1 truncate text-xs text-muted">{[run.project_key, run.research_key, run.branch_key || run.branch_id].filter(Boolean).join(' / ') || run.id}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs font-semibold text-muted">
                    <StatusBadge status={run.status} />
                    <span className="hidden tabular-nums sm:inline">{formatDate(run.updated_at || run.ended_at || run.started_at || run.created_at)}</span>
                  </div>
                </div>
              </button>
            );
          }) : (
            <div className="px-4 py-10 text-center">
              <div className="text-sm font-semibold text-ink">{t('No runs found.')}</div>
              <div className="mt-1 text-xs text-muted">{t('Try another keyword.')}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function isNavItemActive(active, id) {
  return active === id || (active === 'run' && id === 'runs');
}

function ContextNav({ items }) {
  const visibleItems = items.filter((item) => item?.value);
  if (!visibleItems.length) return null;
  return (
    <nav className="-mx-4 mb-5 bg-canvas/95 px-4 pb-3 pt-1 md:-mx-6 md:px-6 lg:-mx-8 lg:px-8" aria-label={t('Page context')}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-base">
        {visibleItems.map((item, index) => (
          <React.Fragment key={`${item.label}-${item.value}`}>
            {index ? <span className="text-muted/60">/</span> : null}
            <button
              className={`min-w-0 max-w-[260px] truncate text-left font-semibold transition hover:text-info ${item.active ? 'text-ink' : 'text-muted'}`}
              type="button"
              onClick={item.onSelect}
              title={item.label === item.value ? item.value : `${t(item.label)}: ${item.value}`}
            >
              {item.value}
            </button>
          </React.Fragment>
        ))}
      </div>
    </nav>
  );
}

function EmptyState({ title, detail }) {
  return (
    <Panel className="p-8 text-center">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-md bg-white/70 text-muted"><Search className="h-5 w-5" /></div>
      <h2 className="mt-4 text-lg font-semibold text-ink">{tx(title)}</h2>
      <p className="mt-2 text-sm text-muted">{tx(detail)}</p>
    </Panel>
  );
}

function StatTile({ label, value, tone = 'neutral' }) {
  return (
    <Panel className="min-h-[118px] p-5">
      <div className="text-xs font-semibold uppercase text-muted">{tx(label)}</div>
      <div className={`metric-value mt-5 text-4xl ${tone === 'negative' ? 'text-negative' : tone === 'positive' ? 'text-positive' : 'text-ink'}`}>{value}</div>
    </Panel>
  );
}

function ManagementPage({ data, selectProject, selectResearch, selectBranch, selectRun }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await apiGet('/api/v1/management/research-summary?stale_days=14&limit=25'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { loadSummary(); }, []);
  const stats = summary?.summary || {};
  return (
    <div className="space-y-5">
      <Hero
        eyebrow="Manage"
        title="研究资产管理"
        description="活跃研究、重产物、陈旧运行和批量实验压力"
        action={<button className="secondary-button" onClick={loadSummary} type="button"><RefreshCw className="h-4 w-4" />{loading ? '刷新中' : '刷新'}</button>}
      />
      {error ? <EmptyState title="Management API unavailable" detail={error} /> : null}
      <div className="dashboard-stats-grid">
        <Panel><ReadOnlyField label="Research" value={`${stats.researches ?? data?.summary?.researches ?? 0} / active ${stats.active_researches ?? 0}`} /></Panel>
        <Panel><ReadOnlyField label="Stale Active" value={stats.stale_active_researches ?? 0} /></Panel>
        <Panel><ReadOnlyField label="Runs" value={stats.runs ?? data?.summary?.runs ?? 0} /></Panel>
        <Panel><ReadOnlyField label="Running" value={`${stats.running_runs ?? 0} / stale ${stats.stale_running_runs ?? 0}`} /></Panel>
        <Panel><ReadOnlyField label="Artifacts" value={`${stats.artifacts ?? 0} · ${formatBytes(stats.artifact_bytes)}`} /></Panel>
        <Panel><ReadOnlyField label="Saved Views" value={`${stats.search_views ?? 0} search / ${stats.compare_sets ?? 0} compare`} /></Panel>
      </div>
      <ManagementProjectPressureTable rows={summary?.projects || []} onSelectProject={selectProject} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ManagementResearchTable title="Run 压力研究线" rows={summary?.top_research_by_runs || []} onSelectResearch={selectResearch} />
        <ManagementResearchTable title="Artifact 压力研究线" rows={summary?.top_research_by_artifacts || []} onSelectResearch={selectResearch} showBytes />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ManagementBranchTable title="Run 压力分支" rows={summary?.top_branches_by_runs || []} onSelectBranch={selectBranch} />
        <ManagementBranchTable title="Artifact 压力分支" rows={summary?.top_branches_by_artifacts || []} onSelectBranch={selectBranch} showBytes />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <StaleRunningRunsTable rows={summary?.stale_running_runs || []} onSelectRun={selectRun} onSelectResearch={selectResearch} />
        <ArtifactPressureTable rows={summary?.artifact_names_by_bytes || []} />
      </div>
      <ManagementResearchTable title="陈旧活跃研究线" rows={summary?.stale_active_researches || []} onSelectResearch={selectResearch} showBytes />
    </div>
  );
}

function ManagementProjectPressureTable({ rows, onSelectProject }) {
  return (
    <Panel>
      <PanelHeader title="项目压力" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head"><tr><th className="table-cell">Project</th><th className="table-cell text-right">Research</th><th className="table-cell text-right">Branches</th><th className="table-cell text-right">Runs</th><th className="table-cell text-right">Artifacts</th><th className="table-cell text-right">Size</th><th className="table-cell text-right">Latest</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="table-row" key={row.id}>
                <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectProject(row.id)} type="button">{row.title || row.key}</button><div className="text-xs text-muted">{row.key}</div></td>
                <td className="table-cell text-right">{row.research_count || 0}</td>
                <td className="table-cell text-right">{row.branch_count || 0}</td>
                <td className="table-cell text-right font-semibold text-info">{row.run_count || 0}</td>
                <td className="table-cell text-right">{row.artifact_count || 0}</td>
                <td className="table-cell text-right text-muted">{formatBytes(row.artifact_bytes)}</td>
                <td className="table-cell text-right text-muted">{formatDate(row.latest_run_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="7">暂无项目压力数据。</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ManagementResearchTable({ title, rows, onSelectResearch, showBytes = false }) {
  return (
    <Panel>
      <PanelHeader title={title} />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head"><tr><th className="table-cell">Research</th><th className="table-cell">Project</th><th className="table-cell">Status</th><th className="table-cell text-right">Branches</th><th className="table-cell text-right">Runs</th><th className="table-cell text-right">Artifacts</th>{showBytes ? <th className="table-cell text-right">Size</th> : null}<th className="table-cell text-right">Latest</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="table-row" key={row.id}>
                <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectResearch(row.id)} type="button">{row.title || row.key}</button><div className="text-xs text-muted">{row.key}</div></td>
                <td className="table-cell text-muted">{row.project_key || '--'}</td>
                <td className="table-cell"><StatusBadge status={row.status} /></td>
                <td className="table-cell text-right">{row.branch_count || 0}</td>
                <td className="table-cell text-right font-semibold text-info">{row.run_count || 0}</td>
                <td className="table-cell text-right">{row.artifact_count || 0}</td>
                {showBytes ? <td className="table-cell text-right text-muted">{formatBytes(row.artifact_bytes)}</td> : null}
                <td className="table-cell text-right text-muted">{formatDate(row.latest_run_at || row.updated_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan={showBytes ? 8 : 7}>暂无研究线数据。</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ManagementBranchTable({ title, rows, onSelectBranch, showBytes = false }) {
  return (
    <Panel>
      <PanelHeader title={title} />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head"><tr><th className="table-cell">Branch</th><th className="table-cell">Research</th><th className="table-cell">Status</th><th className="table-cell text-right">Runs</th><th className="table-cell text-right">Artifacts</th>{showBytes ? <th className="table-cell text-right">Size</th> : null}<th className="table-cell text-right">Latest</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="table-row" key={row.id}>
                <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectBranch(row.id)} type="button">{row.title || row.key}</button><div className="text-xs text-muted">{row.key}</div></td>
                <td className="table-cell text-muted">{row.research_key || '--'}</td>
                <td className="table-cell"><StatusBadge status={row.status} /></td>
                <td className="table-cell text-right font-semibold text-info">{row.run_count || 0}</td>
                <td className="table-cell text-right">{row.artifact_count || 0}</td>
                {showBytes ? <td className="table-cell text-right text-muted">{formatBytes(row.artifact_bytes)}</td> : null}
                <td className="table-cell text-right text-muted">{formatDate(row.latest_run_at || row.updated_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan={showBytes ? 7 : 6}>暂无分支数据。</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function StaleRunningRunsTable({ rows, onSelectRun, onSelectResearch }) {
  return (
    <Panel>
      <PanelHeader title="陈旧 Running Runs" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head"><tr><th className="table-cell">Run</th><th className="table-cell">Research</th><th className="table-cell">Branch</th><th className="table-cell text-right">Updated</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="table-row" key={row.id}>
                <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectRun(row.id)} type="button">{row.name}</button></td>
                <td className="table-cell"><button className="text-muted hover:text-ink hover:underline" onClick={() => onSelectResearch(row.research_id)} type="button">{row.research_key || '--'}</button></td>
                <td className="table-cell text-muted">{row.branch_key || '--'}</td>
                <td className="table-cell text-right text-muted">{formatDate(row.updated_at || row.started_at || row.created_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="4">暂无陈旧 running run。</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ArtifactPressureTable({ rows }) {
  return (
    <Panel>
      <PanelHeader title="Artifact 体积排行" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head"><tr><th className="table-cell">Name</th><th className="table-cell">Kind</th><th className="table-cell text-right">Count</th><th className="table-cell text-right">Size</th><th className="table-cell text-right">Max</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="table-row" key={`${row.name}-${row.kind}`}>
                <td className="table-cell font-semibold text-ink">{row.name}</td>
                <td className="table-cell text-muted">{row.kind}</td>
                <td className="table-cell text-right">{row.artifact_count || 0}</td>
                <td className="table-cell text-right font-semibold text-info">{formatBytes(row.artifact_bytes)}</td>
                <td className="table-cell text-right text-muted">{formatBytes(row.max_artifact_bytes)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="5">暂无 artifact 数据。</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
function Dashboard({ data, selectProject, selectResearch, selectBranch, selectRun, selectSweep, onChanged }) {
  const summary = data?.summary || {};
  const windowStats = dashboardWindowStats(data);
  const runs = data?.runs || [];
  const researches = data?.researches || [];
  const branches = data?.branches || [];
  const recentRuns = [...runs].sort((a, b) => dateMillis(b.updated_at || b.ended_at || b.started_at || b.created_at) - dateMillis(a.updated_at || a.ended_at || a.started_at || a.created_at)).slice(0, 10);
  const issueRuns = dashboardIssueRuns(runs).slice(0, 8);
  const activeResearchRows = projectResearchActivityRows(researches, branches, runs).slice(0, 8);
  const decisionRuns = [...runs]
    .filter((run) => run.status === 'completed')
    .sort((a, b) => Number(metricValue(b, 'strategy.summary', 'sharpe') || -Infinity) - Number(metricValue(a, 'strategy.summary', 'sharpe') || -Infinity))
    .slice(0, 8);
  return (
    <div className="space-y-5">
      <div className="dashboard-stats-grid">
        <StatTile label="Workspaces" value={summary.workspaces || 0} tone="info" />
        <StatTile label="Projects" value={summary.projects || 0} tone="info" />
        <StatTile label="Runs Today" value={summary.today_runs ?? windowStats.runsToday} tone="positive" />
        <StatTile label="Running" value={summary.running_runs || 0} tone="warning" />
        <StatTile label="Failed 24h" value={summary.failed_runs_24h ?? windowStats.failed24h} tone={(summary.failed_runs_24h ?? windowStats.failed24h) ? 'negative' : 'neutral'} />
        <StatTile label="New Branches" value={summary.new_branches_24h ?? windowStats.branches24h} tone="info" />
        <StatTile label="Runs" value={summary.runs || 0} tone="positive" />
        <StatTile label="Compare Sets" value={summary.compare_sets || 0} tone="info" />
        <StatTile label="Search Views" value={summary.search_views || 0} tone="info" />
      </div>
      <ProjectTable rows={data?.projects || []} workspaces={data?.workspaces || []} researches={data?.researches || []} runs={data?.runs || []} onSelect={selectProject} />
      <DashboardActivityHeatmap data={data} />
      <div className="grid gap-5 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-8">
          <RecentResultsPanel runs={recentRuns} onSelectRun={selectRun} onSelectBranch={selectBranch} />
          <ActiveResearchPanel rows={activeResearchRows} selectResearch={selectResearch} selectRun={selectRun} />
        </div>
        <div className="space-y-5 xl:col-span-4">
          <QualityInboxPanel runs={issueRuns} onSelectRun={selectRun} />
          <DecisionCandidatesPanel runs={decisionRuns} onSelectRun={selectRun} />
        </div>
      </div>
      <DashboardCollapsedSection title="System Overview">
        <div className="space-y-5 p-4">
          <DashboardActivityTimeline data={data} selectProject={selectProject} selectResearch={selectResearch} selectRun={selectRun} />
          <WorkspacePanel workspaces={data?.workspaces || []} projects={data?.projects || []} onChanged={onChanged} />
          <SystemStatusPanel />
          {SHOW_SWEEPS ? <SweepTable sweeps={data?.sweeps || []} onSelect={selectSweep} /> : null}
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function RecentResultsPanel({ runs, onSelectRun, onSelectBranch }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Results" icon={LineChart} />
      <DecisionRunsTable runs={runs} onSelectRun={onSelectRun} onSelectBranch={onSelectBranch} emptyText="No recent runs yet." />
    </Panel>
  );
}

function QualityInboxPanel({ runs, onSelectRun }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Quality Inbox" icon={AlertTriangle} />
      <div className="divide-y divide-line">
        {runs.length ? runs.map((run) => (
          <button className="block w-full px-5 py-4 text-left transition hover:bg-white/45" key={run.id} onClick={() => onSelectRun(run.id)} type="button">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{run.name}</div>
                <div className="mt-1 text-xs text-muted">{run.branch_key || run.branch_id} · {t(runQualityHint(run))}</div>
              </div>
              <StatusBadge status={run.status} />
            </div>
          </button>
        )) : <div className="p-5 text-sm text-muted">{t("No failed or suspicious recent runs.")}</div>}
      </div>
    </Panel>
  );
}

function ActiveResearchPanel({ rows, selectResearch, selectRun }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Active Research" icon={ListTree} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Research")}</th>
              <th className="px-4 py-3 text-right">{t("7D Runs")}</th>
              <th className="px-4 py-3 text-right">{t("Fail Rate")}</th>
              <th className="px-4 py-3 text-right">{t("Branches")}</th>
              <th className="px-4 py-3">{t("Champion")}</th>
              <th className="px-4 py-3 text-right">{t("Sharpe")}</th>
              <th className="px-4 py-3 text-right">{t("Last Run")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="transition hover:bg-white/45" key={row.research.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => selectResearch(row.research.id)} type="button">
                    {row.research.title || row.research.key}
                  </button>
                </td>
                <td className="table-cell text-right font-semibold text-positive">{row.runs7d}</td>
                <td className={`table-cell text-right font-semibold ${row.failureRate > 0.25 ? 'text-negative' : 'text-ink'}`}>{Math.round(row.failureRate * 100)}%</td>
                <td className="table-cell text-right text-muted">{row.branchCount}</td>
                <td className="table-cell">
                  {row.champion ? (
                    <button className="font-semibold text-ink hover:text-info" onClick={() => selectRun(row.champion.id)} type="button">
                      {row.champion.name}
                    </button>
                  ) : <span className="text-muted">--</span>}
                </td>
                <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(row.champion, 'strategy.summary', 'sharpe'))}</td>
                <td className="table-cell text-right text-muted">{formatDate(row.lastRunTime || row.research.updated_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="7">{t("No active research yet.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function DecisionCandidatesPanel({ runs, onSelectRun }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Decision Candidates" icon={Trophy} />
      <div className="divide-y divide-line">
        {runs.length ? runs.map((run) => (
          <button className="block w-full px-5 py-4 text-left transition hover:bg-white/45" key={run.id} onClick={() => onSelectRun(run.id)} type="button">
            <div className="truncate text-sm font-semibold text-ink">{run.name}</div>
            <div className="mt-1 grid grid-cols-3 gap-2 text-xs text-muted">
              <span>Sharpe {formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</span>
              <span>DD {formatMetric(metricValue(run, 'strategy.summary', 'max_drawdown'))}</span>
              <span>{runRuntime(run)}</span>
            </div>
          </button>
        )) : <div className="p-5 text-sm text-muted">{t("No completed candidates yet.")}</div>}
      </div>
    </Panel>
  );
}

function DecisionRunsTable({ runs, onSelectRun, onSelectBranch, emptyText }) {
  const orderedRuns = sortRunsByRecentActivity(runs);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[920px] border-collapse">
        <thead className="table-head">
          <tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Branch")}</th><th className="px-4 py-3">{t("Status")}</th><th className="px-4 py-3">{t("Creator")}</th><th className="px-4 py-3 text-right">{t("Sharpe")}</th><th className="px-4 py-3 text-right">{t("Runtime")}</th><th className="px-4 py-3 text-right">{t("Updated")}</th></tr>
        </thead>
        <tbody>
          {orderedRuns.length ? orderedRuns.map((run) => (
            <tr className="transition hover:bg-white/45" key={run.id}>
              <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectRun(run.id)} type="button">{run.name}</button></td>
              <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectBranch(run.branch_id)} type="button">{run.branch_key || run.branch_id || '--'}</button></td>
              <td className="table-cell"><StatusBadge status={run.status} /></td>
              <td className="table-cell text-muted">{runCreator(run)}</td>
              <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</td>
              <td className="table-cell text-right text-muted">{runRuntime(run)}</td>
              <td className="table-cell text-right text-muted">{formatDate(run.updated_at || run.ended_at || run.started_at || run.created_at)}</td>
            </tr>
          )) : <tr><td className="table-cell text-muted" colSpan="7">{emptyText}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function dashboardIssueRuns(runs) {
  return [...(runs || [])]
    .filter((run) => run.status === 'failed' || run.status === 'cancelled' || runQualityHint(run) !== 'needs review')
    .sort((a, b) => dateMillis(b.updated_at || b.ended_at || b.created_at) - dateMillis(a.updated_at || a.ended_at || a.created_at));
}

function runQualityHint(run) {
  if (run.status === 'failed') return 'failed';
  if (run.status === 'cancelled') return 'cancelled';
  if (!Number.isFinite(Number(metricValue(run, 'strategy.summary', 'sharpe'))) && (run.artifact_count || 0) === 0) return 'missing result evidence';
  return 'needs review';
}

function DashboardCollapsedSection({ title, children }) {
  return (
    <details className="group rounded-bento border border-line bg-panel">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-semibold text-ink marker:hidden">
        <span>{title}</span>
        <CollapseToggleIcon native />
      </summary>
      <div className="border-t border-line">{children}</div>
    </details>
  );
}

function CollapseToggleIcon({ open = false, native = false }) {
  const rotateClass = native ? 'group-open:rotate-180' : open ? 'rotate-180' : '';
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted transition hover:bg-white/70 hover:text-ink"
    >
      <ChevronDown className={`h-4 w-4 transition ${rotateClass}`} strokeWidth={2.2} />
    </span>
  );
}

function DashboardActivityHeatmap({ data }) {
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(0);
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return undefined;
    const measure = () => setContainerWidth(node.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);
  const visibleWeeks = Math.max(53, Math.floor(Math.max(containerWidth - 88, 0) / 15));
  const { weeks, max, monthLabels, yearLabels } = dashboardHeatmapData(data, visibleWeeks);
  const heatmapColumns = `44px repeat(${weeks.length}, 12px)`;
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="活动历史" icon={Activity} />
      <div className="overflow-hidden p-4" ref={containerRef}>
        <div className="inline-block">
          <div className="mb-1 grid gap-[3px]" style={{ gridTemplateColumns: heatmapColumns }}>
            <div style={{ gridColumn: 1, gridRow: 1 }} />
            {yearLabels.map((label) => (
              <div className="h-4 text-xs font-semibold text-muted" key={label.key} style={{ gridColumn: `${label.week + 2} / span 4`, gridRow: 1 }}>{label.year}</div>
            ))}
            <div style={{ gridColumn: 1, gridRow: 2 }} />
            {monthLabels.map((label) => (
              <div className="h-4 text-xs font-semibold text-muted" key={label.key} style={{ gridColumn: `${label.week + 2} / span 4`, gridRow: 2 }}>{label.month}</div>
            ))}
          </div>
          <div className="grid gap-[3px]" style={{ gridTemplateColumns: heatmapColumns }}>
            {['Mon', '', 'Wed', '', 'Fri', '', ''].map((label, day) => (
              <React.Fragment key={`row-${day}`}>
                <div className="h-3 pr-2 text-right text-[11px] leading-3 text-muted">{label}</div>
                {weeks.map((week) => {
                  const cell = week.days[day];
                  return (
                    <div
                      className="h-3 w-3 rounded-[3px]"
                      key={cell.key}
                      style={{ backgroundColor: heatmapRed(cell.count, max) }}
                      title={`${cell.dateLabel}: ${cell.count} runs`}
                    />
                  );
                })}
              </React.Fragment>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted">
            <span>Less</span>
            {[0, 1, 2, 3, 4].map((level) => <span className="h-3 w-3 rounded-[3px]" key={level} style={{ backgroundColor: heatmapRed(level, 4) }} />)}
            <span>More</span>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function DashboardActivityTimeline({ data, selectProject, selectResearch, selectRun }) {
  const groups = dashboardTimelineGroups(data);
  const handlers = { project: selectProject, research: selectResearch, run: selectRun };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Activity" icon={Activity} />
      <div className="p-5">
        {groups.length ? (
          <div className="space-y-7">
            {groups.map((group) => (
              <div className="relative pl-8" key={group.type}>
                <div className="absolute bottom-0 left-[10px] top-8 w-px bg-line" />
                <div className="absolute left-0 top-[2px] flex h-5 w-5 items-center justify-center text-muted">
                  <group.icon className="h-5 w-5" />
                </div>
                <div className="mb-3 flex items-center gap-3">
                  <h3 className="text-base font-semibold text-ink">{group.title}</h3>
                  <div className="h-px flex-1 bg-line" />
                </div>
                <div className="space-y-2">
                  {group.items.map((item) => (
                    <button
                      className="grid w-full grid-cols-[1fr_auto] gap-3 rounded-md px-3 py-2 text-left transition hover:bg-white/45"
                      key={item.id}
                      onClick={() => handlers[item.kind]?.(item.targetId)}
                      type="button"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-ink">{item.title}</span>
                        <span className="mt-0.5 block truncate text-xs text-muted">{item.detail}</span>
                      </span>
                      <span className="shrink-0 text-xs text-muted">{formatDate(item.at)}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted">{t("No project, research, or run activity yet.")}</div>
        )}
      </div>
    </Panel>
  );
}

function WorkspacePanel({ workspaces, projects, onChanged }) {
  const [editingWorkspace, setEditingWorkspace] = useState(null);
  const projectCountByWorkspace = projects.reduce((counts, project) => {
    counts[project.workspace_id] = (counts[project.workspace_id] || 0) + 1;
    return counts;
  }, {});
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Workspaces" icon={Boxes} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead className="table-head">
            <tr><th className="px-4 py-3">{t("Workspace")}</th><th className="px-4 py-3">{t("Key")}</th><th className="px-4 py-3">{t("Description")}</th><th className="px-4 py-3 text-right">{t("Projects")}</th><th className="px-4 py-3">{t("Updated")}</th><th className="px-4 py-3 text-right">{t("Actions")}</th></tr>
          </thead>
          <tbody>
            {workspaces.length ? workspaces.map((workspace) => (
              <tr className="hover:bg-white/45" key={workspace.id}>
                <td className="table-cell font-semibold text-ink">{workspace.title}</td>
                <td className="table-cell text-muted">{workspace.key}</td>
                <td className="table-cell text-muted">{workspace.description || '--'}</td>
                <td className="table-cell text-right">{projectCountByWorkspace[workspace.id] || 0}</td>
                <td className="table-cell text-muted">{formatDate(workspace.updated_at)}</td>
                <td className="table-cell text-right">
                  <button className="icon-button" type="button" onClick={() => setEditingWorkspace(workspace)} aria-label={`Edit workspace ${workspace.key}`} title="Edit workspace">
                    <Pencil className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="6">{t("No workspaces yet.")}</td></tr>}
          </tbody>
        </table>
      </div>
      {editingWorkspace ? <WorkspaceEditModal workspace={editingWorkspace} onClose={() => setEditingWorkspace(null)} onChanged={onChanged} /> : null}
    </Panel>
  );
}

function SystemStatusPanel() {
  const [status, setStatus] = useState({ health: null, auth: null, database: null, runtime: null, error: null });
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [health, auth, database, runtime] = await Promise.allSettled([
        apiGet('/healthz'),
        apiGet('/api/v1/auth/status'),
        apiGet('/api/v1/system/db-status'),
        apiGet('/api/v1/system/runtime-status'),
      ]);
      if (cancelled) return;
      const errors = [health, auth, database, runtime]
        .filter((result) => result.status === 'rejected')
        .map((result) => result.reason?.message || 'request failed');
      setStatus({
        health: health.status === 'fulfilled' ? health.value : null,
        auth: auth.status === 'fulfilled' ? auth.value : null,
        database: database.status === 'fulfilled' ? database.value : null,
        runtime: runtime.status === 'fulfilled' ? runtime.value : null,
        error: errors.join('; ') || null,
      })
    };
    load();
    return () => { cancelled = true; };
  }, []);
  const missingCount = (status.database?.missing_tables?.length || 0) + Object.values(status.database?.missing_columns || {}).reduce((total, columns) => total + columns.length, 0);
  const artifactTarget = formatArtifactTarget(status.runtime);
  const missingDetail = formatMissingSchemaDetail(status.database);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="System Status" icon={Activity} />
      <div className="grid gap-4 p-4 md:grid-cols-4 xl:grid-cols-8">
        <ReadOnlyField label="API" value={status.health?.status || (status.error ? 'unavailable' : 'checking')} />
        <ReadOnlyField label="Auth" value={status.auth ? (status.auth.auth_enabled ? 'enabled' : 'disabled') : '--'} />
        <ReadOnlyField label="Token" value={status.auth ? (status.auth.token_configured ? 'configured' : 'not configured') : '--'} />
        <ReadOnlyField label="DB Schema" value={status.database ? (status.database.needs_migration ? 'migration needed' : 'current') : '--'} />
        <ReadOnlyField label="DB Version" value={status.database ? `${status.database.database_version} / ${status.database.current_version}` : '--'} />
        <ReadOnlyField label="Missing" value={status.database ? String(missingCount) : '--'} />
        <ReadOnlyField label="Storage" value={status.runtime?.artifact_storage || '--'} />
        <ReadOnlyField label="Artifact Target" value={artifactTarget} code />
        <ReadOnlyField label="Worker" value={status.runtime?.worker_backend || '--'} />
        {missingDetail ? <ReadOnlyField label="Missing Detail" value={missingDetail} code /> : null}
        {status.error ? <ReadOnlyField label="Error" value={status.error} /> : null}
      </div>
    </Panel>
  );
}

function formatArtifactTarget(runtime) {
  if (!runtime) return '--';
  if (runtime.artifact_storage === 'local') return runtime.artifact_root || '--';
  if (runtime.artifact_storage === 's3') {
    const bucket = runtime.s3_bucket || '--';
    const prefix = runtime.s3_prefix ? `/${runtime.s3_prefix}` : '';
    return `s3://${bucket}${prefix}`;
  }
  return '--';
}

function formatMissingSchemaDetail(database) {
  if (!database) return '';
  const parts = [];
  if (database.missing_tables?.length) parts.push(`tables: ${database.missing_tables.join(', ')}`);
  Object.entries(database.missing_columns || {}).forEach(([table, columns]) => {
    if (columns?.length) parts.push(`${table}: ${columns.join(', ')}`);
  });
  return parts.join(' | ');
}

function CreateModal({ kind, data, onClose, onCreated }) {
  const action = createActions.find((item) => item.id === kind);
  const handleCreated = async (createdKind, entity) => {
    await onCreated(createdKind, entity);
    onClose();
  };
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-ink/25 px-4 py-16 backdrop-blur-sm" role="dialog" aria-modal="true" onPointerDown={onClose}>
      <div className="max-h-[calc(100vh-8rem)] w-full max-w-lg overflow-hidden rounded-md border border-line bg-panel shadow-xl" onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <div className="text-xs font-semibold uppercase text-muted">{t("New")}</div>
            <h2 className="text-lg font-semibold text-ink">{action?.label || 'Item'}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[calc(100vh-14rem)] overflow-y-auto p-4">
          {kind === 'workspace' ? <WorkspaceForm onCreated={handleCreated} /> : null}
          {kind === 'project' ? <ProjectForm data={data} onCreated={handleCreated} /> : null}
          {kind === 'research' ? <ResearchForm data={data} onCreated={handleCreated} /> : null}
          {kind === 'branch' ? <BranchForm data={data} onCreated={handleCreated} /> : null}
          {kind === 'run' ? <RunForm data={data} onCreated={handleCreated} /> : null}
          {kind === 'sweep' ? <GlobalSweepCreateForm branches={data?.branches || []} onChanged={async () => {}} onCreated={(id) => handleCreated('sweep', { id })} /> : null}
          {kind === 'compare-set' ? <CompareSetCreateForm data={data} onCreated={handleCreated} /> : null}
          {kind === 'search-view' ? <SearchViewCreateForm data={data} onCreated={handleCreated} /> : null}
        </div>
      </div>
    </div>
  );
}

function FormCard({ title, children }) {
  return (
    <div className="rounded-md border border-line bg-white/55 p-4">
      <h3 className="text-sm font-semibold text-ink">{tx(title)}</h3>
      <div className="mt-3 space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  const fieldId = useId();
  const visibleLabel = tx(label);
  const fieldName = String(label).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'field';
  const control = React.isValidElement(children)
    ? React.cloneElement(children, {
        id: children.props.id || fieldId,
        name: children.props.name || fieldName,
        autoComplete: children.props.autoComplete || 'off',
        'aria-label': children.props['aria-label'] || visibleLabel,
      })
    : children;
  return (
    <label className="block text-xs font-semibold text-muted">
      <span>{visibleLabel}</span>
      <div className="mt-1">{control}</div>
    </label>
  );
}

function TextInput(props) {
  return <input {...props} className={`form-control ${props.className || ''}`} />;
}

function TextArea(props) {
  return <textarea {...props} className={`form-control min-h-[72px] resize-y ${props.className || ''}`} />;
}

function SelectInput(props) {
  return <select {...props} className={`form-control ${props.className || ''}`} />;
}

function SubmitButton({ loading, children }) {
  return (
    <button className="primary-button mt-2 w-full" disabled={loading}>
      {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
      {tx(children)}
    </button>
  );
}

function InlineError({ message }) {
  if (!message) return null;
  return <div className="rounded-md bg-negativeSoft px-3 py-2 text-xs font-semibold text-negative">{message}</div>;
}

function EditPanelAction({ editing, onEdit, label = 'Edit metadata' }) {
  const visibleLabel = t(label);
  return (
    <div className="flex items-center gap-2">
      {!editing ? (
        <button className="icon-button" type="button" onClick={onEdit} aria-label={visibleLabel} title={visibleLabel}>
          <Pencil className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

function ReadOnlyField({ label, value, multiline = false, code = false }) {
  const valueRef = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const empty = value === undefined || value === null || value === '';
  const text = empty ? '' : String(value);
  const displayValue = multiline || code ? text.replace(/\s+/g, ' ').trim() : text;
  useEffect(() => {
    const node = valueRef.current;
    if (!node) return undefined;
    const measure = () => setOverflowing(node.scrollWidth > node.clientWidth + 1);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [displayValue]);
  useEffect(() => {
    setExpanded(false);
  }, [displayValue]);
  return (
    <div>
      <div className="mb-1 text-xs font-semibold text-muted">{tx(label)}</div>
      <div className={`flex min-h-6 items-start gap-2 text-sm text-ink ${code ? 'font-mono text-xs' : 'font-medium'}`} title={displayValue}>
        {empty ? (
          <span className="text-muted">--</span>
        ) : (
          <>
            <span ref={valueRef} className={`min-w-0 flex-1 ${expanded ? 'whitespace-normal break-words' : 'truncate'}`}>{displayValue}</span>
            {(overflowing || expanded) ? (
              <button className="shrink-0 text-xs font-semibold text-info hover:underline" type="button" onClick={() => setExpanded((current) => !current)}>
                {expanded ? t('Less') : t('More')}
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

const defaultRetentionPolicyText = '{\n  "preview_retention_days": null,\n  "raw_artifact_retention_days": null,\n  "max_artifact_bytes": null\n}';

function WorkspaceForm({ onCreated }) {
  const [form, setForm] = useState({ key: '', title: '', description: '', roles: '{}' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const workspace = await apiPost('/api/v1/workspaces', {
        key: form.key,
        title: form.title,
        description: form.description,
        roles: parseJsonObject(form.roles),
      });
      setForm({ key: '', title: '', description: '', roles: '{}' });
      await onCreated('workspace', workspace);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Workspace">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Key"><TextInput required value={form.key} onChange={(event) => update('key', event.target.value)} placeholder="local" /></Field>
        <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} placeholder="Local Workspace" /></Field>
        <Field label="Description"><TextArea value={form.description} onChange={(event) => update('description', event.target.value)} /></Field>
        <Field label="Roles JSON"><TextArea value={form.roles} onChange={(event) => update('roles', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Create workspace</SubmitButton>
      </form>
    </FormCard>
  );
}

function WorkspaceEditModal({ workspace, onClose, onChanged }) {
  const [form, setForm] = useState({
    title: workspace.title || '',
    description: workspace.description || '',
    roles: JSON.stringify(workspace.roles_json || {}, null, 2),
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/workspaces/${workspace.id}`, {
        title: form.title,
        description: form.description || null,
        roles: parseJsonObject(form.roles),
      });
      await onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-ink/25 px-4 py-16 backdrop-blur-sm" role="dialog" aria-modal="true" onPointerDown={onClose}>
      <div className="max-h-[calc(100vh-8rem)] w-full max-w-lg overflow-hidden rounded-md border border-line bg-panel shadow-xl" onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="truncate text-lg font-semibold text-ink">{workspace.key}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close workspace editor">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
        <form className="max-h-[calc(100vh-14rem)] space-y-2 overflow-y-auto p-4" onSubmit={submit}>
          <ReadOnlyField label="ID" value={workspace.id} />
          <ReadOnlyField label="Key" value={workspace.key} />
          <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
          <Field label="Description"><TextArea value={form.description} onChange={(event) => update('description', event.target.value)} /></Field>
          <Field label="Roles JSON"><TextArea value={form.roles} onChange={(event) => update('roles', event.target.value)} /></Field>
          <InlineError message={error} />
          <SubmitButton loading={loading}>Update workspace</SubmitButton>
        </form>
      </div>
    </div>
  );
}

function ProjectForm({ data, onCreated }) {
  const firstWorkspaceId = data?.workspaces?.[0]?.id || 'local';
  const [form, setForm] = useState({ workspace_id: firstWorkspaceId, key: '', title: '', description: '', retention_policy: defaultRetentionPolicyText });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.workspace_id && firstWorkspaceId) setForm((current) => ({ ...current, workspace_id: firstWorkspaceId }));
  }, [firstWorkspaceId, form.workspace_id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const project = await apiPost('/api/v1/projects', { workspace_id: form.workspace_id, key: form.key, title: form.title, description: form.description, tags: [], retention_policy: compactObject(parseJsonObject(form.retention_policy)) });
      setForm((current) => ({ ...current, key: '', title: '', description: '', retention_policy: defaultRetentionPolicyText }));
      await onCreated('project', project);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Project">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Workspace">
          <SelectInput required value={form.workspace_id} onChange={(event) => update('workspace_id', event.target.value)}>
            {(data?.workspaces || [{ id: 'local', key: 'local' }]).map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Key"><TextInput required value={form.key} onChange={(event) => update('key', event.target.value)} placeholder="alpha-lab" /></Field>
        <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} placeholder="Alpha Lab" /></Field>
        <Field label="Description"><TextArea value={form.description} onChange={(event) => update('description', event.target.value)} /></Field>
        <Field label="Retention Policy JSON"><TextArea value={form.retention_policy} onChange={(event) => update('retention_policy', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Create project</SubmitButton>
      </form>
    </FormCard>
  );
}

function ResearchForm({ data, onCreated }) {
  const firstProjectKey = data?.projects?.[0]?.key || '';
  const [form, setForm] = useState({ project_key: firstProjectKey, key: '', title: '', goal: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.project_key && firstProjectKey) setForm((current) => ({ ...current, project_key: firstProjectKey }));
  }, [firstProjectKey, form.project_key]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const research = await apiPost('/api/v1/researches', form);
      setForm((current) => ({ ...current, key: '', title: '', goal: '' }));
      await onCreated('research', research);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Research">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Project">
          <SelectInput required value={form.project_key} onChange={(event) => update('project_key', event.target.value)}>
            <option value="" disabled>{t("Select project")}</option>
            {(data?.projects || []).map((project) => <option key={project.id} value={project.key}>{project.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Key"><TextInput required value={form.key} onChange={(event) => update('key', event.target.value)} placeholder="csi500-reversal" /></Field>
        <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
        <Field label="Goal"><TextArea value={form.goal} onChange={(event) => update('goal', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Create research</SubmitButton>
      </form>
    </FormCard>
  );
}

function BranchForm({ data, onCreated }) {
  const firstResearchId = data?.researches?.[0]?.id || '';
  const [form, setForm] = useState({
    research_id: firstResearchId,
    key: '',
    title: '',
    parent_branch_id: '',
    source_run_id: '',
    reason_code: '',
    reason_summary: '',
    hypothesis: '',
    expected_change: '{}',
    created_by_type: 'human',
    created_by_id: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.research_id && firstResearchId) setForm((current) => ({ ...current, research_id: firstResearchId }));
  }, [firstResearchId, form.research_id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const branch = await apiPost('/api/v1/branches', compactObject({
        research_id: form.research_id,
        key: form.key,
        title: form.title,
        parent_branch_id: form.parent_branch_id || null,
        source_run_id: form.source_run_id || null,
        reason_code: form.reason_code || null,
        reason_summary: form.reason_summary || null,
        hypothesis: form.hypothesis || null,
        expected_change: compactObject(parseJsonObject(form.expected_change)),
        created_by_type: form.created_by_type || 'human',
        created_by_id: form.created_by_id || null,
      }));
      setForm((current) => ({ ...current, key: '', title: '', parent_branch_id: '', source_run_id: '', reason_code: '', reason_summary: '', hypothesis: '', expected_change: '{}', created_by_type: 'human', created_by_id: '' }));
      await onCreated('branch', branch);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Branch">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Research">
          <SelectInput required value={form.research_id} onChange={(event) => update('research_id', event.target.value)}>
            <option value="" disabled>{t("Select research")}</option>
            {(data?.researches || []).map((research) => <option key={research.id} value={research.id}>{research.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Key"><TextInput required value={form.key} onChange={(event) => update('key', event.target.value)} placeholder="baseline-v1" /></Field>
        <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
        <Field label="Parent branch">
          <SelectInput value={form.parent_branch_id} onChange={(event) => update('parent_branch_id', event.target.value)}>
            <option value="">{t("None")}</option>
            {(data?.branches || []).filter((branch) => !form.research_id || branch.research_id === form.research_id).map((branch) => <option key={branch.id} value={branch.id}>{branch.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="From run">
          <SelectInput value={form.source_run_id} onChange={(event) => update('source_run_id', event.target.value)}>
            <option value="">{t("None")}</option>
            {(data?.runs || []).filter((run) => !form.research_id || (data?.branches || []).some((branch) => branch.id === run.branch_id && branch.research_id === form.research_id)).map((run) => <option key={run.id} value={run.id}>{run.name}</option>)}
          </SelectInput>
        </Field>
        <Field label="Reason code"><TextInput value={form.reason_code} onChange={(event) => update('reason_code', event.target.value)} placeholder="fee-model-change" /></Field>
        <Field label="Reason summary"><TextInput value={form.reason_summary} onChange={(event) => update('reason_summary', event.target.value)} /></Field>
        <Field label="Hypothesis"><TextArea value={form.hypothesis} onChange={(event) => update('hypothesis', event.target.value)} /></Field>
        <Field label="Expected Change JSON"><TextArea value={form.expected_change} onChange={(event) => update('expected_change', event.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Creator">
            <SelectInput value={form.created_by_type} onChange={(event) => update('created_by_type', event.target.value)}>
              <option value="human">human</option>
              <option value="agent">agent</option>
              <option value="system">system</option>
            </SelectInput>
          </Field>
          <Field label="Creator ID"><TextInput value={form.created_by_id} onChange={(event) => update('created_by_id', event.target.value)} placeholder="agent-alpha" /></Field>
        </div>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Create branch</SubmitButton>
      </form>
    </FormCard>
  );
}

function RunForm({ data, onCreated }) {
  const firstBranchId = data?.branches?.[0]?.id || '';
  const [form, setForm] = useState({ branch_id: firstBranchId, name: '', title: '', source_run_id: '', config: '{}', context: '{}', tags: '', created_by_type: 'human', created_by_id: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.branch_id && firstBranchId) setForm((current) => ({ ...current, branch_id: firstBranchId }));
  }, [firstBranchId, form.branch_id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const run = await apiPost('/api/v1/runs', {
        branch_id: form.branch_id,
        name: form.name,
        title: form.title || null,
        source_run_id: form.source_run_id || null,
        config: parseJsonObject(form.config),
        context: parseJsonObject(form.context),
        tags: parseCsv(form.tags),
        created_by_type: form.created_by_type || 'human',
        created_by_id: form.created_by_id || null,
      });
      setForm((current) => ({ ...current, name: '', title: '', source_run_id: '', config: '{}', context: '{}', tags: '', created_by_type: 'human', created_by_id: '' }));
      await onCreated('run', run);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Run">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Branch">
          <SelectInput required value={form.branch_id} onChange={(event) => update('branch_id', event.target.value)}>
            <option value="" disabled>{t("Select branch")}</option>
            {(data?.branches || []).map((branch) => <option key={branch.id} value={branch.id}>{branch.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="lb20_hold5_fee10bp" /></Field>
        <Field label="Title"><TextInput value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
        <Field label="Source run">
          <SelectInput value={form.source_run_id} onChange={(event) => update('source_run_id', event.target.value)}>
            <option value="">{t("None")}</option>
            {(data?.runs || []).filter((run) => !form.branch_id || run.branch_id === form.branch_id).map((run) => <option key={run.id} value={run.id}>{run.name}</option>)}
          </SelectInput>
        </Field>
        <Field label="Author">
          <SelectInput value={form.created_by_type} onChange={(event) => update('created_by_type', event.target.value)}>
            <option value="human">human</option>
            <option value="agent">agent</option>
            <option value="system">system</option>
          </SelectInput>
        </Field>
        <Field label="Creator ID"><TextInput value={form.created_by_id} onChange={(event) => update('created_by_id', event.target.value)} placeholder="agent-alpha" /></Field>
        <Field label="Config JSON"><TextArea required value={form.config} onChange={(event) => update('config', event.target.value)} /></Field>
        <Field label="Context JSON"><TextArea value={form.context} onChange={(event) => update('context', event.target.value)} /></Field>
        <Field label="Tags"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} placeholder="baseline,reversal" /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Start run</SubmitButton>
      </form>
    </FormCard>
  );
}

function CompareSetCreateForm({ data, onCreated }) {
  const firstProjectId = data?.projects?.[0]?.id || '';
  const [form, setForm] = useState({
    project_id: firstProjectId,
    research_id: '',
    name: '',
    run_ids: '',
    layout: '{"metrics":["strategy.summary.sharpe"],"series":[]}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const candidateRuns = useMemo(
    () => (data?.runs || []).filter((run) => (
      (!form.project_id || run.project_id === form.project_id)
      && (!form.research_id || run.research_id === form.research_id)
    )),
    [data?.runs, form.project_id, form.research_id],
  );
  const researchOptions = useMemo(
    () => (data?.researches || []).filter((research) => !form.project_id || research.project_id === form.project_id),
    [data?.researches, form.project_id],
  );
  const selectedRunIds = parseCsv(form.run_ids);
  useEffect(() => {
    if (!form.project_id && firstProjectId) setForm((current) => ({ ...current, project_id: firstProjectId }));
  }, [firstProjectId, form.project_id]);
  const update = (field, value) => {
    setForm((current) => {
      if (field !== 'project_id' && field !== 'research_id') return { ...current, [field]: value };
      const nextProjectId = field === 'project_id' ? value : current.project_id;
      const nextResearchId = field === 'project_id'
        ? ((data?.researches || []).some((research) => research.id === current.research_id && research.project_id === value) ? current.research_id : '')
        : value;
      const allowedIds = new Set((data?.runs || [])
        .filter((run) => (!nextProjectId || run.project_id === nextProjectId) && (!nextResearchId || run.research_id === nextResearchId))
        .map((run) => run.id));
      return { ...current, project_id: nextProjectId, research_id: nextResearchId, run_ids: parseCsv(current.run_ids).filter((id) => allowedIds.has(id)).join(',') };
    });
  };
  const toggleRun = (runId) => {
    setForm((current) => {
      const currentIds = parseCsv(current.run_ids);
      const nextIds = currentIds.includes(runId) ? currentIds.filter((id) => id !== runId) : [...currentIds, runId];
      return { ...current, run_ids: nextIds.join(',') };
    });
  };
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const runIds = parseCsv(form.run_ids);
      if (!runIds.length) throw new Error('Choose at least one run.');
      const compareSet = await apiPost('/api/v1/compare-sets', {
        project_id: form.project_id,
        research_id: form.research_id || null,
        name: form.name,
        run_ids: runIds,
        layout: parseJsonObject(form.layout),
      });
      await onCreated('compare-set', compareSet);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Compare Set">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Project">
          <SelectInput required value={form.project_id} onChange={(event) => update('project_id', event.target.value)}>
            <option value="" disabled>{t("Select project")}</option>
            {(data?.projects || []).map((project) => <option key={project.id} value={project.id}>{project.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Research">
          <SelectInput value={form.research_id} onChange={(event) => update('research_id', event.target.value)}>
            <option value="">{t("Project-level")}</option>
            {researchOptions.map((research) => <option key={research.id} value={research.id}>{research.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="baseline-vs-candidate" /></Field>
        <Field label={`Runs (${selectedRunIds.length})`}><TextInput required value={form.run_ids} onChange={(event) => update('run_ids', event.target.value)} placeholder="run_1,run_2" /></Field>
        <div className="overflow-hidden rounded-md border border-line bg-white/45">
          <div className="max-h-56 overflow-y-auto">
            {candidateRuns.length ? candidateRuns.map((run) => (
              <label className="flex cursor-pointer items-center gap-3 border-b border-line/60 px-3 py-2 text-sm last:border-b-0 hover:bg-white/70" key={run.id}>
                <input checked={selectedRunIds.includes(run.id)} className="h-4 w-4 accent-charcoal" onChange={() => toggleRun(run.id)} type="checkbox" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-ink">{run.name}</span>
                  <span className="block truncate text-xs text-muted">{run.branch_key || run.branch_id} · {formatDate(run.updated_at)}</span>
                </span>
                <span className="shrink-0 text-xs font-semibold tabular-nums text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</span>
              </label>
            )) : <div className="px-3 py-4 text-sm text-muted">{t("No runs in this project.")}</div>}
          </div>
        </div>
        <Field label="Layout JSON"><TextArea value={form.layout} onChange={(event) => update('layout', event.target.value)} /></Field>
        <InlineError message={error || (!(data?.projects || []).length ? 'Create a project before saving compare sets.' : null)} />
        <SubmitButton loading={loading}>Save compare set</SubmitButton>
      </form>
    </FormCard>
  );
}

function SearchViewCreateForm({ data, onCreated }) {
  const firstProjectId = data?.projects?.[0]?.id || '';
  const firstProjectKey = data?.projects?.[0]?.key || '';
  const [form, setForm] = useState({
    project_id: firstProjectId,
    name: '',
    description: '',
    project_key: firstProjectKey,
    research_key: '',
    branch_key: '',
    status: '',
    tags: '',
    metric: 'strategy.summary.sharpe',
    op: '>',
    metric_value: '',
    author_type: '',
    has_artifact: '',
    limit: '50',
    filters: '{}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.project_id && firstProjectId) setForm((current) => ({ ...current, project_id: firstProjectId, project_key: current.project_key || firstProjectKey }));
  }, [firstProjectId, firstProjectKey, form.project_id]);
  const update = (field, value) => {
    setForm((current) => {
      if (field !== 'project_id') return { ...current, [field]: value };
      const project = (data?.projects || []).find((item) => item.id === value);
      return { ...current, project_id: value, project_key: project?.key || current.project_key };
    });
  };
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const structuredFilters = buildSearchFilters(form);
      const advancedFilters = parseJsonObject(form.filters);
      const searchView = await apiPost('/api/v1/search-views', {
        project_id: form.project_id,
        name: form.name,
        description: form.description || null,
        filters: compactObject({ ...structuredFilters, ...advancedFilters }),
      });
      await onCreated('search-view', searchView);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Search View">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Project">
          <SelectInput required value={form.project_id} onChange={(event) => update('project_id', event.target.value)}>
            <option value="" disabled>{t("Select project")}</option>
            {(data?.projects || []).map((project) => <option key={project.id} value={project.id}>{project.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="recent-post-cost-winners" /></Field>
        <Field label="Description"><TextInput value={form.description} onChange={(event) => update('description', event.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Run project">
            <SelectInput value={form.project_key} onChange={(event) => update('project_key', event.target.value)}>
              <option value="">{t("Any project")}</option>
              {(data?.projects || []).map((project) => <option key={project.id} value={project.key}>{project.key}</option>)}
            </SelectInput>
          </Field>
          <Field label="Status">
            <SelectInput value={form.status} onChange={(event) => update('status', event.target.value)}>
              <option value="">{t("Any status")}</option>
              {['running', 'completed', 'failed', 'cancelled'].map((status) => <option key={status} value={status}>{tStatus(status)}</option>)}
            </SelectInput>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Research">
            <SelectInput value={form.research_key} onChange={(event) => update('research_key', event.target.value)}>
              <option value="">{t("Any research")}</option>
              {(data?.researches || []).map((research) => <option key={research.id} value={research.key}>{research.key}</option>)}
            </SelectInput>
          </Field>
          <Field label="Branch">
            <SelectInput value={form.branch_key} onChange={(event) => update('branch_key', event.target.value)}>
              <option value="">{t("Any branch")}</option>
              {(data?.branches || []).map((branch) => <option key={branch.id} value={branch.key}>{branch.key}</option>)}
            </SelectInput>
          </Field>
        </div>
        <Field label="Tags"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} placeholder="baseline,post-cost" /></Field>
        <div className="grid grid-cols-12 gap-2">
          <Field label="Metric"><TextInput className="col-span-12" value={form.metric} onChange={(event) => update('metric', event.target.value)} /></Field>
          <Field label="Op"><SelectInput value={form.op} onChange={(event) => update('op', event.target.value)}>{['>', '>=', '<', '<=', '==', '!='].map((op) => <option key={op} value={op}>{op}</option>)}</SelectInput></Field>
          <Field label="Value"><TextInput value={form.metric_value} onChange={(event) => update('metric_value', event.target.value)} placeholder="1.0" /></Field>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Author">
            <SelectInput value={form.author_type} onChange={(event) => update('author_type', event.target.value)}>
              <option value="">{t("Any author")}</option>
              {['human', 'agent', 'system'].map((author) => <option key={author} value={author}>{author}</option>)}
            </SelectInput>
          </Field>
          <Field label="Artifact kind">
            <SelectInput value={form.has_artifact} onChange={(event) => update('has_artifact', event.target.value)}>
              <option value="">{t("Any artifact")}</option>
              {artifactKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
            </SelectInput>
          </Field>
        </div>
        <Field label="Limit"><TextInput value={form.limit} onChange={(event) => update('limit', event.target.value)} type="number" min="1" /></Field>
        <Field label="Advanced filters JSON"><TextArea value={form.filters} onChange={(event) => update('filters', event.target.value)} /></Field>
        <InlineError message={error || (!(data?.projects || []).length ? 'Create a project before saving search views.' : null)} />
        <SubmitButton loading={loading}>Save search view</SubmitButton>
      </form>
    </FormCard>
  );
}

function SweepTable({ sweeps, onSelect = () => {} }) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const filteredSweeps = sweeps.filter((sweep) => {
    const matchesStatus = !status || sweep.status === status;
    const matchesQuery = !normalizedQuery || sweepSearchText(sweep).includes(normalizedQuery);
    return matchesStatus && matchesQuery;
  }).sort((a, b) => entityUpdatedMillis(b) - entityUpdatedMillis(a));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Sweeps" icon={Database} />
      <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1fr_180px_auto]">
        <Field label="Search sweeps"><TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="name, objective, branch, search space" /></Field>
        <Field label="Status">
          <SelectInput value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">{t("Any status")}</option>
            {['active', 'completed', 'archived'].map((item) => <option key={item} value={item}>{tStatus(item)}</option>)}
          </SelectInput>
        </Field>
        <div className="flex items-end text-xs font-semibold text-muted">{filteredSweeps.length} / {sweeps.length} shown</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Sweep")}</th>
              <th className="px-4 py-3">{t("Status")}</th>
              <th className="px-4 py-3">{t("Objective")}</th>
              <th className="px-4 py-3 text-right">{t("Runs")}</th>
              <th className="px-4 py-3 text-right">{t("Updated")}</th>
            </tr>
          </thead>
          <tbody>
            {filteredSweeps.length ? filteredSweeps.map((sweep) => (
              <tr className="transition hover:bg-white/45" key={sweep.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => onSelect(sweep.id)}>{sweep.name}</button>
                </td>
                <td className="table-cell"><Badge tone={sweep.status === 'active' ? 'positive' : 'neutral'}>{tStatus(sweep.status)}</Badge></td>
                <td className="table-cell text-muted">{formatSweepObjective(sweep.objective_json)}</td>
                <td className="table-cell text-right">{sweep.run_count || 0}</td>
                <td className="table-cell text-right text-muted">{formatDate(sweep.updated_at)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="5">{sweeps.length ? 'No sweeps match the current filters.' : 'No sweeps yet.'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function RecentActivityPanel({ data, selectBranch, selectRun }) {
  const activities = buildRecentActivities(data).slice(0, 12);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Activity" icon={Activity} />
      <div className="divide-y divide-line">
        {activities.length ? activities.map((item) => (
          <button
            className="block w-full px-5 py-4 text-left transition hover:bg-white/45"
            key={item.id}
            onClick={() => {
              if (item.run_id) selectRun(item.run_id);
              if (!item.run_id && item.branch_id) selectBranch(item.branch_id);
            }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{item.title}</div>
                <div className="mt-1 truncate text-xs text-muted">{item.detail}</div>
              </div>
              <div className="shrink-0 text-xs text-muted">{formatDate(item.at)}</div>
            </div>
          </button>
        )) : <div className="p-5 text-sm text-muted">{t("No recent activity yet.")}</div>}
      </div>
    </Panel>
  );
}

function ResearchTable({ rows, branches = [], runs = [], onSelect, onSelectRun }) {
  const sortedRows = [...(rows || [])].sort((a, b) => (
    latestRunMillisForResearch(b, branches, runs) - latestRunMillisForResearch(a, branches, runs)
    || entityUpdatedMillis(b) - entityUpdatedMillis(a)
  ));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Research" icon={TableProperties} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Research")}</th>
              <th className="px-4 py-3">{t("Project")}</th>
              <th className="px-4 py-3">{t("Status")}</th>
              <th className="px-4 py-3">{t("Champion Run")}</th>
              <th className="px-4 py-3 text-right">{t("Sharpe")}</th>
              <th className="px-4 py-3 text-right">{t("Max DD")}</th>
              <th className="px-4 py-3 text-right">{t("Branches")}</th>
              <th className="px-4 py-3 text-right">{t("Runs")}</th>
              <th className="px-4 py-3 text-right">{t("Updated")}</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => {
              const champion = researchChampionRun(row, branches, runs);
              return (
                <tr className="cursor-pointer transition hover:bg-white/45" key={row.id} onClick={() => onSelect(row.id)}>
                  <td className="table-cell font-semibold text-ink">{row.title || row.key}</td>
                  <td className="table-cell text-muted">{row.project_key}</td>
                  <td className="table-cell"><Badge tone={row.status === 'active' ? 'positive' : 'neutral'}>{tStatus(row.status)}</Badge></td>
                  <td className="table-cell">
                    {champion ? (
                      <button
                        className="font-semibold text-ink hover:underline"
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectRun?.(champion.id);
                        }}
                        type="button"
                      >
                        {champion.name}
                      </button>
                    ) : <span className="text-muted">--</span>}
                  </td>
                  <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(champion, 'strategy.summary', 'sharpe'))}</td>
                  <td className="table-cell text-right text-muted">{formatMetric(metricValue(champion, 'strategy.summary', 'max_drawdown'))}</td>
                  <td className="table-cell text-right">{row.branch_count || 0}</td>
                  <td className="table-cell text-right">{row.run_count || 0}</td>
                  <td className="table-cell text-right text-muted">{formatDate(row.updated_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ProjectTable({ rows, workspaces, researches, runs, onSelect }) {
  const workspaceById = Object.fromEntries((workspaces || []).map((workspace) => [workspace.id, workspace]));
  const sortedRows = [...(rows || [])].sort((a, b) => (
    latestRunMillisForProject(b, runs) - latestRunMillisForProject(a, runs)
    || entityUpdatedMillis(b) - entityUpdatedMillis(a)
  ));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Projects" icon={Database} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Project")}</th>
              <th className="px-4 py-3">{t("Key")}</th>
              <th className="px-4 py-3">{t("Workspace")}</th>
              <th className="px-4 py-3 text-right">{t("Researches")}</th>
              <th className="px-4 py-3 text-right">{t("Runs")}</th>
              <th className="px-4 py-3 text-right">{t("Updated")}</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.length ? sortedRows.map((row) => (
              <tr className="cursor-pointer transition hover:bg-white/45" key={row.id} onClick={() => onSelect(row.id)}>
                <td className="table-cell font-semibold text-ink">{row.title || row.key}</td>
                <td className="table-cell text-muted">{row.key}</td>
                <td className="table-cell text-muted">{row.workspace_key || workspaceById[row.workspace_id]?.key || row.workspace_id || '--'}</td>
                <td className="table-cell text-right">{row.research_count ?? researches.filter((item) => item.project_id === row.id).length}</td>
                <td className="table-cell text-right">{row.run_count ?? runs.filter((item) => item.project_id === row.id).length}</td>
                <td className="table-cell text-right text-muted">{formatDate(row.updated_at)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="6">{t("No projects yet.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ProjectPage({ data, selectedProjectId, selectResearch, selectBranch, selectRun, selectCompareSet, selectSearchView, onChanged }) {
  const projectBase = (data?.projects || []).find((item) => item.id === selectedProjectId) || data?.projects?.[0];
  const [projectDetail, setProjectDetail] = useState(null);
  const [projectDetailError, setProjectDetailError] = useState(null);
  useEffect(() => {
    if (!projectBase?.id) {
      setProjectDetail(null);
      setProjectDetailError(null);
      return;
    }
    let cancelled = false;
    setProjectDetail(null);
    apiGet(`/api/v1/projects/${projectBase.id}`)
      .then((payload) => {
        if (!cancelled) {
          setProjectDetail(payload);
          setProjectDetailError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setProjectDetail(null);
          setProjectDetailError(err.message);
        }
      });
    return () => { cancelled = true; };
  }, [projectBase?.id, projectBase?.updated_at, data?.summary?.runs, data?.summary?.compare_sets, data?.summary?.search_views]);
  if (!projectBase) return <EmptyState title="No projects yet" detail="Create a project from Dashboard, then record research runs through SDK or bbox CLI." />;
  const project = { ...projectBase, ...(projectDetail || {}) };
  const researches = projectDetail?.researches || (data?.researches || []).filter((item) => item.project_id === project.id);
  const branches = projectDetail?.branches || data?.branches || [];
  const runs = projectDetail?.runs || (data?.runs || []).filter((run) => run.project_id === project.id);
  const compareSets = projectDetail?.compare_sets || (data?.compare_sets || []).filter((item) => item.project_id === project.id);
  const searchViews = projectDetail?.search_views || (data?.search_views || []).filter((item) => item.project_id === project.id);
  const running = project.running_run_count ?? runs.filter((run) => run.status === 'running').length;
  return (
    <div className="space-y-5">
      <Hero eyebrow="Project" title={project.title || project.key} description={project.description || null} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Workspace" value={project.workspace_id || 'local'} tone="info" />
        <StatTile label="Researches" value={project.research_count ?? researches.length} tone="info" />
        <StatTile label="Runs" value={project.run_count ?? runs.length} tone="positive" />
        <StatTile label="Running" value={running} tone="warning" />
      </div>
      {projectDetailError ? <InlineError message={projectDetailError} /> : null}
      <ProjectEditPanel project={project} onChanged={onChanged} />
      <ProjectResearchHeatPanel researches={researches} branches={branches} runs={runs} selectResearch={selectResearch} selectRun={selectRun} />
      <QuickCompareCard
        title="Compare"
        targets={researches.map((research) => ({ type: 'research', id: research.id }))}
        emptyText="No researches available for compare."
        onSelectRun={selectRun}
      />
      <ResearchTable rows={researches} branches={branches} runs={runs} onSelect={selectResearch} onSelectRun={selectRun} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ProjectSavedItems title="Compare Sets" icon={Layers3} items={compareSets} renderDetail={(item) => `${item.run_ids_json?.length || 0} runs`} actionLabel="Open" onSelect={selectCompareSet} />
        <ProjectSavedItems title="Search Views" icon={Search} items={searchViews} renderDetail={(item) => item.description || formatFilterSummary(item.filters_json)} actionLabel="Run" onSelect={selectSearchView} />
      </div>
      <RunsTable title="Recent Project Runs" runs={sortRunsByRecentActivity(runs).slice(0, 12)} onSelectRun={selectRun} onSelectBranch={selectBranch} />
    </div>
  );
}

function ProjectResearchHeatPanel({ researches, branches, runs, selectResearch, selectRun }) {
  const rows = projectResearchActivityRows(researches, branches, runs);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Research Activity" icon={Activity} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Research")}</th>
              <th className="px-4 py-3 text-right">{t("7D Runs")}</th>
              <th className="px-4 py-3 text-right">{t("Fail Rate")}</th>
              <th className="px-4 py-3 text-right">{t("Branches")}</th>
              <th className="px-4 py-3">{t("Champion")}</th>
              <th className="px-4 py-3 text-right">{t("Sharpe")}</th>
              <th className="px-4 py-3 text-right">{t("Last Run")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="transition hover:bg-white/45" key={row.research.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => selectResearch(row.research.id)} type="button">
                    {row.research.title || row.research.key}
                  </button>
                </td>
                <td className="table-cell text-right font-semibold text-positive">{row.runs7d}</td>
                <td className={`table-cell text-right font-semibold ${row.failureRate > 0.25 ? 'text-negative' : 'text-ink'}`}>{Math.round(row.failureRate * 100)}%</td>
                <td className="table-cell text-right text-info">{row.branchCount}</td>
                <td className="table-cell">
                  {row.champion ? (
                    <button className="font-semibold text-ink hover:text-info break-words [overflow-wrap:anywhere]" onClick={() => selectRun(row.champion.id)} type="button">
                      {row.champion.name}
                    </button>
                  ) : <span className="text-muted">{t("No completed runs.")}</span>}
                </td>
                <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(row.champion, 'strategy.summary', 'sharpe'))}</td>
                <td className="table-cell text-right text-muted">{formatDate(row.lastRunTime || row.research.updated_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="7">{t("No research activity yet.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ProjectEditPanel({ project, onChanged }) {
  const [form, setForm] = useState({ title: project.title || '', description: project.description || '', tags: (project.tags || []).join(','), retention_policy: JSON.stringify(project.retention_policy_json || {}, null, 2) });
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setForm({ title: project.title || '', description: project.description || '', tags: (project.tags || []).join(','), retention_policy: JSON.stringify(project.retention_policy_json || {}, null, 2) });
    setEditing(false);
    setError(null);
  }, [project.id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/projects/${project.id}`, {
        title: form.title,
        description: form.description,
        tags: parseCsv(form.tags),
        retention_policy: compactObject(parseJsonObject(form.retention_policy)),
      });
      await onChanged();
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Project Metadata" icon={Database} action={<EditPanelAction editing={editing} onEdit={() => setEditing(true)} label="Edit project metadata" />} />
      {editing ? (
        <form className="grid gap-4 p-4 lg:grid-cols-2" onSubmit={submit}>
          <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
          <Field label="Tags"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} /></Field>
          <Field label="Description"><TextArea value={form.description} onChange={(event) => update('description', event.target.value)} /></Field>
          <Field label="Retention Policy JSON"><TextArea value={form.retention_policy} onChange={(event) => update('retention_policy', event.target.value)} /></Field>
          <div className="flex items-end gap-2">
            <button className="secondary-button mt-2 w-full" type="button" onClick={() => setEditing(false)}>{t("Cancel")}</button>
            <SubmitButton loading={loading}>Update project</SubmitButton>
          </div>
          <div className="lg:col-span-2"><InlineError message={error} /></div>
        </form>
      ) : (
        <div className="grid gap-4 p-4 lg:grid-cols-2">
          <ReadOnlyField label="Title" value={project.title} />
          <ReadOnlyField label="Tags" value={(project.tags || []).join(', ')} />
          <ReadOnlyField label="Description" value={project.description} multiline />
          <ReadOnlyField label="Retention Policy" value={compactKeyValueSummary(project.retention_policy_json || {})} code />
        </div>
      )}
    </Panel>
  );
}

function ProjectSavedItems({ title, icon: Icon, items, renderDetail, actionLabel, onSelect }) {
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const filteredItems = items.filter((item) => !normalizedQuery || savedItemSearchText(item, renderDetail(item)).includes(normalizedQuery));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title={title} icon={Icon} />
      <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1fr_auto]">
        <Field label={t('Search {{title}}', { title: t(title).toLowerCase() })}><TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('name, filters, metrics, runs')} /></Field>
        <div className="flex items-end text-xs font-semibold text-muted">{t('{{shown}} / {{total}} shown', { shown: filteredItems.length, total: items.length })}</div>
      </div>
      <div className="divide-y divide-line">
        {filteredItems.length ? filteredItems.map((item) => (
          <div className="flex items-center justify-between gap-3 px-5 py-4" key={item.id}>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink">{item.name}</div>
              <div className="mt-1 truncate text-xs text-muted">{renderDetail(item)}</div>
            </div>
            {onSelect ? <button className="secondary-button shrink-0" onClick={() => onSelect(item.id)}>{t(actionLabel || 'Open')}</button> : null}
          </div>
        )) : <div className="p-5 text-sm text-muted">{items.length ? t('No saved items match the current search.') : t('No saved items.')}</div>}
      </div>
    </Panel>
  );
}

function RunsTable({ title, runs, onSelectRun, onSelectBranch }) {
  const orderedRuns = sortRunsByRecentActivity(runs);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title={title} icon={Trophy} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1560px] table-fixed border-collapse">
          <colgroup>
            <col className="w-[300px]" />
            <col className="w-[280px]" />
            <col className="w-[96px]" />
            <col className="w-[96px]" />
            <col className="w-[76px]" />
            <col className="w-[76px]" />
            <col className="w-[76px]" />
            <col className="w-[82px]" />
            <col className="w-[360px]" />
            <col className="w-[100px]" />
            <col className="w-[118px]" />
          </colgroup>
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Run")}</th>
              <th className="px-4 py-3">{t('Research / Branch')}</th>
              <th className="px-4 py-3">{t("Status")}</th>
              <th className="px-4 py-3">{t("Creator")}</th>
              <th className="px-4 py-3 text-right">{t("Sharpe")}</th>
              <th className="px-4 py-3 text-right">{t("Max DD")}</th>
              <th className="px-4 py-3 text-right">{t('IC Mean')}</th>
              <th className="px-4 py-3 text-right">{t("Runtime")}</th>
              <th className="px-4 py-3">{t("Config")}</th>
              <th className="px-4 py-3">{t('Artifacts')}</th>
              <th className="px-4 py-3 text-right">{t("Updated")}</th>
            </tr>
          </thead>
          <tbody>
            {orderedRuns.length ? orderedRuns.map((run) => (
              <tr className="transition hover:bg-white/45" key={run.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:underline break-words [overflow-wrap:anywhere]" onClick={() => onSelectRun(run.id)}>{run.name}</button>
                </td>
                <td className="table-cell text-muted">
                  <div className="break-words [overflow-wrap:anywhere]">{run.research_key || '--'}</div>
                  <button className="mt-1 block font-semibold text-ink hover:underline break-words [overflow-wrap:anywhere]" onClick={() => onSelectBranch(run.branch_id)}>
                    {run.branch_key || run.branch_id}
                  </button>
                </td>
                <td className="table-cell"><StatusBadge status={run.status} /></td>
                <td className="table-cell text-muted">{runCreator(run)}</td>
                <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</td>
                <td className="table-cell text-right text-muted">{formatMetric(metricValue(run, 'strategy.summary', 'max_drawdown'))}</td>
                <td className="table-cell text-right text-muted">{formatMetric(metricValue(run, 'strategy.summary', 'ic_mean'))}</td>
                <td className="table-cell text-right text-muted">{runRuntime(run)}</td>
                <td className="table-cell text-muted"><div className="break-words [overflow-wrap:anywhere]">{configSummary(run.config_json)}</div></td>
                <td className="table-cell"><ArtifactSummary run={run} /></td>
                <td className="table-cell text-right text-muted">{formatDate(run.updated_at)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="11">{t("No runs found.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function RunsBoardPage({ data, selectRun, selectBranch, selectCompareSet, onChanged }) {
  const projects = data?.projects || [];
  const researches = data?.researches || [];
  const branches = data?.branches || [];
  const dashboardRuns = data?.runs || [];
  const [allRuns, setAllRuns] = useState(dashboardRuns);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runsError, setRunsError] = useState(null);
  const [query, setQuery] = useState('');
  const [projectKey, setProjectKey] = useState('');
  const [researchKey, setResearchKey] = useState('');
  const [branchKey, setBranchKey] = useState('');
  const [status, setStatus] = useState('');
  const [creator, setCreator] = useState('');
  const [artifactOnly, setArtifactOnly] = useState('');
  const [sort, setSort] = useState({ key: 'updated', direction: 'desc' });
  const [page, setPage] = useState(1);
  const [selectedRunIds, setSelectedRunIds] = useState([]);
  const [compareCreateLoading, setCompareCreateLoading] = useState(false);
  const [compareCreateError, setCompareCreateError] = useState(null);
  const pageSize = 50;
  const runs = allRuns.length ? allRuns : dashboardRuns;
  const statusOptions = Array.from(new Set(runs.map((run) => run.status).filter(Boolean))).sort();
  const creatorOptions = Array.from(new Set(runs.map((run) => run.created_by_type || 'human').filter(Boolean))).sort();

  useEffect(() => {
    setAllRuns((current) => (current.length ? current : dashboardRuns));
  }, [dashboardRuns]);

  useEffect(() => {
    let cancelled = false;
    setLoadingRuns(true);
    setRunsError(null);
    apiPost('/api/v1/search/runs', { limit: 1000, max_scan: 5000 })
      .then((rows) => {
        if (!cancelled) setAllRuns(rows);
      })
      .catch((err) => {
        if (!cancelled) setRunsError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingRuns(false);
      });
    return () => {
      cancelled = true;
    };
  }, [data?.summary?.runs]);

  const filteredRuns = useMemo(() => {
    const filters = { query, projectKey, researchKey, branchKey, status, creator, artifactOnly };
    return sortRunsForBoard(runs.filter((run) => runMatchesRunBoardFilters(run, filters)), sort);
  }, [runs, query, projectKey, researchKey, branchKey, status, creator, artifactOnly, sort]);
  const pageCount = Math.max(1, Math.ceil(filteredRuns.length / pageSize));
  const pageRuns = filteredRuns.slice((page - 1) * pageSize, page * pageSize);
  const selectedRunSet = useMemo(() => new Set(selectedRunIds), [selectedRunIds]);
  const selectedRuns = useMemo(() => {
    const byId = new Map(runs.map((run) => [run.id, run]));
    return selectedRunIds.map((id) => byId.get(id)).filter(Boolean);
  }, [runs, selectedRunIds]);
  const pageRunIds = pageRuns.map((run) => run.id);
  const allPageRunsSelected = Boolean(pageRunIds.length) && pageRunIds.every((id) => selectedRunSet.has(id));

  useEffect(() => {
    setPage(1);
  }, [query, projectKey, researchKey, branchKey, status, creator, artifactOnly, sort.key, sort.direction]);

  useEffect(() => {
    setPage((current) => Math.min(Math.max(current, 1), pageCount));
  }, [pageCount]);

  useEffect(() => {
    const availableIds = new Set(runs.map((run) => run.id));
    setSelectedRunIds((current) => current.filter((id) => availableIds.has(id)));
  }, [runs]);

  const toggleRunSelection = (runId) => {
    setCompareCreateError(null);
    setSelectedRunIds((current) => (current.includes(runId) ? current.filter((id) => id !== runId) : [...current, runId]));
  };
  const togglePageRunSelection = () => {
    setCompareCreateError(null);
    setSelectedRunIds((current) => {
      const pageIds = new Set(pageRunIds);
      if (pageRunIds.length && pageRunIds.every((id) => current.includes(id))) return current.filter((id) => !pageIds.has(id));
      return Array.from(new Set([...current, ...pageRunIds]));
    });
  };
  const clearRunSelection = () => {
    setSelectedRunIds([]);
    setCompareCreateError(null);
  };
  const createCompareFromSelectedRuns = async () => {
    setCompareCreateLoading(true);
    setCompareCreateError(null);
    try {
      if (selectedRuns.length < 2) throw new Error('至少选择 2 个 run 才能创建对比。');
      const projectId = commonValue(selectedRuns.map((run) => run.project_id).filter(Boolean));
      if (!projectId) throw new Error('请选择同一项目下的 run 创建对比。');
      const researchId = commonValue(selectedRuns.map((run) => run.research_id).filter(Boolean));
      const compareSet = await apiPost('/api/v1/compare-sets', {
        project_id: projectId,
        research_id: researchId || null,
        name: defaultRunsCompareSetName(selectedRuns),
        run_ids: selectedRunIds,
        layout: {
          stage: 'Runs selection',
          metrics: ['strategy.summary.annual_return', 'strategy.summary.annual_volatility', 'strategy.summary.max_drawdown', 'strategy.summary.sharpe', 'strategy.summary.sortino', 'strategy.summary.calmar', 'strategy.summary.turnover'],
          series: [],
        },
      });
      await onChanged?.();
      setSelectedRunIds([]);
      selectCompareSet(compareSet.id);
    } catch (err) {
      setCompareCreateError(err.message);
    } finally {
      setCompareCreateLoading(false);
    }
  };

  const toggleSort = (key) => setSort((current) => (
    current.key === key
      ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: defaultRunBoardSortDirection(key) }
  ));
  const clearFilters = () => {
    setQuery('');
    setProjectKey('');
    setResearchKey('');
    setBranchKey('');
    setStatus('');
    setCreator('');
    setArtifactOnly('');
  };

  return (
    <div className="space-y-5">
      <Hero eyebrow="Runs" title="Run Explorer" />
      <RunsBoardSummary runs={runs} filteredRuns={filteredRuns} />
      <Panel className="overflow-hidden">
        <PanelHeader
          title="All Runs"
          action={<div className="text-xs font-semibold text-muted">{loadingRuns ? 'Loading runs...' : `${filteredRuns.length} / ${runs.length} shown`}</div>}
        />
        <InlineError message={runsError} />
        <RunCompareSelectionBar
          selectedRuns={selectedRuns}
          loading={compareCreateLoading}
          error={compareCreateError}
          onCreate={createCompareFromSelectedRuns}
          onClear={clearRunSelection}
        />
        <div className="grid gap-3 border-b border-line p-4 lg:grid-cols-[minmax(220px,1.6fr)_repeat(5,minmax(140px,1fr))_auto]">
          <Field label="Search runs">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="run, project, branch, config, tag" />
          </Field>
          <Field label="Project">
            <SelectInput value={projectKey} onChange={(event) => setProjectKey(event.target.value)}>
              <option value="">{t("Any project")}</option>
              {projects.map((project) => <option key={project.id} value={project.key}>{project.key}</option>)}
            </SelectInput>
          </Field>
          <Field label="Research">
            <SelectInput value={researchKey} onChange={(event) => setResearchKey(event.target.value)}>
              <option value="">{t("Any research")}</option>
              {researches.map((research) => <option key={research.id} value={research.key}>{research.key}</option>)}
            </SelectInput>
          </Field>
          <Field label="Branch">
            <SelectInput value={branchKey} onChange={(event) => setBranchKey(event.target.value)}>
              <option value="">{t("Any branch")}</option>
              {branches.map((branch) => <option key={branch.id} value={branch.key}>{branch.key}</option>)}
            </SelectInput>
          </Field>
          <Field label="Status">
            <SelectInput value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">{t("Any status")}</option>
              {statusOptions.map((item) => <option key={item} value={item}>{tStatus(item)}</option>)}
            </SelectInput>
          </Field>
          <Field label="Creator">
            <SelectInput value={creator} onChange={(event) => setCreator(event.target.value)}>
              <option value="">{t("Any creator")}</option>
              {creatorOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <div className="flex items-end gap-2">
            <Field label="Artifacts">
              <SelectInput value={artifactOnly} onChange={(event) => setArtifactOnly(event.target.value)}>
                <option value="">{t("Any")}</option>
                <option value="yes">{t("Has artifacts")}</option>
                <option value="report">{t("Has report")}</option>
                <option value="none">{t("No artifacts")}</option>
              </SelectInput>
            </Field>
            <button className="secondary-button mb-0.5 shrink-0" type="button" onClick={clearFilters}>{t("Clear")}</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1532px] table-fixed border-collapse">
            <colgroup>
              <col className="w-[52px]" />
              <col className="w-[280px]" />
              <col className="w-[180px]" />
              <col className="w-[220px]" />
              <col className="w-[96px]" />
              <col className="w-[130px]" />
              <col className="w-[84px]" />
              <col className="w-[92px]" />
              <col className="w-[88px]" />
              <col className="w-[100px]" />
              <col className="w-[260px]" />
              <col className="w-[110px]" />
              <col className="w-[118px]" />
            </colgroup>
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">
                  <input
                    aria-label="选择当前页 runs"
                    checked={allPageRunsSelected}
                    className="h-4 w-4 rounded border-line text-info"
                    disabled={!pageRunIds.length}
                    onChange={togglePageRunSelection}
                    type="checkbox"
                  />
                </th>
                <th className="px-4 py-3"><SortableHeader label="Run" sortKey="name" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3"><SortableHeader label="Project" sortKey="project" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3"><SortableHeader label="Research / Branch" sortKey="branch" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3"><SortableHeader label="Status" sortKey="status" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3"><SortableHeader label="Creator" sortKey="creator" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3 text-right"><SortableHeader label="Sharpe" sortKey="sharpe" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3 text-right"><SortableHeader label="Max DD" sortKey="max_drawdown" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3 text-right"><SortableHeader label="Runtime" sortKey="runtime" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3"><SortableHeader label="Artifacts" sortKey="artifacts" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3">{t("Config")}</th>
                <th className="px-4 py-3 text-right"><SortableHeader label="Created" sortKey="created" sort={sort} onSort={toggleSort} /></th>
                <th className="px-4 py-3 text-right"><SortableHeader label="Updated" sortKey="updated" sort={sort} onSort={toggleSort} /></th>
              </tr>
            </thead>
            <tbody>
              {pageRuns.length ? pageRuns.map((run) => (
                <tr className={`transition hover:bg-white/45 ${selectedRunSet.has(run.id) ? 'bg-infoSoft/35' : ''}`} key={run.id}>
                  <td className="table-cell">
                    <input
                      aria-label={`选择 run ${run.name}`}
                      checked={selectedRunSet.has(run.id)}
                      className="h-4 w-4 rounded border-line text-info"
                      onChange={() => toggleRunSelection(run.id)}
                      type="checkbox"
                    />
                  </td>
                  <td className="table-cell">
                    <button className="font-semibold text-ink hover:text-info break-words [overflow-wrap:anywhere]" onClick={() => selectRun(run.id)} type="button">{run.name}</button>
                    <div className="mt-1 text-xs text-muted break-words [overflow-wrap:anywhere]">{run.id}</div>
                  </td>
                  <td className="table-cell text-muted">{run.project_key || '--'}</td>
                  <td className="table-cell text-muted">
                    <div className="break-words [overflow-wrap:anywhere]">{run.research_key || '--'}</div>
                    <button className="mt-1 block font-semibold text-ink hover:text-info break-words [overflow-wrap:anywhere]" onClick={() => selectBranch(run.branch_id)} type="button">
                      {run.branch_key || run.branch_id || '--'}
                    </button>
                  </td>
                  <td className="table-cell"><StatusBadge status={run.status} /></td>
                  <td className="table-cell text-muted">{runCreator(run)}</td>
                  <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</td>
                  <td className="table-cell text-right text-muted">{formatMetric(metricValue(run, 'strategy.summary', 'max_drawdown'))}</td>
                  <td className="table-cell text-right text-muted">{runRuntime(run)}</td>
                  <td className="table-cell"><ArtifactSummary run={run} /></td>
                  <td className="table-cell text-muted"><div className="break-words [overflow-wrap:anywhere]">{configSummary(run.config_json)}</div></td>
                  <td className="table-cell text-right text-muted">{formatDate(run.created_at || run.started_at)}</td>
                  <td className="table-cell text-right text-muted">{formatDate(run.updated_at || run.ended_at || run.started_at || run.created_at)}</td>
                </tr>
              )) : (
                <tr><td className="table-cell text-muted" colSpan="13">{t("No runs match the current filters.")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
          <div className="text-xs font-semibold text-muted">
            Page {page} / {pageCount} · {pageRuns.length} rows on this page
          </div>
          <div className="flex items-center gap-2">
            <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>{t("Previous")}</button>
            <button className="secondary-button" type="button" disabled={page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>{t("Next")}</button>
          </div>
        </div>
      </Panel>
    </div>
  );
}


function RunCompareSelectionBar({ selectedRuns, loading, error, onCreate, onClear }) {
  const projectKeys = Array.from(new Set((selectedRuns || []).map((run) => run.project_key).filter(Boolean))).sort();
  const researchKeys = Array.from(new Set((selectedRuns || []).map((run) => run.research_key).filter(Boolean))).sort();
  const canCreate = selectedRuns.length >= 2 && projectKeys.length <= 1;
  if (!selectedRuns.length && !error) return null;
  return (
    <div className="border-b border-line bg-infoSoft/35 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink">已选择 {selectedRuns.length} 个 Run</div>
          <div className="mt-1 truncate text-xs text-muted">
            {projectKeys.length ? `Project: ${projectKeys.join(', ')}` : 'Project: --'} · {researchKeys.length === 1 ? `Research: ${researchKeys[0]}` : researchKeys.length > 1 ? `${researchKeys.length} 条研究线` : 'Project-level'}
          </div>
          <div className="mt-1 truncate text-xs text-muted">{selectedRuns.slice(0, 5).map((run) => run.name).join(', ')}{selectedRuns.length > 5 ? ` +${selectedRuns.length - 5}` : ''}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="primary-button" disabled={!canCreate || loading} onClick={onCreate} type="button">
            <Layers3 className="h-4 w-4" />
            {loading ? '创建中' : '创建对比'}
          </button>
          <button className="secondary-button" disabled={loading} onClick={onClear} type="button">清空选择</button>
        </div>
      </div>
      <InlineError message={error || (selectedRuns.length >= 2 && projectKeys.length > 1 ? '请选择同一项目下的 run 创建对比。' : null)} />
    </div>
  );
}

function RunsBoardSummary({ runs, filteredRuns }) {
  const completed = runs.filter((run) => run.status === 'completed').length;
  const running = runs.filter((run) => run.status === 'running').length;
  const failed = runs.filter((run) => run.status === 'failed').length;
  const withArtifacts = runs.filter((run) => Number(run.artifact_count || 0) > 0).length;
  const latest = [...runs].sort((a, b) => dateMillis(b.updated_at || b.ended_at || b.started_at || b.created_at) - dateMillis(a.updated_at || a.ended_at || a.started_at || a.created_at))[0];
  return (
    <Panel className="p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <ReadOnlyField label="Filtered" value={`${filteredRuns.length} / ${runs.length}`} />
        <ReadOnlyField label="Completed" value={completed} />
        <ReadOnlyField label="Running" value={running} />
        <ReadOnlyField label="Failed" value={failed} />
        <ReadOnlyField label="With Artifacts" value={withArtifacts} />
        <ReadOnlyField label="Latest" value={formatDate(latest?.updated_at || latest?.ended_at || latest?.started_at || latest?.created_at)} />
      </div>
    </Panel>
  );
}

function ResearchRecentRunsPanel({ runs, scopeKey, onSelectRun, onSelectBranch }) {
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const sortedRuns = useMemo(() => [...(runs || [])].sort((a, b) => (
    dateMillis(b.updated_at || b.ended_at || b.started_at || b.created_at)
    - dateMillis(a.updated_at || a.ended_at || a.started_at || a.created_at)
  )), [runs]);
  const pageCount = Math.max(1, Math.ceil(sortedRuns.length / pageSize));

  useEffect(() => {
    setPage(1);
  }, [scopeKey]);

  useEffect(() => {
    setPage((current) => Math.min(Math.max(current, 1), pageCount));
  }, [pageCount]);

  const pageRuns = sortedRuns.slice((page - 1) * pageSize, page * pageSize);

  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Recent Runs"
        action={(
          <div className="flex items-center gap-2 text-xs font-semibold text-muted">
            <span>{sortedRuns.length} runs</span>
            {pageCount > 1 ? <span>Page {page} / {pageCount}</span> : null}
          </div>
        )}
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("BRANCH")}</th>
              <th className="px-4 py-3">{t("RUN")}</th>
              <th className="px-4 py-3">{t("STATUS")}</th>
              <th className="px-4 py-3">{t("CREATOR")}</th>
              <th className="px-4 py-3 text-right">{t("SHARPE")}</th>
              <th className="px-4 py-3 text-right">{t("RUNTIME")}</th>
              <th className="px-4 py-3 text-right">{t("UPDATED")}</th>
            </tr>
          </thead>
          <tbody>
            {pageRuns.length ? pageRuns.map((run) => (
              <tr className="transition hover:bg-white/45" key={run.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:underline" onClick={() => onSelectBranch(run.branch_id)}>{run.branch_key || run.branch_id || '--'}</button>
                </td>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:underline" onClick={() => onSelectRun(run.id)}>{run.name}</button>
                </td>
                <td className="table-cell"><StatusBadge status={run.status} /></td>
                <td className="table-cell text-muted">{runCreator(run)}</td>
                <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</td>
                <td className="table-cell text-right text-muted">{runRuntime(run)}</td>
                <td className="table-cell text-right text-muted">{formatDate(run.updated_at || run.ended_at || run.started_at || run.created_at)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="7">{t("No runs found.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {pageCount > 1 ? (
        <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">
          <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>{t("Previous")}</button>
          <button className="secondary-button" type="button" disabled={page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>{t("Next")}</button>
        </div>
      ) : null}
    </Panel>
  );
}

function ResearchCompareSetsPanel({ compareSets, error, onSelectCompareSet }) {
  const rows = [...(compareSets || [])].sort((a, b) => dateMillis(b.created_at) - dateMillis(a.created_at));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Compare Sets"
        action={<div className="text-xs font-semibold text-muted">{rows.length} sets</div>}
      />
      {error ? <div className="px-5 pt-4"><InlineError message={error} /></div> : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Name")}</th>
              <th className="px-4 py-3 text-right">{t("Runs")}</th>
              <th className="px-4 py-3">{t("Layout")}</th>
              <th className="px-4 py-3 text-right">{t("Created")}</th>
              <th className="px-4 py-3 text-right">{t("Action")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((compareSet) => (
              <tr className="transition hover:bg-white/45" key={compareSet.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info break-words [overflow-wrap:anywhere]" onClick={() => onSelectCompareSet(compareSet.id)} type="button">
                    {compareSet.name}
                  </button>
                  <div className="mt-1 text-xs text-muted break-words [overflow-wrap:anywhere]">{compareSet.id}</div>
                </td>
                <td className="table-cell text-right font-semibold text-info">{compareSet.run_ids_json?.length || 0}</td>
                <td className="table-cell text-muted">{compareSetLayoutSummary(compareSet)}</td>
                <td className="table-cell text-right text-muted">{formatDate(compareSet.created_at)}</td>
                <td className="table-cell text-right">
                  <button className="secondary-button" type="button" onClick={() => onSelectCompareSet(compareSet.id)}>{t("Open")}</button>
                </td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="5">{t("No compare sets yet.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ArtifactSummary({ run }) {
  const count = Number(run.artifact_count || 0);
  const kinds = (run.artifact_kinds || []).slice(0, 2);
  if (!count) return <span className="text-muted">--</span>;
  const labels = [...(run.has_report_artifact ? ['report'] : []), ...kinds];
  return (
    <span className="text-xs text-muted">
      {labels.join(', ')}
      {run.artifact_kinds?.length > kinds.length ? ` +${run.artifact_kinds.length - kinds.length}` : ''}
      {labels.length ? ' · ' : ''}
      {count}
    </span>
  );
}

function StatusBadge({ status }) {
  if (status === 'completed') return <Badge tone="positive">{tStatus(status)}</Badge>;
  if (status === 'failed') return <Badge tone="negative">{tStatus(status)}</Badge>;
  if (status === 'running') return <Badge tone="warning">{tStatus(status)}</Badge>;
  return <Badge>{tStatus(status)}</Badge>;
}

function runCreator(run) {
  const type = run.created_by_type || 'human';
  return run.created_by_id ? `${type} / ${run.created_by_id}` : type;
}

function ResearchPage({ data, selectedResearchId, selectBranch, selectRun, selectCompareSet, onChanged }) {
  const research = (data?.researches || []).find((item) => item.id === selectedResearchId) || data?.researches?.[0];
  const branches = (data?.branches || []).filter((branch) => branch.research_id === research?.id);
  const runs = (data?.runs || []).filter((run) => branches.some((branch) => branch.id === run.branch_id));
  const [lineage, setLineage] = useState(null);
  const [lineageError, setLineageError] = useState(null);
  const [lineageExpanded, setLineageExpanded] = useState(false);
  const [researchCompareSets, setResearchCompareSets] = useState(null);
  const [compareSetError, setCompareSetError] = useState(null);
  useEffect(() => {
    if (!research?.id) {
      setLineage(null);
      setLineageError(null);
      return;
    }
    let cancelled = false;
    apiGet(`/api/v1/lineage/researches/${research.id}`)
      .then((payload) => {
        if (!cancelled) {
          setLineage(payload);
          setLineageError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setLineage(null);
          setLineageError(err.message);
        }
      });
    return () => { cancelled = true; };
  }, [research?.id, branches.length, runs.length]);
  useEffect(() => {
    if (!research?.id) {
      setResearchCompareSets(null);
      setCompareSetError(null);
      return;
    }
    let cancelled = false;
    apiGet(`/api/v1/researches/${research.id}/compare-sets`)
      .then((payload) => {
        if (!cancelled) {
          setResearchCompareSets(payload);
          setCompareSetError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setResearchCompareSets(null);
          setCompareSetError(null);
        }
      });
    return () => { cancelled = true; };
  }, [research?.id, data?.summary?.compare_sets]);
  if (!research) return <EmptyState title="No research yet" detail="Create a run through the SDK or bbox CLI, then refresh this page." />;
  const lineageBranches = lineage?.branches || branches;
  const lineageRuns = lineage?.runs || runs;
  const lineageChartOption = lineageOption(lineageBranches, lineageRuns);
  const recentRuns = [...lineageRuns].sort((a, b) => dateMillis(b.updated_at || b.ended_at || b.started_at || b.created_at) - dateMillis(a.updated_at || a.ended_at || a.started_at || a.created_at));
  const compareSets = researchCompareSets || (data?.compare_sets || []).filter((item) => item.research_id === research.id);
  return (
    <div className="space-y-5">
      <Hero eyebrow={`Project / ${research.project_key || '--'}`} title={research.title || research.key} description={research.goal || research.hypothesis || null} />
      <ResearchWorkspaceSummary research={research} branches={lineageBranches} runs={lineageRuns} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-8">
          <ResearchRecentRunsPanel runs={recentRuns} scopeKey={research.id} onSelectBranch={selectBranch} onSelectRun={selectRun} />
          <ResearchCompareSetsPanel compareSets={compareSets} error={compareSetError} onSelectCompareSet={selectCompareSet} />
          <BranchesTable branches={lineageBranches} runs={lineageRuns} onSelect={selectBranch} onChanged={onChanged} />
        </div>
        <ResearchChampionPanel research={research} branches={lineageBranches} runs={lineageRuns} onSelectRun={selectRun} />
      </div>
      {lineageExpanded ? <LineageChartModal option={lineageChartOption} onClose={() => setLineageExpanded(false)} /> : null}
      <QuickCompareCard
        title="Compare"
        targets={lineageBranches.map((branch) => ({ type: 'branch', id: branch.id }))}
        emptyText="No branches available for compare."
        onSelectRun={selectRun}
      />
      <DashboardCollapsedSection title="Lineage and Activity">
        <div className="space-y-5 p-4">
          <ResearchEditPanel research={research} onChanged={onChanged} />
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Branch Lineage"
              icon={GitBranch}
              action={(
                <button className="icon-button" type="button" onClick={() => setLineageExpanded(true)} aria-label="Expand branch lineage">
                  <Maximize2 className="h-4 w-4" />
                </button>
              )}
            />
            {lineageError ? <div className="px-5 pt-4"><InlineError message={lineageError} /></div> : null}
            <div className="h-[360px] cursor-grab p-3 active:cursor-grabbing"><ReactECharts option={lineageChartOption} style={{ height: '100%', width: '100%' }} /></div>
          </Panel>
          <ResearchTimelinePanel research={research} branches={lineageBranches} runs={lineageRuns} notes={data?.notes || []} onSelectBranch={selectBranch} onSelectRun={selectRun} />
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function ResearchWorkspaceSummary({ research, branches, runs }) {
  const completedRuns = runs.filter((run) => run.status === 'completed').length;
  const runningRuns = runs.filter((run) => run.status === 'running').length;
  const failedRuns = runs.filter((run) => run.status === 'failed').length;
  const latestRun = [...runs].sort((a, b) => dateMillis(b.updated_at || b.created_at) - dateMillis(a.updated_at || a.created_at))[0];
  return (
    <Panel className="p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <ReadOnlyField label="Status" value={research.status || 'active'} />
        <ReadOnlyField label="Branches" value={branches.length} />
        <ReadOnlyField label="Completed Runs" value={completedRuns} />
        <ReadOnlyField label="Running" value={runningRuns} />
        <ReadOnlyField label="Failed" value={failedRuns} />
        <ReadOnlyField label="Latest Run" value={latestRun?.name || '--'} />
      </div>
    </Panel>
  );
}

function ResearchLineageEdgesPanel({ edges, branches, runs, onSelectBranch, onSelectRun }) {
  const branchById = Object.fromEntries((branches || []).map((branch) => [branch.id, branch]));
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  const rows = (edges?.length ? edges : (branches || [])
    .filter((branch) => branch.parent_branch_id || branch.source_run_id)
    .map((branch) => ({
      from_branch_id: branch.parent_branch_id,
      to_branch_id: branch.id,
      source_run_id: branch.source_run_id,
    })))
    .map((edge) => ({
      edge,
      fromBranch: branchById[edge.from_branch_id],
      toBranch: branchById[edge.to_branch_id],
      sourceRun: runById[edge.source_run_id],
    }));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Lineage Edges" icon={GitBranch} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse">
          <thead className="table-head">
            <tr><th className="px-4 py-3">{t("From")}</th><th className="px-4 py-3">{t("To")}</th><th className="px-4 py-3">{t("Source Run")}</th><th className="px-4 py-3">{t("Reason")}</th><th className="px-4 py-3 text-right">{t("Created")}</th></tr>
          </thead>
          <tbody>
            {rows.length ? rows.map(({ edge, fromBranch, toBranch, sourceRun }) => (
              <tr className="hover:bg-white/45" key={`${edge.from_branch_id || 'root'}-${edge.to_branch_id}-${edge.source_run_id || 'none'}`}>
                <td className="table-cell">
                  {fromBranch ? <button className="font-semibold text-ink hover:text-info" onClick={() => onSelectBranch(fromBranch.id)}>{fromBranch.title || fromBranch.key}</button> : <span className="text-muted">{t("root")}</span>}
                </td>
                <td className="table-cell">
                  {toBranch ? <button className="font-semibold text-ink hover:text-info" onClick={() => onSelectBranch(toBranch.id)}>{toBranch.title || toBranch.key}</button> : <span className="text-muted">{edge.to_branch_id || '--'}</span>}
                </td>
                <td className="table-cell">
                  {sourceRun ? <button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(sourceRun.id)}>{sourceRun.name}</button> : <span className="text-muted">{edge.source_run_id || '--'}</span>}
                </td>
                <td className="table-cell text-muted">{toBranch?.reason_summary || toBranch?.reason_code || '--'}</td>
                <td className="table-cell text-right text-muted">{formatDate(toBranch?.created_at)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="5">{t("No lineage edges yet.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ResearchChampionPanel({ research, branches, runs, onSelectRun }) {
  const champion = researchChampionRun(research, branches, runs);
  const branch = champion ? (branches || []).find((item) => item.id === champion.branch_id) : null;
  return (
    <Panel className="overflow-hidden xl:col-span-4">
      <PanelHeader title="Champion" />
      {champion ? (
        <div className="space-y-4 p-4">
          <button className="text-left text-xl font-semibold text-ink hover:underline" onClick={() => onSelectRun(champion.id)} type="button">
            {champion.name}
          </button>
          <div className="grid grid-cols-2 gap-3">
            <ReadOnlyField label="Branch" value={branch?.key || champion.branch_key || champion.branch_id} />
            <ReadOnlyField label="Status" value={tStatus(champion.status)} />
            <ReadOnlyField label="Sharpe" value={formatMetric(metricValue(champion, 'strategy.summary', 'sharpe'))} />
            <ReadOnlyField label="Max DD" value={formatMetric(metricValue(champion, 'strategy.summary', 'max_drawdown'))} />
            <ReadOnlyField label="IC Mean" value={formatMetric(metricValue(champion, 'strategy.summary', 'ic_mean'))} />
            <ReadOnlyField label="Turnover" value={formatMetric(metricValue(champion, 'strategy.summary', 'turnover'))} />
          </div>
          <div>
            <div className="mb-1 text-xs font-semibold text-muted">{t("Config")}</div>
            <div className="truncate text-sm text-muted" title={configSummary(champion.config_json)}>{configSummary(champion.config_json)}</div>
          </div>
        </div>
      ) : (
        <div className="p-5 text-sm text-muted">{t("No completed run with comparable metrics yet.")}</div>
      )}
    </Panel>
  );
}

function ResearchTimelinePanel({ research, branches, runs, notes, onSelectBranch, onSelectRun }) {
  const items = researchTimelineItems(research, branches, runs, notes).slice(0, 24);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Research Timeline" icon={Activity} />
      <div className="divide-y divide-line">
        {items.length ? items.map((item) => (
          <button
            className="block w-full px-5 py-4 text-left transition hover:bg-white/45"
            key={item.id}
            onClick={() => {
              if (item.run_id) onSelectRun(item.run_id);
              if (!item.run_id && item.branch_id) onSelectBranch(item.branch_id);
            }}
            type="button"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase text-muted">{item.type}</div>
                <div className="mt-1 truncate text-sm font-semibold text-ink">{item.title}</div>
                <div className="mt-1 truncate text-xs text-muted">{item.detail}</div>
              </div>
              <div className="shrink-0 text-xs text-muted">{formatDate(item.at)}</div>
            </div>
          </button>
        )) : <div className="p-5 text-sm text-muted">{t("No research timeline events yet.")}</div>}
      </div>
    </Panel>
  );
}

function ResearchEditPanel({ research, onChanged }) {
  const [form, setForm] = useState({ title: research.title || '', status: research.status || 'active', goal: research.goal || '', hypothesis: research.hypothesis || '', tags: (research.tags || []).join(',') });
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setForm({ title: research.title || '', status: research.status || 'active', goal: research.goal || '', hypothesis: research.hypothesis || '', tags: (research.tags || []).join(',') });
    setEditing(false);
    setError(null);
  }, [research.id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/researches/${research.id}`, { ...form, tags: parseCsv(form.tags) });
      await onChanged();
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Research Metadata" icon={FileText} action={<EditPanelAction editing={editing} onEdit={() => setEditing(true)} label="Edit research metadata" />} />
      {editing ? (
        <form className="grid gap-4 p-4 lg:grid-cols-2" onSubmit={submit}>
          <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
          <Field label="Status"><TextInput required value={form.status} onChange={(event) => update('status', event.target.value)} /></Field>
          <Field label="Goal"><TextArea value={form.goal} onChange={(event) => update('goal', event.target.value)} /></Field>
          <Field label="Hypothesis"><TextArea value={form.hypothesis} onChange={(event) => update('hypothesis', event.target.value)} /></Field>
          <Field label="Tags"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} /></Field>
          <div className="flex items-end gap-2">
            <button className="secondary-button mt-2 w-full" type="button" onClick={() => setEditing(false)}>{t("Cancel")}</button>
            <SubmitButton loading={loading}>Update research</SubmitButton>
          </div>
          <div className="lg:col-span-2"><InlineError message={error} /></div>
        </form>
      ) : (
        <div className="grid gap-4 p-4 lg:grid-cols-2">
          <ReadOnlyField label="Title" value={research.title} />
          <ReadOnlyField label="Status" value={tStatus(research.status)} />
          <ReadOnlyField label="Goal" value={research.goal} multiline />
          <ReadOnlyField label="Hypothesis" value={research.hypothesis} multiline />
          <ReadOnlyField label="Tags" value={(research.tags || []).join(', ')} />
        </div>
      )}
    </Panel>
  );
}

function BranchesTable({ branches, runs, onSelect, onChanged }) {
  const sortedBranches = [...(branches || [])].sort((a, b) => (
    latestRunMillisForBranch(b, runs) - latestRunMillisForBranch(a, runs)
    || entityUpdatedMillis(b) - entityUpdatedMillis(a)
  ));
  const [selectedIds, setSelectedIds] = useState([]);
  const [status, setStatus] = useState('archived');
  const [editingBatch, setEditingBatch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState('');
  useEffect(() => {
    setSelectedIds((current) => current.filter((id) => branches.some((branch) => branch.id === id)));
  }, [branches]);
  const toggleBranch = (branchId) => {
    setSelectedIds((current) => (current.includes(branchId) ? current.filter((id) => id !== branchId) : [...current, branchId]));
  };
  const submitBatchStatus = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setMessage('');
    try {
      if (!selectedIds.length) {
        setError('Select at least one branch.');
        return;
      }
      await Promise.all(selectedIds.map((branchId) => apiPatch(`/api/v1/branches/${branchId}`, { status })));
      setMessage(`Updated ${selectedIds.length} branch${selectedIds.length === 1 ? '' : 'es'} to ${status}.`);
      setSelectedIds([]);
      await onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Branches"
        icon={ListTree}
        action={editingBatch ? <button className="secondary-button" type="button" onClick={() => setEditingBatch(false)}>{t("Close")}</button> : null}
      />
      <div className="border-b border-line p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button className={`secondary-button ${editingBatch ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setEditingBatch((current) => !current)}>
            <CheckCircle2 className="h-4 w-4" />
            Batch Status
          </button>
          <div className="text-xs font-semibold text-muted">{selectedIds.length} selected · target {status}</div>
        </div>
        {editingBatch ? (
          <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={submitBatchStatus}>
            <Field label="Batch status">
              <SelectInput value={status} onChange={(event) => setStatus(event.target.value)}>
                {branchStatuses.map((item) => <option key={item} value={item}>{tStatus(item)}</option>)}
              </SelectInput>
            </Field>
            <button className="secondary-button" disabled={loading || !selectedIds.length} type="submit">
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              Update selected
            </button>
            <InlineError message={error || (selectedIds.length ? null : 'Select at least one branch.')} />
          </form>
        ) : (
          <div className="mt-3 max-w-xl">
            <ReadOnlyField label="Batch Status" value={`${selectedIds.length} selected · target ${status}`} />
          </div>
        )}
        {message ? <div className="mt-3 rounded-md bg-positiveSoft px-3 py-2 text-xs font-semibold text-positive">{message}</div> : null}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Use")}</th><th className="px-4 py-3">{t("Branch")}</th><th className="px-4 py-3">{t("Status")}</th><th className="px-4 py-3">{t("Reason")}</th><th className="px-4 py-3 text-right">{t("Runs")}</th><th className="px-4 py-3 text-right">{t("Updated")}</th></tr></thead>
          <tbody>
            {sortedBranches.map((branch) => (
              <tr className="cursor-pointer transition hover:bg-white/45" key={branch.id} onClick={() => onSelect(branch.id)}>
                <td className="table-cell" onClick={(event) => event.stopPropagation()}>
                  <input checked={selectedIds.includes(branch.id)} className="h-4 w-4 accent-charcoal" onChange={() => toggleBranch(branch.id)} type="checkbox" />
                </td>
                <td className="table-cell font-semibold text-ink">{branch.title || branch.key}</td>
                <td className="table-cell"><Badge tone={branch.status === 'active' ? 'positive' : 'neutral'}>{tStatus(branch.status)}</Badge></td>
                <td className="table-cell text-muted">{branch.reason_summary || '--'}</td>
                <td className="table-cell text-right">{runs.filter((run) => run.branch_id === branch.id).length}</td>
                <td className="table-cell text-right text-muted">{formatDate(branch.updated_at)}</td>
              </tr>
            ))}
            {!branches.length ? <tr><td className="table-cell text-muted" colSpan="6">{t("No branches yet.")}</td></tr> : null}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function BranchPage({ data, selectedBranchId, selectBranch, selectRun, onChanged }) {
  const branch = (data?.branches || []).find((item) => item.id === selectedBranchId) || data?.branches?.[0];
  const dashboardRuns = (data?.runs || []).filter((run) => run.branch_id === branch?.id);
  const dashboardSweeps = (data?.sweeps || []).filter((sweep) => sweep.branch_id === branch?.id);
  const [lineage, setLineage] = useState(null);
  const [lineageError, setLineageError] = useState(null);
  const [branchSweeps, setBranchSweeps] = useState(null);
  const [branchSweepsError, setBranchSweepsError] = useState(null);
  useEffect(() => {
    if (!branch?.id) {
      setLineage(null);
      setLineageError(null);
      return;
    }
    let cancelled = false;
    apiGet(`/api/v1/lineage/branches/${branch.id}`)
      .then((payload) => {
        if (!cancelled) {
          setLineage(payload);
          setLineageError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setLineage(null);
          setLineageError(err.message);
        }
      });
    return () => { cancelled = true; };
  }, [branch?.id, data?.branches?.length, data?.runs?.length]);
  useEffect(() => {
    if (!SHOW_SWEEPS) {
      setBranchSweeps(null);
      setBranchSweepsError(null);
      return undefined;
    }
    if (!branch?.id) {
      setBranchSweeps(null);
      setBranchSweepsError(null);
      return;
    }
    let cancelled = false;
    setBranchSweeps(null);
    apiGet(`/api/v1/branches/${branch.id}/sweeps`)
      .then((payload) => {
        if (!cancelled) {
          setBranchSweeps(payload);
          setBranchSweepsError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setBranchSweeps(dashboardSweeps);
          setBranchSweepsError(err.message);
        }
      });
    return () => { cancelled = true; };
  }, [branch?.id, data?.sweeps?.length]);
  if (!branch) return <EmptyState title="No branches yet" detail="Branches appear after the first run is recorded." />;
  const sweeps = SHOW_SWEEPS ? (branchSweeps || dashboardSweeps) : [];
  const branchRuns = (lineage?.runs || dashboardRuns).filter((run) => run.branch_id === branch.id);
  const orderedRuns = [...branchRuns].sort((a, b) => new Date(a.created_at || a.updated_at) - new Date(b.created_at || b.updated_at));
  const handleBranchChanged = async () => {
    await onChanged();
    try {
          const payload = await apiGet(`/api/v1/branches/${branch.id}/sweeps`);
      setBranchSweeps(payload);
      setBranchSweepsError(null);
    } catch (err) {
      setBranchSweeps(dashboardSweeps);
      setBranchSweepsError(err.message);
    }
  };
  return (
    <div className="space-y-5">
      <Hero eyebrow={`Research / ${branch.research_key || '--'}`} title={branch.title || branch.key} description={branch.hypothesis || branch.reason_summary || null} />
      <BranchWorkspaceSummary branch={branch} runs={branchRuns} sweeps={sweeps} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-8">
          <DecisionRunsPanel title="Branch Runs" runs={branchRuns} onSelectRun={selectRun} onSelectBranch={() => {}} />
          {SHOW_SWEEPS ? <BranchSweepPanel branch={branch} runs={branchRuns} sweeps={sweeps} error={branchSweepsError} onChanged={handleBranchChanged} onSelectRun={selectRun} /> : null}
        </div>
        <BranchChampionPanel runs={branchRuns} onSelectRun={selectRun} />
      </div>
      <QuickCompareCard
        title="Compare"
        targets={orderedRuns.map((run) => ({ type: 'run', id: run.id }))}
        emptyText="No runs on this branch."
        onSelectRun={selectRun}
      />
      <DashboardCollapsedSection title="Branch Context">
        <div className="space-y-5 p-4">
          <BranchEditPanel branch={branch} onChanged={onChanged} />
          <BranchLineagePanel lineage={lineage} error={lineageError} fallbackBranch={branch} fallbackBranches={data?.branches || []} fallbackRuns={data?.runs || []} onSelectBranch={selectBranch} onSelectRun={selectRun} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <BranchMetricEvolution runs={orderedRuns} onSelectRun={selectRun} />
            <BranchConfigEvolution runs={orderedRuns} onSelectRun={selectRun} />
          </div>
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function BranchWorkspaceSummary({ branch, runs, sweeps }) {
  const completedRuns = runs.filter((run) => run.status === 'completed').length;
  const runningRuns = runs.filter((run) => run.status === 'running').length;
  const latestRun = [...runs].sort((a, b) => dateMillis(b.updated_at || b.created_at) - dateMillis(a.updated_at || a.created_at))[0];
  return (
    <Panel className="p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <ReadOnlyField label="Status" value={tStatus(branch.status)} />
        <ReadOnlyField label="Runs" value={runs.length} />
        <ReadOnlyField label="Completed" value={completedRuns} />
        <ReadOnlyField label="Running" value={runningRuns} />
        {SHOW_SWEEPS ? <ReadOnlyField label="Sweeps" value={sweeps.length} /> : null}
        <ReadOnlyField label="Latest Run" value={latestRun?.name || '--'} />
      </div>
    </Panel>
  );
}

function BranchChampionPanel({ runs, onSelectRun }) {
  const champion = [...runs]
    .filter((run) => run.status === 'completed')
    .sort((a, b) => Number(metricValue(b, 'strategy.summary', 'sharpe') || -Infinity) - Number(metricValue(a, 'strategy.summary', 'sharpe') || -Infinity))[0];
  return (
    <Panel className="overflow-hidden xl:col-span-4">
      <PanelHeader title="Best Candidate" icon={Trophy} />
      {champion ? (
        <div className="space-y-4 p-4">
          <button className="break-words text-left text-xl font-semibold text-ink hover:underline [overflow-wrap:anywhere]" onClick={() => onSelectRun(champion.id)} type="button">
            {champion.name}
          </button>
          <div className="grid grid-cols-2 gap-3">
            <ReadOnlyField label="Sharpe" value={formatMetric(metricValue(champion, 'strategy.summary', 'sharpe'))} />
            <ReadOnlyField label="Max DD" value={formatMetric(metricValue(champion, 'strategy.summary', 'max_drawdown'))} />
            <ReadOnlyField label="Runtime" value={runRuntime(champion)} />
            <ReadOnlyField label="Updated" value={formatDate(champion.updated_at || champion.ended_at)} />
          </div>
        </div>
      ) : <div className="p-5 text-sm text-muted">{t("No completed candidate yet.")}</div>}
    </Panel>
  );
}

function DecisionRunsPanel({ title, runs, onSelectRun, onSelectBranch }) {
  const ordered = [...runs].sort((a, b) => dateMillis(b.updated_at || b.ended_at || b.created_at) - dateMillis(a.updated_at || a.ended_at || a.created_at));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title={title} icon={LineChart} />
      <DecisionRunsTable runs={ordered} onSelectRun={onSelectRun} onSelectBranch={onSelectBranch} emptyText="No runs on this branch." />
    </Panel>
  );
}

function LineageChartModal({ option, onClose }) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-ink/25 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" onPointerDown={onClose}>
      <div className="flex h-[min(86vh,860px)] w-full max-w-6xl flex-col overflow-hidden rounded-md border border-line bg-panel shadow-xl" onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-semibold text-ink">{t("Branch Lineage")}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close branch lineage">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 cursor-grab p-4 active:cursor-grabbing">
          <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
        </div>
      </div>
    </div>
  );
}

function BranchLineagePanel({ lineage, error, fallbackBranch, fallbackBranches, fallbackRuns, onSelectBranch, onSelectRun }) {
  const branches = lineage?.branches || fallbackBranches.filter((item) => item.research_id === fallbackBranch.research_id);
  const runs = lineage?.runs || fallbackRuns.filter((run) => branches.some((branch) => branch.id === run.branch_id));
  const branchById = Object.fromEntries(branches.map((item) => [item.id, item]));
  const runById = Object.fromEntries(runs.map((item) => [item.id, item]));
  const ancestorIds = lineage?.ancestor_branch_ids || collectAncestorIds(fallbackBranch, branchById);
  const descendantIds = lineage?.descendant_branch_ids || branches.filter((item) => item.parent_branch_id === fallbackBranch.id).map((item) => item.id);
  const sourceRows = branches
    .filter((item) => item.source_run_id)
    .map((item) => ({ branch: item, run: runById[item.source_run_id] }))
    .sort((left, right) => new Date(right.branch.created_at || 0) - new Date(left.branch.created_at || 0));
  const lineageCount = new Set([...ancestorIds, fallbackBranch.id, ...descendantIds]).size;
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Lineage Context" icon={GitBranch} />
      {error ? <div className="px-5 pt-4"><InlineError message={error} /></div> : null}
      <div className="grid gap-4 p-4 xl:grid-cols-3">
        <LineageBranchList title="Ancestors" ids={ancestorIds} branchById={branchById} empty="No ancestor branches." onSelectBranch={onSelectBranch} />
        <LineageBranchList title="Descendants" ids={descendantIds} branchById={branchById} empty="No descendant branches." onSelectBranch={onSelectBranch} />
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t("Source Runs")}</div>
          <div className="space-y-2">
            {sourceRows.length ? sourceRows.map(({ branch, run }) => (
              <div className="rounded-md border border-line bg-white/55 p-3" key={`${branch.id}-${branch.source_run_id}`}>
                <button className="block text-left text-sm font-semibold text-ink hover:text-info" onClick={() => onSelectBranch(branch.id)}>{branch.title || branch.key}</button>
                {run ? <button className="mt-1 block text-left text-xs text-muted hover:text-info" onClick={() => onSelectRun(run.id)}>from {run.name}</button> : <div className="mt-1 text-xs text-muted">from {branch.source_run_id}</div>}
              </div>
            )) : <div className="rounded-md border border-line bg-white/45 p-3 text-sm text-muted">{t("No source run links.")}</div>}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function LineageBranchList({ title, ids, branchById, empty, onSelectBranch }) {
  const branches = ids.map((id) => branchById[id]).filter(Boolean);
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      <div className="space-y-2">
        {branches.length ? branches.map((branch) => (
          <button className="block w-full rounded-md border border-line bg-white/55 p-3 text-left transition hover:border-info" key={branch.id} onClick={() => onSelectBranch(branch.id)}>
            <div className="text-sm font-semibold text-ink">{branch.title || branch.key}</div>
            <div className="mt-1 text-xs text-muted">{tStatus(branch.status)} · {branch.reason_summary || branch.reason_code || t('lineage branch')}</div>
          </button>
        )) : <div className="rounded-md border border-line bg-white/45 p-3 text-sm text-muted">{empty}</div>}
      </div>
    </div>
  );
}

function collectAncestorIds(branch, branchById) {
  const ids = [];
  let current = branch;
  const seen = new Set([branch?.id]);
  while (current?.parent_branch_id && branchById[current.parent_branch_id] && !seen.has(current.parent_branch_id)) {
    current = branchById[current.parent_branch_id];
    ids.unshift(current.id);
    seen.add(current.id);
  }
  return ids;
}

function BranchEditPanel({ branch, onChanged }) {
  const [form, setForm] = useState({ title: branch.title || '', status: branch.status || 'active', reason_summary: branch.reason_summary || '', hypothesis: branch.hypothesis || '', expected_change: JSON.stringify(branch.expected_change || {}) });
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setForm({ title: branch.title || '', status: branch.status || 'active', reason_summary: branch.reason_summary || '', hypothesis: branch.hypothesis || '', expected_change: JSON.stringify(branch.expected_change || {}) });
    setEditing(false);
    setError(null);
  }, [branch.id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/branches/${branch.id}`, {
        title: form.title,
        status: form.status,
        reason_summary: form.reason_summary,
        hypothesis: form.hypothesis,
        expected_change: parseJsonObject(form.expected_change),
      });
      await onChanged();
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Branch Metadata" icon={GitBranch} action={<EditPanelAction editing={editing} onEdit={() => setEditing(true)} label="Edit branch metadata" />} />
      {editing ? (
        <form className="grid gap-4 p-4 lg:grid-cols-2" onSubmit={submit}>
          <Field label="Title"><TextInput required value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
          <Field label="Status">
            <SelectInput required value={form.status} onChange={(event) => update('status', event.target.value)}>
              {branchStatuses.map((status) => <option key={status} value={status}>{tStatus(status)}</option>)}
            </SelectInput>
          </Field>
          <Field label="Reason"><TextArea value={form.reason_summary} onChange={(event) => update('reason_summary', event.target.value)} /></Field>
          <Field label="Hypothesis"><TextArea value={form.hypothesis} onChange={(event) => update('hypothesis', event.target.value)} /></Field>
          <Field label="Expected Change JSON"><TextInput value={form.expected_change} onChange={(event) => update('expected_change', event.target.value)} /></Field>
          <div className="flex items-end gap-2">
            <button className="secondary-button mt-2 w-full" type="button" onClick={() => setEditing(false)}>{t("Cancel")}</button>
            <SubmitButton loading={loading}>Update branch</SubmitButton>
          </div>
          <div className="lg:col-span-2"><InlineError message={error} /></div>
        </form>
      ) : (
        <div className="grid gap-4 p-4 lg:grid-cols-2">
          <ReadOnlyField label="Title" value={branch.title} />
          <ReadOnlyField label="Status" value={tStatus(branch.status)} />
          <ReadOnlyField label="Creator" value={runCreator(branch)} />
          <ReadOnlyField label="Reason" value={branch.reason_summary} multiline />
          <ReadOnlyField label="Hypothesis" value={branch.hypothesis} multiline />
          <ReadOnlyField label="Expected Change" value={compactKeyValueSummary(branch.expected_change || {})} code />
        </div>
      )}
    </Panel>
  );
}

const quickCompareMetrics = [
  'strategy.summary.annual_return',
  'strategy.summary.annual_volatility',
  'strategy.summary.max_drawdown',
  'strategy.summary.sharpe',
  'strategy.summary.sortino',
  'strategy.summary.calmar',
  'strategy.summary.turnover',
];

function QuickCompareCard({ title = 'Compare', targets, emptyText = 'No targets available for compare.', onSelectRun }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedRunIds, setSelectedRunIds] = useState([]);
  const [sort, setSort] = useState({ key: null, direction: 'asc' });
  const normalizedTargets = (targets || []).filter((target) => target?.type && target?.id);
  const targetKey = normalizedTargets.map((target) => `${target.type}:${target.id}`).join('|');
  useEffect(() => {
    let cancelled = false;
    const loadCompare = async () => {
      if (!normalizedTargets.length) {
        setResult(null);
        setError(null);
        return;
      }
      try {
        const payload = await apiPost('/api/v1/quick-compare', {
          targets: normalizedTargets,
          metrics: quickCompareMetrics,
          series: ['equity_curve', 'returns_series', 'pnl_series', 'absolute_return_series'],
        });
        if (!cancelled) {
          setResult(payload);
          setSelectedRunIds((payload.targets || []).map((target) => target.resolved_run?.id).filter(Boolean));
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setResult(null);
          setError(err.message);
        }
      }
    };
    loadCompare();
    return () => { cancelled = true; };
  }, [targetKey]);
  const seriesEntry = preferredQuickCompareSeries(result?.series || {});
  const runById = Object.fromEntries((result?.runs || []).map((run) => [run.id, run]));
  const rows = (result?.targets || []).map((target) => ({
    target,
    run: target.resolved_run,
  }));
  const sortedRows = sortQuickCompareRows(rows, result?.metrics || {}, sort);
  const selectableRunIds = rows.map((row) => row.run?.id).filter(Boolean);
  const selectedSet = new Set(selectedRunIds);
  const allSelected = selectableRunIds.length > 0 && selectableRunIds.every((id) => selectedSet.has(id));
  const selectedSeriesEntry = seriesEntry ? {
    ...seriesEntry,
    byRun: Object.fromEntries(Object.entries(seriesEntry.byRun || {}).filter(([runId]) => selectedSet.has(runId))),
  } : null;
  const toggleSort = (key) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  };
  const toggleRun = (runId) => {
    if (!runId) return;
    setSelectedRunIds((current) => (current.includes(runId) ? current.filter((id) => id !== runId) : [...current, runId]));
  };
  const toggleAll = () => {
    setSelectedRunIds(allSelected ? [] : selectableRunIds);
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title={title} icon={LineChart} />
      {error ? <div className="px-5 pt-4"><InlineError message={error} /></div> : null}
      {normalizedTargets.length ? (
        <div className="space-y-5 p-5">
          <div>
            {selectedSeriesEntry ? (
              <ReactECharts
                key={selectedRunIds.join('|') || 'empty'}
                notMerge
                option={seriesChartOption(selectedSeriesEntry.name, selectedSeriesEntry.byRun, runById)}
                style={{ height: 320 }}
              />
            ) : (
              <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No Series Data Available")}</div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse">
              <thead className="table-head">
                <tr>
                  <th className="px-4 py-3">
                    <input checked={allSelected} className="h-4 w-4 accent-charcoal" onChange={toggleAll} type="checkbox" aria-label="Toggle all compare series" />
                  </th>
                  <th className="px-4 py-3"><SortableHeader label="Target" sortKey="target" sort={sort} onSort={toggleSort} /></th>
                  <th className="px-4 py-3"><SortableHeader label="Run" sortKey="run" sort={sort} onSort={toggleSort} /></th>
                  {quickCompareMetrics.map((metric) => <th className="px-4 py-3 text-right" key={metric}><SortableHeader label={quickMetricLabel(metric)} sortKey={metric} sort={sort} onSort={toggleSort} /></th>)}
                </tr>
              </thead>
              <tbody>
                {sortedRows.length ? sortedRows.map(({ target, run }) => (
                  <tr className="hover:bg-white/45" key={`${target.type}-${target.id}`}>
                    <td className="table-cell">
                      <input
                        checked={Boolean(run?.id && selectedSet.has(run.id))}
                        className="h-4 w-4 accent-charcoal"
                        disabled={!run?.id}
                        onChange={() => toggleRun(run?.id)}
                        type="checkbox"
                        aria-label={`Toggle ${target.label || run?.name || 'compare series'}`}
                      />
                    </td>
                    <td className="table-cell">
                      <div className="font-semibold text-ink">{target.label}</div>
                      <div className="mt-1 text-xs text-muted">{target.type}</div>
                    </td>
                    <td className="table-cell">
                      {run ? (
                        <button className="font-semibold text-ink hover:text-info" type="button" onClick={() => onSelectRun?.(run.id)}>
                          {run.name}
                        </button>
                      ) : <span className="text-muted">{t("No representative run")}</span>}
                    </td>
                    {quickCompareMetrics.map((metric) => (
                      <td className="table-cell text-right" key={metric}>
                        {formatQuickMetric(metric, result?.metrics?.[metric]?.[run?.id])}
                      </td>
                    ))}
                  </tr>
                )) : <tr><td className="table-cell text-muted" colSpan={quickCompareMetrics.length + 3}>{t("No compare rows.")}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      ) : <div className="p-5 text-sm text-muted">{emptyText}</div>}
    </Panel>
  );
}

function SortableHeader({ label, sortKey, sort, onSort }) {
  const active = sort?.key === sortKey;
  return (
    <button className="inline-flex items-center gap-1 text-left uppercase hover:text-ink" type="button" onClick={() => onSort(sortKey)}>
      <span>{tx(label)}</span>
      <span className={`text-[10px] ${active ? 'text-ink' : 'text-muted/50'}`}>{active ? (sort.direction === 'asc' ? '↑' : '↓') : '↕'}</span>
    </button>
  );
}

function sortQuickCompareRows(rows, metrics, sort) {
  if (!sort?.key) return rows;
  const direction = sort.direction === 'desc' ? -1 : 1;
  const valueFor = (row) => {
    if (sort.key === 'target') return row.target?.label || '';
    if (sort.key === 'run') return row.run?.name || '';
    return toNumber(metrics?.[sort.key]?.[row.run?.id]);
  };
  return [...rows].sort((left, right) => {
    const leftValue = valueFor(left);
    const rightValue = valueFor(right);
    const leftNumber = Number(leftValue);
    const rightNumber = Number(rightValue);
    if (Number.isFinite(leftNumber) || Number.isFinite(rightNumber)) {
      if (!Number.isFinite(leftNumber)) return 1;
      if (!Number.isFinite(rightNumber)) return -1;
      return (leftNumber - rightNumber) * direction;
    }
    return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' }) * direction;
  });
}

function preferredQuickCompareSeries(series) {
  for (const name of ['equity_curve', 'returns_series', 'pnl_series', 'absolute_return_series']) {
    if (series?.[name]) return { name, byRun: series[name] };
  }
  const first = Object.entries(series || {})[0];
  return first ? { name: first[0], byRun: first[1] } : null;
}

function quickMetricLabel(metric) {
  return metric.split('.').slice(-1)[0].replaceAll('_', ' ');
}

function formatQuickMetric(metric, value) {
  if (/annual_return|annual_volatility|max_drawdown/.test(metric)) return formatPercentMetric(value);
  return formatMetric(value);
}

function BranchMetricEvolution({ runs, onSelectRun }) {
  const metrics = branchEvolutionMetrics(runs);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Metric Evolution" icon={LineChart} />
      {runs.length ? (
        <div className="p-4">
          <ReactECharts option={branchMetricOption(runs, metrics)} style={{ height: 320 }} />
          <div className="mt-3 flex flex-wrap gap-2">
            {runs.map((run) => (
              <button className="secondary-button" key={run.id} onClick={() => onSelectRun(run.id)}>
                <LineChart className="h-4 w-4" />{run.name}
              </button>
            ))}
          </div>
        </div>
      ) : <div className="p-5 text-sm text-muted">{t("No runs on this branch.")}</div>}
    </Panel>
  );
}

function BranchConfigEvolution({ runs, onSelectRun }) {
  const rows = configEvolutionRows(runs);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Config Evolution" icon={GitBranch} />
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full min-w-[720px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Config Path")}</th><th className="px-4 py-3">{t("Before")}</th><th className="px-4 py-3">{t("After")}</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="hover:bg-white/45" key={`${row.run.id}-${row.path}`}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(row.run.id)}>{row.run.name}</button>
                </td>
                <td className="table-cell text-muted">{row.path}</td>
                <td className="table-cell text-muted">{formatConfigValue(row.before)}</td>
                <td className="table-cell font-semibold text-ink">{formatConfigValue(row.after)}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="4">{t("No config changes detected between consecutive runs.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function BranchSweepPanel({ branch, runs, sweeps, error, onChanged, onSelectRun }) {
  const [selectedSweepId, setSelectedSweepId] = useState(sweeps[0]?.id || '');
  const [activeAction, setActiveAction] = useState('');
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  useEffect(() => {
    setSelectedSweepId((current) => (sweeps.some((sweep) => sweep.id === current) ? current : sweeps[0]?.id || ''));
  }, [sweeps]);
  useEffect(() => {
    setActiveAction('');
  }, [branch.id]);
  useEffect(() => {
    let cancelled = false;
    const loadSummary = async () => {
      if (!selectedSweepId) {
        setSummary(null);
        setSummaryError(null);
        return;
      }
      try {
        const payload = await apiGet(`/api/v1/sweeps/${selectedSweepId}/summary`);
        if (!cancelled) {
          setSummary(payload);
          setSummaryError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSummary(null);
          setSummaryError(err.message);
        }
      }
    };
    loadSummary();
    return () => { cancelled = true; };
  }, [selectedSweepId]);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Sweep Management"
        action={activeAction ? <button className="secondary-button" type="button" onClick={() => setActiveAction('')}>{t("Close")}</button> : null}
      />
      {error ? <div className="px-4 pt-4"><InlineError message={error} /></div> : null}
      <div className="border-b border-line p-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:max-w-xl">
          <button className={`secondary-button justify-start ${activeAction === 'create' ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setActiveAction((current) => (current === 'create' ? '' : 'create'))}>
            <PlusCircle className="h-4 w-4" />
            Create Sweep
          </button>
          <button className={`secondary-button justify-start ${activeAction === 'attach' ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setActiveAction((current) => (current === 'attach' ? '' : 'attach'))}>
            <GitBranch className="h-4 w-4" />
            Attach Run
          </button>
        </div>
        {activeAction ? (
          <div className="mt-4 max-w-2xl">
            {activeAction === 'create' ? <SweepCreateForm branch={branch} onChanged={onChanged} /> : null}
            {activeAction === 'attach' ? <SweepAttachForm runs={runs} sweeps={sweeps} onChanged={onChanged} /> : null}
          </div>
        ) : <div className="mt-3 max-w-xl"><ReadOnlyField label="Current Operation" value="none selected" /></div>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Sweep")}</th><th className="px-4 py-3">{t("Status")}</th><th className="px-4 py-3">{t("Search Space")}</th><th className="px-4 py-3">{t("Objective")}</th><th className="px-4 py-3 text-right">{t("Runs")}</th></tr></thead>
          <tbody>
            {sweeps.length ? sweeps.map((sweep) => (
              <tr className={`hover:bg-white/45 ${selectedSweepId === sweep.id ? 'bg-infoSoft/60' : ''}`} key={sweep.id}>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => setSelectedSweepId(sweep.id)}>{sweep.name}</button>
                </td>
                <td className="table-cell"><Badge tone={sweep.status === 'active' ? 'positive' : 'neutral'}>{tStatus(sweep.status)}</Badge></td>
                <td className="table-cell text-muted">{formatSearchSpace(sweep.search_space_json)}</td>
                <td className="table-cell text-muted">{formatSweepObjective(sweep.objective_json)}</td>
                <td className="table-cell text-right">{sweep.run_count || 0}</td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="5">{t("No sweeps on this branch.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <SweepSummary summary={summary} error={summaryError} onSelectRun={onSelectRun} />
    </Panel>
  );
}

function SweepSummary({ summary, error, onSelectRun }) {
  if (error) return <div className="border-t border-line p-4"><InlineError message={error} /></div>;
  if (!summary) return <div className="border-t border-line p-4 text-sm text-muted">{t("Select a sweep to inspect parameter results.")}</div>;
  return (
    <div className="grid gap-4 border-t border-line p-4 xl:grid-cols-2">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-ink">{t("Parameter Heatmap")}</div>
            <div className="mt-1 text-xs text-muted">{summary.objective.metric} · {summary.objective.direction}</div>
          </div>
        </div>
        <SweepHeatmap heatmap={summary.heatmap} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Rank")}</th><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Coord")}</th><th className="px-4 py-3 text-right">{t("Value")}</th></tr></thead>
          <tbody>
            {summary.rows.map((row) => (
              <tr className="hover:bg-white/45" key={row.sweep_run_id}>
                <td className="table-cell">{row.rank || row.computed_rank || '--'}</td>
                <td className="table-cell">
                  <button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(row.run_id)}>{row.run_name || row.run_id}</button>
                </td>
                <td className="table-cell text-muted">{formatCoord(row.coord)}</td>
                <td className="table-cell text-right">{formatMetric(row.value)}</td>
              </tr>
            ))}
            {!summary.rows.length && <tr><td className="table-cell text-muted" colSpan="4">{t("No runs attached.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SweepHeatmap({ heatmap }) {
  const cells = heatmap?.cells || [];
  if (!heatmap?.x_key || !heatmap?.y_key || !cells.length) {
    return <div className="rounded-md border border-line bg-white/45 p-4 text-sm text-muted">{t("Attach runs with two coordinate keys to render a heatmap.")}</div>;
  }
  const values = cells.map((cell) => Number(cell.value)).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const cellMap = new Map(cells.map((cell) => [`${JSON.stringify(cell.x)}\u0000${JSON.stringify(cell.y)}`, cell]));
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid min-w-full gap-1" style={{ gridTemplateColumns: `88px repeat(${heatmap.x_values.length}, minmax(76px, 1fr))` }}>
        <div className="px-2 py-2 text-xs font-semibold text-muted">{heatmap.y_key} \\ {heatmap.x_key}</div>
        {heatmap.x_values.map((xValue) => <div className="px-2 py-2 text-center text-xs font-semibold text-muted" key={JSON.stringify(xValue)}>{String(xValue)}</div>)}
        {heatmap.y_values.map((yValue) => (
          <React.Fragment key={JSON.stringify(yValue)}>
            <div className="px-2 py-3 text-xs font-semibold text-muted">{String(yValue)}</div>
            {heatmap.x_values.map((xValue) => {
              const cell = cellMap.get(`${JSON.stringify(xValue)}\u0000${JSON.stringify(yValue)}`);
              const intensity = heatIntensity(cell?.value, min, max);
              return (
                <div
                  className="min-h-12 rounded-md border border-line px-2 py-2 text-center text-xs font-semibold text-ink"
                  key={`${JSON.stringify(xValue)}-${JSON.stringify(yValue)}`}
                  style={{ backgroundColor: cell ? `rgba(20, 184, 166, ${intensity})` : 'rgba(255,255,255,0.45)' }}
                  title={cell ? `${cell.run_name || cell.run_id}: ${formatMetric(cell.value)}` : 'No run'}
                >
                  {cell ? formatMetric(cell.value) : '--'}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function SweepCreateForm({ branch, onChanged }) {
  const [form, setForm] = useState({
    name: '',
    search_space: '{"lookback":[10,20],"hold_days":[5]}',
    objective: '{"metric":"strategy.summary.sharpe","direction":"max"}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost('/api/v1/sweeps', {
        branch_id: branch.id,
        name: form.name,
        search_space: parseJsonObject(form.search_space),
        objective: parseJsonObject(form.objective),
        status: 'active',
      });
      setForm((current) => ({ ...current, name: '' }));
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Create Sweep">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="lookback-hold-grid" /></Field>
        <Field label="Search Space JSON"><TextArea required value={form.search_space} onChange={(event) => update('search_space', event.target.value)} /></Field>
        <Field label="Objective JSON"><TextArea required value={form.objective} onChange={(event) => update('objective', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Create sweep</SubmitButton>
      </form>
    </FormCard>
  );
}

function SweepAttachForm({ runs, sweeps, onChanged }) {
  const firstSweepId = sweeps[0]?.id || '';
  const firstRunId = runs[0]?.id || '';
  const [form, setForm] = useState({ sweep_id: firstSweepId, run_id: firstRunId, coord: '{}', rank: '' });
  const [runQuery, setRunQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const normalizedRunQuery = runQuery.trim().toLowerCase();
  const filteredRuns = (runs || []).filter((run) => !normalizedRunQuery || runSelectionSearchText(run).includes(normalizedRunQuery));
  const selectedRun = (runs || []).find((run) => run.id === form.run_id);
  const runIdsKey = (runs || []).map((run) => run.id).join('|');
  useEffect(() => {
    setForm((current) => ({
      ...current,
      sweep_id: current.sweep_id || firstSweepId,
      run_id: current.run_id && runs.some((run) => run.id === current.run_id) ? current.run_id : firstRunId,
    }));
  }, [firstSweepId, firstRunId, runIdsKey]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/sweeps/${form.sweep_id}/runs`, {
        run_id: form.run_id,
        coord: parseJsonObject(form.coord),
        rank: form.rank ? Number(form.rank) : null,
      });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Attach Run">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Sweep">
          <SelectInput required value={form.sweep_id} onChange={(event) => update('sweep_id', event.target.value)}>
            <option value="" disabled>{t("Select sweep")}</option>
            {sweeps.map((sweep) => <option key={sweep.id} value={sweep.id}>{sweep.name}</option>)}
          </SelectInput>
        </Field>
        <Field label="Run">
          <SelectInput required value={form.run_id} onChange={(event) => update('run_id', event.target.value)}>
            <option value="" disabled>{t("Select run")}</option>
            {filteredRuns.map((run) => <option key={run.id} value={run.id}>{run.name}</option>)}
          </SelectInput>
        </Field>
        <Field label="Search runs"><TextInput value={runQuery} onChange={(event) => setRunQuery(event.target.value)} placeholder="run, branch, tag, config" /></Field>
        {selectedRun ? (
          <div className="rounded-md border border-line bg-white/45 p-3 text-xs text-muted">
            <div className="font-semibold text-ink">{selectedRun.name}</div>
            <div className="mt-1">{selectedRun.branch_key || selectedRun.branch_id} · {tStatus(selectedRun.status)} · {t('Sharpe')} {formatMetric(metricValue(selectedRun, 'strategy.summary', 'sharpe'))}</div>
            <div className="mt-1 truncate" title={configSummary(selectedRun.config_json)}>{configSummary(selectedRun.config_json)}</div>
          </div>
        ) : <div className="rounded-md border border-line bg-white/45 p-3 text-xs text-muted">{t("No run selected.")}</div>}
        <Field label="Coord JSON"><TextInput required value={form.coord} onChange={(event) => update('coord', event.target.value)} /></Field>
        <Field label="Rank"><TextInput value={form.rank} onChange={(event) => update('rank', event.target.value)} type="number" min="1" /></Field>
        <InlineError message={error || (!sweeps.length ? 'Create a sweep before attaching runs.' : null) || (runQuery && !filteredRuns.length ? 'No runs match the current search.' : null)} />
        <SubmitButton loading={loading}>{t("Attach run")}</SubmitButton>
      </form>
    </FormCard>
  );
}

function SweepPage({ data, selectedSweepId, selectSweep, selectRun, onChanged }) {
  const sweeps = data?.sweeps || [];
  const branches = data?.branches || [];
  const runs = data?.runs || [];
  const [sweepQuery, setSweepQuery] = useState('');
  const [sweepStatus, setSweepStatus] = useState('');
  const [activeOperation, setActiveOperation] = useState('');
  const selectedSweepBase = sweeps.find((sweep) => sweep.id === selectedSweepId) || sweeps[0];
  const [selectedSweepDetail, setSelectedSweepDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!selectedSweepBase?.id) {
        setSelectedSweepDetail(null);
        setDetailError(null);
        setSummary(null);
        setSummaryError(null);
        return;
      }
      try {
        const [detailPayload, summaryPayload] = await Promise.all([
          apiGet(`/api/v1/sweeps/${selectedSweepBase.id}`),
          apiGet(`/api/v1/sweeps/${selectedSweepBase.id}/summary`),
        ]);
        if (!cancelled) {
          setSelectedSweepDetail(detailPayload);
          setDetailError(null);
          setSummary(summaryPayload);
          setSummaryError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedSweepDetail(null);
          setDetailError(err.message);
          try {
            const summaryPayload = await apiGet(`/api/v1/sweeps/${selectedSweepBase.id}/summary`);
            if (!cancelled) {
              setSummary(summaryPayload);
              setSummaryError(null);
            }
          } catch (summaryErr) {
            if (!cancelled) {
              setSummary(null);
              setSummaryError(summaryErr.message);
            }
          }
        }
      }
    };
    load();
    return () => { cancelled = true; };
  }, [selectedSweepBase?.id]);
  useEffect(() => {
    setActiveOperation('');
  }, [selectedSweepBase?.id]);
  if (!sweeps.length && !branches.length) {
    return <EmptyState title="No branches for sweeps" detail="Create a project, research, and branch before starting parameter sweeps." />;
  }
  const selectedSweep = selectedSweepDetail || selectedSweepBase;
  const candidateRuns = mergeRunsById(
    runs.filter((run) => !selectedSweep?.branch_id || run.branch_id === selectedSweep.branch_id),
    selectedSweepDetail?.runs || [],
  );
  const sweepRuns = mergeRunsById(selectedSweepDetail?.runs || [], runs);
  const branchById = Object.fromEntries(branches.map((branch) => [branch.id, branch]));
  const normalizedSweepQuery = sweepQuery.trim().toLowerCase();
  const filteredSweeps = sweeps.filter((sweep) => {
    const matchesStatus = !sweepStatus || sweep.status === sweepStatus;
    const matchesQuery = !normalizedSweepQuery || sweepSearchText(sweep, branchById[sweep.branch_id]).includes(normalizedSweepQuery);
    return matchesStatus && matchesQuery;
  });
  return (
    <div className="space-y-5">
      <Hero eyebrow="Sweep" title={selectedSweep?.name || 'Parameter Sweeps'} description={selectedSweep ? formatSweepObjective(selectedSweep.objective_json) : null} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Sweeps" value={sweeps.length} tone="warning" />
        <StatTile label="Selected Runs" value={summary?.rows?.length || selectedSweep?.run_count || 0} tone="positive" />
        <StatTile label="Coord Keys" value={summary?.coord_keys?.length || 0} tone="info" />
        <StatTile label="Objective" value={selectedSweep?.objective_json?.direction || '--'} tone="neutral" />
      </div>
      <Panel className="overflow-hidden">
        <PanelHeader
          title="Sweep Operations"
          action={activeOperation ? <button className="secondary-button" type="button" onClick={() => setActiveOperation('')}>{t("Close")}</button> : null}
        />
        {detailError ? <div className="px-4 pt-4"><InlineError message={detailError} /></div> : null}
        <div className="p-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:max-w-xl">
            <button className={`secondary-button justify-start ${activeOperation === 'create' ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setActiveOperation((current) => (current === 'create' ? '' : 'create'))}>
              <PlusCircle className="h-4 w-4" />
              Create Sweep
            </button>
            <button className={`secondary-button justify-start ${activeOperation === 'attach' ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setActiveOperation((current) => (current === 'attach' ? '' : 'attach'))}>
              <GitBranch className="h-4 w-4" />
              Attach Run
            </button>
          </div>
          {activeOperation ? (
            <div className="mt-4 max-w-2xl">
              {activeOperation === 'create' ? <GlobalSweepCreateForm branches={branches} onChanged={onChanged} onCreated={selectSweep} /> : null}
              {activeOperation === 'attach' ? <SweepAttachForm runs={candidateRuns} sweeps={sweeps} onChanged={onChanged} /> : null}
            </div>
          ) : <div className="mt-3 max-w-xl"><ReadOnlyField label="Current Operation" value="none selected" /></div>}
        </div>
      </Panel>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="overflow-hidden xl:col-span-5">
          <PanelHeader title="Sweep List" icon={Database} />
          <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1fr_160px_auto]">
            <Field label="Search sweeps"><TextInput value={sweepQuery} onChange={(event) => setSweepQuery(event.target.value)} placeholder="name, branch, objective, search space" /></Field>
            <Field label="Status">
              <SelectInput value={sweepStatus} onChange={(event) => setSweepStatus(event.target.value)}>
                <option value="">{t("Any status")}</option>
                {['active', 'completed', 'archived'].map((item) => <option key={item} value={item}>{tStatus(item)}</option>)}
              </SelectInput>
            </Field>
            <div className="flex items-end text-xs font-semibold text-muted">{filteredSweeps.length} / {sweeps.length} shown</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] border-collapse">
              <thead className="table-head"><tr><th className="px-4 py-3">{t("Sweep")}</th><th className="px-4 py-3">{t("Branch")}</th><th className="px-4 py-3">{t("Objective")}</th><th className="px-4 py-3 text-right">{t("Runs")}</th></tr></thead>
              <tbody>
                {filteredSweeps.length ? filteredSweeps.map((sweep) => (
                  <tr className={`hover:bg-white/45 ${selectedSweep?.id === sweep.id ? 'bg-infoSoft/60' : ''}`} key={sweep.id}>
                    <td className="table-cell"><button className="font-semibold text-ink hover:text-info" onClick={() => selectSweep(sweep.id)}>{sweep.name}</button></td>
                    <td className="table-cell text-muted">{branchById[sweep.branch_id]?.key || sweep.branch_id}</td>
                    <td className="table-cell text-muted">{formatSweepObjective(sweep.objective_json)}</td>
                    <td className="table-cell text-right">{sweep.run_count || 0}</td>
                  </tr>
                )) : <tr><td className="table-cell text-muted" colSpan="4">{sweeps.length ? 'No sweeps match the current filters.' : 'No sweeps yet.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel className="overflow-hidden xl:col-span-7">
          <SweepSummary summary={summary} error={summaryError} onSelectRun={selectRun} />
        </Panel>
      </div>
      <SweepParetoPanel summary={summary} runs={sweepRuns} onSelectRun={selectRun} />
    </div>
  );
}

function GlobalSweepCreateForm({ branches, onChanged, onCreated }) {
  const firstBranchId = branches[0]?.id || '';
  const [form, setForm] = useState({
    branch_id: firstBranchId,
    name: '',
    search_space: '{"lookback":[10,20],"hold_days":[5]}',
    objective: '{"metric":"strategy.summary.sharpe","direction":"max"}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!form.branch_id && firstBranchId) setForm((current) => ({ ...current, branch_id: firstBranchId }));
  }, [firstBranchId, form.branch_id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const sweep = await apiPost('/api/v1/sweeps', {
        branch_id: form.branch_id,
        name: form.name,
        search_space: parseJsonObject(form.search_space),
        objective: parseJsonObject(form.objective),
        status: 'active',
      });
      setForm((current) => ({ ...current, name: '' }));
      await onChanged();
      onCreated(sweep.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Create Sweep">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Branch">
          <SelectInput required value={form.branch_id} onChange={(event) => update('branch_id', event.target.value)}>
            <option value="" disabled>{t("Select branch")}</option>
            {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="lookback-hold-grid" /></Field>
        <Field label="Search Space JSON"><TextArea required value={form.search_space} onChange={(event) => update('search_space', event.target.value)} /></Field>
        <Field label="Objective JSON"><TextArea required value={form.objective} onChange={(event) => update('objective', event.target.value)} /></Field>
        <InlineError message={error || (!branches.length ? 'Create a branch before creating sweeps.' : null)} />
        <SubmitButton loading={loading}>Create sweep</SubmitButton>
      </form>
    </FormCard>
  );
}

function SweepParetoPanel({ summary, runs, onSelectRun }) {
  const [xMetric, setXMetric] = useState('strategy.summary.sharpe');
  const [yMetric, setYMetric] = useState('strategy.summary.max_drawdown');
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  const sweepRuns = (summary?.rows || []).map((row) => runById[row.run_id]).filter(Boolean);
  const metricOptions = sweepMetricOptions(sweepRuns);
  useEffect(() => {
    if (!metricOptions.includes(xMetric) && metricOptions[0]) setXMetric(metricOptions[0]);
    if (!metricOptions.includes(yMetric) && metricOptions[1]) setYMetric(metricOptions[1]);
  }, [metricOptions.join('|'), xMetric, yMetric]);
  const points = sweepRuns.map((run) => ({
    run,
    x: toNumber(getSummaryMetric(run.summary_json, xMetric)),
    y: toNumber(getSummaryMetric(run.summary_json, yMetric)),
  })).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const frontierIds = paretoFrontierIds(points, xMetric, yMetric);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Pareto Frontier" icon={Activity} />
      <div className="grid gap-4 p-4 xl:grid-cols-12">
        <div className="grid gap-2 xl:col-span-3">
          <Field label="X metric">
            <SelectInput value={xMetric} onChange={(event) => setXMetric(event.target.value)}>
              {metricOptions.map((metric) => <option key={metric} value={metric}>{metric}</option>)}
            </SelectInput>
          </Field>
          <Field label="Y metric">
            <SelectInput value={yMetric} onChange={(event) => setYMetric(event.target.value)}>
              {metricOptions.map((metric) => <option key={metric} value={metric}>{metric}</option>)}
            </SelectInput>
          </Field>
        </div>
        <div className="xl:col-span-9">
          {points.length ? (
            <ReactECharts option={paretoChartOption(points, frontierIds, xMetric, yMetric)} style={{ height: 340 }} />
          ) : <div className="rounded-md border border-line bg-white/45 p-4 text-sm text-muted">{t("Attach sweep runs with at least two numeric summary metrics to render Pareto frontier.")}</div>}
        </div>
      </div>
      {points.length ? (
        <div className="overflow-x-auto border-t border-line">
          <table className="w-full min-w-[760px] border-collapse">
            <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3 text-right">{xMetric}</th><th className="px-4 py-3 text-right">{yMetric}</th><th className="px-4 py-3">{t("Frontier")}</th></tr></thead>
            <tbody>
              {points.map((point) => (
                <tr className="hover:bg-white/45" key={point.run.id}>
                  <td className="table-cell"><button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(point.run.id)}>{point.run.name}</button></td>
                  <td className="table-cell text-right">{formatMetric(point.x)}</td>
                  <td className="table-cell text-right">{formatMetric(point.y)}</td>
                  <td className="table-cell text-muted">{frontierIds.includes(point.run.id) ? 'frontier' : 'dominated'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}

function RunPage({ runDetail, data, onRunChanged }) {
  const [activeTab, setActiveTab] = useState('results');
  if (!runDetail) return <EmptyState title="No run selected" detail="Select a run from Dashboard, Research, or Branch." />;
  const metrics = runDetail.metrics || [];
  const artifacts = runDetail.artifacts || [];
  const events = runDetail.events || [];
  const notes = runDetail.notes || [];
  const seriesArtifacts = runSeriesArtifacts(runDetail);
  const equityChart = runEquityChartData(seriesArtifacts);
  const resultItems = runResultItems(runDetail);
  const keyMetrics = runKeyMetricTiles(runDetail, equityChart);
  const diagnostics = runQualityDiagnostics(runDetail, { seriesArtifacts, equityChart, resultItems });
  return (
    <div className="space-y-5">
      <Hero
        eyebrow={`Run / ${tStatus(runDetail.status)}`}
        title={runDetail.title || runDetail.name}
        description={runHeroDescription(runDetail)}
        action={<StatusBadge status={runDetail.status} />}
      />
      <RunSummaryStrip run={runDetail} />
      <RunResultSummaryPanel
        run={runDetail}
        diagnostics={diagnostics}
        resultItems={resultItems}
        keyMetrics={keyMetrics}
        equityChart={equityChart}
        seriesArtifacts={seriesArtifacts}
      />
      <RunQualityDiagnosticsCard diagnostics={diagnostics} />
      <RunTabs
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        resultItems={resultItems}
        keyMetrics={keyMetrics}
        equityChart={equityChart}
        metrics={metrics}
        events={events}
        artifacts={artifacts}
        run={runDetail}
        notes={notes}
      />
      <DashboardCollapsedSection title="Actions">
        <div className="p-4">
          <RunWritePanel run={runDetail} data={data} onRunChanged={onRunChanged} />
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function RunResultSummaryPanel({ run, diagnostics, resultItems, keyMetrics, equityChart, seriesArtifacts }) {
  const summary = runResultSummary(run, { diagnostics, resultItems, keyMetrics, equityChart, seriesArtifacts });
  return (
    <Panel className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">{t("Result Summary")}</div>
          <div className="mt-1 text-xs text-muted">{t("Current run result coverage, primary curve, metrics, and quality status.")}</div>
        </div>
        <DiagnosticCountBadges errorCount={summary.errorCount} warningCount={summary.warningCount} showHealthy />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <ReadOnlyField label="Primary Curve" value={summary.primaryCurve} />
        <ReadOnlyField label="Series Range" value={summary.seriesRange} />
        <ReadOnlyField label="Result Domains" value={summary.domains} />
        <ReadOnlyField label="Key Metrics" value={summary.keyMetricCoverage} />
        <ReadOnlyField label="Artifacts" value={summary.artifactSummary} />
        <ReadOnlyField label="Updated" value={summary.updated} />
      </div>
    </Panel>
  );
}

function runResultSummary(run, { diagnostics, resultItems, keyMetrics, equityChart, seriesArtifacts }) {
  const primary = runPrimarySeriesItem(seriesArtifacts || []);
  const domainCounts = new Map();
  for (const item of resultItems || []) {
    domainCounts.set(item.domain, (domainCounts.get(item.domain) || 0) + 1);
  }
  const domains = Array.from(domainCounts.entries())
    .sort((left, right) => resultDomainOrder(left[0]) - resultDomainOrder(right[0]) || left[0].localeCompare(right[0]))
    .map(([domain, count]) => `${resultDomainLabel(domain)} ${count}`)
    .join(', ');
  const populatedMetrics = (keyMetrics || []).filter((item) => item.value && item.value !== '--').length;
  const primaryName = primary?.name || equityChart?.sourceName || null;
  const mode = primary?.mode || equityChart?.valueMode || null;
  return {
    errorCount: diagnostics?.errorCount || 0,
    warningCount: diagnostics?.warningCount || 0,
    primaryCurve: primaryName ? `${primaryName}${mode ? ` (${mode})` : ''}` : 'No Series Data Available',
    seriesRange: runSeriesRange(primary),
    domains: domains || 'none',
    keyMetricCoverage: `${populatedMetrics}/${(keyMetrics || []).length || 0}`,
    artifactSummary: `${(run?.artifacts || []).length} total · ${(resultItems || []).length} result`,
    updated: formatDate(run?.updated_at || run?.ended_at || run?.started_at),
  };
}

function runSeriesRange(item) {
  const rows = item?.rows || [];
  const xKey = item?.x;
  if (!rows.length || !xKey) return '--';
  const first = rows.find((row) => row?.[xKey] !== undefined && row?.[xKey] !== null && row?.[xKey] !== '')?.[xKey];
  const last = [...rows].reverse().find((row) => row?.[xKey] !== undefined && row?.[xKey] !== null && row?.[xKey] !== '')?.[xKey];
  const rowCount = Number(item?.previewRowCount);
  const suffix = Number.isFinite(rowCount) ? `${rows.length}/${rowCount} rows` : `${rows.length} rows`;
  return first || last ? `${first || '--'} -> ${last || '--'} · ${suffix}` : suffix;
}

function RunSummaryStrip({ run }) {
  const items = [
    { label: 'Project', value: run.project_key },
    { label: 'Research', value: run.research_key },
    { label: 'Branch', value: run.branch_key || run.branch_id },
    { label: 'Source run', value: run.source_run?.name || run.source_run_id },
    { label: 'Started', value: formatDate(run.started_at) },
    { label: 'Ended', value: formatDate(run.ended_at) },
    { label: 'Runtime', value: runRuntime(run) },
    { label: 'Creator', value: runCreator(run) },
    { label: 'Tags', value: (run.tags || []).join(', ') },
  ];
  return (
    <Panel className="p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-9">
        {items.map((item) => <ReadOnlyField key={item.label} label={item.label} value={item.value} />)}
      </div>
    </Panel>
  );
}

function DiagnosticCountBadges({ errorCount = 0, warningCount = 0, showHealthy = false }) {
  const errors = Number(errorCount) || 0;
  const warnings = Number(warningCount) || 0;
  if (!errors && !warnings && !showHealthy) return null;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {errors ? (
        <span className="rounded-sm bg-negativeSoft px-2 py-1 text-xs font-semibold uppercase text-negative">
          {errors} {errors === 1 ? 'ERROR' : 'ERRORS'}
        </span>
      ) : null}
      {warnings ? (
        <span className="rounded-sm bg-warningSoft px-2 py-1 text-xs font-semibold uppercase text-warning">
          {warnings} {warnings === 1 ? 'WARNING' : 'WARNINGS'}
        </span>
      ) : null}
      {!errors && !warnings && showHealthy ? (
        <span className="rounded-sm bg-positiveSoft px-2 py-1 text-xs font-semibold uppercase text-positive">
          HEALTHY
        </span>
      ) : null}
    </span>
  );
}

function RunQualityDiagnosticsCard({ diagnostics }) {
  const [open, setOpen] = useState(false);
  const issues = diagnostics?.issues || [];
  if (!issues.length) return null;
  const hasError = diagnostics.severity === 'error';
  const toneClass = hasError
    ? 'border-negative/60 bg-negativeSoft/80 text-negative'
    : 'border-warning/60 bg-warningSoft/80 text-warning';
  const detailClass = hasError ? 'border-negative/25 bg-white/45' : 'border-warning/25 bg-white/45';
  const Icon = hasError ? XCircle : AlertTriangle;
  return (
    <div className={`overflow-hidden rounded-md border ${toneClass}`}>
      <button className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left" type="button" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <span className="flex min-w-0 items-center gap-3">
          <Icon className="h-5 w-5 shrink-0" />
          <span className="min-w-0">
            <span className="block text-sm font-semibold">{t("Result diagnostics")}</span>
            <span className="mt-1 flex"><DiagnosticCountBadges errorCount={diagnostics.errorCount} warningCount={diagnostics.warningCount} /></span>
          </span>
        </span>
        <CollapseToggleIcon open={open} />
      </button>
      {open ? (
        <div className={`border-t px-4 py-3 ${detailClass}`}>
          <div className="space-y-2">
            {issues.map((issue, index) => (
              <div className="rounded-md border border-line/70 bg-white/55 p-3" key={`${issue.severity}-${issue.title}-${index}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase ${issue.severity === 'error' ? 'bg-negativeSoft text-negative' : 'bg-warningSoft text-warning'}`}>{issue.severity}</span>
                  <span className="text-sm font-semibold text-ink">{issue.title}</span>
                </div>
                {issue.detail ? <div className="mt-1 text-sm text-muted">{issue.detail}</div> : null}
                <RunQualityIssueFix issue={issue} />
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RunQualityIssueFix({ issue }) {
  const fix = runQualityIssueFix(issue);
  if (!fix) return null;
  return (
    <div className="mt-3 rounded-md border border-line bg-white/60 p-3">
      <div className="text-xs font-semibold uppercase text-muted">{t("Suggested fix")}</div>
      <div className="mt-1 text-sm text-ink">{fix.text}</div>
      {fix.command ? <code className="mt-2 block overflow-x-auto whitespace-pre rounded bg-ink px-3 py-2 text-xs text-white">{fix.command}</code> : null}
    </div>
  );
}

function runQualityIssueFix(issue) {
  const title = String(issue?.title || '').toLowerCase();
  if (title.includes('no typed run results') || title.includes('result metadata') || title.includes('legacy inference')) {
    return {
      text: 'Re-upload result artifacts with metadata.result so the Results tab can classify them by domain and role.',
      command: 'bbox run log-series --run-id <run_id> --name equity_curve --data-file equity.json --x date --y series_values --mode nav --result-domain performance --result-name primary_performance --result-role primary_curve --strict-contract --dry-run',
    };
  }
  if (title.includes('missing primary performance curve')) {
    return {
      text: 'Upload one primary performance curve. Use equity_curve for NAV, returns_series for periodic returns, or pnl_series for absolute PnL.',
      command: 'bbox run log-series --run-id <run_id> --name equity_curve --data-file equity.json --x date --y series_values --mode nav --result-domain performance --result-name primary_performance --result-role primary_curve --strict-contract',
    };
  }
  if (title.includes('series_values')) {
    return {
      text: 'Normalize the value column to series_values and set mode to nav, return, or pnl.',
      command: 'bbox run log-series --run-id <run_id> --name equity_curve --data-file equity.json --x date --y series_values --mode nav --result-domain performance --result-name primary_performance --result-role primary_curve --strict-contract --dry-run',
    };
  }
  if (title.includes('preview rows') || title.includes('row count') || title.includes('start') || title.includes('end')) {
    return {
      text: 'Validate against the expected date range and full row count, then re-upload the full artifact content if the series is truncated.',
      command: 'bbox run validate --run-id <run_id> --expected-start <YYYY-MM-DD> --expected-end <YYYY-MM-DD> --expected-rows <n> --primary-series equity_curve --fail-on-warning',
    };
  }
  if (title.includes('mode')) {
    return {
      text: 'Set the series mode explicitly. Use nav for net value levels, return for decimal period returns, and pnl for absolute changes.',
      command: 'bbox run log-series --run-id <run_id> --name pnl_series --data-file pnl.json --x date --y series_values --mode pnl --result-domain performance --result-name primary_performance --result-role primary_curve --strict-contract --dry-run',
    };
  }
  if (title.includes('drawdown')) {
    return {
      text: 'Use drawdown_series with mode=drawdown. For NAV/return runs drawdown values should usually be decimals such as -0.09.',
      command: 'bbox run log-series --run-id <run_id> --name drawdown_series --data-file drawdown.json --x date --y drawdown --mode drawdown --result-domain performance --result-name primary_drawdown --result-role drawdown --strict-contract --dry-run',
    };
  }
  if (title.includes('decimal units') || title.includes('differs from curve')) {
    return {
      text: 'Check summary metrics against the primary curve. Percent metrics in strategy.summary should be percentage points, not decimals.',
      command: 'bbox run log-metric --run-id <run_id> --namespace strategy.summary --values \'{"annual_return":18.5,"max_drawdown":-9.0,"sharpe":1.34}\' --strict-contract --dry-run',
    };
  }
  if (title.includes('x column') || title.includes('date')) {
    return {
      text: 'Declare a date/time x column and keep it non-empty, parseable, sorted, and unique.',
      command: 'bbox run log-series --run-id <run_id> --name equity_curve --data-file equity.json --x date --y series_values --mode nav --strict-contract --dry-run',
    };
  }
  if (title.includes('numeric value')) {
    return {
      text: 'Ensure the declared y column exists and contains finite numeric values.',
      command: 'bbox run log-series --run-id <run_id> --name equity_curve --data-file equity.json --x date --y series_values --mode nav --strict-contract --dry-run',
    };
  }
  return null;
}

function RunWritePanel({ run, data, onRunChanged }) {
  const [activeAction, setActiveAction] = useState('');
  useEffect(() => {
    setActiveAction('');
  }, [run.id]);
  const actions = [
    { id: 'lifecycle', label: 'Lifecycle', icon: CheckCircle2 },
    { id: 'clone', label: 'Clone', icon: GitBranch },
    { id: 'event', label: 'Event', icon: Activity },
    { id: 'metric', label: 'Metric', icon: BarChart3 },
    { id: 'series', label: 'Series', icon: LineChart },
    { id: 'note', label: 'Note', icon: ListTree },
    { id: 'upload', label: 'Upload', icon: FileText },
    { id: 'staged-upload', label: 'Staged Upload', icon: FileText },
    { id: 'external-artifact', label: 'External Artifact', icon: ExternalLink },
    { id: 'code', label: 'Code', icon: GitBranch },
    { id: 'dataset', label: 'Dataset', icon: Database },
    { id: 'environment', label: 'Environment', icon: Database },
    { id: 'advanced-snapshot', label: 'Snapshot JSON', icon: TableProperties },
  ];
  const active = actions.find((item) => item.id === activeAction);
  return (
    <div className="space-y-4">
      <RunMetadataForm run={run} data={data} onRunChanged={onRunChanged} />
      <Panel className="overflow-hidden">
        <PanelHeader
          title="Record"
          action={active ? (
            <button className="secondary-button" type="button" onClick={() => setActiveAction('')}>
              Close
            </button>
          ) : null}
        />
        <div className="border-b border-line p-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            {actions.map(({ id, label, icon: Icon }) => (
              <button
                className={`secondary-button justify-start ${activeAction === id ? 'border-lineStrong bg-white' : ''}`}
                key={id}
                type="button"
                onClick={() => setActiveAction((current) => (current === id ? '' : id))}
              >
                <Icon className="h-4 w-4" />
                <span className="truncate">{label}</span>
              </button>
            ))}
          </div>
        </div>
        {active ? (
          <div className="p-4">
            {activeAction === 'lifecycle' ? <RunStatusActions run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'clone' ? <RunCloneForm run={run} data={data} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'event' ? <EventForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'metric' ? <MetricForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'series' ? <SeriesForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'note' ? <NoteForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'upload' ? <ArtifactUploadForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'staged-upload' ? <StagedArtifactForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'external-artifact' ? <ExternalArtifactForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'code' ? <CodeSnapshotForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'dataset' ? <DatasetSnapshotForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'environment' ? <EnvSnapshotForm run={run} onRunChanged={onRunChanged} /> : null}
            {activeAction === 'advanced-snapshot' ? <SnapshotForm run={run} onRunChanged={onRunChanged} /> : null}
          </div>
        ) : (
          <div className="p-4">
            <div className="max-w-xl">
              <ReadOnlyField label="Current Action" value="none selected" />
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function RunResultsPanel({ chart, resultItems, keyMetrics = [] }) {
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [selectedDataMetric, setSelectedDataMetric] = useState(null);
  const performanceItems = resultItems.filter((item) => item.domain === 'performance');
  const domainGroups = groupRunResultsByDomain(resultItems.filter((item) => item.domain !== 'performance'));
  return (
    <div className="space-y-6 p-4">
      <PerformanceResultsSection
        chart={chart}
        items={performanceItems}
        keyMetrics={keyMetrics}
        onOpenArtifact={setSelectedArtifact}
        onOpenDataMetric={setSelectedDataMetric}
      />
      {domainGroups.length ? domainGroups.map((domainGroup) => (
        <RunResultDomainSection
          domainGroup={domainGroup}
          key={domainGroup.domain}
          onOpenArtifact={setSelectedArtifact}
          onOpenDataMetric={setSelectedDataMetric}
        />
      )) : (
        <div className="rounded-md border border-line bg-white/35 p-5 text-sm text-muted">
          No typed non-performance results yet. Use result metadata for factor, factor batch, diagnostic, or custom artifacts.
        </div>
      )}
      {selectedArtifact ? <ArtifactDetailModal artifact={selectedArtifact} onClose={() => setSelectedArtifact(null)} /> : null}
      {selectedDataMetric ? <MetricDataModal item={selectedDataMetric} onClose={() => setSelectedDataMetric(null)} /> : null}
    </div>
  );
}

function PerformanceResultsSection({ chart, items, keyMetrics, onOpenArtifact, onOpenDataMetric }) {
  const primaryItems = roleItems(items, ['primary_curve']);
  const drawdownItems = roleItems(items, ['drawdown']);
  const summaryItems = roleItems(items, ['summary_table']);
  const used = new Set([...primaryItems, ...drawdownItems, ...summaryItems].map((item) => item.artifact.id));
  const otherItems = (items || []).filter((item) => !used.has(item.artifact.id));
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{t("Performance")}</h3>
          <div className="mt-1 text-xs text-muted">{items.length ? `${items.length} result artifacts · primary curve and drawdown` : 'primary curve and drawdown'}</div>
        </div>
      </div>
      {keyMetrics.length ? (
        <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
          {keyMetrics.map((item) => <StatTile key={item.label} label={item.label} value={item.value} tone={item.tone} />)}
        </div>
      ) : null}
      <div className="rounded-md border border-line bg-white/45 p-4">
        {chart ? (
          <ReactECharts option={runEquityChartOption(chart)} style={{ height: 420 }} />
        ) : <div className="p-8 text-center text-sm font-semibold text-muted">{t("No Series Data Available")}</div>}
      </div>
      {summaryItems.length ? (
        <div className="mt-4">
          <ResultTemplateBlock title="Performance Summary" detail={`${summaryItems.length} summary table${summaryItems.length > 1 ? 's' : ''}`}>
            <RunResultItemsTable items={summaryItems} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
          </ResultTemplateBlock>
        </div>
      ) : null}
      {(primaryItems.length || drawdownItems.length || otherItems.length) ? (
        <div className="mt-4">
          <ResultTemplateBlock title="Performance Artifacts" detail={`${primaryItems.length + drawdownItems.length + otherItems.length} curve or supporting artifact${primaryItems.length + drawdownItems.length + otherItems.length > 1 ? 's' : ''}`}>
            <ResultChartGrid items={otherItems.filter(isResultSeriesChartable)} />
            <RunResultItemsTable items={[...primaryItems, ...drawdownItems, ...otherItems]} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
          </ResultTemplateBlock>
        </div>
      ) : null}
    </section>
  );
}

const defaultResultDomainTemplateRegistry = {
  factor: {
    blocks: [
      { title: 'IC / Cumulative IC', roles: ['ic_curve'], chart: true, detailLabel: 'series result' },
      { title: 'Grouped Returns', roles: ['quantile_returns'], detailLabel: 'table or series result' },
      { title: 'Coverage / Turnover', roles: ['coverage', 'turnover', 'metric_series'], chart: true, detailLabel: 'supporting result' },
    ],
    fallbackTitle: 'Other Factor Results',
  },
  factor_batch: {
    blocks: [
      { title: 'Factor Overlay', roles: ['comparison_curve'], chart: true, detail: 'multi-factor curve comparison' },
      { title: 'Factor Ranking Table', roles: ['comparison_table'], detail: 'key metrics across tested factors' },
    ],
    fallbackTitle: 'Other Batch Results',
  },
  risk: { grouped: true },
  cost: { grouped: true },
  diagnostic: { grouped: true },
};

function RunResultDomainSection({ domainGroup, onOpenArtifact, onOpenDataMetric }) {
  const template = resultDomainTemplateRegistry()[domainGroup.domain];
  if (template?.grouped) {
    return <GroupedResultTemplateSection domainGroup={domainGroup} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />;
  }
  if (template?.blocks) {
    return <ConfiguredResultTemplateSection domainGroup={domainGroup} template={template} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />;
  }
  return (
    <section>
      <ResultTemplateHeader domainGroup={domainGroup} />
      <div className="space-y-3">
        {domainGroup.groups.map((group) => (
          <RunResultGroup
            group={group}
            key={group.key}
            onOpenArtifact={onOpenArtifact}
            onOpenDataMetric={onOpenDataMetric}
          />
        ))}
      </div>
    </section>
  );
}

function resultDomainTemplateRegistry() {
  return mergeResultTemplateRegistries(defaultResultDomainTemplateRegistry, runtimeResultTemplateRegistry());
}

function runtimeResultTemplateRegistry() {
  const fromWindow = typeof window !== 'undefined' && window.BLACKBOX_RESULT_TEMPLATES && typeof window.BLACKBOX_RESULT_TEMPLATES === 'object'
    ? window.BLACKBOX_RESULT_TEMPLATES
    : {};
  let fromStorage = {};
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      const raw = window.localStorage.getItem('blackbox.resultTemplates');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) fromStorage = parsed;
      }
    } catch {
      fromStorage = {};
    }
  }
  return mergeResultTemplateRegistries(fromWindow, fromStorage);
}

function mergeResultTemplateRegistries(base, override) {
  const merged = { ...(base || {}) };
  for (const [domain, template] of Object.entries(override || {})) {
    if (!template || typeof template !== 'object' || Array.isArray(template)) continue;
    const existing = merged[domain] || {};
    merged[domain] = {
      ...existing,
      ...template,
      blocks: Array.isArray(template.blocks) ? template.blocks : existing.blocks,
    };
  }
  return merged;
}

function ConfiguredResultTemplateSection({ domainGroup, template, onOpenArtifact, onOpenDataMetric }) {
  const items = domainGroupItems(domainGroup);
  const used = new Set();
  const blocks = (template.blocks || [])
    .map((block) => {
      const blockItems = roleItems(items, block.roles || []);
      for (const item of blockItems) used.add(item.artifact.id);
      return { ...block, items: blockItems };
    })
    .filter((block) => block.items.length);
  const otherItems = items.filter((item) => !used.has(item.artifact.id));
  return (
    <section>
      <ResultTemplateHeader domainGroup={domainGroup} />
      <div className="space-y-4">
        {blocks.map((block) => (
          <ResultTemplateBlock key={block.title} title={block.title} detail={block.detail || resultTemplateBlockDetail(block.items, block.detailLabel)}>
            {block.chart ? <ResultChartGrid items={block.items} /> : null}
            <RunResultItemsTable items={block.items} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
          </ResultTemplateBlock>
        ))}
        {otherItems.length ? (
          <ResultTemplateBlock title={template.fallbackTitle || 'Other Results'} detail={resultTemplateBlockDetail(otherItems, 'result artifact')}>
            <ResultChartGrid items={otherItems.filter(isResultSeriesChartable)} />
            <RunResultItemsTable items={otherItems} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
          </ResultTemplateBlock>
        ) : null}
      </div>
    </section>
  );
}

function GroupedResultTemplateSection({ domainGroup, onOpenArtifact, onOpenDataMetric }) {
  return (
    <section>
      <ResultTemplateHeader domainGroup={domainGroup} />
      <div className="space-y-3">
        {domainGroup.groups.map((group) => (
          <ResultTemplateBlock detail={`${group.items.length} result artifact${group.items.length > 1 ? 's' : ''}`} key={group.key} title={group.title}>
            <ResultChartGrid items={group.items.filter(isResultSeriesChartable)} />
            <RunResultItemsTable items={group.items} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
          </ResultTemplateBlock>
        ))}
      </div>
    </section>
  );
}

function resultTemplateBlockDetail(items, label = 'result artifact') {
  return `${items.length} ${label}${items.length > 1 ? 's' : ''}`;
}

function RunResultGroup({ group, onOpenArtifact, onOpenDataMetric }) {
  const chartItems = group.items.filter(isResultSeriesChartable).slice(0, 2);
  return (
    <div className="rounded-md border border-line bg-white/45">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-ink">{group.title}</div>
          <div className="mt-1 text-xs text-muted">{group.items.length} artifacts</div>
        </div>
      </div>
      <ResultChartGrid bordered items={chartItems} />
      <RunResultItemsTable items={group.items} onOpenArtifact={onOpenArtifact} onOpenDataMetric={onOpenDataMetric} />
    </div>
  );
}

function ResultTemplateHeader({ domainGroup }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h3 className="text-sm font-semibold text-ink">{resultDomainLabel(domainGroup.domain)}</h3>
        <div className="mt-1 text-xs text-muted">{domainGroup.itemCount} result artifacts · {domainGroup.groups.length} groups</div>
      </div>
    </div>
  );
}

function ResultTemplateBlock({ title, detail, children }) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-white/45">
      <div className="border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink">{title}</div>
        {detail ? <div className="mt-1 text-xs text-muted">{detail}</div> : null}
      </div>
      <div className="space-y-3 p-4">{children}</div>
    </div>
  );
}

function ResultChartGrid({ items, bordered = false }) {
  const chartItems = (items || []).filter(isResultSeriesChartable).slice(0, 4);
  if (!chartItems.length) return null;
  return (
    <div className={`grid gap-3 ${bordered ? 'border-b border-line p-4' : ''} ${chartItems.length > 1 ? 'xl:grid-cols-2' : ''}`}>
      {chartItems.map((item) => (
        <div className="min-w-0 rounded-md border border-line bg-white/45 p-3" key={`chart-${item.artifact.id}`}>
          <div className="mb-2 truncate text-xs font-semibold text-muted">{item.title}</div>
          <ReactECharts option={resultSeriesChartOption(item)} style={{ height: 360 }} />
        </div>
      ))}
    </div>
  );
}

function RunResultItemsTable({ items, onOpenArtifact, onOpenDataMetric }) {
  if (!(items || []).length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse">
        <thead className="table-head">
          <tr><th className="px-4 py-3">{t("Result")}</th><th className="px-4 py-3">{t("Role")}</th><th className="px-4 py-3">{t("Artifact")}</th><th className="px-4 py-3">{t("Abstract")}</th><th className="px-4 py-3 text-right">{t("Actions")}</th></tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr className="hover:bg-white/45" key={item.artifact.id}>
              <td className="table-cell">
                <div className="font-semibold text-ink">{item.title}</div>
                <div className="mt-1 text-xs text-muted">{item.result.name || item.artifact.name}</div>
              </td>
              <td className="table-cell text-muted">{resultRoleLabel(item.role)}</td>
              <td className="table-cell text-muted">{item.artifact.name} · {item.artifact.kind}</td>
              <td className="table-cell max-w-[420px] text-muted"><ArtifactPreviewSummary preview={item.artifact.preview_json || {}} /></td>
              <td className="table-cell">
                <div className="flex justify-end gap-2">
                  <button className="icon-button" type="button" onClick={() => onOpenDataMetric(resultMetricModalItem(item))} aria-label={`View result ${item.title}`} title={resultViewAction(item).title}>
                    {React.createElement(resultViewAction(item).icon, { className: 'h-4 w-4' })}
                  </button>
                  <button className="icon-button" type="button" onClick={() => onOpenArtifact(item.artifact)} aria-label={`View artifact ${item.artifact.name}`} title="View artifact">
                    <FileText className="h-4 w-4" />
                  </button>
                  <a className="icon-button" href={artifactContentUrl(item.artifact.id)} target="_blank" rel="noreferrer" title="Open artifact">
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function domainGroupItems(domainGroup) {
  return (domainGroup.groups || []).flatMap((group) => group.items || []);
}

function roleItems(items, roles) {
  const accepted = new Set(roles);
  return (items || []).filter((item) => accepted.has(item.role));
}

function resultViewAction(item) {
  if (isImageArtifact(item.artifact, item.artifact.preview_json || {})) return { icon: ImageIcon, title: 'View image' };
  if (isSeriesResultItem(item, item.artifact)) return { icon: LineChart, title: 'View series data' };
  return { icon: TableProperties, title: 'View table data' };
}

function resultMetricModalItem(item) {
  const metadata = item.artifact.metadata_json || {};
  const metric = metadata.metric && typeof metadata.metric === 'object' ? metadata.metric : null;
  const series = metadata.series && typeof metadata.series === 'object' ? metadata.series : null;
  return {
    id: `result-${item.artifact.id}`,
    namespace: metric?.namespace || series?.namespace || item.domain,
    key: metric?.key || item.result.name || item.artifact.name,
    artifact: item.artifact,
    metricBinding: metric,
    seriesBinding: series,
    result: item.result,
    resultRole: item.role,
    resultDomain: item.domain,
  };
}

function isResultSeriesChartable(item) {
  const metadata = item.artifact.metadata_json || {};
  const series = metadata.series && typeof metadata.series === 'object' ? metadata.series : null;
  const rows = Array.isArray(item.artifact.preview_json?.rows) ? item.artifact.preview_json.rows : [];
  if (!series || !rows.length) return false;
  const yKeys = Array.isArray(series.y) ? series.y : [series.y || 'series_values'].filter(Boolean);
  return yKeys.some((key) => rows.some((row) => Number.isFinite(toNumber(row?.[key]))));
}

function isSeriesResultItem(item, artifact = item?.artifact) {
  const role = String(item?.role || item?.resultRole || item?.result?.role || '').toLowerCase();
  const metricKind = String(item?.metricBinding?.kind || item?.result?.metric?.kind || '').toLowerCase();
  if (role.includes('table') || role === 'quantile_returns' || role === 'report') return false;
  if (role.includes('series')
    || role.includes('curve')
    || role === 'drawdown'
    || role === 'primary_curve'
    || role === 'ic_curve'
    || role === 'comparison_curve') return true;
  if (metricKind === 'series') return true;
  return Boolean(item?.seriesBinding) && hasNumericSeriesRows(item.seriesBinding, artifact);
}

function hasNumericSeriesRows(series, artifact) {
  const rows = Array.isArray(artifact?.preview_json?.rows) ? artifact.preview_json.rows : [];
  if (!series || !rows.length) return false;
  const yKeys = Array.isArray(series.y) ? series.y : [series.y || 'series_values'].filter(Boolean);
  return yKeys.some((key) => rows.some((row) => Number.isFinite(toNumber(row?.[key]))));
}

function resultSeriesChartOption(item) {
  const metadata = item.artifact.metadata_json || {};
  const seriesMeta = metadata.series || {};
  const rows = Array.isArray(item.artifact.preview_json?.rows) ? item.artifact.preview_json.rows : [];
  const yKeys = (Array.isArray(seriesMeta.y) ? seriesMeta.y : [seriesMeta.y || 'series_values'])
    .filter((key) => rows.some((row) => Number.isFinite(toNumber(row?.[key]))))
    .slice(0, 6);
  const seriesItem = {
    name: seriesMeta.name || item.artifact.name,
    mode: seriesMeta.mode || null,
    namespace: seriesMeta.namespace || null,
    rows,
  };
  return {
    animation: false,
    color: ['#111111', '#2563eb', '#16a34a', '#f97316', '#7c3aed', '#dc2626'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, left: 0, right: 8, type: 'scroll', textStyle: { color: '#6b7280' } },
    grid: { top: 42, left: 44, right: 12, bottom: 34 },
    xAxis: { type: 'category', boundaryGap: false, axisLabel: { color: '#6b7280', hideOverlap: true } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
    series: yKeys.map((key) => ({
      name: key,
      type: 'line',
      showSymbol: false,
      smooth: false,
      data: seriesPreviewData(seriesItem.name, { ...seriesItem, y: yKeys }, key, seriesMeta.x),
    })),
  };
}

function RunPrimaryChart({ chart }) {
  return (
    <Panel className="overflow-hidden">
      <div className="p-4">
        {chart ? (
          <ReactECharts option={runEquityChartOption(chart)} style={{ height: 420 }} />
        ) : <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No Series Data Available")}</div>}
      </div>
    </Panel>
  );
}

function RunTabs({ activeTab, setActiveTab, resultItems, keyMetrics, equityChart, metrics, events, artifacts, run, notes }) {
  const tabs = [
    { id: 'results', label: 'Results', icon: LineChart },
    { id: 'metrics', label: 'Metrics', icon: BarChart3 },
    { id: 'events', label: 'Events', icon: Activity },
    { id: 'artifacts', label: 'Artifacts', icon: FileText },
    { id: 'config', label: 'Config', icon: GitBranch },
    { id: 'snapshots', label: 'Context', icon: Database },
    { id: 'notes', label: 'Notes', icon: ListTree },
  ];
  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-wrap gap-2 border-b border-line p-3">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${activeTab === id ? 'bg-white text-ink shadow-insetLine' : 'text-muted hover:bg-white/55 hover:text-ink'}`}
            key={id}
            onClick={() => setActiveTab(id)}
          >
            <Icon className="h-4 w-4" />{label}
          </button>
        ))}
      </div>
      {activeTab === 'results' && <RunResultsPanel chart={equityChart} resultItems={resultItems || []} keyMetrics={keyMetrics || []} />}
      {activeTab === 'metrics' && <MetricsPanel metrics={metrics} artifacts={artifacts} />}
      {activeTab === 'events' && <EventsPanel events={events} />}
      {activeTab === 'artifacts' && <ArtifactsPanel artifacts={artifacts} />}
      {activeTab === 'config' && <RunConfigPanel run={run} />}
      {activeTab === 'snapshots' && <SnapshotsDetailPanel snapshots={run.snapshots} />}
      {activeTab === 'notes' && <NotesPanel notes={notes} />}
    </Panel>
  );
}

function MetricsPanel({ metrics, artifacts }) {
  const rows = useMemo(() => metricDisplayRows(metrics, artifacts), [metrics, artifacts]);
  const namespaces = Array.from(new Set(rows.map((row) => row.namespace || 'default'))).sort();
  const [namespace, setNamespace] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedDataMetric, setSelectedDataMetric] = useState(null);
  useEffect(() => {
    if (namespace !== 'all' && !namespaces.includes(namespace)) setNamespace('all');
  }, [namespace, namespaces.join('|')]);
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = rows.filter((row) => {
    if (namespace !== 'all' && (row.namespace || 'default') !== namespace) return false;
    if (!normalizedQuery) return true;
    return row.searchText.includes(normalizedQuery);
  });
  return (
    <div>
      <PanelHeader title="Metrics" icon={BarChart3} />
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 sm:grid-cols-[220px_minmax(260px,1fr)]">
          <Field label="Namespace">
            <SelectInput value={namespace} onChange={(event) => setNamespace(event.target.value)}>
              <option value="all">{t("All namespaces")}</option>
              {namespaces.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <Field label="Search metrics">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="key, value, point, artifact" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">
          {filtered.length} shown · {rows.length} total · {namespaces.length} namespaces
        </div>
      </div>
      <MetricsTable rows={filtered} onOpenDataMetric={setSelectedDataMetric} />
      {selectedDataMetric ? <MetricDataModal item={selectedDataMetric} onClose={() => setSelectedDataMetric(null)} /> : null}
    </div>
  );
}

function ArtifactsPanel({ artifacts }) {
  return (
    <div>
      <PanelHeader title="Artifacts" icon={FileText} />
      <ArtifactList artifacts={artifacts} />
    </div>
  );
}

function RunConfigPanel({ run }) {
  const sourceDiff = run.source_config_diff || [];
  return (
    <div>
      <PanelHeader title="Config" icon={GitBranch} />
      <div className="grid gap-4 p-4 xl:grid-cols-2">
        <ReadOnlyField label="Current Config" value={configSummary(run.config_json || {})} code />
        <ReadOnlyField label="Context" value={configSummary(run.context_json || {})} code />
      </div>
      <SourceConfigDiffPanel sourceRun={run.source_run} rows={sourceDiff} />
    </div>
  );
}

function SourceConfigDiffPanel({ sourceRun, rows }) {
  return (
    <div className="border-t border-line">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <div className="text-xs font-semibold uppercase text-muted">{t('Source run diff')}</div>
          <div className="mt-1 text-sm text-ink">{sourceRun ? `${sourceRun.name} (${sourceRun.id})` : 'No source run'}</div>
        </div>
      </div>
      {sourceRun ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead className="table-head">
              <tr><th className="px-4 py-3">{t("Path")}</th><th className="px-4 py-3">{t("Source")}</th><th className="px-4 py-3">{t("Current")}</th></tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((row) => (
                <tr className="hover:bg-white/45" key={row.path}>
                  <td className="table-cell font-semibold text-ink">{row.path}</td>
                  <td className="table-cell text-muted">{formatConfigValue(row.before)}</td>
                  <td className="table-cell text-muted">{formatConfigValue(row.after)}</td>
                </tr>
              )) : <tr><td className="table-cell text-muted" colSpan="3">{t("Current config matches the source run.")}</td></tr>}
            </tbody>
          </table>
        </div>
      ) : <div className="px-5 pb-5 text-sm text-muted">{t("This run was not cloned from another run.")}</div>}
    </div>
  );
}

function RunMetadataForm({ run, data, onRunChanged }) {
  const [form, setForm] = useState({
    name: run.name || '',
    title: run.title || '',
    source_run_id: run.source_run_id || '',
    tags: (run.tags || []).join(','),
    config: JSON.stringify(run.config_json || {}),
    context: JSON.stringify(run.context_json || {}),
  });
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const terminal = ['completed', 'failed', 'cancelled'].includes(run.status);
  useEffect(() => {
    setForm({
      name: run.name || '',
      title: run.title || '',
      source_run_id: run.source_run_id || '',
      tags: (run.tags || []).join(','),
      config: JSON.stringify(run.config_json || {}),
      context: JSON.stringify(run.context_json || {}),
    });
    setEditing(false);
    setError(null);
  }, [run.id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: form.name,
        title: form.title,
        source_run_id: form.source_run_id || null,
        tags: parseCsv(form.tags),
        context: parseJsonObject(form.context),
      };
      if (!terminal) payload.config = parseJsonObject(form.config);
      await apiPatch(`/api/v1/runs/${run.id}`, payload);
      await onRunChanged(run.id);
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Metadata" icon={LineChart} action={<EditPanelAction editing={editing} onEdit={() => setEditing(true)} label="Edit run metadata" />} />
      {editing ? (
        <form className="space-y-2 p-4" onSubmit={submit}>
          <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} /></Field>
          <Field label="Title"><TextInput value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
          <Field label="Source run">
            <SelectInput value={form.source_run_id} onChange={(event) => update('source_run_id', event.target.value)}>
              <option value="">{t("None")}</option>
              {(data?.runs || []).filter((item) => item.id !== run.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </SelectInput>
          </Field>
          <Field label="Tags"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} /></Field>
          <Field label="Config JSON"><TextArea disabled={terminal} value={form.config} onChange={(event) => update('config', event.target.value)} /></Field>
          <Field label="Context JSON"><TextArea value={form.context} onChange={(event) => update('context', event.target.value)} /></Field>
          {terminal ? <div className="text-xs text-muted">{t("Config is locked after a run reaches a terminal status; title and tags remain editable.")}</div> : null}
          <InlineError message={error} />
          <div className="flex items-center gap-2">
            <button className="secondary-button mt-2 w-full" type="button" onClick={() => setEditing(false)}>{t("Cancel")}</button>
            <SubmitButton loading={loading}>Update run</SubmitButton>
          </div>
        </form>
      ) : (
        <div className="space-y-3 p-4">
          <ReadOnlyField label="Name" value={run.name} />
          <ReadOnlyField label="Title" value={run.title} />
          <ReadOnlyField label="Source run" value={run.source_run?.name || run.source_run_id} />
          <ReadOnlyField label="Creator" value={runCreator(run)} />
          <ReadOnlyField label="Tags" value={(run.tags || []).join(', ')} />
          <ReadOnlyField label="Config" value={configSummary(run.config_json || {})} code />
          <ReadOnlyField label="Context" value={configSummary(run.context_json || {})} code />
        </div>
      )}
    </Panel>
  );
}

function RunCloneForm({ run, data, onRunChanged }) {
  const [form, setForm] = useState({ branch_id: run.branch_id || '', name: `${run.name}_clone`, title: run.title || '', config_overrides: '{}', context_overrides: '{}', tags: '', created_by_type: run.created_by_type || 'human', created_by_id: run.created_by_id || '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setForm({ branch_id: run.branch_id || '', name: `${run.name}_clone`, title: run.title || '', config_overrides: '{}', context_overrides: '{}', tags: '', created_by_type: run.created_by_type || 'human', created_by_id: run.created_by_id || '' });
  }, [run.id, run.name, run.branch_id, run.title, run.created_by_type, run.created_by_id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tags = parseCsv(form.tags);
      const cloned = await apiPost(`/api/v1/runs/${run.id}/clone`, compactObject({
        branch_id: form.branch_id,
        name: form.name,
        title: form.title,
        config_overrides: parseJsonObject(form.config_overrides),
        context_overrides: parseJsonObject(form.context_overrides),
        tags: tags.length ? tags : null,
        created_by_type: form.created_by_type || 'human',
        created_by_id: form.created_by_id || null,
      }));
      await onRunChanged(cloned.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Clone">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Target branch">
          <SelectInput value={form.branch_id} onChange={(event) => update('branch_id', event.target.value)}>
            {(data?.branches || [{ id: run.branch_id, key: run.branch_key || run.branch_id }]).map((branch) => <option key={branch.id} value={branch.id}>{branch.key}</option>)}
          </SelectInput>
        </Field>
        <Field label="New name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} /></Field>
        <Field label="Title"><TextInput value={form.title} onChange={(event) => update('title', event.target.value)} /></Field>
        <Field label="Tags override"><TextInput value={form.tags} onChange={(event) => update('tags', event.target.value)} placeholder="empty = inherit source tags" /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Creator">
            <SelectInput value={form.created_by_type} onChange={(event) => update('created_by_type', event.target.value)}>
              <option value="human">human</option>
              <option value="agent">agent</option>
              <option value="system">system</option>
            </SelectInput>
          </Field>
          <Field label="Creator ID"><TextInput value={form.created_by_id} onChange={(event) => update('created_by_id', event.target.value)} placeholder="agent-alpha" /></Field>
        </div>
        <Field label="Config overrides"><TextArea value={form.config_overrides} onChange={(event) => update('config_overrides', event.target.value)} /></Field>
        <Field label="Context overrides"><TextArea value={form.context_overrides} onChange={(event) => update('context_overrides', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Clone run</SubmitButton>
      </form>
    </FormCard>
  );
}

function RunStatusActions({ run, onRunChanged }) {
  const [form, setForm] = useState({
    fail_code: 'RUN_FAILED',
    fail_message: 'failed from WebUI',
    fail_details: '{}',
    cancel_reason: 'cancelled from WebUI',
    cancel_details: '{}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const terminal = ['completed', 'failed', 'cancelled'].includes(run.status);
  useEffect(() => {
    setForm({
      fail_code: 'RUN_FAILED',
      fail_message: 'failed from WebUI',
      fail_details: '{}',
      cancel_reason: 'cancelled from WebUI',
      cancel_details: '{}',
    });
    setError(null);
  }, [run.id]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (path, body) => {
    setLoading(true);
    setError(null);
    try {
      await apiPost(path, body);
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  const failRun = () => {
    try {
      submit(`/api/v1/runs/${run.id}/fail`, compactObject({
        code: form.fail_code,
        message: form.fail_message,
        details: parseJsonObject(form.fail_details),
      }));
    } catch (err) {
      setError(err.message);
    }
  };
  const cancelRun = () => {
    try {
      submit(`/api/v1/runs/${run.id}/cancel`, compactObject({
        reason: form.cancel_reason,
        details: parseJsonObject(form.cancel_details),
      }));
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <FormCard title="Lifecycle">
      <div className="space-y-2">
        <div className="text-sm text-muted">{t('Current status')}: <span className="font-semibold text-ink">{tStatus(run.status)}</span></div>
        <button className="primary-button w-full" disabled={loading || terminal} onClick={() => submit(`/api/v1/runs/${run.id}/finish`)}>
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          {t('Finish')}
        </button>
        <Field label="Error code"><TextInput disabled={terminal} value={form.fail_code} onChange={(event) => update('fail_code', event.target.value)} /></Field>
        <Field label="Error message"><TextInput disabled={terminal} value={form.fail_message} onChange={(event) => update('fail_message', event.target.value)} /></Field>
        <Field label="Error details JSON"><TextArea disabled={terminal} value={form.fail_details} onChange={(event) => update('fail_details', event.target.value)} /></Field>
        <button
          className="secondary-button w-full border-negativeSoft text-negative hover:border-negative"
          disabled={loading || terminal}
          onClick={failRun}
        >
          <XCircle className="h-4 w-4" />
          {t('Mark failed')}
        </button>
        <Field label="Cancel reason"><TextInput disabled={terminal} value={form.cancel_reason} onChange={(event) => update('cancel_reason', event.target.value)} /></Field>
        <Field label="Cancel details JSON"><TextArea disabled={terminal} value={form.cancel_details} onChange={(event) => update('cancel_details', event.target.value)} /></Field>
        <button
          className="secondary-button w-full"
          disabled={loading || terminal}
          onClick={cancelRun}
        >
          <XCircle className="h-4 w-4" />
          {t('Cancel')}
        </button>
        <InlineError message={error || (terminal ? 'Terminal runs cannot be changed.' : null)} />
      </div>
    </FormCard>
  );
}

function EventForm({ run, onRunChanged }) {
  const [form, setForm] = useState({
    event_type: 'stage_completed',
    stage: 'stage_completed',
    payload: '{"source":"webui"}',
    client_event_id: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/events`, {
        event_type: form.event_type,
        stage: form.stage || null,
        payload: parseJsonObject(form.payload),
        client_event_id: form.client_event_id || null,
      });
      setForm((current) => ({ ...current, stage: '', payload: '{"source":"webui"}', client_event_id: '' }));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Event">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Type">
          <SelectInput value={form.event_type} onChange={(event) => update('event_type', event.target.value)}>
            <option value="stage_completed">stage_completed</option>
            <option value="run_started">run_started</option>
            <option value="artifact_uploaded">artifact_uploaded</option>
            <option value="run_finished">run_finished</option>
            <option value="run_failed">run_failed</option>
            <option value="run_cancelled">run_cancelled</option>
            <option value="note_added">note_added</option>
          </SelectInput>
        </Field>
        <Field label="Stage"><TextInput value={form.stage} onChange={(event) => update('stage', event.target.value)} placeholder="data_loaded" /></Field>
        <Field label="Payload JSON"><TextArea value={form.payload} onChange={(event) => update('payload', event.target.value)} /></Field>
        <Field label="Client event ID"><TextInput value={form.client_event_id} onChange={(event) => update('client_event_id', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Log event</SubmitButton>
      </form>
    </FormCard>
  );
}

function MetricForm({ run, onRunChanged }) {
  const [form, setForm] = useState({ namespace: 'strategy.summary', key: '', value: '', point: '{"kind":"summary"}', client_event_id: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/metrics`, {
        namespace: form.namespace,
        values: { [form.key]: parseJsonScalar(form.value) },
        point: parseJsonObject(form.point),
        client_event_id: form.client_event_id || null,
      });
      setForm((current) => ({ ...current, key: '', value: '', client_event_id: '' }));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Metric">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Namespace"><TextInput required value={form.namespace} onChange={(event) => update('namespace', event.target.value)} /></Field>
        <Field label="Key"><TextInput required value={form.key} onChange={(event) => update('key', event.target.value)} placeholder="sharpe" /></Field>
        <Field label="Value"><TextInput required value={form.value} onChange={(event) => update('value', event.target.value)} placeholder="1.42" /></Field>
        <Field label="Point JSON"><TextInput required value={form.point} onChange={(event) => update('point', event.target.value)} /></Field>
        <Field label="Client event ID"><TextInput value={form.client_event_id} onChange={(event) => update('client_event_id', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Log metric</SubmitButton>
      </form>
    </FormCard>
  );
}

function SeriesForm({ run, onRunChanged }) {
  const [form, setForm] = useState({
    name: 'returns',
    data: '[{"date":"2026-01-01","series_values":0.01}]',
    x: 'date',
    y: 'series_values',
    mode: 'return',
    namespace: '',
    metric_key: '',
    metric_namespace: '',
    metric_kind: 'series',
    kind: 'table_csv',
    filename: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/series`, {
        name: form.name,
        data: parseJsonArray(form.data),
        x: form.x || null,
        y: parseCsv(form.y),
        mode: form.mode || null,
        namespace: form.namespace || null,
        metric: form.metric_key ? {
          namespace: form.metric_namespace || form.namespace || 'default',
          key: form.metric_key,
          kind: form.metric_kind || 'series',
          x: form.x || null,
          y: parseCsv(form.y),
          mode: form.mode || null,
        } : null,
        kind: form.kind || 'table_csv',
        filename: form.filename || null,
      });
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Series">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} /></Field>
        <Field label="Rows JSON"><TextArea required value={form.data} onChange={(event) => update('data', event.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="X"><TextInput value={form.x} onChange={(event) => update('x', event.target.value)} /></Field>
          <Field label="Value column"><TextInput value={form.y} onChange={(event) => update('y', event.target.value)} placeholder="series_values" /></Field>
        </div>
        <Field label="Mode">
          <SelectInput value={form.mode} onChange={(event) => update('mode', event.target.value)}>
            <option value="nav">nav</option>
            <option value="return">return</option>
            <option value="pnl">pnl</option>
            <option value="drawdown">drawdown</option>
            <option value="level">level</option>
          </SelectInput>
        </Field>
        <Field label="Namespace"><TextInput value={form.namespace} onChange={(event) => update('namespace', event.target.value)} placeholder="strategy.returns" /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Metric key"><TextInput value={form.metric_key} onChange={(event) => update('metric_key', event.target.value)} placeholder="optional" /></Field>
          <Field label="Metric namespace"><TextInput value={form.metric_namespace} onChange={(event) => update('metric_namespace', event.target.value)} placeholder="defaults to namespace" /></Field>
        </div>
        <Field label="Metric data type">
          <SelectInput value={form.metric_kind} onChange={(event) => update('metric_kind', event.target.value)}>
            <option value="series">series</option>
            <option value="table">table</option>
          </SelectInput>
        </Field>
        <Field label="Kind">
          <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
            <option value="table_csv">table_csv</option>
            <option value="table_parquet">table_parquet</option>
            <option value="returns_series_parquet">returns_series_parquet</option>
            <option value="factor_values_parquet">factor_values_parquet</option>
            <option value="position_log_parquet">position_log_parquet</option>
            <option value="trade_log_parquet">trade_log_parquet</option>
          </SelectInput>
        </Field>
        <Field label="Filename"><TextInput value={form.filename} onChange={(event) => update('filename', event.target.value)} placeholder="auto by kind" /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Log series</SubmitButton>
      </form>
    </FormCard>
  );
}

function NoteForm({ run, onRunChanged }) {
  const [form, setForm] = useState({ kind: 'observation', author_type: 'human', summary: '', content: '', structured: '{}', client_event_id: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/notes`, {
        kind: form.kind,
        summary: form.summary,
        content: form.content || null,
        structured: parseJsonObject(form.structured),
        author_type: form.author_type || 'human',
        client_event_id: form.client_event_id || null,
      });
      setForm((current) => ({ ...current, summary: '', content: '', structured: '{}', client_event_id: '' }));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Note">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Kind">
          <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
            <option value="hypothesis">hypothesis</option>
            <option value="observation">observation</option>
            <option value="anomaly">anomaly</option>
            <option value="decision">decision</option>
            <option value="todo">todo</option>
            <option value="review">review</option>
          </SelectInput>
        </Field>
        <Field label="Author">
          <SelectInput value={form.author_type} onChange={(event) => update('author_type', event.target.value)}>
            <option value="human">human</option>
            <option value="agent">agent</option>
            <option value="system">system</option>
          </SelectInput>
        </Field>
        <Field label="Summary"><TextInput required value={form.summary} onChange={(event) => update('summary', event.target.value)} /></Field>
        <Field label="Content"><TextArea value={form.content} onChange={(event) => update('content', event.target.value)} /></Field>
        <Field label="Structured JSON"><TextArea value={form.structured} onChange={(event) => update('structured', event.target.value)} /></Field>
        <Field label="Client event ID"><TextInput value={form.client_event_id} onChange={(event) => update('client_event_id', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Add note</SubmitButton>
      </form>
    </FormCard>
  );
}

function ArtifactUploadForm({ run, onRunChanged }) {
  const [form, setForm] = useState({ name: '', kind: 'other', metadata: '{}' });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (!file) {
      setError('Choose a file to upload.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const metadata = parseJsonObject(form.metadata);
      await apiUpload(`/api/v1/runs/${run.id}/artifacts/upload`, file, {
        name: form.name || file.name,
        kind: form.kind || 'other',
        filename: file.name,
        metadata: JSON.stringify(metadata),
      });
      setForm({ name: '', kind: 'other', metadata: '{}' });
      setFile(null);
      formElement.reset();
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Upload Artifact">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="File">
          <input className="form-control" type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </Field>
        <Field label="Name"><TextInput value={form.name} onChange={(event) => update('name', event.target.value)} placeholder={file?.name || 'artifact name'} /></Field>
        <Field label="Kind">
          <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
            {artifactKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
          </SelectInput>
        </Field>
        <Field label="Metadata JSON"><TextArea value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Upload artifact</SubmitButton>
      </form>
    </FormCard>
  );
}

function StagedArtifactForm({ run, onRunChanged }) {
  const [form, setForm] = useState({ name: '', kind: 'other', filename: '', preview: '{}', metadata: '{}' });
  const [file, setFile] = useState(null);
  const [target, setTarget] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const effectiveName = () => form.name || file?.name || form.filename || 'artifact';
  const effectiveFilename = () => form.filename || file?.name || 'artifact.bin';
  const initUpload = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const uploadTarget = await apiPost(`/api/v1/runs/${run.id}/artifacts/init-upload`, {
        name: effectiveName(),
        kind: form.kind || 'other',
        filename: effectiveFilename(),
        metadata: parseJsonObject(form.metadata),
      });
      setTarget(uploadTarget);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  const completeUpload = async () => {
    if (!target) {
      setError('Initialize the upload first.');
      return;
    }
    if (!file) {
      setError('Choose a file before uploading.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (target.upload_path) {
        await apiUpload(target.upload_path, file);
      } else if (target.upload_url) {
        const response = await fetch(target.upload_url, {
          method: target.method || 'PUT',
          headers: target.headers || {},
          body: file,
        });
        if (!response.ok) throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
        await apiPost(`/api/v1/runs/${run.id}/artifacts/complete-upload`, {
          artifact_id: target.artifact_id,
          name: effectiveName(),
          kind: form.kind || 'other',
          uri: target.storage_uri,
          filename: effectiveFilename(),
          mime_type: file.type || null,
          size_bytes: file.size,
          sha256: await fileSha256(file),
          preview: parseJsonObject(form.preview),
          metadata: parseJsonObject(form.metadata),
        });
      } else {
        throw new Error('Upload target did not include an upload path or URL.');
      }
      setForm({ name: '', kind: 'other', filename: '', preview: '{}', metadata: '{}' });
      setFile(null);
      setTarget(null);
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Staged Artifact">
      <form className="space-y-2" onSubmit={initUpload}>
        <Field label="File">
          <input className="form-control" type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </Field>
        <Field label="Name"><TextInput value={form.name} onChange={(event) => update('name', event.target.value)} placeholder={file?.name || 'artifact name'} /></Field>
        <Field label="Kind">
          <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
            {artifactKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
          </SelectInput>
        </Field>
        <Field label="Filename"><TextInput value={form.filename} onChange={(event) => update('filename', event.target.value)} placeholder={file?.name || 'artifact.bin'} /></Field>
        <Field label="Preview JSON"><TextArea value={form.preview} onChange={(event) => update('preview', event.target.value)} /></Field>
        <Field label="Metadata JSON"><TextArea value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        {target ? (
          <div className="space-y-2 rounded-md border border-line bg-white/50 p-3">
            <ReadOnlyField label="Artifact ID" value={target.artifact_id} />
            <ReadOnlyField label="Target" value={target.upload_path || target.storage_uri || target.upload_url} />
          </div>
        ) : null}
        <InlineError message={error} />
        <SubmitButton loading={loading}>{target ? 'Refresh target' : 'Init upload'}</SubmitButton>
        <button className="secondary-button w-full" disabled={loading || !target} type="button" onClick={completeUpload}>{t("Upload and complete")}</button>
      </form>
    </FormCard>
  );
}

function ExternalArtifactForm({ run, onRunChanged }) {
  const [form, setForm] = useState({ name: '', uri: '', kind: 'other', filename: '', mime_type: '', size_bytes: '', sha256: '', preview: '{}', metadata: '{}' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/artifacts/register-external`, {
        name: form.name,
        uri: form.uri,
        kind: form.kind || 'other',
        filename: form.filename || null,
        mime_type: form.mime_type || null,
        size_bytes: form.size_bytes ? Number(form.size_bytes) : null,
        sha256: form.sha256 || null,
        preview: parseJsonObject(form.preview),
        metadata: parseJsonObject(form.metadata),
      });
      setForm((current) => ({ ...current, name: '', uri: '', filename: '', mime_type: '', size_bytes: '', sha256: '', preview: '{}', metadata: '{}' }));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="External Artifact">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Name"><TextInput required value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="post_cost_report" /></Field>
        <Field label="URI"><TextInput required value={form.uri} onChange={(event) => update('uri', event.target.value)} placeholder="s3://bucket/report.html" /></Field>
        <Field label="Kind">
          <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
            {artifactKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
          </SelectInput>
        </Field>
        <Field label="Filename"><TextInput value={form.filename} onChange={(event) => update('filename', event.target.value)} placeholder="report.html" /></Field>
        <Field label="MIME type"><TextInput value={form.mime_type} onChange={(event) => update('mime_type', event.target.value)} placeholder="text/html" /></Field>
        <Field label="Size bytes"><TextInput value={form.size_bytes} onChange={(event) => update('size_bytes', event.target.value)} type="number" min="0" /></Field>
        <Field label="SHA256"><TextInput value={form.sha256} onChange={(event) => update('sha256', event.target.value)} /></Field>
        <Field label="Preview JSON"><TextArea value={form.preview} onChange={(event) => update('preview', event.target.value)} /></Field>
        <Field label="Metadata JSON"><TextArea required value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Register artifact</SubmitButton>
      </form>
    </FormCard>
  );
}

const snapshotPayloadDefaults = {
  code: '{\n  "git_commit": "",\n  "git_dirty": false,\n  "repo_url": "",\n  "requirements_hash": "",\n  "metadata": {}\n}',
  data: '{\n  "dataset_name": "",\n  "dataset_version": "",\n  "universe": "",\n  "benchmark": "",\n  "time_range": {},\n  "metadata": {}\n}',
  env: '{\n  "python_version": "",\n  "platform": "",\n  "hostname": "",\n  "packages": {},\n  "metadata": {}\n}',
};

function CodeSnapshotForm({ run, onRunChanged }) {
  const [form, setForm] = useState({
    repo_url: '',
    git_commit: '',
    git_dirty: false,
    patch_artifact_id: '',
    requirements_hash: '',
    container_image: '',
    metadata: '{}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/snapshots/code`, compactObject({
        repo_url: form.repo_url,
        git_commit: form.git_commit,
        git_dirty: form.git_dirty,
        patch_artifact_id: form.patch_artifact_id,
        requirements_hash: form.requirements_hash,
        container_image: form.container_image,
        metadata: parseJsonObject(form.metadata),
      }));
      setForm({
        repo_url: '',
        git_commit: '',
        git_dirty: false,
        patch_artifact_id: '',
        requirements_hash: '',
        container_image: '',
        metadata: '{}',
      });
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Code Snapshot">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Repository URL"><TextInput value={form.repo_url} onChange={(event) => update('repo_url', event.target.value)} placeholder="https://..." /></Field>
        <Field label="Git commit"><TextInput value={form.git_commit} onChange={(event) => update('git_commit', event.target.value)} placeholder="abc123" /></Field>
        <label className="flex items-center gap-2 text-xs font-semibold text-muted">
          <input checked={form.git_dirty} className="h-4 w-4 accent-charcoal" onChange={(event) => update('git_dirty', event.target.checked)} type="checkbox" />
          Git dirty
        </label>
        <Field label="Patch artifact ID"><TextInput value={form.patch_artifact_id} onChange={(event) => update('patch_artifact_id', event.target.value)} /></Field>
        <Field label="Requirements hash"><TextInput value={form.requirements_hash} onChange={(event) => update('requirements_hash', event.target.value)} /></Field>
        <Field label="Container image"><TextInput value={form.container_image} onChange={(event) => update('container_image', event.target.value)} /></Field>
        <Field label="Metadata JSON"><TextArea value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Record code snapshot</SubmitButton>
      </form>
    </FormCard>
  );
}

function DatasetSnapshotForm({ run, onRunChanged }) {
  const [form, setForm] = useState({
    dataset_name: '',
    dataset_version: '',
    fingerprint: '',
    universe: '',
    benchmark: '',
    calendar: '',
    fee_model: '',
    slippage_model: '',
    time_range: '{}',
    metadata: '{}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/snapshots/data`, compactObject({
        dataset_name: form.dataset_name,
        dataset_version: form.dataset_version,
        fingerprint: form.fingerprint,
        universe: form.universe,
        benchmark: form.benchmark,
        calendar: form.calendar,
        fee_model: form.fee_model,
        slippage_model: form.slippage_model,
        time_range: parseJsonObject(form.time_range),
        metadata: parseJsonObject(form.metadata),
      }));
      setForm((current) => ({ ...current, dataset_name: '', dataset_version: '', fingerprint: '', universe: '', benchmark: '', calendar: '', fee_model: '', slippage_model: '', time_range: '{}', metadata: '{}' }));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Dataset">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Dataset name"><TextInput value={form.dataset_name} onChange={(event) => update('dataset_name', event.target.value)} /></Field>
        <Field label="Version"><TextInput value={form.dataset_version} onChange={(event) => update('dataset_version', event.target.value)} /></Field>
        <Field label="Fingerprint"><TextInput value={form.fingerprint} onChange={(event) => update('fingerprint', event.target.value)} /></Field>
        <Field label="Universe"><TextInput value={form.universe} onChange={(event) => update('universe', event.target.value)} /></Field>
        <Field label="Benchmark"><TextInput value={form.benchmark} onChange={(event) => update('benchmark', event.target.value)} /></Field>
        <Field label="Calendar"><TextInput value={form.calendar} onChange={(event) => update('calendar', event.target.value)} /></Field>
        <Field label="Fee model"><TextInput value={form.fee_model} onChange={(event) => update('fee_model', event.target.value)} /></Field>
        <Field label="Slippage model"><TextInput value={form.slippage_model} onChange={(event) => update('slippage_model', event.target.value)} /></Field>
        <Field label="Time range JSON"><TextArea value={form.time_range} onChange={(event) => update('time_range', event.target.value)} /></Field>
        <Field label="Metadata JSON"><TextArea value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Register dataset</SubmitButton>
      </form>
    </FormCard>
  );
}

function EnvSnapshotForm({ run, onRunChanged }) {
  const [form, setForm] = useState({
    python_version: '',
    platform: '',
    hostname: '',
    packages: '{}',
    metadata: '{}',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/snapshots/env`, compactObject({
        python_version: form.python_version,
        platform: form.platform,
        hostname: form.hostname,
        packages: parseJsonObject(form.packages),
        metadata: parseJsonObject(form.metadata),
      }));
      setForm({ python_version: '', platform: '', hostname: '', packages: '{}', metadata: '{}' });
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Environment">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Python version"><TextInput value={form.python_version} onChange={(event) => update('python_version', event.target.value)} placeholder="3.11.9" /></Field>
        <Field label="Platform"><TextInput value={form.platform} onChange={(event) => update('platform', event.target.value)} placeholder="Windows-..." /></Field>
        <Field label="Hostname"><TextInput value={form.hostname} onChange={(event) => update('hostname', event.target.value)} /></Field>
        <Field label="Packages JSON"><TextArea value={form.packages} onChange={(event) => update('packages', event.target.value)} /></Field>
        <Field label="Metadata JSON"><TextArea value={form.metadata} onChange={(event) => update('metadata', event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Record environment</SubmitButton>
      </form>
    </FormCard>
  );
}

function SnapshotForm({ run, onRunChanged }) {
  const [kind, setKind] = useState('code');
  const [payload, setPayload] = useState(snapshotPayloadDefaults.code);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const updateKind = (value) => {
    setKind(value);
    setPayload(snapshotPayloadDefaults[value]);
  };
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/v1/runs/${run.id}/snapshots/${kind}`, compactObject(parseJsonObject(payload)));
      await onRunChanged(run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Advanced Snapshot">
      <form className="space-y-2" onSubmit={submit}>
        <Field label="Kind">
          <SelectInput value={kind} onChange={(event) => updateKind(event.target.value)}>
            <option value="code">code</option>
            <option value="data">data</option>
            <option value="env">env</option>
          </SelectInput>
        </Field>
        <Field label="Payload JSON"><TextArea required value={payload} onChange={(event) => setPayload(event.target.value)} /></Field>
        <InlineError message={error} />
        <SubmitButton loading={loading}>Add snapshot</SubmitButton>
      </form>
    </FormCard>
  );
}

function SearchPage({ data, selectRun, selectResearch, selectBranch, selectedSearchViewId, quickSearch, onChanged }) {
  const projects = data?.projects || [];
  const researches = data?.researches || [];
  const branches = data?.branches || [];
  const views = data?.search_views || [];
  const [viewQuery, setViewQuery] = useState('');
  const [projectId, setProjectId] = useState(projects[0]?.id || '');
  const [filterForm, setFilterForm] = useState({
    project_key: '',
    research_key: '',
    branch_key: '',
    status: '',
    tags: '',
    metric: 'strategy.summary.sharpe',
    op: '>',
    metric_value: '',
    config_key: '',
    config_value: '',
    context_key: '',
    context_value: '',
    author_type: '',
    created_after: '',
    created_before: '',
    has_artifact: '',
    where: '',
    limit: '20',
  });
  const [filtersText, setFiltersText] = useState('{"limit":20}');
  const [viewForm, setViewForm] = useState({ name: '', description: '' });
  const [activeViewId, setActiveViewId] = useState(selectedSearchViewId || null);
  const [results, setResults] = useState([]);
  const [researchResults, setResearchResults] = useState([]);
  const [researchFilter, setResearchFilter] = useState({ project_key: '', status: '', text: '', tags: '', limit: '20' });
  const [activeSearchPanel, setActiveSearchPanel] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!projectId && projects[0]?.id) setProjectId(projects[0].id);
  }, [projectId, projects]);
  useEffect(() => {
    if (selectedSearchViewId) setActiveViewId(selectedSearchViewId);
  }, [selectedSearchViewId]);
  const selectedView = views.find((item) => item.id === activeViewId) || null;
  const normalizedViewQuery = viewQuery.trim().toLowerCase();
  const filteredViews = views.filter((view) => !normalizedViewQuery || searchViewSearchText(view).includes(normalizedViewQuery));
  const runSearch = async (filters = parseJsonObject(filtersText)) => {
    setLoading(true);
    setError(null);
    try {
      const rows = await apiPost('/api/v1/search/runs', filters);
      setResults(rows);
    } catch (err) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };
  const saveView = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: viewForm.name,
        description: viewForm.description,
        filters: parseJsonObject(filtersText),
      };
      if (selectedView) {
        await apiPatch(`/api/v1/search-views/${selectedView.id}`, payload);
      } else {
        await apiPost('/api/v1/search-views', { project_id: projectId, ...payload });
        setViewForm({ name: '', description: '' });
      }
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  const runView = async (view) => {
    setActiveViewId(view.id);
    setProjectId(view.project_id || projectId);
    setViewForm({ name: view.name || '', description: view.description || '' });
    setFiltersText(JSON.stringify(view.filters_json || {}, null, 2));
    setLoading(true);
    setError(null);
    try {
      const rows = await apiPost(`/api/v1/search-views/${view.id}/run`, {});
      setResults(rows);
    } catch (err) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    const view = views.find((item) => item.id === selectedSearchViewId);
    if (view) runView(view);
  }, [selectedSearchViewId]);
  const clearSelectedView = () => {
    setActiveViewId(null);
    setViewForm({ name: '', description: '' });
  };
  const updateFilter = (field, value) => setFilterForm((current) => ({ ...current, [field]: value }));
  const updateResearchFilter = (field, value) => setResearchFilter((current) => ({ ...current, [field]: value }));
  const applyStructuredFilters = () => {
    const filters = buildSearchFilters(filterForm);
    setFiltersText(JSON.stringify(filters, null, 2));
    runSearch(filters);
  };
  const applyWhereFilters = () => {
    try {
      const filters = {
        ...parseSearchWhere(filterForm.where),
        limit: filterForm.limit ? Number(filterForm.limit) : 20,
      };
      setFiltersText(JSON.stringify(filters, null, 2));
      runSearch(filters);
    } catch (err) {
      setError(err.message);
    }
  };
  const runResearchSearch = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await apiPost('/api/v1/search/researches', buildResearchSearchFilters(researchFilter));
      setResearchResults(rows);
    } catch (err) {
      setError(err.message);
      setResearchResults([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    if (!quickSearch?.query) return;
    const filters = { name: quickSearch.query, limit: 20 };
    setFiltersText(JSON.stringify(filters, null, 2));
    setFilterForm((current) => ({ ...current, limit: '20' }));
    setResearchFilter((current) => ({ ...current, text: quickSearch.query, limit: '20' }));
    runSearch(filters);
    apiPost('/api/v1/search/researches', { text: quickSearch.query, limit: 20 })
      .then((rows) => setResearchResults(rows))
      .catch(() => setResearchResults([]));
  }, [quickSearch?.nonce]);
  return (
    <div className="space-y-5">
      <Hero eyebrow="Search" title="Saved Run Search" description={null} />
      <Panel className="overflow-hidden">
        <PanelHeader title="Search Controls" icon={Search} />
        <div className="border-b border-line p-4">
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'structured', label: 'Structured Filters', icon: Search },
              { id: 'research', label: 'Research Search', icon: TableProperties },
              { id: 'json', label: 'JSON Filters', icon: FileText },
              { id: 'view', label: selectedView ? 'Update View' : 'Save View', icon: ListTree },
            ].map(({ id, label, icon: Icon }) => (
              <button
                className={activeSearchPanel === id ? 'primary-button' : 'secondary-button'}
                key={id}
                type="button"
                onClick={() => setActiveSearchPanel((current) => (current === id ? null : id))}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4">
          {!activeSearchPanel ? (
            <div className="max-w-3xl">
              <ReadOnlyField label="Current Filters" value={formatFilterTextSummary(filtersText)} code />
            </div>
          ) : null}
          {activeSearchPanel === 'structured' ? <div className="max-w-3xl"><FormCard title="Structured Filters">
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Field label="Project">
                  <SelectInput value={filterForm.project_key} onChange={(event) => updateFilter('project_key', event.target.value)}>
                    <option value="">{t("Any project")}</option>
                    {projects.map((project) => <option key={project.id} value={project.key}>{project.key}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Status">
                  <SelectInput value={filterForm.status} onChange={(event) => updateFilter('status', event.target.value)}>
                    <option value="">{t("Any status")}</option>
                    {['running', 'completed', 'failed', 'cancelled'].map((status) => <option key={status} value={status}>{tStatus(status)}</option>)}
                  </SelectInput>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Research">
                  <SelectInput value={filterForm.research_key} onChange={(event) => updateFilter('research_key', event.target.value)}>
                    <option value="">{t("Any research")}</option>
                    {researches.map((research) => <option key={research.id} value={research.key}>{research.key}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Branch">
                  <SelectInput value={filterForm.branch_key} onChange={(event) => updateFilter('branch_key', event.target.value)}>
                    <option value="">{t("Any branch")}</option>
                    {branches.map((branch) => <option key={branch.id} value={branch.key}>{branch.key}</option>)}
                  </SelectInput>
                </Field>
              </div>
              <Field label="Tags"><TextInput value={filterForm.tags} onChange={(event) => updateFilter('tags', event.target.value)} placeholder="baseline,post-cost" /></Field>
              <div className="grid grid-cols-12 gap-2">
                <Field label="Metric"><TextInput className="col-span-12" value={filterForm.metric} onChange={(event) => updateFilter('metric', event.target.value)} /></Field>
                <Field label="Op"><SelectInput value={filterForm.op} onChange={(event) => updateFilter('op', event.target.value)}>{['>', '>=', '<', '<=', '==', '!='].map((op) => <option key={op} value={op}>{op}</option>)}</SelectInput></Field>
                <Field label="Value"><TextInput value={filterForm.metric_value} onChange={(event) => updateFilter('metric_value', event.target.value)} placeholder="1.0" /></Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Config key"><TextInput value={filterForm.config_key} onChange={(event) => updateFilter('config_key', event.target.value)} placeholder="fee_bps" /></Field>
                <Field label="Config value"><TextInput value={filterForm.config_value} onChange={(event) => updateFilter('config_value', event.target.value)} placeholder="10" /></Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Context key"><TextInput value={filterForm.context_key} onChange={(event) => updateFilter('context_key', event.target.value)} placeholder="asset_class" /></Field>
                <Field label="Context value"><TextInput value={filterForm.context_value} onChange={(event) => updateFilter('context_value', event.target.value)} placeholder="CN_EQ" /></Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Author">
                  <SelectInput value={filterForm.author_type} onChange={(event) => updateFilter('author_type', event.target.value)}>
                    <option value="">{t("Any author")}</option>
                    {['human', 'agent', 'system'].map((author) => <option key={author} value={author}>{author}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Created after"><TextInput value={filterForm.created_after} onChange={(event) => updateFilter('created_after', event.target.value)} placeholder="2026-01-01T00:00:00Z" /></Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Created before"><TextInput value={filterForm.created_before} onChange={(event) => updateFilter('created_before', event.target.value)} placeholder="2026-12-31T23:59:59Z" /></Field>
                <Field label="Artifact kind">
                  <SelectInput value={filterForm.has_artifact} onChange={(event) => updateFilter('has_artifact', event.target.value)}>
                    <option value="">{t("Any artifact")}</option>
                    {artifactKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
                  </SelectInput>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Limit"><TextInput value={filterForm.limit} onChange={(event) => updateFilter('limit', event.target.value)} type="number" min="1" /></Field>
              </div>
              <button className="secondary-button w-full" disabled={loading} onClick={applyStructuredFilters}>
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Apply filters
              </button>
              <Field label="Where expression"><TextArea value={filterForm.where} onChange={(event) => updateFilter('where', event.target.value)} placeholder={'metrics.strategy.summary.sharpe > 1 and tags contains "baseline"'} /></Field>
              <button className="secondary-button w-full" disabled={loading} onClick={applyWhereFilters}>
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Apply where
              </button>
            </div>
          </FormCard></div> : null}
          {activeSearchPanel === 'research' ? <div className="max-w-3xl"><FormCard title="Research Search">
            <div className="space-y-2">
              <Field label="Project">
                <SelectInput value={researchFilter.project_key} onChange={(event) => updateResearchFilter('project_key', event.target.value)}>
                  <option value="">{t("Any project")}</option>
                  {projects.map((project) => <option key={project.id} value={project.key}>{project.key}</option>)}
                </SelectInput>
              </Field>
              <Field label="Status">
                <SelectInput value={researchFilter.status} onChange={(event) => updateResearchFilter('status', event.target.value)}>
                  <option value="">{t("Any status")}</option>
                  {['active', 'paused', 'archived'].map((status) => <option key={status} value={status}>{tStatus(status)}</option>)}
                </SelectInput>
              </Field>
              <Field label="Text"><TextInput value={researchFilter.text} onChange={(event) => updateResearchFilter('text', event.target.value)} placeholder="hypothesis, title, key" /></Field>
              <Field label="Tags"><TextInput value={researchFilter.tags} onChange={(event) => updateResearchFilter('tags', event.target.value)} /></Field>
              <Field label="Limit"><TextInput value={researchFilter.limit} onChange={(event) => updateResearchFilter('limit', event.target.value)} type="number" min="1" /></Field>
              <button className="secondary-button w-full" disabled={loading} onClick={runResearchSearch}>
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Search researches
              </button>
            </div>
          </FormCard></div> : null}
          {activeSearchPanel === 'json' ? <div className="max-w-3xl"><FormCard title="Filters">
            <div className="space-y-2">
              <Field label="Filters JSON"><TextArea value={filtersText} onChange={(event) => setFiltersText(event.target.value)} className="min-h-[150px]" /></Field>
              <button className="secondary-button w-full" disabled={loading} onClick={() => runSearch()}>
                {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Search runs
              </button>
              <InlineError message={error} />
            </div>
          </FormCard></div> : null}
          {activeSearchPanel === 'view' ? <div className="max-w-3xl"><FormCard title={selectedView ? 'Update View' : 'Save View'}>
            <form className="space-y-2" onSubmit={saveView}>
              <Field label="Project">
                <SelectInput required disabled={Boolean(selectedView)} value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                  <option value="" disabled>{t("Select project")}</option>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.key}</option>)}
                </SelectInput>
              </Field>
              <Field label="Name"><TextInput required value={viewForm.name} onChange={(event) => setViewForm((current) => ({ ...current, name: event.target.value }))} /></Field>
              <Field label="Description"><TextInput value={viewForm.description} onChange={(event) => setViewForm((current) => ({ ...current, description: event.target.value }))} /></Field>
              <SubmitButton loading={loading}>{selectedView ? 'Update search view' : 'Save search view'}</SubmitButton>
              {selectedView ? <button className="secondary-button w-full" type="button" onClick={clearSelectedView}>{t("Save as new view")}</button> : null}
            </form>
          </FormCard></div> : null}
        </div>
      </Panel>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel className="overflow-hidden">
          <PanelHeader title="Saved Views" icon={ListTree} />
          <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1fr_auto]">
            <Field label="Search saved views"><TextInput value={viewQuery} onChange={(event) => setViewQuery(event.target.value)} placeholder="name, description, filters" /></Field>
            <div className="flex items-end text-xs font-semibold text-muted">{filteredViews.length} / {views.length} shown</div>
          </div>
          <div className="divide-y divide-line">
            {filteredViews.length ? filteredViews.map((view) => (
              <div className={`flex items-center justify-between gap-3 px-5 py-4 ${selectedView?.id === view.id ? 'bg-infoSoft/60' : ''}`} key={view.id}>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-ink">{view.name}</div>
                  <div className="mt-1 truncate text-xs text-muted">{view.description || formatFilterSummary(view.filters_json)}</div>
                </div>
                <button className="secondary-button shrink-0" onClick={() => runView(view)}><Search className="h-4 w-4" />{t("Run")}</button>
              </div>
            )) : <div className="p-5 text-sm text-muted">{views.length ? 'No saved views match the current search.' : 'No saved search views.'}</div>}
          </div>
        </Panel>
        <RunsTable title="Search Results" runs={results} onSelectRun={selectRun} onSelectBranch={selectBranch} />
      </div>
      <ResearchSearchResults rows={researchResults} onSelect={selectResearch} />
    </div>
  );
}

function ResearchSearchResults({ rows, onSelect }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Research Results" icon={TableProperties} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Research")}</th><th className="px-4 py-3">{t("Project")}</th><th className="px-4 py-3">{t("Status")}</th><th className="px-4 py-3 text-right">{t("Branches")}</th><th className="px-4 py-3 text-right">{t("Runs")}</th><th className="px-4 py-3">{t("Champion")}</th></tr></thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr className="cursor-pointer hover:bg-white/45" key={row.id} onClick={() => onSelect(row.id)}>
                <td className="table-cell font-semibold text-ink">{row.title || row.key}</td>
                <td className="table-cell text-muted">{row.project_key}</td>
                <td className="table-cell"><Badge tone={row.status === 'active' ? 'positive' : 'neutral'}>{tStatus(row.status)}</Badge></td>
                <td className="table-cell text-right">{row.branch_count || 0}</td>
                <td className="table-cell text-right">{row.run_count || 0}</td>
                <td className="table-cell text-muted">{row.champion_run?.name || '--'}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="6">{t("No research search results.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ComparePage({ data, selectProject, selectResearch, selectRun, selectBranch, selectCompareSet, selectedCompareSetId, onChanged }) {
  const runs = data?.runs || [];
  const compareSets = data?.compare_sets || [];
  const [mode, setMode] = useState(selectedCompareSetId ? 'detail' : 'workbench');
  const [result, setResult] = useState(null);
  const [activeCompareSetId, setActiveCompareSetId] = useState(selectedCompareSetId || null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [metricsText, setMetricsText] = useState('strategy.summary.annual_return,strategy.summary.annual_volatility,strategy.summary.max_drawdown,strategy.summary.sharpe,strategy.summary.sortino,strategy.summary.calmar,strategy.summary.turnover');
  const [seriesText, setSeriesText] = useState('');
  const [sortMetric, setSortMetric] = useState('strategy.summary.sharpe');
  const [sortDirection, setSortDirection] = useState('auto');
  const [compareError, setCompareError] = useState(null);
  const loadedCompareSetIdRef = useRef(null);
  const loadingCompareSetIdRef = useRef(null);
  const metrics = parseCsv(metricsText);
  const comparedRuns = mergeRunsBySelection(selectedIds, runs, result?.runs || []);
  const sortedRuns = sortComparedRuns(comparedRuns, result?.metrics || {}, sortMetric || metrics[0], sortDirection);
  const baselineRun = comparedRuns[0] || sortedRuns[0] || null;
  const selectedCompareSet = compareSets.find((item) => item.id === activeCompareSetId) || null;

  const openWorkbench = () => {
    setMode('workbench');
    setActiveCompareSetId(null);
    setSelectedIds([]);
    setResult(null);
    setCompareError(null);
    loadedCompareSetIdRef.current = null;
    loadingCompareSetIdRef.current = null;
    if (selectCompareSet) selectCompareSet(null);
  };

  const runCompare = async () => {
    setMode('detail');
    setCompareError(null);
    try {
      const compare = await apiPost('/api/v1/compare/runs', {
        run_ids: selectedIds,
        metrics,
        series: parseCsv(seriesText),
        with_config_diff: true,
      });
      setResult(compare);
    } catch (err) {
      setResult(null);
      setCompareError(err.message);
    }
  };

  const runCompareSet = async (compareSetId, options = {}) => {
    setMode('detail');
    setCompareError(null);
    loadingCompareSetIdRef.current = compareSetId;
    if (options.updateRoute !== false && selectCompareSet) selectCompareSet(compareSetId);
    try {
      const compareSet = await apiGet(`/api/v1/compare-sets/${compareSetId}`);
      const layout = compareSet.layout_json || {};
      const setMetrics = listOrCsv(layout.metrics || []);
      const setSeries = listOrCsv(layout.series || []);
      const runIds = compareSet.run_ids_json || [];
      setActiveCompareSetId(compareSet.id);
      setSelectedIds(runIds);
      if (setMetrics.length) setMetricsText(setMetrics.join(','));
      setSeriesText(setSeries.join(','));
      const compare = await apiPost('/api/v1/compare/runs', {
        run_ids: runIds,
        metrics: setMetrics,
        series: setSeries,
        with_config_diff: true,
      });
      setResult(compare);
      loadedCompareSetIdRef.current = compareSet.id;
    } catch (err) {
      setResult(null);
      setCompareError(err.message);
    } finally {
      if (loadingCompareSetIdRef.current === compareSetId) loadingCompareSetIdRef.current = null;
    }
  };

  useEffect(() => {
    if (selectedCompareSetId) {
      setActiveCompareSetId(selectedCompareSetId);
      setMode('detail');
    } else {
      setActiveCompareSetId(null);
      setMode('workbench');
    }
  }, [selectedCompareSetId]);

  useEffect(() => {
    if (!selectedCompareSet) return;
    const layout = selectedCompareSet.layout_json || {};
    setSelectedIds(selectedCompareSet.run_ids_json || []);
    if (Array.isArray(layout.metrics) && layout.metrics.length) setMetricsText(layout.metrics.join(','));
    if (Array.isArray(layout.series)) setSeriesText(layout.series.join(','));
  }, [selectedCompareSet]);

  useEffect(() => {
    if (mode !== 'detail' || !selectedCompareSet?.id) return;
    if (loadedCompareSetIdRef.current === selectedCompareSet.id || loadingCompareSetIdRef.current === selectedCompareSet.id) return;
    runCompareSet(selectedCompareSet.id, { updateRoute: false });
  }, [mode, selectedCompareSet?.id]);

  useEffect(() => {
    if (!sortMetric && metrics.length) setSortMetric(metrics[0]);
  }, [metricsText, sortMetric]);

  const toggleRun = (runId) => {
    setSelectedIds((current) => (current.includes(runId) ? current.filter((id) => id !== runId) : [...current, runId]));
  };

  if (mode !== 'detail') {
    return (
      <CompareWorkbenchPage
        data={data}
        runs={runs}
        selectedIds={selectedIds}
        selectedCompareSet={selectedCompareSet}
        result={result}
        metricsText={metricsText}
        seriesText={seriesText}
        sortMetric={sortMetric}
        sortDirection={sortDirection}
        compareSets={compareSets}
        comparedRuns={comparedRuns}
        onMetricsChange={setMetricsText}
        onSeriesChange={setSeriesText}
        onSortMetricChange={setSortMetric}
        onSortDirectionChange={setSortDirection}
        onRunCompare={runCompare}
        onRunCompareSet={runCompareSet}
        onChanged={onChanged}
        onToggleRun={toggleRun}
        onSelectProject={selectProject}
        onSelectResearch={selectResearch}
        onSelectRun={selectRun}
        onClearCompareSet={() => setActiveCompareSetId(null)}
      />
    );
  }

  return (
    <div className="space-y-5">
      <Hero
        eyebrow="Compare"
        title="策略结果对比"
        description={selectedCompareSet ? selectedCompareSet.name : '临时 Run 对比'}
        action={<button className="secondary-button" onClick={openWorkbench} type="button"><ListTree className="h-4 w-4" />返回对比列表</button>}
      />
      <CompareDecisionSummaryPanel
        metrics={result?.metrics || {}}
        metricNames={metrics}
        runs={sortedRuns}
        baselineRun={baselineRun}
        series={result?.series || {}}
        error={compareError}
      />
      <CompareDiagnosticsPanel diagnostics={compareDiagnostics(sortedRuns, result?.series || {}, result?.metrics || {}, metrics)} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ComparePrimarySeriesPanel series={result?.series || {}} runs={result?.runs || sortedRuns} onSelectRun={selectRun} />
        <CompareDrawdownPanel series={result?.series || {}} runs={result?.runs || sortedRuns} onSelectRun={selectRun} />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <MetricMatrixPanel metrics={result?.metrics || {}} runs={sortedRuns} baselineRunId={baselineRun?.id || sortedRuns[0]?.id} error={compareError} />
        <ParetoPanel metrics={result?.metrics || {}} runs={sortedRuns} metricNames={metrics} onSelectRun={selectRun} />
      </div>
      <RunsTable title="参与对比的 Runs" runs={sortedRuns} onSelectRun={selectRun} onSelectBranch={selectBranch} />
      <DashboardCollapsedSection title="对比设置与保存">
        <div className="space-y-4 p-4">
          <CompareControlPanel
            data={data}
            metricsText={metricsText}
            onMetricsChange={setMetricsText}
            seriesText={seriesText}
            onSeriesChange={setSeriesText}
            sortMetric={sortMetric}
            onSortMetricChange={setSortMetric}
            sortDirection={sortDirection}
            onSortDirectionChange={setSortDirection}
            onRunCompare={runCompare}
            onChanged={onChanged}
            result={result}
            selectedIds={selectedIds}
            selectedCompareSet={selectedCompareSet}
            comparedRuns={comparedRuns}
            onClearCompareSet={() => setActiveCompareSetId(null)}
          />
          <CompareSetListPanel compareSets={compareSets} selectedCompareSet={selectedCompareSet} onRun={runCompareSet} />
          <BatchComparePanel selectedIds={selectedIds} metricsText={metricsText} seriesText={seriesText} />
          <RunSelectionTable runs={runs} selectedIds={selectedIds} onToggle={toggleRun} onSelectRun={selectRun} />
        </div>
      </DashboardCollapsedSection>
      <DashboardCollapsedSection title="高级诊断与原始明细">
        <div className="space-y-4 p-4">
          <SeriesPreviewPanel series={result?.series || {}} runs={result?.runs || sortedRuns} onSelectRun={selectRun} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <CompareConfigDiffPanel diff={result?.config_diff || {}} runs={sortedRuns} />
            <ArtifactComparisonPanel artifacts={result?.artifacts || {}} runs={sortedRuns} />
          </div>
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function CompareWorkbenchPage({ data, runs, selectedIds, selectedCompareSet, result, metricsText, seriesText, sortMetric, sortDirection, compareSets, comparedRuns, onMetricsChange, onSeriesChange, onSortMetricChange, onSortDirectionChange, onRunCompare, onRunCompareSet, onChanged, onToggleRun, onSelectProject, onSelectResearch, onSelectRun, onClearCompareSet }) {
  const rows = useMemo(() => buildCompareWorkbenchRows(compareSets, data), [compareSets, data]);
  const [projectId, setProjectId] = useState('');
  const [researchId, setResearchId] = useState('');
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const projectOptions = rows.filter((row) => row.project).map((row) => row.project);
  const uniqueProjects = Array.from(new Map(projectOptions.map((project) => [project.id, project])).values())
    .sort((a, b) => entityName(a).localeCompare(entityName(b)));
  const researchOptions = rows
    .filter((row) => row.research && (!projectId || row.project_id === projectId))
    .map((row) => row.research);
  const uniqueResearches = Array.from(new Map(researchOptions.map((research) => [research.id, research])).values())
    .sort((a, b) => entityName(a).localeCompare(entityName(b)));
  const filteredRows = rows.filter((row) => {
    if (projectId && row.project_id !== projectId) return false;
    if (researchId && row.research_id !== researchId) return false;
    return !normalizedQuery || row.searchText.includes(normalizedQuery);
  });
  const projectCount = new Set(rows.map((row) => row.project_id).filter(Boolean)).size;
  const researchCount = new Set(rows.map((row) => row.research_id).filter(Boolean)).size;
  const runReferenceCount = rows.reduce((count, row) => count + row.runCount, 0);

  useEffect(() => {
    if (researchId && !uniqueResearches.some((research) => research.id === researchId)) setResearchId('');
  }, [projectId, researchId, uniqueResearches]);

  return (
    <div className="space-y-5">
      <Hero eyebrow="Compare" title="对比工作台" description="按项目和研究阶段管理保存的对比集合，再进入具体对比结果。" />
      <div className="dashboard-stats-grid">
        <Panel><ReadOnlyField label="Compare Sets" value={String(rows.length)} /></Panel>
        <Panel><ReadOnlyField label="Projects" value={String(projectCount)} /></Panel>
        <Panel><ReadOnlyField label="Research" value={String(researchCount)} /></Panel>
        <Panel><ReadOnlyField label="Run References" value={String(runReferenceCount)} /></Panel>
      </div>
      <Panel className="overflow-hidden">
        <PanelHeader title="项目 / 阶段对比表" icon={TableProperties} />
        <div className="grid gap-3 border-b border-line p-4 lg:grid-cols-[minmax(160px,220px)_minmax(160px,220px)_1fr_auto]">
          <Field label="Project">
            <SelectInput value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">全部项目</option>
              {uniqueProjects.map((project) => <option key={project.id} value={project.id}>{entityName(project)}</option>)}
            </SelectInput>
          </Field>
          <Field label="Research">
            <SelectInput value={researchId} onChange={(event) => setResearchId(event.target.value)}>
              <option value="">全部研究</option>
              {uniqueResearches.map((research) => <option key={research.id} value={research.id}>{entityName(research)}</option>)}
            </SelectInput>
          </Field>
          <Field label="搜索"><TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="项目、研究、阶段、对比名称、指标" /></Field>
          <div className="flex items-end text-xs font-semibold text-muted">{filteredRows.length} / {rows.length} shown</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="table-cell">Project</th>
                <th className="table-cell">Research / 阶段</th>
                <th className="table-cell">Compare Set</th>
                <th className="table-cell text-right">Runs</th>
                <th className="table-cell">模板</th>
                <th className="table-cell text-right">Created</th>
                <th className="table-cell text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length ? filteredRows.map((row) => (
                <tr className="table-row" key={row.id}>
                  <td className="table-cell">
                    {row.project ? <button className="font-semibold text-ink hover:underline" type="button" onClick={() => onSelectProject(row.project.id)}>{entityName(row.project)}</button> : <span className="text-muted">--</span>}
                    <div className="text-xs text-muted">{row.project?.key || row.project_id || '--'}</div>
                  </td>
                  <td className="table-cell">
                    {row.research ? <button className="font-semibold text-ink hover:underline" type="button" onClick={() => onSelectResearch(row.research.id)}>{entityName(row.research)}</button> : <span className="font-semibold text-muted">项目级</span>}
                    <div className="mt-1 text-xs text-muted">{row.stage}</div>
                  </td>
                  <td className="table-cell">
                    <button className="font-semibold text-ink hover:underline" type="button" onClick={() => onRunCompareSet(row.id)}>{row.name}</button>
                    <div className="mt-1 truncate text-xs text-muted">{(row.run_ids_json || []).slice(0, 4).join(', ')}{(row.run_ids_json || []).length > 4 ? ` +${(row.run_ids_json || []).length - 4}` : ''}</div>
                  </td>
                  <td className="table-cell text-right font-semibold text-info">{row.runCount}</td>
                  <td className="table-cell text-muted">{compareSetLayoutSummary(row)}</td>
                  <td className="table-cell text-right text-muted">{formatDate(row.created_at)}</td>
                  <td className="table-cell text-right">
                    <button className="secondary-button justify-end" type="button" onClick={() => onRunCompareSet(row.id)}>
                      <RefreshCw className="h-4 w-4" />
                      打开
                    </button>
                  </td>
                </tr>
              )) : <tr><td className="table-cell text-muted" colSpan="7">暂无保存的对比集合。可以在下方临时选择 runs 后保存为 Compare Set。</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
      <DashboardCollapsedSection title="临时 Run 对比与保存">
        <div className="space-y-4 p-4">
          <CompareControlPanel
            data={data}
            metricsText={metricsText}
            onMetricsChange={onMetricsChange}
            seriesText={seriesText}
            onSeriesChange={onSeriesChange}
            sortMetric={sortMetric}
            onSortMetricChange={onSortMetricChange}
            sortDirection={sortDirection}
            onSortDirectionChange={onSortDirectionChange}
            onRunCompare={onRunCompare}
            onChanged={onChanged}
            result={result}
            selectedIds={selectedIds}
            selectedCompareSet={selectedCompareSet}
            comparedRuns={comparedRuns}
            onClearCompareSet={onClearCompareSet}
          />
          <RunSelectionTable runs={runs} selectedIds={selectedIds} onToggle={onToggleRun} onSelectRun={onSelectRun} />
        </div>
      </DashboardCollapsedSection>
    </div>
  );
}

function CompareDecisionSummaryPanel({ metrics, metricNames, runs, baselineRun, series, error }) {
  const primaryMetric = metricNames.find((metric) => Object.keys(metrics?.[metric] || {}).length) || Object.keys(metrics || {})[0] || '';
  const drawdownMetric = metricNames.find((metric) => /drawdown|dd/i.test(metric)) || Object.keys(metrics || {}).find((metric) => /drawdown|dd/i.test(metric)) || '';
  const bestMetricRun = primaryMetric ? bestComparedRun(primaryMetric, metrics?.[primaryMetric], runs) : null;
  const bestDrawdownRun = drawdownMetric ? bestComparedRun(drawdownMetric, metrics?.[drawdownMetric], runs) : null;
  const seriesEntries = Object.entries(series || {});
  const seriesRunCount = new Set(seriesEntries.flatMap(([, byRun]) => Object.keys(byRun || {}))).size;
  const metricCells = Object.values(metrics || {}).reduce((count, byRun) => count + Object.values(byRun || {}).filter((value) => value !== null && value !== undefined && value !== '').length, 0);
  const expectedMetricCells = Math.max(1, runs.length * Math.max(1, Object.keys(metrics || {}).length));
  const coverage = runs.length ? `${metricCells}/${expectedMetricCells}` : '--';
  const recommendation = compareRecommendation({ runs, bestMetricRun, bestDrawdownRun, baselineRun, primaryMetric, drawdownMetric, metrics });
  return (
    <Panel className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">决策摘要</div>
          <div className="mt-1 text-xs text-muted">先回答哪个方案更值得推进，再给出曲线、回撤、指标和诊断证据。</div>
        </div>
        <Badge tone={error ? 'negative' : runs.length >= 2 ? 'positive' : 'warning'}>{error ? '错误' : runs.length >= 2 ? '可决策' : '需要更多 Run'}</Badge>
      </div>
      {error ? <div className="mb-3"><InlineError message={error} /></div> : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-8">
        <ReadOnlyField label="模板" value="绩效对比" />
        <ReadOnlyField label="Runs" value={String(runs.length)} />
        <ReadOnlyField label="基准" value={baselineRun?.name || '--'} />
        <ReadOnlyField label="领先候选" value={bestMetricRun ? `${bestMetricRun.run.name} / ${formatMetric(bestMetricRun.value)}` : '--'} />
        <ReadOnlyField label="主指标" value={shortMetricName(primaryMetric) || '--'} />
        <ReadOnlyField label="回撤最优" value={bestDrawdownRun ? `${bestDrawdownRun.run.name} / ${formatMetric(bestDrawdownRun.value)}` : '--'} />
        <ReadOnlyField label="Series" value={seriesEntries.length ? `${seriesEntries.length} 组 / ${seriesRunCount} runs` : 'No Series Data Available'} />
        <ReadOnlyField label="指标覆盖" value={coverage} />
      </div>
      <div className="mt-4 rounded-md border border-line bg-white/55 p-3">
        <div className="text-xs font-semibold uppercase text-muted">建议</div>
        <div className={`mt-1 text-sm font-semibold ${recommendation.tone === 'positive' ? 'text-positive' : recommendation.tone === 'warning' ? 'text-warning' : 'text-muted'}`}>{recommendation.text}</div>
      </div>
    </Panel>
  );
}

function CompareDiagnosticsPanel({ diagnostics }) {
  const [open, setOpen] = useState(false);
  const diagnosticsKey = diagnostics.map((item) => `${item.severity}:${item.title}:${item.detail}`).join('|');
  useEffect(() => {
    setOpen(false);
  }, [diagnosticsKey]);
  if (!diagnostics.length) return null;
  const hasError = diagnostics.some((item) => item.severity === 'error');
  const errorCount = diagnostics.filter((item) => item.severity === 'error').length;
  const warningCount = diagnostics.filter((item) => item.severity !== 'error').length;
  const toneClass = hasError
    ? 'border-negative/60 bg-negativeSoft/80 text-negative'
    : 'border-warning/60 bg-warningSoft/80 text-warning';
  const detailClass = hasError ? 'border-negative/25 bg-white/45' : 'border-warning/25 bg-white/45';
  const Icon = hasError ? XCircle : AlertTriangle;
  return (
    <div className={`overflow-hidden rounded-md border ${toneClass}`}>
      <button className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left" type="button" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <span className="flex min-w-0 items-center gap-3">
          <Icon className="h-5 w-5 shrink-0" />
          <span className="min-w-0">
            <span className="block text-sm font-semibold">对比诊断</span>
            <span className="mt-1 flex"><DiagnosticCountBadges errorCount={errorCount} warningCount={warningCount} /></span>
          </span>
        </span>
        <CollapseToggleIcon open={open} />
      </button>
      {open ? (
        <div className={`border-t px-4 py-3 ${detailClass}`}>
          <div className="space-y-2">
            {diagnostics.map((item, index) => (
              <div className="rounded-md border border-line/70 bg-white/55 p-3" key={`${item.severity}-${item.title}-${index}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase ${item.severity === 'error' ? 'bg-negativeSoft text-negative' : 'bg-warningSoft text-warning'}`}>{item.severity}</span>
                  <span className="text-sm font-semibold text-ink">{item.title}</span>
                </div>
                {item.detail ? <div className="mt-1 text-sm text-muted">{item.detail}</div> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
function CompareControlPanel({ data, metricsText, onMetricsChange, seriesText, onSeriesChange, sortMetric, onSortMetricChange, sortDirection, onSortDirectionChange, onRunCompare, onChanged, result, selectedIds, selectedCompareSet, comparedRuns, onClearCompareSet }) {
  const selectedRuns = comparedRuns?.length ? comparedRuns : (data?.runs || []).filter((run) => selectedIds.includes(run.id));
  const defaultProjectId = selectedCompareSet?.project_id || selectedRuns[0]?.project_id || data?.projects?.[0]?.id || '';
  const commonResearchId = selectedCompareSet?.research_id || commonValue(selectedRuns.map((run) => run.research_id).filter(Boolean)) || '';
  const metrics = parseCsv(metricsText);
  const [form, setForm] = useState({ project_id: defaultProjectId, research_id: commonResearchId, name: '' });
  const [activePanel, setActivePanel] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const researchOptions = (data?.researches || []).filter((research) => !form.project_id || research.project_id === form.project_id);
  useEffect(() => {
    if (selectedCompareSet) return;
    setForm((current) => ({
      ...current,
      project_id: current.project_id || defaultProjectId,
      research_id: current.research_id || commonResearchId,
    }));
  }, [commonResearchId, defaultProjectId, selectedCompareSet]);
  useEffect(() => {
    if (selectedCompareSet) {
      setForm({ project_id: selectedCompareSet.project_id || defaultProjectId, research_id: selectedCompareSet.research_id || '', name: selectedCompareSet.name || '' });
    }
  }, [selectedCompareSet, defaultProjectId]);
  const updateCompareSetProject = (projectId) => {
    setForm((current) => {
      const researchStillValid = (data?.researches || []).some((research) => research.id === current.research_id && research.project_id === projectId);
      return { ...current, project_id: projectId, research_id: researchStillValid ? current.research_id : '' };
    });
  };
  const saveCompareSet = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: form.name,
        research_id: form.research_id || null,
        run_ids: selectedIds,
        layout: { metrics: parseCsv(metricsText), series: parseCsv(seriesText), result_summary: result?.metrics || {} },
      };
      if (selectedCompareSet) {
        await apiPatch(`/api/v1/compare-sets/${selectedCompareSet.id}`, payload);
      } else {
        await apiPost('/api/v1/compare-sets', { project_id: form.project_id, ...payload });
        setForm((current) => ({ ...current, name: '' }));
      }
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="对比设置" icon={Layers3} />
      <div className="border-b border-line p-4">
        <div className="flex flex-wrap gap-2">
          {[
            { id: 'metrics', label: '指标与序列', icon: BarChart3 },
            { id: 'compare-set', label: selectedCompareSet ? '更新对比集合' : '保存对比集合', icon: ListTree },
          ].map(({ id, label, icon: Icon }) => (
            <button
              className={activePanel === id ? 'primary-button' : 'secondary-button'}
              key={id}
              type="button"
              onClick={() => setActivePanel((current) => (current === id ? null : id))}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
          <button className="secondary-button" type="button" onClick={onRunCompare}>
            <RefreshCw className="h-4 w-4" />
            重新对比
          </button>
        </div>
      </div>
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        {!activePanel ? (
          <>
            <ReadOnlyField label="指标模板" value={metrics.length ? metrics.map(shortMetricName).join(', ') : '--'} />
            <ReadOnlyField label="序列范围" value={parseCsv(seriesText).length ? parseCsv(seriesText).join(', ') : '全部 series，自动识别主曲线和回撤'} />
            <ReadOnlyField label="已选 Runs" value={String(selectedIds.length)} />
            <ReadOnlyField label="排序" value={`${shortMetricName(sortMetric || metrics[0] || '--')} · ${sortDirection === 'auto' ? '自动最优' : sortDirection}`} />
          </>
        ) : null}
        {activePanel === 'metrics' ? <div className="max-w-3xl lg:col-span-2"><FormCard title="指标与序列">
          <div className="space-y-2">
            <Field label="Metrics"><TextInput value={metricsText} onChange={(event) => onMetricsChange(event.target.value)} /></Field>
            <Field label="Series"><TextInput value={seriesText} onChange={(event) => onSeriesChange(event.target.value)} placeholder="留空 = 全部 series，前端自动识别" /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="排序指标">
                <SelectInput value={sortMetric} onChange={(event) => onSortMetricChange(event.target.value)}>
                  {metrics.map((metric) => <option key={metric} value={metric}>{metric}</option>)}
                </SelectInput>
              </Field>
              <Field label="排序方向">
                <SelectInput value={sortDirection} onChange={(event) => onSortDirectionChange(event.target.value)}>
                  <option value="auto">自动最优</option>
                  <option value="desc">高值优先</option>
                  <option value="asc">低值优先</option>
                </SelectInput>
              </Field>
            </div>
            <button className="secondary-button w-full" onClick={onRunCompare}>
              <RefreshCw className="h-4 w-4" />
              重新对比
            </button>
          </div>
        </FormCard></div> : null}
        {activePanel === 'compare-set' ? <div className="max-w-3xl lg:col-span-2"><FormCard title={selectedCompareSet ? '更新对比集合' : '保存对比集合'}>
          <form className="space-y-2" onSubmit={saveCompareSet}>
            <Field label="Project">
              <SelectInput required disabled={Boolean(selectedCompareSet)} value={form.project_id} onChange={(event) => updateCompareSetProject(event.target.value)}>
                <option value="" disabled>{t("Select project")}</option>
                {(data?.projects || []).map((project) => <option key={project.id} value={project.id}>{project.key}</option>)}
              </SelectInput>
            </Field>
            <Field label="Research">
              <SelectInput value={form.research_id} onChange={(event) => setForm((current) => ({ ...current, research_id: event.target.value }))}>
                <option value="">{t("Project-level")}</option>
                {researchOptions.map((research) => <option key={research.id} value={research.id}>{research.key}</option>)}
              </SelectInput>
            </Field>
            <Field label="名称"><TextInput required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="baseline-compare" /></Field>
            <InlineError message={error || (selectedIds.length ? null : 'Select at least one run.')} />
            <SubmitButton loading={loading}>{selectedCompareSet ? '更新对比集合' : '保存对比集合'}</SubmitButton>
            {selectedCompareSet ? <button className="secondary-button w-full" type="button" onClick={onClearCompareSet}>另存为新的对比集合</button> : null}
          </form>
        </FormCard></div> : null}
        <div className={activePanel ? 'lg:col-span-2' : 'lg:col-span-2'}>
          <BatchNoteForm selectedIds={selectedIds} onChanged={onChanged} />
        </div>
      </div>
    </Panel>
  );
}

function CompareSetListPanel({ compareSets, selectedCompareSet, onRun }) {
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const filteredCompareSets = compareSets.filter((compareSet) => !normalizedQuery || compareSetSearchText(compareSet).includes(normalizedQuery));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="已保存的对比集合" icon={ListTree} />
      <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1fr_auto]">
        <Field label="搜索对比集合"><TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名称、指标、序列、run id" /></Field>
        <div className="flex items-end text-xs font-semibold text-muted">{filteredCompareSets.length} / {compareSets.length} shown</div>
      </div>
      <div className="divide-y divide-line">
        {filteredCompareSets.length ? filteredCompareSets.map((compareSet) => {
          const layout = compareSet.layout_json || {};
          const metrics = listOrCsv(layout.metrics || []);
          const series = listOrCsv(layout.series || []);
          return (
            <div className={`flex items-center justify-between gap-3 px-5 py-4 ${selectedCompareSet?.id === compareSet.id ? 'bg-infoSoft/60' : ''}`} key={compareSet.id}>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{compareSet.name}</div>
                <div className="mt-1 truncate text-xs text-muted">
                  {(compareSet.run_ids_json || []).length} runs · {metrics.length ? metrics.map(shortMetricName).join(', ') : '默认指标'}{series.length ? ` · series: ${series.join(', ')}` : ''}
                </div>
              </div>
              <button className="secondary-button shrink-0" type="button" onClick={() => onRun(compareSet.id)}>
                <RefreshCw className="h-4 w-4" />
                运行
              </button>
            </div>
          );
        }) : <div className="p-5 text-sm text-muted">{compareSets.length ? 'No compare sets match the current search.' : 'No saved compare sets.'}</div>}
      </div>
    </Panel>
  );
}

function BatchComparePanel({ selectedIds, metricsText, seriesText }) {
  const defaultGroups = useMemo(() => JSON.stringify([{ name: 'default', run_ids: selectedIds }], null, 2), [selectedIds]);
  const [editing, setEditing] = useState(false);
  const [groupsText, setGroupsText] = useState(defaultGroups);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setGroupsText(defaultGroups);
  }, [defaultGroups]);
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const groups = parseCompareGroups(groupsText, metricsText, seriesText);
      const rows = await Promise.all(groups.map(async (group) => {
        try {
          const data = await apiPost('/api/v1/compare/runs', {
            run_ids: group.run_ids,
            metrics: group.metrics,
            series: group.series,
            with_config_diff: group.with_config_diff,
          });
          return { ok: true, group, data, error: null };
        } catch (err) {
          return { ok: false, group, data: null, error: err.message };
        }
      }));
      setResults(rows);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="批量对比"
        action={editing ? <button className="secondary-button" type="button" onClick={() => setEditing(false)}>{t("Close")}</button> : null}
      />
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button className={`secondary-button ${editing ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setEditing((current) => !current)}>
            <TableProperties className="h-4 w-4" />
            配置批量对比
          </button>
          <div className="text-xs font-semibold text-muted">{selectedIds.length} 个已选 runs · {results.length} 个批量结果</div>
        </div>
        {editing ? (
          <FormCard title="Groups">
            <form className="space-y-2" onSubmit={submit}>
              <Field label="Groups JSON"><TextArea className="min-h-[160px]" value={groupsText} onChange={(event) => setGroupsText(event.target.value)} /></Field>
              <InlineError message={error} />
              <SubmitButton loading={loading}>Run batch compare</SubmitButton>
            </form>
          </FormCard>
        ) : null}
        <BatchCompareResults results={results} />
      </div>
    </Panel>
  );
}

function BatchCompareResults({ results }) {
  if (!results.length) return <div className="rounded-md border border-line bg-white/45 p-4 text-sm text-muted">{t("No batch compare results yet.")}</div>;
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full min-w-[760px] border-collapse">
        <thead className="table-head">
          <tr><th className="px-4 py-3">{t("Group")}</th><th className="px-4 py-3">{t("Status")}</th><th className="px-4 py-3 text-right">{t("Runs")}</th><th className="px-4 py-3">{t("Metrics")}</th><th className="px-4 py-3">{t("Error")}</th></tr>
        </thead>
        <tbody>
          {results.map((row) => (
            <tr className="hover:bg-white/45" key={row.group.name}>
              <td className="table-cell font-semibold text-ink">{row.group.name}</td>
              <td className="table-cell"><Badge tone={row.ok ? 'positive' : 'negative'}>{row.ok ? 'ok' : 'failed'}</Badge></td>
              <td className="table-cell text-right">{row.data?.runs?.length || row.group.run_ids.length}</td>
              <td className="table-cell text-muted">{batchMetricSummary(row.data?.metrics || {}, row.group.metrics)}</td>
              <td className="table-cell text-muted">{row.error || '--'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BatchNoteForm({ selectedIds, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ kind: 'decision', author_type: 'human', summary: '', content: '', structured: '{}' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState('');
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setMessage('');
    try {
      if (!selectedIds.length) {
        setError('Select at least one run.');
        return;
      }
      const structured = parseJsonObject(form.structured);
      await Promise.all(selectedIds.map((runId) => apiPost(`/api/v1/runs/${runId}/notes`, {
        kind: form.kind,
        summary: form.summary,
        content: form.content || null,
        structured,
        author_type: form.author_type || 'human',
      })));
      setForm((current) => ({ ...current, summary: '', content: '', structured: '{}' }));
      setMessage(`Added note to ${selectedIds.length} run${selectedIds.length === 1 ? '' : 's'}.`);
      setEditing(false);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <FormCard title="Batch Note">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button className={`secondary-button ${editing ? 'border-lineStrong bg-white' : ''}`} type="button" onClick={() => setEditing((current) => !current)}>
            <ListTree className="h-4 w-4" />
            Add Batch Note
          </button>
          <div className="text-xs font-semibold text-muted">{selectedIds.length} selected runs</div>
        </div>
        {message ? <div className="rounded-md bg-positiveSoft px-3 py-2 text-xs font-semibold text-positive">{message}</div> : null}
        {!editing ? <InlineError message={selectedIds.length ? null : 'Select at least one run.'} /> : null}
        {editing ? (
          <form className="space-y-2" onSubmit={submit}>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Kind">
                <SelectInput value={form.kind} onChange={(event) => update('kind', event.target.value)}>
                  <option value="hypothesis">hypothesis</option>
                  <option value="observation">observation</option>
                  <option value="anomaly">anomaly</option>
                  <option value="decision">decision</option>
                  <option value="todo">todo</option>
                  <option value="review">review</option>
                </SelectInput>
              </Field>
              <Field label="Author">
                <SelectInput value={form.author_type} onChange={(event) => update('author_type', event.target.value)}>
                  <option value="human">human</option>
                  <option value="agent">agent</option>
                  <option value="system">system</option>
                </SelectInput>
              </Field>
            </div>
            <Field label="Summary"><TextInput required value={form.summary} onChange={(event) => update('summary', event.target.value)} placeholder="decision summary for selected runs" /></Field>
            <Field label="Content"><TextArea value={form.content} onChange={(event) => update('content', event.target.value)} /></Field>
            <Field label="Structured JSON"><TextArea value={form.structured} onChange={(event) => update('structured', event.target.value)} /></Field>
            <InlineError message={error || (selectedIds.length ? null : 'Select at least one run.')} />
            <SubmitButton loading={loading}>Add note to selected</SubmitButton>
          </form>
        ) : null}
      </div>
    </FormCard>
  );
}

function MetricMatrixPanel({ metrics, runs, baselineRunId, error }) {
  const entries = Object.entries(metrics || {});
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="关键指标表" icon={TableProperties} />
      <InlineError message={error} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Metric")}</th>
              {(runs || []).map((run) => (
                <th className="px-4 py-3 text-right" key={run.id}>{run.name}{run.id === baselineRunId ? ' (基准)' : ''}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.length ? entries.map(([metric, byRun]) => {
              const bestIds = bestRunIdsForMetric(metric, byRun);
              const baseline = toNumber(byRun?.[baselineRunId]);
              return (
                <tr className="hover:bg-white/45" key={metric}>
                  <td className="table-cell font-semibold text-ink">{shortMetricName(metric)}</td>
                  {(runs || []).map((run) => {
                    const raw = byRun?.[run.id];
                    const value = toNumber(raw);
                    const improvement = improvementFromBaseline(metric, value, baseline);
                    const isBest = bestIds.includes(run.id);
                    return (
                      <td className={`table-cell text-right ${isBest ? 'bg-positiveSoft font-semibold text-positive' : ''}`} key={run.id}>
                        <div>{formatMetric(raw)}</div>
                        {run.id !== baselineRunId && Number.isFinite(improvement.delta) ? (
                          <div className={`mt-1 text-[11px] ${improvement.delta >= 0 ? 'text-positive' : 'text-negative'}`}>
                            {formatSigned(improvement.delta)}{Number.isFinite(improvement.percent) ? ` / ${formatSigned(improvement.percent)}%` : ''}
                          </div>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              );
            }) : (
              <tr><td className="table-cell text-muted" colSpan={(runs || []).length + 1}>{t("No compare metrics returned.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {Object.keys(runById).length ? null : <div className="p-5 text-sm text-muted">{t("Select runs to compare metrics.")}</div>}
    </Panel>
  );
}

function ParetoPanel({ metrics, runs, metricNames, onSelectRun }) {
  const [xMetric, yMetric] = metricNames.length >= 2 ? metricNames : Object.keys(metrics || {});
  if (!xMetric || !yMetric || !(runs || []).length) {
    return (
      <Panel className="overflow-hidden">
        <PanelHeader title="收益风险散点" icon={Activity} />
        <div className="p-5 text-sm text-muted">{t("Select at least two metrics and one run to show Pareto scatter.")}</div>
      </Panel>
    );
  }
  const points = (runs || []).map((run) => ({
    run,
    x: toNumber(metrics?.[xMetric]?.[run.id]),
    y: toNumber(metrics?.[yMetric]?.[run.id]),
  })).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const frontierIds = paretoFrontierIds(points, xMetric, yMetric);
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="收益风险散点" icon={Activity} />
      {points.length ? (
        <div className="grid gap-4 p-4 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <ReactECharts option={paretoChartOption(points, frontierIds, xMetric, yMetric)} style={{ height: 320 }} />
          </div>
          <div className="space-y-2 xl:col-span-4">
            {points.map((point) => (
              <button
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${frontierIds.includes(point.run.id) ? 'border-positive bg-positiveSoft text-positive' : 'border-line bg-white/45 text-ink hover:bg-white/70'}`}
                key={point.run.id}
                onClick={() => onSelectRun(point.run.id)}
              >
                <div className="font-semibold">{point.run.name}</div>
                <div className="mt-1 text-xs opacity-80">{formatMetric(point.x)} / {formatMetric(point.y)}</div>
              </button>
            ))}
          </div>
        </div>
      ) : <div className="p-5 text-sm text-muted">Selected runs do not have numeric values for {xMetric} and {yMetric}.</div>}
    </Panel>
  );
}

function CompareConfigDiffPanel({ diff, runs }) {
  const entries = Object.entries(diff || {});
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="配置差异" icon={GitBranch} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">{t("Path")}</th>
              {(runs || []).map((run) => <th className="px-4 py-3" key={run.id}>{run.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {entries.length ? entries.map(([path, values]) => (
              <tr className="hover:bg-white/45" key={path}>
                <td className="table-cell font-semibold text-ink">{path}</td>
                {(runs || []).map((run) => {
                  const present = Object.prototype.hasOwnProperty.call(values || {}, run.id);
                  return (
                    <td className="table-cell text-muted" key={run.id}>
                      {present ? formatConfigValue(values[run.id]) : '--'}
                    </td>
                  );
                })}
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan={(runs || []).length + 1}>{t("Selected runs have matching config values.")}</td></tr>}
          </tbody>
        </table>
      </div>
      {Object.keys(runById).length ? null : <div className="p-5 text-sm text-muted">{t("Select runs to compare config values.")}</div>}
    </Panel>
  );
}

function ArtifactComparisonPanel({ artifacts, runs }) {
  const [selectedKey, setSelectedKey] = useState('');
  const rows = (runs || []).flatMap((run) => (artifacts?.[run.id] || []).map((artifact) => ({ run, artifact })));
  useEffect(() => {
    setSelectedKey((current) => (rows.some(({ run, artifact }) => `${run.id}:${artifact.id}` === current) ? current : rows[0] ? `${rows[0].run.id}:${rows[0].artifact.id}` : ''));
  }, [rows.map(({ run, artifact }) => `${run.id}:${artifact.id}`).join('|')]);
  const selected = rows.find(({ run, artifact }) => `${run.id}:${artifact.id}` === selectedKey) || rows[0];
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="产物对比" icon={FileText} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Artifact")}</th><th className="px-4 py-3">{t("Kind")}</th><th className="px-4 py-3">{t("Preview")}</th><th className="px-4 py-3 text-right">{t("Actions")}</th></tr></thead>
          <tbody>
            {rows.length ? rows.map(({ run, artifact }) => (
              <tr className="hover:bg-white/45" key={`${run.id}-${artifact.id}`}>
                <td className="table-cell font-semibold text-ink">{run.name}</td>
                <td className="table-cell">
                  <div className="font-semibold text-ink">{artifact.name}</div>
                  <div className="mt-1 text-xs text-muted">{artifact.filename || '--'} · {formatBytes(artifact.size_bytes)}</div>
                </td>
                <td className="table-cell text-muted">{artifact.kind}</td>
                <td className="table-cell"><ArtifactPreviewSummary preview={artifact.preview_json || {}} /></td>
                <td className="table-cell text-right">
                  <button className="secondary-button mr-2 inline-flex" type="button" onClick={() => setSelectedKey(`${run.id}:${artifact.id}`)}>
                    <FileText className="h-4 w-4" />Preview
                  </button>
                  <a className="secondary-button inline-flex" href={artifactContentUrl(artifact.id)} target="_blank" rel="noreferrer">
                    <ExternalLink className="h-4 w-4" />Open
                  </a>
                  <a className="secondary-button ml-2 inline-flex" href={artifactContentUrl(artifact.id)} download={artifact.filename || artifact.name}>
                    <Download className="h-4 w-4" />Download
                  </a>
                </td>
              </tr>
            )) : (
              <tr><td className="table-cell text-muted" colSpan="5">{t("No artifacts returned for compared runs.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {selected ? (
        <div className="border-t border-line p-4">
          <div className="mb-3">
            <div className="text-sm font-semibold text-ink">{selected.artifact.name}</div>
            <div className="mt-1 text-xs text-muted">{selected.run.name} · {selected.artifact.kind} · {selected.artifact.filename || '--'}</div>
          </div>
          <ArtifactPreview detail={selected.artifact} />
        </div>
      ) : null}
    </Panel>
  );
}

function ComparePrimarySeriesPanel({ series, runs, onSelectRun }) {
  const entry = comparePrimarySeriesEntry(series, runs);
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="主曲线重叠" icon={LineChart} />
      {entry ? (
        <div className="space-y-4 p-5">
          <ReactECharts option={seriesChartOption(entry.name, entry.byRun, runById)} style={{ height: 340 }} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse">
              <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Series")}</th><th className="px-4 py-3">{t("Mode")}</th><th className="px-4 py-3 text-right">{t("Rows")}</th><th className="px-4 py-3">{t("Value")}</th></tr></thead>
              <tbody>
                {Object.entries(entry.byRun || {}).map(([runId, item]) => (
                  <tr className="hover:bg-white/45" key={runId}>
                    <td className="table-cell"><button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(runId)} type="button">{runById[runId]?.name || runId}</button></td>
                    <td className="table-cell text-muted">{item.artifact_name || item.name || entry.name}</td>
                    <td className="table-cell text-muted">{seriesValueMode({ ...item, name: item.name || entry.name }, Array.isArray(item.y) ? item.y[0] : item.y) || '--'}</td>
                    <td className="table-cell text-right">{item.rows?.length || 0}</td>
                    <td className="table-cell text-muted">{Array.isArray(item.y) ? item.y.join(', ') : item.y || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : <div className="p-8 text-center text-sm font-semibold text-muted">{t("No Series Data Available")}</div>}
    </Panel>
  );
}

function CompareDrawdownPanel({ series, runs, onSelectRun }) {
  const entry = compareDrawdownSeriesEntry(series, runs);
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="回撤重叠" icon={Activity} />
      {entry ? (
        <div className="space-y-4 p-5">
          <ReactECharts option={seriesChartOption(entry.name, entry.byRun, runById)} style={{ height: 340 }} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse">
              <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">Series</th><th className="px-4 py-3 text-right">Rows</th><th className="px-4 py-3">Value</th></tr></thead>
              <tbody>
                {Object.entries(entry.byRun || {}).map(([runId, item]) => (
                  <tr className="hover:bg-white/45" key={runId}>
                    <td className="table-cell"><button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(runId)} type="button">{runById[runId]?.name || runId}</button></td>
                    <td className="table-cell text-muted">{item.artifact_name || item.name || entry.name}</td>
                    <td className="table-cell text-right">{item.rows?.length || 0}</td>
                    <td className="table-cell text-muted">{Array.isArray(item.y) ? item.y.join(', ') : item.y || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : <div className="p-8 text-center text-sm font-semibold text-muted">No Drawdown Series Available</div>}
    </Panel>
  );
}

function comparePrimarySeriesEntry(series, runs) {
  const byRun = {};
  for (const run of runs || []) {
    const selected = comparePrimarySeriesForRun(series, run.id);
    if (selected) byRun[run.id] = selected;
  }
  return Object.keys(byRun).length ? { name: 'Primary Curve', byRun } : null;
}

function compareDrawdownSeriesEntry(series, runs) {
  const byRun = {};
  for (const run of runs || []) {
    const selected = compareDrawdownSeriesForRun(series, run.id);
    if (selected) byRun[run.id] = selected;
  }
  return Object.keys(byRun).length ? { name: 'Drawdown', byRun } : null;
}

function comparePrimarySeriesForRun(series, runId) {
  const candidates = Object.entries(series || {}).flatMap(([name, byRun]) => {
    const item = byRun?.[runId];
    return item ? [{ name, item }] : [];
  });
  if (!candidates.length) return null;
  const ranked = candidates
    .map(({ name, item }) => ({ name, item, rank: comparePrimarySeriesRank(name, item) }))
    .filter((candidate) => candidate.rank < 100)
    .sort((left, right) => left.rank - right.rank || String(left.name).localeCompare(String(right.name)));
  const selected = ranked[0];
  return selected ? { ...selected.item, name: selected.name } : null;
}

function compareDrawdownSeriesForRun(series, runId) {
  const candidates = Object.entries(series || {}).flatMap(([name, byRun]) => {
    const item = byRun?.[runId];
    return item ? [{ name, item }] : [];
  });
  const selected = candidates
    .filter(({ name, item }) => compareDrawdownSeriesRank(name, item) < 100)
    .sort((left, right) => compareDrawdownSeriesRank(left.name, left.item) - compareDrawdownSeriesRank(right.name, right.item))[0];
  return selected ? { ...selected.item, name: selected.name } : null;
}

function comparePrimarySeriesRank(name, item) {
  const text = [name, item?.artifact_name, item?.mode, ...(Array.isArray(item?.y) ? item.y : [item?.y])].filter(Boolean).join(' ').toLowerCase();
  if (/drawdown|\bdd\b/.test(text)) return 100;
  if (/primary_curve|equity_curve|\bequity\b|\bnav\b|net_value/.test(text)) return 0;
  if (/return|ret|pnl|profit|change|series_values/.test(text)) return 1;
  return 100;
}

function compareDrawdownSeriesRank(name, item) {
  const text = [name, item?.artifact_name, item?.mode, ...(Array.isArray(item?.y) ? item.y : [item?.y])].filter(Boolean).join(' ').toLowerCase();
  if (/drawdown|maximum_drawdown|\bdd\b/.test(text)) return 0;
  return 100;
}

function SeriesPreviewPanel({ series, runs, onSelectRun }) {
  const entries = Object.entries(series || {});
  if (!entries.length) {
    return (
      <Panel className="overflow-hidden">
        <PanelHeader title="全部序列明细" icon={LineChart} />
        <div className="p-5 text-sm text-muted">{t("No series artifacts found for the selected runs.")}</div>
      </Panel>
    );
  }
  const runById = Object.fromEntries((runs || []).map((run) => [run.id, run]));
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="全部序列明细" icon={LineChart} />
      <div className="space-y-5 p-5">
        {entries.map(([name, byRun]) => (
          <div className="rounded-md border border-line bg-white/45 p-4" key={name}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-ink">{name}</div>
                <div className="mt-1 text-xs text-muted">{Object.keys(byRun || {}).length} runs with preview data</div>
              </div>
            </div>
            <ReactECharts option={seriesChartOption(name, byRun, runById)} style={{ height: 280 }} />
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead className="table-head"><tr><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">X</th><th className="px-4 py-3">Y</th><th className="px-4 py-3">{t("Preview Rows")}</th><th className="px-4 py-3">{t("Artifact")}</th></tr></thead>
                <tbody>
                  {Object.entries(byRun || {}).map(([runId, item]) => (
                    <tr className="hover:bg-white/45" key={runId}>
                      <td className="table-cell"><button className="font-semibold text-ink hover:text-info" onClick={() => onSelectRun(runId)}>{runById[runId]?.name || runId}</button></td>
                      <td className="table-cell text-muted">{item.x || '--'}</td>
                      <td className="table-cell text-muted">{Array.isArray(item.y) ? item.y.join(', ') : item.y || '--'}</td>
                      <td className="table-cell text-right">{item.rows?.length || 0}</td>
                      <td className="table-cell text-muted">{item.artifact_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function seriesChartOption(name, byRun, runById) {
  const seriesItems = Object.entries(byRun || {}).flatMap(([runId, item]) => {
    const yKeys = Array.isArray(item.y) ? item.y : [item.y].filter(Boolean);
    const xKey = item.x;
    return yKeys.map((yKey) => {
      const data = seriesPreviewData(name, item, yKey, xKey);
      const runName = runById[runId]?.name || runId;
      return {
        name: yKeys.length > 1 ? `${runName} / ${yKey}` : runName,
        type: 'line',
        showSymbol: false,
        data,
      };
    });
  }).filter((item) => item.data.length);
  const allPoints = seriesItems.flatMap((item) => item.data || []);
  const xAxisType = shouldUseTimeAxis(allPoints) ? 'time' : 'category';
  const categoryValues = xAxisType === 'category' ? sortedUniqueChartXValues(allPoints.map((point) => point?.[0])) : undefined;
  return {
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    grid: { top: 42, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: xAxisType,
      boundaryGap: false,
      ...(categoryValues ? { data: categoryValues } : {}),
    },
    yAxis: { type: 'value', scale: true },
    series: seriesItems.length ? seriesItems : [{ name, type: 'line', showSymbol: false, data: [] }],
  };
}

function seriesPreviewData(seriesName, item, yKey, xKey) {
  const valueMode = seriesValueMode({ ...item, name: seriesName }, yKey);
  let compounded = 1;
  let cumulative = 0;
  const points = sortedChartRows(item.rows || [], xKey).map(({ row, x }) => {
    const raw = toNumber(row?.[yKey]);
    if (!Number.isFinite(raw)) return null;
    if (valueMode === 'period_return') {
      compounded *= 1 + raw;
      return [x, compounded - 1];
    }
    if (valueMode === 'absolute_change') {
      cumulative += raw;
      return [x, cumulative];
    }
    return [x, raw];
  }).filter(Boolean);
  return normalizeChartPoints(points);
}

function bestComparedRun(metric, byRun, runs) {
  const candidates = (runs || []).map((run) => ({ run, value: toNumber(byRun?.[run.id]) })).filter((item) => Number.isFinite(item.value));
  if (!candidates.length) return null;
  const direction = metricDirection(metric, candidates.map((item) => item.value));
  return candidates.sort((left, right) => (direction === 'asc' ? left.value - right.value : right.value - left.value))[0];
}

function compareRecommendation({ runs, bestMetricRun, bestDrawdownRun, baselineRun, primaryMetric, drawdownMetric, metrics }) {
  if ((runs || []).length < 2) return { tone: 'warning', text: '至少选择两个 Run 后才能形成对比结论。' };
  if (!bestMetricRun) return { tone: 'warning', text: '关键指标缺失，先补齐绩效指标后再做推进判断。' };
  const baselineValue = toNumber(metrics?.[primaryMetric]?.[baselineRun?.id]);
  const bestValue = toNumber(bestMetricRun.value);
  const drawdownValue = toNumber(metrics?.[drawdownMetric]?.[bestMetricRun.run.id]);
  const baselineName = baselineRun?.name || '基准';
  const bestName = bestMetricRun.run.name;
  if (bestMetricRun.run.id === baselineRun?.id) {
    return { tone: 'positive', text: `${baselineName} 仍是当前主指标领先方案；优先检查回撤、成本和 OOS 后决定是否继续作为 champion。` };
  }
  const improvement = improvementFromBaseline(primaryMetric, bestValue, baselineValue);
  const improvementText = Number.isFinite(improvement.delta) ? `，相对基准提升 ${formatSigned(improvement.delta)}` : '';
  const riskText = Number.isFinite(drawdownValue) ? `，该候选 ${shortMetricName(drawdownMetric)}=${formatMetric(drawdownValue)}` : '';
  const riskBestText = bestDrawdownRun ? `；风险最优为 ${bestDrawdownRun.run.name}` : '';
  return { tone: 'positive', text: `${bestName} 是当前主指标领先候选${improvementText}${riskText}${riskBestText}。建议围绕成本、OOS 和异常诊断再做 promote / iterate 决策。` };
}

function compareDiagnostics(runs, series, metrics, metricNames) {
  const diagnostics = [];
  const comparedRuns = runs || [];
  if (comparedRuns.length < 2) {
    diagnostics.push({ severity: 'warning', title: '对比对象不足', detail: 'Compare 至少需要两个 run 才能形成有效判断。' });
  }
  const primaryEntry = comparePrimarySeriesEntry(series, comparedRuns);
  const drawdownEntry = compareDrawdownSeriesEntry(series, comparedRuns);
  const primaryRunIds = new Set(Object.keys(primaryEntry?.byRun || {}));
  const drawdownRunIds = new Set(Object.keys(drawdownEntry?.byRun || {}));
  const missingPrimary = comparedRuns.filter((run) => !primaryRunIds.has(run.id));
  const missingDrawdown = comparedRuns.filter((run) => !drawdownRunIds.has(run.id));
  if (missingPrimary.length) {
    diagnostics.push({ severity: 'error', title: '部分 Run 缺少主曲线', detail: `${missingPrimary.length} 个 run 没有可识别的 equity/nav/return/pnl 主曲线，主图可能不完整。` });
  }
  if (missingDrawdown.length) {
    diagnostics.push({ severity: 'warning', title: '部分 Run 缺少回撤序列', detail: `${missingDrawdown.length} 个 run 没有可识别的 drawdown_series，回撤图可能不完整。` });
  }
  const metricCoverage = compareMetricCoverage(comparedRuns, metrics, metricNames);
  if (metricCoverage.missingCells > 0) {
    diagnostics.push({ severity: 'warning', title: '关键指标不完整', detail: `${metricCoverage.missingCells}/${metricCoverage.totalCells} 个指标单元缺失，指标表结论需要谨慎。` });
  }
  const primaryItems = Object.values(primaryEntry?.byRun || {});
  const ranges = primaryItems.map(compareSeriesRangeKey).filter(Boolean);
  if (new Set(ranges).size > 1) {
    diagnostics.push({ severity: 'warning', title: '主曲线时间区间不一致', detail: '不同 run 的主曲线起止时间不同，收益和回撤不能直接视为完全公平比较。' });
  }
  const rowCounts = primaryItems.map((item) => item.rows?.length || 0).filter(Boolean);
  if (new Set(rowCounts).size > 1) {
    diagnostics.push({ severity: 'warning', title: '主曲线行数不一致', detail: `主曲线行数分别为 ${Array.from(new Set(rowCounts)).join(', ')}，请确认样本区间和频率一致。` });
  }
  const modes = primaryItems.map((item) => seriesValueMode({ ...item, name: item.name }, Array.isArray(item.y) ? item.y[0] : item.y)).filter(Boolean);
  if (new Set(modes).size > 1) {
    diagnostics.push({ severity: 'warning', title: '收益序列模式不一致', detail: `检测到不同 mode：${Array.from(new Set(modes)).join(', ')}。nav / return / pnl 混比时需要统一解释。` });
  }
  return diagnostics;
}

function compareMetricCoverage(runs, metrics, metricNames) {
  const names = (metricNames || []).filter(Boolean);
  const totalCells = Math.max(0, (runs || []).length * names.length);
  let missingCells = 0;
  for (const metric of names) {
    for (const run of runs || []) {
      const value = metrics?.[metric]?.[run.id];
      if (value === null || value === undefined || value === '') missingCells += 1;
    }
  }
  return { totalCells, missingCells };
}

function compareSeriesRangeKey(item) {
  const rows = item?.rows || [];
  const xKey = item?.x;
  if (!rows.length || !xKey) return '';
  const first = sortedChartRows(rows, xKey)[0]?.x;
  const last = sortedChartRows(rows, xKey).slice(-1)[0]?.x;
  return first || last ? `${first}..${last}` : '';
}

function shortMetricName(metric) {
  return String(metric || '').replace(/^strategy\.summary\./, '');
}

function sortComparedRuns(runs, metrics, sortMetric, sortDirection) {
  if (!sortMetric) return runs;
  const row = metrics?.[sortMetric] || {};
  const direction = sortDirection === 'auto' ? metricDirection(sortMetric, Object.values(row).map(toNumber)) : sortDirection;
  return [...runs].sort((a, b) => {
    const av = toNumber(row[a.id]);
    const bv = toNumber(row[b.id]);
    if (!Number.isFinite(av) && !Number.isFinite(bv)) return 0;
    if (!Number.isFinite(av)) return 1;
    if (!Number.isFinite(bv)) return -1;
    return direction === 'asc' ? av - bv : bv - av;
  });
}

function mergeRunsBySelection(selectedIds, dashboardRuns, resultRuns) {
  const byId = new Map();
  (dashboardRuns || []).forEach((run) => byId.set(run.id, run));
  (resultRuns || []).forEach((run) => byId.set(run.id, { ...(byId.get(run.id) || {}), ...run }));
  return (selectedIds || []).map((id) => byId.get(id)).filter(Boolean);
}

function mergeRunsById(...runLists) {
  const byId = new Map();
  const order = [];
  runLists.flat().filter(Boolean).forEach((run) => {
    if (!byId.has(run.id)) order.push(run.id);
    byId.set(run.id, { ...(byId.get(run.id) || {}), ...run });
  });
  return order.map((id) => byId.get(id)).filter(Boolean);
}

function bestRunIdsForMetric(metric, byRun) {
  const entries = Object.entries(byRun || {}).map(([runId, value]) => [runId, toNumber(value)]).filter(([, value]) => Number.isFinite(value));
  if (!entries.length) return [];
  const direction = metricDirection(metric, entries.map(([, value]) => value));
  const best = direction === 'asc' ? Math.min(...entries.map(([, value]) => value)) : Math.max(...entries.map(([, value]) => value));
  return entries.filter(([, value]) => value === best).map(([runId]) => runId);
}

function metricDirection(metric, values = []) {
  const name = String(metric || '').toLowerCase();
  if (/drawdown|dd|loss|cost|fee|turnover|risk|vol|error|rmse|mae|latency|runtime|duration/.test(name)) {
    if (/drawdown|dd/.test(name) && values.length && values.every((value) => value <= 0)) return 'desc';
    return 'asc';
  }
  return 'desc';
}

function improvementFromBaseline(metric, value, baseline) {
  if (!Number.isFinite(value) || !Number.isFinite(baseline)) return { delta: NaN, percent: NaN };
  const direction = metricDirection(metric, [value, baseline]);
  const rawDelta = value - baseline;
  const delta = direction === 'asc' ? -rawDelta : rawDelta;
  const percent = baseline === 0 ? NaN : (delta / Math.abs(baseline)) * 100;
  return { delta, percent };
}

function paretoFrontierIds(points, xMetric, yMetric) {
  const xDirection = metricDirection(xMetric, points.map((point) => point.x));
  const yDirection = metricDirection(yMetric, points.map((point) => point.y));
  return points.filter((point) => !points.some((other) => {
    if (other.run.id === point.run.id) return false;
    const xBetterOrEqual = xDirection === 'asc' ? other.x <= point.x : other.x >= point.x;
    const yBetterOrEqual = yDirection === 'asc' ? other.y <= point.y : other.y >= point.y;
    const xStrict = xDirection === 'asc' ? other.x < point.x : other.x > point.x;
    const yStrict = yDirection === 'asc' ? other.y < point.y : other.y > point.y;
    return xBetterOrEqual && yBetterOrEqual && (xStrict || yStrict);
  })).map((point) => point.run.id);
}

function paretoChartOption(points, frontierIds, xMetric, yMetric) {
  const frontier = points.filter((point) => frontierIds.includes(point.run.id));
  const other = points.filter((point) => !frontierIds.includes(point.run.id));
  const toScatterData = (items) => items.map((point) => ({ value: [point.x, point.y], name: point.run.name }));
  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: (params) => `${params.name}<br/>${xMetric}: ${formatMetric(params.value?.[0])}<br/>${yMetric}: ${formatMetric(params.value?.[1])}`,
    },
    legend: { top: 0 },
    grid: { top: 42, left: 58, right: 24, bottom: 50 },
    xAxis: { type: 'value', name: xMetric, scale: true },
    yAxis: { type: 'value', name: yMetric, scale: true },
    series: [
      { name: 'Runs', type: 'scatter', symbolSize: 10, data: toScatterData(other) },
      { name: 'Frontier', type: 'scatter', symbolSize: 14, data: toScatterData(frontier), itemStyle: { color: '#16803d' } },
    ],
  };
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return NaN;
  const number = Number(value);
  return Number.isFinite(number) ? number : NaN;
}

function formatSigned(value) {
  if (!Number.isFinite(value)) return '--';
  const abs = Math.abs(value);
  return `${value >= 0 ? '+' : '-'}${formatMetric(abs)}`;
}

function RunSelectionTable({ runs, selectedIds, onToggle, onSelectRun }) {
  const projects = Array.from(new Set((runs || []).map((run) => run.project_key).filter(Boolean))).sort();
  const statuses = Array.from(new Set((runs || []).map((run) => run.status).filter(Boolean))).sort();
  const [project, setProject] = useState('all');
  const [status, setStatus] = useState('all');
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (project !== 'all' && !projects.includes(project)) setProject('all');
  }, [project, projects.join('|')]);
  useEffect(() => {
    if (status !== 'all' && !statuses.includes(status)) setStatus('all');
  }, [status, statuses.join('|')]);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredRuns = (runs || []).filter((run) => {
    if (project !== 'all' && run.project_key !== project) return false;
    if (status !== 'all' && run.status !== status) return false;
    if (!normalizedQuery) return true;
    return runSelectionSearchText(run).includes(normalizedQuery);
  });
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Run Selection" icon={TableProperties} />
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 lg:grid-cols-[180px_180px_minmax(260px,1fr)]">
          <Field label="Project">
            <SelectInput value={project} onChange={(event) => setProject(event.target.value)}>
              <option value="all">{t("All projects")}</option>
              {projects.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <Field label="Status">
            <SelectInput value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">{t("All statuses")}</option>
              {statuses.map((item) => <option key={item} value={item}>{tStatus(item)}</option>)}
            </SelectInput>
          </Field>
          <Field label="Search runs">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="run, research, branch, tag, config" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">{filteredRuns.length} shown · {(runs || []).length} total · {selectedIds.length} selected</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse">
          <thead className="table-head"><tr><th className="px-4 py-3">{t("Use")}</th><th className="px-4 py-3">{t("Run")}</th><th className="px-4 py-3">{t("Project")}</th><th className="px-4 py-3">{t("Branch")}</th><th className="px-4 py-3 text-right">{t("Sharpe")}</th><th className="px-4 py-3 text-right">{t("Updated")}</th></tr></thead>
          <tbody>
            {filteredRuns.length ? filteredRuns.map((run) => (
              <tr className="hover:bg-white/45" key={run.id}>
                <td className="table-cell"><input checked={selectedIds.includes(run.id)} className="h-4 w-4 accent-charcoal" onChange={() => onToggle(run.id)} type="checkbox" /></td>
                <td className="table-cell"><button className="font-semibold text-ink hover:underline" onClick={() => onSelectRun(run.id)}>{run.name}</button></td>
                <td className="table-cell text-muted">{run.project_key || '--'}</td>
                <td className="table-cell text-muted">{run.branch_key || run.branch_id}</td>
                <td className="table-cell text-right font-semibold text-positive">{formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}</td>
                <td className="table-cell text-right text-muted">{formatDate(run.updated_at)}</td>
              </tr>
            )) : <tr><td className="table-cell text-muted" colSpan="6">{t("No runs match the current filters.")}</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function runSelectionSearchText(run) {
  return [
    run.id,
    run.name,
    run.title,
    run.status,
    run.project_key,
    run.research_key,
    run.branch_key,
    run.branch_id,
    run.created_by_type,
    run.created_by_id,
    ...(run.tags || []),
    configSummary(run.config_json),
    JSON.stringify(run.summary_json || {}),
  ].filter(Boolean).join(' ').toLowerCase();
}

function sweepSearchText(sweep, branch = null) {
  return [
    sweep.id,
    sweep.name,
    sweep.status,
    sweep.branch_id,
    branch?.key,
    branch?.title,
    JSON.stringify(sweep.objective_json || {}),
    JSON.stringify(sweep.search_space_json || {}),
  ].filter(Boolean).join(' ').toLowerCase();
}

function searchViewSearchText(view) {
  return [
    view.id,
    view.name,
    view.description,
    view.project_id,
    JSON.stringify(view.filters_json || {}),
  ].filter(Boolean).join(' ').toLowerCase();
}

function buildCompareWorkbenchRows(compareSets, data) {
  const projectById = Object.fromEntries((data?.projects || []).map((project) => [project.id, project]));
  const researchById = Object.fromEntries((data?.researches || []).map((research) => [research.id, research]));
  return (compareSets || []).map((compareSet) => {
    const project = projectById[compareSet.project_id] || null;
    const research = researchById[compareSet.research_id] || null;
    const stage = compareSetStageLabel(compareSet);
    const row = {
      ...compareSet,
      project,
      research,
      stage,
      runCount: (compareSet.run_ids_json || []).length,
    };
    row.searchText = compareWorkbenchSearchText(row);
    return row;
  }).sort((a, b) => {
    const projectOrder = (entityName(a.project) || a.project_id || '').localeCompare(entityName(b.project) || b.project_id || '');
    if (projectOrder) return projectOrder;
    const researchOrder = (entityName(a.research) || '').localeCompare(entityName(b.research) || '');
    if (researchOrder) return researchOrder;
    const stageOrder = String(a.stage || '').localeCompare(String(b.stage || ''));
    if (stageOrder) return stageOrder;
    return dateMillis(b.created_at) - dateMillis(a.created_at);
  });
}

function compareWorkbenchSearchText(row) {
  return [
    compareSetSearchText(row),
    row.project?.key,
    row.project?.title,
    row.research?.key,
    row.research?.title,
    row.stage,
  ].filter(Boolean).join(' ').toLowerCase();
}

function compareSetStageLabel(compareSet) {
  const layout = compareSet.layout_json || {};
  const explicit = layout.stage || layout.phase || layout.step || layout.milestone;
  if (explicit) return String(explicit);
  const name = String(compareSet.name || '').trim();
  const match = name.match(/(?:阶段|phase|stage|step|round|batch)[\s:_-]*([\w\u4e00-\u9fa5.-]+)/i);
  if (match) return match[0];
  return compareSet.research_id ? '未标注阶段' : '项目级对比';
}

function compareSetSearchText(compareSet) {
  const layout = compareSet.layout_json || {};
  return [
    compareSet.id,
    compareSet.name,
    compareSet.project_id,
    compareSet.research_id,
    compareSetStageLabel(compareSet),
    ...(compareSet.run_ids_json || []),
    ...listOrCsv(layout.metrics || []),
    ...listOrCsv(layout.series || []),
    JSON.stringify(layout.result_summary || {}),
  ].filter(Boolean).join(' ').toLowerCase();
}

function commonValue(values) {
  const normalized = values.filter(Boolean);
  if (!normalized.length) return '';
  return normalized.every((value) => value === normalized[0]) ? normalized[0] : '';
}

function compareSetLayoutSummary(compareSet) {
  const layout = compareSet.layout_json || {};
  const metrics = listOrCsv(layout.metrics || []);
  const series = listOrCsv(layout.series || []);
  const parts = [];
  if (metrics.length) parts.push(`${metrics.length} metrics`);
  if (series.length) parts.push(`${series.length} series`);
  return parts.length ? parts.join(' / ') : '--';
}

function savedItemSearchText(item, detail = '') {
  return [
    item.id,
    item.name,
    item.description,
    item.project_id,
    item.research_id,
    detail,
    JSON.stringify(item.filters_json || {}),
    JSON.stringify(item.layout_json || {}),
    ...(item.run_ids_json || []),
  ].filter(Boolean).join(' ').toLowerCase();
}

function Hero({ eyebrow, title, description, action }) {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {eyebrow ? <div className="mb-2 text-xs font-semibold uppercase text-muted">{tx(eyebrow)}</div> : null}
          <h1 className="break-words text-3xl font-semibold text-ink md:text-4xl">{tx(title)}</h1>
          {description ? <p className="mt-3 max-w-5xl text-sm leading-6 text-muted">{tx(description)}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </Panel>
  );
}

function MetricsTable({ rows, onOpenDataMetric }) {
  const groups = groupMetricRowsByNamespace(rows);
  if (!rows.length) return <div className="p-5 text-sm text-muted">{t("No metrics yet.")}</div>;
  return (
    <div className="divide-y divide-line">
      {groups.map((group) => (
        <div key={group.namespace}>
          <div className="flex items-center justify-between gap-3 bg-white/35 px-5 py-3">
            <h3 className="text-sm font-semibold text-ink">{group.namespace}</h3>
            <div className="text-xs font-semibold text-muted">{group.rows.length} metrics</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px] border-collapse">
              <thead className="table-head"><tr><th className="px-4 py-3">{t("Metric")}</th><th className="px-4 py-3">{t("Type")}</th><th className="px-4 py-3 text-right">{t("Value / Shape")}</th><th className="px-4 py-3">{t("Point")}</th><th className="px-4 py-3">{t("Source")}</th></tr></thead>
              <tbody>
                {group.rows.map((row) => (
                  <tr key={row.id} className="hover:bg-white/45">
                    <td className="table-cell font-semibold text-ink">
                      {row.type === 'scalar' ? row.key : (
                        <button className="font-semibold text-ink hover:underline" type="button" onClick={() => onOpenDataMetric(row)}>{row.key}</button>
                      )}
                    </td>
                    <td className="table-cell text-muted">{row.type}</td>
                    <td className="table-cell text-right">{row.displayValue}</td>
                    <td className="table-cell text-muted">{row.point || '--'}</td>
                    <td className="table-cell text-muted">{row.source || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

function metricDisplayRows(metrics, artifacts) {
  const scalarRows = (metrics || []).map((metric) => {
    const displayValue = metricDisplayValue(metric);
    return {
      id: `metric-${metric.id}`,
      namespace: metric.namespace || 'default',
      key: metric.key,
      type: 'scalar',
      displayValue,
      point: metricPointLabel(metric),
      source: metric.client_event_id || '--',
      metric,
      searchText: metricSearchText(metric),
    };
  });
  const dataRows = (artifacts || []).map(metricArtifactRow).filter(Boolean);
  return [...scalarRows, ...dataRows].sort((left, right) => (
    left.namespace.localeCompare(right.namespace)
    || left.key.localeCompare(right.key)
    || left.type.localeCompare(right.type)
  ));
}

function metricArtifactRow(artifact) {
  const metadata = artifact.metadata_json || {};
  const metric = metadata.metric && typeof metadata.metric === 'object' ? metadata.metric : null;
  const series = metadata.series && typeof metadata.series === 'object' ? metadata.series : null;
  if (!metric && !series?.namespace) return null;
  const namespace = metric?.namespace || series?.namespace || 'default';
  const key = metric?.key || series?.name || artifact.name;
  const type = metric?.kind || (series ? 'series' : 'table');
  const rows = Array.isArray(artifact.preview_json?.rows) ? artifact.preview_json.rows : [];
  const columns = Array.isArray(artifact.preview_json?.columns) ? artifact.preview_json.columns : [];
  const rowCount = Number(artifact.preview_json?.row_count);
  const displayValue = [
    Number.isFinite(rowCount) ? `${rowCount} rows` : rows.length ? `${rows.length} preview rows` : null,
    columns.length ? `${columns.length} columns` : null,
  ].filter(Boolean).join(' · ') || artifact.kind || '--';
  return {
    id: `artifact-${artifact.id}`,
    namespace,
    key,
    type,
    displayValue,
    point: metric?.point || metric?.event || series?.mode || '--',
    source: artifact.name,
    artifact,
    metricBinding: metric,
    seriesBinding: series,
    searchText: [
      namespace,
      key,
      type,
      displayValue,
      artifact.name,
      artifact.kind,
      artifact.filename,
      JSON.stringify(metadata),
      JSON.stringify(artifact.preview_json || {}),
    ].filter(Boolean).join(' ').toLowerCase(),
  };
}

function groupMetricRowsByNamespace(rows) {
  const groups = new Map();
  for (const row of rows || []) {
    const namespace = row.namespace || 'default';
    groups.set(namespace, [...(groups.get(namespace) || []), row]);
  }
  return Array.from(groups.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([namespace, rows]) => ({ namespace, rows }));
}

function metricPointLabel(metric) {
  const parts = [
    metric.point_event_name || metric.point_kind,
    metric.point_step !== null && metric.point_step !== undefined ? `step ${metric.point_step}` : null,
    metric.point_timestamp ? formatDate(metric.point_timestamp) : null,
    metric.point_coord_json && Object.keys(metric.point_coord_json).length ? compactKeyValueSummary(metric.point_coord_json) : null,
  ].filter(Boolean);
  return parts.join(' · ') || '--';
}

function metricDisplayValue(metric) {
  if (metric.value_number !== null && metric.value_number !== undefined) return formatMetric(metric.value_number);
  if (metric.value_string !== null && metric.value_string !== undefined) return metric.value_string;
  if (metric.value_bool !== null && metric.value_bool !== undefined) return metric.value_bool ? 'true' : 'false';
  return '--';
}

function metricSearchText(metric) {
  return [
    metric.id,
    metric.namespace,
    metric.key,
    metricDisplayValue(metric),
    metric.point_kind,
    metric.point_event_name,
    metric.point_step,
    metric.point_timestamp,
    JSON.stringify(metric.point_coord_json || {}),
    metric.client_event_id,
  ].filter((value) => value !== null && value !== undefined && value !== '').join(' ').toLowerCase();
}

function MetricDataModal({ item, onClose }) {
  const [detail, setDetail] = useState(item.artifact);
  const [rows, setRows] = useState(() => Array.isArray(item.artifact.preview_json?.rows) ? item.artifact.preview_json.rows : []);
  const [markdownText, setMarkdownText] = useState('');
  const [error, setError] = useState(null);
  const [activeView, setActiveView] = useState(() => artifactDataViews(item.artifact, item)[0] || 'table');
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    let cancelled = false;
    setDetail(item.artifact);
    setRows(Array.isArray(item.artifact.preview_json?.rows) ? item.artifact.preview_json.rows : []);
    setMarkdownText('');
    setError(null);
    setActiveView(artifactDataViews(item.artifact, item)[0] || 'table');
    apiGet(`/api/v1/artifacts/${item.artifact.id}`)
      .then(async (payload) => {
        if (cancelled) return;
        setDetail(payload);
        const views = artifactDataViews(payload, item);
        setActiveView((current) => (views.includes(current) ? current : views[0] || 'table'));
        if (isMarkdownArtifact(payload)) {
          const text = await loadArtifactText(payload);
          if (!cancelled) setMarkdownText(text || markdownTextFromPreview(payload.preview_json));
        } else if (isImageArtifact(payload, payload.preview_json || {})) {
          if (!cancelled) setRows([]);
        } else {
          const parsedRows = await loadArtifactRows(payload);
          if (!cancelled) setRows(parsedRows.length ? parsedRows : (Array.isArray(payload.preview_json?.rows) ? payload.preview_json.rows : []));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelled = true;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [item.artifact.id]);
  const columns = metricDataColumns(rows, detail.preview_json || {});
  const availableViews = artifactDataViews(detail, item);
  const showTabs = availableViews.length > 1;
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-ink/25 px-4 py-16 backdrop-blur-sm" role="dialog" aria-modal="true" onPointerDown={onClose}>
      <div className="max-h-[calc(100vh-8rem)] w-full max-w-5xl overflow-hidden rounded-md border border-line bg-panel shadow-xl" onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-ink">{item.namespace}.{item.key}</h2>
            <div className="mt-1 truncate text-xs text-muted">{artifactDataSubtitle(detail, rows)}</div>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close metric details">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
        {showTabs ? (
          <div className="flex gap-1 border-b border-line px-4 py-3">
            {availableViews.map((view) => (
              <button
                className={`rounded-md px-3 py-2 text-sm font-semibold transition ${activeView === view ? 'bg-[#e8ebe7] text-ink' : 'text-muted hover:bg-[#f3f4f1] hover:text-ink'}`}
                key={view}
                type="button"
                onClick={() => setActiveView(view)}
              >
                {artifactDataViewLabel(view)}
              </button>
            ))}
          </div>
        ) : null}
        <div className="max-h-[calc(100vh-18rem)] overflow-y-auto p-4">
          <InlineError message={error} />
          {renderArtifactDataView(activeView, { item, detail, rows, columns, markdownText })}
        </div>
      </div>
    </div>
  );
}

function renderArtifactDataView(view, { item, detail, rows, columns, markdownText }) {
  if (view === 'image') return <ImageArtifactView artifact={detail} />;
  if (view === 'markdown') return <MarkdownDocument text={markdownText || markdownTextFromPreview(detail.preview_json)} />;
  if (view === 'plot') return <MetricDataPlot item={item} rows={rows} columns={columns} />;
  return <MetricDataTable columns={columns} rows={rows} />;
}

function artifactDataViews(artifact, item = {}) {
  const preview = artifact?.preview_json || {};
  if (isImageArtifact(artifact, preview)) return ['image'];
  if (isMarkdownArtifact(artifact)) return ['markdown'];
  if (isSeriesResultItem(item, artifact)) return ['table', 'plot'];
  return ['table'];
}

function artifactDataViewLabel(view) {
  return {
    image: 'Image',
    markdown: 'Report',
    plot: 'Plot',
    table: 'Table',
  }[view] || view;
}

function artifactDataSubtitle(artifact, rows) {
  const preview = artifact?.preview_json || {};
  const parts = [artifact?.name, artifact?.kind];
  if (isImageArtifact(artifact, preview)) {
    parts.push(['image', preview.width && preview.height ? `${preview.width}x${preview.height}` : null].filter(Boolean).join(' · '));
  } else if (isMarkdownArtifact(artifact)) {
    parts.push('report');
  } else {
    const rowCount = Number(preview.row_count);
    parts.push(Number.isFinite(rowCount) ? `${rowCount} rows` : `${rows.length || 0} rows`);
  }
  return parts.filter(Boolean).join(' · ');
}

function ImageArtifactView({ artifact }) {
  if (!artifact?.id) {
    return <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No image available.")}</div>;
  }
  return (
    <div className="overflow-hidden rounded-md border border-line bg-white/55">
      <img className="max-h-[calc(100vh-18rem)] w-full object-contain" src={artifactContentUrl(artifact.id)} alt={artifact.name || 'artifact image'} />
    </div>
  );
}

async function loadArtifactRows(artifact) {
  try {
    const response = await fetch(artifactContentUrl(artifact.id));
    if (!response.ok) return [];
    const text = await response.text();
    if (looksLikeJsonArtifact(artifact)) return rowsFromJsonText(text);
    if (looksLikeCsvArtifact(artifact)) return parseCsvRows(text);
    return rowsFromJsonText(text);
  } catch {
    return [];
  }
}

async function loadArtifactText(artifact) {
  try {
    const response = await fetch(artifactContentUrl(artifact.id));
    if (!response.ok) return '';
    return await response.text();
  } catch {
    return '';
  }
}

function isMarkdownArtifact(artifact) {
  const name = String(artifact?.filename || artifact?.name || '').toLowerCase();
  const kind = String(artifact?.kind || '').toLowerCase();
  const mimeType = String(artifact?.mime_type || '').toLowerCase();
  return kind.includes('markdown') || mimeType.includes('markdown') || name.endsWith('.md') || name.endsWith('.markdown');
}

function markdownTextFromPreview(preview) {
  const rows = Array.isArray(preview?.rows) ? preview.rows : [];
  if (!rows.length) return '';
  return rows.map((row) => {
    if (typeof row === 'string') return row;
    if (row && typeof row === 'object') {
      return row.markdown || row.content || row.text || row.line || Object.values(row).join(' ');
    }
    return String(row ?? '');
  }).join('\n');
}

function MarkdownDocument({ text }) {
  if (!String(text || '').trim()) {
    return <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No markdown content available.")}</div>;
  }
  return (
    <div className="markdown-document max-h-[calc(100vh-18rem)] overflow-auto rounded-md border border-line bg-white/55 p-5 text-sm leading-7 text-ink">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function looksLikeJsonArtifact(artifact) {
  const name = String(artifact.filename || '').toLowerCase();
  return name.endsWith('.json') || String(artifact.mime_type || '').includes('json');
}

function looksLikeCsvArtifact(artifact) {
  const name = String(artifact.filename || '').toLowerCase();
  return name.endsWith('.csv') || String(artifact.mime_type || '').includes('csv') || String(artifact.mime_type || '').startsWith('text/');
}

function rowsFromJsonText(text) {
  try {
    const payload = JSON.parse(text);
    if (Array.isArray(payload)) return payload.filter((row) => row && typeof row === 'object');
    if (Array.isArray(payload?.rows)) return payload.rows.filter((row) => row && typeof row === 'object');
  } catch {
    return [];
  }
  return [];
}

function parseCsvRows(text) {
  const lines = String(text || '').split(/\r?\n/).filter((line) => line.trim() !== '');
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? '']));
  });
}

function parseCsvLine(line) {
  const values = [];
  let current = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ',' && !quoted) {
      values.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  values.push(current);
  return values;
}

function metricDataColumns(rows, preview) {
  const previewColumns = Array.isArray(preview.columns) ? preview.columns : [];
  if (previewColumns.length) return prioritizeTemporalColumns(previewColumns);
  const columns = new Set();
  for (const row of rows || []) {
    Object.keys(row || {}).forEach((key) => columns.add(key));
    if (columns.size >= 24) break;
  }
  return prioritizeTemporalColumns(Array.from(columns));
}

function prioritizeTemporalColumns(columns) {
  return (columns || [])
    .map((column, index) => ({ column, index, rank: temporalColumnRank(column) }))
    .sort((left, right) => {
      if (left.rank !== right.rank) return left.rank - right.rank;
      return left.index - right.index;
    })
    .map((entry) => entry.column);
}

function temporalColumnRank(column) {
  const order = ['DATE', 'DATETIME', 'TRADE_DATE', 'END_DATE', 'TIME'];
  const normalized = String(column || '').trim().toUpperCase();
  const index = order.indexOf(normalized);
  return index === -1 ? order.length : index;
}

function MetricDataTable({ columns, rows }) {
  const [sort, setSort] = useState({ column: null, direction: 'asc' });
  if (!rows.length || !columns.length) return <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No table data available.")}</div>;
  const visibleColumns = columns.slice(0, 12);
  const sortedRows = useMemo(() => sortMetricDataRows(rows, sort), [rows, sort.column, sort.direction]);
  const toggleSort = (column) => {
    setSort((current) => (
      current.column === column
        ? { column, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { column, direction: 'asc' }
    ));
  };
  return (
    <div className="max-h-[520px] overflow-auto rounded-md border border-line">
      <table className="w-full min-w-[760px] border-collapse">
        <thead className="table-head">
          <tr>
            {visibleColumns.map((column) => {
              const active = sort.column === column;
              const SortIcon = active ? (sort.direction === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
              return (
                <th className="px-4 py-3" key={column} aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  <button
                    className="inline-flex max-w-full items-center gap-1 text-left font-semibold text-muted transition hover:text-ink"
                    type="button"
                    onClick={() => toggleSort(column)}
                    title={`Sort by ${column}`}
                  >
                    <span className="truncate">{formatTableHeader(column)}</span>
                    <SortIcon className={`h-3.5 w-3.5 shrink-0 ${active ? 'text-ink' : 'text-muted/60'}`} />
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.slice(0, 500).map((row, index) => (
            <tr className="hover:bg-white/45" key={index}>
              {visibleColumns.map((column) => <td className="table-cell text-muted" key={column}>{formatPreviewCell(row?.[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function sortMetricDataRows(rows, sort) {
  if (!sort?.column) return rows;
  const direction = sort.direction === 'desc' ? -1 : 1;
  return [...(rows || [])].map((row, index) => ({ row, index })).sort((left, right) => {
    const compared = compareMetricDataValues(left.row?.[sort.column], right.row?.[sort.column]);
    return compared === 0 ? left.index - right.index : compared * direction;
  }).map((item) => item.row);
}

function compareMetricDataValues(left, right) {
  const leftEmpty = isEmptySortValue(left);
  const rightEmpty = isEmptySortValue(right);
  if (leftEmpty && rightEmpty) return 0;
  if (leftEmpty) return 1;
  if (rightEmpty) return -1;
  const leftNumber = toNumber(left);
  const rightNumber = toNumber(right);
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber;
  const leftTime = Date.parse(left);
  const rightTime = Date.parse(right);
  if (Number.isFinite(leftTime) && Number.isFinite(rightTime)) return leftTime - rightTime;
  return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' });
}

function isEmptySortValue(value) {
  return value === null || value === undefined || value === '';
}

function MetricDataPlot({ item, rows, columns }) {
  const xKey = item.metricBinding?.x || item.seriesBinding?.x || columns[0] || null;
  const requestedY = item.metricBinding?.y || item.seriesBinding?.y;
  const requestedYKeys = Array.isArray(requestedY) ? requestedY : [requestedY].filter(Boolean);
  const numericColumns = columns.filter((column) => column !== xKey && rows.some((row) => Number.isFinite(toNumber(row?.[column]))));
  const yKeys = (requestedYKeys.length ? requestedYKeys : numericColumns).filter((column) => numericColumns.includes(column)).slice(0, 6);
  if (!rows.length || !xKey || !yKeys.length) return <div className="rounded-md border border-line bg-white/45 p-8 text-center text-sm font-semibold text-muted">{t("No plottable numeric data.")}</div>;
  const option = {
    color: ['#2563eb', '#16a34a', '#f97316', '#7c3aed', '#0891b2', '#dc2626'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#6b7280' } },
    grid: { left: 54, right: 22, top: 48, bottom: 54 },
    xAxis: { type: 'category', data: rows.map((row, index) => String(row?.[xKey] ?? index + 1)), axisLabel: { color: '#6b7280' } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
    series: yKeys.map((key) => ({
      name: key,
      type: 'line',
      showSymbol: false,
      smooth: false,
      data: rows.map((row) => {
        const value = toNumber(row?.[key]);
        return Number.isFinite(value) ? value : null;
      }),
    })),
  };
  return <ReactECharts option={option} style={{ height: 430, width: '100%' }} />;
}

function ArtifactList({ artifacts }) {
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const kinds = Array.from(new Set((artifacts || []).map((artifact) => artifact.kind).filter(Boolean))).sort();
  const [kind, setKind] = useState('all');
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (kind !== 'all' && !kinds.includes(kind)) setKind('all');
  }, [kind, kinds.join('|')]);
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = (artifacts || []).filter((artifact) => {
    if (kind !== 'all' && artifact.kind !== kind) return false;
    if (!normalizedQuery) return true;
    return artifactSearchText(artifact).includes(normalizedQuery);
  });
  if (!artifacts.length) return <div className="p-5 text-sm text-muted">{t("No artifacts.")}</div>;
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 sm:grid-cols-[220px_minmax(260px,1fr)]">
          <Field label="Artifact kind">
            <SelectInput value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="all">{t("All artifacts")}</option>
              {kinds.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <Field label="Search artifacts">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="name, filename, preview, metadata" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">{filtered.length} shown · {artifacts.length} total</div>
      </div>
      <div className="divide-y divide-line">
        {filtered.length ? filtered.map((artifact) => (
          <div className="flex items-start justify-between gap-3 px-5 py-4" key={artifact.id}>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-ink">{artifact.name}</div>
              <div className="mt-1 truncate text-xs text-muted">{artifact.kind} · {artifact.filename} · {artifact.size_bytes} bytes</div>
              <ArtifactPreviewSummary preview={artifact.preview_json || {}} />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button className="icon-button" type="button" onClick={() => setSelectedArtifact(artifact)} aria-label={`View artifact ${artifact.name}`} title="View details">
                <FileText size={16} />
              </button>
              <a
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-line bg-white/70 text-muted transition hover:border-info hover:text-info"
                href={artifactContentUrl(artifact.id)}
                target="_blank"
                rel="noreferrer"
                title="Open artifact"
              >
                <ExternalLink size={16} />
              </a>
              <a
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-line bg-white/70 text-muted transition hover:border-info hover:text-info"
                href={artifactContentUrl(artifact.id)}
                download={artifact.filename || artifact.name}
                title="Download artifact"
              >
                <Download size={16} />
              </a>
            </div>
          </div>
        )) : <div className="p-5 text-sm text-muted">{t("No artifacts match the current filters.")}</div>}
        {selectedArtifact ? <ArtifactDetailModal artifact={selectedArtifact} onClose={() => setSelectedArtifact(null)} /> : null}
      </div>
    </div>
  );
}

function artifactSearchText(artifact) {
  return [
    artifact.id,
    artifact.name,
    artifact.kind,
    artifact.filename,
    artifact.mime_type,
    artifact.sha256,
    artifact.storage_uri,
    JSON.stringify(artifact.preview_json || {}),
    JSON.stringify(artifact.metadata_json || {}),
  ].filter(Boolean).join(' ').toLowerCase();
}

function ArtifactDetailModal({ artifact, onClose }) {
  const [detail, setDetail] = useState(artifact);
  const [error, setError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    apiGet(`/api/v1/artifacts/${artifact.id}`)
      .then((payload) => {
        if (!cancelled) {
          setDetail(payload);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelled = true;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [artifact.id, onClose]);
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-ink/25 px-4 py-16 backdrop-blur-sm" role="dialog" aria-modal="true" onPointerDown={onClose}>
      <div className="max-h-[calc(100vh-8rem)] w-full max-w-3xl overflow-hidden rounded-md border border-line bg-panel shadow-xl" onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="truncate text-lg font-semibold text-ink">{detail.name}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close artifact details">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[calc(100vh-14rem)] overflow-y-auto p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <ReadOnlyField label="ID" value={detail.id} />
            <ReadOnlyField label="Kind" value={detail.kind} />
            <ReadOnlyField label="Filename" value={detail.filename} />
            <ReadOnlyField label="MIME type" value={detail.mime_type} />
            <ReadOnlyField label="Size" value={formatBytes(detail.size_bytes)} />
            <ReadOnlyField label="SHA256" value={detail.sha256} code />
            <ReadOnlyField label="Storage URI" value={detail.storage_uri} code />
            <ReadOnlyField label="Created" value={formatDate(detail.created_at)} />
          </div>
          {error ? <div className="mt-3"><InlineError message={error} /></div> : null}
          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold text-muted">{t("Preview")}</div>
            <ArtifactPreview detail={detail} />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <ReadOnlyField label="Metadata" value={compactKeyValueSummary(detail.metadata_json || {})} code />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <a className="secondary-button" href={artifactContentUrl(detail.id)} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
              Open artifact
            </a>
            <a className="secondary-button" href={artifactContentUrl(detail.id)} download={detail.filename || detail.name}>
              <Download className="h-4 w-4" />
              Download
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

function ArtifactPreview({ detail }) {
  const preview = detail.preview_json || {};
  const rows = Array.isArray(preview.rows) ? preview.rows : [];
  const columns = Array.isArray(preview.columns) ? prioritizeTemporalColumns(preview.columns) : [];
  if (isImageArtifact(detail, preview)) {
    return (
      <div className="overflow-hidden rounded-md border border-line bg-white/50">
        <img className="max-h-[420px] w-full object-contain" src={artifactContentUrl(detail.id)} alt={detail.name} />
      </div>
    );
  }
  if (rows.length && columns.length) {
    return <ArtifactPreviewTable columns={columns} rows={rows} />;
  }
  if (preview.title || detail.kind === 'report_html' || detail.mime_type === 'text/html') {
    return (
      <div className="rounded-md border border-line bg-white/50 p-4">
        <div className="text-sm font-semibold text-ink">{preview.title || detail.name}</div>
        <div className="mt-1 text-xs text-muted">{detail.filename || 'HTML report'}</div>
      </div>
    );
  }
  if (Array.isArray(preview.keys) && preview.keys.length) {
    return (
      <div className="rounded-md border border-line bg-white/50 p-4 text-sm text-muted">
        {preview.keys.join(', ')}
      </div>
    );
  }
  return <ReadOnlyField label="Preview" value={compactKeyValueSummary(preview)} code />;
}

function ArtifactPreviewTable({ columns, rows }) {
  const visibleColumns = columns.slice(0, 8);
  return (
    <div className="max-h-[420px] overflow-auto rounded-md border border-line">
      <table className="w-full min-w-[640px] border-collapse">
        <thead className="table-head">
          <tr>{visibleColumns.map((column) => <th className="px-4 py-3" key={column}>{formatTableHeader(column)}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((row, index) => (
            <tr className="hover:bg-white/45" key={index}>
              {visibleColumns.map((column) => (
                <td className="table-cell text-muted" key={column}>{formatPreviewCell(row?.[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function isImageArtifact(detail, preview) {
  return Boolean(preview.width && preview.height) || String(detail.mime_type || '').startsWith('image/') || String(detail.kind || '').startsWith('image_');
}

function formatPreviewCell(value) {
  if (value === null || value === undefined || value === '') return '--';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function formatTableHeader(value) {
  return String(value || '').toUpperCase();
}

function ArtifactPreviewSummary({ preview }) {
  const summary = [];
  if (preview.format) summary.push(preview.format);
  if (preview.title) summary.push(`title: ${preview.title}`);
  if (preview.width && preview.height) summary.push(`${preview.width}x${preview.height}`);
  if (Number.isFinite(Number(preview.row_count))) summary.push(`${preview.row_count} rows`);
  if (Array.isArray(preview.columns) && preview.columns.length) {
    const shownColumns = preview.columns.slice(0, 3);
    const remaining = preview.columns.length - shownColumns.length;
    summary.push(`columns: ${shownColumns.join(', ')}${remaining > 0 ? `, +${remaining} more` : ''}`);
  }
  if (Array.isArray(preview.schema) && preview.schema.length) summary.push(`schema: ${preview.schema.slice(0, 4).map((field) => `${field.name}${field.type ? `:${field.type}` : ''}`).join(', ')}`);
  if (Array.isArray(preview.keys) && preview.keys.length) summary.push(`keys: ${preview.keys.slice(0, 8).join(', ')}`);
  if (preview.preview_status) summary.push(preview.preview_status);
  if (Array.isArray(preview.rows) && preview.rows.length && !Number.isFinite(Number(preview.row_count))) summary.push(`${preview.rows.length} preview rows`);
  if (!summary.length) return null;
  return <div className="truncate text-[11px] text-muted">{summary.join(' · ')}</div>;
}

function EventsPanel({ events }) {
  const ordered = [...(events || [])].sort((a, b) => Number(a.sequence_no || 0) - Number(b.sequence_no || 0) || new Date(a.created_at || 0) - new Date(b.created_at || 0));
  const eventTypes = Array.from(new Set(ordered.map((event) => event.event_type).filter(Boolean))).sort();
  const [eventType, setEventType] = useState('all');
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (eventType !== 'all' && !eventTypes.includes(eventType)) setEventType('all');
  }, [eventType, eventTypes.join('|')]);
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = ordered.filter((event) => {
    if (eventType !== 'all' && event.event_type !== eventType) return false;
    if (!normalizedQuery) return true;
    return [
      event.event_type,
      event.stage,
      event.client_event_id,
      JSON.stringify(event.payload_json || {}),
    ].filter(Boolean).some((value) => String(value).toLowerCase().includes(normalizedQuery));
  });
  return (
    <div>
      <PanelHeader title="Events" icon={Activity} />
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 sm:grid-cols-[220px_minmax(240px,1fr)]">
          <Field label="Event type">
            <SelectInput value={eventType} onChange={(event) => setEventType(event.target.value)}>
              <option value="all">{t("All event types")}</option>
              {eventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </SelectInput>
          </Field>
          <Field label="Search events">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="stage, client event id, payload" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">
          {filtered.length} shown · {ordered.length} total
        </div>
      </div>
      <div className="p-5">
        {filtered.length ? (
          <div className="relative space-y-5 before:absolute before:bottom-0 before:left-[18px] before:top-1 before:w-px before:bg-line">
            {filtered.map((event) => <EventTimelineItem event={event} key={event.id} />)}
          </div>
        ) : <div className="text-sm text-muted">{ordered.length ? 'No events match the current filters.' : 'No events.'}</div>}
      </div>
    </div>
  );
}

function EventTimelineItem({ event }) {
  const payload = event.payload_json || {};
  return (
    <div className="relative flex gap-4">
      <div className={`z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border text-xs font-semibold ${eventToneClass(event.event_type)}`}>
        {event.sequence_no || '--'}
      </div>
      <div className="min-w-0 flex-1 rounded-md border border-line bg-white/45 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-ink">{event.stage || event.event_type}</div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
              <span>{event.event_type}</span>
              {event.client_event_id ? <span>client {event.client_event_id}</span> : null}
            </div>
          </div>
          <div className="shrink-0 text-xs text-muted">{formatDate(event.created_at)}</div>
        </div>
        {Object.keys(payload).length ? <div className="mt-3"><ReadOnlyField label="Payload" value={compactKeyValueSummary(payload)} code /></div> : null}
      </div>
    </div>
  );
}

function eventToneClass(eventType) {
  if (eventType === 'run_failed') return 'border-negativeSoft bg-negativeSoft text-negative';
  if (eventType === 'run_finished') return 'border-positiveSoft bg-positiveSoft text-positive';
  if (eventType === 'run_cancelled') return 'border-line bg-white text-muted';
  if (eventType === 'artifact_uploaded') return 'border-infoSoft bg-infoSoft text-info';
  return 'border-line bg-white text-ink';
}

function SnapshotsPanel({ snapshots }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Snapshots" icon={Database} />
      <div className="grid grid-cols-3 gap-3 p-5">
        {['code', 'data', 'env'].map((kind) => <div className="rounded-md border border-line bg-white/55 p-3" key={kind}><div className="text-xs font-semibold uppercase text-muted">{kind}</div><div className="metric-value mt-2 text-2xl text-ink">{snapshots?.[kind]?.length || 0}</div></div>)}
      </div>
    </Panel>
  );
}

function SnapshotsDetailPanel({ snapshots }) {
  const baseGroups = [
    { id: 'code', title: 'Code', rows: snapshots?.code || [] },
    { id: 'data', title: 'Data', rows: snapshots?.data || [] },
    { id: 'env', title: 'Env', rows: snapshots?.env || [] },
  ];
  const [kind, setKind] = useState('all');
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const groups = baseGroups.map((group) => ({
    ...group,
    rows: group.rows.filter((row) => {
      if (kind !== 'all' && group.id !== kind) return false;
      if (!normalizedQuery) return true;
      return snapshotSearchText(group.id, row).includes(normalizedQuery);
    }),
  }));
  const totalCount = baseGroups.reduce((sum, group) => sum + group.rows.length, 0);
  const filteredCount = groups.reduce((sum, group) => sum + group.rows.length, 0);
  return (
    <div>
      <PanelHeader title="Context" icon={Database} />
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 sm:grid-cols-[180px_minmax(260px,1fr)]">
          <Field label="Snapshot kind">
            <SelectInput value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="all">{t("All snapshots")}</option>
              <option value="code">Code</option>
              <option value="data">Data</option>
              <option value="env">Env</option>
            </SelectInput>
          </Field>
          <Field label="Search snapshots">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="git commit, dataset, fingerprint, host, package" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">
          {filteredCount} shown · {totalCount} total
        </div>
      </div>
      <div className="grid gap-4 p-4 xl:grid-cols-3">
        {groups.map((group) => (
          <div className="rounded-md border border-line bg-white/45" key={group.id}>
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div className="text-sm font-semibold text-ink">{group.title}</div>
              <div className="text-xs font-semibold text-muted">{group.rows.length} / {baseGroups.find((item) => item.id === group.id)?.rows.length || 0}</div>
            </div>
            <div className="divide-y divide-line">
              {group.rows.length ? group.rows.map((row) => <SnapshotCard kind={group.id} row={row} key={row.id} />) : <div className="p-4 text-sm text-muted">{baseGroups.find((item) => item.id === group.id)?.rows.length ? 'No snapshots match the current filters.' : `No ${group.title.toLowerCase()} snapshots.`}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SnapshotCard({ kind, row }) {
  const fields = snapshotDisplayFields(kind, row);
  const metadata = row.metadata_json || {};
  const packages = kind === 'env' ? row.packages_json || {} : {};
  return (
    <div className="p-4">
      <div className="text-xs text-muted">{formatDate(row.created_at)}</div>
      <div className="mt-3 space-y-2">
        {fields.map(([label, value]) => (
          <div className="flex items-start justify-between gap-3 rounded-md border border-line bg-white/45 px-3 py-2" key={label}>
            <span className="text-xs font-semibold uppercase text-muted">{label}</span>
            <span className="max-w-[70%] break-words text-right text-xs text-ink">{formatSnapshotValue(value)}</span>
          </div>
        ))}
      </div>
      {Object.keys(packages).length ? <SnapshotJsonBlock title="Packages" value={packages} /> : null}
      {Object.keys(metadata).length ? <SnapshotJsonBlock title="Metadata" value={metadata} /> : null}
    </div>
  );
}

function SnapshotJsonBlock({ title, value }) {
  return (
    <div className="mt-3">
      <ReadOnlyField label={title} value={compactKeyValueSummary(value)} code />
    </div>
  );
}

function snapshotDisplayFields(kind, row) {
  const fieldMap = {
    code: ['git_commit', 'git_dirty', 'repo_url', 'requirements_hash', 'container_image', 'patch_artifact_id'],
    data: ['dataset_name', 'dataset_version', 'fingerprint', 'universe', 'benchmark', 'calendar', 'fee_model', 'slippage_model', 'time_range'],
    env: ['python_version', 'platform', 'hostname'],
  };
  return (fieldMap[kind] || [])
    .map((key) => [key, row[key]])
    .filter(([, value]) => value !== null && value !== undefined && value !== '' && !(typeof value === 'object' && !Array.isArray(value) && !Object.keys(value).length));
}

function snapshotSearchText(kind, row) {
  return [
    kind,
    row.id,
    row.created_at,
    ...snapshotDisplayFields(kind, row).map(([label, value]) => `${label} ${formatSnapshotValue(value)}`),
    JSON.stringify(row.metadata_json || {}),
    kind === 'env' ? JSON.stringify(row.packages_json || {}) : '',
  ].filter(Boolean).join(' ').toLowerCase();
}

function formatSnapshotValue(value) {
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function NotesPanel({ notes }) {
  const ordered = [...(notes || [])].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const kinds = Array.from(new Set(ordered.map((note) => note.kind).filter(Boolean))).sort();
  const authors = Array.from(new Set(ordered.map((note) => note.author_type).filter(Boolean))).sort();
  const [kind, setKind] = useState('all');
  const [author, setAuthor] = useState('all');
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (kind !== 'all' && !kinds.includes(kind)) setKind('all');
  }, [kind, kinds.join('|')]);
  useEffect(() => {
    if (author !== 'all' && !authors.includes(author)) setAuthor('all');
  }, [author, authors.join('|')]);
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = ordered.filter((note) => {
    if (kind !== 'all' && note.kind !== kind) return false;
    if (author !== 'all' && note.author_type !== author) return false;
    if (!normalizedQuery) return true;
    return [
      note.summary,
      note.content_md,
      note.client_event_id,
      JSON.stringify(note.structured_json || {}),
    ].filter(Boolean).some((value) => String(value).toLowerCase().includes(normalizedQuery));
  });
  return (
    <div>
      <PanelHeader title="Notes" icon={ListTree} />
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-4">
        <div className="grid gap-3 md:grid-cols-[180px_180px_minmax(240px,1fr)]">
          <Field label="Kind">
            <SelectInput value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="all">{t("All kinds")}</option>
              {kinds.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <Field label="Author">
            <SelectInput value={author} onChange={(event) => setAuthor(event.target.value)}>
              <option value="all">{t("All authors")}</option>
              {authors.map((item) => <option key={item} value={item}>{item}</option>)}
            </SelectInput>
          </Field>
          <Field label="Search notes">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="summary, content, client event id, structured JSON" />
          </Field>
        </div>
        <div className="text-xs font-semibold text-muted">{filtered.length} shown · {ordered.length} total</div>
      </div>
      <div className="divide-y divide-line">
        {filtered.length ? filtered.map((note) => (
          <div className="px-5 py-4" key={note.id}>
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-ink">{note.summary}</div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
                  <span>{note.kind || 'note'}</span>
                  <span>{note.author_type || 'human'}</span>
                  {note.client_event_id ? <span>client {note.client_event_id}</span> : null}
                </div>
              </div>
              <div className="text-xs text-muted">{formatDate(note.created_at)}</div>
            </div>
            {note.content_md ? <MarkdownView text={note.content_md} /> : null}
            {Object.keys(note.structured_json || {}).length ? <div className="mt-3"><ReadOnlyField label="Structured" value={compactKeyValueSummary(note.structured_json)} code /></div> : null}
          </div>
        )) : <div className="p-5 text-sm text-muted">{ordered.length ? 'No notes match the current filters.' : 'No notes yet.'}</div>}
      </div>
    </div>
  );
}

function MarkdownView({ text }) {
  const blocks = markdownBlocks(text);
  return (
    <div className="mt-3 space-y-2 text-sm leading-6 text-muted">
      {blocks.map((block, index) => renderMarkdownBlock(block, index))}
    </div>
  );
}

function renderMarkdownBlock(block, index) {
  if (block.type === 'heading') {
    const sizeClass = block.level === 1 ? 'text-base' : 'text-sm';
    return <div className={`${sizeClass} font-semibold text-ink`} key={index}>{renderInlineMarkdown(block.text, index)}</div>;
  }
  if (block.type === 'code') {
    return <pre className="overflow-auto rounded-md border border-line bg-white/55 p-3 text-xs text-muted" key={index}>{block.text}</pre>;
  }
  if (block.type === 'quote') {
    return <blockquote className="border-l-2 border-line pl-3 text-muted" key={index}>{renderInlineMarkdown(block.text, index)}</blockquote>;
  }
  if (block.type === 'ul') {
    return <ul className="list-disc space-y-1 pl-5" key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item, `${index}-${itemIndex}`)}</li>)}</ul>;
  }
  if (block.type === 'ol') {
    return <ol className="list-decimal space-y-1 pl-5" key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item, `${index}-${itemIndex}`)}</li>)}</ol>;
  }
  return <p className="whitespace-pre-wrap" key={index}>{renderInlineMarkdown(block.text, index)}</p>;
}

function markdownBlocks(value) {
  const lines = String(value || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.trim().startsWith('```')) {
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: 'code', text: code.join('\n') });
      index += 1;
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const quote = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'quote', text: quote.join(' ') });
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*]\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ul', items });
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ol', items });
      continue;
    }
    const paragraph = [];
    while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines[index])) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraph.join(' ') });
  }
  return blocks;
}

function isMarkdownBlockStart(line) {
  return line.trim().startsWith('```') || /^(#{1,3})\s+/.test(line) || /^>\s?/.test(line) || /^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line);
}

function renderInlineMarkdown(value, keyPrefix) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  return String(value || '').split(pattern).filter((part) => part !== '').map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code className="rounded bg-white/70 px-1 py-0.5 font-mono text-xs text-ink" key={key}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong className="font-semibold text-ink" key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link && isSafeMarkdownUrl(link[2])) {
      return <a className="font-semibold text-info hover:underline" href={link[2]} key={key} rel="noreferrer" target="_blank">{link[1]}</a>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

function isSafeMarkdownUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    return ['http:', 'https:', 'mailto:'].includes(url.protocol);
  } catch {
    return false;
  }
}

function lineageOption(branches, runs = []) {
  const root = branches.find((branch) => !branch.parent_branch_id) || branches[0];
  const runsByBranch = runs.reduce((acc, run) => {
    acc[run.branch_id] = [...(acc[run.branch_id] || []), run];
    return acc;
  }, {});
  const toNode = (branch) => ({
    name: branchLabel(branch, runsByBranch[branch?.id] || []),
    value: branch?.status || '',
    children: branches.filter((item) => item.parent_branch_id === branch?.id).map(toNode),
  });
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => String(params.name || '').replaceAll('\n', '<br/>'),
    },
    series: [{
      type: 'tree',
      data: root ? [toNode(root)] : [],
      top: 24,
      left: 24,
      right: 160,
      bottom: 24,
      orient: 'LR',
      roam: true,
      symbolSize: 12,
      lineStyle: { color: '#b8bbb5', width: 2 },
      label: { color: '#202326', fontWeight: 700, lineHeight: 18 },
      leaves: { label: { position: 'right', color: '#202326', fontWeight: 700, lineHeight: 18 } },
    }],
  };
}

function branchLabel(branch, runs) {
  if (!branch) return 'empty';
  const best = [...runs].sort((left, right) => Number(metricValue(right, 'strategy.summary', 'sharpe') ?? -Infinity) - Number(metricValue(left, 'strategy.summary', 'sharpe') ?? -Infinity))[0];
  const bestSharpe = best ? metricValue(best, 'strategy.summary', 'sharpe') : null;
  return [
    branch.key || branch.title || branch.id,
    `${branch.status || 'unknown'} · ${runs.length} runs`,
    bestSharpe === null || bestSharpe === undefined ? null : `best sharpe ${formatMetric(bestSharpe)}`,
  ].filter(Boolean).join('\n');
}

function buildRecentActivities(data) {
  const runs = (data?.runs || []).map((run) => ({
    id: `run-${run.id}`,
    type: run.status === 'failed' ? 'run failed' : run.status === 'completed' ? 'run finished' : 'run',
    tone: run.status === 'failed' ? 'negative' : run.status === 'completed' ? 'positive' : run.status === 'running' ? 'warning' : 'neutral',
    title: run.name,
    detail: `${run.research_key || '--'} / ${run.branch_key || run.branch_id}`,
    at: run.updated_at || run.created_at,
    run_id: run.id,
  }));
  const branches = (data?.branches || []).map((branch) => ({
    id: `branch-${branch.id}`,
    type: 'branch',
    tone: branch.status === 'active' ? 'info' : 'neutral',
    title: branch.title || branch.key,
    detail: branch.reason_summary || branch.hypothesis || `Research ${branch.research_key || branch.research_id}`,
    at: branch.updated_at || branch.created_at,
    branch_id: branch.id,
  }));
  const artifacts = (data?.artifacts || []).map((artifact) => ({
    id: `artifact-${artifact.id}`,
    type: 'artifact',
    tone: 'info',
    title: artifact.name,
    detail: artifact.kind,
    at: artifact.created_at,
    run_id: artifact.run_id,
  }));
  const notes = (data?.notes || []).map((note) => ({
    id: `note-${note.id}`,
    type: `${note.kind} note`,
    tone: note.kind === 'decision' ? 'positive' : note.kind === 'anomaly' ? 'warning' : note.author_type === 'agent' ? 'info' : 'neutral',
    title: note.summary,
    detail: `${note.author_type || 'human'} · ${note.run_name || note.run_id} · ${note.research_key || '--'} / ${note.branch_key || note.branch_id || '--'}`,
    at: note.created_at,
    run_id: note.run_id,
  }));
  return [...runs, ...branches, ...artifacts, ...notes].sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0));
}

function dashboardHeatmapData(data, weekCount = 53) {
  const end = startOfLocalDay(new Date());
  const firstDay = new Date(end);
  firstDay.setDate(end.getDate() - ((end.getDay() + 6) % 7) - (weekCount - 1) * 7);
  const start = firstDay;
  const counts = dashboardRunDailyCounts(data);
  const weeks = Array.from({ length: weekCount }, (_, weekIndex) => ({
    days: Array.from({ length: 7 }, (_, dayIndex) => {
      const date = new Date(firstDay);
      date.setDate(firstDay.getDate() + weekIndex * 7 + dayIndex);
      const key = dateKey(date);
      return {
        key,
        date,
        dateLabel: date.toLocaleDateString('en-US'),
        count: date < start || date > end ? 0 : counts.get(key) || 0,
      };
    }),
  }));
  const monthLabels = [];
  const yearLabels = [];
  let lastMonth = '';
  let lastYear = '';
  weeks.forEach((week, weekIndex) => {
    const visible = week.days.find((day) => day.date >= start && day.date <= end);
    if (!visible) return;
    const month = visible.date.toLocaleString('en-US', { month: 'short' });
    const year = String(visible.date.getFullYear());
    if (month !== lastMonth) {
      if (weekIndex > 0) {
        monthLabels.push({ key: `${year}-${month}-${weekIndex}`, month, week: weekIndex });
      }
      lastMonth = month;
    }
    if (year !== lastYear) {
      if (weekIndex > 0) {
        yearLabels.push({ key: `${year}-${weekIndex}`, year, week: weekIndex });
      }
      lastYear = year;
    }
  });
  const values = weeks.flatMap((week) => week.days.map((day) => day.count));
  return {
    weeks,
    total: values.reduce((sum, value) => sum + value, 0),
    max: Math.max(1, ...values),
    monthLabels,
    yearLabels,
  };
}

function dashboardRunDates(data) {
  return (data?.runs || [])
    .map((run) => run.ended_at || run.started_at || run.created_at || run.updated_at)
    .map(parseDateValue)
    .filter((date) => date && Number.isFinite(date.getTime()));
}

function dashboardRunDailyCounts(data) {
  const rows = data?.run_activity_daily || [];
  const counts = new Map();
  if (rows.length) {
    rows.forEach((row) => {
      const date = parseDateValue(row.date);
      const count = Number(row.run_count ?? row.count ?? 0);
      if (!date || !Number.isFinite(date.getTime()) || !Number.isFinite(count) || count <= 0) return;
      counts.set(dateKey(startOfLocalDay(date)), (counts.get(dateKey(startOfLocalDay(date))) || 0) + count);
    });
    return counts;
  }
  dashboardRunDates(data).forEach((date) => {
    const key = dateKey(startOfLocalDay(date));
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return counts;
}

function dashboardTimelineGroups(data) {
  const groups = [
    {
      type: 'project',
      title: 'Projects',
      icon: Database,
      items: (data?.projects || []).map((project) => ({
        id: `project-${project.id}`,
        kind: 'project',
        targetId: project.id,
        title: project.title || project.key,
        detail: `${project.key || project.id} · ${project.research_count ?? 0} researches · ${project.run_count ?? 0} runs`,
        at: project.updated_at || project.created_at,
      })),
    },
    {
      type: 'research',
      title: 'Research',
      icon: ListTree,
      items: (data?.researches || []).map((research) => ({
        id: `research-${research.id}`,
        kind: 'research',
        targetId: research.id,
        title: research.title || research.key,
        detail: `${research.project_key || 'Project'} · ${research.status || 'unknown'} · ${research.run_count ?? 0} runs`,
        at: research.updated_at || research.created_at,
      })),
    },
    {
      type: 'run',
      title: 'Runs',
      icon: LineChart,
      items: (data?.runs || []).map((run) => ({
        id: `run-${run.id}`,
        kind: 'run',
        targetId: run.id,
        title: run.title || run.name,
        detail: `${run.research_key || '--'} / ${run.branch_key || run.branch_id || '--'} · ${run.status || 'unknown'} · Sharpe ${formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))}`,
        at: run.updated_at || run.ended_at || run.started_at || run.created_at,
      })),
    },
  ];
  return groups.map((group) => ({
    ...group,
    items: group.items
      .filter((item) => item.targetId)
      .sort((a, b) => dateMillis(b.at) - dateMillis(a.at))
      .slice(0, 8),
  })).filter((group) => group.items.length);
}

function heatmapRed(value, max) {
  if (!value) return '#f3f4f1';
  const level = Math.min(4, Math.max(1, Math.ceil((Number(value) / Math.max(1, max)) * 4)));
  return ['#f3f4f1', '#fee2e2', '#fca5a5', '#ef4444', '#991b1b'][level];
}

function startOfLocalDay(date) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  return result;
}

function dateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function parseDateValue(value) {
  if (!value) return null;
  const text = String(value);
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  const isoWithoutTimezone = /^\d{4}-\d{2}-\d{2}T/.test(text) && !hasTimezone;
  const date = new Date(isoWithoutTimezone ? `${text}Z` : text);
  return Number.isFinite(date.getTime()) ? date : null;
}

function dateMillis(value) {
  return parseDateValue(value)?.getTime() || 0;
}

function entityUpdatedMillis(item) {
  return dateMillis(item?.updated_at || item?.ended_at || item?.started_at || item?.created_at);
}

function runRecentActivityMillis(run) {
  return dateMillis(run?.updated_at || run?.ended_at || run?.started_at || run?.created_at);
}

function sortRunsByRecentActivity(runs) {
  return [...(runs || [])].sort((a, b) => runRecentActivityMillis(b) - runRecentActivityMillis(a));
}

function latestRunMillisForProject(project, runs) {
  const latestRun = sortRunsByRecentActivity((runs || []).filter((run) => run.project_id === project?.id || run.project_key === project?.key))[0];
  return latestRun ? runRecentActivityMillis(latestRun) : entityUpdatedMillis(project);
}

function latestRunMillisForResearch(research, branches, runs) {
  const branchIds = new Set((branches || []).filter((branch) => branch.research_id === research?.id || branch.research_key === research?.key).map((branch) => branch.id));
  const latestRun = sortRunsByRecentActivity((runs || []).filter((run) => run.research_id === research?.id || run.research_key === research?.key || branchIds.has(run.branch_id)))[0];
  return latestRun ? runRecentActivityMillis(latestRun) : entityUpdatedMillis(research);
}

function latestRunMillisForBranch(branch, runs) {
  const latestRun = sortRunsByRecentActivity((runs || []).filter((run) => run.branch_id === branch?.id || run.branch_key === branch?.key))[0];
  return latestRun ? runRecentActivityMillis(latestRun) : entityUpdatedMillis(branch);
}

function researchTimelineItems(research, branches, runs, notes) {
  const branchIds = new Set((branches || []).map((branch) => branch.id));
  const runIds = new Set((runs || []).map((run) => run.id));
  const branchById = Object.fromEntries((branches || []).map((branch) => [branch.id, branch]));
  const branchItems = (branches || []).map((branch) => ({
    id: `branch-${branch.id}`,
    type: 'branch created',
    title: branch.title || branch.key,
    detail: branch.reason_summary || branch.hypothesis || `Research ${research?.key || branch.research_key || branch.research_id}`,
    at: branch.created_at || branch.updated_at,
    branch_id: branch.id,
  }));
  const runItems = (runs || [])
    .filter((run) => ['completed', 'failed', 'cancelled'].includes(run.status))
    .map((run) => ({
      id: `run-${run.id}`,
      type: run.status === 'completed' ? 'run finished' : `run ${run.status}`,
      title: run.title || run.name,
      detail: `${run.branch_key || branchById[run.branch_id]?.key || run.branch_id} · Sharpe ${formatMetric(metricValue(run, 'strategy.summary', 'sharpe'))} · ${runRuntime(run)}`,
      at: run.ended_at || run.updated_at || run.created_at,
      run_id: run.id,
    }));
  const noteItems = (notes || [])
    .filter((note) => runIds.has(note.run_id) || branchIds.has(note.branch_id))
    .map((note) => ({
      id: `note-${note.id}`,
      type: `${note.kind || 'note'} note`,
      title: note.summary,
      detail: `${note.author_type || 'human'} · ${note.run_name || note.run_id || branchById[note.branch_id]?.key || '--'}`,
      at: note.created_at,
      run_id: note.run_id,
      branch_id: note.branch_id,
    }));
  return [...branchItems, ...runItems, ...noteItems].sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0));
}

function dashboardWindowStats(data) {
  const now = Date.now();
  const dayStart = new Date();
  dayStart.setHours(0, 0, 0, 0);
  const since24h = now - 24 * 60 * 60 * 1000;
  const runs = data?.runs || [];
  const branches = data?.branches || [];
  return {
    runsToday: runs.filter((run) => new Date(run.created_at || run.started_at || run.updated_at).getTime() >= dayStart.getTime()).length,
    failed24h: runs.filter((run) => run.status === 'failed' && new Date(run.updated_at || run.ended_at || run.created_at).getTime() >= since24h).length,
    branches24h: branches.filter((branch) => new Date(branch.created_at || branch.updated_at).getTime() >= since24h).length,
  };
}

function projectResearchActivityRows(researches, branches, runs) {
  const since7d = Date.now() - 7 * 24 * 60 * 60 * 1000;
  return (researches || []).map((research) => {
    const researchBranches = (branches || []).filter((branch) => branch.research_id === research.id);
    const branchIds = new Set(researchBranches.map((branch) => branch.id));
    const researchRuns = (runs || []).filter((run) => branchIds.has(run.branch_id));
    const fallbackRuns7d = researchRuns.filter((run) => new Date(run.created_at || run.started_at || run.updated_at).getTime() >= since7d).length;
    const runs7d = research.run_count_7d ?? fallbackRuns7d;
    const failed7d = research.failed_run_count_7d ?? researchRuns.filter((run) => run.status === 'failed' && new Date(run.updated_at || run.ended_at || run.created_at).getTime() >= since7d).length;
    const champion = researchChampionRun(research, researchBranches, researchRuns);
    const latestRun = sortRunsByRecentActivity(researchRuns)[0] || null;
    const lastRunTime = latestRun?.updated_at || latestRun?.ended_at || latestRun?.started_at || latestRun?.created_at || research.updated_at || research.created_at;
    const lastRunAt = dateMillis(lastRunTime);
    return {
      research,
      branchCount: research.branch_count ?? researchBranches.length,
      runs7d,
      failureRate: runs7d ? failed7d / runs7d : 0,
      champion,
      latestRun,
      lastRunTime,
      lastRunAt,
    };
  }).sort((a, b) => b.lastRunAt - a.lastRunAt || entityUpdatedMillis(b.research) - entityUpdatedMillis(a.research));
}

function runHeroDescription(run) {
  const parts = [
    `${run.project_key || 'Project'} / ${run.research_key || 'Research'} / ${run.branch_key || run.branch_id}`,
    run.source_run?.name || run.source_run_id ? `source ${run.source_run?.name || run.source_run_id}` : null,
    `started ${formatDate(run.started_at)}`,
    `ended ${formatDate(run.ended_at)}`,
    (run.tags || []).length ? `tags ${(run.tags || []).join(', ')}` : null,
  ].filter(Boolean);
  return parts.join(' · ');
}

function runQualityDiagnostics(run, { seriesArtifacts = [], equityChart = null, resultItems = [] } = {}) {
  const issues = [];
  const completed = String(run?.status || '').toLowerCase() === 'completed';
  const explicitResultCount = (run?.artifacts || []).filter(hasExplicitResultMetadata).length;
  const inferredResults = (resultItems || []).filter((item) => !hasExplicitResultMetadata(item.artifact));
  const primarySeries = runPrimarySeriesItem(seriesArtifacts);
  const drawdownSeries = findDrawdownSeriesItem(seriesArtifacts);
  const expectsPerformance = runExpectsPerformanceResult(run, resultItems, seriesArtifacts);

  if (completed && !(resultItems || []).length) {
    addRunQualityIssue(issues, 'error', 'No typed run results', 'Completed runs should publish result artifacts with metadata_json.result so Results can be rendered by domain and role.');
  }
  if (completed && expectsPerformance && !equityChart) {
    addRunQualityIssue(issues, 'error', 'Missing primary performance curve', 'Completed runs should include a chartable performance series such as equity_curve, returns_series, or pnl_series.');
  }
  if (completed && resultItems.length && !explicitResultCount) {
    addRunQualityIssue(issues, 'warning', 'Results are inferred from legacy artifact names', 'Add metadata_json.result to result artifacts so WebUI does not depend on artifact-name guessing.');
  } else if (inferredResults.length) {
    addRunQualityIssue(issues, 'warning', 'Some result artifacts use legacy inference', `${inferredResults.length} result artifact${inferredResults.length > 1 ? 's' : ''} should add explicit metadata_json.result.`);
  }
  if (completed && primarySeries && !hasSeriesValuesColumn(primarySeries)) {
    addRunQualityIssue(issues, 'warning', 'Primary curve does not use series_values', 'New result uploads should use series_values with an explicit mode so nav, return, and pnl series are unambiguous.');
  }

  const checkedIds = new Set();
  if (primarySeries) {
    validateRunSeriesArtifact(issues, primarySeries, { label: 'Primary performance curve', criticalPreview: true, requireMode: completed, role: 'primary_curve' });
    checkedIds.add(primarySeries.id);
  }
  if (drawdownSeries && !checkedIds.has(drawdownSeries.id)) {
    validateRunSeriesArtifact(issues, drawdownSeries, { label: 'Drawdown series', criticalPreview: true, role: 'drawdown' });
    checkedIds.add(drawdownSeries.id);
  }
  for (const item of seriesArtifacts || []) {
    if (checkedIds.has(item.id)) continue;
    validateRunSeriesArtifact(issues, item, { label: item.name || item.artifactName || 'Series artifact', criticalPreview: false, role: item.result?.role });
  }
  validateRunSummaryConsistency(issues, run, equityChart);

  const sorted = issues.sort((left, right) => severityRank(left.severity) - severityRank(right.severity) || left.title.localeCompare(right.title));
  const errorCount = sorted.filter((issue) => issue.severity === 'error').length;
  const warningCount = sorted.filter((issue) => issue.severity === 'warning').length;
  return {
    severity: errorCount ? 'error' : warningCount ? 'warning' : 'ok',
    errorCount,
    warningCount,
    issues: sorted,
  };
}

function runPrimarySeriesItem(seriesArtifacts) {
  const equityKeys = ['series_values', 'nav', 'net_value', 'equity', 'value', 'cumulative_return', 'cum_return', 'total_return', 'return', 'ret', 'pnl', 'profit', 'delta', 'change', 'amount'];
  return findResultSeriesItem(seriesArtifacts, 'performance', 'primary_curve', equityKeys) || findSeriesItem(
    seriesArtifacts,
    ['equity_curve', 'nav', 'net_value', 'cumulative_return', 'returns_series', 'returns', 'pnl_series', 'absolute_return_series', 'pnl', 'profit_series', 'delta_series'],
    equityKeys
  );
}

function runExpectsPerformanceResult(run, resultItems, seriesArtifacts) {
  if ((resultItems || []).some((item) => item.domain === 'performance')) return true;
  if ((seriesArtifacts || []).some((item) => {
    const name = String(item?.name || '').toLowerCase();
    const namespace = String(item?.namespace || '').toLowerCase();
    return /equity|return|pnl|profit|nav|net_value/.test(name) || namespace.startsWith('strategy.');
  })) return true;
  return ['sharpe', 'annual_return', 'annualized_return', 'max_drawdown', 'total_pnl', 'annualized_pnl']
    .some((key) => firstRunSummaryMetric(run, [key]) !== null);
}

function validateRunSeriesArtifact(issues, item, { label, criticalPreview = false, requireMode = false, role = '' } = {}) {
  const rows = item?.rows || [];
  const previewRowCount = Number(item?.previewRowCount);
  if (Number.isFinite(previewRowCount) && previewRowCount > rows.length) {
    addRunQualityIssue(
      issues,
      criticalPreview ? 'error' : 'warning',
      `${label} only has preview rows loaded`,
      `${item.artifactName || item.name} preview exposes ${rows.length} of ${previewRowCount} rows. Charts may be incomplete until full artifact content is used.`
    );
  }
  if (rows.length < 2) {
    addRunQualityIssue(issues, criticalPreview ? 'error' : 'warning', `${label} has too few rows`, `${item.artifactName || item.name} has ${rows.length} preview row${rows.length === 1 ? '' : 's'}.`);
  }
  const xKey = item?.x;
  if (!xKey) {
    addRunQualityIssue(issues, 'warning', `${label} has no x column`, `${item.artifactName || item.name} should declare a date/time x column in metadata.series.x or result.view.x.`);
  } else {
    validateSeriesXValues(issues, item, label, xKey);
  }
  const valueKey = chooseSeriesKey(item, ['series_values', 'nav', 'return', 'ret', 'pnl', 'change', 'drawdown']);
  if (!valueKey) {
    addRunQualityIssue(issues, criticalPreview ? 'error' : 'warning', `${label} has no numeric value column`, `${item.artifactName || item.name} should include numeric series_values or another declared numeric y column.`);
    return;
  }
  const values = rows.map((row) => toNumber(row?.[valueKey])).filter(Number.isFinite);
  const mode = runSeriesDeclaredMode(item);
  if (requireMode && !mode) {
    addRunQualityIssue(issues, 'warning', `${label} has no mode`, `${item.artifactName || item.name} should declare mode=nav, return, or pnl.`);
  }
  if (role === 'primary_curve') validatePrimaryCurveMode(issues, item, label, valueKey, values, mode);
  if (role === 'drawdown' || mode === 'drawdown') validateDrawdownValues(issues, item, label, values);
}

function validateSeriesXValues(issues, item, label, xKey) {
  const rows = item?.rows || [];
  const values = rows.map((row) => row?.[xKey]).filter((value) => value !== null && value !== undefined && value !== '');
  if (!values.length) {
    addRunQualityIssue(issues, 'warning', `${label} x column is empty`, `${item.artifactName || item.name}.${xKey} has no non-empty values in preview rows.`);
    return;
  }
  const counts = new Map();
  for (const value of values) {
    const key = String(value);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const duplicateCount = Array.from(counts.values()).filter((count) => count > 1).length;
  if (duplicateCount) {
    addRunQualityIssue(issues, 'warning', `${label} has duplicate x values`, `${item.artifactName || item.name}.${xKey} has ${duplicateCount} duplicated timestamp/date value${duplicateCount > 1 ? 's' : ''}.`);
  }
  if (isDateLikeColumnName(xKey)) {
    const invalidCount = values.filter((value) => !parseChartDate(value) && !parseDateValue(value)).length;
    if (invalidCount) {
      addRunQualityIssue(issues, 'warning', `${label} has invalid date values`, `${item.artifactName || item.name}.${xKey} has ${invalidCount} value${invalidCount > 1 ? 's' : ''} that cannot be parsed as date/datetime.`);
    }
  }
}

function validatePrimaryCurveMode(issues, item, label, valueKey, values, mode) {
  if (!values.length) return;
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)));
  const minValue = Math.min(...values);
  if (['nav', 'equity', 'net_value', 'level'].includes(mode) && minValue <= 0) {
    addRunQualityIssue(issues, 'error', `${label} has non-positive nav values`, `${item.artifactName || item.name}.${valueKey} declares mode=${mode} but includes values <= 0.`);
  }
  if (['return', 'returns', 'period_return', 'periodic_return'].includes(mode) && maxAbs > 1) {
    addRunQualityIssue(issues, 'warning', `${label} return values look too large`, `${item.artifactName || item.name}.${valueKey} declares return mode but has absolute values above 1. Check whether values are percentage points or net-value levels.`);
  }
}

function validateDrawdownValues(issues, item, label, values) {
  if (!values.length) return;
  const maxValue = Math.max(...values);
  const minValue = Math.min(...values);
  if (maxValue > 0) {
    addRunQualityIssue(issues, 'warning', `${label} has positive drawdown values`, `${item.artifactName || item.name} drawdown should usually be zero or negative.`);
  }
  if (minValue < -1.5) {
    addRunQualityIssue(issues, 'warning', `${label} drawdown unit looks suspicious`, `${item.artifactName || item.name} drawdown is below -1.5. For nav/return runs drawdown_series should usually be decimal values such as -0.09.`);
  }
}

function validateRunSummaryConsistency(issues, run, equityChart) {
  const derived = deriveRunPerformanceMetrics(equityChart);
  if (!derived || !Object.keys(derived).length) return;
  const checks = [
    { label: 'Annual Return', keys: ['annual_return', 'annualized_return'], derived: derived.annual_return },
    { label: 'Annual Volatility', keys: ['annual_volatility', 'annualized_volatility', 'annualized_vol', 'volatility'], derived: derived.annual_volatility },
    { label: 'Max Drawdown', keys: ['max_drawdown', 'maximum_drawdown'], derived: derived.max_drawdown },
  ];
  for (const check of checks) {
    const raw = firstRunSummaryMetric(run, check.keys);
    const value = toNumber(raw);
    if (!Number.isFinite(value) || !Number.isFinite(check.derived)) continue;
    const tolerance = Math.max(5, Math.abs(check.derived) * 0.25);
    if (Math.abs(value - check.derived) <= tolerance) continue;
    if (Math.abs(value * 100 - check.derived) <= tolerance) {
      addRunQualityIssue(issues, 'warning', `${check.label} may use decimal units`, `Summary ${check.label} is ${formatMetric(value)}, while curve-derived value is ${formatMetric(check.derived)} percentage points. Summary percentages should use percentage points.`);
    } else {
      addRunQualityIssue(issues, 'warning', `${check.label} differs from curve-derived value`, `Summary ${check.label} is ${formatMetric(value)}, while curve-derived value is ${formatMetric(check.derived)}. Check metric source and series mode.`);
    }
  }
}

function hasExplicitResultMetadata(artifact) {
  const result = artifact?.metadata_json?.result;
  return Boolean(result && typeof result === 'object' && !Array.isArray(result));
}

function hasSeriesValuesColumn(item) {
  return (item?.y || []).some((key) => String(key || '').toLowerCase() === 'series_values');
}

function runSeriesDeclaredMode(item) {
  return String(item?.mode || item?.result?.view?.mode || '').trim().toLowerCase();
}

function isDateLikeColumnName(column) {
  const normalized = String(column || '').trim().toUpperCase();
  return ['DATE', 'DATETIME', 'TRADE_DATE', 'END_DATE'].includes(normalized);
}

function addRunQualityIssue(issues, severity, title, detail) {
  issues.push({ severity, title, detail });
}

function severityRank(severity) {
  return severity === 'error' ? 0 : severity === 'warning' ? 1 : 2;
}

function runKeyMetricTiles(run, equityChart = null) {
  if (equityChart?.valueMode === 'absolute_change') {
    const pnlMetrics = [
      { label: 'Total PnL', paths: ['strategy.pnl.total_pnl', 'strategy.raw_pnl.total_pnl', 'strategy.summary.total_pnl'], tone: 'positive' },
      { label: 'Annualized PnL', paths: ['strategy.pnl.annualized_pnl', 'strategy.raw_pnl.annualized_pnl', 'strategy.summary.annualized_pnl'], tone: 'positive' },
      { label: 'Max Drawdown', paths: ['strategy.pnl.max_drawdown', 'strategy.raw_pnl.max_drawdown'], tone: 'negative' },
      { label: 'Sharpe', paths: ['strategy.pnl.sharpe', 'strategy.raw_pnl.sharpe', 'strategy.summary.sharpe'], tone: 'positive' },
      { label: 'Sortino', paths: ['strategy.pnl.sortino', 'strategy.raw_pnl.sortino', 'strategy.summary.sortino'], tone: 'positive' },
      { label: 'Calmar', paths: ['strategy.pnl.calmar', 'strategy.raw_pnl.calmar', 'strategy.summary.calmar'], tone: 'positive' },
    ];
    return pnlMetrics.map((item) => ({
      label: item.label,
      value: formatMetric(firstRunMetric(run, item.paths)),
      tone: item.tone,
    }));
  }
  const derived = deriveRunPerformanceMetrics(equityChart);
  const preferred = [
    { label: 'Annual Return', keys: ['annual_return', 'annualized_return', 'annualized_pnl'], tone: 'positive', percent: true },
    { label: 'Annual Volatility', keys: ['annual_volatility', 'annualized_volatility', 'annualized_vol', 'volatility', 'daily_vol'], tone: 'neutral', percent: true },
    { label: 'Max Drawdown', keys: ['max_drawdown', 'maximum_drawdown'], tone: 'negative', percent: true },
    { label: 'Sharpe', keys: ['sharpe'], tone: 'positive' },
    { label: 'Sortino', keys: ['sortino'], tone: 'positive' },
    { label: 'Calmar', keys: ['calmar'], tone: 'positive' },
  ];
  return preferred.map((item) => {
    const summaryRaw = firstRunSummaryMetric(run, item.keys);
    const raw = summaryRaw !== null && summaryRaw !== undefined && summaryRaw !== '' ? summaryRaw : derived[item.keys[0]];
    return {
      label: item.label,
      value: item.percent ? formatPercentMetric(raw) : formatMetric(raw),
      tone: item.tone,
    };
  });
}

function deriveRunPerformanceMetrics(chart) {
  if (!chart || chart.valueMode === 'absolute_change') return {};
  const navPoints = (chart.equityData || [])
    .map(([x, value]) => {
      const number = toNumber(value);
      return { x, nav: chart.valueAsPercent ? 1 + number : number };
    })
    .filter((point) => Number.isFinite(point.nav) && point.nav > 0);
  if (navPoints.length < 2) return {};

  const returns = [];
  for (let index = 1; index < navPoints.length; index += 1) {
    const previous = navPoints[index - 1].nav;
    const current = navPoints[index].nav;
    if (previous > 0 && Number.isFinite(current)) returns.push(current / previous - 1);
  }
  if (!returns.length) return {};

  const first = navPoints[0];
  const last = navPoints[navPoints.length - 1];
  const elapsedDays = elapsedCalendarDays(first.x, last.x);
  const periodsPerYear = elapsedDays > 0 ? returns.length / (elapsedDays / 365.25) : 252;
  const annualReturn = elapsedDays > 0 && first.nav > 0
    ? (Math.exp(Math.log(last.nav / first.nav) * (365.25 / elapsedDays)) - 1)
    : mean(returns) * periodsPerYear;
  const returnDeviation = standardDeviation(returns);
  const volatility = returnDeviation * Math.sqrt(periodsPerYear);
  const downsideDeviation = downsideRiskDeviation(returns) * Math.sqrt(periodsPerYear);
  const averageReturn = mean(returns);
  const maxDrawdown = minFinite((chart.drawdownData || []).map((point) => toNumber(point?.[1])));

  return {
    annual_return: annualReturn * 100,
    annual_volatility: Number.isFinite(volatility) ? volatility * 100 : NaN,
    max_drawdown: Number.isFinite(maxDrawdown) ? maxDrawdown * 100 : NaN,
    sharpe: returnDeviation > 0 ? (averageReturn / returnDeviation) * Math.sqrt(periodsPerYear) : NaN,
    sortino: downsideDeviation > 0 ? (averageReturn * periodsPerYear) / downsideDeviation : NaN,
    calmar: Number.isFinite(maxDrawdown) && maxDrawdown < 0 ? annualReturn / Math.abs(maxDrawdown) : NaN,
  };
}

function elapsedCalendarDays(start, end) {
  const startDate = parseDateValue(start);
  const endDate = parseDateValue(end);
  if (!startDate || !endDate) return NaN;
  const days = (endDate.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000);
  return days > 0 ? days : NaN;
}

function mean(values) {
  const numbers = values.filter(Number.isFinite);
  if (!numbers.length) return NaN;
  return numbers.reduce((total, value) => total + value, 0) / numbers.length;
}

function standardDeviation(values) {
  const numbers = values.filter(Number.isFinite);
  if (numbers.length < 2) return NaN;
  const average = mean(numbers);
  const variance = numbers.reduce((total, value) => total + (value - average) ** 2, 0) / (numbers.length - 1);
  return Math.sqrt(variance);
}

function downsideRiskDeviation(values) {
  const downsideSquares = values
    .filter(Number.isFinite)
    .map((value) => Math.min(0, value) ** 2);
  if (!downsideSquares.length) return NaN;
  return Math.sqrt(downsideSquares.reduce((total, value) => total + value, 0) / downsideSquares.length);
}

function minFinite(values) {
  const numbers = values.filter(Number.isFinite);
  return numbers.length ? Math.min(...numbers) : NaN;
}

function firstRunSummaryMetric(run, keys) {
  for (const key of keys) {
    const value = metricValue(run, 'strategy.summary', key);
    if (value !== null && value !== undefined && value !== '') return value;
  }
  return null;
}

function firstRunMetric(run, paths) {
  for (const path of paths) {
    const parts = String(path || '').split('.');
    const key = parts.pop();
    const namespace = parts.join('.');
    if (!namespace || !key) continue;
    const value = metricValue(run, namespace, key);
    if (value !== null && value !== undefined && value !== '') return value;
  }
  return null;
}

function formatPercentMetric(value) {
  const formatted = formatMetric(value);
  return formatted === '--' ? formatted : `${formatted}%`;
}

function scrollPageToTop() {
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    document.scrollingElement?.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  });
}

function researchChampionRun(research, branches, runs) {
  if (research?.champion_run) return research.champion_run;
  const branchIds = new Set((branches || [])
    .filter((branch) => !research?.id || branch.research_id === research.id)
    .map((branch) => branch.id));
  return [...(runs || [])]
    .filter((run) => (!branchIds.size || branchIds.has(run.branch_id)) && run.status === 'completed')
    .sort((a, b) => Number(metricValue(b, 'strategy.summary', 'sharpe') ?? -Infinity) - Number(metricValue(a, 'strategy.summary', 'sharpe') ?? -Infinity))[0] || null;
}

function summaryMetricRows(summary) {
  const rows = [];
  for (const [namespace, values] of Object.entries(summary || {})) {
    if (!values || typeof values !== 'object' || Array.isArray(values)) continue;
    for (const [key, value] of Object.entries(values)) {
      const number = Number(value);
      if (Number.isFinite(number)) rows.push({ metric: `${namespace}.${key}`, value: number });
    }
  }
  return rows.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
}

function sweepMetricOptions(runs) {
  const options = [];
  for (const run of runs || []) {
    for (const row of summaryMetricRows(run.summary_json || {})) {
      if (!options.includes(row.metric)) options.push(row.metric);
    }
  }
  const preferred = ['strategy.summary.sharpe', 'strategy.summary.max_drawdown', 'strategy.summary.turnover', 'strategy.summary.ic_mean'];
  return [
    ...preferred.filter((metric) => options.includes(metric)),
    ...options.filter((metric) => !preferred.includes(metric)),
  ];
}

function runResultItems(run) {
  return (run.artifacts || [])
    .map((artifact) => {
      const result = artifactResultMetadata(artifact);
      if (!result) return null;
      const domain = String(result.domain || 'custom').toLowerCase();
      const role = String(result.role || 'artifact').toLowerCase();
      return {
        artifact,
        result,
        domain,
        role,
        group: result.group || `${domain}.${result.name || artifact.name}`,
        title: result.title || result.name || artifact.name,
        order: Number.isFinite(Number(result.order)) ? Number(result.order) : 50,
      };
    })
    .filter(Boolean)
    .sort((left, right) => resultDomainOrder(left.domain) - resultDomainOrder(right.domain) || left.order - right.order || left.title.localeCompare(right.title));
}

function artifactResultMetadata(artifact) {
  const metadata = artifact.metadata_json || {};
  if (metadata.result && typeof metadata.result === 'object' && !Array.isArray(metadata.result)) {
    return metadata.result;
  }
  const series = metadata.series && typeof metadata.series === 'object' ? metadata.series : null;
  const metric = metadata.metric && typeof metadata.metric === 'object' ? metadata.metric : null;
  const name = String(series?.name || artifact.name || '').toLowerCase();
  const namespace = String(series?.namespace || metric?.namespace || '').toLowerCase();
  const kind = String(artifact.kind || '').toLowerCase();
  if (['equity_curve', 'returns_series', 'returns', 'pnl_series', 'absolute_return_series'].includes(name) || namespace.startsWith('strategy.returns') || namespace.startsWith('strategy.pnl') || namespace.startsWith('strategy.equity')) {
    return {
      domain: 'performance',
      name: 'primary_performance',
      role: 'primary_curve',
      title: 'Performance Curve',
      group: 'performance.primary',
      order: 10,
      view: { default: 'performance_chart', x: series?.x, y: series?.y, mode: series?.mode, chart: 'line_drawdown' },
    };
  }
  if (name === 'drawdown_series' || name === 'drawdown' || namespace.includes('drawdown') || series?.mode === 'drawdown') {
    return {
      domain: 'performance',
      name: 'primary_drawdown',
      role: 'drawdown',
      title: 'Drawdown',
      group: 'performance.primary',
      order: 20,
      view: { default: 'drawdown', x: series?.x, y: series?.y, mode: 'drawdown', chart: 'area' },
    };
  }
  if (name.includes('factor_ic') || namespace.startsWith('factor.ic')) {
    return {
      domain: 'factor',
      name: metric?.key || 'primary_ic',
      role: 'ic_curve',
      title: 'Factor IC',
      group: 'factor.primary',
      order: 10,
      view: { default: 'plot', x: series?.x, y: series?.y, chart: 'line' },
    };
  }
  if (name.includes('quantile') || name.includes('group_return') || namespace.startsWith('factor.quantile')) {
    return {
      domain: 'factor',
      name: metric?.key || 'primary_quantile_returns',
      role: 'quantile_returns',
      title: 'Grouped Returns',
      group: 'factor.primary',
      order: 20,
      view: { default: 'table', chart: 'bar' },
    };
  }
  if (name.includes('factor_comparison') || name.includes('factor_rank') || namespace.startsWith('factor.batch')) {
    return {
      domain: 'factor_batch',
      name: metric?.key || name || 'factor_comparison',
      role: series ? 'comparison_curve' : 'comparison_table',
      title: series ? 'Factor Return Comparison' : 'Factor Comparison',
      group: 'factor_batch.primary',
      order: series ? 20 : 10,
      view: { default: series ? 'plot' : 'table', x: series?.x, y: series?.y, chart: series ? 'line' : undefined },
    };
  }
  if (metric) {
    const domain = namespace.split('.')[0] || 'custom';
    return {
      domain,
      name: metric.key || artifact.name,
      role: metric.kind === 'series' ? 'metric_series' : 'metric_table',
      title: metric.key || artifact.name,
      group: namespace || `${domain}.metrics`,
      order: 50,
      view: { default: metric.kind === 'series' ? 'plot' : 'table', x: metric.x, y: metric.y, mode: metric.mode },
    };
  }
  if (kind.includes('report') || kind.includes('risk') || kind.includes('position') || kind.includes('trade')) {
    return {
      domain: kind.includes('risk') ? 'risk' : 'diagnostic',
      name: artifact.name,
      role: kind.includes('report') ? 'report' : 'table',
      title: artifact.name,
      group: kind.includes('risk') ? 'risk.primary' : 'diagnostic.primary',
      order: 80,
      view: { default: kind.includes('report') ? 'report' : 'table' },
    };
  }
  return null;
}

function groupRunResultsByDomain(items) {
  const domains = new Map();
  for (const item of items || []) {
    if (!domains.has(item.domain)) domains.set(item.domain, new Map());
    const domain = domains.get(item.domain);
    const key = item.group || `${item.domain}.default`;
    domain.set(key, [...(domain.get(key) || []), item]);
  }
  return Array.from(domains.entries())
    .map(([domain, groups]) => ({
      domain,
      itemCount: Array.from(groups.values()).reduce((total, groupItems) => total + groupItems.length, 0),
      groups: Array.from(groups.entries()).map(([key, groupItems]) => ({
        key,
        title: resultGroupTitle(key, groupItems),
        items: [...groupItems].sort((left, right) => left.order - right.order || left.title.localeCompare(right.title)),
      })).sort((left, right) => left.title.localeCompare(right.title)),
    }))
    .sort((left, right) => resultDomainOrder(left.domain) - resultDomainOrder(right.domain) || resultDomainLabel(left.domain).localeCompare(resultDomainLabel(right.domain)));
}

function resultGroupTitle(key, items) {
  const explicit = items.find((item) => item.result.group_title)?.result.group_title;
  if (explicit) return explicit;
  const suffix = String(key || '').split('.').filter(Boolean).slice(1).join(' / ');
  return suffix || resultDomainLabel(items[0]?.domain);
}

function resultDomainOrder(domain) {
  return {
    performance: 0,
    factor: 10,
    factor_batch: 20,
    risk: 30,
    cost: 40,
    diagnostic: 50,
    custom: 90,
  }[domain] ?? 80;
}

function resultDomainLabel(domain) {
  return {
    performance: 'Performance',
    factor: 'Factor',
    factor_batch: 'Factor Batch',
    risk: 'Risk',
    cost: 'Cost',
    diagnostic: 'Diagnostics',
    custom: 'Custom',
  }[domain] || titleCase(domain);
}

function resultRoleLabel(role) {
  return {
    primary_curve: 'Primary Curve',
    drawdown: 'Drawdown',
    summary_table: 'Summary Table',
    ic_curve: 'IC Curve',
    quantile_returns: 'Grouped Returns',
    comparison_table: 'Comparison Table',
    comparison_curve: 'Comparison Curve',
    metric_series: 'Metric Series',
    metric_table: 'Metric Table',
    report: 'Report',
    table: 'Table',
  }[role] || titleCase(role);
}

function titleCase(value) {
  return String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function runSeriesArtifacts(run) {
  const preferred = ['equity_curve', 'returns', 'returns_series', 'pnl_series', 'absolute_return_series', 'drawdown_series', 'factor_ic_series', 'turnover'];
  return (run.artifacts || [])
    .map((artifact) => {
      const metadata = artifact.metadata_json || {};
      const series = metadata.series && typeof metadata.series === 'object' ? metadata.series : null;
      const rows = Array.isArray(artifact.preview_json?.rows) ? artifact.preview_json.rows : [];
      if (!series || !rows.length) return null;
      const yKeys = Array.isArray(series.y) ? series.y : [series.y || 'series_values'].filter(Boolean);
      const numericYKeys = yKeys.filter((key) => rows.some((row) => Number.isFinite(toNumber(row?.[key]))));
      if (!numericYKeys.length) return null;
      return {
        id: artifact.id,
        name: series.name || artifact.name,
        artifactName: artifact.name,
        x: series.x || null,
        y: numericYKeys,
        mode: series.mode || null,
        namespace: series.namespace || null,
        result: artifactResultMetadata(artifact),
        previewRowCount: Number(artifact.preview_json?.row_count),
        rows,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      const leftRank = preferred.indexOf(left.name);
      const rightRank = preferred.indexOf(right.name);
      return (leftRank === -1 ? 999 : leftRank) - (rightRank === -1 ? 999 : rightRank) || left.name.localeCompare(right.name);
    });
}

function runEquityChartData(items) {
  const equityKeys = ['series_values', 'nav', 'net_value', 'equity', 'value', 'cumulative_return', 'cum_return', 'total_return', 'return', 'ret', 'pnl', 'profit', 'delta', 'change', 'amount'];
  const equityItem = findResultSeriesItem(items, 'performance', 'primary_curve', equityKeys) || findSeriesItem(
    items,
    ['equity_curve', 'nav', 'net_value', 'cumulative_return', 'returns_series', 'returns', 'pnl_series', 'absolute_return_series', 'pnl', 'profit_series', 'delta_series'],
    equityKeys
  );
  if (!equityItem) return null;
  const equityKey = chooseSeriesKey(equityItem, equityKeys);
  if (!equityKey) return null;
  const xKey = equityItem.x;
  const valueMode = seriesValueMode(equityItem, equityKey);
  const equityPoints = [];
  let compounded = 1;
  let cumulative = 0;
  for (const { row, x } of sortedChartRows(equityItem.rows || [], xKey)) {
    const raw = toNumber(row?.[equityKey]);
    if (!Number.isFinite(raw)) continue;
    if (valueMode === 'period_return') {
      compounded *= 1 + raw;
      equityPoints.push({ x, value: compounded - 1 });
    } else if (valueMode === 'absolute_change') {
      cumulative += raw;
      equityPoints.push({ x, value: cumulative });
    } else {
      equityPoints.push({ x, value: raw });
    }
  }
  if (!equityPoints.length) return null;

  const drawdownItem = findDrawdownSeriesItem(items);
  const drawdownKey = drawdownItem ? chooseSeriesKey(drawdownItem, ['drawdown', 'max_drawdown', 'dd', 'series_values']) : null;
  let drawdownPoints = [];
  if (drawdownItem && drawdownKey) {
    drawdownPoints = sortedChartRows(drawdownItem.rows || [], drawdownItem.x).map(({ row, x }) => ({
      x,
      value: normalizeDrawdown(toNumber(row?.[drawdownKey]), valueMode),
    })).filter((point) => Number.isFinite(point.value));
  }
  if (!drawdownPoints.length) {
    drawdownPoints = computeDrawdownPoints(equityPoints, valueMode);
  }

  const xValues = [];
  const addX = (x) => {
    if (!xValues.includes(x)) xValues.push(x);
  };
  equityPoints.forEach((point) => addX(point.x));
  drawdownPoints.forEach((point) => addX(point.x));
  xValues.sort(compareChartXValues);
  const equityByX = new Map(equityPoints.map((point) => [point.x, point.value]));
  const drawdownByX = new Map(drawdownPoints.map((point) => [point.x, point.value]));
  const xAxisType = shouldUseTimeAxis(xValues.map((x) => [x, 0])) ? 'time' : 'category';
  return {
    xValues,
    xAxisType,
    equityData: xValues.map((x) => [x, equityByX.get(x) ?? null]),
    drawdownData: xValues.map((x) => [x, drawdownByX.get(x) ?? null]),
    lineName: chartLineName(valueMode, equityKey),
    valueAsPercent: valueMode === 'period_return',
    drawdownAsPercent: valueMode !== 'absolute_change',
    valueMode,
  };
}

function findResultSeriesItem(items, domain, role, keys) {
  return (items || []).find((item) => {
    const result = item.result || {};
    if (String(result.domain || '').toLowerCase() !== domain) return false;
    if (String(result.role || '').toLowerCase() !== role) return false;
    return chooseSeriesKey(item, keys);
  }) || null;
}

function findSeriesItem(items, names, keys) {
  const normalizedNames = names.map((name) => name.toLowerCase());
  const normalizedKeys = keys.map((key) => key.toLowerCase());
  return (items || []).find((item) => normalizedNames.some((name) => String(item.name || '').toLowerCase().includes(name)) && chooseSeriesKey(item, normalizedKeys))
    || (items || []).find((item) => chooseSeriesKey(item, normalizedKeys));
}

function findSeriesItemStrict(items, names, keys) {
  const normalizedNames = names.map((name) => name.toLowerCase());
  const normalizedKeys = keys.map((key) => key.toLowerCase());
  return (items || []).find((item) => normalizedNames.some((name) => String(item.name || '').toLowerCase().includes(name)) && chooseSeriesKeyStrict(item, normalizedKeys))
    || (items || []).find((item) => chooseSeriesKeyStrict(item, normalizedKeys));
}

function findDrawdownSeriesItem(items) {
  const resultItem = findResultSeriesItem(items, 'performance', 'drawdown', ['drawdown', 'max_drawdown', 'dd', 'series_values']);
  if (resultItem) return resultItem;
  return (items || []).find((item) => {
    const name = String(item.name || '').toLowerCase();
    const namespace = String(item.namespace || '').toLowerCase();
    const mode = String(item.mode || '').toLowerCase();
    if (!(name.includes('drawdown') || name === 'dd' || namespace.includes('drawdown') || mode === 'drawdown')) return false;
    return chooseSeriesKey(item, ['drawdown', 'max_drawdown', 'dd', 'series_values']);
  }) || null;
}

function chooseSeriesKey(item, preferredKeys) {
  const keys = (item?.y || []).filter((key) => (item.rows || []).some((row) => Number.isFinite(toNumber(row?.[key]))));
  if (!keys.length) return null;
  const normalizedPreferred = preferredKeys.map((key) => key.toLowerCase());
  return keys.find((key) => normalizedPreferred.includes(String(key).toLowerCase()))
    || keys.find((key) => normalizedPreferred.some((preferred) => String(key).toLowerCase().includes(preferred)))
    || keys[0];
}

function chooseSeriesKeyStrict(item, preferredKeys) {
  const keys = (item?.y || []).filter((key) => (item.rows || []).some((row) => Number.isFinite(toNumber(row?.[key]))));
  if (!keys.length) return null;
  const normalizedPreferred = preferredKeys.map((key) => key.toLowerCase());
  return keys.find((key) => normalizedPreferred.includes(String(key).toLowerCase()))
    || keys.find((key) => normalizedPreferred.some((preferred) => String(key).toLowerCase().includes(preferred)))
    || null;
}

function seriesValueMode(item, key) {
  const explicitMode = String(item?.mode || '').toLowerCase();
  if (['return', 'returns', 'period_return', 'periodic_return'].includes(explicitMode)) return 'period_return';
  if (['pnl', 'profit', 'absolute', 'absolute_return', 'absolute_change'].includes(explicitMode)) return 'absolute_change';
  if (['nav', 'equity', 'net_value', 'level'].includes(explicitMode)) return 'level';
  if (isAbsoluteChangeSeries(item, key)) return 'absolute_change';
  if (isPeriodicReturnSeries(item, key)) return 'period_return';
  return 'level';
}

function isPeriodicReturnSeries(item, key) {
  const keyName = String(key || '').toLowerCase();
  const seriesName = String(item?.name || '').toLowerCase();
  if (/cumulative|cum_|total/.test(keyName)) return false;
  if (!/^(ret|return|returns|daily_return|period_return)$/.test(keyName)) return false;
  const values = (item?.rows || []).map((row) => Math.abs(toNumber(row?.[key]))).filter(Number.isFinite);
  return seriesName.includes('return') && values.length && Math.max(...values) < 1;
}

function isAbsoluteChangeSeries(item, key) {
  const keyName = String(key || '').toLowerCase();
  const seriesName = String(item?.name || '').toLowerCase();
  const namespace = String(item?.namespace || '').toLowerCase();
  if (/equity|nav|net_value|drawdown|cumulative|cum_|total/.test(seriesName) || /cumulative|cum_|total|nav|net_value|equity/.test(keyName)) return false;
  if (/pnl|profit|absolute|amount|delta|change/.test(seriesName) || /pnl|profit|amount|delta|change/.test(keyName) || namespace.includes('pnl')) return true;
  if (/return/.test(seriesName) && /absolute/.test(seriesName)) return true;
  return false;
}

function chartLineName(valueMode, key) {
  if (valueMode === 'period_return') return 'Cumulative Return';
  if (valueMode === 'absolute_change') return /pnl|profit/i.test(String(key || '')) ? 'Cumulative PnL' : 'Cumulative Change';
  return 'Net Value';
}

function chartXValue(row, xKey, index) {
  const value = xKey ? row?.[xKey] : undefined;
  if (value === null || value === undefined || value === '') return String(index + 1);
  return normalizeChartXValue(value);
}

function sortedChartRows(rows, xKey) {
  return (rows || [])
    .map((row, index) => ({ row, index, x: chartXValue(row, xKey, index) }))
    .sort((left, right) => compareChartXValues(left.x, right.x) || left.index - right.index);
}

function normalizeChartXValue(value) {
  const raw = String(value).trim();
  const date = parseChartDate(raw);
  return date ? date.iso : raw;
}

function parseChartDate(value) {
  const raw = String(value || '').trim();
  let match = raw.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T].*)?$/);
  if (!match) match = raw.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  const timestamp = Date.UTC(year, month - 1, day);
  const date = new Date(timestamp);
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return { iso: `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`, timestamp };
}

function chartXSortValue(value) {
  const date = parseChartDate(value);
  if (date) return { type: 'date', value: date.timestamp };
  const number = toNumber(value);
  if (Number.isFinite(number)) return { type: 'number', value: number };
  return { type: 'text', value: String(value || '') };
}

function compareChartXValues(left, right) {
  const a = chartXSortValue(left);
  const b = chartXSortValue(right);
  if (a.type === b.type) {
    if (a.type === 'text') return a.value.localeCompare(b.value, undefined, { numeric: true, sensitivity: 'base' });
    return a.value - b.value;
  }
  const rank = { date: 0, number: 1, text: 2 };
  return rank[a.type] - rank[b.type];
}

function normalizeChartPoints(points) {
  const byX = new Map();
  for (const point of points || []) {
    const x = normalizeChartXValue(point?.[0]);
    const y = toNumber(point?.[1]);
    if (!x || !Number.isFinite(y)) continue;
    byX.set(x, y);
  }
  return Array.from(byX.entries())
    .sort(([left], [right]) => compareChartXValues(left, right))
    .map(([x, y]) => [x, y]);
}

function sortedUniqueChartXValues(values) {
  return Array.from(new Set((values || []).map(normalizeChartXValue).filter(Boolean))).sort(compareChartXValues);
}

function shouldUseTimeAxis(points) {
  const values = (points || []).map((point) => Array.isArray(point) ? point[0] : point).filter((value) => value !== null && value !== undefined && value !== '');
  return values.length > 0 && values.every((value) => Boolean(parseChartDate(value)));
}

function normalizeDrawdown(value, valueMode = 'level') {
  if (!Number.isFinite(value)) return NaN;
  if (valueMode === 'absolute_change') return value > 0 ? -value : value;
  return value > 1 ? -Math.abs(value) / 100 : value > 0 ? -value : value;
}

function computeDrawdownPoints(equityPoints, valueMode) {
  let runningPeak = -Infinity;
  return equityPoints.map((point) => {
    if (valueMode === 'absolute_change') {
      if (!Number.isFinite(point.value)) return { x: point.x, value: null };
      runningPeak = Math.max(runningPeak, point.value);
      return { x: point.x, value: point.value - runningPeak };
    }
    const nav = valueMode === 'period_return' ? 1 + point.value : point.value;
    if (!Number.isFinite(nav)) return { x: point.x, value: null };
    runningPeak = Math.max(runningPeak, nav);
    return { x: point.x, value: runningPeak > 0 ? nav / runningPeak - 1 : 0 };
  }).filter((point) => Number.isFinite(point.value));
}

function runEquityChartOption(chart) {
  const drawdowns = chart.drawdownData.map((point) => point[1]).filter(Number.isFinite);
  const minDrawdown = drawdowns.length ? Math.min(...drawdowns) : 0;
  const drawdownAxisMin = minDrawdown < 0 ? minDrawdown * 1.12 : -0.001;
  const percentLabel = (value) => {
    const percent = value * 100;
    const digits = Math.abs(percent) < 1 ? 2 : 1;
    return `${percent.toFixed(digits)}%`;
  };
  return {
    animation: false,
    color: ['#111111', '#dc2626'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const rows = params.map((item) => {
          const value = item.value?.[1];
          const formatted = Number.isFinite(value) ? ((item.seriesName === 'Drawdown' ? chart.drawdownAsPercent : chart.valueAsPercent) ? percentLabel(value) : formatMetric(value)) : '--';
          return `${item.marker}${item.seriesName}: ${formatted}`;
        });
        return [params[0]?.axisValueLabel, ...rows].filter(Boolean).join('<br/>');
      },
    },
    grid: { top: 12, left: 56, right: 58, bottom: 36 },
    xAxis: {
      type: chart.xAxisType || 'category',
      boundaryGap: false,
      ...(chart.xAxisType === 'time' ? {} : { data: chart.xValues || [] }),
      axisLine: { lineStyle: { color: '#d7dce2' } },
      axisTick: { show: false },
      axisLabel: { color: '#5f6b7a', hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        scale: true,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: '#edf0f3' } },
        axisLabel: { color: '#5f6b7a', formatter: chart.valueAsPercent ? percentLabel : undefined },
      },
      {
        type: 'value',
        max: 0,
        min: drawdownAxisMin,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#374151', formatter: chart.drawdownAsPercent ? percentLabel : undefined },
      },
    ],
    series: [
      {
        name: chart.lineName,
        type: 'line',
        yAxisIndex: 0,
        data: chart.equityData,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: '#111111', width: 2 },
        z: 3,
      },
      {
        name: 'Drawdown',
        type: 'line',
        yAxisIndex: 1,
        data: chart.drawdownData,
        showSymbol: false,
        smooth: false,
        lineStyle: { width: 0, color: 'rgba(220, 38, 38, 0)' },
        areaStyle: { color: 'rgba(220, 38, 38, 0.24)', origin: 'end' },
        z: 1,
      },
    ],
  };
}

function runSummaryChartOption(rows) {
  return {
    animation: false,
    tooltip: { trigger: 'axis' },
    grid: { top: 24, left: 150, right: 32, bottom: 32 },
    xAxis: { type: 'value', scale: true },
    yAxis: { type: 'category', data: rows.map((row) => row.metric), axisLabel: { width: 138, overflow: 'truncate' } },
    series: [{
      type: 'bar',
      data: rows.map((row) => row.value),
      itemStyle: { color: '#16803d' },
    }],
  };
}

function runRuntime(run) {
  const start = new Date(run.started_at || run.created_at).getTime();
  const end = new Date(run.ended_at || run.updated_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '--';
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${(minutes / 60).toFixed(1)}h`;
}

function runRuntimeSeconds(run) {
  const start = new Date(run.started_at || run.created_at).getTime();
  const end = new Date(run.ended_at || run.updated_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return NaN;
  return Math.round((end - start) / 1000);
}


function defaultRunsCompareSetName(runs) {
  const firstRun = runs[0] || {};
  const scope = firstRun.research_key || firstRun.project_key || 'runs';
  const now = new Date();
  const hhmmss = [now.getHours(), now.getMinutes(), now.getSeconds()].map((value) => String(value).padStart(2, '0')).join('');
  return `${scope}-compare-${runs.length}-runs-${dateKey(now)}-${hhmmss}`;
}

function runMatchesRunBoardFilters(run, filters) {
  const normalizedQuery = String(filters.query || '').trim().toLowerCase();
  if (filters.projectKey && run.project_key !== filters.projectKey) return false;
  if (filters.researchKey && run.research_key !== filters.researchKey) return false;
  if (filters.branchKey && run.branch_key !== filters.branchKey) return false;
  if (filters.status && run.status !== filters.status) return false;
  if (filters.creator && (run.created_by_type || 'human') !== filters.creator) return false;
  const artifactCount = Number(run.artifact_count || 0);
  if (filters.artifactOnly === 'yes' && artifactCount <= 0) return false;
  if (filters.artifactOnly === 'report' && !run.has_report_artifact) return false;
  if (filters.artifactOnly === 'none' && artifactCount > 0) return false;
  if (!normalizedQuery) return true;
  return runBoardSearchText(run).includes(normalizedQuery);
}

function runBoardSearchText(run) {
  return [
    run.id,
    run.name,
    run.title,
    run.status,
    run.project_key,
    run.research_key,
    run.branch_key,
    run.branch_id,
    runCreator(run),
    configSummary(run.config_json),
    JSON.stringify(run.config_json || {}),
    JSON.stringify(run.context_json || {}),
    ...(run.tags || []),
    ...(run.artifact_kinds || []),
  ].filter(Boolean).join(' ').toLowerCase();
}

function defaultRunBoardSortDirection(key) {
  return ['name', 'project', 'branch', 'status', 'creator'].includes(key) ? 'asc' : 'desc';
}

function sortRunsForBoard(runs, sort) {
  const direction = sort?.direction === 'asc' ? 1 : -1;
  const key = sort?.key || 'updated';
  return [...(runs || [])].sort((left, right) => compareRunBoardValues(runBoardSortValue(left, key), runBoardSortValue(right, key)) * direction);
}

function runBoardSortValue(run, key) {
  if (key === 'name') return run.name || run.title || run.id || '';
  if (key === 'project') return run.project_key || '';
  if (key === 'branch') return `${run.research_key || ''} ${run.branch_key || run.branch_id || ''}`;
  if (key === 'status') return run.status || '';
  if (key === 'creator') return runCreator(run);
  if (key === 'sharpe') return toNumber(metricValue(run, 'strategy.summary', 'sharpe'));
  if (key === 'max_drawdown') return toNumber(metricValue(run, 'strategy.summary', 'max_drawdown'));
  if (key === 'runtime') return runRuntimeSeconds(run);
  if (key === 'artifacts') return Number(run.artifact_count || 0);
  if (key === 'created') return dateMillis(run.created_at || run.started_at);
  return dateMillis(run.updated_at || run.ended_at || run.started_at || run.created_at);
}

function compareRunBoardValues(left, right) {
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  const leftFinite = Number.isFinite(leftNumber);
  const rightFinite = Number.isFinite(rightNumber);
  if (leftFinite && rightFinite) return leftNumber - rightNumber;
  if (leftFinite) return 1;
  if (rightFinite) return -1;
  return String(left || '').localeCompare(String(right || ''));
}

function branchEvolutionMetrics(runs) {
  const preferred = ['strategy.summary.sharpe', 'strategy.summary.max_drawdown', 'strategy.summary.ic_mean', 'strategy.summary.turnover'];
  const allMetrics = new Set();
  for (const run of runs) {
    for (const [namespace, values] of Object.entries(run.summary_json || {})) {
      if (!values || typeof values !== 'object' || Array.isArray(values)) continue;
      for (const [key, value] of Object.entries(values)) {
        if (Number.isFinite(Number(value))) allMetrics.add(`${namespace}.${key}`);
      }
    }
  }
  const ordered = preferred.filter((metric) => allMetrics.has(metric));
  for (const metric of allMetrics) {
    if (ordered.length >= 4) break;
    if (!ordered.includes(metric)) ordered.push(metric);
  }
  return ordered;
}

function branchMetricOption(runs, metrics) {
  const labels = runs.map((run) => run.name);
  const series = metrics.map((metric) => ({
    name: metric,
    type: 'line',
    showSymbol: false,
    data: runs.map((run) => toNumber(getSummaryMetric(run.summary_json, metric))),
  }));
  return {
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    grid: { top: 54, left: 56, right: 24, bottom: 62 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: labels.some((label) => label.length > 16) ? 30 : 0 } },
    yAxis: { type: 'value', scale: true },
    series: series.length ? series : [{ name: 'metrics', type: 'line', showSymbol: false, data: [] }],
  };
}

function configEvolutionRows(runs) {
  const rows = [];
  for (let index = 1; index < runs.length; index += 1) {
    const previous = flattenObject(runs[index - 1].config_json || {});
    const current = flattenObject(runs[index].config_json || {});
    const keys = Array.from(new Set([...Object.keys(previous), ...Object.keys(current)])).sort();
    for (const key of keys) {
      if (JSON.stringify(previous[key]) !== JSON.stringify(current[key])) {
        rows.push({ run: runs[index], path: key, before: previous[key], after: current[key] });
      }
    }
  }
  return rows;
}

function flattenObject(value, prefix = '') {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return prefix ? { [prefix]: value } : {};
  }
  const entries = {};
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === 'object' && !Array.isArray(child)) {
      Object.assign(entries, flattenObject(child, path));
    } else {
      entries[path] = child;
    }
  }
  return entries;
}

function formatConfigValue(value) {
  if (value === undefined) return '--';
  if (value === null) return 'null';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `[${value.length}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).length}}`;
  return JSON.stringify(value);
}

function configSummary(config) {
  const entries = Object.entries(flattenObject(config || {}));
  if (!entries.length) return '--';
  return entries.slice(0, 3).map(([key, value]) => `${key}=${formatConfigValue(value)}`).join(', ');
}

function formatSweepObjective(objective) {
  if (!objective || typeof objective !== 'object') return '--';
  const metric = objective.metric || objective.target || objective.name;
  const direction = objective.direction || objective.mode;
  if (metric && direction) return `${metric} · ${direction}`;
  if (metric) return String(metric);
  return compactKeyValueSummary(objective);
}

function formatSearchSpace(searchSpace) {
  if (!searchSpace || typeof searchSpace !== 'object') return '--';
  const entries = Object.entries(searchSpace);
  if (!entries.length) return '--';
  return entries.slice(0, 4).map(([key, value]) => {
    if (Array.isArray(value)) return `${key}[${value.length}]`;
    return `${key}=${formatConfigValue(value)}`;
  }).join(', ');
}

function formatCoord(coord) {
  return compactKeyValueSummary(coord);
}

function formatFilterSummary(filters) {
  if (!filters || typeof filters !== 'object') return '--';
  const parts = [];
  if (filters.project_key) parts.push(`project=${filters.project_key}`);
  if (filters.research_key) parts.push(`research=${filters.research_key}`);
  if (filters.branch_key) parts.push(`branch=${filters.branch_key}`);
  if (filters.status) parts.push(`status=${filters.status}`);
  if (filters.has_artifact) parts.push(`artifact=${filters.has_artifact}`);
  if (Array.isArray(filters.tags) && filters.tags.length) parts.push(`tags=${filters.tags.join(',')}`);
  if (Array.isArray(filters.metrics) && filters.metrics.length) {
    parts.push(filters.metrics.slice(0, 2).map((item) => `${item.metric || 'metric'} ${item.op || '='} ${formatConfigValue(item.value)}`).join(', '));
  }
  if (filters.limit) parts.push(`limit=${filters.limit}`);
  return parts.length ? parts.join(' · ') : compactKeyValueSummary(filters);
}

function formatFilterTextSummary(text) {
  try {
    return formatFilterSummary(parseJsonObject(text));
  } catch {
    return 'Invalid JSON';
  }
}

function compactKeyValueSummary(value) {
  if (Array.isArray(value)) return value.length ? `[${value.length}] ${value.slice(0, 4).map(formatConfigValue).join(', ')}` : '--';
  const entries = Object.entries(value || {});
  if (!entries.length) return '--';
  const summary = entries.slice(0, 4).map(([key, item]) => `${key}=${formatConfigValue(item)}`).join(', ');
  const remaining = entries.length > 4 ? ` +${entries.length - 4}` : '';
  return `${summary}${remaining}`;
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return '--';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let scaled = bytes / 1024;
  let unitIndex = 0;
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024;
    unitIndex += 1;
  }
  return `${scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)} ${units[unitIndex]}`;
}

function buildSearchFilters(form) {
  const filters = {};
  if (form.project_key) filters.project_key = form.project_key;
  if (form.research_key) filters.research_key = form.research_key;
  if (form.branch_key) filters.branch_key = form.branch_key;
  if (form.status) filters.status = form.status;
  if (form.tags) filters.tags = parseCsv(form.tags);
  if (form.author_type) filters.author_type = form.author_type;
  if (form.created_after) filters.created_after = form.created_after;
  if (form.created_before) filters.created_before = form.created_before;
  if (form.has_artifact) filters.has_artifact = form.has_artifact;
  if (form.config_key) filters.config = { [form.config_key]: parseJsonScalar(form.config_value) };
  if (form.context_key) filters.context = { [form.context_key]: parseJsonScalar(form.context_value) };
  if (form.metric && form.metric_value !== '') {
    filters.metrics = [{ metric: form.metric, op: form.op || '==', value: parseJsonScalar(form.metric_value) }];
  }
  if (form.limit) filters.limit = Number(form.limit);
  return filters;
}

function buildResearchSearchFilters(form) {
  const filters = {};
  if (form.project_key) filters.project_key = form.project_key;
  if (form.status) filters.status = form.status;
  if (form.text) filters.text = form.text;
  if (form.tags) filters.tags = parseCsv(form.tags);
  if (form.limit) filters.limit = Number(form.limit);
  return filters;
}

function parseSearchWhere(where) {
  const text = String(where || '').trim();
  if (!text) return {};
  const filters = { tags: [], metrics: [], config: {}, context: {} };
  text.split(/\s+and\s+/i).map((clause) => clause.trim()).filter(Boolean).forEach((clause) => applySearchWhereClause(filters, clause));
  if (!filters.tags.length) delete filters.tags;
  if (!filters.metrics.length) delete filters.metrics;
  if (!Object.keys(filters.config).length) delete filters.config;
  if (!Object.keys(filters.context).length) delete filters.context;
  return filters;
}

function applySearchWhereClause(filters, clause) {
  const artifact = clause.match(/^has_artifact\(([^)]+)\)$/i);
  if (artifact) {
    filters.has_artifact = parseSearchScalar(artifact[1].trim().replace(/^['"]|['"]$/g, ''));
    return;
  }
  const contains = clause.match(/^([A-Za-z_][\w.]*)\s+contains\s+(.+)$/i);
  if (contains) {
    const field = contains[1];
    if (!['tag', 'tags'].includes(field)) throw new Error(`unsupported contains field: ${field}`);
    filters.tags.push(String(parseSearchScalar(contains[2])));
    return;
  }
  const binary = clause.match(/^([A-Za-z_][\w.]*)\s*(>=|<=|!=|==|>|<|=)\s*(.+)$/);
  if (!binary) throw new Error(`invalid where clause: ${clause}`);
  const [, field, op, rawValue] = binary;
  const value = parseSearchScalar(rawValue);
  if (field.startsWith('metrics.')) {
    filters.metrics.push({ metric: field.slice('metrics.'.length), op, value });
    return;
  }
  if (field.startsWith('config.')) {
    if (!['=', '=='].includes(op)) throw new Error(`unsupported config operator: ${op}`);
    filters.config[field.slice('config.'.length)] = value;
    return;
  }
  if (field.startsWith('context.')) {
    if (!['=', '=='].includes(op)) throw new Error(`unsupported context operator: ${op}`);
    filters.context[field.slice('context.'.length)] = value;
    return;
  }
  const simpleFields = {
    project: 'project_key',
    project_key: 'project_key',
    research: 'research_key',
    research_key: 'research_key',
    branch: 'branch_key',
    branch_key: 'branch_key',
    branch_id: 'branch_id',
    status: 'status',
    name: 'name',
    author_type: 'author_type',
  };
  if (simpleFields[field] && ['=', '=='].includes(op)) {
    filters[simpleFields[field]] = value;
    return;
  }
  throw new Error(`unsupported where clause: ${clause}`);
}

function parseSearchScalar(value) {
  const text = String(value ?? '').trim().replace(/^['"]|['"]$/g, '');
  return parseJsonScalar(text);
}

function getSummaryMetric(summary, metric) {
  const namespace = metric.split('.').slice(0, -1).join('.');
  const key = metric.split('.').slice(-1)[0];
  if (namespace && summary?.[namespace] && typeof summary[namespace] === 'object') {
    return summary[namespace][key];
  }
  return metric.split('.').reduce((current, part) => (current && typeof current === 'object' ? current[part] : undefined), summary);
}

function formatDate(value) {
  if (!value) return '--';
  return parseDateValue(value)?.toLocaleString() || '--';
}

function parseCsv(value) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function listOrCsv(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === 'string') return parseCsv(value);
  return [];
}

function parseCompareGroups(value, metricsText = '', seriesText = '') {
  const parsed = JSON.parse(value || '[]');
  if (!Array.isArray(parsed)) throw new Error('compare groups must be a JSON list');
  return parsed.map((group, index) => {
    if (!group || typeof group !== 'object' || Array.isArray(group)) throw new Error(`compare group at index ${index} must be an object`);
    const runIds = listOrCsv(group.run_ids);
    if (!runIds.length) throw new Error(`compare group at index ${index} has no run_ids`);
    return {
      name: group.name || `group_${index + 1}`,
      run_ids: runIds,
      metrics: listOrCsv(group.metrics).length ? listOrCsv(group.metrics) : parseCsv(metricsText),
      series: listOrCsv(group.series).length ? listOrCsv(group.series) : parseCsv(seriesText),
      with_config_diff: group.with_config_diff === undefined ? true : Boolean(group.with_config_diff),
    };
  });
}

function batchMetricSummary(metrics, metricNames) {
  const names = metricNames?.length ? metricNames : Object.keys(metrics || {});
  if (!names.length) return '--';
  return names.slice(0, 4).map((metric) => {
    const values = Object.values(metrics?.[metric] || {}).map((value) => Number(value)).filter(Number.isFinite);
    if (!values.length) return `${metric}: --`;
    const best = Math.max(...values);
    return `${metric}: best ${formatMetric(best)}`;
  }).join(', ');
}

function parseJsonObject(value) {
  const parsed = JSON.parse(value || '{}');
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('JSON must be an object');
  }
  return parsed;
}

function compactObject(value) {
  if (Array.isArray(value)) return value.map(compactObject);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, item]) => item !== '' && item !== undefined)
      .map(([key, item]) => [key, compactObject(item)]),
  );
}

function parseJsonArray(value) {
  const parsed = JSON.parse(value || '[]');
  if (!Array.isArray(parsed)) {
    throw new Error('JSON must be an array');
  }
  return parsed;
}

function parseJsonScalar(value) {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

async function fileSha256(file) {
  if (!window.crypto?.subtle) return '';
  const buffer = await file.arrayBuffer();
  const digest = await window.crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function heatIntensity(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0.08;
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return 0.42;
  return 0.18 + ((number - min) / (max - min)) * 0.56;
}

function entityName(entity) {
  return entity?.title || entity?.name || entity?.key || entity?.id || '';
}

function buildPageContext(data, active, selections, runDetail) {
  if (!data || active === 'dashboard') return {};
  if (active === 'management') return { extra: { label: 'Manage', value: '研究管理', active: 'management' } };
  const projects = data.projects || [];
  const researches = data.researches || [];
  const branches = data.branches || [];
  const runs = data.runs || [];
  const sweeps = data.sweeps || [];
  const compareSets = data.compare_sets || [];
  const searchViews = data.search_views || [];
  const selectedProject = projects.find((item) => item.id === selections.projectId) || projects[0] || null;
  const selectedResearch = researches.find((item) => item.id === selections.researchId) || researches[0] || null;
  const selectedBranch = branches.find((item) => item.id === selections.branchId) || branches[0] || null;
  const selectedRun = runDetail || runs.find((item) => item.id === selections.runId) || runs[0] || null;
  const selectedSweep = sweeps.find((item) => item.id === selections.sweepId) || sweeps[0] || null;
  const selectedCompareSet = compareSets.find((item) => item.id === selections.compareSetId) || null;
  const selectedSearchView = searchViews.find((item) => item.id === selections.searchViewId) || null;

  let project = null;
  let research = null;
  let branch = null;
  let run = null;
  let extra = null;

  if (active === 'project') {
    project = selectedProject;
  } else if (active === 'research') {
    research = selectedResearch;
    project = projects.find((item) => item.id === research?.project_id) || selectedProject;
  } else if (active === 'branch') {
    branch = selectedBranch;
    research = researches.find((item) => item.id === branch?.research_id) || selectedResearch;
    project = projects.find((item) => item.id === research?.project_id || item.id === branch?.project_id) || selectedProject;
  } else if (active === 'run') {
    run = selectedRun;
    branch = branches.find((item) => item.id === run?.branch_id) || selectedBranch;
    research = researches.find((item) => item.id === branch?.research_id || item.id === run?.research_id) || selectedResearch;
    project = projects.find((item) => item.id === run?.project_id || item.id === research?.project_id) || selectedProject;
  } else if (active === 'runs') {
    extra = { label: 'Runs', value: 'All Runs' };
  } else if (active === 'sweep') {
    extra = { label: 'Sweep', value: entityName(selectedSweep), id: selectedSweep?.id };
    branch = branches.find((item) => item.id === selectedSweep?.branch_id) || selectedBranch;
    research = researches.find((item) => item.id === branch?.research_id) || selectedResearch;
    project = projects.find((item) => item.id === research?.project_id || item.id === branch?.project_id) || selectedProject;
  } else if (active === 'compare') {
    extra = { label: 'Compare', value: entityName(selectedCompareSet), id: selectedCompareSet?.id };
    research = researches.find((item) => item.id === selectedCompareSet?.research_id) || null;
    project = projects.find((item) => item.id === selectedCompareSet?.project_id) || selectedProject;
  } else if (active === 'search') {
    extra = { label: 'Search', value: entityName(selectedSearchView), id: selectedSearchView?.id };
    project = projects.find((item) => item.id === selectedSearchView?.project_id) || selectedProject;
  }

  return { project, research, branch, run, extra };
}

function decodeRouteSegment(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function parseAppRoute(pathname = '/') {
  const [section, id] = String(pathname || '/').split('/').filter(Boolean).map(decodeRouteSegment);
  if (!section) return { active: 'dashboard' };
  if (section === 'manage') return { active: 'management' };
  if (section === 'projects') return { active: 'project', projectId: id || null };
  if (section === 'researches') return { active: 'research', researchId: id || null };
  if (section === 'branches') return { active: 'branch', branchId: id || null };
  if (section === 'runs') return id ? { active: 'run', runId: id } : { active: 'runs' };
  if (section === 'sweeps') return { active: 'sweep', sweepId: id || null };
  if (section === 'compare') return { active: 'compare', compareSetId: id || null };
  if (section === 'search') return { active: 'search', searchViewId: id || null };
  return { active: 'dashboard' };
}

function pathWithOptionalId(base, id) {
  return id ? `${base}/${encodeURIComponent(id)}` : base;
}

function pathForAppState(active, selections) {
  if (active === 'management') return '/manage';
  if (active === 'project') return pathWithOptionalId('/projects', selections.projectId);
  if (active === 'research') return pathWithOptionalId('/researches', selections.researchId);
  if (active === 'branch') return pathWithOptionalId('/branches', selections.branchId);
  if (active === 'run') return pathWithOptionalId('/runs', selections.runId);
  if (active === 'runs') return '/runs';
  if (active === 'sweep') return pathWithOptionalId('/sweeps', selections.sweepId);
  if (active === 'compare') return pathWithOptionalId('/compare', selections.compareSetId);
  if (active === 'search') return pathWithOptionalId('/search', selections.searchViewId);
  return '/';
}

function App() {
  const initialRouteRef = useRef(null);
  if (!initialRouteRef.current) {
    initialRouteRef.current = parseAppRoute(typeof window === 'undefined' ? '/' : window.location.pathname);
  }
  const skipNextHistoryWriteRef = useRef(false);
  const lastScrollPathRef = useRef(typeof window === 'undefined' ? '' : window.location.pathname);
  const initialRoute = initialRouteRef.current;
  const [active, setActive] = useState(initialRoute.active);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedResearchId, setSelectedResearchId] = useState(initialRoute.researchId || null);
  const [selectedBranchId, setSelectedBranchId] = useState(initialRoute.branchId || null);
  const [selectedRunId, setSelectedRunId] = useState(initialRoute.runId || null);
  const [selectedProjectId, setSelectedProjectId] = useState(initialRoute.projectId || null);
  const [selectedSweepId, setSelectedSweepId] = useState(initialRoute.sweepId || null);
  const [selectedCompareSetId, setSelectedCompareSetId] = useState(initialRoute.compareSetId || null);
  const [selectedSearchViewId, setSelectedSearchViewId] = useState(initialRoute.searchViewId || null);
  const [runDetail, setRunDetail] = useState(null);
  const [liveStatus, setLiveStatus] = useState('connecting');
  const [quickSearch, setQuickSearch] = useState(null);
  const [quickRunSearchOpen, setQuickRunSearchOpen] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const dashboard = await apiGet('/api/v1/dashboard');
      setData(dashboard);
      setSelectedProjectId((current) => current || dashboard.projects?.[0]?.id || null);
      setSelectedResearchId((current) => current || dashboard.researches?.[0]?.id || null);
      setSelectedBranchId((current) => current || dashboard.branches?.[0]?.id || null);
      setSelectedRunId((current) => current || dashboard.runs?.[0]?.id || null);
      setSelectedSweepId((current) => current || dashboard.sweeps?.[0]?.id || null);
      return dashboard;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setQuickRunSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const route = parseAppRoute(window.location.pathname);
      skipNextHistoryWriteRef.current = true;
      setActive(route.active);
      setSelectedProjectId(route.projectId || null);
      setSelectedResearchId(route.researchId || null);
      setSelectedBranchId(route.branchId || null);
      setSelectedRunId(route.runId || null);
      setSelectedSweepId(route.sweepId || null);
      setSelectedCompareSetId(route.compareSetId || null);
      setSelectedSearchViewId(route.searchViewId || null);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    const nextPath = pathForAppState(active, {
      projectId: selectedProjectId,
      researchId: selectedResearchId,
      branchId: selectedBranchId,
      runId: selectedRunId,
      sweepId: selectedSweepId,
      compareSetId: selectedCompareSetId,
      searchViewId: selectedSearchViewId,
    });
    if (skipNextHistoryWriteRef.current) {
      skipNextHistoryWriteRef.current = false;
      return;
    }
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath);
    }
  }, [active, selectedBranchId, selectedCompareSetId, selectedProjectId, selectedResearchId, selectedRunId, selectedSearchViewId, selectedSweepId]);

  useEffect(() => {
    const nextPath = pathForAppState(active, {
      projectId: selectedProjectId,
      researchId: selectedResearchId,
      branchId: selectedBranchId,
      runId: selectedRunId,
      sweepId: selectedSweepId,
      compareSetId: selectedCompareSetId,
      searchViewId: selectedSearchViewId,
    });
    if (lastScrollPathRef.current === nextPath) return;
    lastScrollPathRef.current = nextPath;
    scrollPageToTop();
  }, [active, selectedBranchId, selectedCompareSetId, selectedProjectId, selectedResearchId, selectedRunId, selectedSearchViewId, selectedSweepId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      refresh();
      if (active === 'run' && selectedRunId) loadRunDetail(selectedRunId);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [active, selectedRunId]);

  useEffect(() => {
    if (!window.WebSocket) {
      setLiveStatus('unavailable');
      return undefined;
    }
    setLiveStatus('connecting');
    let socket;
    let refreshTimer;
    let reconnectTimer;
    let stopped = false;
    const scheduleRefresh = () => {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        refresh();
        if (active === 'run' && selectedRunId) loadRunDetail(selectedRunId);
      }, 250);
    };
    const connect = () => {
      socket = new WebSocket(websocketUrl('/api/v1/ws'));
      socket.onopen = () => setLiveStatus('connected');
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type !== 'connected') scheduleRefresh();
        } catch {
          scheduleRefresh();
        }
      };
      socket.onerror = () => setLiveStatus('unavailable');
      socket.onclose = () => {
        if (stopped) return;
        setLiveStatus('unavailable');
        reconnectTimer = window.setTimeout(connect, 5000);
      };
    };
    connect();
    return () => {
      window.clearTimeout(refreshTimer);
      window.clearTimeout(reconnectTimer);
      stopped = true;
      if (socket) socket.close();
    };
  }, [active, selectedRunId]);

  const loadRunDetail = async (runId = selectedRunId) => {
    if (!runId) {
      setRunDetail(null);
      return null;
    }
    try {
      const detail = await apiGet(`/api/v1/runs/${runId}`);
      setRunDetail(detail);
      return detail;
    } catch {
      setRunDetail(null);
      return null;
    }
  };

  useEffect(() => {
    if (active === 'run') loadRunDetail(selectedRunId);
  }, [active, selectedRunId]);

  const selectProject = (id) => { setSelectedProjectId(id); setActive('project'); };
  const selectResearch = (id) => { setSelectedResearchId(id); setActive('research'); };
  const selectBranch = (id) => { setSelectedBranchId(id); setActive('branch'); };
  const selectRun = (id) => { setSelectedRunId(id); setActive('run'); };
  const selectSweep = (id) => { setSelectedSweepId(id); setActive('sweep'); };
  const selectCompareSet = (id) => { setSelectedCompareSetId(id || null); setActive('compare'); };
  const selectSearchView = (id) => { setSelectedSearchViewId(id); setActive('search'); };
  const selectSection = (id) => {
    if (id === 'compare') setSelectedCompareSetId(null);
    setActive(id);
  };
  const runGlobalSearch = (query) => {
    if (query) setQuickSearch({ query, nonce: Date.now() });
    setSelectedSearchViewId(null);
    setActive('search');
  };
  const onCreated = async (kind, entity) => {
    await refresh();
    if (kind === 'project') selectProject(entity.id);
    if (kind === 'research') selectResearch(entity.id);
    if (kind === 'branch') selectBranch(entity.id);
    if (kind === 'run') selectRun(entity.id);
    if (kind === 'sweep') selectSweep(entity.id);
    if (kind === 'compare-set') selectCompareSet(entity.id);
    if (kind === 'search-view') selectSearchView(entity.id);
  };
  const onRunChanged = async (runId) => {
    setSelectedRunId(runId);
    await loadRunDetail(runId);
    await refresh();
  };
  const onChanged = async () => {
    await refresh();
  };

  const pageContext = useMemo(() => buildPageContext(data, active, {
    projectId: selectedProjectId,
    researchId: selectedResearchId,
    branchId: selectedBranchId,
    runId: selectedRunId,
    sweepId: selectedSweepId,
    compareSetId: selectedCompareSetId,
    searchViewId: selectedSearchViewId,
  }, runDetail), [active, data, runDetail, selectedBranchId, selectedCompareSetId, selectedProjectId, selectedResearchId, selectedRunId, selectedSearchViewId, selectedSweepId]);

  const contextItems = useMemo(() => {
    if (active === 'dashboard') return [];
    return [
      { label: 'Dashboard', value: 'Dashboard', active: false, onSelect: () => setActive('dashboard') },
      pageContext.project ? { label: 'Project', value: entityName(pageContext.project), active: active === 'project', onSelect: () => selectProject(pageContext.project.id) } : null,
      pageContext.research ? { label: 'Research', value: entityName(pageContext.research), active: active === 'research', onSelect: () => selectResearch(pageContext.research.id) } : null,
      pageContext.branch ? { label: 'Branch', value: entityName(pageContext.branch), active: active === 'branch', onSelect: () => selectBranch(pageContext.branch.id) } : null,
      pageContext.run ? { label: 'Run', value: entityName(pageContext.run), active: active === 'run', onSelect: () => selectRun(pageContext.run.id) } : null,
      pageContext.extra ? { label: pageContext.extra.label, value: pageContext.extra.value, active: true, onSelect: () => setActive(pageContext.extra.active || active) } : null,
    ].filter(Boolean);
  }, [active, pageContext]);

  const page = useMemo(() => {
    if (error) return <EmptyState title="API unavailable" detail={error} />;
    if (!data && loading) return <EmptyState title="Loading Blackbox" detail="Fetching live data from the API." />;
    if (!data) return <EmptyState title="No API data" detail="Start the FastAPI server or set VITE_BLACKBOX_API_BASE." />;
    if (active === 'management') return <ManagementPage data={data} selectProject={selectProject} selectResearch={selectResearch} selectBranch={selectBranch} selectRun={selectRun} />;
    if (active === 'project') return <ProjectPage data={data} selectedProjectId={selectedProjectId} selectResearch={selectResearch} selectBranch={selectBranch} selectRun={selectRun} selectCompareSet={selectCompareSet} selectSearchView={selectSearchView} onChanged={onChanged} />;
    if (active === 'research') return <ResearchPage data={data} selectedResearchId={selectedResearchId} selectBranch={selectBranch} selectRun={selectRun} selectCompareSet={selectCompareSet} onChanged={onChanged} />;
    if (active === 'branch') return <BranchPage data={data} selectedBranchId={selectedBranchId} selectBranch={selectBranch} selectRun={selectRun} onChanged={onChanged} />;
    if (active === 'runs') return <RunsBoardPage data={data} selectRun={selectRun} selectBranch={selectBranch} selectCompareSet={selectCompareSet} onChanged={onChanged} />;
    if (active === 'run') return <RunPage runDetail={runDetail} data={data} onRunChanged={onRunChanged} />;
    if (active === 'sweep' && !SHOW_SWEEPS) return <Dashboard data={data} selectProject={selectProject} selectResearch={selectResearch} selectBranch={selectBranch} selectRun={selectRun} selectSweep={selectSweep} onChanged={onChanged} />;
    if (active === 'sweep') return <SweepPage data={data} selectedSweepId={selectedSweepId} selectSweep={selectSweep} selectRun={selectRun} onChanged={onChanged} />;
    if (active === 'search') return <SearchPage data={data} selectRun={selectRun} selectResearch={selectResearch} selectBranch={selectBranch} selectedSearchViewId={selectedSearchViewId} quickSearch={quickSearch} onChanged={onChanged} />;
    if (active === 'compare') return <ComparePage data={data} selectProject={selectProject} selectResearch={selectResearch} selectRun={selectRun} selectBranch={selectBranch} selectCompareSet={selectCompareSet} selectedCompareSetId={selectedCompareSetId} onChanged={onChanged} />;
    return <Dashboard data={data} selectProject={selectProject} selectResearch={selectResearch} selectBranch={selectBranch} selectRun={selectRun} selectSweep={selectSweep} onChanged={onChanged} />;
  }, [active, data, error, loading, quickSearch, runDetail, selectedBranchId, selectedCompareSetId, selectedProjectId, selectedResearchId, selectedSearchViewId, selectedSweepId]);

  return (
    <>
      <Shell
        active={active}
        onSelect={selectSection}
        data={data}
        onCreated={onCreated}
        onOpenSearch={() => setQuickRunSearchOpen(true)}
        contextNav={<ContextNav items={contextItems} />}
      >
        {page}
      </Shell>
      <QuickRunSearchModal open={quickRunSearchOpen} data={data} onClose={() => setQuickRunSearchOpen(false)} onSelectRun={selectRun} />
    </>
  );
}

const rootElement = document.getElementById('root');
const root = window.__BLACKBOX_ROOT__ ?? ReactDOM.createRoot(rootElement);
window.__BLACKBOX_ROOT__ = root;
root.render(<React.StrictMode><App /></React.StrictMode>);
