import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderMarkdown as md } from '../js/core/markdown.js';

test('headings map to h2-h5 so the page keeps a single h1', () => {
  assert.equal(md('# Title'), '<h2>Title</h2>');
  assert.equal(md('#### Deep'), '<h5>Deep</h5>');
});

test('inline formatting and code spans', () => {
  assert.equal(md('a **bold** and *em* and `x < y`'), '<p>a <strong>bold</strong> and <em>em</em> and <code>x &lt; y</code></p>');
  assert.equal(md('snake_case_name stays'), '<p>snake_case_name stays</p>');
  assert.equal(md('2 * 3 * 4'), '<p>2 * 3 * 4</p>');
});

test('fenced code is escaped and keeps its language', () => {
  const html = md('```python\nif a < b:\n    print("<hi>")\n```');
  assert.match(html, /<pre><code class="language-python">if a &lt; b:\n    print\(&quot;&lt;hi&gt;&quot;\)<\/code><\/pre>/);
});

test('unclosed fences do not swallow the renderer', () => {
  assert.match(md('```\ncode'), /<pre><code>code<\/code><\/pre>/);
});

test('lists nest by indentation and keep ordered/unordered kinds', () => {
  assert.equal(md('- a\n  - b\n- c'), '<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>');
  assert.equal(md('1. one\n2. two'), '<ol><li>one</li><li>two</li></ol>');
});

test('tables render with a header row', () => {
  const html = md('| A | B |\n|---|---|\n| 1 | **2** |');
  assert.match(html, /<th>A<\/th><th>B<\/th>/);
  assert.match(html, /<td>1<\/td><td><strong>2<\/strong><\/td>/);
});

test('blockquotes, rules and paragraph breaks', () => {
  assert.equal(md('> note\n> more'), '<blockquote>note<br>more</blockquote>');
  assert.equal(md('---'), '<hr>');
  assert.equal(md('line one\nline two\n\nnext'), '<p>line one<br>line two</p>\n<p>next</p>');
});

test('raw HTML is shown as text, never executed', () => {
  assert.equal(md('<script>alert(1)</script>'), '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
  assert.doesNotMatch(md('**<img src=x onerror=alert(1)>**'), /<img/);
  assert.doesNotMatch(md('```\n</code></pre><script>x()</script>\n```'), /<script>/);
});

test('only http(s) links become anchors, and attributes cannot be broken out of', () => {
  assert.match(md('[docs](https://example.com/a?b=1&c=2)'), /<a href="https:\/\/example.com\/a\?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">docs<\/a>/);
  assert.doesNotMatch(md('[x](javascript:alert(1))'), /<a /);
  assert.doesNotMatch(md('[x](data:text/html;base64,AAAA)'), /<a /);
  assert.doesNotMatch(md('![i](https://e.com/x.png" onerror="alert(1))'), /<img|onerror="/);
  assert.doesNotMatch(md('[x](https://e.com/" onmouseover="alert(1))'), /onmouseover="/);
});

test('empty and non-string input is safe', () => {
  assert.equal(md(''), '');
  assert.equal(md(null), '');
});
