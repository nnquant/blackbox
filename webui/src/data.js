export const summaryStats = [
  { label: '活跃项目', value: '12', delta: '+2', tone: 'info' },
  { label: '今日新增 Run', value: '156', delta: '+34', tone: 'positive' },
  { label: '运行中', value: '24', delta: '6 queued', tone: 'info' },
  { label: '24h 失败', value: '3', delta: '-5', tone: 'negative' },
  { label: '新增分支', value: '8', delta: '+3', tone: 'warning' },
];

export const topRuns = [
  { name: 'Eq_Mom_Alpha_v3', research: 'Global Equities', branch: 'scaled-alpha-v4', sharpe: 2.41, drawdown: '-8.2%', ic: 0.045, updated: '10m ago' },
  { name: 'StatArb_FX_G10', research: 'FX MeanRev', branch: 'experiment-beta', sharpe: 1.95, drawdown: '-12.1%', ic: 0.031, updated: '1h ago' },
  { name: 'Macro_Rates_Carry', research: 'Fixed Income', branch: 'carry-opt', sharpe: 1.62, drawdown: '-4.5%', ic: 0.022, updated: '3h ago' },
  { name: 'Vol_Dispersion_US', research: 'Options Vol', branch: 'main', sharpe: 1.45, drawdown: '-18.4%', ic: 0.018, updated: '5h ago' },
  { name: 'Crypto_Trend_Intraday', research: 'Digital Assets', branch: 'trend-hft', sharpe: 1.2, drawdown: '-22.1%', ic: 0.012, updated: 'Yesterday' },
  { name: 'Comm_Curve_Roll', research: 'Commodities', branch: 'term-structure', sharpe: 0.85, drawdown: '-6.7%', ic: 0.009, updated: 'Yesterday' },
];

export const activities = [
  { time: 'Just now', title: '创建 Alpha-V2 分支', detail: 'Global Equities / scaled-alpha-v4', tone: 'positive' },
  { time: '45m ago', title: 'Backtest_6552 失败', detail: '读取 prod_ticks_db 超时，pipeline 已停止', tone: 'negative' },
  { time: '2h ago', title: 'Agent 写入 decision note', detail: '建议围绕成交成本假设继续验证 IC 衰减', tone: 'info' },
  { time: '5h ago', title: '同步 Factor Library', detail: '从 core repo 拉取 12 个新因子', tone: 'neutral' },
  { time: 'Yesterday', title: '优化套件完成', detail: 'experiment-beta 完成 96 组参数遍历', tone: 'warning' },
];

export const researchRows = [
  { name: 'Alpha Factors Research', status: 'active', branches: 7, runs: 193, champion: 'Scaled_Alpha_v4', metric: 'Sharpe 1.85 / DD -4.1%', updated: '12m ago' },
  { name: 'Intraday Reversal CN', status: 'active', branches: 4, runs: 86, champion: 'FeeAware_v2', metric: 'IC 0.038 / Turnover 18%', updated: '1h ago' },
  { name: 'Rates Carry RV', status: 'review', branches: 5, runs: 62, champion: 'CTD_Basis_v3', metric: 'IR 1.32 / Hit 61%', updated: '4h ago' },
  { name: 'Options Vol Dispersion', status: 'paused', branches: 3, runs: 41, champion: 'USDisp_main', metric: 'Sharpe 1.45 / DD -18.4%', updated: '2d ago' },
];

export const lineageTree = {
  name: 'Baseline_v1',
  value: 'Raw Momentum',
  children: [
    {
      name: 'Neutralized_v2',
      value: 'Sector / Industry',
      children: [
        {
          name: 'Scaled_Alpha_v4',
          value: 'Champion · Sharpe 1.85',
        },
      ],
    },
    {
      name: 'Liq_Filtered_v2',
      value: 'Abandoned · Sharpe -0.12',
      children: [
        {
          name: 'Cost_Aware_v3',
          value: 'Review · Sharpe 1.21',
        },
      ],
    },
  ],
};

