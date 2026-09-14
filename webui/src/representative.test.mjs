import test from 'node:test';
import assert from 'node:assert/strict';
import { representativeRun } from './representative.js';
import { compareScope } from './comparisonScope.js';
const run=(id,score,extra={})=>({id,status:'completed',summary_json:{'strategy.summary':{sharpe:score}},updated_at:'2026-01-01',...extra});
test('manual > highest finite completed metric > latest, including zero',()=>{
  const rows=[run('zero',0),run('negative',-1),run('missing',null,{updated_at:'2026-02-01'}),run('running',99,{status:'running'})];
  assert.equal(representativeRun(rows).id,'zero');
  assert.equal(representativeRun(rows,undefined,'negative').id,'negative');
  assert.equal(representativeRun([rows[2],run('old',null)]).id,'missing');
  assert.equal(representativeRun([]),null);
});
test('comparison retains zero, false, null and distinguishes absent fields',()=>{
  const groups=compareScope([{config_json:{fee_bps:0,cost_enabled:false,start_date:null}},{config_json:{fee_bps:10,cost_enabled:true}}]);
  assert.equal(groups[1].status,'存在差异');
  assert.deepEqual(groups[1].rows.find(row=>row.key==='config.cost_enabled').values,['false','true']);
  assert.deepEqual(groups[0].rows[0].values,['null','未提供']);
  assert.equal(groups[2].status,'未提供 / 未校验');
});
