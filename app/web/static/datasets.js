import { api } from './api.js';
import { el } from './params.js';
import { modalForm, newDatasetDialog } from './recipes.js';
import { confirmDialog, fmtBytes, fmtDate, toast } from './ui.js';

const PAGE = 24;

// ---------------------------------------------------------------- list

export async function datasetsView(root) {
  const datasets = await api.listDatasets();

  const rows = datasets.map((d) =>
    el('tr', {},
      el('td', {}, el('a', { class: 'link', href: `#/datasets/${d.id}` }, d.name)),
      el('td', {}, stateBadge(d.build)),
      el('td', { class: 'muted small' }, `${d.images_built} / ${d.count}`),
      el('td', { class: 'muted small' }, fmtBytes(d.bytes_on_disk)),
      el('td', { class: 'muted small' },
        d.recipe_id
          ? el('a', { class: 'link', href: `#/recipes/${d.recipe_id}` }, d.recipe_name ?? d.recipe_id)
          : el('span', {}, '—')),
      el('td', { class: 'muted small' }, fmtDate(d.created_at)),
      el('td', { class: 'actions' },
        el('button', { class: 'tiny', onclick: () => location.hash = `#/datasets/${d.id}` }, 'Abrir'),
        el('button', { class: 'tiny', onclick: () => removeDataset(d) }, 'Eliminar')
      )
    )
  );

  root.replaceChildren(
    el('div', { class: 'page-head' },
      el('h2', {}, 'Datasets'),
      el('button', { class: 'primary', onclick: () => newDatasetDialog() }, '+ Nuevo dataset')
    ),
    el('div', { class: 'panel' },
      datasets.length
        ? el('table', {},
            el('thead', {}, el('tr', {},
              el('th', {}, 'Nombre'), el('th', {}, 'Estado'), el('th', {}, 'Imágenes'),
              el('th', {}, 'En disco'), el('th', {}, 'Receta'), el('th', {}, 'Creado'), el('th', {})
            )),
            el('tbody', {}, ...rows)
          )
        : el('p', { class: 'muted' }, 'No hay datasets todavía.')
    )
  );
}

function stateBadge(build) {
  const label = { empty: 'sin renderizar', building: 'construyendo', ready: 'listo', error: 'error' };
  return el('span', { class: `badge ${build.state}` }, label[build.state] ?? build.state);
}

