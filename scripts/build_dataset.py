#!/usr/bin/env python3
"""Materializa un dataset ya congelado, sin levantar el servidor ni la UI.

Por que existe
--------------
La promesa del proyecto es que los specs SON el dataset y los PNG son un cache
(README, "the storage promise"): `data/datasets/<id>/specs.jsonl` esta en git y
los pixeles no. Reconstruirlos, sin embargo, solo se podia por HTTP: arrancar
`app.serve`, POST /datasets/<id>/build, y ponerse a sondear /build hasta que
termine. Eso vale desde la UI y no vale desde un droplet recien hecho, que es
donde de verdad hace falta -- y ahi la reconstruccion se ha dado por imposible
mas de una vez, con el resultado de medir un benchmark sobre otra fuente.

Esto es el mismo trabajo (`_run_build` de app/api/routes.py) sin el servidor:
un comando que se puede correr por SSH, en cron o desde un script.

    .venv/bin/python scripts/build_dataset.py dirty-1000-699b2e01
    .venv/bin/python scripts/build_dataset.py dirty-1000-699b2e01 --end 4

Lo reproducible es el spec, no este comando: los specs ya estaban resueltos y
congelados en JSONL, asi que dos maquinas que corran esto obtienen los mismos
pixeles (con la salvedad de siempre: la rasterizacion de Chromium entre SO; los
labels salen del layout y esos si son exactos siempre).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import storage
from app.core.renderer import Renderer


async def build(
    dataset_id: str,
    start: int,
    end: int | None,
    *,
    masks: bool,
    mask_threshold: int,
    overwrite: bool,
) -> int:
    meta = storage.load_meta(dataset_id)
    fin = meta.count if end is None else min(end, meta.count)
    ini = max(0, start)

    pendientes = [
        i
        for i in range(ini, fin)
        if overwrite or not storage.image_path(dataset_id, i).is_file()
    ]
    ya = (fin - ini) - len(pendientes)
    print(f"dataset {dataset_id}: {meta.name}, seed {meta.seed}, {meta.count} specs")
    print(f"  rango [{ini}, {fin}) -- {len(pendientes)} por renderizar, {ya} ya en disco")
    if not pendientes:
        # Aun asi se reescribe el indice: puede faltar aunque los PNG esten.
        idx = storage.write_index(dataset_id)
        print(f"  nada que hacer. Indice reescrito: {idx}")
        return 0

    renderer = Renderer()
    await renderer.start()
    hechos = 0
    t0 = time.monotonic()
    fallos: list[tuple[int, str]] = []

    async def uno(index: int) -> None:
        nonlocal hechos
        try:
            spec = storage.read_spec(dataset_id, index)
            res = await renderer.render(spec, want_mask=masks, mask_threshold=mask_threshold)
            storage.write_item(
                dataset_id, index, res.image, res.mask, res.labels, overwrite=overwrite
            )
        except Exception as exc:  # noqa: BLE001 -- un spec malo no tumba la corrida
            fallos.append((index, f"{type(exc).__name__}: {exc}"))
        finally:
            hechos += 1
            if hechos % 25 == 0 or hechos == len(pendientes):
                transcurrido = time.monotonic() - t0
                ritmo = hechos / transcurrido if transcurrido else 0
                queda = (len(pendientes) - hechos) / ritmo if ritmo else 0
                print(
                    f"  {hechos}/{len(pendientes)}  ({ritmo:.1f} img/s, "
                    f"quedan ~{queda / 60:.1f} min)",
                    flush=True,
                )

    try:
        # El Renderer ya trae su propio semaforo (ITF_RENDER_CONCURRENCY), asi
        # que no hace falta trocear aqui: lanzarlas todas solo crea corrutinas
        # esperando turno, que es barato.
        await asyncio.gather(*(uno(i) for i in pendientes))
    finally:
        await renderer.stop()

    idx = storage.write_index(dataset_id)
    total = time.monotonic() - t0
    print(f"\n{hechos - len(fallos)}/{len(pendientes)} renderizadas en {total / 60:.1f} min")
    print(f"indice: {idx}")
    if fallos:
        print(f"\n{len(fallos)} fallaron:", file=sys.stderr)
        for index, msg in fallos[:10]:
            print(f"  [{index}] {msg}", file=sys.stderr)
        if len(fallos) > 10:
            print(f"  ... y {len(fallos) - 10} mas", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Renderiza los PNG/masks/labels de un dataset congelado, sin servidor"
    )
    ap.add_argument("dataset_id", help="id del dataset (el directorio de data/datasets/)")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None, help="exclusivo; por defecto, todos")
    ap.add_argument("--no-masks", action="store_true", help="no generar masks/")
    ap.add_argument("--mask-threshold", type=int, default=128)
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="rehacer los que ya estan en disco (por defecto se saltan)",
    )
    ap.add_argument("--list", action="store_true", help="lista los datasets y sale")
    args = ap.parse_args()

    if args.list:
        for meta in storage.list_all():
            print(f"{meta.id:<28} {meta.name:<20} seed={meta.seed} n={meta.count}")
        return 0

    try:
        storage.load_meta(args.dataset_id)
    except FileNotFoundError:
        disponibles = ", ".join(m.id for m in storage.list_all()) or "(ninguno)"
        print(
            f"ERROR: no existe el dataset '{args.dataset_id}'.\n"
            f"  En data/datasets/ hay: {disponibles}",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(
        build(
            args.dataset_id,
            args.start,
            args.end,
            masks=not args.no_masks,
            mask_threshold=args.mask_threshold,
            overwrite=args.overwrite,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
