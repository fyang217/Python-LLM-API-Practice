import re
from math import fsum, isfinite
from numbers import Real
from pathlib import Path
from statistics import mean, median

import pandas as pd


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "tpm.xlsx"
SAMPLE_PATTERN = re.compile(r"(I|E)_(LF|IZ|RW|AZ)([0-9]+)")


def _is_blank(value):
    return bool(pd.isna(value)) or isinstance(value, str) and not value.strip()


def read_arg_excel(path=DEFAULT_PATH, sheet_name=None):
    """Read an ARG worksheet and return a JSON-serializable quality report."""
    report, _ = _read_arg_worksheet(path, sheet_name)
    return report


def _read_arg_worksheet(path, sheet_name):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        if sheet_name is not None:
            raise ValueError("CSV 文件不支持工作表参数。")
        table = pd.read_csv(path, header=None, keep_default_na=False, skip_blank_lines=False)
        excel_errors = {}
    elif path.suffix.lower() == ".xlsx":
        table, sheet_name, excel_errors = _read_excel_table(path, sheet_name)
    else:
        raise ValueError("只支持 .xlsx 和 .csv 文件。")

    return _inspect_table(path, sheet_name, table, excel_errors)


def _read_excel_table(path, sheet_name):
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        sheets = workbook.sheet_names
        if sheet_name is None:
            if len(sheets) != 1:
                raise ValueError("工作簿有多个工作表，请通过 sheet_name 指定数据表。")
            sheet_name = sheets[0]
        worksheet = workbook.book[sheet_name]
        table = pd.read_excel(workbook, sheet_name=sheet_name, header=None, dtype=object, keep_default_na=False)
        excel_errors = {
            (cell.row, cell.column): cell.value
            for row in worksheet.iter_rows(max_row=len(table), max_col=len(table.columns))
            for cell in row
            if cell.data_type == "e"
        } if not table.empty else {}
    return table, sheet_name, excel_errors


def _inspect_table(path, sheet_name, table, excel_errors):
    if table.empty:
        raise ValueError("工作表为空。")
    headers = table.iloc[0].tolist()
    arg_columns = [
        index for index, name in enumerate(headers)
        if isinstance(name, str) and name.strip().casefold() in {"arg", "arg name", "arg_name"}
    ]
    if len(arg_columns) != 1:
        raise ValueError("需要且只能有一个 ARG 名称列（ARG、ARG name 或 ARG_name）。")
    arg_column = arg_columns[0]

    samples = []
    unrecognized_columns = []
    sample_names = set()
    for index, name in enumerate(headers):
        if index == arg_column:
            continue
        match = SAMPLE_PATTERN.fullmatch(name) if isinstance(name, str) else None
        if match is None:
            unrecognized_columns.append({"excel_column": index + 1, "header": str(name)})
            continue
        if name in sample_names:
            raise ValueError(f"样本列名重复：{name}")
        sample_names.add(name)
        prefix, region, number = match.groups()
        samples.append({
            "name": name,
            "excel_column": index + 1,
            "dna_type": "iDNA" if prefix == "I" else "eDNA",
            "region": region,
            "sample_id": region + number,
        })
    if not samples:
        raise ValueError("未找到符合 I_/E_、区域及数字编号规则的样本列。")

    quality = {
        "blank_rows": [],
        "missing_arg_names": [],
        "invalid_arg_names": [],
        "missing_values": [],
        "non_numeric_values": [],
        "non_finite_values": [],
        "negative_values": [],
    }
    exact_names = {}
    folded_names = {}
    data_rows = 0
    for excel_row, row in enumerate(table.iloc[1:].itertuples(index=False, name=None), start=2):
        row = tuple(excel_errors.get((excel_row, column), value)
                    for column, value in enumerate(row, start=1))
        if all(_is_blank(value) for value in row):
            quality["blank_rows"].append(excel_row)
            continue
        data_rows += 1
        arg_name = row[arg_column]
        if _is_blank(arg_name):
            quality["missing_arg_names"].append(excel_row)
        elif not isinstance(arg_name, str):
            quality["invalid_arg_names"].append({"row": excel_row, "value": str(arg_name)})
        else:
            exact_names.setdefault(arg_name, []).append(excel_row)
            folded_names.setdefault(arg_name.casefold(), {}).setdefault(arg_name, []).append(excel_row)

        for sample in samples:
            value = row[sample["excel_column"] - 1]
            location = {"row": excel_row, "sample": sample["name"]}
            if _is_blank(value):
                quality["missing_values"].append(location)
            else:
                number = _abundance_number(value, path)
                if isinstance(number, bool) or not isinstance(number, Real):
                    quality["non_numeric_values"].append({**location, "value": str(value)})
                elif not isfinite(number):
                    quality["non_finite_values"].append({**location, "value": str(value)})
                elif number < 0:
                    quality["negative_values"].append({**location, "value": float(number)})

    quality["duplicate_arg_names"] = [
        {"name": name, "rows": rows} for name, rows in exact_names.items() if len(rows) > 1
    ]
    quality["case_conflicts"] = [
        {"variants": [{"name": name, "rows": rows} for name, rows in variants.items()]}
        for variants in folded_names.values() if len(variants) > 1
    ]

    groups = {region: {"iDNA": 0, "eDNA": 0} for region in ("LF", "IZ", "RW", "AZ")}
    for sample in samples:
        groups[sample["region"]][sample["dna_type"]] += 1

    report = {
        "file": str(path),
        "worksheet": sheet_name,
        "arg_column": headers[arg_column],
        "data_rows": data_rows,
        "arg_name_count": sum(len(rows) for rows in exact_names.values()),
        "sample_count": len(samples),
        "samples": samples,
        "sample_counts_by_region": groups,
        "unrecognized_columns": unrecognized_columns,
        "quality": quality,
    }
    return report, table


