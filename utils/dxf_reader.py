from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import ezdxf
import pandas as pd
from ezdxf import recover
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.bbox import extents
from matplotlib import pyplot as plt

SpaceType = Literal["model", "layout"]
BackgroundType = Literal["white", "dark"]


def load_dxf_from_bytes(data: bytes | str):
    """Load a DXF document from uploaded bytes with robust file-based fallback.

    `ezdxf.read()` can fail depending on stream type/encoding; persisting the payload
    to a temporary `.dxf` file and using `ezdxf.readfile()` is more robust.
    """
    if isinstance(data, str):
        payload = data.encode("utf-8", errors="ignore")
    else:
        payload = data

    with NamedTemporaryFile(delete=False, suffix=".dxf") as temp:
        temp.write(payload)
        temp_path = Path(temp.name)

    try:
        try:
            return ezdxf.readfile(temp_path)
        except Exception:
            doc, _auditor = recover.readfile(temp_path)
            return doc
    finally:
        temp_path.unlink(missing_ok=True)


def list_layouts(doc) -> list[str]:
    """Return available paper-space layouts (excluding modelspace)."""
    names: list[str] = []
    for layout in doc.layouts:
        if layout.name.lower() != "model":
            names.append(layout.name)
    return names


def _get_space(doc, space: SpaceType, layout_name: str | None = None):
    if space == "model":
        return doc.modelspace()
    if not layout_name:
        raise ValueError("layout_name es obligatorio cuando space='layout'.")
    return doc.layouts.get(layout_name)


def count_polylines_by_layer(doc, space: SpaceType = "model", layout_name: str | None = None) -> pd.DataFrame:
    """Count LWPOLYLINE and POLYLINE entities grouped by layer."""
    target_space = _get_space(doc, space=space, layout_name=layout_name)
    entities = target_space.query("LWPOLYLINE POLYLINE")

    counts: Counter[str] = Counter()
    for entity in entities:
        layer = getattr(entity.dxf, "layer", "0") or "0"
        counts[layer] += 1

    rows = [{"Layer": layer, "Polylines": qty} for layer, qty in counts.items()]
    df = pd.DataFrame(rows, columns=["Layer", "Polylines"])
    if not df.empty:
        df = df.sort_values("Polylines", ascending=False, kind="stable").reset_index(drop=True)
    return df


def render_preview_png(
    doc,
    space: SpaceType,
    layout_name: str | None,
    visible_layers: set[str] | None,
    bg: BackgroundType = "white",
) -> bytes:
    """Render DXF preview to PNG bytes using matplotlib backend."""
    target_space = _get_space(doc, space=space, layout_name=layout_name)

    all_entities = list(target_space)
    if visible_layers is None:
        draw_entities = all_entities
    else:
        draw_entities = [
            entity for entity in all_entities if (getattr(entity.dxf, "layer", "0") or "0") in visible_layers
        ]

    fig, ax = plt.subplots(figsize=(12, 8), dpi=180)

    if bg == "dark":
        bg_color = "#111111"
        fg_color = "#f5f5f5"
    else:
        bg_color = "white"
        fg_color = "black"

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.tick_params(colors=fg_color)

    context = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    frontend = Frontend(context, backend)

    if draw_entities:
        frontend.draw_entities(draw_entities, finalize=True)

    try:
        bbox = extents(draw_entities)
    except Exception:
        bbox = None

    if bbox and bbox.has_data:
        margin = max((bbox.size.x + bbox.size.y) * 0.01, 1.0)
        ax.set_xlim(bbox.extmin.x - margin, bbox.extmax.x + margin)
        ax.set_ylim(bbox.extmin.y - margin, bbox.extmax.y + margin)
    else:
        ax.autoscale(enable=True, axis="both", tight=True)

    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    plt.tight_layout(pad=0.15)

    output = BytesIO()
    fig.savefig(output, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    output.seek(0)
    return output.getvalue()
