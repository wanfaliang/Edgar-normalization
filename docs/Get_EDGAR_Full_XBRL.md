Great, this is the right next step.

You basically need to go **one level down** from the FSDS into the actual filing directory on EDGAR and grab the XBRL package (instance, schema, linkbases). I’ll show you:

1. How to build the **EDGAR filing URL** from your existing `cik` + `adsh`.
2. How to **locate & download** the XBRL files, especially `*_cal.xml`.
3. A **ready-to-drop-in Python helper** that you can integrate with your `StatementReconstructor` to fetch & cache the calc linkbase.

I’ll stay within official SEC infrastructure, no third-party services.

---

## 1. From CIK + ADSH to the filing folder URL

You already have `cik` and `adsh` in your pipeline (from `sub.txt`) .

EDGAR filing folder pattern:

```text
https://www.sec.gov/Archives/edgar/data/{CIK_no_leading_zeros}/{ADSH_no_dashes}/
```

Example (Amazon, fake numbers):

```text
CIK = 1018724
ADSH = 0001018724-24-000130

→ cik_str = "1018724"
→ adsh_stripped = "0001018724-24-000130".replace("-", "") = "000101872424000130"

Base URL:
https://www.sec.gov/Archives/edgar/data/1018724/000101872424000130/
```

In that directory you’ll typically see:

* Instance: `xxx-20240630.xml` or `.xbrl`
* Schema: `xxx-20240630.xsd`
* Linkbases:

  * `xxx-20240630_pre.xml`
  * `xxx-20240630_cal.xml`  ⬅️ **calculation linkbase**
  * `xxx-20240630_lab.xml`
  * `xxx-20240630_def.xml`
* Helper: `FilingSummary.xml`, `MetaLinks.json`, etc.

---

## 2. Ways to get “full XBRL”

You have two practical options:

### Option A — Per-filing HTTP access (simplest, good for research)

For each filing you care about:

1. Construct base URL as above.
2. List or guess filenames.
3. Download files you need (`*.xsd`, `*_cal.xml`, `*_pre.xml`, `*_lab.xml`, instance).

Because you don’t have an index of filenames from FSDS, you usually either:

* Fetch `FilingSummary.xml` and/or `MetaLinks.json` to find the XBRL file names, or
* Use a simple pattern: “first `.xsd` file in the folder”, then derive `*_cal.xml` etc. from its base name.

### Option B — SEC’s HTML interface “xbrl.zip” (bulk grabbing for a filing)

For many filings, if you go through the HTML index manually there’s an **XBRL zip package** (named like `xxx-xbrl.zip`) that bundles instance + schema + linkbases. Programmatically it’s possible but slightly messier (you’d need to find the file in the index). For now, Option A is usually enough.

Given what you’re building, **Option A with direct linkbase downloads** is the most straightforward.

---

## 3. Python helper: download and parse calc linkbase

Here’s a ready-to-use helper module you can add, e.g. `xbrl_loader.py`.

It:

* Builds the EDGAR filing URL from `cik`, `adsh`.
* Fetches `index.json` (lightweight directory listing the SEC exposes).
* Finds the XBRL **schema** (`.xsd`) and uses its base name to construct `*_cal.xml`.
* Downloads and parses the calc linkbase.

