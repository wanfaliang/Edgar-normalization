# SEC EDGAR API Walkthrough

## Overview: What URLs/Endpoints Are Called?

The sec-edgar library makes requests to 3 main SEC endpoints:

1. **CIK Lookup** - Convert ticker to CIK number
2. **Filing List** - Get list of filings for a company
3. **Filing Download** - Download individual filing files

Let me walk through each step with real examples.

---

## Step 1: Ticker → CIK Lookup

### Endpoint
```
https://www.sec.gov/files/company_tickers.json
```

### What It Does
Converts company ticker symbols (like "AAPL") to CIK numbers (like "0000320193").

### Code Location
`secedgar/cik_lookup.py` lines 32-37

```python
def get_cik_map(user_agent):
    headers = {'user-agent': user_agent}
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=headers
    )
    return response.json()
```

### Request Example
```http
GET https://www.sec.gov/files/company_tickers.json
Headers:
  User-Agent: Faliang Wan (wanfaliang88@gmail.com)
```

### Response Sample
```json
{
  "0": {
    "cik_str": 320193,
    "ticker": "AAPL",
    "title": "Apple Inc."
  },
  "1": {
    "cik_str": 789019,
    "ticker": "MSFT",
    "title": "MICROSOFT CORP"
  },
  ...
}
```

### What Happens
- Downloads complete mapping of ~13,000 companies
- Cached using `@functools.lru_cache()` - only fetched once
- Converts ticker "aapl" → CIK "320193"

---

## Step 2: Get Filing List

### Endpoint
```
http://www.sec.gov/cgi-bin/browse-edgar
```

### What It Does
Gets a list of all filings for a company, with metadata and URLs.

### Code Location
`secedgar/core/company.py` lines 110-114, 129, 312-316

```python
# Base params
self._params = {
    "action": "getcompany",
    "output": "xml",
    "start": 0
}

# Path
path = "cgi-bin/browse-edgar"

# Make request
data = self.client.get_soup(self.path, self.params)
```

### Request Example
```http
GET http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K&output=xml&start=0&count=10
Headers:
  User-Agent: Faliang Wan (wanfaliang88@gmail.com)
```

### Full URL Breakdown
```
http://www.sec.gov/cgi-bin/browse-edgar
  ?action=getcompany          # Action type
  &CIK=0000320193            # Company CIK (Apple)
  &type=10-K                 # Filing type
  &output=xml                # Return format
  &start=0                   # Pagination start
  &count=10                  # Results per page
  &dateb=20241231            # Optional: end date
  &datea=20200101            # Optional: start date
  &ownership=include         # Include ownership filings
```

### Parameters Explained

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `action` | ✅ Yes | API action | `getcompany` |
| `CIK` | ✅ Yes | Company identifier | `0000320193` |
| `type` | ❌ No | Filing type filter | `10-K`, `10-Q`, `8-K` |
| `output` | ✅ Yes | Response format | `xml` (or `atom`) |
| `start` | ✅ Yes | Pagination offset | `0`, `10`, `20` |
| `count` | ❌ No | Results per page | `10` (default: 100) |
| `dateb` | ❌ No | End date | `20241231` (YYYYMMDD) |
| `datea` | ❌ No | Start date | `20200101` (YYYYMMDD) |
| `ownership` | ❌ No | Include ownership | `include`, `exclude` |

### Response Sample (XML)
```xml
<?xml version="1.0" encoding="ISO-8859-1" ?>
<companyFilings>
  <companyInfo>
    <CIK>0000320193</CIK>
    <name>Apple Inc.</name>
    <fiscalYearEnd>0927</fiscalYearEnd>
  </companyInfo>
  <results>
    <filing>
      <type>10-K</type>
      <dateFiled>2024-11-01</dateFiled>
      <filingHREF>https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm</filingHREF>
      <formName>Annual report [Section 13 and 15(d)]</formName>
    </filing>
    <filing>
      <type>10-K</type>
      <dateFiled>2023-11-03</dateFiled>
      <filingHREF>https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm</filingHREF>
    </filing>
    ...
  </results>
</companyFilings>
```

### What Code Does With Response

**Parsing** (`company.py` line 262-294):
```python
filings = data.find_all("filing")  # Find all <filing> tags

for f in filings:
    href_tag = f.find('filingHREF')  # Get filing URL
    type_tag = f.find('type')        # Get filing type

    # Filter by type if specified
    if type_tag.get_text() == self.filing_type.value:
        results.append(href_tag.string)
```

**URL Transformation** (`company.py` line 323):
```python
# Input:  https://www.sec.gov/.../0000320193-24-000123-index.htm
# Output: https://www.sec.gov/.../0000320193-24-000123.txt

txt_urls = [link[:link.rfind("-")].strip() + ".txt" for link in links]
```

The code:
1. Takes the filing index HTML URL
2. Strips off `-index.htm`
3. Adds `.txt` to get the full filing text file

### Pagination

If you request `count=50` but SEC returns 10 per page:

```python
# First request
?start=0   # Gets filings 0-9

# Second request
?start=10  # Gets filings 10-19

# Continues until we have 50 or run out
```

Code: `company.py` line 315-321

---

## Step 3: Download Individual Filings

### Endpoint
```
https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}.txt
```

### What It Does
Downloads the complete filing text file.

### URL Construction

From Step 2, we got:
```
https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm
```

Code transforms it to:
```
https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt
```

