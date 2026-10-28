
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.lines import Line2D

# ==========================================
# CONFIGURATION
# ==========================================

INPUT_CSV = "results/rq3_results.csv"

OUTPUT_DIR = Path("figures")
OUTPUT_DIR.mkdir(exist_ok=True)

ALGORITHMS = [
    "ECDSA-P256",
    "ml_dsa_44",
    "slh_dsa_sha2_128s"
]

DATABASES = [
    "postgresql",
    "mysql",
    "mongodb"
]

CLIENT_COUNTS = [1, 5, 10]

ALGORITHM_NAMES = {
    "ECDSA-P256": "ECDSA-P256",
    "ml_dsa_44": "ML-DSA-44",
    "slh_dsa_sha2_128s": "SLH-DSA-128s"
}

DATABASE_NAMES = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB"
}

ALGORITHM_SHORT = {
    "ECDSA-P256": "ECDSA",
    "ml_dsa_44": "ML",
    "slh_dsa_sha2_128s": "SLH"
}

DATABASE_SHORT = {
    "postgresql": "PG",
    "mysql": "MySQL",
    "mongodb": "Mongo"
}

COLORS = {
    "ECDSA-P256": "#3278BD",
    "ml_dsa_44": "#239E77",
    "slh_dsa_sha2_128s": "#E66B36"
}

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

# ==========================================
# LOAD CSV
# ==========================================

df = pd.read_csv(INPUT_CSV)

# Check required columns
required_columns = [
    "algorithm",
    "database",
    "mode",
    "clients",
    "throughput_ops_s",
    "mean_latency_ms",
    "p95_latency_ms"
]

missing = [
    col for col in required_columns
    if col not in df.columns
]

if missing:
    raise ValueError(
        f"Missing CSV columns: {missing}\n"
        f"Available columns: {list(df.columns)}"
    )

# Normalize text fields
for col in ["algorithm", "database", "mode"]:
    df[col] = df[col].astype(str).str.strip()

df["database"] = df["database"].str.lower()
df["mode"] = df["mode"].str.lower()
df["clients"] = pd.to_numeric(df["clients"])

# Validate expected configurations
expected = pd.MultiIndex.from_product(
    [DATABASES, ALGORITHMS, CLIENT_COUNTS, ["fresh", "reuse"]],
    names=["database", "algorithm", "clients", "mode"]
)

actual = pd.MultiIndex.from_frame(
    df[["database", "algorithm", "clients", "mode"]]
)

missing_configs = expected.difference(actual)

if len(missing_configs) > 0:
    raise ValueError(
        "Missing RQ3 configurations:\n"
        + str(missing_configs.tolist())
    )

# ==========================================
# FIGURE 3:
# THROUGHPUT VS CONCURRENT CLIENTS
# ==========================================

fig, axes = plt.subplots(
    1, 3,
    figsize=(10.5, 3.6),
    sharey=True
)

for ax, database in zip(axes, DATABASES):

    for algorithm in ALGORITHMS:

        for mode in ["fresh", "reuse"]:

            data = df[
                (df["database"] == database) &
                (df["algorithm"] == algorithm) &
                (df["mode"] == mode)
            ].sort_values("clients")

            ax.plot(
                data["clients"],
                data["throughput_ops_s"],
                color=COLORS[algorithm],
                linestyle="-" if mode == "reuse" else "--",
                marker="o" if mode == "reuse" else "s",
                linewidth=1.7,
                markersize=4.5,
                label=f"{ALGORITHM_NAMES[algorithm]} ({mode})"
            )

    ax.set_title(
        DATABASE_NAMES[database],
        fontweight="bold"
    )

    ax.set_xlabel("Concurrent clients")
    ax.set_xticks(CLIENT_COUNTS)
    ax.set_yscale("log")

    ax.grid(
        axis="both",
        linestyle="--",
        alpha=0.3
    )

    ax.set_axisbelow(True)

axes[0].set_ylabel(
    "Throughput (operations/s, log scale)"
)

# Legend: algorithm = color, mode = line style
legend_handles = []

for algorithm in ALGORITHMS:
    legend_handles.append(
        Line2D(
            [0], [0],
            color=COLORS[algorithm],
            linewidth=2,
            label=ALGORITHM_NAMES[algorithm]
        )
    )


