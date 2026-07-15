import { api } from './api.js';
import { boolField, el, paramField, tupleField } from './params.js';
import * as S from './schema.js';
import { confirmDialog, fmtDate, toast } from './ui.js';

let FONTS = [];

// ---------------------------------------------------------------- list

export async function recipesView(root) {
  const recipes = await api.listRecipes();

  const rows = recipes.map((r) =>
    el('tr', {},
      el('td', {}, el('a', { class: 'link', href: `#/recipes/${r.id}` }, r.name)),
      el('td', { class: 'muted small' }, `${r.recipe.blocks.length} bloque(s)`),
      el('td', { class: 'muted small' }, `${r.recipe.canvas.width ?? '?'} × ${r.recipe.canvas.height ?? '?'}`),
      el('td', { class: 'muted small' }, fmtDate(r.updated_at)),
      el('td', { class: 'actions' },
        el('button', { class: 'tiny primary', onclick: () => newDatasetDialog(r.id) }, 'Generar dataset'),
        el('button', { class: 'tiny', onclick: () => duplicate(r) }, 'Duplicar'),
        el('button', { class: 'tiny', onclick: () => remove(r) }, 'Eliminar'),
      )
    )
  );

  root.replaceChildren(
    el('div', { class: 'page-head' },
      el('h2', {}, 'Recetas'),
      el('button', { class: 'primary', onclick: createRecipe }, '+ Nueva receta')
    ),
    el('div', { class: 'panel' },
      recipes.length
        ? el('table', {},
            el('thead', {}, el('tr', {},
              el('th', {}, 'Nombre'), el('th', {}, 'Bloques'),
              el('th', {}, 'Lienzo'), el('th', {}, 'Modificada'), el('th', {})
            )),
            el('tbody', {}, ...rows)
          )
        : el('p', { class: 'muted' }, 'No hay recetas todavía.')
    )
  );
}

async function createRecipe() {
  const name = prompt('Nombre de la receta:', 'nueva receta');
  if (!name) return;
  try {
    const defaults = await api.recipeDefaults();
    const rec = await api.createRecipe(name, { ...defaults.recipe, name });
    location.hash = `#/recipes/${rec.id}`;
  } catch (e) { toast(e.message, true); }
}

async function duplicate(r) {
  try {
    await api.duplicateRecipe(r.id);
    toast('Receta duplicada');
    recipesView(document.getElementById('view'));
  } catch (e) { toast(e.message, true); }
}

