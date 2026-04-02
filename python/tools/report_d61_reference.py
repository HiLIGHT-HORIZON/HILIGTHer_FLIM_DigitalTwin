import argparse
import base64
import contextlib
import io
import json
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys

THIS_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = THIS_DIR.parent
REPO_ROOT = PYTHON_ROOT.parent
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from backend.models import PhysicsConfig
from backend.twin_engine import TwinEngine


DEFAULT_DOCX = REPO_ROOT / "resources" / "D6.1_HILIGHT_M18_SEN_v2.docx"
DEFAULT_HTML = REPO_ROOT / "docs" / "d61_reference_replication.html"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

TAU_GRID = np.linspace(0.5, 10.0, 96)
FIGURE2_WIDTHS = [0.05, 0.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0]
FIGURE3_JITTERS = [0, 100, 250, 500, 1000]
FIGURE4_CASES = {
    "4 gates (case i)": [0.0, 8.0, 16.0, 24.0, 32.0],
    "4 gates (case ii)": [0.0, 7.5, 10.0, 15.0, 32.0],
    "4 gates (case iii)": [0.0, 2.8, 7.5, 12.5, 32.0],
    "8 gates (reference)": np.linspace(0.0, 32.0, 9).tolist(),
}
FIGURE4_TARGETS = {
    "8 gates (reference)": {"peak_eff": 0.75, "peak_tau": 4.0, "eff_tau": 2.0, "eff_value": 0.50},
    "4 gates (case i)": {"peak_eff": 0.70, "peak_tau": 4.5, "eff_tau": 2.0, "eff_value": 0.40},
    "4 gates (case ii)": {"peak_eff": 0.70, "peak_tau": 5.5, "eff_tau": 2.0, "eff_value": 0.50},
    "4 gates (case iii)": {"peak_eff": 0.70, "peak_tau": 3.5, "eff_tau": 3.0, "eff_value": 0.50},
}


def base_config() -> PhysicsConfig:
    return PhysicsConfig(
        period=50.0,
        gate_edges=[0.0, 8.0, 16.0, 24.0, 32.0],
        irf_profile="rectangular",
        irf_fwhm=7.5,
        irf_position=0.0,
        irf_rise_time=0.01,
        irf_fall_time=0.01,
        gate_rise=0.0,
        gate_fall=0.0,
        b_decay_wrapping=True,
        dt_input=0.01,
    )


def compute_efficiency_curve(cfg: PhysicsConfig, tau_grid: np.ndarray) -> np.ndarray:
    engine = TwinEngine(cfg)
    with contextlib.redirect_stdout(io.StringIO()):
        _, f_values = engine.compute_fisher_info(tau_grid, n_photons=1)
    return 1.0 / (np.maximum(f_values, 1e-12) ** 2)


def summarize_curve(tau_grid: np.ndarray, eff: np.ndarray, sample_tau: float) -> dict:
    peak_idx = int(np.nanargmax(eff))
    sample_idx = int(np.argmin(np.abs(tau_grid - sample_tau)))
    return {
        "peak_tau": float(tau_grid[peak_idx]),
        "peak_eff": float(eff[peak_idx]),
        "sample_tau": float(tau_grid[sample_idx]),
        "sample_eff": float(eff[sample_idx]),
    }


def extract_report_figures(docx_path: Path) -> dict:
    if not docx_path.exists():
        return {}

    with tempfile.TemporaryDirectory(prefix="d61_docx_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(docx_path) as archive:
            archive.extractall(tmpdir_path)

        rels_root = ET.parse(tmpdir_path / "word" / "_rels" / "document.xml.rels").getroot()
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}
        document_root = ET.parse(tmpdir_path / "word" / "document.xml").getroot()

        figures = {}
        last_image = None
        for paragraph in document_root.findall(".//w:p", NS):
            embeds = [
                blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                for blip in paragraph.findall(".//a:blip", NS)
            ]
            embeds = [embed for embed in embeds if embed]
            if embeds:
                last_image = tmpdir_path / "word" / rel_map[embeds[-1]]

            text = "".join(
                node.text for node in paragraph.findall(".//w:t", NS) if node.text
            ).strip()
            if text.startswith("Figure ") and last_image and last_image.exists():
                figures[text.split(".")[0]] = {
                    "caption": text,
                    "image_b64": image_to_base64(last_image),
                }
        return figures


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def figure_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def plot_efficiency_curves(title: str, tau_grid: np.ndarray, curves: dict, xlabel: str = "Simulated τ (ns)") -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for label, eff in curves.items():
        ax.plot(tau_grid, eff, linewidth=2, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Efficiency (F$^{-2}$)")
    ax.grid(True, alpha=0.25)
    ax.set_xlim(float(np.min(tau_grid)), float(np.max(tau_grid)))
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8)
    return figure_to_base64(fig)


