# CLAUDE.md — cómo se trabaja en este repo

El **qué** está en [README.md](README.md) y el formato de salida en
[docs/SAMPLE_FORMAT.md](docs/SAMPLE_FORMAT.md). Aquí solo van las reglas de trabajo.

## ⚠ Este repo es una pieza de un sistema de seis, y el CENTRAL es otro

Lo que **no es de ningún repo en concreto** —los reportes de todos los estudios, qué está
decidido y qué sigue abierto, y qué pieza hace qué— vive en
[`estudios-redes-neuronales`](https://github.com/stalinbeltran/estudios-redes-neuronales).
Se enlaza, no se copia.

| Si quieres saber… | Mira en |
|---|---|
| **qué está fijado hoy** y qué sigue abierto | [`ESTADO.md`](https://github.com/stalinbeltran/estudios-redes-neuronales/blob/main/ESTADO.md) |
| **qué se corrió, cuándo y qué costó** | [`reportes/README.md`](https://github.com/stalinbeltran/estudios-redes-neuronales/blob/main/reportes/README.md) |
| **qué repo hace qué** | su [`README.md`](https://github.com/stalinbeltran/estudios-redes-neuronales/blob/main/README.md) |

⚠ **Y si algo que se hace aquí termina en un estudio o una medición, su reporte va allí**, no
aquí — sea cual sea el repo desde el que se lanzó. Un reporte guardado en el repo que lo dispara
es invisible para quien clona otro.

## Entrega: cada cambio pedido acaba en un commit y en `main`

**Cada cosa que el usuario pida, una vez terminada y probada, se cierra con su propio
commit descriptivo y se empuja a `main`.** No se acumulan cambios para un commit grande
al final.

```bash
git add -A && git commit -m "..." && git push origin main
```

⚠ **Esto INVIERTE la instrucción anterior de este fichero, que mandaba a `dev`.** La regla
vigente es de **2026-08-26, por decisión del usuario**, y estaba escrita en el repo hermano
—[`foveal-vision/CLAUDE.md`](https://github.com/stalinbeltran/foveal-vision/blob/main/CLAUDE.md),
que incluso decía *«misma regla en el proyecto hermano `image-text-sample-generator`»*— pero
**aquí no se actualizó hasta el 2026-09-01**. O sea que durante cinco semanas los dos repos
del mismo sistema se contradecían por escrito.

**El porqué**: los servidores son efímeros y se rehacen sin aviso. **Un clon limpio saca
`main`**, así que un commit parado en `dev` es invisible para la máquina siguiente.

⚠ **Y este repo es el que lo pagó.** Medido el 2026-08-14: el procedimiento para reconstruir
el dato del benchmark **sí estaba commiteado y empujado —pero a `dev` de aquí, sin fusionar a
`main`—**; en el server nuevo no había ni rastro, se dio por imposible lo que sí estaba
escrito, y se gastó una corrida de benchmark sobre la fuente equivocada.

⚠ **`origin/dev` sigue existiendo y quedó al día el 2026-09-01. Es historia: no se le empuja
más**, y no hay merge que esperar.

### La única excepción: varias sesiones a la vez en el mismo server

Cuando hay **trabajos paralelos** —otras sesiones de Claude, con sus propias conversaciones,
en **workspaces separados** del mismo dev— ésas **no escriben en `main`**: cada workspace usa
su rama para que dos líneas de trabajo no se pisen. El mecanismo y sus reglas están en
[`telegram-coordinator/CLAUDE.md` § «Varias sesiones a la vez»](https://github.com/stalinbeltran/telegram-coordinator/blob/main/CLAUDE.md).

⚠ Si **no** estás en un workspace (`~/ws/<algo>`), no es tu caso: vas a `main`.

## Estos servidores son efímeros: lo que no está empujado, no existe

La máquina de trabajo se rehace sin aviso y de ella solo sobrevive lo que está en el
remoto. Por eso el push de arriba no es una formalidad ni algo para «cuando quede
bonito»: **todo cambio y toda documentación se empuja en cuanto queda terminado**.

Y el merge a `main` pendiente es **deuda visible**, no un detalle: un clon limpio saca
`main`, así que lo que se quedó en `dev` no existe para la máquina siguiente. Medido el
2026-08-14: el droplet apareció recién restaurado, y la receta `dirty`, los specs
congelados de `dirty-1000` y `scripts/setup-linux.sh` estaban commiteados y empujados
—pero solo a `dev`—, así que el proyecto hermano no encontró forma de reconstruir el
dato del benchmark, lo dio por imposible y midió sobre la fuente equivocada. Estaba
todo escrito; simplemente no estaba donde se clona.

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
