
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================

INPUT_CSV = "rq1_results.csv"
OUTPUT_DIR = Path("figures")
OUTPUT_DIR.mkdir(exist_ok=True)

# ==========================================
# LOAD DATA
# ==========================================

df = pd.read_csv(INPUT_CSV)

names = {
    "ECDSA-P256": "ECDSA-P256",
    "ml_dsa_44": "ML-DSA-44",
    "ml_dsa_65": "ML-DSA-65",
    "ml_dsa_87": "ML-DSA-87",
    "slh_dsa_sha2_128s": "SLH-DSA-128s"
}

df["label"] = df["algorithm"].replace(names)

# ==========================================
# CREATE FIGURE
# ==========================================

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

fig, ax = plt.subplots(figsize=(7.2, 3.4))

y = np.arange(len(df))
bar_height = 0.34

ax.barh(
    y - bar_height / 2,
    df["sign_us"],
    height=bar_height,
    label="Signing",
    color="#3278BD"
)

ax.barh(
    y + bar_height / 2,
    df["verify_us"],
    height=bar_height,
    label="Verification",
    color="#E66B36"
)

ax.set_xscale("log")

ax.set_yticks(y)
ax.set_yticklabels(df["label"])
ax.invert_yaxis()

ax.set_xlabel("Execution time (microseconds, log scale)")
ax.set_xlim(10, 1_000_000)

ax.grid(
    axis="x",
    linestyle="--",
    alpha=0.3
)
ax.set_axisbelow(True)

ax.legend(
    loc="upper right",
    frameon=False,
    ncol=2
)

# ==========================================
# VALUE LABELS
# ==========================================

for i, row in df.iterrows():
    ax.text(
        row["sign_us"] * 1.12,
        i - bar_height / 2,
        f'{row["sign_us"]:,.0f}',
        va="center",
        fontsize=7
    )

    ax.text(
        row["verify_us"] * 1.12,
        i + bar_height / 2,
        f'{row["verify_us"]:,.1f}',
        va="center",
        fontsize=7
    )

plt.tight_layout()

# ==========================================
# EXPORT FOR IEEE PAPER
# ==========================================

fig.savefig(
    OUTPUT_DIR / "RQ1_Figure1.pdf",
    bbox_inches="tight"
)

fig.savefig(
    OUTPUT_DIR / "RQ1_Figure1.png",
    dpi=600,
    bbox_inches="tight"
)

plt.show()