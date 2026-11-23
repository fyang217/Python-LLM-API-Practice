"""Build a Word report directly from validated Python results."""

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


def _format(value):
    return "—" if value is None else f"{value:.6f}".rstrip("0").rstrip(".")


def _add_table(document, headers, rows):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Shading Accent 1"
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = value
    for values in rows:
        for cell, value in zip(table.add_row().cells, values):
            cell.text = str(value)


def create_report(quality, abundance, comparison, figures, path, simulated):
    """Write a DOCX from quality, abundance, comparison and figure outputs."""
    document = Document()
    normal = document.styles["Normal"]
    normal.font.size = Pt(10.5)
    fonts = normal.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    document.add_heading("ARG 丰度描述性分析报告", 0)
    document.add_paragraph("模拟数据演示" if simulated else "用户提供的数据", style="Subtitle")
    document.add_paragraph(
        f"数据文件为 {abundance['file']}，"
        f"含 {abundance['arg_record_count']} 条 ARG 记录和 {abundance['sample_count']} 个样本。"
        "本次任务为逐样本求和，并汇总各区域的 iDNA 和 eDNA 丰度。"
    )
    document.add_heading("数据质量", level=1)
    labels = {
        "missing_arg_names": "缺失 ARG 名称", "invalid_arg_names": "无效 ARG 名称",
        "missing_values": "缺失丰度", "non_numeric_values": "非数值丰度",
        "non_finite_values": "非有限丰度", "negative_values": "负值",
        "duplicate_arg_names": "完全重复名称", "case_conflicts": "大小写冲突组",
    }
    document.add_paragraph("；".join(f"{label} {len(quality['quality'][key])}" for key, label in labels.items()) + "。")
    for conflict in quality["quality"]["case_conflicts"]:
        variants = [f"{item['name']}（行 {', '.join(map(str, item['rows']))}）" for item in conflict["variants"]]
        document.add_paragraph(" 与 ".join(variants) + " 分别计入求和。")

    document.add_heading("分组结果", level=1)
    _add_table(document, ("区域", "iDNA n", "iDNA 均值", "eDNA n", "eDNA 均值", "均值差 i−e"), (
        (row["region"], row["iDNA"]["n"], _format(row["iDNA"]["mean"]),
         row["eDNA"]["n"], _format(row["eDNA"]["mean"]), _format(row["mean_difference_i_minus_e"]))
        for row in comparison["comparisons"]
    ))
    document.add_heading("方法与解释", level=1)
    document.add_paragraph(
        "逐样本加总表内 ARG 数值，组内按样本等权求均值。均值差为 iDNA 均值减 eDNA 均值。"
        "正值表示本批数据中 iDNA 组均值较大。样本标准差以 n−1 为分母，仅在组内样本数至少为 2 时计算。"
        "本报告仅作描述性比较，未计算配对差值或显著性检验。"
    )
    document.add_paragraph(
        "TPM 总和依赖上游归一化分母及注释口径，无法换算成绝对基因拷贝数。"
        + ("此处数据为人工构造，不能用于推断环境样品中的实际差异。" if simulated
           else "解释组间差异前应核实归一化口径和采样设计。")
    )

    document.add_page_break()
    document.add_heading("逐样本 ARG 丰度总和", level=1)
    _add_table(document, ("样本", "区域", "DNA 类型", "ARG 数值总和"), (
        (row["name"], row["region"], row["dna_type"], _format(row["arg_tpm_sum"]))
        for row in abundance["samples"]
    ))
    document.add_picture(str(figures[0]), width=Inches(6))

    document.add_page_break()
    document.add_heading("分布与区域比较", level=1)
    document.add_picture(str(figures[1]), width=Inches(6))
    document.add_picture(str(figures[2]), width=Inches(6))
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path
