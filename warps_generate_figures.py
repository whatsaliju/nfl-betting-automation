"""
Generate publication-quality figures for the WARPS-NFL paper.

Figure 1: Walk-forward parameter stability (w_pyth and R by year)
Figure 2: MAE basin heatmap (w_pyth × R, full sample)
Figure 3: Prediction interval calibration (stated vs actual coverage)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
})

CHAMP_W = 0.75
CHAMP_R = 0.75
BLUE   = "#2563eb"
ORANGE = "#ea580c"
GRAY   = "#94a3b8"
GREEN  = "#16a34a"


# ─────────────────────────────────────────────
# Figure 1 — Walk-forward stability
# ─────────────────────────────────────────────

def fig_walk_forward():
    df = pd.read_csv("warps_q1_walk_forward.csv")
    years = df["year"].values

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    fig.subplots_adjust(hspace=0.10)

    # — Panel A: w_pyth —
    ax1.plot(years, df["opt_w_pyth"], "o-", color=BLUE, lw=2, ms=6, label="Walk-forward optimal")
    ax1.axhline(CHAMP_W, color=BLUE, lw=1.2, ls="--", alpha=0.5, label=f"Champion = {CHAMP_W}")
    ax1.fill_between(years, df["opt_w_pyth"] - 0.025, df["opt_w_pyth"] + 0.025,
                     color=BLUE, alpha=0.08)
    ax1.set_ylim(0.55, 0.95)
    ax1.set_yticks([0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
    ax1.set_ylabel("Pythagorean weight (w_pyth)", fontsize=10)
    ax1.legend(fontsize=9, frameon=False)
    ax1.text(0.01, 0.92, "A", transform=ax1.transAxes, fontweight="bold", fontsize=12)
    ax1.annotate("Locked at 0.70\nacross all 16 windows",
                 xy=(2017, 0.70), xytext=(2013.5, 0.63),
                 arrowprops=dict(arrowstyle="->", color=GRAY, lw=1),
                 fontsize=8.5, color="#475569")

    # — Panel B: R —
    ax2.plot(years, df["opt_R"], "s-", color=ORANGE, lw=2, ms=6, label="Walk-forward optimal")
    ax2.axhline(CHAMP_R, color=ORANGE, lw=1.2, ls="--", alpha=0.5, label=f"Champion = {CHAMP_R}")
    ax2.set_ylim(0.55, 1.00)
    ax2.set_yticks([0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95])
    ax2.set_ylabel("Regression factor (R)", fontsize=10)
    ax2.set_xlabel("Prediction year (test window)", fontsize=10)
    ax2.legend(fontsize=9, frameon=False)
    ax2.text(0.01, 0.92, "B", transform=ax2.transAxes, fontweight="bold", fontsize=12)
    ax2.annotate("R drifts upward with\nmore training data;\nOOS cost = −0.005w",
                 xy=(2022, 0.90), xytext=(2013.5, 0.92),
                 arrowprops=dict(arrowstyle="->", color=GRAY, lw=1),
                 fontsize=8.5, color="#475569")

    ax2.set_xticks(years)
    ax2.set_xticklabels([str(y) for y in years], rotation=45, ha="right", fontsize=9)

    fig.suptitle(
        "Figure 1. Walk-forward parameter stability (2010–2025)\n"
        "Each year: train on 2000..(Y−1), find optimal parameters, test on year Y.",
        fontsize=11, y=1.01
    )

    plt.savefig("warps_fig1_walk_forward.pdf", bbox_inches="tight")
    plt.savefig("warps_fig1_walk_forward.png", bbox_inches="tight")
    plt.close()
    print("[OUT] warps_fig1_walk_forward.pdf / .png")


# ─────────────────────────────────────────────
# Figure 2 — MAE basin heatmap
# ─────────────────────────────────────────────

def fig_basin():
    df = pd.read_csv("warps_q3_heatmap.csv")
    pivot = df.pivot(index="w_pyth", columns="R", values="mae")
    pivot = pivot.sort_index(ascending=True)

    champ_mae = pivot.loc[CHAMP_W, CHAMP_R]
    basin_threshold = champ_mae + 0.05

    fig, ax = plt.subplots(figsize=(8, 6))

    w_vals = pivot.index.values
    r_vals = pivot.columns.values
    Z = pivot.values

    # Main heatmap — white (low MAE) to dark blue (high MAE)
    im = ax.imshow(
        Z, origin="lower", aspect="auto",
        extent=[r_vals[0] - 0.025, r_vals[-1] + 0.025,
                w_vals[0] - 0.025, w_vals[-1] + 0.025],
        cmap="YlOrRd", vmin=2.32, vmax=2.90,
        interpolation="bilinear",
    )

    # Basin contour
    R_grid, W_grid = np.meshgrid(r_vals, w_vals)
    cs = ax.contour(R_grid, W_grid, Z, levels=[basin_threshold],
                    colors=[GREEN], linewidths=2, linestyles="--")
    ax.clabel(cs, fmt=f"Basin boundary\n(MAE ≤ {basin_threshold:.3f}w)", fontsize=8.5,
              inline=True, inline_spacing=4)

    # Champion marker
    ax.plot(CHAMP_R, CHAMP_W, "*", color="white", ms=16,
            markeredgecolor="#1e293b", markeredgewidth=1.2, zorder=5)
    ax.annotate(f"Champion\n(w_pyth={CHAMP_W}, R={CHAMP_R})\nMAE={champ_mae:.3f}w",
                xy=(CHAMP_R, CHAMP_W), xytext=(0.60, 0.90),
                arrowprops=dict(arrowstyle="->", color="white", lw=1.2),
                fontsize=8.5, color="white",
                bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", alpha=0.7))

    # Full-sample minimum marker
    min_idx = np.unravel_index(np.argmin(Z), Z.shape)
    best_w, best_r = w_vals[min_idx[0]], r_vals[min_idx[1]]
    best_mae = Z[min_idx]
    ax.plot(best_r, best_w, "D", color="#fbbf24", ms=9,
            markeredgecolor="#1e293b", markeredgewidth=1, zorder=5)
    ax.annotate(f"Full-sample min\n(w_pyth={best_w:.2f}, R={best_r:.2f})\nMAE={best_mae:.3f}w",
                xy=(best_r, best_w), xytext=(0.55, 0.62),
                arrowprops=dict(arrowstyle="->", color="#fbbf24", lw=1.2),
                fontsize=8.5, color="#fbbf24",
                bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", alpha=0.7))

    cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("MAE (wins per team)", fontsize=10)

    ax.set_xlabel("Regression factor (R)", fontsize=10)
    ax.set_ylabel("Pythagorean weight (w_pyth)", fontsize=10)
    ax.set_xticks(r_vals)
    ax.set_yticks(w_vals[::2])

    # Basin stats annotation
    n_basin = (df["in_basin"]).sum()
    n_total = len(df)
    ax.text(0.98, 0.02,
            f"Basin: {n_basin}/{n_total} configs ({round(100*n_basin/n_total)}%) within 0.05w of champion",
            transform=ax.transAxes, fontsize=8.5, ha="right", va="bottom",
            color="white",
            bbox=dict(boxstyle="round,pad=0.3", fc="#1e293b", alpha=0.7))

    ax.set_title(
        "Figure 2. MAE landscape — Pythagorean weight × regression factor\n"
        "Full sample 2000–2025. white star = champion. yellow diamond = full-sample min. "
        "Green dashes = basin boundary.",
        fontsize=10, pad=10
    )

    plt.savefig("warps_fig2_basin.pdf", bbox_inches="tight")
    plt.savefig("warps_fig2_basin.png", bbox_inches="tight")
    plt.close()
    print("[OUT] warps_fig2_basin.pdf / .png")


# ─────────────────────────────────────────────
# Figure 3 — Prediction interval calibration
# ─────────────────────────────────────────────

def fig_calibration():
    df = pd.read_csv("warps_pi_summary.csv")
    full = df[df["sample"] == "Full (2000-2025)"].sort_values("stated_pct")
    val  = df[df["sample"] == "Validation (2022-2025)"].sort_values("stated_pct")

    stated = full["stated_pct"].values
    perfect = stated  # y = x reference

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))
    fig.subplots_adjust(wspace=0.35)

    # — Panel A: calibration curve —
    ax1.plot(perfect, perfect, "--", color=GRAY, lw=1.5, label="Perfect calibration")
    ax1.plot(stated, full["actual_pct"].values, "o-", color=BLUE, lw=2, ms=7,
             label="Full sample (2000–2025)")
    ax1.plot(stated, val["actual_pct"].values, "s-", color=ORANGE, lw=2, ms=7,
             label="Validation (2022–2025)")

    ax1.set_xlim(45, 95)
    ax1.set_ylim(40, 98)
    ax1.set_xticks(stated)
    ax1.set_xticklabels([f"{s}%" for s in stated], fontsize=9)
    ax1.set_xlabel("Stated coverage", fontsize=10)
    ax1.set_ylabel("Actual coverage (%)", fontsize=10)
    ax1.legend(fontsize=8.5, frameon=False)
    ax1.text(0.03, 0.96, "A", transform=ax1.transAxes, fontweight="bold", fontsize=12,
             va="top")
    ax1.annotate("Validation slightly\nunder-covers (2024–2025\nvolatility)",
                 xy=(80, val.loc[val.stated_pct == 80, "actual_pct"].values[0]),
                 xytext=(52, 68),
                 arrowprops=dict(arrowstyle="->", color=GRAY, lw=1),
                 fontsize=8, color="#475569")

    # — Panel B: 80% interval width by projection bin —
    bins_df = pd.read_csv("warps_pi_by_bin.csv")
    bins80 = bins_df[bins_df["stated_pct"] == 80].copy()
    bins80 = bins80[bins80["bin"] != "All"]

    bin_order = ["5–7", "7–9", "9–11"]
    bins80 = bins80[bins80["bin"].isin(bin_order)].copy()
    bins80["bin"] = pd.Categorical(bins80["bin"], categories=bin_order, ordered=True)
    bins80 = bins80.sort_values("bin")

    x = np.arange(len(bins80))
    bars = ax2.bar(x, bins80["width"].values, color=BLUE, alpha=0.75, width=0.5)
    ax2.axhline(bins_df.loc[(bins_df["bin"] == "All") & (bins_df["stated_pct"] == 80),
                             "width"].values[0],
                color=GRAY, lw=1.5, ls="--", label="All-teams average")

    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{b}\n(n={int(n)})"
                          for b, n in zip(bins80["bin"], bins80["n"])], fontsize=9)
    ax2.set_xlabel("Projected wins (bin)", fontsize=10)
    ax2.set_ylabel("80% interval width (wins)", fontsize=10)
    ax2.set_ylim(0, 10)
    ax2.legend(fontsize=8.5, frameon=False)
    ax2.text(0.03, 0.96, "B", transform=ax2.transAxes, fontweight="bold", fontsize=12,
             va="top")
    ax2.annotate("Approximately\nhomoskedastic",
                 xy=(1, bins80["width"].mean()), xytext=(1.35, 5.0),
                 arrowprops=dict(arrowstyle="->", color=GRAY, lw=1),
                 fontsize=8, color="#475569")

    fig.suptitle(
        "Figure 3. Prediction interval calibration\n"
        "A: Stated vs actual coverage (leave-year-out).  "
        "B: 80% interval width by projection bin.",
        fontsize=10, y=1.01,
    )

    plt.savefig("warps_fig3_calibration.pdf", bbox_inches="tight")
    plt.savefig("warps_fig3_calibration.png", bbox_inches="tight")
    plt.close()
    print("[OUT] warps_fig3_calibration.pdf / .png")


if __name__ == "__main__":
    fig_walk_forward()
    fig_basin()
    fig_calibration()
    print("Done. Files: warps_fig1_walk_forward.{pdf,png}  "
          "warps_fig2_basin.{pdf,png}  warps_fig3_calibration.{pdf,png}")
