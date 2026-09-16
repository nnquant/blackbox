import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Vite replaces import.meta.env; exercise the actual request implementation in Node.
const source = (await readFile(new URL('../src/api.js', import.meta.url), 'utf8'))
  .replace("import { t } from './i18n';", 'const t = value => value;')
  .replaceAll('import.meta.env', '({})');
globalThis.window = { localStorage: { getItem: () => '' } };
const { apiGet } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('overlapping refreshes share one request, including a slow response', async () => {
  let calls = 0;
  let finish;
  globalThis.fetch = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  const first = apiGet('/slow-map');
  const second = apiGet('/slow-map');
  assert.equal(first, second);
  assert.equal(calls, 1);
  finish(new Response(JSON.stringify({ ok: true, data: { nodes: [1] } })));
  assert.deepEqual(await first, { nodes: [1] });
  assert.equal(await first, await second);
});

test('304 and identical payloads preserve the object used by the map', async () => {
  const url = '/stable-map';
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, data: { nodes: [2] } }), { headers: { ETag: '"version-1"' } });
  const first = await apiGet(url);
  globalThis.fetch = async (_, options) => {
    assert.equal(options.headers['If-None-Match'], '"version-1"');
    return new Response(null, { status: 304 });
  };
  assert.equal(await apiGet(url), first);
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, data: { nodes: [2] } }));
  assert.equal(await apiGet(url), first);
});

test('a failed request can retry without returning a rejected in-flight promise', async () => {
  globalThis.fetch = async () => { throw new Error('offline'); };
  await assert.rejects(apiGet('/retry'), /offline/);
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, data: { ready: true } }));
  assert.deepEqual(await apiGet('/retry'), { ready: true });
});
