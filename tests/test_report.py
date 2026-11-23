import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from PIL import Image

from agent.agent import local_request
from agent.workflow import AnalysisRun, run_workflow
from tests.fixtures import DEMO, EXPECTED


class ReportTests(unittest.TestCase):
    def test_report_and_figure_outputs_match_independent_answers(self):
        with TemporaryDirectory() as folder:
            output = Path(folder)
            run = AnalysisRun(DEMO, output, True, log=lambda _: None)
            status = run_workflow(local_request(), [{"role": "user", "content": "demo"}], run)
            self.assertEqual(status["tool_calls"], 5)
            report = Document(output / "reports" / "arg_report.docx")
            self.assertIn("模拟数据", "\n".join(p.text for p in report.paragraphs))
            self.assertEqual(len(report.inline_shapes), 3)
            grouped, samples = report.tables
            self.assertEqual({
                row.cells[0].text: [float(row.cells[i].text) for i in (2, 4, 5)]
                for row in grouped.rows[1:]
            }, EXPECTED["group_means"])
            self.assertEqual({
                row.cells[0].text: float(row.cells[3].text) for row in samples.rows[1:]
            }, EXPECTED["sample_totals"])
            for name in ("sample_totals.png", "dna_boxplot.png", "regional_means.png"):
                with Image.open(output / "figures" / name) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertGreaterEqual(image.width, 2000)
                    self.assertAlmostEqual(image.info["dpi"][0], 300, places=0)