async function removeDataset(d) {
  if (!(await confirmDialog('Eliminar dataset', `¿Eliminar "${d.name}" por completo? Se borran las specs y las imágenes: esto no se puede deshacer.`))) return;
  try {
    await api.deleteDataset(d.id);
    toast('Dataset eliminado');
    datasetsView(document.getElementById('view'));
  } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------- detail

export async function datasetView(root, id) {
  let meta = await api.getDataset(id);
  let page = 0;
  let poll = null;

  const bar = el('i', { style: 'width:0%' });
  const progressWrap = el('div', { class: 'stack', hidden: true },
    el('div', { class: 'progress' }, bar),
    el('div', { class: 'muted small' }, '')
  );
  const gallery = el('div', { class: 'gallery' });
  const pager = el('div', { class: 'row end', style: 'margin-top:14px' });
  const head = el('div', { class: 'panel stack' });

  function renderHead() {
    const b = meta.build;
    head.replaceChildren(
      el('div', { class: 'row between wrap' },
        el('div', {},
          el('div', { class: 'row' }, el('h2', {}, meta.name), stateBadge(b)),
          el('div', { class: 'muted small' },
            `${meta.count} imágenes · semilla `,
            el('span', { class: 'mono' }, String(meta.seed)),
            meta.recipe_id ? ' · receta ' : '',
            meta.recipe_id
              ? el('a', { class: 'link', href: `#/recipes/${meta.recipe_id}` }, meta.recipe.name)
              : ''
          )
        ),
        el('div', { class: 'row wrap' },
          el('button', { onclick: rename }, 'Renombrar'),
          el('button', { class: 'primary', onclick: build, disabled: b.state === 'building' }, 'Construir PNGs'),
          el('a', { class: 'link', href: api.archiveUrl(id) },
            el('button', {}, 'Descargar ZIP')),
          el('button', { onclick: free }, 'Liberar imágenes'),
          el('button', { class: 'danger', onclick: destroy }, 'Eliminar')
        )
      ),
      b.state === 'error' ? el('div', { class: 'err small' }, b.error ?? '') : '',
      progressWrap
    );
  }

  function renderGallery() {
    const start = page * PAGE;
    const end = Math.min(meta.count, start + PAGE);
    gallery.replaceChildren(
      ...Array.from({ length: end - start }, (_, k) => {
        const i = start + k;
        return el('div', { class: 'thumb', onclick: () => itemDialog(id, i) },
          el('img', { src: api.imageUrl(id, i), loading: 'lazy', alt: `imagen ${i}` }),
          el('div', { class: 'cap' }, el('span', {}, `#${i}`))
        );
      })
    );
    const pages = Math.ceil(meta.count / PAGE);
    pager.replaceChildren(
      el('span', { class: 'muted small grow' },
        `${start + 1}–${end} de ${meta.count}`,
        meta.build.state === 'empty' ? ' · se renderizan al verlas' : ''
      ),
      el('button', { class: 'tiny', disabled: page === 0, onclick: () => { page--; renderGallery(); } }, '‹ Anterior'),
      el('span', { class: 'muted small' }, `${page + 1} / ${pages}`),
      el('button', { class: 'tiny', disabled: page >= pages - 1, onclick: () => { page++; renderGallery(); } }, 'Siguiente ›')
    );
  }

  async function build() {
    try {
      await api.buildDataset(id, { masks: true, labels: true });
      startPolling();
    } catch (e) { toast(e.message, true); }
  }

  function startPolling() {
    progressWrap.hidden = false;
    clearInterval(poll);
    poll = setInterval(async () => {
      let status;
      try { status = await api.buildStatus(id); } catch { return; }
      const pct = status.total ? Math.round((status.done / status.total) * 100) : 0;
      bar.style.width = `${pct}%`;
      progressWrap.lastChild.textContent = `${status.done} / ${status.total} (${pct}%)`;
      if (status.state === 'ready' || status.state === 'error') {
        clearInterval(poll);
        poll = null;
        meta = await api.getDataset(id);
        renderHead();
        renderGallery();
        toast(status.state === 'ready' ? 'Dataset construido' : `Error: ${status.error}`, status.state === 'error');
      }
    }, 800);
  }

  async function rename() {
    const name = prompt('Nuevo nombre:', meta.name);
    if (!name) return;
    try {
      meta = await api.renameDataset(id, name);
      renderHead();
      toast('Renombrado');
    } catch (e) { toast(e.message, true); }
  }

  async function free() {
    if (!(await confirmDialog(
      'Liberar imágenes',
      'Se borran los PNG, las máscaras y las etiquetas, pero se conservan las specs. Las imágenes se regeneran idénticas cuando vuelvas a pedirlas.'
    ))) return;
    try {
      const res = await api.freeArtifacts(id);
      meta = await api.getDataset(id);
      renderHead();
      renderGallery();
      toast(`Liberados ${fmtBytes(res.bytes_freed)}`);
    } catch (e) { toast(e.message, true); }
  }

  async function destroy() {
    if (!(await confirmDialog('Eliminar dataset', `¿Eliminar "${meta.name}" por completo? Esto no se puede deshacer.`))) return;
    try {
      await api.deleteDataset(id);
      location.hash = '#/datasets';
    } catch (e) { toast(e.message, true); }
  }

  renderHead();
  renderGallery();
  if (meta.build.state === 'building') startPolling();

  root.replaceChildren(
    el('div', { class: 'page-head' }, el('a', { class: 'link', href: '#/datasets' }, '← Datasets')),
    head,
    el('div', { class: 'panel', style: 'margin-top:16px' }, gallery, pager)
  );
}

// ---------------------------------------------------------------- item

async function itemDialog(id, i) {
  const img = el('img', { src: api.imageUrl(id, i), style: 'width:100%;display:block;border-radius:6px;background:#fff' });
  const canvas = el('canvas', { style: 'position:absolute;inset:0;width:100%;height:100%' });
  const stage = el('div', { style: 'position:relative' }, img, canvas);
  const info = el('div', { class: 'muted small' }, 'Cargando…');

  const showBoxes = el('input', { type: 'checkbox', checked: true, onchange: draw });
  const showMask = el('input', {
    type: 'checkbox',
    onchange: () => {
      img.src = showMask.checked ? api.maskUrl(id, i) : api.imageUrl(id, i);
    },
  });

  let labels = null;

  function draw() {
    const ctx = canvas.getContext('2d');
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!showBoxes.checked || !labels) return;
    const k = img.clientWidth / labels.width;
    ctx.lineWidth = 1;
    for (const w of labels.words) quad(ctx, w.quad, k, '#2ecc71');
    for (const b of labels.blocks) quad(ctx, b.quad, k, '#e8615a');
  }

  const body = el('div', {},
    el('div', { class: 'row between', style: 'margin-bottom:10px' },
      el('div', { class: 'row' },
        el('label', { class: 'inline small muted' }, showBoxes, 'cajas'),
        el('label', { class: 'inline small muted' }, showMask, 'máscara')
      ),
      el('a', { class: 'link small', href: api.imageUrl(id, i), target: '_blank' }, 'abrir PNG')
    ),
    stage,
    el('div', { style: 'margin-top:10px' }, info)
  );

  // Labels come from the API, same as everything else the UI shows.
  api.itemLabels(id, i).then((l) => {
    labels = l;
    draw();
    info.innerHTML =
      `${l.width}×${l.height} · ${l.blocks.length} bloques · ${l.lines.length} líneas · ${l.words.length} palabras`
      + (l.has_overlap ? ' · <span style="color:var(--warn)">hay solape</span>' : '');
  }).catch((e) => { info.textContent = e.message; });

  img.addEventListener('load', draw);

  await modalForm(`Imagen #${i}`, body, 'Cerrar', { cancel: false, wide: true });
}

function quad(ctx, points, k, color) {
  ctx.strokeStyle = color;
  ctx.beginPath();
  points.forEach(([x, y], n) => (n ? ctx.lineTo(x * k, y * k) : ctx.moveTo(x * k, y * k)));
  ctx.closePath();
  ctx.stroke();
}
