"""
generate_research_graphs.py
Generates research-quality ML visualization graphs from Pollysync data.
Run from the ml/src directory: python generate_research_graphs.py
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings("ignore")

DATA_DIR   = Path(__file__).resolve().parent.parent / "data"
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── consistent style ──────────────────────────────────────────────────────────
PALETTE = {
    "sunflower": "#F4A620",
    "mustard":   "#6DBF67",
    "cotton":    "#5B8FD6",
    "Low":       "#2ECC71",
    "Medium":    "#F39C12",
    "High":      "#E74C3C",
}
DISTRICTS = ["nashik","pune","solapur","aurangabad","nagpur",
             "amravati","kolhapur","satara","jalgaon","latur"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "grid.linestyle":    "--",
    "figure.dpi":        150,
})

# ── load data ─────────────────────────────────────────────────────────────────
print("Loading data ...")
df_mh   = pd.read_csv(DATA_DIR / "maharashtra_ground_truth.csv")
df_psi  = pd.read_csv(DATA_DIR / "psi_data.csv")
df_flow = pd.read_csv(DATA_DIR / "flowering_data.csv")

print(f"  Maharashtra GT : {len(df_mh)} rows")
print(f"  PSI data       : {len(df_psi)} rows")
print(f"  Flowering data : {len(df_flow)} rows")


# =============================================================================
# FIGURE 1 - Flowering DOY Distribution by Crop & District
# =============================================================================
def fig_flowering_distribution():
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)
    fig.suptitle("Flowering Day-of-Year (DOY) Distribution by Crop - Maharashtra Districts",
                 fontsize=14, fontweight="bold", y=1.02)

    for ax, crop in zip(axes, ["sunflower", "mustard", "cotton"]):
        sub   = df_mh[df_mh["crop"] == crop]
        color = PALETTE[crop]

        data_per_dist = [
            sub[sub["district"] == d]["start_doy"].dropna().values
            for d in DISTRICTS
        ]
        data_per_dist = [d if len(d) > 0 else np.array([0]) for d in data_per_dist]

        parts = ax.violinplot(data_per_dist, positions=range(len(DISTRICTS)),
                              showmedians=True, showextrema=True)
        for pc in parts["bodies"]:
            pc.set_facecolor(color)
            pc.set_alpha(0.55)
        parts["cmedians"].set_color("#333")
        parts["cbars"].set_color(color)
        parts["cmins"].set_color(color)
        parts["cmaxes"].set_color(color)

        ax.set_xticks(range(len(DISTRICTS)))
        ax.set_xticklabels(DISTRICTS, rotation=40, ha="right", fontsize=8)
        ax.set_title(f"{crop.capitalize()}", fontsize=12, color=color, fontweight="bold")
        ax.set_ylabel("Flowering Start DOY" if crop == "sunflower" else "")
        ax.set_xlabel("District")

    plt.tight_layout()
    out = REPORT_DIR / "fig1_flowering_doy_distribution.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 2 - Temperature vs Flowering DOY (scatter + regression)
# =============================================================================
def fig_temp_vs_flowering():
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    fig.suptitle("Temperature (7-day Mean) vs Flowering DOY - Per Crop",
                 fontsize=14, fontweight="bold", y=1.02)

    for ax, crop in zip(axes, ["sunflower", "mustard", "cotton"]):
        sub   = df_mh[df_mh["crop"] == crop].dropna(subset=["temp_7d_mean", "start_doy"])
        color = PALETTE[crop]
        x, y  = sub["temp_7d_mean"], sub["start_doy"]

        sc = ax.scatter(x, y, c=sub["year"], cmap="viridis",
                        alpha=0.7, edgecolors="white", linewidths=0.4, s=50)
        plt.colorbar(sc, ax=ax, label="Year", shrink=0.8)

        z  = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, np.poly1d(z)(xs), color=color, linewidth=2,
                linestyle="--", label="Trend")

        r = np.corrcoef(x, y)[0, 1]
        ax.text(0.05, 0.92, f"r = {r:.3f}", transform=ax.transAxes,
                fontsize=10, color=color, fontweight="bold")

        ax.set_title(f"{crop.capitalize()}", fontsize=12, color=color, fontweight="bold")
        ax.set_xlabel("Temp 7d Mean (deg C)")
        if crop == "sunflower":
            ax.set_ylabel("Flowering Start DOY")

    plt.tight_layout()
    out = REPORT_DIR / "fig2_temp_vs_flowering.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 3 - Model Performance Comparison Bar Chart
# =============================================================================
def fig_model_performance():
    models   = ["Random Forest\n(General V1)", "XGBoost\n(General V1)",
                "Stacking Ensemble\n(General V1)", "Random Forest\n(MH V2)",
                "XGBoost\n(MH V2)"]
    r2_vals  = [0.926, 0.891, 0.938, 0.532, 0.489]
    mae_vals = [15.0,  18.4,  13.1,  37.2,  41.5]
    colors   = ["#5B8FD6","#5B8FD6","#5B8FD6","#F4A620","#F4A620"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Model Performance Comparison - Flowering DOY Prediction",
                 fontsize=14, fontweight="bold")

    x = np.arange(len(models))
    w = 0.55

    bars1 = ax1.bar(x, r2_vals, width=w, color=colors,
                    alpha=0.85, edgecolor="white", linewidth=1.2)
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, fontsize=8)
    ax1.set_ylabel("R2 Score")
    ax1.set_ylim(0, 1.05)
    ax1.axhline(1.0, color="gray", linestyle=":", linewidth=0.8)
    ax1.set_title("R2 Score (higher = better)", fontsize=11)
    for bar, val in zip(bars1, r2_vals):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    bars2 = ax2.bar(x, mae_vals, width=w, color=colors,
                    alpha=0.85, edgecolor="white", linewidth=1.2)
    ax2.set_xticks(x)
    ax2.set_xticklabels(models, fontsize=8)
    ax2.set_ylabel("MAE (days)")
    ax2.set_title("Mean Absolute Error (lower = better)", fontsize=11)
    for bar, val in zip(bars2, mae_vals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.1f}d", ha="center", va="bottom", fontsize=9, fontweight="bold")

    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor="#5B8FD6", label="General V1 Models"),
                       Patch(facecolor="#F4A620", label="Maharashtra V2 Models")]
    ax1.legend(handles=legend_elements, loc="lower right", fontsize=9)

    plt.tight_layout()
    out = REPORT_DIR / "fig3_model_performance_comparison.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 4 - PSI Score Distribution by Risk Level & Crop
# =============================================================================
def fig_psi_distribution():
    mh_psi = df_psi[df_psi["region"] == "Maharashtra"] if "region" in df_psi.columns else df_psi
    crops  = ["sunflower", "mustard", "cotton"]
    risks  = ["Low", "Medium", "High"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    fig.suptitle("Pollination Sync Index (PSI) Distribution by Risk Level - Maharashtra",
                 fontsize=14, fontweight="bold", y=1.02)

    for ax, crop in zip(axes, crops):
        sub = mh_psi[mh_psi["crop"] == crop] if "crop" in mh_psi.columns else mh_psi
        for risk in risks:
            rsub = sub[sub["risk_level"] == risk]["psi_score"].dropna()
            if len(rsub) > 0:
                ax.hist(rsub, bins=25, alpha=0.65,
                        color=PALETTE[risk], label=f"{risk} Risk",
                        edgecolor="white", linewidth=0.5)
        ax.set_title(f"{crop.capitalize()}", fontsize=12,
                     color=PALETTE[crop], fontweight="bold")
        ax.set_xlabel("PSI Score (0-100)")
        if crop == "sunflower":
            ax.set_ylabel("Count")
        ax.legend(fontsize=8)

    plt.tight_layout()
    out = REPORT_DIR / "fig4_psi_distribution.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 5 - NDVI vs PSI Score Scatter (coloured by risk)
# =============================================================================
def fig_ndvi_vs_psi():
    sub = df_psi.dropna(subset=["ndvi", "psi_score", "risk_level"])
    fig, ax = plt.subplots(figsize=(9, 6))

    for risk in ["Low", "Medium", "High"]:
        rs = sub[sub["risk_level"] == risk]
        ax.scatter(rs["ndvi"], rs["psi_score"],
                   c=PALETTE[risk], label=f"{risk} Risk",
                   alpha=0.45, edgecolors="none", s=18)

    x, y = sub["ndvi"], sub["psi_score"]
    z    = np.polyfit(x, y, 1)
    xs   = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, np.poly1d(z)(xs), color="#333", linewidth=1.5,
            linestyle="--", label="Linear Trend")

    r = np.corrcoef(x, y)[0, 1]
    ax.text(0.05, 0.93, f"Pearson r = {r:.3f}", transform=ax.transAxes,
            fontsize=11, fontweight="bold")

    ax.set_xlabel("NDVI (Vegetation Index)", fontsize=12)
    ax.set_ylabel("PSI Score (Pollination Sync Index)", fontsize=12)
    ax.set_title("NDVI vs Pollination Sync Index - All Crops & Regions",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)

    plt.tight_layout()
    out = REPORT_DIR / "fig5_ndvi_vs_psi.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 6 - Year-wise Flowering Trend (2015-2025) per District
# =============================================================================
def fig_yearly_trend():
    crops = ["sunflower", "mustard", "cotton"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle("Year-wise Mean Flowering DOY Trend per District (2015-2025)",
                 fontsize=14, fontweight="bold", y=1.02)

    cmap = plt.cm.get_cmap("tab10", len(DISTRICTS))

    for ax, crop in zip(axes, crops):
        sub = df_mh[df_mh["crop"] == crop]
        for i, dist in enumerate(DISTRICTS):
            dsub = sub[sub["district"] == dist].groupby("year")["start_doy"].mean()
            if len(dsub) > 1:
                ax.plot(dsub.index, dsub.values, marker="o", markersize=4,
                        linewidth=1.5, color=cmap(i), label=dist, alpha=0.85)

        ax.set_title(f"{crop.capitalize()}", fontsize=12,
                     color=PALETTE[crop], fontweight="bold")
        ax.set_xlabel("Year")
        if crop == "sunflower":
            ax.set_ylabel("Mean Flowering Start DOY")
        ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
        ax.tick_params(axis="x", rotation=30)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, title="District", fontsize=8,
               loc="lower center", ncol=10, bbox_to_anchor=(0.5, -0.08))

    plt.tight_layout()
    out = REPORT_DIR / "fig6_yearly_flowering_trend.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# FIGURE 7 - Feature Correlation Heatmap
# =============================================================================
def fig_correlation_heatmap():
    cols  = ["start_doy","temp_7d_mean","humidity","rainfall_7d",
             "wind_speed","ndvi","bee_richness","bee_count",
             "pollen_tree","pollen_grass","pollen_weed","shannon_diversity"]
    valid = [c for c in cols if c in df_mh.columns]
    corr  = df_mh[valid].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = LinearSegmentedColormap.from_list(
        "rg", ["#E74C3C", "#FFFFFF", "#2E86AB"], N=256
    )
    im = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, label="Pearson Correlation")

    ax.set_xticks(range(len(valid)))
    ax.set_yticks(range(len(valid)))
    ax.set_xticklabels(valid, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(valid, fontsize=9)

    for i in range(len(valid)):
        for j in range(len(valid)):
            val = corr.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=7, color="black" if abs(val) < 0.6 else "white")

    ax.set_title("Feature Correlation Matrix - Maharashtra Ground Truth",
                 fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    out = REPORT_DIR / "fig7_feature_correlation_heatmap.png"
    plt.savefig(out, bbox_inches="tight", dpi=180)
    plt.close()
    print(f"  Saved -> {out}")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Pollysync - Research Graph Generator")
    print("="*55)

    print("\n[1/7] Flowering DOY Distribution ...")
    fig_flowering_distribution()

    print("[2/7] Temperature vs Flowering DOY ...")
    fig_temp_vs_flowering()

    print("[3/7] Model Performance Comparison ...")
    fig_model_performance()

    print("[4/7] PSI Score Distribution ...")
    fig_psi_distribution()

    print("[5/7] NDVI vs PSI Score ...")
    fig_ndvi_vs_psi()

    print("[6/7] Year-wise Flowering Trend ...")
    fig_yearly_trend()

    print("[7/7] Feature Correlation Heatmap ...")
    fig_correlation_heatmap()

    print("\n" + "="*55)
    print(f"  All 7 figures saved to:")
    print(f"  {REPORT_DIR}")
    print("="*55 + "\n")
