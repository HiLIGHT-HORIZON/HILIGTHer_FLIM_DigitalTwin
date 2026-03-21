import csv
import html
import re
from pathlib import Path

import numpy as np


LIGHT_PALETTE = {
    "page_bg": "#f5f7fb",
    "panel_bg": "#ffffff",
    "plot_bg": "#ffffff",
    "text": "#0f172a",
    "muted": "#475569",
    "grid": "#d7dee8",
    "ideal": "#2ca02c",
    "pdf": "#111827",
    "irf": "#0f766e",
    "identity": "#6b7280",
    "bg_curve": "#cbd5e1",
    "series": ["#1f77b4", "#d62728", "#9467bd", "#ff7f0e", "#2ca02c", "#17becf", "#8c564b"],
    "gate_series": ["#d62728", "#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#17becf"],
}

DARK_PALETTE = {
    "page_bg": "#07111f",
    "panel_bg": "#10233d",
    "plot_bg": "#0a0a0a",
    "text": "#e5eefb",
    "muted": "#9fb3ca",
    "grid": "#29415f",
    "ideal": "#34d399",
    "pdf": "#f8fafc",
    "irf": "#22d3ee",
    "identity": "#d1d5db",
    "bg_curve": "#64748b",
    "series": ["#8b5cf6", "#3b82f6", "#ec4899", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"],
    "gate_series": ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"],
}


def slugify(text):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip().lower()).strip("_")
    return value or "series"


def get_palette(theme_name):
    return DARK_PALETTE if str(theme_name).lower() == "dark" else LIGHT_PALETTE


def _get_matplotlib_pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def write_precision_report_package(file_path, payload):
    html_path = Path(file_path)
    if html_path.suffix.lower() != ".html":
        html_path = html_path.with_suffix(".html")

    asset_dir = html_path.with_name(f"{html_path.stem}_assets")
    asset_dir.mkdir(parents=True, exist_ok=True)

    table_entries = _write_csv_assets(asset_dir, payload)
    image_entries = _write_svg_assets(asset_dir, payload)
    html_path.write_text(
        _build_report_html(payload, asset_dir.name, table_entries, image_entries),
        encoding="utf-8",
    )
    return str(html_path), str(asset_dir)