async function remove(r) {
  if (!(await confirmDialog('Eliminar receta', `¿Eliminar "${r.name}"? Los datasets ya generados no se tocan: cada uno guarda su propia copia de la receta.`))) return;
  try {
    await api.deleteRecipe(r.id);
    toast('Receta eliminada');
    recipesView(document.getElementById('view'));
  } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------- editor

export async function recipeEditorView(root, id) {
  const [record, fonts] = await Promise.all([api.getRecipe(id), api.fonts()]);
  FONTS = fonts.map((f) => f.family).filter((v, i, a) => a.indexOf(v) === i);

  let recipe = structuredClone(record.recipe);
  let tab = 'form';
  let readers = [];

  const nameInput = el('input', { type: 'text', value: record.name, style: 'min-width:260px' });
  const formPane = el('div', {});
  const jsonPane = el('textarea', { class: 'mono', spellcheck: 'false', hidden: true });
  const errBox = el('div', { class: 'err small' });
  const preview = previewPanel(() => currentRecipe());

  // Pull the live values out of the form (or the JSON tab, whichever is open).
  function currentRecipe() {
    if (tab === 'json') {
      try {
        const parsed = JSON.parse(jsonPane.value);
        errBox.textContent = '';
        return parsed;
      } catch (e) {
        errBox.textContent = `JSON inválido: ${e.message}`;
        return null;
      }
    }
    const next = structuredClone(recipe);
    for (const r of readers) r.apply(next);
    return next;
  }

  function renderForm() {
    // Each widget knows how to write itself back into a recipe object, so
    // reading the form is just replaying them over a fresh clone.
    readers = [];
    const bind = (fields, container, getTarget) => {
      for (const f of fields) {
        const value = getTarget(recipe)[f.key];
        let widget;
        if (f.type === 'tuple') widget = tupleField(f, value, preview.invalidate);
        else if (f.type === 'plainbool') widget = boolField(f, value, preview.invalidate);
        else if (f.type === 'font') widget = paramField({ ...f, type: 'text', options: FONTS.length ? FONTS : undefined }, value, preview.invalidate);
        else widget = paramField(f, value, preview.invalidate);
        container.append(widget.node);
        readers.push({ apply: (next) => { getTarget(next)[f.key] = widget.read(); } });
      }
    };

    const canvasSet = el('fieldset', {}, el('legend', {}, 'Lienzo'));
    bind(S.CANVAS, canvasSet, (r) => r.canvas);

    const bgSet = el('fieldset', {}, el('legend', {}, 'Fondo'));
    bind(S.BACKGROUND, bgSet, (r) => r.background);

    const postSet = el('fieldset', {}, el('legend', {}, 'Post-proceso (degradación)'));
    bind(S.POST, postSet, (r) => r.post);

    const blocksWrap = el('div', {});
    recipe.blocks.forEach((block, i) => {
      const card = el('details', { class: 'block-card', open: i === 0 });
      const title = S.BLOCK_KIND_LABEL[block.kind] ?? block.kind;
      card.append(el('summary', {}, `Bloque ${i + 1} · ${title}`));

      const top = el('fieldset', {}, el('legend', {}, 'Bloque'));
      bind(S.BLOCK_TOP, top, (r) => r.blocks[i]);

      const content = el('fieldset', {}, el('legend', {}, 'Contenido'));
      bind(S.CONTENT, content, (r) => r.blocks[i].content);

      const typo = el('fieldset', {}, el('legend', {}, 'Tipografía'));
      bind(S.TYPOGRAPHY, typo, (r) => r.blocks[i].typography);

      const place = el('fieldset', {}, el('legend', {}, 'Colocación'));
      bind(S.PLACEMENT, place, (r) => r.blocks[i].placement);

      card.append(top, content, typo, place,
        el('div', { class: 'row end' },
          el('button', { class: 'tiny danger', onclick: () => removeBlock(i) }, 'Eliminar bloque')
        )
      );
      blocksWrap.append(card);
    });

    formPane.replaceChildren(
      canvasSet, bgSet,
      el('div', { class: 'row between', style: 'margin:16px 0 8px' },
        el('h3', { style: 'margin:0' }, 'Bloques de texto'),
        el('button', { class: 'tiny', onclick: addBlock }, '+ Añadir bloque')
      ),
      blocksWrap,
      postSet
    );
  }

  async function addBlock() {
    const defaults = await api.recipeDefaults();
    recipe = currentRecipe() ?? recipe;
    recipe.blocks.push(structuredClone(defaults.block));
    renderForm();
    preview.invalidate();
  }

  function removeBlock(i) {
    recipe = currentRecipe() ?? recipe;
    if (recipe.blocks.length === 1) { toast('Una receta necesita al menos un bloque', true); return; }
    recipe.blocks.splice(i, 1);
    renderForm();
    preview.invalidate();
  }

  function switchTab(next) {
    const live = currentRecipe();
    if (!live) { toast('Corrige el JSON antes de cambiar de pestaña', true); return; }
    recipe = live;
    tab = next;
    if (tab === 'json') jsonPane.value = JSON.stringify(recipe, null, 2);
    else renderForm();
    formPane.hidden = tab !== 'form';
    jsonPane.hidden = tab !== 'json';
    tabBtns.form.classList.toggle('active', tab === 'form');
    tabBtns.json.classList.toggle('active', tab === 'json');
  }

  async function save() {
    const live = currentRecipe();
    if (!live) { toast('JSON inválido', true); return; }
    try {
      const updated = await api.updateRecipe(id, { name: nameInput.value, recipe: live });
      recipe = structuredClone(updated.recipe);
      errBox.textContent = '';
      toast('Receta guardada');
    } catch (e) {
      errBox.textContent = e.message;
      toast('No se pudo guardar', true);
    }
  }

  const tabBtns = {
    form: el('button', { class: 'active', onclick: () => switchTab('form') }, 'Formulario'),
    json: el('button', { onclick: () => switchTab('json') }, 'JSON'),
  };

  renderForm();

  root.replaceChildren(
    el('div', { class: 'page-head' },
      el('div', { class: 'row' },
        el('a', { class: 'link', href: '#/recipes' }, '← Recetas'),
        nameInput
      ),
      el('div', { class: 'row' },
        el('button', { class: 'primary', onclick: save }, 'Guardar'),
        el('button', { onclick: () => newDatasetDialog(id) }, 'Generar dataset')
      )
    ),
    el('div', { class: 'editor' },
      el('div', { class: 'panel' },
        el('div', { class: 'tabs' }, tabBtns.form, tabBtns.json),
        errBox,
        formPane,
        jsonPane
      ),
      preview.node
    )
  );

  preview.invalidate();
}

// ---------------------------------------------------------------- preview

function previewPanel(getRecipe) {
  let seed = Math.floor(Math.random() * 1e9);
  let timer = null;
  let lastLabels = null;

  const img = el('img', { alt: 'vista previa' });
  const canvas = el('canvas');
  const stage = el('div', { class: 'stagearea' }, img, canvas);
  const status = el('div', { class: 'muted small' }, 'Renderizando…');
  const boxes = el('input', { type: 'checkbox', checked: true, onchange: () => drawBoxes() });

  function drawBoxes() {
    const ctx = canvas.getContext('2d');
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!boxes.checked || !lastLabels || !img.naturalWidth) return;

    const k = img.clientWidth / lastLabels.width;
    ctx.lineWidth = 1;
    for (const w of lastLabels.words) strokeQuad(ctx, w.quad, k, '#2ecc71');
    for (const b of lastLabels.blocks) strokeQuad(ctx, b.quad, k, '#e8615a');
  }

  async function refresh() {
    const recipe = getRecipe();
    if (!recipe) return;
    status.textContent = 'Renderizando…';
    try {
      const res = await api.render({ recipe, seed, mask: false });
      img.src = `data:image/png;base64,${res.image_png}`;
      lastLabels = res.labels;
      await img.decode().catch(() => {});
      drawBoxes();
      const n = res.labels.words.length;
      status.innerHTML = `semilla <span class="mono">${seed}</span> · ${res.labels.blocks.length} bloques · ${n} palabras`
        + (res.labels.has_overlap ? ' · <span style="color:var(--warn)">hay solape</span>' : '');
    } catch (e) {
      status.textContent = '';
      status.append(el('span', { class: 'err' }, e.message));
    }
  }

  // Debounced: every keystroke would otherwise fire a browser render.
  const invalidate = () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, 350);
  };

  window.addEventListener('resize', drawBoxes);

  const node = el('div', { class: 'panel preview' },
    el('div', { class: 'sticky' },
      el('div', { class: 'row between', style: 'margin-bottom:10px' },
        el('h3', { style: 'margin:0' }, 'Vista previa'),
        el('div', { class: 'row' },
          el('label', { class: 'inline small muted' }, boxes, 'cajas'),
          el('button', { class: 'tiny', onclick: () => { seed = Math.floor(Math.random() * 1e9); refresh(); } }, '⟳ Otra semilla')
        )
      ),
      stage,
      el('div', { style: 'margin-top:8px' }, status)
    )
  );

  return { node, invalidate, refresh };
}

