"""Descriptive comparisons using samples as the observational unit."""

from statistics import stdev

from arg_analysis_tools import calculate_arg_abundance


def compare_dna_types(abundance):
    """Return unpaired group summaries and signed differences in sample means."""
    samples = abundance["samples"]
    groups = [
        ("ALL", samples, abundance["by_dna_type"]),
        *(
            (region, [sample for sample in samples if sample["region"] == region],
             summary["by_dna_type"])
            for region, summary in abundance["by_region"].items()
        ),
    ]
    comparisons = []
    for region, subset, summary in groups:
        stats = {}
        for dna_type, descriptive in summary.items():
            values = [row["arg_tpm_sum"] for row in subset if row["dna_type"] == dna_type]
            stats[dna_type] = {
                **descriptive,
                "sample_sd": stdev(values) if len(values) >= 2 else None,
            }
        i_mean, e_mean = stats["iDNA"]["mean"], stats["eDNA"]["mean"]
        comparisons.append({
            "region": region,
            **stats,
            "mean_difference_i_minus_e": i_mean - e_mean if i_mean is not None and e_mean is not None else None,
        })
    return {
        "method": "Unpaired descriptive comparison of sample-level ARG sums",
        "difference_definition": "Arithmetic mean(iDNA) minus arithmetic mean(eDNA)",
        "conditions": [
            "Valid non-negative abundance values and consistent upstream normalization are required.",
            "Each column contributes one sample total; samples receive equal weight.",
            "Sample SD uses n - 1 and is omitted when n < 2.",
            "No paired differences, p-values, or inference about a population.",
        ],
        "comparisons": comparisons,
    }
