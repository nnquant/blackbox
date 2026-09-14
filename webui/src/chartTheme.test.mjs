import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { parse, lift } from 'zrender/lib/tool/color.js';

test('theme colors remain valid when zrender computes hover emphasis', () => {
  const source = readFileSync(new URL('./App.jsx', import.meta.url), 'utf8');
  const helper = source.slice(source.indexOf('function tone(name)'), source.indexOf('\nconst navItems'));
  const css = readFileSync(new URL('./main.css', import.meta.url), 'utf8');
  const colors = [...css.matchAll(/--c-([\w]+):\s*(\d+\s+\d+\s+\d+)/g)];
  assert.ok(colors.length > 0);
  for (const [, name, value] of colors) {
    const tone = vm.runInNewContext(`${helper}; tone`, {
      document: { documentElement: {} },
      getComputedStyle: () => ({ getPropertyValue: () => value }),
    });
    assert.ok(parse(tone(name)), `${name}: normal color`);
    assert.ok(lift(tone(name), -0.1), `${name}: hover color`);
  }
});