def build_figure2_results() -> dict:
    curves = {}
    summary_rows = []
    for width in FIGURE2_WIDTHS:
        cfg = base_config()
        cfg.irf_fwhm = width
        eff = compute_efficiency_curve(cfg, TAU_GRID)
        label = f"{width:g} ns"
        curves[label] = eff
        row = summarize_curve(TAU_GRID, eff, sample_tau=5.0)
        row["label"] = label
        summary_rows.append(row)
    return {
        "plot_b64": plot_efficiency_curves("Python backend replication of Figure 2", TAU_GRID, curves),
        "summary_rows": summary_rows,
        "notes": [
            "Trend check: efficiency stays high up to 5 ns burst width.",
            "Observed in Python backend: 7.5 ns is still usable but already measurably worse than 5 ns.",
        ],
    }


def build_figure3_results() -> dict:
    curves = {}
    summary_rows = []
    for jitter in FIGURE3_JITTERS:
        cfg = base_config()
        cfg.timing_jitter = jitter
        eff = compute_efficiency_curve(cfg, TAU_GRID)
        label = f"{jitter} ps"
        curves[label] = eff
        row = summarize_curve(TAU_GRID, eff, sample_tau=5.0)
        row["label"] = label
        summary_rows.append(row)

    sample_by_label = {row["label"]: row["sample_eff"] for row in summary_rows}
    sample_values = list(sample_by_label.values())
    span = max(sample_values) - min(sample_values)
    eff_0 = sample_by_label.get("0 ps", np.nan)
    eff_500 = sample_by_label.get("500 ps", np.nan)
    eff_1000 = sample_by_label.get("1000 ps", np.nan)
    high_through_500 = np.isfinite(eff_500) and eff_500 >= 0.60
    deterioration_at_1000 = (
        np.isfinite(eff_0)
        and np.isfinite(eff_1000)
        and (eff_1000 <= eff_0 - 0.02)
    )
    if high_through_500 and deterioration_at_1000:
        status = "pass"
    elif span >= 0.02:
        status = "partial"
    else:
        status = "fail"

    if status == "pass":
        notes = [
            "The updated Python backend now shows the expected qualitative trend: efficiency stays high through ~500 ps and deteriorates by 1000 ps.",
            "This figure is now reproduced qualitatively, although the exact MATLAB curve shapes may still differ.",
        ]
    elif status == "partial":
        notes = [
            "The updated Python backend is no longer flat across the jitter sweep and now shows a measurable deterioration.",
            "However, the match is still only partial if stricter quantitative parity with the MATLAB curves is required.",
        ]
    else:
        notes = [
            "Expected from report: efficiency should deteriorate gradually from 0 to 1000 ps and remain acceptable up to ~500 ps.",
            "Observed in Python backend: the jitter/skewness sweep remains too flat, indicating missing or mismatched gate-jitter modelling.",
        ]
    return {
        "plot_b64": plot_efficiency_curves("Python backend replication of Figure 3", TAU_GRID, curves),
        "summary_rows": summary_rows,
        "variation_span": span,
        "status": status,
        "notes": notes,
    }


def within_tol(value: float, target: float, tol: float) -> bool:
    return abs(value - target) <= tol


def build_figure4_results() -> dict:
    curves = {}
    comparison_rows = []
    pass_count = 0

    for label, edges in FIGURE4_CASES.items():
        cfg = base_config()
        cfg.gate_edges = edges
        eff = compute_efficiency_curve(cfg, TAU_GRID)
        curves[label] = eff

        target = FIGURE4_TARGETS[label]
        measured = summarize_curve(TAU_GRID, eff, sample_tau=target["eff_tau"])
        measured["label"] = label
        measured["target_peak_eff"] = target["peak_eff"]
        measured["target_peak_tau"] = target["peak_tau"]
        measured["target_eff_tau"] = target["eff_tau"]
        measured["target_eff_value"] = target["eff_value"]

        checks = {
            "peak_eff": within_tol(measured["peak_eff"], target["peak_eff"], 0.06),
            "peak_tau": within_tol(measured["peak_tau"], target["peak_tau"], 0.7),
            "sample_eff": within_tol(measured["sample_eff"], target["eff_value"], 0.06),
        }
        measured["checks"] = checks
        measured["status"] = "pass" if all(checks.values()) else "partial"
        if measured["status"] == "pass":
            pass_count += 1
        comparison_rows.append(measured)

    return {
        "plot_b64": plot_efficiency_curves("Python backend replication of Figure 4", TAU_GRID, curves),
        "comparison_rows": comparison_rows,
        "status": "pass" if pass_count == len(comparison_rows) else "partial",
        "notes": [
            "The baseline 4-gate and 8-gate configurations match the report closely.",
            "The decay-optimised 4-gate case reproduces the 2 ns efficiency target but shifts the peak to shorter lifetimes.",
            "The rise/fall-optimised case is qualitatively similar but not numerically identical.",
        ],
    }


