# Embedded fonts

These `.ttf` files are **committed on purpose**, and that is a reproducibility
decision rather than a convenience one.

With this directory empty the renderer falls back to system families, and a
system family is a promise the machine may not keep: ask a Linux box for Arial
and fontconfig hands back Liberation Sans without a word, so the spec records a
font that never touched the canvas and the same spec yields different pixels on
a different machine. Fonts in here are embedded into the page as `@font-face`
data URIs, so the render depends on the file — not on what happens to be
installed.

| File | Family the app derives | Licence |
|---|---|---|
| `LiberationSans.ttf` | `LiberationSans` | SIL Open Font License 1.1 |
| `LiberationSerif.ttf` | `LiberationSerif` | SIL Open Font License 1.1 |
| `LiberationMono.ttf` | `LiberationMono` | SIL Open Font License 1.1 |
| `DejaVuSans.ttf` | `DejaVuSans` | Bitstream Vera Fonts License |
| `DejaVuSerif.ttf` | `DejaVuSerif` | Bitstream Vera Fonts License |

Both licences permit redistribution, which is what makes committing them legal
as well as useful. Copies came from Debian's `fonts-liberation2` and
`fonts-dejavu-core`; the Liberation faces are metrically compatible with Arial,
Times New Roman and Courier New, so recipes written against those metrics keep
their line breaks.

The family name is derived from the filename, cut at the first `-` or `_`
(`app/core/fonts.py`). That is why these are named `LiberationSans.ttf` and not
`LiberationSans-Regular.ttf` — the latter would work, but the family would read
`LiberationSans` anyway and the file name would imply a weight the registry does
not model.

**Only regular weights are embedded.** `face_css` emits one `@font-face` per
file with no `font-weight` descriptor, so shipping `-Bold` alongside `-Regular`
would register two faces under the same family and the last one would win for
every weight. Bold in a recipe is therefore synthesised by Chromium, which is
deterministic for a given Chromium build — the same caveat that already applies
to every glyph it rasterises.
