"""Create reproducible PNG figures from Python analysis results."""

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Patch


COLORS = {"iDNA": "#17649A", "eDNA": "#BD5A22"}


def create_figures(abundance, comparison, directory, simulated):
    """Save three 300 dpi figures and return their paths in display order."""
    directory.mkdir(parents=True, exist_ok=True)
    samples = abundance["samples"]
    source = "Simulated data" if simulated else "User supplied data"
    paths = []

    def save(fig, ax, title, filename):
        ax.set_title(f"{title}\n{source}", loc="left", fontweight="bold")
        ax.set_ylabel("ARG abundance sum (reported TPM)")
        ax.grid(axis="y", alpha=0.23)
        ax.set_axisbelow(True)
        path = directory / filename
        try:
            fig.savefig(path, dpi=300)
        finally:
            plt.close(fig)
        paths.append(path)

    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    ax.bar([sample["name"] for sample in samples], [sample["arg_tpm_sum"] for sample in samples],
           color=[COLORS[sample["dna_type"]] for sample in samples])
    ax.tick_params(axis="x", labelrotation=55)
    ax.set_xlabel("Sample")
    ax.legend(handles=[Patch(color=color, label=label) for label, color in COLORS.items()])
    save(fig, ax, "ARG abundance by sample", "sample_totals.png")

    fig, ax = plt.subplots(figsize=(7, 3.6), layout="constrained")
    for index, (label, color) in enumerate(COLORS.items(), start=1):
        values = [sample["arg_tpm_sum"] for sample in samples if sample["dna_type"] == label]
        if values:
            ax.boxplot(values, positions=[index], widths=0.4, patch_artist=True,
                       boxprops={"facecolor": color, "alpha": 0.35})
            ax.scatter([index] * len(values), values, color=color, s=12, zorder=3)
    ax.set_xticks([1, 2], list(COLORS))
    ax.set_xlim(0.5, 2.5)
    ax.set_xlabel("DNA type")
    save(fig, ax, "Distribution of sample ARG totals", "dna_boxplot.png")

    fig, ax = plt.subplots(figsize=(8, 3.6), layout="constrained")
    regional = comparison["comparisons"][1:]
    for label, color in COLORS.items():
        offset = -0.18 if label == "iDNA" else 0.18
        values = [(i + offset, row[label]["mean"]) for i, row in enumerate(regional)
                  if row[label]["mean"] is not None]
        ax.bar([x for x, _ in values], [y for _, y in values], width=0.34, color=color, label=label)
    ax.set_xticks(range(len(regional)), [row["region"] for row in regional])
    ax.set_xlabel("Region")
    ax.legend()
    save(fig, ax, "Mean sample ARG total by region and DNA type", "regional_means.png")
    return paths
