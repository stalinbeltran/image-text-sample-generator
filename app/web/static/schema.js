// Which recipe fields the form exposes, and how each one behaves.
// The *values* still come from GET /recipes/defaults, so the server stays the
// single source of truth -- this only describes presentation.

export const CANVAS = [
  { key: 'width', type: 'int', label: 'ancho', fallback: 640 },
  { key: 'height', type: 'int', label: 'alto', fallback: 480 },
];

export const BACKGROUND = [
  {
    key: 'kind', type: 'text', label: 'tipo', fallback: 'solid',
    options: ['solid', 'gradient', 'noise', 'paper', 'lines', 'grid', 'dots', 'photo'],
    help: 'Elige "opciones" para mezclar varios tipos en un mismo dataset.',
  },
  { key: 'color', type: 'color', label: 'color', fallback: '#ffffff' },
  { key: 'color2', type: 'color', label: 'color 2', fallback: '#d8d8d8', help: 'Segundo color del degradado / textura.' },
  { key: 'angle', type: 'float', label: 'ángulo', fallback: 0 },
  { key: 'intensity', type: 'float', label: 'intensidad', fallback: 0.1, help: 'Fuerza del ruido o la textura.' },
  { key: 'scale', type: 'float', label: 'escala', fallback: 4, help: 'Separación de líneas / rejilla / puntos.' },
  { key: 'line_color', type: 'color', label: 'color línea', fallback: '#9fb6d1' },
  { key: 'photo_dir', type: 'text', label: 'carpeta fotos', fallback: '', nullable: true, dist: false, help: 'Subcarpeta de assets/backgrounds. Vacío = la raíz.' },
  { key: 'photo_file', type: 'text', label: 'foto fija', fallback: '', nullable: true, help: 'Fija una foto concreta en vez de elegirla al azar.' },
  { key: 'photo_brightness', type: 'float', label: 'brillo foto', fallback: 1 },
  { key: 'photo_blur', type: 'float', label: 'desenfoque foto', fallback: 0 },
  { key: 'overlay_color', type: 'color', label: 'velo color', fallback: '#ffffff' },
  { key: 'overlay_alpha', type: 'float', label: 'velo opacidad', fallback: 0, help: 'Subir el velo aclara la foto y hace el texto más legible.' },
];

export const CONTENT = [
  { key: 'source', type: 'text', label: 'origen', fallback: 'words', options: ['words', 'chars', 'fixed'] },
  { key: 'text', type: 'text', label: 'texto fijo', fallback: '', nullable: true, help: 'Sólo se usa con origen = fixed.' },
  { key: 'lang', type: 'text', label: 'idioma', fallback: 'mixed', options: ['es', 'en', 'mixed'] },
  { key: 'words', type: 'int', label: 'nº palabras', fallback: 30 },
  { key: 'chars', type: 'int', label: 'nº caracteres', fallback: 1 },
  { key: 'alphabet', type: 'text', label: 'alfabeto', fallback: 'ABC', dist: false },
  { key: 'uppercase', type: 'bool', label: 'mayúsculas', fallback: false },
];

export const TYPOGRAPHY = [
  { key: 'font_family', type: 'font', label: 'fuente', fallback: '', nullable: true, help: 'Auto = al azar del catálogo, pero consistente dentro del bloque.' },
  { key: 'font_size', type: 'float', label: 'tamaño', fallback: 16 },
  { key: 'font_weight', type: 'int', label: 'grosor', fallback: 400, options: [100, 200, 300, 400, 500, 600, 700, 800, 900] },
  { key: 'italic', type: 'bool', label: 'cursiva', fallback: false },
  { key: 'color', type: 'color', label: 'color', fallback: '#000000', autoLiteral: true, help: 'Auto = elige un color que supere el contraste mínimo contra el fondo.' },
  { key: 'min_contrast', type: 'float', label: 'contraste mín.', fallback: 3, help: 'Ratio WCAG. 4.5 es el umbral de legibilidad.' },
  { key: 'opacity', type: 'float', label: 'opacidad', fallback: 1 },
  { key: 'letter_spacing', type: 'float', label: 'espaciado letra', fallback: 0 },
  { key: 'word_spacing', type: 'float', label: 'espaciado palabra', fallback: 0 },
  { key: 'line_height', type: 'float', label: 'interlineado', fallback: 1.4 },
  { key: 'align', type: 'text', label: 'alineación', fallback: 'left', options: ['left', 'center', 'right', 'justify'] },
  { key: 'text_stroke', type: 'float', label: 'trazo', fallback: 0 },
  { key: 'stroke_color', type: 'color', label: 'color trazo', fallback: '#000000' },
  { key: 'shadow', type: 'bool', label: 'sombra', fallback: false },
  { key: 'blur', type: 'float', label: 'desenfoque', fallback: 0 },
];

export const PLACEMENT = [
  { key: 'area', type: 'tuple', label: 'área', fallback: [0, 0, 1, 1], help: 'Región donde puede caer el bloque, en fracciones del lienzo.' },
  { key: 'x', type: 'float', label: 'x fija', fallback: 0, nullable: true },
  { key: 'y', type: 'float', label: 'y fija', fallback: 0, nullable: true },
  { key: 'angle', type: 'float', label: 'rotación', fallback: 0 },
  { key: 'avoid_overlap', type: 'plainbool', label: 'evitar solapes', fallback: true },
  { key: 'margin', type: 'float', label: 'margen', fallback: 8 },
];

export const BLOCK_TOP = [
  { key: 'kind', type: 'text', label: 'tipo', fallback: 'paragraph', dist: false, options: ['paragraph', 'word', 'letter', 'spaced'] },
  { key: 'count', type: 'int', label: 'cantidad', fallback: 1, help: 'Cuántos bloques de este tipo. Puede ser un rango.' },
  { key: 'width', type: 'float', label: 'ancho', fallback: 300, nullable: true, help: 'Auto = se ajusta al contenido (palabras/letras).' },
  { key: 'height', type: 'float', label: 'alto', fallback: 100, nullable: true, help: 'Auto = crece con el texto. Un valor lo recorta.' },
];

export const POST = [
  { key: 'blur', type: 'float', label: 'desenfoque', fallback: 0 },
  { key: 'noise', type: 'float', label: 'ruido', fallback: 0, help: 'Sigma gaussiana sobre 0-255.' },
  { key: 'jpeg_quality', type: 'int', label: 'calidad JPEG', fallback: 80, nullable: true, help: 'Introduce artefactos de compresión.' },
  { key: 'grayscale', type: 'bool', label: 'escala de grises', fallback: false },
];

export const BLOCK_KIND_LABEL = {
  paragraph: 'Párrafo',
  word: 'Palabra suelta',
  letter: 'Letra suelta',
  spaced: 'Letras espaciadas',
};