def _abundance_number(value, path):
    """Parse numeric text in CSV. Excel cells must already be numeric."""
    if path.suffix.lower() == ".csv" and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def _summarize_totals(samples):
    values = [sample["arg_tpm_sum"] for sample in samples]
    return {
        "n": len(values),
        "mean": mean(values) if values else None,
        "median": median(values) if values else None,
        "min": min(values, default=None),
        "max": max(values, default=None),
    }


def calculate_arg_abundance(path=DEFAULT_PATH, sheet_name=None):
    """Sum ARG values per sample and describe those totals by group."""
    report, table = _read_arg_worksheet(path, sheet_name)
    quality = report["quality"]
    blocking_issues = [
        key for key in (
            "missing_arg_names", "invalid_arg_names", "missing_values",
            "non_numeric_values", "non_finite_values", "negative_values",
            "duplicate_arg_names",
        )
        if quality[key]
    ]
    if blocking_issues:
        raise ValueError("无法计算完整的 ARG 丰度总和，请先检查：" + "、".join(blocking_issues))
    if not report["data_rows"]:
        raise ValueError("工作表没有 ARG 数据行。")

    rows = table.iloc[1:].drop(index=[row - 1 for row in quality["blank_rows"]])
    samples = [
        {**sample, "arg_tpm_sum": fsum(
            _abundance_number(value, Path(path))
            for value in rows.iloc[:, sample["excel_column"] - 1]
        )}
        for sample in report["samples"]
    ]

    dna_types = ("iDNA", "eDNA")
    by_dna_type = {
        dna_type: _summarize_totals([sample for sample in samples if sample["dna_type"] == dna_type])
        for dna_type in dna_types
    }
    by_region = {}
    for region in report["sample_counts_by_region"]:
        regional_samples = [sample for sample in samples if sample["region"] == region]
        by_region[region] = {
            "all_samples": _summarize_totals(regional_samples),
            "by_dna_type": {
                dna_type: _summarize_totals([
                    sample for sample in regional_samples if sample["dna_type"] == dna_type
                ])
                for dna_type in dna_types
            },
        }

    return {
        "file": report["file"],
        "worksheet": report["worksheet"],
        "arg_record_count": report["data_rows"],
        "sample_count": report["sample_count"],
        "samples": samples,
        "by_dna_type": by_dna_type,
        "by_region": by_region,
        "case_conflicts": quality["case_conflicts"],
        "unrecognized_columns": report["unrecognized_columns"],
    }
