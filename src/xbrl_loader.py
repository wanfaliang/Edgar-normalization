"""
XBRL Loader
===========
Fetches and parses XBRL files from SEC EDGAR filing directories.

Key functionality:
- Build EDGAR filing URL from CIK + ADSH
- Fetch index.json to discover XBRL file names
- Download and cache calculation linkbase (*_cal.xml)
- Parse calc linkbase to build parent-child graph with weights

Usage:
    from xbrl_loader import load_calc_graph

    cik = 1018724
    adsh = "0001018724-24-000130"

    calc_graph = load_calc_graph(cik, adsh)
    # calc_graph: {parent_tag: [(child_tag, weight), ...], ...}

    # Example: see what rolls into Assets
    print(calc_graph.get('Assets'))
    # [('AssetsCurrent', 1.0), ('AssetsNoncurrent', 1.0)]
"""

import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import json
import time

# SEC requires a proper User-Agent header
HEADERS = {
    "User-Agent": "Edgar-Explorer Research Project contact@example.com"
}

# Default cache directory
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "xbrl_cache"

# Rate limiting: SEC asks for max 10 requests per second
RATE_LIMIT_DELAY = 0.1  # 100ms between requests

# US-GAAP Standard Taxonomy calc linkbase URLs by year
# These provide standard calculation relationships for Inline XBRL filings
US_GAAP_CALC_LINKBASES = {
    2023: [
        # Balance Sheet - Classified (current/non-current)
        'https://xbrl.fasb.org/us-gaap/2023/stm/us-gaap-stm-sfp-cls-cal-2023.xml',
        # Balance Sheet - Deposit Based Operations (banks)
        'https://xbrl.fasb.org/us-gaap/2023/stm/us-gaap-stm-sfp-dbo-cal-2023.xml',
        # Income Statement
        'https://xbrl.fasb.org/us-gaap/2023/stm/us-gaap-stm-soi-cal-2023.xml',
        # Cash Flow - Indirect method
        'https://xbrl.fasb.org/us-gaap/2023/stm/us-gaap-stm-scf-indir-cal-2023.xml',
        # Stockholders Equity
        'https://xbrl.fasb.org/us-gaap/2023/stm/us-gaap-stm-sheci-cal-2023.xml',
    ],
    2024: [
        'https://xbrl.fasb.org/us-gaap/2024/stm/us-gaap-stm-sfp-cls-cal-2024.xml',
        'https://xbrl.fasb.org/us-gaap/2024/stm/us-gaap-stm-sfp-dbo-cal-2024.xml',
        'https://xbrl.fasb.org/us-gaap/2024/stm/us-gaap-stm-soi-cal-2024.xml',
        'https://xbrl.fasb.org/us-gaap/2024/stm/us-gaap-stm-scf-indir-cal-2024.xml',
        'https://xbrl.fasb.org/us-gaap/2024/stm/us-gaap-stm-sheci-cal-2024.xml',
    ],
}


def get_filing_base_url(cik: int, adsh: str) -> str:
    """
    Build the EDGAR filing directory URL from CIK and ADSH.

    Example:
        CIK = 1018724, ADSH = "0001018724-24-000130"
        -> https://www.sec.gov/Archives/edgar/data/1018724/000101872424000130/
    """
    cik_str = str(cik).lstrip("0")
    adsh_no_dash = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_str}/{adsh_no_dash}/"


