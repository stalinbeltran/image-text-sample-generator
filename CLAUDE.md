# CLAUDE.md — cómo se trabaja en este repo

El **qué** está en [README.md](README.md) y el formato de salida en
[docs/SAMPLE_FORMAT.md](docs/SAMPLE_FORMAT.md). Aquí solo van las reglas de trabajo.

## Entrega: cada cambio pedido acaba en un commit y en `dev`

**Cada cosa que el usuario pida, una vez terminada y probada, se cierra con su propio
commit descriptivo y se empuja a la rama de desarrollo `dev`.** No se acumulan cambios
para un commit grande al final, y no se trabaja sobre `main`.

```bash
git checkout dev            # o: git checkout -b dev  la primera vez
# ... el cambio, y sus pruebas ...
git add -A && git commit -m "..."
git push -u origin dev
```

`main` se queda como está: a `main` se llega por merge cuando el usuario lo decida,
nunca por un push directo de un cambio recién hecho. Si un encargo se compone de varias
piezas, cada pieza terminada es un commit; el push puede ser uno al final del encargo.

## Antes de decir que algo funciona

- `.venv/bin/python -m pytest -q` desde la raíz (en Windows, `.venv\Scripts\python`).
- **Un comando documentado se ejecuta antes de presentarlo como verificado.** Si el
  README dice que algo se arranca así, se arranca así y se mira la salida.
- Para depurar un render sin levantar nada:
  `.venv/bin/python scripts/demo.py examples/<receta>.json --n 4 --out out/demo`.

## Qué se versiona y qué no

La promesa del proyecto es que **los specs son el dataset y los PNG son un caché**
(README, *the storage promise*). El `.gitignore` la aplica al pie de la letra:

- **Sí** van a git: `data/recipes/`, `data/datasets/*/dataset.json`,
  `data/datasets/*/specs.jsonl` y las fuentes de `assets/fonts/`.
- **No** van: `data/datasets/*/images|masks|labels`, `labels.jsonl`, `out/`, `.venv/`.

Un dataset se reconstruye desde sus specs, así que subir los píxeles sería subir un
caché. Si un cambio hace que un spec **deje de reproducir sus píxeles**, ese cambio está
roto aunque los tests pasen.

## Reproducibilidad: las fuentes se embeben, no se piden al sistema

Con `assets/fonts/` vacío el renderer cae a familias del sistema, y una familia del
sistema es una promesa que la máquina puede no cumplir: fontconfig sustituye Arial por
Liberation Sans **sin avisar**, así que el spec nombra una fuente que nunca tocó el
canvas. Las recetas que deban reproducirse en otra máquina **fijan `fonts`** a las
familias embebidas (ver [assets/fonts/README.md](assets/fonts/README.md)).

Lo que sigue sin garantía entre SO es la rasterización de Chromium; los **labels sí son
exactos siempre**, porque salen del layout y no de los píxeles.

## Idioma

El usuario se comunica en español; documentación y mensajes al usuario en español. El
código (identificadores, docstrings, comentarios) en inglés, como el que ya hay.
