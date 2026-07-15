// A recipe field is never just a value: it is a value *or* a distribution the
// server samples from. This widget is that idea made clickable.
//
//   fijo     -> 14
//   rango    -> { range: [12, 28], step: null }
//   opciones -> { choice: ["left", "justify"], weights: null }
//   auto     -> null, or the literal "auto" for colors (auto-contrast)

export const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
};

export function detectMode(value, field) {
  if (value === null || value === undefined) return 'auto';
  if (field.autoLiteral && value === 'auto') return 'auto';
  if (typeof value === 'object' && !Array.isArray(value)) {
    if ('range' in value) return 'range';
    if ('choice' in value) return 'choice';
  }
  return 'fixed';
}

const isNum = (t) => t === 'int' || t === 'float';

function coerce(type, raw) {
  if (type === 'int') return raw === '' ? 0 : parseInt(raw, 10);
  if (type === 'float') return raw === '' ? 0 : parseFloat(raw);
  if (type === 'bool') return raw === true || raw === 'true';
  return raw;
}

const parseList = (text, type) =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s !== '')
    .map((s) => coerce(type, s));

/** Build the control for one field. Returns {node, read()}. */
export function paramField(field, value, onChange) {
  const modes = ['fixed'];
  if (field.dist !== false) {
    if (isNum(field.type)) modes.push('range');
    modes.push('choice');
  }
  if (field.nullable || field.autoLiteral) modes.push('auto');

  let mode = detectMode(value, field);
  if (!modes.includes(mode)) mode = 'fixed';

  const inputs = el('span', { class: 'inputs' });
  const select = el(
    'select',
    { onchange: () => { mode = select.value; draw(); onChange?.(); } },
    ...modes.map((m) =>
      el('option', { value: m, selected: m === mode }, MODE_LABEL[m])
    )
  );

  let read = () => null;

  function draw() {
    inputs.replaceChildren();
    if (mode === 'auto') {
      const why = field.autoLiteral ? 'contraste automático' : 'automático';
      inputs.append(el('span', { class: 'muted small' }, why));
      read = () => (field.autoLiteral ? 'auto' : null);
      return;
    }

    if (mode === 'fixed') {
      const input = makeInput(field, isPlain(value, field) ? value : field.fallback);
      inputs.append(input.node);
      read = () => input.read();
      return;
    }

    if (mode === 'range') {
      const cur = value && value.range ? value.range : [field.fallback, field.fallback];
      const lo = el('input', { type: 'number', step: 'any', value: cur[0] });
      const hi = el('input', { type: 'number', step: 'any', value: cur[1] });
      const step = el('input', {
        type: 'number', step: 'any', placeholder: 'paso',
        value: value?.step ?? (field.type === 'int' ? 1 : ''),
      });
      [lo, hi, step].forEach((i) => i.addEventListener('input', () => onChange?.()));
      inputs.append(lo, el('span', { class: 'muted' }, '–'), hi, step);
      read = () => ({
        range: [parseFloat(lo.value) || 0, parseFloat(hi.value) || 0],
        step: step.value === '' ? null : parseFloat(step.value),
      });
      return;
    }

    // choice
    const cur = value && value.choice ? value.choice : [];
    if (field.options) {
      const boxes = field.options.map((opt) => {
        const box = el('input', {
          type: 'checkbox',
          checked: cur.some((c) => String(c) === String(opt)),
          onchange: () => onChange?.(),
        });
        return { opt, box, node: el('label', { class: 'inline small' }, box, String(opt)) };
      });
      inputs.append(...boxes.map((b) => b.node));
      read = () => ({
        choice: boxes.filter((b) => b.box.checked).map((b) => coerce(field.type, b.opt)),
        weights: null,
      });
      return;
    }

    const list = el('input', {
      type: 'text',
      value: cur.join(', '),
      placeholder: 'separados por comas',
      oninput: () => onChange?.(),
    });
    const weights = el('input', {
      type: 'text',
      value: (value?.weights ?? []).join(', '),
      placeholder: 'pesos (opcional)',
      oninput: () => onChange?.(),
    });
    weights.style.maxWidth = '130px';
    inputs.append(list, weights);
    read = () => {
      const w = parseList(weights.value, 'float');
      return { choice: parseList(list.value, field.type), weights: w.length ? w : null };
    };
  }

  const isPlainVal = (v) => detectMode(v, field) === 'fixed';
  function isPlain(v, f) { return isPlainVal(v, f); }

  draw();

  const node = el('div', { class: 'field' },
    el('label', { title: field.help || '' }, field.label || field.key),
    select,
    inputs
  );

  return { node, read: () => read() };
}

const MODE_LABEL = { fixed: 'fijo', range: 'rango', choice: 'opciones', auto: 'auto' };

function makeInput(field, value) {
  const fire = (n) => n.addEventListener('input', () => field.onChange?.());

  if (field.type === 'bool' || field.options) {
    const opts = field.options ?? [true, false];
    const sel = el('select', {},
      ...opts.map((o) =>
        el('option', { value: String(o), selected: String(o) === String(value) }, String(o))
      )
    );
    return { node: sel, read: () => coerce(field.type, sel.value) };
  }

  if (field.type === 'color') {
    const hex = /^#[0-9a-f]{6}$/i.test(value ?? '') ? value : '#000000';
    const picker = el('input', { type: 'color', value: hex });
    const text = el('input', { type: 'text', value: value ?? '' });
    picker.addEventListener('input', () => { text.value = picker.value; });
    return { node: el('span', { class: 'inputs' }, picker, text), read: () => text.value };
  }

  if (isNum(field.type)) {
    const n = el('input', { type: 'number', step: field.type === 'int' ? '1' : 'any', value: value ?? 0 });
    fire(n);
    return { node: n, read: () => coerce(field.type, n.value) };
  }

  const t = el('input', { type: 'text', value: value ?? '' });
  fire(t);
  return { node: t, read: () => t.value };
}

/** A fixed-length tuple of numbers (placement.area). Never a distribution. */
export function tupleField(field, value, onChange) {
  const vals = value ?? field.fallback;
  const boxes = vals.map((v) =>
    el('input', { type: 'number', step: 'any', value: v, oninput: () => onChange?.() })
  );
  const node = el('div', { class: 'field' },
    el('label', { title: field.help || '' }, field.label || field.key),
    el('span', { class: 'muted small' }, 'x0 y0 x1 y1'),
    el('span', { class: 'inputs' }, ...boxes)
  );
  return { node, read: () => boxes.map((b) => parseFloat(b.value) || 0) };
}

/** A plain boolean with no distribution (placement.avoid_overlap). */
export function boolField(field, value, onChange) {
  const box = el('input', { type: 'checkbox', checked: !!value, onchange: () => onChange?.() });
  const node = el('div', { class: 'field' },
    el('label', {}, field.label || field.key),
    el('span', { class: 'muted small' }, ''),
    el('span', { class: 'inputs' }, box)
  );
  return { node, read: () => box.checked };
}