```python
# xbrl_loader.py

import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

# IMPORTANT: set a proper contact UA
HEADERS = {
    "User-Agent": "Your Name your_email@domain.com"
}


def get_filing_base_url(cik: int, adsh: str) -> str:
    cik_str = str(cik).lstrip("0")
    adsh_no_dash = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_str}/{adsh_no_dash}/"


def fetch_index_json(cik: int, adsh: str) -> dict:
    """
    SEC exposes a simple JSON index under each filing directory:
       .../{cik}/{adsh_no_dash}/index.json
    which lists all files in that folder.
    """
    import json

    base = get_filing_base_url(cik, adsh)
    url = base + "index.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def find_xbrl_filenames(index_json: dict) -> Dict[str, str]:
    """
    Use index.json to find the main XBRL schema + linkbases.

    Returns dict like:
        {
          "schema": "company-20240630.xsd",
          "cal":    "company-20240630_cal.xml",
          "pre":    "company-20240630_pre.xml",
          "lab":    "company-20240630_lab.xml",
          "def":    "company-20240630_def.xml",
          "instance": "company-20240630.xml"
        }
    """
    files = index_json.get("directory", {}).get("item", [])

    schema = None
    instance = None

    # 1) find the company extension schema (.xsd)
    for f in files:
        name = f["name"]
        if name.lower().endswith(".xsd"):
            schema = name
            break

    # 2) find instance (.xml or .xbrl), not FilingSummary.xml
    for f in files:
        name = f["name"]
        lower = name.lower()
        if lower.endswith(".xml") or lower.endswith(".xbrl"):
            if name.lower() not in ("filingsummary.xml", "metadataroles.xml"):
                instance = name
                break

    if not schema:
        raise FileNotFoundError("No XBRL schema (.xsd) found in filing directory")

    base = schema.rsplit(".", 1)[0]  # e.g. "company-20240630"

    return {
        "schema": schema,
        "cal": base + "_cal.xml",
        "pre": base + "_pre.xml",
        "lab": base + "_lab.xml",
        "def": base + "_def.xml",
        "instance": instance
    }


def download_file(base_url: str, filename: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = base_url + filename
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    out_path = dest_dir / filename
    out_path.write_bytes(resp.content)
    return out_path


def load_calc_linkbase(cik: int, adsh: str, cache_dir: Path) -> ET.ElementTree:
    """
    Download (or load from cache) the calculation linkbase for a filing
    and return it as an ElementTree object.
    """
    base_url = get_filing_base_url(cik, adsh)

    # Use index.json to discover file names
    index_json = fetch_index_json(cik, adsh)
    names = find_xbrl_filenames(index_json)
    cal_name = names["cal"]

    # Cache path: cache_dir/{cik}/{adsh_no_dash}/cal.xml
    subdir = cache_dir / str(cik).lstrip("0") / adsh.replace("-", "")
    cal_path = subdir / cal_name

    if not cal_path.exists():
        cal_path = download_file(base_url, cal_name, subdir)

    tree = ET.parse(cal_path)
    return tree
```

Usage example in your environment:

```python
from pathlib import Path
from xbrl_loader import load_calc_linkbase

cik = 1018724
adsh = "0001018724-24-000130"

cache_dir = Path("xbrl_cache")  # wherever you like
cal_tree = load_calc_linkbase(cik, adsh, cache_dir)

root = cal_tree.getroot()
```

At this point you have the full **calculation linkbase** in memory; you can walk `link:calculationLink` arcs and build your parent–child + weight structures.

---

## 4. Integrate with your `StatementReconstructor`

Inside `StatementReconstructor.reconstruct_statement` (after you have `cik`, `adsh`, `stmt_type`):

```python
from pathlib import Path
from xbrl_loader import load_calc_linkbase

...

cal_tree = load_calc_linkbase(cik, adsh, Path(config.storage.xbrl_cache_dir))

# Now you can build a mapping: tag -> list of (child_tag, weight)
from collections import defaultdict

def build_calc_graph(cal_tree):
    ns = {
        "link": "http://www.xbrl.org/2003/linkbase",
        "xlink": "http://www.w3.org/1999/xlink"
    }
    root = cal_tree.getroot()

    loc_map = {}  # label -> tag
    graph = defaultdict(list)

    # First collect locators (label -> concept name)
    for loc in root.findall(".//link:loc", ns):
        label = loc.attrib.get("{http://www.w3.org/1999/xlink}label")
        href = loc.attrib.get("{http://www.w3.org/1999/xlink}href")
        # href like "company-20240630.xsd#AssetsCurrent"
        if "#" in href:
            tag = href.split("#", 1)[1]
            loc_map[label] = tag

    # Then collect arcs (parent_loc -> child_loc with weight)
    for arc in root.findall(".//link:calculationArc", ns):
        from_label = arc.attrib.get("{http://www.w3.org/1999/xlink}from")
        to_label = arc.attrib.get("{http://www.w3.org/1999/xlink}to")
        weight = float(arc.attrib.get("weight", "1"))

        parent_tag = loc_map.get(from_label)
        child_tag = loc_map.get(to_label)

        if parent_tag and child_tag:
            graph[parent_tag].append((child_tag, weight))

    return graph

calc_graph = build_calc_graph(cal_tree)
```

