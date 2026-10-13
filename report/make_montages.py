"""Compose the report's multi-panel figures.

The report has a 20-page budget, so related screenshots are combined into a
single labelled panel figure instead of one figure per screenshot.

    cd backend && .venv/Scripts/python ../report/make_montages.py

Outputs fig_ui_*.png and fig_analytics.png into report/assets/.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

CELL_W = 1240          # panel width in px (~3.1 in at 400 dpi once placed)
GAP = 26               # gap between panels
LABEL_BG = (255, 255, 255)


def _font(size: int = 34):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def panel(name: str, height: int, crop_top: int = 0, width: int = CELL_W) -> Image.Image:
    """Load a screenshot, crop its top region and scale it to the panel width."""
    img = Image.open(os.path.join(ASSETS, name)).convert("RGB")
    if crop_top:
        img = img.crop((0, crop_top, img.width, img.height))
    scale = width / img.width
    new_h = min(height, max(1, int(img.height * scale)))
    img = img.resize((width, new_h), Image.LANCZOS)
    if img.height < height:  # pad short panels so the grid stays aligned
        padded = Image.new("RGB", (width, height), (17, 22, 20))
        padded.paste(img, (0, 0))
        img = padded
    return img


def labelled(img: Image.Image, tag: str) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = _font(34)
    pad = 10
    box = draw.textbbox((0, 0), tag, font=font)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    draw.rectangle([8, 8, 8 + w, 8 + h], fill=LABEL_BG)
    draw.text((8 + pad, 8 + pad - box[1]), tag, fill=(20, 20, 20), font=font)
    return out


def grid(rows: list[list[tuple[str, Image.Image]]], out_name: str, bg=(255, 255, 255)):
    """Assemble labelled panels into a grid and save the composite."""
    row_imgs = []
    for row in rows:
        height = max(img.height for _, img in row)
        width = sum(img.width for _, img in row) + GAP * (len(row) - 1)
        strip = Image.new("RGB", (width, height), bg)
        x = 0
        for tag, img in row:
            strip.paste(labelled(img, tag), (x, 0))
            x += img.width + GAP
        row_imgs.append(strip)

    total_h = sum(s.height for s in row_imgs) + GAP * (len(row_imgs) - 1)
    total_w = max(s.width for s in row_imgs)
    canvas = Image.new("RGB", (total_w, total_h), bg)
    y = 0
    for strip in row_imgs:
        canvas.paste(strip, ((total_w - strip.width) // 2, y))
        y += strip.height + GAP
    path = os.path.join(ASSETS, out_name)
    canvas.save(path)
    print("wrote", out_name, canvas.size)


def build():
    # ---- dashboard + run configuration --------------------------------- #
    grid(
        [
            [
                ("(a) Dashboard", panel("shot_dashboard.png", 820)),
                ("(b) Run configuration", panel("shot_run_config.png", 820)),
            ],
            [
                ("(c) Dataset, engine and year window", panel("shot_status_grid.png", 520)),
                ("(d) Run history and live console", panel("shot_run_history.png", 520)),
            ],
        ],
        "fig_ui_dashboard.png",
    )

    # ---- results ------------------------------------------------------- #
    grid(
        [
            [
                ("(a) Results header and headline stats", panel("shot_results_overview.png", 640)),
                ("(b) Decade x cluster vibe-shift heatmap", panel("shot_vibe_heatmap.png", 640)),
            ],
            [
                ("(c) Cluster profiles and sizes", panel("shot_cluster_row.png", 430)),
                ("(d) PCA map and decade trends", panel("shot_projection_row.png", 430)),
            ],
        ],
        "fig_ui_results.png",
    )

    # ---- core BDA panels ------------------------------------------------ #
    grid(
        [
            [
                ("(a) MapReduce job inspector", panel("shot_bda_mapreduce.png", 840)),
                ("(b) MongoDB / NoSQL console", panel("shot_bda_mongodb.png", 840)),
            ],
            [
                ("(c) Statistics and visualisation", panel("shot_bda_eda.png", 620)),
                ("(d) Additional analyses", panel("shot_bda_advanced.png", 620)),
            ],
        ],
        "fig_ui_bda.png",
    )

    # ---- concepts + explorer -------------------------------------------- #
    grid(
        [
            [
                ("(a) Core concept catalogue with live evidence", panel("shot_concepts_core.png", 900)),
                ("(b) Track explorer with Bloom verdict", panel("shot_track_explorer.png", 900)),
            ]
        ],
        "fig_ui_explore.png",
    )

    # ---- statistics figures side by side -------------------------------- #
    grid(
        [
            [
                ("(a) Pearson correlation of the eight features", panel("fig_correlation.png", 1000, width=1150)),
                ("(b) Cluster sizes and decade composition", panel("fig_clusters.png", 1000, width=1250)),
            ]
        ],
        "fig_analytics.png",
    )


if __name__ == "__main__":
    build()
