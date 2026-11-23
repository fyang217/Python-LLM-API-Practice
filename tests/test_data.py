import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from arg_analysis_tools import calculate_arg_abundance, read_arg_excel
from tests.fixtures import DATA, DEMO, EXPECTED


class DataTests(unittest.TestCase):
    def test_default_input_matches_explicit_demo_workbook(self):
        self.assertEqual(read_arg_excel(), read_arg_excel(DEMO))
        self.assertEqual(calculate_arg_abundance(), calculate_arg_abundance(DEMO))

    def test_excel_and_csv_read(self):
        excel = read_arg_excel(DEMO)
        csv = read_arg_excel(DATA / "demo_arg_data.csv")
        self.assertEqual(excel["worksheet"], "Simulated_ARG")
        self.assertIsNone(csv["worksheet"])
        self.assertEqual(excel["samples"], csv["samples"])
        self.assertEqual(excel["data_rows"], 4)

    def test_sample_labels(self):
        result = read_arg_excel(DEMO)
        self.assertEqual(result["sample_count"], 16)
        self.assertEqual(result["sample_counts_by_region"], {
            "LF": {"iDNA": 2, "eDNA": 2}, "IZ": {"iDNA": 2, "eDNA": 2},
            "RW": {"iDNA": 2, "eDNA": 2}, "AZ": {"iDNA": 2, "eDNA": 2},
        })
        self.assertEqual(result["samples"][2]["name"], "E_LF1")
        self.assertEqual(result["samples"][2]["dna_type"], "eDNA")
        self.assertEqual(result["samples"][2]["region"], "LF")

    def test_abundance_against_manual_totals_including_zero(self):
        for source in (DEMO, DATA / "demo_arg_data.csv"):
            with self.subTest(source=source.name):
                result = calculate_arg_abundance(source)
                self.assertEqual(result["arg_record_count"], EXPECTED["arg_record_count"])
                self.assertEqual({row["name"]: row["arg_tpm_sum"] for row in result["samples"]},
                                 EXPECTED["sample_totals"])
                self.assertEqual(result["case_conflicts"][0]["variants"], [
                    {"name": "beta-lactam_ampC", "rows": [4]},
                    {"name": "beta-lactam_AmpC", "rows": [5]},
                ])

    def test_anomalies_and_blocked_sum(self):
        source = DATA / "anomalies.csv"
        quality = read_arg_excel(source)["quality"]
        self.assertEqual(quality["missing_values"], [{"row": 2, "sample": "E_LF1"}])
        self.assertEqual(quality["negative_values"], [{"row": 3, "sample": "I_LF1", "value": -2}])
        self.assertEqual(quality["non_numeric_values"], [{"row": 3, "sample": "E_LF1", "value": "text"}])
        self.assertEqual(quality["non_finite_values"], [{"row": 4, "sample": "I_LF1", "value": "NaN"}])
        self.assertEqual(quality["missing_arg_names"], [5])
        self.assertEqual(quality["duplicate_arg_names"], [{"name": "demo_ARG_1", "rows": [2, 3]}])
        with self.assertRaisesRegex(ValueError, "missing_values"):
            calculate_arg_abundance(source)

    def test_excel_errors_and_text_numbers(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "errors.xlsx"
            workbook = Workbook()
            workbook.active.append(["ARG", "I_LF1", "E_LF1"])
            workbook.active.append(["demo_ARG", "#DIV/0!", "2"])
            workbook.save(source)
            quality = read_arg_excel(source)["quality"]
            self.assertEqual([item["value"] for item in quality["non_numeric_values"]], ["#DIV/0!", "2"])

    def test_wrong_input(self):
        with self.assertRaisesRegex(ValueError, "只支持"):
            read_arg_excel(DATA / "expected.json")
        with self.assertRaises(FileNotFoundError):
            read_arg_excel(DATA / "absent.xlsx")
