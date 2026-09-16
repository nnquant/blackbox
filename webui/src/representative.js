export function representativeScore(run, metric = 'strategy.summary.sharpe') {
  const split = metric.lastIndexOf('.');
  const value = run?.summary_json?.[metric.slice(0, split)]?.[metric.slice(split + 1)];
  if (!['number', 'string'].includes(typeof value) || (typeof value === 'string' && !value.trim())) return -Infinity;
  const number = Number(value);
  return Number.isFinite(number) ? number : -Infinity;
}

export function representativeRun(runs, metric = 'strategy.summary.sharpe', manualId = null) {
  const recent = (a, b) => (Date.parse(b.updated_at || b.created_at) || 0) - (Date.parse(a.updated_at || a.created_at) || 0) || String(b.id).localeCompare(String(a.id));
  const manual = runs.filter(run => run.id === manualId || run.is_manual_baseline).sort(recent);
  if (manual.length) return manual[0];
  const scored = runs.filter(run => run.status === 'completed' && Number.isFinite(representativeScore(run, metric)));
  return scored.sort((a, b) => representativeScore(b, metric) - representativeScore(a, metric) || recent(a, b))[0] || [...runs].sort(recent)[0] || null;
}

export function representativeReason(run, metric = 'strategy.summary.sharpe') {
  if (!run) return '暂无 Run';
  if (run.is_manual_baseline) return '人工指定最优候选';
  return run.status === 'completed' && Number.isFinite(representativeScore(run, metric)) ? `最高 ${metric.split('.').pop()}` : '最新 Run（指标未齐）';
}