Now `calc_graph` tells you, for each **parent tag**, which tags roll into it and with what `weight`. That’s the formal XBRL definition of “sum item”.

From here you can:

* Mark your `StatementNode` as a **sum/total item** if its `tag` appears as a key in `calc_graph`.
* Optionally validate: parent value ≈ Σ weight × child values from NUM for same context.

---

## 5. Summary

To get “full EDGAR XBRL including calc linkbase”:

1. Use your `cik` + `adsh` → build filing directory URL
   `https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_no_dashes}/`
2. Call `index.json` in that directory to discover all XBRL file names.
3. Identify the XBRL schema `*.xsd`, derive `*_cal.xml`, `*_pre.xml`, `*_lab.xml`, etc.
4. Download and cache those files; parse `*_cal.xml` as the **calculation linkbase**.
5. Use the calc linkbase to know, programmatically, which tags are **sum items** (parents in the calculation graph).

If you want, next step I can:

* Wire up a `mark_sum_items_from_calc_graph` function that walks your existing hierarchy and sets `node.is_sum_item` based on the calc linkbase, so you no longer rely on heuristics.


  Problem

  For Inline XBRL filings, the calculation linkbase is embedded in the .xsd schema file, not in a separate _cal.xml file. The current    
   xbrl_loader.py only looks for _cal.xml files and falls back to the US-GAAP standard taxonomy when not found. This causes incorrect    
   parent_line assignments because the standard taxonomy has different/generic tags that don't match the company's actual tags.

  Example (AMERISAFE - CIK 1018979)

  - Line 3 tag: DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLossCurrent
  - Line 5 tag: EquitySecuritiesFvNi
  - These tags ARE in the filing's .xsd calc linkbase as children of Investments
  - But the US-GAAP standard taxonomy has different child tags for Investments
  - Result: parent_line is None for these items, so they don't get skipped

  Solution

  Update xbrl_loader.py to:
  1. First try to load separate _cal.xml file (current behavior)
  2. If not found, try to parse embedded calc linkbase from the .xsd schema file
  3. Only fall back to US-GAAP standard taxonomy if neither is available

  Changes to xbrl_loader.py

  1. Add new function parse_calc_linkbase_from_schema() to parse <link:calculationArc> elements from .xsd file
  2. Update load_calc_graph_with_fallback() to try loading from .xsd before falling back to US-GAAP taxonomy

  Now let me implement the fix:

  Summary

  Problem: For Inline XBRL filings, the calculation linkbase was embedded in the .xsd schema file, not in a separate _cal.xml file.      
  The code was falling back to the US-GAAP standard taxonomy which has different/generic tags that didn't match the company's actual     
  tags. This caused parent_line to be None for some items, so they weren't skipped by the mapping logic.

  Solution: Updated xbrl_loader.py to:
  1. First try to load separate _cal.xml file (existing behavior)
  2. If not found, NEW: parse embedded calc linkbase from the .xsd schema file
  3. Only fall back to US-GAAP standard taxonomy if neither is available

  Changes made to xbrl_loader.py:
  1. Added load_schema_file() - Downloads/caches the .xsd schema file
  2. Added parse_calc_linkbase_from_schema() - Parses <link:calculationArc> elements from .xsd
  3. Added load_calc_graph_from_schema() - Combines the above two functions
  4. Updated load_calc_graph_with_fallback() - Added step 2 (try schema) before falling back to US-GAAP

  Result: For AMERISAFE, all 4 children of "Total investments" now correctly have parent_line: 7, so they will be skipped by the
  mapping logic as intended.

> so, we first check  _cal.xml, for inline we then check .xsd, and finally if none works, we go get fasb taxonomy, right? 

● Yes, exactly! The fallback chain is:

  1. _cal.xml - Separate calculation linkbase file (traditional XBRL filings)
  2. .xsd - Embedded calc linkbase in schema file (Inline XBRL filings)
  3. FASB US-GAAP taxonomy - Standard taxonomy from fasb.org (last resort fallback)

  This way we always prefer the filing-specific calculation relationships (which have the exact tags the company uses) over the
  generic US-GAAP standard taxonomy.