
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

ALGORITHM_NAMES = {
    "ECDSA-P256": "ECDSA-P256",
    "ml_dsa_44": "ML-DSA-44",
    "ml_dsa_65": "ML-DSA-65",
    "ml_dsa_87": "ML-DSA-87",
    "slh_dsa_sha2_128s": "SLH-DSA-128s"
}

DATABASES = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB"
}

COLORS = {
    "ECDSA-P256": "#3278BD",
    "ml_dsa_44": "#239E77",
    "ml_dsa_65": "#9B59B6",
    "ml_dsa_87": "#E66B36",
    "slh_dsa_sha2_128s": "#444444"
}

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

# ==========================================
# LOAD DATA
# ==========================================

df = pd.read_csv(INPUT_CSV)

# Accept either flat or median-suffixed columns
df = df.rename(columns={
    "auth_ms_median": "auth_ms",
    "connect_ms_median": "connect_ms",
    "query_ms_median": "query_ms",
    "median_auth_ms": "auth_ms",
    "median_connect_ms": "connect_ms",
    "median_query_ms": "query_ms"
})

required = [
    "algorithm", "database",
    "auth_ms", "connect_ms", "query_ms"
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(
        f"Missing columns: {missing}\n"
        f"Available columns: {list(df.columns)}"
    )

df["algorithm"] = df["algorithm"].astype(str).str.strip()
df["database"] = (
    df["database"].astype(str).str.strip().str.lower()
)

# ==========================================
# AUTHENTICATION AMORTIZATION MODEL
# ==========================================

# Logarithmically spaced query counts, 1 to 100,000
queries = np.logspace(0, 5, 500)

def auth_share(auth, connect, query, k):
    return 100 * auth / (connect + auth + k * query)

# ==========================================
# FIGURE 5: AUTHENTICATION SHARE VS QUERIES
# ==========================================

fig, axes = plt.subplots(
    1, 3,
    figsize=(10.5, 3.6),
    sharex=True,
    sharey=True
)

for ax, (database, db_name) in zip(
    axes, DATABASES.items()
):

    for algorithm in ALGORITHMS:

        data = df[
            (df["database"] == database) &
            (df["algorithm"] == algorithm)
        ]

        if len(data) != 1:
            raise ValueError(
                f"Expected one row for {database}, "
                f"{algorithm}; found {len(data)}"
            )

        row = data.iloc[0]

        A = row["auth_ms"]
        C = row["connect_ms"]
        Q = row["query_ms"]

        share = auth_share(A, C, Q, queries)

        ax.plot(
            queries,
            share,
            color=COLORS[algorithm],
            linewidth=1.8,
            label=ALGORITHM_NAMES[algorithm]
        )

    # 10% authentication threshold
    ax.axhline(
        10,
        color="black",
        linestyle=(0, (3, 3)),
        linewidth=1.2,
        label="10% threshold"
    )

    ax.set_title(db_name, fontweight="bold")
    ax.set_xlabel("Queries per authenticated session")
    ax.set_xscale("log")
    ax.set_xlim(1, 100000)
    ax.set_ylim(0, 100)

    ax.grid(
        True,
        linestyle="--",
        alpha=0.25
    )
    ax.set_axisbelow(True)

axes[0].set_ylabel(
    "Authentication share of session time (%)"
)

# ==========================================
# SHARED LEGEND
# ==========================================

handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles,
    labels,
    loc="lower center",
    bbox_to_anchor=(0.5, -0.08),
    ncol=3,
    frameon=False,
    handlelength=3
)

fig.tight_layout(rect=[0, 0.13, 1, 1])

# ==========================================
# SAVE FIGURE
# ==========================================

fig.savefig(
    OUTPUT_DIR / "RQ4_Figure5.pdf",
    bbox_inches="tight"
)

fig.savefig(
    OUTPUT_DIR / "RQ4_Figure5.png",
    dpi=600,
    bbox_inches="tight"
)

plt.show()

print("RQ4 Figure 5 generated successfully!")