### URL Breakdown
```
https://www.sec.gov/Archives/edgar/data
  /320193                      # CIK (leading zeros removed)
  /000032019324000123          # Accession number (no dashes)
  /0000320193-24-000123.txt    # Accession number (with dashes) + .txt
```

### Download Method

**Code Location**: `secedgar/client.py` lines 237-278

The library uses **async batch downloading**:

```python
async def wait_for_download_async(self, inputs):
    # inputs = [(url, save_path), (url, save_path), ...]

    # Create connection pool
    conn = aiohttp.TCPConnector(limit=self.rate_limit)  # Max 10 concurrent

    # Batch into groups (rate limiting)
    for group in batch(inputs, self.rate_limit):
        start = time.monotonic()

        # Download all in group concurrently
        tasks = [fetch_and_save(link, path, client) for link, path in group]
        await asyncio.gather(*tasks)

        # Ensure we don't exceed 1 second per batch (10 req/sec)
        execution_time = time.monotonic() - start
        await asyncio.sleep(max(0, 1 - execution_time))
```

### Request Example
```http
GET https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt
Headers:
  User-Agent: Faliang Wan (wanfaliang88@gmail.com)
  Connection: keep-alive
```

### Response
Complete filing text file (9-12 MB for modern iXBRL filings):

```
<SEC-DOCUMENT>0000320193-24-000123.txt : 20241101
<SEC-HEADER>0000320193-24-000123.hdr.sgml : 20241101
...
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>aapl-20240928.htm
<TEXT>
<html>
  ... full HTML/iXBRL content ...
</html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-31.1
... exhibits ...
</DOCUMENT>
...
```

---

## Complete Flow Example

Let's trace: `python download_filings.py --tickers aapl --type 10-K --count 2`

### Request 1: CIK Lookup
```http
GET https://www.sec.gov/files/company_tickers.json
Response: {"0": {"cik_str": 320193, "ticker": "AAPL", ...}}
Result: AAPL → CIK 0000320193
```

### Request 2: Get Filing List
```http
GET http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K&output=xml&start=0

Response (XML):
<filing>
  <type>10-K</type>
  <filingHREF>https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm</filingHREF>
</filing>
<filing>
  <type>10-K</type>
  <filingHREF>https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm</filingHREF>
</filing>

Result: 2 filing URLs found
```

### Request 3a: Download Filing 1
```http
GET https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt
Response: 9.4 MB text file
Saved to: sec_filings/aapl/10-K/0000320193-24-000123.txt
```

### Request 3b: Download Filing 2 (concurrent with 3a)
```http
GET https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106.txt
Response: 9.2 MB text file
Saved to: sec_filings/aapl/10-K/0000320193-23-000106.txt
```

**Total Requests**: 1 (CIK lookup) + 1 (filing list) + 2 (downloads) = **4 HTTP requests**

---

## Rate Limiting

### SEC Policy
- **Maximum**: 10 requests per second
- **Enforcement**: Temporary IP ban for 10 minutes if exceeded

### How Library Handles It

**Code**: `client.py` lines 257-278

```python
rate_limit = 10  # Requests per second

# Batch downloads into groups of 10
for group in batch(inputs, rate_limit):
    start_time = time.monotonic()

    # Download group concurrently
    await asyncio.gather(*tasks)

    # Ensure 1 second elapsed per batch
    elapsed = time.monotonic() - start_time
    await asyncio.sleep(max(0, 1 - elapsed))
```

**Example**:
- Download 50 files
- Batches: 10, 10, 10, 10, 10
- Each batch takes ~1 second
- Total time: ~5 seconds
- Rate: 50 files / 5 sec = 10 req/sec ✅

---

## HTTP Headers Required

### User-Agent (Required!)
```
User-Agent: Your Name (your.email@example.com)
```

**Why**: SEC fair access policy requires identification

**Code**: All requests include this header
```python
headers = {"User-Agent": self.user_agent}
```

**From Config**:
```python
# .env file
USER_NAME=Faliang Wan
USER_EMAIL=wanfaliang88@gmail.com

# Becomes
User-Agent: Faliang Wan (wanfaliang88@gmail.com)
```

---

## Summary Table

| Step | Endpoint | Purpose | Frequency |
|------|----------|---------|-----------|
| 1 | `https://www.sec.gov/files/company_tickers.json` | Ticker → CIK | Once (cached) |
| 2 | `http://www.sec.gov/cgi-bin/browse-edgar` | Get filing list | 1+ per company |
| 3 | `https://www.sec.gov/Archives/edgar/data/...` | Download filing | Per filing |

## Code Files Reference

| File | Purpose | Key Functions |
|------|---------|---------------|
| `client.py` | HTTP client | `get_response()`, `wait_for_download_async()` |
| `cik_lookup.py` | Ticker→CIK | `get_cik_map()`, `CIKLookup` |
| `core/company.py` | Company filings | `_get_urls_for_cik()`, `save()` |
| `core/_base.py` | Base class | `get_urls_safely()` |

---

## Additional Endpoints (Not Used by Default)

### SEC Viewer (for iXBRL)
```
https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession}&xbrl_type=v
```

Used by `filing_viewer.py` to get rendered HTML view.

### Company Search
```
http://www.sec.gov/cgi-bin/browse-edgar?company={name}&action=getcompany
```

Alternative way to find companies by name.

---

## Want to See the Actual Requests?

Run the debug script:
```bash
python debug_sec_response.py
```

This shows you the exact XML responses from SEC!