def _write_csv(path, header_rows, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for header_row in header_rows:
            writer.writerow(header_row)
        writer.writerows(rows)


def _header_descriptor(header, x_label):
    x_unit = "[ns]" if "tau" in str(x_label).lower() else ""
    if header == x_label:
        return ("X", str(x_label), f"{x_label} {x_unit}".strip())
    if header == "ideal_f":
        return ("Y", "Numerical F", "Ideal Reference [F]")
    if header == "ideal_eff":
        return ("Y", "Numerical F^-2", "Ideal Reference [F^-2]")
    if header == "ideal_throughput":
        return ("Y", "Numerical Throughput", "Ideal Reference [throughput]")
    if header == "time_ns":
        return ("X", "Time", "Time [ns]")
    if header == "irf":
        return ("Y", "Excitation", "IRF amplitude [a.u.]")
    if header == "pdf":
        return ("Y", "Reference PDF", "PDF amplitude [a.u.]")
    if header == "iteration":
        return ("X", "Iteration", "Iteration index")
    if header == "objective":
        return ("Y", "Optimisation objective", "Objective value")
    if header == "minimum_f":
        return ("Y", "Minimum F", "Minimum F [F]")
    if header == "minimum_f_inv2":
        return ("Y", "Minimum F^-2", "Minimum F^-2 [efficiency]")
    if header == "auc_f_inv2":
        return ("Y", "AUC F^-2", "Area under F^-2 curve")
    if header == "throughput":
        return ("Y", "Fisher Throughput", "Fisher throughput")
    if header == "throughput_auc":
        return ("Y", "Throughput AUC", "Area under throughput curve")
    if header == "gate_count":
        return ("Y", "Gate count", "Number of gates")
    if header == "label":
        return ("Y", "Snapshot label", "State label")
    if header == "gate_edges_ns":
        return ("Y", "Gate edges", "Gate edges [ns]")
    if header.startswith("gate_"):
        gate_idx = header.split("_", 1)[1]
        return ("Y", "Gate waveform", f"Gate {gate_idx} [a.u.]")
    if header.endswith("_theory_f"):
        label = header[: -len("_theory_f")].replace("_", " ")
        return ("Y", "Numerical F", f"{label} [F]")
    if header.endswith("_theory_eff"):
        label = header[: -len("_theory_eff")].replace("_", " ")
        return ("Y", "Numerical F^-2", f"{label} [F^-2]")
    if header.endswith("_theory_throughput"):
        label = header[: -len("_theory_throughput")].replace("_", " ")
        return ("Y", "Numerical Throughput", f"{label} [throughput]")
    if header.endswith("_mc_f"):
        label = header[: -len("_mc_f")].replace("_", " ")
        return ("Y", "Monte Carlo mean F", f"{label} [F]")
    if header.endswith("_mc_eff"):
        label = header[: -len("_mc_eff")].replace("_", " ")
        return ("Y", "Monte Carlo mean F^-2", f"{label} [F^-2]")
    if header.endswith("_mc_throughput"):
        label = header[: -len("_mc_throughput")].replace("_", " ")
        return ("Y", "Monte Carlo mean Throughput", f"{label} [throughput]")
    if header.endswith("_mean_tau"):
        label = header[: -len("_mean_tau")].replace("_", " ")
        return ("Y", "Monte Carlo mean estimate", f"{label} [estimate]")
    if header.endswith("_std_tau"):
        label = header[: -len("_std_tau")].replace("_", " ")
        return ("Y", "Monte Carlo standard deviation", f"{label} [estimate]")
    if header.endswith("_mc_f_ci_lower"):
        label = header[: -len("_mc_f_ci_lower")].replace("_", " ")
        return ("Y", "Lower 95% CI on F", f"{label} [F]")
    if header.endswith("_mc_f_ci_upper"):
        label = header[: -len("_mc_f_ci_upper")].replace("_", " ")
        return ("Y", "Upper 95% CI on F", f"{label} [F]")
    if header.endswith("_mc_eff_ci_lower"):
        label = header[: -len("_mc_eff_ci_lower")].replace("_", " ")
        return ("Y", "Lower 95% CI on F^-2", f"{label} [F^-2]")
    if header.endswith("_mc_eff_ci_upper"):
        label = header[: -len("_mc_eff_ci_upper")].replace("_", " ")
        return ("Y", "Upper 95% CI on F^-2", f"{label} [F^-2]")
    if header.endswith("_mc_throughput_ci_lower"):
        label = header[: -len("_mc_throughput_ci_lower")].replace("_", " ")
        return ("Y", "Lower 95% CI on Throughput", f"{label} [throughput]")
    if header.endswith("_mc_throughput_ci_upper"):
        label = header[: -len("_mc_throughput_ci_upper")].replace("_", " ")
        return ("Y", "Upper 95% CI on Throughput", f"{label} [throughput]")
    if header.endswith("_mean"):
        label = header[: -len("_mean")].replace("_", " ")
        return ("Y", "MLE mean estimate", f"{label} [estimate]")
    if header.endswith("_std"):
        label = header[: -len("_std")].replace("_", " ")
        return ("Y", "MLE standard deviation", f"{label} [estimate]")
    if header.startswith("optimization_") or header.startswith("optimize_") or header.startswith("detection_opt_") or header.startswith("excitation_"):
        return ("Y", "Optimisation option", header.replace("_", " "))
    return ("Y", "Exported value", header.replace("_", " "))


def _header_rows(headers, x_label):
    descriptors = [_header_descriptor(header, x_label) for header in headers]
    return [
        [item[0] for item in descriptors],
        [item[1] for item in descriptors],
        [item[2] for item in descriptors],
    ]


def _write_csv_assets(asset_dir, payload):
    entries = []
    x_values = np.asarray(payload["x_range"], dtype=float)
    x_label = payload["x_label"]

    theory_headers = [x_label, "ideal_f", "ideal_eff", "ideal_throughput"]
    for series in payload["series"]:
        series_slug = slugify(series["label"])
        theory_headers.extend([f"{series_slug}_theory_f", f"{series_slug}_theory_eff", f"{series_slug}_theory_throughput"])
    theory_rows = []
    for idx, x_val in enumerate(x_values):
        row = [x_val, payload["ideal_f"][idx], payload["ideal_eff"][idx], payload["ideal_throughput"][idx]]
        for series in payload["series"]:
            row.extend([series["theory_f"][idx], series["theory_eff"][idx], series["theory_throughput"][idx]])
        theory_rows.append(row)
    theory_name = "precision_theory.csv"
    theory_header_rows = _header_rows(theory_headers, x_label)
    _write_csv(asset_dir / theory_name, theory_header_rows, theory_rows)
    entries.append({
        "title": "Precision Theory Data",
        "filename": theory_name,
        "headers": theory_headers,
        "header_rows": theory_header_rows,
        "rows": theory_rows,
        "column_help": _describe_columns(theory_headers, x_label),
    })

    mc_series = [series for series in payload["series"] if series.get("mc_f")]
    if mc_series:
        mc_headers = [x_label]
        for series in mc_series:
            series_slug = slugify(series["label"])
            mc_headers.extend([
                f"{series_slug}_mc_f",
                f"{series_slug}_mc_eff",
                f"{series_slug}_mc_throughput",
                f"{series_slug}_mean_tau",
                f"{series_slug}_std_tau",
                f"{series_slug}_mc_f_ci_lower",
                f"{series_slug}_mc_f_ci_upper",
                f"{series_slug}_mc_eff_ci_lower",
                f"{series_slug}_mc_eff_ci_upper",
                f"{series_slug}_mc_throughput_ci_lower",
                f"{series_slug}_mc_throughput_ci_upper",
            ])
        mc_rows = []
        for idx, x_val in enumerate(x_values):
            row = [x_val]
            for series in mc_series:
                row.extend([
                    series["mc_f"][idx],
                    series["mc_eff"][idx],
                    series["mc_throughput"][idx],
                    series["mc_mean"][idx],
                    series["mc_std"][idx],
                    series["mc_f_ci_lower"][idx],
                    series["mc_f_ci_upper"][idx],
                    series["mc_eff_ci_lower"][idx],
                    series["mc_eff_ci_upper"][idx],
                    series["mc_throughput_ci_lower"][idx],
                    series["mc_throughput_ci_upper"][idx],
                ])
            mc_rows.append(row)
        mc_name = "precision_monte_carlo.csv"
        mc_header_rows = _header_rows(mc_headers, x_label)
        _write_csv(asset_dir / mc_name, mc_header_rows, mc_rows)
        entries.append({
            "title": "Precision Monte Carlo Data",
            "filename": mc_name,
            "headers": mc_headers,
            "header_rows": mc_header_rows,
            "rows": mc_rows,
            "column_help": _describe_columns(mc_headers, x_label),
        })

    accuracy = payload.get("accuracy", {})
    accuracy_series = accuracy.get("series", [])
    if accuracy_series:
        accuracy_headers = [x_label]
        for series in accuracy_series:
            series_slug = slugify(series["label"])
            accuracy_headers.extend([f"{series_slug}_mean", f"{series_slug}_std"])
        accuracy_rows = []
        for idx, x_val in enumerate(x_values):
            row = [x_val]
            for series in accuracy_series:
                row.extend([series["mean"][idx], series["std"][idx]])
            accuracy_rows.append(row)
        accuracy_name = "accuracy_mle_tracking.csv"
        accuracy_header_rows = _header_rows(accuracy_headers, x_label)
        _write_csv(asset_dir / accuracy_name, accuracy_header_rows, accuracy_rows)
        entries.append({
            "title": "MLE Accuracy Data",
            "filename": accuracy_name,
            "headers": accuracy_headers,
            "header_rows": accuracy_header_rows,
            "rows": accuracy_rows,
            "column_help": _describe_columns(accuracy_headers, x_label),
        })

    for frame_idx, frame in enumerate(payload.get("frames", []), start=1):
        frame_slug = slugify(frame["label"])
        headers = ["time_ns", "irf", "pdf"] + [f"gate_{gate_idx + 1}" for gate_idx in range(len(frame["gates"]))]
        rows = []
        time_vals = np.asarray(frame["time"], dtype=float)
        irf_vals = np.asarray(frame["irf"], dtype=float)
        pdf_vals = np.asarray(frame["pdf"], dtype=float)
        if irf_vals.size == 0:
            irf_vals = np.full(time_vals.shape, np.nan, dtype=float)
        if pdf_vals.size == 0:
            pdf_vals = np.full(time_vals.shape, np.nan, dtype=float)
        gate_vals = [np.asarray(gate, dtype=float) for gate in frame["gates"]]
        for idx, time_val in enumerate(time_vals):
            row = [time_val, irf_vals[idx], pdf_vals[idx]]
            for gate in gate_vals:
                row.append(gate[idx])
            rows.append(row)
        filename = f"gates_{frame_idx:02d}_{frame_slug}.csv"
        header_rows = _header_rows(headers, x_label)
        _write_csv(asset_dir / filename, header_rows, rows)
        entries.append({
            "title": f"Diagnostics Gate Data: {frame['label']}",
            "filename": filename,
            "headers": headers,
            "header_rows": header_rows,
            "rows": rows,
            "column_help": _describe_columns(headers, x_label),
        })

    optimisation = payload.get("optimization")
    if optimisation:
        options = optimisation.get("options", {})
        if options:
            opt_headers = list(options.keys())
            opt_rows = [[options.get(header) for header in opt_headers]]
            opt_name = "optimisation_options.csv"
            opt_header_rows = _header_rows(opt_headers, x_label)
            _write_csv(asset_dir / opt_name, opt_header_rows, opt_rows)
            entries.append({
                "title": "Optimisation Options",
                "filename": opt_name,
                "headers": opt_headers,
                "header_rows": opt_header_rows,
                "rows": opt_rows,
                "column_help": _describe_columns(opt_headers, x_label),
            })

        objective_history = optimisation.get("objective_history", [])
        min_f_history = optimisation.get("min_f_history", [])
        min_eff_history = optimisation.get("min_eff_history", [])
        auc_eff_history = optimisation.get("auc_eff_history", [])
        throughput_history = optimisation.get("throughput_history", [])
        throughput_auc_history = optimisation.get("throughput_auc_history", [])
        gate_count_history = optimisation.get("gate_count_history", [])
        if objective_history or min_f_history or min_eff_history or auc_eff_history or throughput_history or throughput_auc_history or gate_count_history:
            history_headers = ["iteration", "objective", "minimum_f", "minimum_f_inv2", "auc_f_inv2", "throughput", "throughput_auc", "gate_count"]
            history_rows = []
            n_rows = max(
                len(objective_history),
                len(min_f_history),
                len(min_eff_history),
                len(auc_eff_history),
                len(throughput_history),
                len(throughput_auc_history),
                len(gate_count_history),
            )
            for idx in range(n_rows):
                history_rows.append([
                    idx,
                    objective_history[idx] if idx < len(objective_history) else np.nan,
                    min_f_history[idx] if idx < len(min_f_history) else np.nan,
                    min_eff_history[idx] if idx < len(min_eff_history) else np.nan,
                    auc_eff_history[idx] if idx < len(auc_eff_history) else np.nan,
                    throughput_history[idx] if idx < len(throughput_history) else np.nan,
                    throughput_auc_history[idx] if idx < len(throughput_auc_history) else np.nan,
                    gate_count_history[idx] if idx < len(gate_count_history) else np.nan,
                ])
            history_name = "optimisation_history.csv"
            history_header_rows = _header_rows(history_headers, x_label)
            _write_csv(asset_dir / history_name, history_header_rows, history_rows)
            entries.append({
                "title": "Optimisation History",
                "filename": history_name,
                "headers": history_headers,
                "header_rows": history_header_rows,
                "rows": history_rows,
                "column_help": _describe_columns(history_headers, x_label),
            })

        snapshots = optimisation.get("snapshots", [])
        if snapshots:
            snapshot_headers = ["label", "gate_count", "objective", "minimum_f", "gate_edges_ns"]
            snapshot_rows = []
            for snapshot in snapshots:
                cfg = snapshot.get("config", {})
                edges = cfg.get("gate_edges", [])
                snapshot_rows.append([
                    snapshot.get("label", ""),
                    int(snapshot.get("gate_count", max(0, len(edges) - 1))),
                    snapshot.get("objective", np.nan),
                    snapshot.get("min_f", np.nan),
                    ", ".join(f"{float(edge):.6g}" for edge in edges),
                ])
            snapshot_name = "optimisation_snapshots.csv"
            snapshot_header_rows = _header_rows(snapshot_headers, x_label)
            _write_csv(asset_dir / snapshot_name, snapshot_header_rows, snapshot_rows)
            entries.append({
                "title": "Optimisation Snapshot Summary",
                "filename": snapshot_name,
                "headers": snapshot_headers,
                "header_rows": snapshot_header_rows,
                "rows": snapshot_rows,
                "column_help": _describe_columns(snapshot_headers, x_label),
            })

    return entries


def _save_precision_svg(path, payload, theme_name):
    plt = _get_matplotlib_pyplot()
    palette = get_palette(theme_name)
    metric = payload["precision_display"]["metric"]
    log_x = bool(payload["precision_display"]["log_x"])
    log_y = bool(payload["precision_display"]["log_y"])
    y_label = "Fisher Throughput" if metric == "throughput" else ("Photon Efficiency (F^-2)" if metric == "efficiency" else "F-Value")
    fig, ax = plt.subplots(figsize=(10.8, 6.8), constrained_layout=False)
    _style_axes(fig, ax, palette)

    x = np.asarray(payload["x_range"], dtype=float)
    ideal_key = "ideal_throughput" if metric == "throughput" else ("ideal_eff" if metric == "efficiency" else "ideal_f")
    ideal = np.asarray(payload[ideal_key], dtype=float)
    ax.plot(x, ideal, linestyle="--", linewidth=2.0, color=palette["ideal"], label="Ideal Reference")

    for idx, series in enumerate(payload["series"]):
        color = palette["series"][idx % len(palette["series"])]
        theory_key = "theory_throughput" if metric == "throughput" else ("theory_eff" if metric == "efficiency" else "theory_f")
        theory = np.asarray(series[theory_key], dtype=float)
        theory_mask = np.isfinite(x) & np.isfinite(theory)
        if log_x:
            theory_mask &= x > 0
        if log_y:
            theory_mask &= theory > 0
        _plot_masked_line(ax, x, theory, theory_mask, color=color, linewidth=2.0, label=f"Theory | {series['label']}")

        mc_key = "mc_throughput" if metric == "throughput" else ("mc_eff" if metric == "efficiency" else "mc_f")
        ci_low_key = "mc_throughput_ci_lower" if metric == "throughput" else ("mc_eff_ci_lower" if metric == "efficiency" else "mc_f_ci_lower")
        ci_high_key = "mc_throughput_ci_upper" if metric == "throughput" else ("mc_eff_ci_upper" if metric == "efficiency" else "mc_f_ci_upper")
        mc_vals = np.asarray(series.get(mc_key, []), dtype=float) if series.get(mc_key) else np.array([])
        ci_low = np.asarray(series.get(ci_low_key, []), dtype=float) if series.get(ci_low_key) else np.array([])
        ci_high = np.asarray(series.get(ci_high_key, []), dtype=float) if series.get(ci_high_key) else np.array([])

        if mc_vals.size:
            has_ci = ci_low.size == x.size and ci_high.size == x.size and np.any(np.isfinite(ci_low)) and np.any(np.isfinite(ci_high))
            if has_ci:
                mask = np.isfinite(x) & np.isfinite(ci_low) & np.isfinite(ci_high)
                if log_x:
                    mask &= x > 0
                if log_y:
                    mask &= (ci_low > 0) & (ci_high > 0)
                if np.any(mask):
                    ax.fill_between(x[mask], ci_low[mask], ci_high[mask], color=color, alpha=0.18, label=f"Monte Carlo 95% CI | {series['label']}")
            else:
                mask = np.isfinite(x) & np.isfinite(mc_vals)
                if log_x:
                    mask &= x > 0
                if log_y:
                    mask &= mc_vals > 0
                ax.scatter(x[mask], mc_vals[mask], color=color, s=24, alpha=0.9, label=f"Monte Carlo | {series['label']}")

    if log_x:
        ax.set_xscale("log")
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel(payload["x_label"])
    ax.set_ylabel(y_label)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
        fontsize=9,
        frameon=False,
        ncols=2,
        handlelength=2.4,
        columnspacing=1.4,
        borderaxespad=0.0,
    )
    ax.margins(x=0.04, y=0.08)
    fig.subplots_adjust(left=0.11, right=0.98, top=0.97, bottom=0.28)
    fig.savefig(path, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_accuracy_svg(path, payload, theme_name):
    plt = _get_matplotlib_pyplot()
    accuracy = payload.get("accuracy", {})
    series_list = accuracy.get("series", [])
    if not series_list:
        return False

    palette = get_palette(theme_name)
    fig, ax = plt.subplots(figsize=(10.8, 6.2), constrained_layout=False)
    _style_axes(fig, ax, palette)

    stacked = bool(accuracy.get("stacked"))
    all_means = [np.asarray(series["mean"], dtype=float) for series in series_list if len(series["mean"])]
    offset_step = 0.0
    if stacked and all_means:
        flat_means = np.concatenate(all_means)
        finite = flat_means[np.isfinite(flat_means)]
        if finite.size:
            offset_step = max((np.nanmax(finite) - np.nanmin(finite)) * 0.15, 1.0)

    x = np.asarray(payload["x_range"], dtype=float)
    for idx, series in enumerate(series_list):
        color = palette["series"][idx % len(palette["series"])]
        mean = np.asarray(series["mean"], dtype=float)
        std = np.asarray(series["std"], dtype=float)
        mask = np.isfinite(x) & np.isfinite(mean) & np.isfinite(std)
        if not np.any(mask):
            continue
        offset = idx * offset_step if stacked else 0.0
        x_plot = x[mask]
        mean_plot = mean[mask] + offset
        std_plot = std[mask]
        ax.plot(x_plot, x_plot + offset, linestyle="--", linewidth=1.4, color=palette["identity"])
        ax.errorbar(
            x_plot,
            mean_plot,
            yerr=std_plot,
            fmt="o-",
            markersize=4,
            linewidth=1.8,
            capsize=2,
            color=color,
            label=series["label"],
        )

    ax.set_xlabel(payload["x_label"])
    ax.set_ylabel("Estimated Value")
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        fontsize=9,
        frameon=False,
        ncols=2,
        borderaxespad=0.0,
    )
    ax.margins(x=0.04, y=0.08)
    fig.subplots_adjust(left=0.11, right=0.98, top=0.97, bottom=0.24)
    fig.savefig(path, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def _save_diagnostics_svg(path, frame, theme_name):
    plt = _get_matplotlib_pyplot()
    palette = get_palette(theme_name)
    fig, ax = plt.subplots(figsize=(10.8, 5.2), constrained_layout=False)
    _style_axes(fig, ax, palette)

    time_vals = np.asarray(frame["time"], dtype=float)
    for idx, gate in enumerate(frame["gates"]):
        gate_vals = np.asarray(gate, dtype=float)
        gate_norm = gate_vals / np.nanmax(gate_vals) if np.nanmax(gate_vals) > 0 else gate_vals
        color = palette["gate_series"][idx % len(palette["gate_series"])]
        ax.plot(time_vals, gate_norm, linewidth=1.4, color=color, label=f"Gate {idx + 1}")
        ax.fill_between(time_vals, gate_norm, 0.0, color=color, alpha=0.16)

    irf = np.asarray(frame["irf"], dtype=float)
    pdf = np.asarray(frame["pdf"], dtype=float)
    if irf.size:
        irf_norm = irf / np.nanmax(irf) if np.nanmax(irf) > 0 else irf
        ax.plot(time_vals, irf_norm, linewidth=2.2, color=palette["irf"], label="Excitation (IRF)")
    if pdf.size:
        pdf_norm = pdf / np.nanmax(pdf) if np.nanmax(pdf) > 0 else pdf
        ax.plot(time_vals, pdf_norm, linewidth=2.2, linestyle="--", color=palette["pdf"], label="Reference PDF")

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Relative Amplitude")
    ax.set_title(frame["label"], color=palette["text"], fontsize=12)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        fontsize=8,
        frameon=False,
        ncols=3,
        borderaxespad=0.0,
    )
    ax.margins(x=0.02, y=0.08)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.26)
    fig.savefig(path, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_optimization_history_svg(path, payload, theme_name):
    plt = _get_matplotlib_pyplot()
    optimisation = payload.get("optimization", {})
    objective = np.asarray(optimisation.get("objective_history", []), dtype=float)
    min_f = np.asarray(optimisation.get("min_f_history", []), dtype=float)
    min_eff = np.asarray(optimisation.get("min_eff_history", []), dtype=float)
    auc_eff = np.asarray(optimisation.get("auc_eff_history", []), dtype=float)
    throughput = np.asarray(optimisation.get("throughput_history", []), dtype=float)
    throughput_auc = np.asarray(optimisation.get("throughput_auc_history", []), dtype=float)
    gate_count = np.asarray(optimisation.get("gate_count_history", []), dtype=float)
    n = max(objective.size, min_f.size, min_eff.size, auc_eff.size, throughput.size, throughput_auc.size, gate_count.size)
    if n == 0:
        return False
    x_vals = np.arange(n, dtype=float)

    palette = get_palette(theme_name)
    fig, ax = plt.subplots(figsize=(11.0, 5.8), constrained_layout=False)
    _style_axes(fig, ax, palette)
    ax.set_yscale("log")
    ax2 = ax.twinx()
    _style_axes(fig, ax2, palette)
    ax2.set_yscale("log")
    ax2.grid(False)
    if objective.size:
        ax.plot(x_vals[: objective.size], objective, color=palette["series"][0], linewidth=2.0, marker="o", markersize=4, label="Objective")
    if min_f.size:
        ax2.plot(x_vals[: min_f.size], min_f, color=palette["series"][1], linewidth=1.8, marker="o", markersize=3.5, label="Min F")
    if min_eff.size:
        ax2.plot(x_vals[: min_eff.size], min_eff, color=palette["series"][2], linewidth=1.8, marker="o", markersize=3.5, label="Min F^-2")
    if auc_eff.size:
        ax2.plot(x_vals[: auc_eff.size], auc_eff, color=palette["series"][3], linewidth=1.8, marker="o", markersize=3.5, label="AUC F^-2")
    if throughput.size:
        ax2.plot(x_vals[: throughput.size], throughput, color=palette["series"][4], linewidth=1.8, marker="o", markersize=3.5, label="Throughput")
    if throughput_auc.size:
        ax2.plot(x_vals[: throughput_auc.size], throughput_auc, color=palette["series"][5], linewidth=1.8, marker="o", markersize=3.5, label="Throughput AUC")
    if gate_count.size and np.nanmax(gate_count) != np.nanmin(gate_count):
        ax2.plot(x_vals[: gate_count.size], gate_count, color=palette["series"][6], linewidth=1.8, marker="o", markersize=3.5, label="Gate count")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Objective")
    ax2.set_ylabel("F / F^-2 / Throughput / Gates")
    ax.set_title("Optimisation History", color=palette["text"], fontsize=12)
    handles, labels = [], []
    for axes in (ax, ax2):
        h, l = axes.get_legend_handles_labels()
        handles.extend(h)
        labels.extend(l)
    if handles:
        legend = ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(6, len(handles)), frameon=False)
        for text in legend.get_texts():
            text.set_color(palette["text"])
    ax.margins(x=0.03, y=0.08)
    fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.28)
    fig.savefig(path, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def _plot_masked_line(ax, x, y, mask, color, linewidth, label):
    if not np.any(mask):
        return
    idx = np.flatnonzero(mask)
    splits = np.where(np.diff(idx) > 1)[0] + 1
    first = True
    for segment in np.split(idx, splits):
        ax.plot(
            x[segment],
            y[segment],
            color=color,
            linewidth=linewidth,
            label=label if first else None,
        )
        first = False


def _style_axes(fig, ax, palette):
    fig.patch.set_facecolor(palette["page_bg"])
    ax.set_facecolor(palette["plot_bg"])
    ax.grid(True, color=palette["grid"], linewidth=0.8, alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color(palette["grid"])
    ax.tick_params(colors=palette["text"], pad=6)
    ax.xaxis.label.set_color(palette["text"])
    ax.yaxis.label.set_color(palette["text"])
    ax.xaxis.labelpad = 10
    ax.yaxis.labelpad = 10


def _write_svg_assets(asset_dir, payload):
    images = []

    for theme_name in ("dark", "light"):
        precision_name = f"precision_{theme_name}.svg"
        _save_precision_svg(asset_dir / precision_name, payload, theme_name)
    images.append({
        "group": "precision",
        "title": f"Precision Plot ({payload['precision_display']['metric_label']})",
        "dark": "precision_dark.svg",
        "light": "precision_light.svg",
    })

    accuracy_written = False
    for theme_name in ("dark", "light"):
        accuracy_name = f"accuracy_{theme_name}.svg"
        result = _save_accuracy_svg(asset_dir / accuracy_name, payload, theme_name)
        accuracy_written = accuracy_written or result
    if accuracy_written:
        images.append({
            "group": "accuracy",
            "title": "MLE Accuracy Plot",
            "dark": "accuracy_dark.svg",
            "light": "accuracy_light.svg",
        })

    diagnostics_entries = []
    for idx, frame in enumerate(payload.get("frames", []), start=1):
        frame_slug = slugify(frame["label"])
        dark_name = f"diagnostics_{idx:02d}_{frame_slug}_dark.svg"
        light_name = f"diagnostics_{idx:02d}_{frame_slug}_light.svg"
        _save_diagnostics_svg(asset_dir / dark_name, frame, "dark")
        _save_diagnostics_svg(asset_dir / light_name, frame, "light")
        diagnostics_entries.append({
            "group": "diagnostics",
            "title": f"Diagnostics Plot: {frame['label']}",
            "dark": dark_name,
            "light": light_name,
        })

    optimisation = payload.get("optimization")
    if optimisation:
        history_written = False
        for theme_name in ("dark", "light"):
            history_name = f"optimisation_history_{theme_name}.svg"
            history_written = _save_optimization_history_svg(
                asset_dir / history_name,
                payload,
                theme_name,
            ) or history_written
        if history_written:
            images.append({
                "group": "optimisation",
                "title": "Optimisation History",
                "dark": "optimisation_history_dark.svg",
                "light": "optimisation_history_light.svg",
            })

    return images + diagnostics_entries


def _table_to_html(entry, asset_dir_name):
    header_rows = entry.get("header_rows") or [entry["headers"]]
    headers = "".join(
        "<tr>" + "".join(f"<th>{html.escape(str(value))}</th>" for value in row) + "</tr>"
        for row in header_rows
    )
    body_rows = []
    for row in entry["rows"]:
        cells = "".join(f"<td>{html.escape(_format_cell(value))}</td>" for value in row)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    help_items = "".join(f"<li>{html.escape(item)}</li>" for item in entry.get("column_help", []))
    return (
        f"<section class='panel'>"
        f"<div class='section-head'><h3>{html.escape(entry['title'])}</h3>"
        f"<a href='{asset_dir_name}/{html.escape(entry['filename'])}' download>Download CSV</a></div>"
        f"<div class='column-help'><strong>Column guide</strong><ul>{help_items}</ul></div>"
        f"<div class='table-wrap'><table><thead>{headers}</thead><tbody>{body}</tbody></table></div>"
        f"</section>"
    )


def _format_cell(value):
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return ""
        return f"{float(value):.8g}"
    return str(value)


def _describe_column(header, x_label):
    if header == x_label:
        return f"{header}: swept x-axis value used for this precision run."
    if header == "time_ns":
        return "time_ns: time sample in nanoseconds for the diagnostics waveform export."
    if header == "iteration":
        return "iteration: optimisation iteration index used for the progress-history export."
    if header == "objective":
        return "objective: optimisation objective value recorded for that iteration or retained state."
    if header == "minimum_f":
        return "minimum_f: minimum F value across the swept x-axis for that optimisation state."
    if header == "minimum_f_inv2":
        return "minimum_f_inv2: minimum photon efficiency, computed as F^-2, across the swept x-axis for that optimisation state."
    if header == "auc_f_inv2":
        return "auc_f_inv2: area under the F^-2 curve across the swept x-axis for that optimisation state."
    if header == "throughput":
        return "throughput: Fisher throughput summary tracked for that optimisation iteration."
    if header == "throughput_auc":
        return "throughput_auc: area under the Fisher-throughput curve across the swept x-axis for that optimisation iteration."
    if header == "gate_count":
        return "gate_count: number of detection gates used by that retained optimisation state."
    if header == "label":
        return "label: human-readable name for the retained optimisation state."
    if header == "gate_edges_ns":
        return "gate_edges_ns: comma-separated gate-edge positions in nanoseconds for the retained optimisation state."
    if header.startswith("optimization_") or header.startswith("optimize_") or header.startswith("detection_opt_") or header.startswith("excitation_"):
        return f"{header}: optimisation option captured from the controller configuration."
    if header == "ideal_f":
        return "ideal_f: ideal Fisher metric F for the same x-axis coordinate."
    if header == "ideal_eff":
        return "ideal_eff: ideal photon efficiency, computed as min(1, 1/F^2). The physical ceiling is 1."
    if header == "ideal_throughput":
        return "ideal_throughput: ideal Fisher throughput, computed here as ideal photon efficiency scaled by the normalized throughput factor."
    if header == "irf":
        return "irf: normalized excitation or instrument response function samples."
    if header == "pdf":
        return "pdf: normalized reference decay probability density samples."
    if header.startswith("gate_"):
        gate_idx = header.split("_", 1)[1]
        return f"{header}: normalized diagnostics trace for detection gate {gate_idx}."
    if header.endswith("_theory_f"):
        label = header[: -len("_theory_f")]
        return f"{header}: numerical-theory F values for sweep series '{label}'."
    if header.endswith("_theory_eff"):
        label = header[: -len("_theory_eff")]
        return f"{header}: numerical-theory photon efficiency values for sweep series '{label}', computed as min(1, 1/F^2)."
    if header.endswith("_theory_throughput"):
        label = header[: -len("_theory_throughput")]
        return f"{header}: numerical-theory Fisher throughput values for sweep series '{label}', computed as photon efficiency multiplied by the series throughput factor."
    if header.endswith("_mc_f"):
        label = header[: -len("_mc_f")]
        return f"{header}: Monte Carlo validation F values for sweep series '{label}'."
    if header.endswith("_mc_eff"):
        label = header[: -len("_mc_eff")]
        return f"{header}: Monte Carlo validation photon efficiency values for sweep series '{label}', computed as min(1, 1/F^2)."
    if header.endswith("_mc_throughput"):
        label = header[: -len("_mc_throughput")]
        return f"{header}: Monte Carlo validation Fisher throughput values for sweep series '{label}', computed as photon efficiency multiplied by the series throughput factor."
    if header.endswith("_mean_tau"):
        label = header[: -len("_mean_tau")]
        return f"{header}: mean estimated lifetime or parameter from Monte Carlo repeats for sweep series '{label}'."
    if header.endswith("_std_tau"):
        label = header[: -len("_std_tau")]
        return f"{header}: standard deviation of the estimated lifetime or parameter from Monte Carlo repeats for sweep series '{label}'."
    if header.endswith("_mc_f_ci_lower"):
        label = header[: -len("_mc_f_ci_lower")]
        return f"{header}: lower 95% bootstrap confidence bound on Monte Carlo F for sweep series '{label}'."
    if header.endswith("_mc_f_ci_upper"):
        label = header[: -len("_mc_f_ci_upper")]
        return f"{header}: upper 95% bootstrap confidence bound on Monte Carlo F for sweep series '{label}'."
    if header.endswith("_mc_eff_ci_lower"):
        label = header[: -len("_mc_eff_ci_lower")]
        return f"{header}: lower bootstrap confidence bound on Monte Carlo photon efficiency for sweep series '{label}'."
    if header.endswith("_mc_eff_ci_upper"):
        label = header[: -len("_mc_eff_ci_upper")]
        return f"{header}: upper bootstrap confidence bound on Monte Carlo photon efficiency for sweep series '{label}'."
    if header.endswith("_mc_throughput_ci_lower"):
        label = header[: -len("_mc_throughput_ci_lower")]
        return f"{header}: lower bootstrap confidence bound on Monte Carlo Fisher throughput for sweep series '{label}'."
    if header.endswith("_mc_throughput_ci_upper"):
        label = header[: -len("_mc_throughput_ci_upper")]
        return f"{header}: upper bootstrap confidence bound on Monte Carlo Fisher throughput for sweep series '{label}'."
    if header.endswith("_mean"):
        label = header[: -len("_mean")]
        return f"{header}: mean estimated parameter shown in the MLE accuracy panel for sweep series '{label}'."
    if header.endswith("_std"):
        label = header[: -len("_std")]
        return f"{header}: standard deviation or error-bar value shown in the MLE accuracy panel for sweep series '{label}'."
    return f"{header}: exported numeric column."


def _describe_columns(headers, x_label):
    return [_describe_column(header, x_label) for header in headers]


def _build_report_html(payload, asset_dir_name, table_entries, image_entries):
    tables_html = "".join(_table_to_html(entry, asset_dir_name) for entry in table_entries)
    image_blocks = []
    for image in image_entries:
        image_blocks.append(
            f"<figure class='panel image-panel'>"
            f"<figcaption>{html.escape(image['title'])}</figcaption>"
            f"<a class='image-link' href='{asset_dir_name}/{html.escape(image['dark'])}' target='_blank' rel='noopener noreferrer'>"
            f"<img class='theme-image' data-dark='{asset_dir_name}/{html.escape(image['dark'])}' "
            f"data-light='{asset_dir_name}/{html.escape(image['light'])}' "
            f"src='{asset_dir_name}/{html.escape(image['dark'])}' alt='{html.escape(image['title'])}'></a>"
            "</figure>"
        )
    images_html = "".join(image_blocks)
    config_text = html.escape(str(payload.get("config", {})))
    optimisation = payload.get("optimization", {})
    optimisation_items = ""
    if optimisation.get("options"):
        optimisation_items = "".join(
            f"<li><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</li>"
            for key, value in optimisation["options"].items()
        )
    optimisation_html = ""
    if optimisation:
        objective_points = len(optimisation.get("objective_history", []))
        snapshot_points = len(optimisation.get("snapshots", []))
        excitation_summary = optimisation.get("final_excitation_summary", {})
        excitation_summary_html = ""
        if excitation_summary:
            excitation_summary_html = (
                "<h3>Best Excitation Profile</h3><ul>"
                + "".join(
                    f"<li><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</li>"
                    for key, value in excitation_summary.items()
                )
                + "</ul>"
            )
        optimisation_html = (
            "<section class='panel'>"
            "<h2>Optimisation Run</h2>"
            f"<p class='meta'>Objective samples: {objective_points}<br>Retained displayed states: {snapshot_points}</p>"
            f"<ul>{optimisation_items}</ul>"
            f"{excitation_summary_html}"
            "</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HILIGHTer Precision and Optimisation Report</title>
  <style>
    :root {{
      --page-bg: #07111f;
      --panel-bg: #10233d;
      --text: #e5eefb;
      --muted: #9fb3ca;
      --line: #29415f;
      --link: #7dd3fc;
    }}
    body[data-theme="light"] {{
      --page-bg: #f5f7fb;
      --panel-bg: #ffffff;
      --text: #0f172a;
      --muted: #475569;
      --line: #d7dee8;
      --link: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--page-bg);
      color: var(--text);
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 24px;
    }}
    .panel {{
      background: var(--panel-bg);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .meta {{
      color: var(--muted);
      line-height: 1.6;
    }}
    button {{
      border: 1px solid var(--line);
      background: transparent;
      color: var(--text);
      border-radius: 999px;
      padding: 10px 16px;
      cursor: pointer;
      font-weight: 600;
    }}
    h1, h2, h3 {{
      margin: 0 0 12px;
    }}
    a {{
      color: var(--link);
      text-decoration: none;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    .column-help {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .column-help strong {{
      display: block;
      color: var(--text);
      margin-bottom: 6px;
    }}
    .column-help ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .column-help li {{
      margin: 3px 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 900px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{
      text-align: left;
      position: sticky;
      left: 0;
      background: var(--panel-bg);
    }}
    thead th {{
      position: sticky;
      top: 0;
      background: var(--panel-bg);
    }}
    .image-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 18px;
    }}
    .image-link {{
      display: block;
    }}
    .image-panel figcaption {{
      margin-bottom: 12px;
      font-weight: 600;
    }}
    .image-panel img {{
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #ffffff;
      cursor: zoom-in;
    }}
    pre {{
      white-space: pre-wrap;
      color: var(--muted);
      margin: 0;
    }}
    .math-block {{
      margin: 12px 0;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(127, 127, 127, 0.06);
    }}
    math {{
      font-size: 1.1rem;
    }}
  </style>
</head>
<body data-theme="dark">
  <main>
    <section class="panel hero">
      <div>
        <h1>HILIGHTer Precision and Optimisation Report</h1>
        <div class="meta">Generated: {html.escape(payload['timestamp'])}<br>X-Axis: {html.escape(payload['x_label'])}</div>
      </div>
      <button id="themeToggle" type="button">Switch to Light Theme</button>
    </section>

    <section class="panel">
      <h2>Configuration Snapshot</h2>
      <pre>{config_text}</pre>
    </section>

    <section class="panel">
      <h2>Metric Definitions</h2>
      <p>This report uses the same precision definitions as the desktop workspace and backend service layer.</p>
      <div class="math-block">
        <div><strong>Relative precision metric</strong></div>
        <math display="block">
          <mrow>
            <mi>F</mi>
            <mo>=</mo>
            <mfrac>
              <msub><mi>&sigma;</mi><mi>&theta;</mi></msub>
              <mrow><mo>|</mo><mi>&theta;</mi><mo>|</mo></mrow>
            </mfrac>
            <msqrt><mi>N</mi></msqrt>
          </mrow>
        </math>
      </div>
      <div class="math-block">
        <div><strong>Photon efficiency</strong></div>
        <math display="block">
          <mrow>
            <mi>&eta;</mi>
            <mo>=</mo>
            <mtext>min</mtext>
            <mo>(</mo>
            <mn>1</mn>
            <mo>,</mo>
            <mfrac><mn>1</mn><msup><mi>F</mi><mn>2</mn></msup></mfrac>
            <mo>)</mo>
          </mrow>
        </math>
      </div>
      <div class="math-block">
        <div><strong>Fisher scaling used in theory curves</strong></div>
        <math display="block">
          <mrow>
            <mi>I</mi><mo>(</mo><mi>&theta;</mi><mo>)</mo>
            <mo>=</mo>
            <mi>N</mi>
            <munderover><mo>&sum;</mo><mi>j</mi><mrow><mi>gates</mi></mrow></munderover>
            <mfrac>
              <msup>
                <mrow><mo>(</mo><mfrac><mrow><mi>d</mi><msub><mi>P</mi><mi>j</mi></msub></mrow><mrow><mi>d</mi><mi>&theta;</mi></mrow></mfrac><mo>)</mo></mrow>
                <mn>2</mn>
              </msup>
              <msub><mi>P</mi><mi>j</mi></msub>
            </mfrac>
          </mrow>
        </math>
      </div>
      <p class="meta">The ideal reference is always computed as an ideal histogram-bin ceiling. It does not inherit sequential-gating penalties or non-ideal overlap modes from the live configuration.</p>
    </section>

    <section class="panel">
      <h2>Gating Semantics</h2>
      <p>Equal gates are generated from the selected start and end anchors. Custom gates use the explicit edge list. Diagnostics plots show the raw geometric gate shapes, while overlap exclusivity is applied later in the statistical counting model.</p>
      <p class="meta">Sequential collection, explicit overlap, duplicate events, and independent duplicates are still under active development and should be interpreted cautiously.</p>
    </section>

    {optimisation_html}

    <section>
      <h2>SVG Plot Assets</h2>
      <p class="meta">Each figure is saved as a dark-theme and light-theme SVG in the asset folder. The light theme is intended for paper, poster, and slide reuse with a white background.</p>
      <div class="image-grid">
        {images_html}
      </div>
    </section>

    <section>
      <h2>Simulation Data</h2>
      <p class="meta">CSV tables are stored in the asset folder beside the HTML file. They contain the exact exported values used in the figures above.</p>
      {tables_html}
    </section>
  </main>
  <script>
    const toggle = document.getElementById('themeToggle');
    function applyTheme(theme) {{
      document.body.dataset.theme = theme;
      toggle.textContent = theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme';
      document.querySelectorAll('.theme-image').forEach((img) => {{
        img.src = theme === 'dark' ? img.dataset.dark : img.dataset.light;
        const link = img.closest('.image-link');
        if (link) {{
          link.href = theme === 'dark' ? img.dataset.dark : img.dataset.light;
        }}
      }});
    }}
    toggle.addEventListener('click', () => {{
      applyTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark');
    }});
    applyTheme('dark');
  </script>
</body>
</html>"""