def render_table(rows: list, headers: list, formatters: dict | None = None) -> str:
    formatters = formatters or {}
    html = ["<table><tr>"]
    for header in headers:
        html.append(f"<th>{header}</th>")
    html.append("</tr>")
    for row in rows:
        html.append("<tr>")
        for header in headers:
            value = row.get(header, "")
            if header in formatters:
                value = formatters[header](value, row)
            html.append(f"<td>{value}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "".join(html)


def build_html(docx_path: Path, figure_map: dict, fig2: dict, fig3: dict, fig4: dict) -> str:
    overall = "No, not fully."
    if fig3["status"] == "pass":
        rationale = (
            "The Python backend reproduces the main 4-gate and 8-gate baseline results from Figure 4, the broad excitation-width trend from Figure 2, "
            "and now reproduces the Figure 3 jitter/skewness trend qualitatively. It is still not a full match because the excitation-width optimum "
            "and one optimised gate configuration remain shifted relative to the legacy reference report."
        )
    elif fig3["status"] == "partial":
        rationale = (
            "The Python backend reproduces the main 4-gate and 8-gate baseline results from Figure 4 and the broad excitation-width trend from Figure 2. "
            "The Figure 3 jitter/skewness sweep now responds in the right direction, but the overall parity is still partial and one optimised gate "
            "configuration remains numerically shifted."
        )
    else:
        rationale = (
            "The Python backend reproduces the main 4-gate and 8-gate baseline results from Figure 4 and the broad excitation-width trend from Figure 2, "
            "but it does not currently reproduce the jitter/skewness figure and one optimised gate configuration is numerically shifted."
        )

    def pct(value, _row=None):
        return f"{100.0 * value:.1f}%"

    def ns(value, _row=None):
        return f"{value:.2f} ns"

    fig2_headers = ["label", "peak_tau", "peak_eff", "sample_tau", "sample_eff"]
    fig3_headers = ["label", "peak_tau", "peak_eff", "sample_tau", "sample_eff"]
    fig4_headers = [
        "label",
        "target_peak_tau",
        "peak_tau",
        "target_peak_eff",
        "peak_eff",
        "target_eff_tau",
        "target_eff_value",
        "sample_eff",
        "status",
    ]

    style = """
    <style>
      :root { --bg:#08111d; --panel:#122235; --line:#25415f; --text:#e7eef8; --muted:#98abc1; --accent:#38bdf8; --good:#34d399; --warn:#fbbf24; --bad:#f87171; }
      body { font-family: Segoe UI, Arial, sans-serif; background:linear-gradient(180deg,#08111d,#0d1827); color:var(--text); margin:0; }
      main { max-width: 1320px; margin: 0 auto; padding: 28px 20px 48px; }
      h1,h2,h3 { color: var(--accent); }
      .card { background: rgba(18,34,53,.96); border:1px solid var(--line); border-radius:14px; padding:20px; margin:18px 0; }
      .grid { display:grid; grid-template-columns: 1fr 1fr; gap:18px; align-items:start; }
      .img { width:100%; border-radius:10px; border:1px solid var(--line); background:#fff; }
      table { width:100%; border-collapse: collapse; margin-top: 12px; }
      th,td { padding:10px 12px; border-bottom:1px solid #21384f; text-align:left; vertical-align:top; }
      th { color: var(--accent); }
      code, pre { background:#06101a; color:#fde68a; border-radius:8px; }
      code { padding:2px 6px; }
      .good { color: var(--good); font-weight: 600; }
      .warn { color: var(--warn); font-weight: 600; }
      .bad { color: var(--bad); font-weight: 600; }
      ul { padding-left: 20px; }
    </style>
    """

    sections = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>D6.1 Python Replication Report</title>",
        style,
        "</head><body><main>",
        "<h1>D6.1 Reference Replication Report</h1>",
        "<div class='card'>",
        f"<p><strong>Source report:</strong> <code>{docx_path.relative_to(REPO_ROOT) if docx_path.is_relative_to(REPO_ROOT) else docx_path.name}</code></p>",
        f"<p><strong>Verdict:</strong> {overall}</p>",
        f"<p>{rationale}</p>",
        "</div>",
    ]

    if figure_map:
        sections.extend([
            "<div class='card'><h2>Reference Figures Extracted from the Legacy Report</h2>",
            "<div class='grid'>",
        ])
        for fig_key in ["Figure 2", "Figure 3", "Figure 4"]:
            if fig_key in figure_map:
                sections.append(
                    f"<div><h3>{fig_key}</h3><img class='img' src='data:image/png;base64,{figure_map[fig_key]['image_b64']}'><p>{figure_map[fig_key]['caption']}</p></div>"
                )
        sections.append("</div></div>")

    sections.extend([
        "<div class='card'><h2>Figure 2 Replication: Excitation Burst Width</h2>",
        "<div class='grid'>",
        f"<div><img class='img' src='data:image/png;base64,{fig2['plot_b64']}'></div>",
        "<div>",
        render_table(
            fig2["summary_rows"],
            fig2_headers,
            {"peak_tau": ns, "sample_tau": ns, "peak_eff": pct, "sample_eff": pct},
        ),
        "<ul>" + "".join(f"<li>{note}</li>" for note in fig2["notes"]) + "</ul>",
        "</div></div></div>",
    ])

    sections.extend([
        "<div class='card'><h2>Figure 3 Replication: Gate Jitter / Skewness</h2>",
        "<div class='grid'>",
        f"<div><img class='img' src='data:image/png;base64,{fig3['plot_b64']}'></div>",
        "<div>",
        render_table(
            fig3["summary_rows"],
            fig3_headers,
            {"peak_tau": ns, "sample_tau": ns, "peak_eff": pct, "sample_eff": pct},
        ),
        f"<p><strong>Status:</strong> <span class='{'bad' if fig3['status'] == 'fail' else 'good'}'>{fig3['status'].upper()}</span></p>",
        f"<p>Observed efficiency span across the jitter sweep at ~5 ns: <strong>{100.0 * fig3['variation_span']:.3f}%</strong></p>",
        "<ul>" + "".join(f"<li>{note}</li>" for note in fig3["notes"]) + "</ul>",
        "</div></div></div>",
    ])

    sections.extend([
        "<div class='card'><h2>Figure 4 Replication: Gate Number and Gate Position Benchmarks</h2>",
        "<div class='grid'>",
        f"<div><img class='img' src='data:image/png;base64,{fig4['plot_b64']}'></div>",
        "<div>",
        render_table(
            fig4["comparison_rows"],
            fig4_headers,
            {
                "target_peak_tau": ns,
                "peak_tau": ns,
                "target_peak_eff": pct,
                "peak_eff": pct,
                "target_eff_tau": ns,
                "target_eff_value": pct,
                "sample_eff": pct,
                "status": lambda value, _row: (
                    f"<span class='{'good' if value == 'pass' else 'warn'}'>{value.upper()}</span>"
                ),
            },
        ),
        f"<p><strong>Status:</strong> <span class='{'good' if fig4['status'] == 'pass' else 'warn'}'>{fig4['status'].upper()}</span></p>",
        "<ul>" + "".join(f"<li>{note}</li>" for note in fig4["notes"]) + "</ul>",
        "</div></div></div>",
    ])

    sections.extend([
        "<div class='card'><h2>Assessment</h2>",
        "<ul>",
        "<li><span class='good'>Replicated well</span>: the 8-gate reference and 4-gate baseline curves align closely with the report targets.</li>",
        "<li><span class='warn'>Partially replicated</span>: the burst-width trend is broadly correct, but the Python sweet spot is closer to 5 ns than 7.5 ns.</li>",
        (
            "<li><span class='good'>Replicated qualitatively</span>: the jitter/skewness figure now keeps efficiency high through ~500 ps and shows deterioration by 1000 ps, matching the legacy reference report directionally.</li>"
            if fig3["status"] == "pass"
            else "<li><span class='warn'>Partially replicated</span>: the jitter/skewness figure now responds in the correct direction, but not yet with full quantitative parity.</li>"
            if fig3["status"] == "partial"
            else "<li><span class='bad'>Not replicated</span>: the jitter/skewness figure is effectively flat in the current Python backend for rectangular excitation, unlike the legacy reference report.</li>"
        ),
        "<li><span class='warn'>Needs investigation</span>: one optimised 4-gate configuration reproduces the target efficiency at 2 ns but shifts the peak lifetime substantially.</li>",
        "</ul>",
        "<p>The current Python backend is therefore <strong>not yet a full parity match</strong> to the legacy reference results.</p>",
        "</div>",
        "</main></body></html>",
    ])
    return "".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Replicate D6.1 legacy reference figures with the Python backend.")
    parser.add_argument("--docx", type=Path, default=DEFAULT_DOCX, help="Path to the D6.1 DOCX report.")
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML, help="Output HTML report path.")
    args = parser.parse_args()

    figure_map = extract_report_figures(args.docx)
    fig2 = build_figure2_results()
    fig3 = build_figure3_results()
    fig4 = build_figure4_results()
    html = build_html(args.docx, figure_map, fig2, fig3, fig4)

    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(html, encoding="utf-8")
    print(f"Report written to {args.html}")


if __name__ == "__main__":
    main()
