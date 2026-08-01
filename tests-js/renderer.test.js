const path = require('path');
const { spawnSync } = require('child_process');
const test = require('node:test');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..');

test('vendored CSL assets render a real citation with citeproc-js', () => {
  const input = JSON.stringify([
    {
      id: 'work-1',
      type: 'book',
      title: 'A Test Title',
      author: [{ family: 'Doe', given: 'Jane' }],
      issued: { 'date-parts': [[2024]] },
    },
  ]);
  const result = spawnSync(
    process.execPath,
    [
      path.join(root, 'scripts', 'render-citations.js'),
      path.join(root, 'static', 'csl',
        'modern-humanities-research-association.csl'),
      path.join(root, 'static', 'csl', 'locales-en-GB.xml'),
    ],
    { cwd: root, encoding: 'utf8', input }
  );

  assert.equal(result.status, 0, result.stderr);
  const entries = JSON.parse(result.stdout);
  assert.equal(entries.length, 1);
  assert.match(entries[0], /Doe/);
  assert.match(entries[0], /A Test Title/);
});