def fetch_index_json(cik: int, adsh: str) -> dict:
    """
    Fetch the index.json file from the filing directory.

    SEC exposes a JSON index at each filing directory:
        .../{cik}/{adsh_no_dash}/index.json
    which lists all files in that folder.
    """
    base = get_filing_base_url(cik, adsh)
    url = base + "index.json"

    time.sleep(RATE_LIMIT_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_xbrl_filenames(index_json: dict) -> Dict[str, Optional[str]]:
    """
    Use index.json to find the main XBRL schema and linkbase filenames.

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
    cal = None
    pre = None
    lab = None
    def_file = None

    # Build a list of all filenames
    filenames = [f["name"] for f in files]

    # Find the company extension schema (.xsd) - not the standard xbrl schemas
    for name in filenames:
        lower = name.lower()
        if lower.endswith(".xsd") and "xbrl" not in lower:
            schema = name
            break

    # Find instance (.xml), excluding known non-instance files
    exclude_patterns = ["filingsummary", "metadataroles", "_cal", "_pre", "_lab", "_def", "r1", "r2", "r3"]
    for name in filenames:
        lower = name.lower()
        if lower.endswith(".xml") and not any(p in lower for p in exclude_patterns):
            # Additional check: instance files usually have a date pattern
            if any(c.isdigit() for c in name):
                instance = name
                break

    # Find linkbase files directly if they exist
    for name in filenames:
        lower = name.lower()
        if lower.endswith("_cal.xml"):
            cal = name
        elif lower.endswith("_pre.xml"):
            pre = name
        elif lower.endswith("_lab.xml"):
            lab = name
        elif lower.endswith("_def.xml"):
            def_file = name

    # If linkbases not found directly, derive from schema name
    if schema and not cal:
        base = schema.rsplit(".", 1)[0]  # e.g. "company-20240630"
        cal = base + "_cal.xml" if (base + "_cal.xml") in filenames else None
        pre = pre or (base + "_pre.xml" if (base + "_pre.xml") in filenames else None)
        lab = lab or (base + "_lab.xml" if (base + "_lab.xml") in filenames else None)
        def_file = def_file or (base + "_def.xml" if (base + "_def.xml") in filenames else None)

    return {
        "schema": schema,
        "cal": cal,
        "pre": pre,
        "lab": lab,
        "def": def_file,
        "instance": instance,
        "all_files": filenames
    }


def download_file(base_url: str, filename: str, dest_dir: Path) -> Path:
    """Download a file from the filing directory and save to cache."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = base_url + filename

    time.sleep(RATE_LIMIT_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    out_path = dest_dir / filename
    out_path.write_bytes(resp.content)
    return out_path


def get_cache_dir(cik: int, adsh: str, cache_dir: Path = None) -> Path:
    """Get the cache directory path for a specific filing."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cik_str = str(cik).lstrip("0")
    adsh_no_dash = adsh.replace("-", "")
    return cache_dir / cik_str / adsh_no_dash


def load_calc_linkbase(cik: int, adsh: str, cache_dir: Path = None) -> ET.ElementTree:
    """
    Download (or load from cache) the calculation linkbase for a filing
    and return it as an ElementTree object.
    """
    base_url = get_filing_base_url(cik, adsh)
    subdir = get_cache_dir(cik, adsh, cache_dir)

    # Check if we have cached index.json
    index_cache = subdir / "index.json"
    if index_cache.exists():
        with open(index_cache, 'r') as f:
            index_json = json.load(f)
    else:
        index_json = fetch_index_json(cik, adsh)
        # Cache the index
        subdir.mkdir(parents=True, exist_ok=True)
        with open(index_cache, 'w') as f:
            json.dump(index_json, f)

    names = find_xbrl_filenames(index_json)
    cal_name = names.get("cal")

    if not cal_name:
        raise FileNotFoundError(f"No calculation linkbase found for CIK {cik}, ADSH {adsh}")

    # Check cache
    cal_path = subdir / cal_name
    if not cal_path.exists():
        cal_path = download_file(base_url, cal_name, subdir)

    tree = ET.parse(cal_path)
    return tree


def parse_calc_linkbase(cal_tree: ET.ElementTree) -> Dict[str, List[Tuple[str, float]]]:
    """
    Parse the calculation linkbase XML and build a graph.

    Returns:
        dict: {parent_tag: [(child_tag, weight), ...], ...}

    The calc linkbase contains:
    - <link:loc> elements that map labels to concept names (tags)
    - <link:calculationArc> elements that define parent->child relationships with weights
    """
    ns = {
        "link": "http://www.xbrl.org/2003/linkbase",
        "xlink": "http://www.w3.org/1999/xlink"
    }
    root = cal_tree.getroot()

    # Map: xlink:label -> concept tag name
    loc_map = {}

    # First pass: collect all locators (label -> tag)
    for loc in root.iter("{http://www.xbrl.org/2003/linkbase}loc"):
        label = loc.attrib.get("{http://www.w3.org/1999/xlink}label")
        href = loc.attrib.get("{http://www.w3.org/1999/xlink}href")

        if label and href and "#" in href:
            # href like "company-20240630.xsd#AssetsCurrent" or "http://...#AssetsCurrent"
            tag = href.split("#", 1)[1]
            loc_map[label] = tag

    # Build the graph: parent_tag -> [(child_tag, weight), ...]
    graph = defaultdict(list)

    # Second pass: collect all calculation arcs
    for arc in root.iter("{http://www.xbrl.org/2003/linkbase}calculationArc"):
        from_label = arc.attrib.get("{http://www.w3.org/1999/xlink}from")
        to_label = arc.attrib.get("{http://www.w3.org/1999/xlink}to")
        weight = float(arc.attrib.get("weight", "1"))
        order = arc.attrib.get("order", "0")

        parent_tag = loc_map.get(from_label)
        child_tag = loc_map.get(to_label)

        if parent_tag and child_tag:
            graph[parent_tag].append((child_tag, weight, float(order)))

    # Sort children by order and remove order from result
    result = {}
    for parent, children in graph.items():
        sorted_children = sorted(children, key=lambda x: x[2])
        result[parent] = [(child, weight) for child, weight, _ in sorted_children]

    return result


def load_schema_file(cik: int, adsh: str, cache_dir: Path = None) -> Optional[ET.ElementTree]:
    """
    Download (or load from cache) the XBRL schema (.xsd) file for a filing.

    For Inline XBRL filings, the calc linkbase is often embedded in the .xsd file
    rather than in a separate _cal.xml file.

    Returns:
        ElementTree object if schema found, None otherwise
    """
    base_url = get_filing_base_url(cik, adsh)
    subdir = get_cache_dir(cik, adsh, cache_dir)

    # Check if we have cached index.json
    index_cache = subdir / "index.json"
    if index_cache.exists():
        with open(index_cache, 'r') as f:
            index_json = json.load(f)
    else:
        index_json = fetch_index_json(cik, adsh)
        # Cache the index
        subdir.mkdir(parents=True, exist_ok=True)
        with open(index_cache, 'w') as f:
            json.dump(index_json, f)

    names = find_xbrl_filenames(index_json)
    schema_name = names.get("schema")

    if not schema_name:
        return None

    # Check cache
    schema_path = subdir / schema_name
    if not schema_path.exists():
        schema_path = download_file(base_url, schema_name, subdir)

    tree = ET.parse(schema_path)
    return tree


def parse_calc_linkbase_from_schema(schema_tree: ET.ElementTree) -> Dict[str, List[Tuple[str, float]]]:
    """
    Parse embedded calculation linkbase from an XBRL schema (.xsd) file.

    For Inline XBRL filings, the calc linkbase is often embedded directly in the .xsd
    file as <link:calculationLink> elements containing <link:calculationArc> elements.

    Args:
        schema_tree: ElementTree object of the .xsd file

    Returns:
        dict: {parent_tag: [(child_tag, weight), ...], ...}
    """
    root = schema_tree.getroot()

    # Map: xlink:label -> concept tag name
    loc_map = {}

    # First pass: collect all locators (label -> tag)
    # In embedded calc linkbase, locators are inside <link:calculationLink> elements
    for loc in root.iter("{http://www.xbrl.org/2003/linkbase}loc"):
        label = loc.attrib.get("{http://www.w3.org/1999/xlink}label")
        href = loc.attrib.get("{http://www.w3.org/1999/xlink}href")

        if label and href and "#" in href:
            # href like "us-gaap_Assets" or with namespace prefix
            tag = href.split("#", 1)[1]
            loc_map[label] = tag

    # Build the graph: parent_tag -> [(child_tag, weight, order), ...]
    graph = defaultdict(list)

    # Second pass: collect all calculation arcs
    for arc in root.iter("{http://www.xbrl.org/2003/linkbase}calculationArc"):
        from_label = arc.attrib.get("{http://www.w3.org/1999/xlink}from")
        to_label = arc.attrib.get("{http://www.w3.org/1999/xlink}to")
        weight = float(arc.attrib.get("weight", "1"))
        order = float(arc.attrib.get("order", "0"))

        parent_tag = loc_map.get(from_label)
        child_tag = loc_map.get(to_label)

        if parent_tag and child_tag:
            # Check if this child is already in the parent's list (avoid duplicates)
            existing = [c for c, w, o in graph[parent_tag] if c == child_tag]
            if not existing:
                graph[parent_tag].append((child_tag, weight, order))

    # Sort children by order and remove order from result
    result = {}
    for parent, children in graph.items():
        sorted_children = sorted(children, key=lambda x: x[2])
        result[parent] = [(child, weight) for child, weight, _ in sorted_children]

    return result


def load_calc_graph_from_schema(cik: int, adsh: str, cache_dir: Path = None) -> Dict[str, List[Tuple[str, float]]]:
    """
    Load calc graph from embedded linkbase in the .xsd schema file.

    Args:
        cik: Company CIK number
        adsh: Filing ADSH
        cache_dir: Optional cache directory

    Returns:
        dict: {parent_tag: [(child_tag, weight), ...], ...}

    Raises:
        FileNotFoundError: If no schema file found or no calc linkbase in schema
    """
    schema_tree = load_schema_file(cik, adsh, cache_dir)
    if schema_tree is None:
        raise FileNotFoundError(f"No schema file found for CIK {cik}, ADSH {adsh}")

    calc_graph = parse_calc_linkbase_from_schema(schema_tree)

    if not calc_graph:
        raise FileNotFoundError(f"No embedded calc linkbase found in schema for CIK {cik}, ADSH {adsh}")

    return calc_graph


def load_calc_graph(cik: int, adsh: str, cache_dir: Path = None) -> Dict[str, List[Tuple[str, float]]]:
    """
    Main entry point: load and parse the calculation linkbase for a filing.

    Args:
        cik: Company CIK number
        adsh: Filing ADSH (accession number)
        cache_dir: Optional cache directory (defaults to xbrl_cache/)

    Returns:
        dict: {parent_tag: [(child_tag, weight), ...], ...}

    Example:
        calc_graph = load_calc_graph(1018724, "0001018724-24-000130")

        # See what items roll into Assets
        print(calc_graph.get('Assets'))
        # [('AssetsCurrent', 1.0), ('AssetsNoncurrent', 1.0)]

        # See what items roll into AssetsCurrent
        print(calc_graph.get('AssetsCurrent'))
        # [('CashAndCashEquivalentsAtCarryingValue', 1.0),
        #  ('MarketableSecuritiesCurrent', 1.0),
        #  ('AccountsReceivableNetCurrent', 1.0), ...]
    """
    cal_tree = load_calc_linkbase(cik, adsh, cache_dir)
    return parse_calc_linkbase(cal_tree)


# =============================================================================
# US-GAAP Standard Taxonomy Support (for Inline XBRL filings)
# =============================================================================

def load_us_gaap_calc_linkbase(taxonomy_year: int = 2023, cache_dir: Path = None, verbose: bool = False) -> Dict[str, List[Tuple[str, float]]]:
    """
    Load the standard US-GAAP taxonomy calculation linkbase for a given year.

    This is used as a fallback for Inline XBRL filings that don't have their own
    _cal.xml files. The standard taxonomy defines calculation relationships for
    all US-GAAP concepts.

    Args:
        taxonomy_year: The US-GAAP taxonomy year (2023, 2024, etc.)
        cache_dir: Optional cache directory
        verbose: If True, print progress messages

    Returns:
        dict: Combined calc graph from all statement types
              {parent_tag: [(child_tag, weight), ...], ...}
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR

    # Check cache first
    cache_file = cache_dir / f"us-gaap-{taxonomy_year}-calc-combined.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
            # Convert back to tuples
            return {k: [(c, w) for c, w in v] for k, v in cached_data.items()}

    # Get URLs for this taxonomy year
    urls = US_GAAP_CALC_LINKBASES.get(taxonomy_year)
    if not urls:
        raise ValueError(f"No US-GAAP calc linkbase URLs defined for year {taxonomy_year}")

    combined_graph = defaultdict(list)

    for url in urls:
        if verbose:
            print(f"  Fetching: {url.split('/')[-1]}")
        try:
            time.sleep(RATE_LIMIT_DELAY)
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()

            # Parse the calc linkbase
            root = ET.fromstring(resp.content)

            # Map: xlink:label -> concept tag name
            loc_map = {}
            for loc in root.iter("{http://www.xbrl.org/2003/linkbase}loc"):
                label = loc.attrib.get("{http://www.w3.org/1999/xlink}label")
                href = loc.attrib.get("{http://www.w3.org/1999/xlink}href")
                if label and href and "#" in href:
                    tag = href.split("#", 1)[1]
                    loc_map[label] = tag

            # Collect calculation arcs
            for arc in root.iter("{http://www.xbrl.org/2003/linkbase}calculationArc"):
                from_label = arc.attrib.get("{http://www.w3.org/1999/xlink}from")
                to_label = arc.attrib.get("{http://www.w3.org/1999/xlink}to")
                weight = float(arc.attrib.get("weight", "1"))
                order = float(arc.attrib.get("order", "0"))

                parent_tag = loc_map.get(from_label)
                child_tag = loc_map.get(to_label)

                if parent_tag and child_tag:
                    # Check if this child is already in the parent's list
                    existing = [c for c, w, o in combined_graph[parent_tag] if c == child_tag]
                    if not existing:
                        combined_graph[parent_tag].append((child_tag, weight, order))

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"    Warning: Failed to fetch {url}: {e}")
            continue

    # Sort children by order and remove order from result
    result = {}
    for parent, children in combined_graph.items():
        sorted_children = sorted(children, key=lambda x: x[2])
        result[parent] = [(child, weight) for child, weight, _ in sorted_children]

    # Cache the result
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(result, f, indent=2)

    if verbose:
        print(f"  Loaded {len(result)} parent tags from US-GAAP {taxonomy_year} taxonomy")
    return result


def detect_taxonomy_year_from_filing(cik: int, adsh: str) -> int:
    """
    Detect the US-GAAP taxonomy year used by a filing from MetaLinks.json.

    Returns the taxonomy year (e.g., 2023, 2024) or defaults to 2023.
    """
    base_url = get_filing_base_url(cik, adsh)
    url = base_url + "MetaLinks.json"

    try:
        time.sleep(RATE_LIMIT_DELAY)
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return 2023  # Default

        data = resp.json()
        # Look for taxonomy namespace in instance data
        for instance_key, instance_data in data.get('instance', {}).items():
            base_taxonomies = instance_data.get('baseTaxonomies', {})
            for ns in base_taxonomies.keys():
                # e.g., "http://fasb.org/us-gaap/2023" -> 2023
                if 'fasb.org/us-gaap/' in ns:
                    year_str = ns.split('/')[-1]
                    try:
                        return int(year_str)
                    except ValueError:
                        pass

        return 2023  # Default

    except Exception:
        return 2023  # Default


def load_calc_graph_with_fallback(cik: int, adsh: str, cache_dir: Path = None, verbose: bool = False) -> Tuple[Dict[str, List[Tuple[str, float]]], str]:
    """
    Load calculation graph, with fallback chain:
    1. Filing-specific calc linkbase (_cal.xml)
    2. Embedded calc linkbase in schema file (.xsd)
    3. US-GAAP standard taxonomy

    Args:
        cik: Company CIK number
        adsh: Filing ADSH
        cache_dir: Optional cache directory
        verbose: If True, print progress messages

    Returns:
        tuple: (calc_graph, source)
            - calc_graph: {parent_tag: [(child_tag, weight), ...], ...}
            - source: "filing", "schema", or "us-gaap-{year}"
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR

    # Try 1: Filing-specific calc linkbase (_cal.xml)
    try:
        calc_graph = load_calc_graph(cik, adsh, cache_dir)
        return calc_graph, "filing"
    except FileNotFoundError:
        pass

    # Try 2: Embedded calc linkbase in schema file (.xsd)
    try:
        calc_graph = load_calc_graph_from_schema(cik, adsh, cache_dir)
        if verbose:
            print(f"  Loaded calc graph from embedded linkbase in schema ({len(calc_graph)} parent tags)")
        return calc_graph, "schema"
    except FileNotFoundError:
        pass

    # Try 3: Fallback to US-GAAP standard taxonomy
    if verbose:
        print("  No filing-specific calc linkbase found, using US-GAAP standard taxonomy...")
    taxonomy_year = detect_taxonomy_year_from_filing(cik, adsh)
    calc_graph = load_us_gaap_calc_linkbase(taxonomy_year, cache_dir, verbose=verbose)
    return calc_graph, f"us-gaap-{taxonomy_year}"


def get_sum_items(calc_graph: Dict[str, List[Tuple[str, float]]]) -> set:
    """
    Get all tags that are sum/total items (i.e., they are parents in the calc graph).
    """
    return set(calc_graph.keys())


# =============================================================================
# Control Item Tags (structural totals in balance sheet)
# =============================================================================

# These are the XBRL tags for control items - structural totals we use to organize the balance sheet
# Items whose parent is one of these tags should be mapped; others should be skipped
CONTROL_ITEM_TAGS = {
    # Current Assets
    'assetscurrent',
    # Non-current Assets
    'assetsnoncurrent',
    'assetsnoncurrentexcludingpropertyplantandequipment',
    'assetsnoncurrentotherthanpropertyplantandequipmentandfinanceassets',
    # Total Assets
    'assets',
    # Current Liabilities
    'liabilitiescurrent',
    # Non-current Liabilities
    'liabilitiesnoncurrent',
    'liabilitiesotherthanlongtermdebtnonncurrent',
    # Total Liabilities
    'liabilities',
    # Stockholders Equity
    'stockholdersequity',
    'stockholdersequityincludingportionattributabletononcontrollinginterest',
    'equity',
    'equityincludingportionattributabletononcontrollinginterest',
    # Total Liabilities and Equity
    'liabilitiesandstockholdersequity',
    # Additional variations for financial companies
    'assetsnet',
    'liabilitiesandequity',
}


def build_parent_lookup(calc_graph: Dict[str, List[Tuple[str, float]]]) -> Dict[str, str]:
    """
    Build a reverse lookup from child tag to parent tag.

    Args:
        calc_graph: {parent_tag: [(child_tag, weight), ...], ...}

    Returns:
        {child_tag: parent_tag, ...}

    Note: If a child has multiple parents (rare), only one is kept.
    """
    parent_lookup = {}
    for parent_tag, children in calc_graph.items():
        for child_tag, weight in children:
            # Store parent for this child (last one wins if multiple parents)
            parent_lookup[child_tag] = parent_tag
    return parent_lookup


def is_control_item_tag(tag: str) -> bool:
    """
    Check if a tag is a control item tag.

    Normalizes the tag (lowercase, removes prefix) before checking.
    """
    if not tag:
        return False
    # Normalize: lowercase and remove namespace prefix
    tag_normalized = tag.lower()
    if '_' in tag_normalized:
        tag_normalized = tag_normalized.split('_', 1)[1]
    return tag_normalized in CONTROL_ITEM_TAGS


def should_map_item(item_tag: str, parent_lookup: Dict[str, str]) -> bool:
    """
    Determine if an item should be mapped based on its parent in the calc graph.

    Logic:
    - If item has no parent in calc graph -> map it (assume direct child of control item)
    - If item's parent is a control item tag -> map it
    - If item's parent is NOT a control item tag -> skip it (grandchild or deeper)

    Args:
        item_tag: The XBRL tag of the item to check
        parent_lookup: {child_tag: parent_tag, ...} from build_parent_lookup()

    Returns:
        True if item should be mapped, False if it should be skipped
    """
    if not item_tag:
        return True  # No tag, can't check, default to map

    # Normalize item tag for lookup
    item_tag_normalized = item_tag
    if '_' in item_tag:
        item_tag_no_prefix = item_tag.split('_', 1)[1]
    else:
        item_tag_no_prefix = item_tag

    # Try to find parent (check both with and without prefix)
    parent_tag = parent_lookup.get(item_tag) or parent_lookup.get(item_tag_no_prefix)

    if not parent_tag:
        # No parent found in calc graph -> assume it's a direct child of control item
        return True

    # Check if parent is a control item
    return is_control_item_tag(parent_tag)


def get_calc_children(calc_graph: Dict[str, List[Tuple[str, float]]], parent_tag: str) -> List[Tuple[str, float]]:
    """
    Get the children of a parent tag with their weights.
    """
    return calc_graph.get(parent_tag, [])


def print_calc_tree(calc_graph: Dict[str, List[Tuple[str, float]]], root_tag: str, indent: int = 0, visited: set = None):
    """
    Print the calculation tree starting from a root tag.
    Useful for debugging and understanding the structure.
    """
    if visited is None:
        visited = set()

    if root_tag in visited:
        print("  " * indent + f"{root_tag} (circular ref)")
        return

    visited.add(root_tag)

    children = calc_graph.get(root_tag, [])
    weight_str = ""
    print("  " * indent + f"{root_tag}")

    for child_tag, weight in children:
        sign = "+" if weight > 0 else "-"
        print("  " * (indent + 1) + f"{sign} {child_tag} (weight: {weight})")
        if child_tag in calc_graph:
            print_calc_tree(calc_graph, child_tag, indent + 2, visited.copy())


# =============================================================================
# Database lookup helpers
# =============================================================================

def lookup_filing(ticker: str = None, cik: int = None, year: int = None, quarter: int = None):
    """
    Lookup CIK and ADSH from database using ticker or CIK with year/quarter.

    Returns:
        dict with keys: cik, adsh, company_name, ticker, form_type
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from config import config

    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        if ticker:
            # Lookup CIK from ticker
            cur.execute("SELECT cik, company_name, ticker FROM companies WHERE UPPER(ticker) = %s", (ticker.upper(),))
            company = cur.fetchone()
            if not company:
                raise ValueError(f"Ticker not found: {ticker}")
            cik = company['cik']
            company_name = company['company_name']
            ticker = company['ticker']
        elif cik:
            cur.execute("SELECT cik, company_name, ticker FROM companies WHERE cik = %s", (str(cik),))
            company = cur.fetchone()
            if not company:
                raise ValueError(f"CIK not found: {cik}")
            company_name = company['company_name']
            ticker = company['ticker']
        else:
            raise ValueError("Must provide either --ticker or --cik")

        # Lookup filing (ensure cik is string for varchar column)
        cik_str = str(cik)
        if year and quarter:
            cur.execute("""
                SELECT adsh, form_type, filed_date
                FROM filings
                WHERE cik = %s AND source_year = %s AND source_quarter = %s
                ORDER BY filed_date DESC LIMIT 1
            """, (cik_str, year, quarter))
        else:
            # Get most recent filing
            cur.execute("""
                SELECT adsh, form_type, filed_date, source_year, source_quarter
                FROM filings
                WHERE cik = %s
                ORDER BY filed_date DESC LIMIT 1
            """, (cik_str,))

        filing = cur.fetchone()
        if not filing:
            raise ValueError(f"No filing found for CIK {cik}" + (f" in {year}Q{quarter}" if year else ""))

        return {
            'cik': cik,
            'adsh': filing['adsh'],
            'company_name': company_name,
            'ticker': ticker,
            'form_type': filing['form_type']
        }
    finally:
        cur.close()
        conn.close()


def print_detailed_calc_tree(calc_graph: Dict[str, List[Tuple[str, float]]], root_tag: str,
                              indent: int = 0, visited: set = None, show_all_children: bool = True):
    """
    Print detailed calculation tree with weights and child counts.
    """
    if visited is None:
        visited = set()

    if root_tag in visited:
        print("  " * indent + f"[circular ref: {root_tag}]")
        return

    visited.add(root_tag)
    children = calc_graph.get(root_tag, [])

    # Print current node
    is_parent = root_tag in calc_graph
    suffix = f" [{len(children)} children]" if is_parent else " [leaf]"
    print("  " * indent + f"{root_tag}{suffix}")

    # Print children
    for child_tag, weight in children:
        sign = "+" if weight > 0 else "-"
        child_is_parent = child_tag in calc_graph
        child_children = calc_graph.get(child_tag, [])
        child_suffix = f" [{len(child_children)} children]" if child_is_parent else ""

        print("  " * (indent + 1) + f"{sign} {child_tag} (weight: {weight}){child_suffix}")

        # Recursively print if child is also a parent
        if show_all_children and child_is_parent:
            print_detailed_calc_tree(calc_graph, child_tag, indent + 2, visited.copy(), show_all_children)


def export_calc_graph_to_dict(calc_graph: Dict[str, List[Tuple[str, float]]]) -> dict:
    """
    Export calc graph to a more detailed dictionary structure.

    Returns:
        {
            'parent_tag': {
                'children': [
                    {'tag': 'child_tag', 'weight': 1.0, 'is_parent': True/False},
                    ...
                ],
                'child_count': N
            },
            ...
        }
    """
    result = {}
    for parent, children in calc_graph.items():
        result[parent] = {
            'children': [
                {
                    'tag': child_tag,
                    'weight': weight,
                    'is_parent': child_tag in calc_graph
                }
                for child_tag, weight in children
            ],
            'child_count': len(children)
        }
    return result


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Load and display XBRL calculation linkbase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using ticker and year/quarter (recommended)
  python xbrl_loader.py --ticker AMZN --year 2024 --quarter 2

  # Using CIK and year/quarter
  python xbrl_loader.py --cik 1018724 --year 2024 --quarter 2

  # Show calculation tree for a specific tag
  python xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --tree Assets

  # List all parent (sum) tags with children
  python xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --list-parents

  # Show detailed children for all parents
  python xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --show-children
        """
    )

    # Company identification (one of these required)
    id_group = parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument('--ticker', help='Company ticker (e.g., AMZN, MSFT)')
    id_group.add_argument('--cik', type=int, help='Company CIK number')

    # Filing identification
    parser.add_argument('--year', type=int, help='Fiscal year (e.g., 2024)')
    parser.add_argument('--quarter', type=int, choices=[1,2,3,4], help='Fiscal quarter')
    parser.add_argument('--adsh', help='Filing ADSH (overrides year/quarter lookup)')

    # Display options
    parser.add_argument('--tree', help='Print calc tree starting from this tag (e.g., Assets)')
    parser.add_argument('--list-parents', action='store_true', help='List all parent (sum) tags')
    parser.add_argument('--show-children', action='store_true', help='Show detailed children for each parent')
    parser.add_argument('--export-json', help='Export calc graph to JSON file')

    args = parser.parse_args()

    try:
        # Lookup filing info from database
        if args.adsh:
            # Direct ADSH provided
            if args.cik:
                cik = args.cik
                filing_info = {'cik': cik, 'adsh': args.adsh, 'company_name': f'CIK {cik}', 'ticker': None}
            else:
                raise ValueError("When using --adsh, must also provide --cik")
        else:
            # Lookup from database
            filing_info = lookup_filing(
                ticker=args.ticker,
                cik=args.cik,
                year=args.year,
                quarter=args.quarter
            )

        cik = filing_info['cik']
        adsh = filing_info['adsh']

        print("=" * 70)
        print(f"Company: {filing_info['company_name']}")
        print(f"Ticker: {filing_info['ticker']} | CIK: {cik}")
        print(f"Filing: {adsh} ({filing_info.get('form_type', 'N/A')})")
        print(f"URL: {get_filing_base_url(cik, adsh)}")
        print("=" * 70)
        print()

        print("Loading calculation linkbase...")
        calc_graph, source = load_calc_graph_with_fallback(cik, adsh)
        print(f"Loaded calc graph with {len(calc_graph)} parent (sum) tags")
        print(f"Source: {source}")
        print()

        # Export to JSON if requested
        if args.export_json:
            detailed = export_calc_graph_to_dict(calc_graph)
            with open(args.export_json, 'w') as f:
                json.dump(detailed, f, indent=2)
            print(f"Exported to {args.export_json}")
            print()

        # List parents
        if args.list_parents:
            print("Parent (sum) tags:")
            print("-" * 50)
            for parent in sorted(calc_graph.keys()):
                children = calc_graph[parent]
                print(f"  {parent}: {len(children)} children")
            print()

        # Show detailed children
        if args.show_children:
            print("Detailed Parent-Children Relationships:")
            print("=" * 70)
            for parent in sorted(calc_graph.keys()):
                children = calc_graph[parent]
                print(f"\n{parent} ({len(children)} children):")
                for child_tag, weight in children:
                    sign = "+" if weight > 0 else "-"
                    is_parent = child_tag in calc_graph
                    parent_indicator = " [PARENT]" if is_parent else ""
                    print(f"  {sign} {child_tag} (weight: {weight}){parent_indicator}")
            print()

        # Show tree for specific tag
        if args.tree:
            print(f"Calculation tree for '{args.tree}':")
            print("=" * 70)

            # Try exact match first, then with us-gaap_ prefix
            search_tags = [args.tree, f"us-gaap_{args.tree}"]
            found_tag = None
            for tag in search_tags:
                if tag in calc_graph:
                    found_tag = tag
                    break

            if found_tag:
                print_detailed_calc_tree(calc_graph, found_tag)
            else:
                print(f"Tag '{args.tree}' not found as a parent in calc graph")
                # Try to find similar tags
                similar = [t for t in calc_graph.keys() if args.tree.lower() in t.lower()]
                if similar:
                    print(f"\nSimilar tags found:")
                    for t in similar[:10]:
                        print(f"  - {t}")
            print()

        # Default: show key balance sheet/income statement items
        if not args.tree and not args.list_parents and not args.show_children:
            print("Key Calculation Relationships:")
            print("=" * 70)

            key_tags = [
                ('us-gaap_Assets', 'Total Assets'),
                ('us-gaap_AssetsCurrent', 'Current Assets'),
                ('us-gaap_LiabilitiesAndStockholdersEquity', 'Liabilities & Equity'),
                ('us-gaap_LiabilitiesCurrent', 'Current Liabilities'),
                ('us-gaap_StockholdersEquity', 'Stockholders Equity'),
                ('us-gaap_NetIncomeLoss', 'Net Income'),
                ('us-gaap_OperatingIncomeLoss', 'Operating Income'),
                ('us-gaap_NetCashProvidedByUsedInOperatingActivities', 'Cash from Operations'),
            ]

            for tag, label in key_tags:
                if tag in calc_graph:
                    children = calc_graph[tag]
                    print(f"\n{label} ({tag}):")
                    for child_tag, weight in children:
                        sign = "+" if weight > 0 else "-"
                        # Simplify tag name for display
                        short_name = child_tag.replace('us-gaap_', '').replace('amzn_', '[amzn]')
                        print(f"  {sign} {short_name}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
