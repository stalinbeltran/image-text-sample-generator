import { el } from './params.js';

export function toast(message, bad = false) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.classList.toggle('bad', bad);
  node.hidden = false;
  clearTimeout(node._t);
  node._t = setTimeout(() => { node.hidden = true; }, bad ? 5000 : 2500);
}

export function confirmDialog(title, body) {
  return new Promise((resolve) => {
    const frag = document.getElementById('tpl-confirm').content.cloneNode(true);
    const back = frag.querySelector('.modal-backdrop');
    frag.querySelector('.c-title').textContent = title;
    frag.querySelector('.c-body').textContent = body;
    const close = (v) => { back.remove(); resolve(v); };
    frag.querySelector('.c-cancel').addEventListener('click', () => close(false));
    frag.querySelector('.c-ok').addEventListener('click', () => close(true));
    back.addEventListener('click', (e) => { if (e.target === back) close(false); });
    document.body.append(frag);
  });
}

export function fmtBytes(n) {
  if (!n) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export function spinner(text = 'Cargando…') {
  return el('div', { class: 'muted', style: 'padding:30px;text-align:center' }, text);
}
