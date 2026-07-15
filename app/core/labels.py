from __future__ import annotations

import math
from typing import Any

from app.models.spec import (
    BlockLabel,
    Box,
    Labels,
    LineLabel,
    Quad,
    WordLabel,
)

# Rects come out of the DOM with transforms disabled, so they are the true
# layout boxes. Rotation is re-applied here, analytically, about each block's
# center -- which is exactly what `transform-origin: center` does in CSS.


def _rotate(px: float, py: float, cx: float, cy: float, rad: float) -> tuple[float, float]:
    dx, dy = px - cx, py - cy
    cos, sin = math.cos(rad), math.sin(rad)
    return cx + dx * cos - dy * sin, cy + dx * sin + dy * cos


def quad_of(box: Box, center: tuple[float, float], angle: float) -> Quad:
    x, y, w, h = box
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if not angle:
        return [(round(cx, 2), round(cy, 2)) for cx, cy in corners]
    rad = math.radians(angle)
    return [
        tuple(round(v, 2) for v in _rotate(px, py, center[0], center[1], rad))
        for px, py in corners
    ]


def aabb_of(quad: Quad) -> Box:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, y0 = min(xs), min(ys)
    return (round(x0, 2), round(y0, 2), round(max(xs) - x0, 2), round(max(ys) - y0, 2))


def _group_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cluster word rects into lines by vertical position."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w["y"], w["x"]))
    lines: list[list[dict[str, Any]]] = [[ordered[0]]]
    for word in ordered[1:]:
        current = lines[-1]
        ref = current[0]
        # Same line when the vertical centers are within half a glyph height.
        if abs((word["y"] + word["h"] / 2) - (ref["y"] + ref["h"] / 2)) < ref["h"] * 0.5:
            current.append(word)
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w["x"])
    return lines


def _union(rects: list[dict[str, Any]]) -> Box:
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


def _boxes_overlap(a: Box, b: Box) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def build(image_id: str, width: int, height: int, dom: list[dict[str, Any]]) -> Labels:
    """Turn the raw DOM rects into hierarchical labels."""
    labels = Labels(image_id=image_id, width=width, height=height)

    for block in dom:
        angle = float(block.get("angle") or 0.0)
        ls = float(block.get("ls") or 0.0)
        bbox: Box = (block["x"], block["y"], block["w"], block["h"])
        center = (bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2)

        # CSS adds letter-spacing *after* the final glyph too, so a span's rect
        # runs one gap wider than the ink it contains.
        words = [
            {**w, "w": max(1.0, w["w"] - ls)}
            for w in block["words"]
            if w["w"] > 0 and w["h"] > 0
        ]

        block_quad = quad_of(bbox, center, angle)
        labels.blocks.append(
            BlockLabel(
                block_id=block["id"],
                kind=block["kind"],
                text=" ".join(w["text"] for w in words),
                angle=angle,
                box=aabb_of(block_quad),
                quad=block_quad,
            )
        )

        for li, line in enumerate(_group_lines(words)):
            line_box = _union(line)
            line_quad = quad_of(line_box, center, angle)
            labels.lines.append(
                LineLabel(
                    block_id=block["id"],
                    index=li,
                    text=" ".join(w["text"] for w in line),
                    box=aabb_of(line_quad),
                    quad=line_quad,
                )
            )
            for word in line:
                wbox: Box = (word["x"], word["y"], word["w"], word["h"])
                wquad = quad_of(wbox, center, angle)
                labels.words.append(
                    WordLabel(
                        block_id=block["id"],
                        line_index=li,
                        text=word["text"],
                        box=aabb_of(wquad),
                        quad=wquad,
                    )
                )

    boxes = [b.box for b in labels.blocks]
    labels.has_overlap = any(
        _boxes_overlap(boxes[i], boxes[j])
        for i in range(len(boxes))
        for j in range(i + 1, len(boxes))
    )
    return labels
