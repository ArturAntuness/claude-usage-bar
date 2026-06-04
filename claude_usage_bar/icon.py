from __future__ import annotations

import math

import cairo

COLORS = {
    "ok":   (0.30, 0.78, 0.31),   # verde
    "warn": (0.95, 0.61, 0.07),   # laranja
    "crit": (0.90, 0.22, 0.21),   # vermelho
    "idle": (0.55, 0.55, 0.55),   # cinza (carregando/erro)
}
SIZE = 22
RING = 4.0  # espessura do anel


def render_png(path: str, pct: float | None, state: str) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    ctx = cairo.Context(surface)
    cx = cy = SIZE / 2
    radius = SIZE / 2 - RING / 2 - 1

    ctx.set_line_width(RING)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(0.5, 0.5, 0.5, 0.30)
    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.stroke()

    if pct and pct > 0 and state != "idle":
        frac = max(0.0, min(1.0, pct / 100.0))
        r, g, b = COLORS.get(state, COLORS["ok"])
        ctx.set_source_rgb(r, g, b)
        start = -math.pi / 2
        end = start + 2 * math.pi * frac
        ctx.arc(cx, cy, radius, start, end)
        ctx.stroke()

    surface.write_to_png(path)
