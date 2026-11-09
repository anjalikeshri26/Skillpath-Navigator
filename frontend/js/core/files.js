/** Save text as a file in the browser. File names are sanitised so any note title is safe to use. */
export function safeFileName(title, extension = 'md') {
  const base = String(title || 'note').trim().replace(/[\\/:*?"<>|\u0000-\u001f]+/g, '-').replace(/\s+/g, ' ').replace(/^\.+/, '').slice(0, 80);
  return `${base || 'note'}.${extension}`;
}

export function downloadText(title, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
  const link = Object.assign(document.createElement('a'), { href: url, download: safeFileName(title) });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Ctrl+S / Cmd+S inside `root` runs `save` instead of the browser's save-page dialog. */
export function saveShortcut(root, save) {
  root.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      save();
    }
  });
}