function strokeQuad(ctx, quad, k, color) {
  ctx.strokeStyle = color;
  ctx.beginPath();
  quad.forEach(([x, y], i) => (i ? ctx.lineTo(x * k, y * k) : ctx.moveTo(x * k, y * k)));
  ctx.closePath();
  ctx.stroke();
}

// ---------------------------------------------------------------- generate

export async function newDatasetDialog(recipeId = null) {
  const recipes = await api.listRecipes();
  if (!recipes.length) { toast('Crea una receta primero', true); return; }

  const sel = el('select', {},
    ...recipes.map((r) => el('option', { value: r.id, selected: r.id === recipeId }, r.name))
  );
  const name = el('input', { type: 'text', placeholder: 'igual que la receta' });
  const count = el('input', { type: 'number', value: 20, min: 1, max: 200000 });
  const seed = el('input', { type: 'text', placeholder: 'aleatoria' });
  const buildNow = el('input', { type: 'checkbox', checked: true });

  const body = el('div', {},
    el('div', { class: 'field' }, el('label', {}, 'Receta'), sel),
    el('div', { class: 'field' }, el('label', {}, 'Nombre'), name),
    el('div', { class: 'field' }, el('label', {}, 'Nº de imágenes'), count),
    el('div', { class: 'field' }, el('label', {}, 'Semilla'), seed),
    el('div', { class: 'field' }, el('label', {}, 'Renderizar ya'),
      el('label', { class: 'inline small muted' }, buildNow, 'genera los PNG ahora (si no, se crean al verlos)')),
  );

  const ok = await modalForm('Generar dataset', body, 'Generar');
  if (!ok) return;

  try {
    const payload = {
      recipe_id: sel.value,
      count: parseInt(count.value, 10),
      name: name.value || null,
      seed: seed.value === '' ? null : parseInt(seed.value, 10),
    };
    const ds = await api.createDataset(payload);
    if (buildNow.checked) await api.buildDataset(ds.id, {});
    toast(`Dataset "${ds.name}" creado`);
    location.hash = `#/datasets/${ds.id}`;
  } catch (e) { toast(e.message, true); }
}

// A tiny promise-based modal; resolves true on confirm.
// `cancel: false` for read-only panels -- there is nothing there to cancel.
export function modalForm(title, bodyNode, okLabel = 'Aceptar', { cancel = true, wide = false } = {}) {
  return new Promise((resolve) => {
    const back = el('div', { class: 'modal-backdrop' });
    const close = (v) => { back.remove(); resolve(v); };
    back.append(el('div', { class: `modal${wide ? ' wide' : ''}` },
      el('h3', {}, title),
      bodyNode,
      el('div', { class: 'row end', style: 'margin-top:16px' },
        cancel ? el('button', { class: 'ghost', onclick: () => close(false) }, 'Cancelar') : null,
        el('button', { class: 'primary', onclick: () => close(true) }, okLabel)
      )
    ));
    back.addEventListener('click', (e) => { if (e.target === back) close(false); });
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(false); }
    });
    document.body.append(back);
  });
}
