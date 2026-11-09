/**
 * A small Markdown renderer for notes. It supports headings, paragraphs, bold/italic, inline code, fenced code,
 * lists (nested), blockquotes, tables, rules and http(s) links, which covers what the study generator and
 * typical hand-written notes use.
 *
 * Safety model: all input is HTML-escaped first and markup is produced only by this file, so note text can never
 * inject elements or attributes. Links are limited to http(s). Images and raw HTML are shown as plain text.
 */
const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const escapeHtml = (text) => text.replace(/[&<>"']/g, (c) => ENTITIES[c]);

function inline(raw) {
  const codeSpans = [];
  let text = escapeHtml(raw).replace(/`([^`]+)`/g, (_, code) => {
    codeSpans.push(`<code>${code}</code>`);
    return `\u0000${codeSpans.length - 1}\u0000`;
  });
  text = text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<em>$2</em>')
    .replace(/(^|[^\w])_([^_\s][^_]*?)_(?!\w)/g, '$1<em>$2</em>');
  return text.replace(/\u0000(\d+)\u0000/g, (_, i) => codeSpans[Number(i)]);
}

const FENCE = /^```\s*([\w+#-]*)\s*$/;
const HEADING = /^(#{1,4})\s+(.+?)\s*#*\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

const splitRow = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
const startsBlock = (line, next) =>
  FENCE.test(line) || HEADING.test(line) || RULE.test(line) || LIST_ITEM.test(line) || /^\s*>/.test(line) || (line.includes('|') && next !== undefined && TABLE_DIVIDER.test(next));

function renderList(items) {
  // items: [{indent, ordered, text}] for one contiguous block; deeper indent opens a nested list.
  let html = '';
  const stack = [];
  const close = () => { const top = stack.pop(); html += `</li></${top.tag}>`; };
  for (const item of items) {
    const tag = item.ordered ? 'ol' : 'ul';
    while (stack.length && item.indent < stack[stack.length - 1].indent) close();
    const top = stack[stack.length - 1];
    if (!top || item.indent > top.indent) {
      html += `<${tag}><li>${inline(item.text)}`;
      stack.push({ indent: item.indent, tag });
    } else {
      html += `</li><li>${inline(item.text)}`;
    }
  }
  while (stack.length) close();
  return html;
}

export function renderMarkdown(source) {
  const lines = String(source ?? '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const fence = line.match(FENCE);
    if (fence) {
      const code = [];
      i++;
      while (i < lines.length && !FENCE.test(lines[i])) code.push(lines[i++]);
      i++; // closing fence (or end of input)
      out.push(`<pre><code${fence[1] ? ` class="language-${escapeHtml(fence[1])}"` : ''}>${escapeHtml(code.join('\n'))}</code></pre>`);
      continue;
    }
    const heading = line.match(HEADING);
    if (heading) { const level = heading[1].length + 1; out.push(`<h${level}>${inline(heading[2])}</h${level}>`); i++; continue; }
    if (RULE.test(line)) { out.push('<hr>'); i++; continue; }

    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ''));
      out.push(`<blockquote>${quote.map(inline).join('<br>')}</blockquote>`);
      continue;
    }
    if (line.includes('|') && TABLE_DIVIDER.test(lines[i + 1] ?? '')) {
      const head = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(splitRow(lines[i++]));
      out.push(`<div class="md-table"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    if (LIST_ITEM.test(line)) {
      const items = [];
      while (i < lines.length && LIST_ITEM.test(lines[i])) {
        const [, indent, marker, text] = lines[i].match(LIST_ITEM);
        items.push({ indent: indent.replace(/\t/g, '    ').length, ordered: /\d/.test(marker), text });
        i++;
      }
      out.push(renderList(items));
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !(paragraph.length && startsBlock(lines[i], lines[i + 1]))) paragraph.push(lines[i++].trim());
    out.push(`<p>${paragraph.map(inline).join('<br>')}</p>`);
  }
  return out.join('\n');
}
