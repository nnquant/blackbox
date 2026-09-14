// Display recorded values verbatim: no inferred fee conversion or sample equivalence.
export function scopeFields(run) {
  const fields = {};
  const walk = (value, prefix) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) Object.entries(value).forEach(([key, item]) => walk(item, `${prefix}.${key}`));
    else fields[prefix] = value;
  };
  walk(run.config_json || {}, 'config');
  walk(run.context_json || {}, 'context');
  return fields;
}

export const scopeGroups = [
  { label: '样本 / 时间窗', match: /(?:^|[._])(start|end|start_date|end_date|date_start|date_end|sample|sample_start|sample_end|split|window|oos|period|train|valid|test)(?:$|[._])/i },
  { label: '费用 / 滑点', match: /fee|cost|commission|slippage/i },
  { label: '资产 / 数据 / 单位', match: /universe|asset|symbol|dataset|data_version|frequency|currency|unit|periods_per_year/i },
];

export function compareScope(runs) {
  const fields = runs.map(scopeFields);
  return scopeGroups.map(group => {
    const keys = [...new Set(fields.flatMap(item => Object.keys(item).filter(key => group.match.test(key))))].sort();
    const rows = keys.map(key => ({ key, values: fields.map(item => Object.hasOwn(item, key) ? JSON.stringify(item[key]) : '未提供') }));
    const missing = !rows.length || rows.some(row => row.values.includes('未提供'));
    const differs = rows.some(row => new Set(row.values).size > 1);
    return { label: group.label, rows, status: differs ? '存在差异' : missing ? '未提供 / 未校验' : '已记录字段一致 · 未校验业务等价性' };
  });
}