export const decisions = [
  { time: '2026-05-19 14:30', title: '手续费模型切到 5bps', detail: '更贴近当前机构执行能力，post-cost Sharpe 提升 0.15。' },
  { time: '2026-05-18 09:15', title: '加入行业与风格中性化', detail: '使用 USE4 风格暴露约束，隔离更纯的 momentum alpha。' },
  { time: '2026-05-16 16:45', title: '废弃 liquidity filter v2', detail: '过滤条件过强导致覆盖率下降，回退到 Top 3000 市值池。' },
  { time: '2026-05-12 10:00', title: '定义初始研究目标', detail: '构建 3-6 个月中期价量动量因子，优先验证稳定 regime。' },
];

export const branchRuns = [
  { id: '#42', date: 'Today 10:24', status: 'finished', ann: '14.2%', sharpe: 1.85, dd: '-6.4%', config: 'lookback: 40, neutralize: industry' },
  { id: '#41', date: 'Yesterday 16:15', status: 'finished', ann: '11.8%', sharpe: 1.52, dd: '-8.1%', config: 'lookback: 20, neutralize: sector' },
  { id: '#40', date: 'May 17 14:30', status: 'failed', ann: '--', sharpe: '--', dd: '--', config: 'cov matrix OOM' },
  { id: '#39', date: 'May 17 11:00', status: 'finished', ann: '10.5%', sharpe: 1.41, dd: '-8.5%', config: 'base implementation' },
  { id: '#38', date: 'May 16 18:22', status: 'finished', ann: '9.8%', sharpe: 1.22, dd: '-9.3%', config: 'fee_bps: 10' },
];

export const metrics = [
  { category: 'Return', name: 'Annual Return', value: '18.5%', benchmark: '11.2%', trend: 'up' },
  { category: 'Risk', name: 'Volatility', value: '8.4%', benchmark: '12.1%', trend: 'down' },
  { category: 'Risk', name: 'Max Drawdown', value: '-5.2%', benchmark: '-9.5%', trend: 'down' },
  { category: 'Factor', name: 'IC Mean', value: '0.045', benchmark: '0.026', trend: 'up' },
  { category: 'Execution', name: 'Slippage Est.', value: '5 bps', benchmark: '5 bps', trend: 'flat' },
];

export const artifacts = [
  { name: 'tearsheet.html', type: 'Report', size: '2.4 MB' },
  { name: 'factor_ic.parquet', type: 'Table', size: '18.7 MB' },
  { name: 'risk_exposure.png', type: 'Image', size: '740 KB' },
];

const heatmapYearSpecs = [
  { year: 2025, weeks: 24 },
  { year: 2026, weeks: 20 },
];

export const activityHeatmapColumns = heatmapYearSpecs.flatMap((spec, yearIndex) => {
  const yearColumns = Array.from({ length: spec.weeks }, (_, week) => ({
    id: `${spec.year}-${week}`,
    year: spec.year,
    week,
    isGap: false,
    days: Array.from({ length: 7 }, (_, day) => {
      const wave = (week * 5 + day * 7 + yearIndex * 3) % 17;
      const value = Math.min(4, Math.floor((wave + (week > spec.weeks * 0.55 ? 4 : 0)) / 4));
      return {
        id: `${spec.year}-${week}-${day}`,
        year: spec.year,
        week,
        day,
        value: day === 0 && week % 5 === 0 ? 0 : value,
      };
    }),
  }));

  if (yearIndex === heatmapYearSpecs.length - 1) {
    return yearColumns;
  }

  return [
    ...yearColumns,
    {
      id: `${spec.year}-gap`,
      year: spec.year,
      isGap: true,
      days: Array.from({ length: 7 }, (_, day) => ({
        id: `${spec.year}-gap-${day}`,
        day,
        value: 0,
        isGap: true,
      })),
    },
  ];
});

export const activityHeatmap = activityHeatmapColumns.flatMap((column) => column.days).filter((day) => !day.isGap);
