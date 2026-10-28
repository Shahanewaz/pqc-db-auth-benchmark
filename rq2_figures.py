import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================

INPUT_CSV = "results/rq2_summary.csv"
OUTPUT_DIR = Path("figures")
OUTPUT_DIR.mkdir(exist_ok=True)

ALGORITHMS = [
    "ECDSA-P256",
    "ml_dsa_44",
    "ml_dsa_65",
    "ml_dsa_87",
    "slh_dsa_sha2_128s"
]

LABELS = [
    "ECDSA",
    "ML-44",
    "ML-65",
    "ML-87",
    "SLH-128s"
]

DATABASES = [
    "postgresql",
    "mysql",
    "mongodb"
]

# ==========================================
# LOAD DATA
# ==========================================

df = pd.read_csv(INPUT_CSV)

# ==========================================
# CREATE FIGURE
# ==========================================

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

fig, axes = plt.subplots(
    1, 3,
    figsize=(10.5, 3.5),
    sharey=True
)

colors = {
    "connect": "#3278BD",
    "auth": "#E66B36",
    "query": "#239E77"
}

for ax, database in zip(axes, DATABASES):

    data = (
        df[df["database"] == database]
        .set_index("algorithm")
        .loc[ALGORITHMS]
    )

    x = np.arange(len(ALGORITHMS))

    connect = data["connect_ms"].values
    auth = data["auth_ms"].values
    query = data["query_ms"].values

    # Stacked bars
    ax.bar(
        x, connect,
        label="DB Connection",
        color=colors["connect"]
    )

    ax.bar(
        x, auth,
        bottom=connect,
        label="Signature Authentication",
        color=colors["auth"]
    )

    ax.bar(
        x, query,
        bottom=connect + auth,
        label="Query",
        color=colors["query"]
    )

    # Authentication share
    for i in range(len(x)):
        share = 100 * auth[i] / (auth[i] + connect[i])
        total = connect[i] + auth[i] + query[i]

        ax.text(
            i, total + 3,
            f"{share:.0f}%",
            ha="center",
            fontsize=7
        )

    db_names = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB"
    }

    ax.set_title(db_names[database], fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS, rotation=45, ha="right")
    ax.set_ylim(0, 255)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)

axes[0].set_ylabel("Latency (ms)")

# Shared legend
handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles, labels,
    loc="upper center",
    ncol=3,
    frameon=False,
    bbox_to_anchor=(0.5, 1.08)
)

plt.tight_layout(rect=[0, 0, 1, 0.95])

# ==========================================
# EXPORT FIGURE
# ==========================================

fig.savefig(
    OUTPUT_DIR / "RQ2_Figure2.pdf",
    bbox_inches="tight"
)

fig.savefig(
    OUTPUT_DIR / "RQ2_Figure2.png",
    dpi=600,
    bbox_inches="tight"
)

plt.show()