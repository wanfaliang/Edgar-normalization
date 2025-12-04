# Filter TXT to Excel Scripts

Scripts for filtering SEC EDGAR dataset files (TSV format) and exporting to Excel.

The SEC EDGAR Financial Statement datasets contain four main files:
- `sub.txt` - Submission metadata (company info, filing details)
- `pre.txt` - Presentation data (how data appears in statements)
- `num.txt` - Numeric values (actual financial data)
- `tag.txt` - Tag definitions (XBRL taxonomy info)

## Scripts Overview

| Script | Description |
|--------|-------------|
| `filter_pre.py` | Filter pre.txt by adsh or company name, join with tag.txt |
| `filter_num_with_pre.py` | Filter num.txt and pre.txt by company name, merge on tag |
| `filter_pre_by_plabel.py` | Filter pre.txt by plabel substrings, join with sub.txt |
| `export_tag.py` | Export tag.txt to Excel without filtering |

---

## filter_pre.py

Filter `pre.txt` by adsh or company name and export to Excel. Automatically joins with `tag.txt` to include tag metadata.

### Usage

```bash
# Filter by adsh
python scripts/filter_pre.py <pre.txt_path> --adsh <adsh_value1> [<adsh_value2> ...]

# Filter by company name
python scripts/filter_pre.py <pre.txt_path> --name <company_name>
```

### Examples

```bash
# Filter by specific adsh
python scripts/filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --adsh 0000002178-24-000054

# Filter by multiple adsh values
python scripts/filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --adsh 0000002178-24-000054 0000002488-24-000056

# Filter by company name (case-insensitive substring match)
python scripts/filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --name "APPLE"
```

### Output

- File: `pre_filtered.xlsx` (for --adsh) or `pre_<company_name>.xlsx` (for --name)
- Location: Same folder as input file
- Columns from pre.txt: `adsh`, `report`, `line`, `stmt`, `inpth`, `rfile`, `tag`, `version`, `plabel`, `negating`
- Columns from tag.txt: `custom`, `abstract`, `datatype`, `iord`, `crdr`, `tlabel`, `doc`

---

## filter_num_with_pre.py

Filter `num.txt` and `pre.txt` by company name, then merge them on `adsh` and `tag` to extend numeric data with presentation metadata.

### Usage

```bash
python scripts/filter_num_with_pre.py <folder_path> --name <company_name>
```

### Example

```bash
python scripts/filter_num_with_pre.py data/sec_datasets/extracted/2024q2 --name "APPLE"
```

### Output

- File: `num_pre_<company_name>.xlsx`
- Location: Same folder as input
- Columns from num.txt: `adsh`, `tag`, `version`, `ddate`, `qtrs`, `uom`, `segments`, `coreg`, `value`, `footnote`
- Columns from pre.txt: `report`, `line`, `stmt`, `inpth`, `rfile`, `plabel`, `negating`

---

## filter_pre_by_plabel.py

Filter `pre.txt` by plabel substrings and join with company names from `sub.txt`.

### Usage

```bash
python scripts/filter_pre_by_plabel.py <pre.txt_path> --plabel <substring1> [<substring2> ...]
```

### Examples

```bash
# Single substring
python scripts/filter_pre_by_plabel.py data/sec_datasets/extracted/2024q2/pre.txt --plabel "revenue"

# Multiple substrings (OR logic - matches any)
python scripts/filter_pre_by_plabel.py data/sec_datasets/extracted/2024q2/pre.txt --plabel "revenue" "income" "sales"
```

### Output

- File: `pre_plabel_<substrings>.xlsx`
- Location: Same folder as input file
- Columns from pre.txt: `adsh`, `report`, `line`, `stmt`, `inpth`, `rfile`, `tag`, `version`, `plabel`, `negating`
- Columns from sub.txt: `name`

---

## export_tag.py

Export `tag.txt` to Excel without any filtering.

### Usage

```bash
python scripts/export_tag.py <tag.txt_path>
```

### Example

```bash
python scripts/export_tag.py data/sec_datasets/extracted/2024q2/tag.txt
```

### Output

- File: `tag.xlsx`
- Location: Same folder as input file
- Columns: `tag`, `version`, `custom`, `abstract`, `datatype`, `iord`, `crdr`, `tlabel`, `doc`

---

## Dependencies

```bash
pip install pandas xlsxwriter
```

## Notes

- All scripts use TSV (tab-separated) format for input files
- Company name matching is case-insensitive substring search
- Long text fields are truncated to 32000 characters to avoid Excel cell limits
- Excel files use `xlsxwriter` engine for better handling of large files