legend_handles.extend([
    Line2D(
        [0], [0],
        color="black",
        linestyle=(0, (2, 2)),
        marker="s",
        markersize=6,
        linewidth=1.8,
        label="Fresh authentication"
    ),
    Line2D(
        [0], [0],
        color="black",
        linestyle="-",
        marker="o",
        markersize=6,
        linewidth=1.8,
        label="Session reuse"
    )
])

fig.legend(
    handles=legend_handles,
    loc="lower center",
    bbox_to_anchor=(0.5, -0.08),
    ncol=5,
    frameon=False,
    handlelength=4.5,
    handletextpad=0.6,
    numpoints=1
)

fig.tight_layout(rect=[0, 0.13, 1, 1])

fig.savefig(
    OUTPUT_DIR / "RQ3_Figure3.pdf",
    bbox_inches="tight"
)

fig.savefig(
    OUTPUT_DIR / "RQ3_Figure3.png",
    dpi=600,
    bbox_inches="tight"
)

plt.close(fig)

# ==========================================
# FIGURE 4:
# MEAN VS P95 LATENCY REDUCTION (DUMBBELL)
# ==========================================

wide = df.pivot(
    index=["database", "algorithm", "clients"],
    columns="mode",
    values=["mean_latency_ms", "p95_latency_ms"]
)

reductions = pd.DataFrame({
    "mean": 100 * (
        1 - wide[("mean_latency_ms", "reuse")] /
            wide[("mean_latency_ms", "fresh")]
    ),
    "p95": 100 * (
        1 - wide[("p95_latency_ms", "reuse")] /
            wide[("p95_latency_ms", "fresh")]
    )
}).reset_index()

# Build row ordering:
# PostgreSQL ECDSA, ML, SLH;
# MySQL ECDSA, ML, SLH;
# MongoDB ECDSA, ML, SLH.
row_order = [
    (db, alg)
    for db in DATABASES
    for alg in ALGORITHMS
]

row_labels = [
    f"{DATABASE_SHORT[db]} · {ALGORITHM_SHORT[alg]}"
    for db, alg in row_order
]

fig, axes = plt.subplots(
    1, 3,
    figsize=(10.5, 4.2),
    sharex=True,
    sharey=True
)

for ax, clients in zip(axes, CLIENT_COUNTS):

    data = reductions[
        reductions["clients"] == clients
    ].copy()

    data = data.set_index(
        ["database", "algorithm"]
    ).loc[row_order]

    y = np.arange(len(row_order))

    # Gray connectors between mean and p95 dots
    for i, (_, row) in enumerate(data.iterrows()):
        ax.plot(
            [row["mean"], row["p95"]],
            [i, i],
            color="#DEDEDE",
            linewidth=3.5,
            solid_capstyle="round",
            zorder=1
        )

    # Mean latency reduction (blue)
    ax.scatter(
        data["mean"],
        y,
        color="#3278BD",
        s=30,
        label="Mean latency",
        zorder=3
    )

    # p95 latency reduction (orange)
    ax.scatter(
        data["p95"],
        y,
        color="#E66B36",
        s=30,
        label="p95 latency",
        zorder=3
    )

    ax.axvline(
        0,
        color="gray",
        linewidth=0.8
    )

    ax.set_title(
        f"{clients} client" if clients == 1
        else f"{clients} clients",
        fontweight="bold"
    )

    ax.set_xlabel("Reduction vs fresh (%)")

    ax.set_xlim(-60, 105)
    ax.set_xticks([-50, 0, 50, 100])

    ax.set_yticks(y)
    ax.set_yticklabels(
        row_labels,
        fontsize=8
    )

    ax.invert_yaxis()

    ax.grid(
        axis="x",
        linestyle="-",
        alpha=0.2
    )

    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)

# Shared legend
handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles,
    labels,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.04),
    ncol=2,
    frameon=False
)

fig.tight_layout(rect=[0, 0, 1, 0.94])

fig.savefig(
    OUTPUT_DIR / "RQ3_Figure4.pdf",
    bbox_inches="tight"
)

fig.savefig(
    OUTPUT_DIR / "RQ3_Figure4.png",
    dpi=600,
    bbox_inches="tight"
)

plt.close(fig)

print("RQ3 figures generated successfully!")
print(f"Saved to: {OUTPUT_DIR.resolve()}")