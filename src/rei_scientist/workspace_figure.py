"""Optional Matplotlib figure exporter for measured study results.

Independently authored; does not embed third-party figure-making helper assets.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .workspace_store import WorkspaceError, WorkspaceStore, residuals


def export_figure(db: str | Path, identifier: str, output_prefix: str | Path) -> tuple[Path, Path]:
    record = WorkspaceStore(db).get(identifier)
    study = record["study"]
    data = [row for row in residuals(study) if row["baseline"] is not None and row["candidate"] is not None]
    if not data:
        raise WorkspaceError("No paired measured values; no figure generated")
    prefix = Path(output_prefix).expanduser().resolve()
    png, svg = prefix.with_suffix(".png"), prefix.with_suffix(".svg")
    if png.exists() or svg.exists():
        raise FileExistsError("Figure export refuses to overwrite existing files")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install optional matplotlib figure dependency") from exc
    # Each variable has a separately scaled axis. Units must not be mixed.
    fig, axs = plt.subplots(len(data), 1, figsize=(8, max(2.7, 2.55 * len(data))), squeeze=False)
    for axis, row in zip(axs[:, 0], data):
        values = [row["baseline"], row["candidate"]]
        axis.bar([0, 1], values, color=["#0E3D8A", "#228B55"], width=.42)
        axis.set_xticks([0, 1], ["Baseline", "Candidate"])
        axis.set_ylabel(f"{row['variable']} [{row['unit']}]")
        axis.axhline(0, color="#5e6570", linewidth=.7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#d9e0e7", linewidth=.5, zorder=0)
        axis.set_axisbelow(True)
        axis.set_title(f"Residual = {row['residual']:.6g} {row['unit']} · {row['verification']}", loc="left", fontsize=10)
    fig.suptitle(f"{study['title']} / r{record['revision']}", fontsize=12, fontweight="bold")
    fig.text(.01, .008, "Recorded observations only. NOT VERIFIED until independent evidence review.",
             fontsize=8, color="#596779")
    fig.tight_layout(rect=[0, .03, 1, .96])
    try:
        fig.savefig(png, dpi=300, bbox_inches="tight", metadata={"Title": study["title"], "Software": "REI Scientist"})
        fig.savefig(svg, bbox_inches="tight", metadata={"Title": study["title"], "Creator": "REI Scientist"})
    except BaseException:
        png.unlink(missing_ok=True)
        svg.unlink(missing_ok=True)
        raise
    finally:
        plt.close(fig)
    return png, svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export recorded results as PNG 300 DPI + vector SVG")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output prefix without extension")
    args = parser.parse_args(argv)
    try:
        png, svg = export_figure(args.db, args.id, args.out)
    except (WorkspaceError, FileNotFoundError, FileExistsError, OSError, RuntimeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"PNG: {png}\nSVG: {svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
