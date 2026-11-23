import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arg_analysis_tools import calculate_arg_abundance
from tests.fixtures import DEMO, EXPECTED
from tools.statistics_tools import compare_dna_types


class StatisticsTests(unittest.TestCase):
    def test_group_means_against_manual_results(self):
        rows = compare_dna_types(calculate_arg_abundance(DEMO))["comparisons"]
        self.assertEqual({row["region"]: [row["iDNA"]["mean"], row["eDNA"]["mean"],
                                         row["mean_difference_i_minus_e"]] for row in rows},
                         EXPECTED["group_means"])
        self.assertEqual(rows[1]["iDNA"]["n"], 2)
        self.assertAlmostEqual(rows[1]["iDNA"]["sample_sd"], 2.8284271247461903)

    def test_missing_group_has_no_difference_or_sd(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "one_group.csv"
            source.write_text("ARG,I_LF1\ndemo_ARG,0\n", encoding="utf-8")
            overall = compare_dna_types(calculate_arg_abundance(source))["comparisons"][0]
            self.assertEqual(overall["iDNA"]["mean"], 0)
            self.assertIsNone(overall["iDNA"]["sample_sd"])
            self.assertIsNone(overall["eDNA"]["mean"])
            self.assertIsNone(overall["mean_difference_i_minus_e"])
