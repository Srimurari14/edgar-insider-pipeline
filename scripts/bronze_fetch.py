# bronze_fetch.py

import re
from scripts.config import BRONZE_PREFIX
from scripts.storage import read_bytes


def fetch_raw_filing(accession: str, filing_date: str) -> dict:
    """
    Fetches the raw bronze XML for one filing, given its accession number
    and filing_date (accepts either 'YYYY-MM-DD' or 'YYYYMMDD').

    Returns {"success": True, "xml": "<...>"} or {"success": False, "error": "..."}.
    Never raises, same contract as run_query, so the agent loop can hand
    a failure back to the model instead of crashing.
    """
    filing_date_compact = filing_date.replace("-", "")
    path = f"{BRONZE_PREFIX}/filing_date={filing_date_compact}/{accession}.txt"

    try:
        raw = read_bytes(path).decode("utf-8", errors="replace")
    except Exception as e:
        return {"success": False, "error": f"Could not fetch bronze file at {path}: {e}"}

    # Strip the SEC header/footer wrapper, same extraction parse.py already
    # does, so the model sees just the filing's actual XML content.
    xml_start = raw.find("<XML>")
    xml_end = raw.find("</XML>")
    if xml_start == -1 or xml_end == -1:
        return {"success": False, "error": "No <XML> block found in this filing"}

    xml_content = raw[xml_start + 5 : xml_end].strip()
    return {"success": True, "xml": xml_content}

def extract_explanation(xml_content: str) -> dict:
    """
    Pulls the <remarks> text and any <footnote> texts out of a filing's raw
    XML, the same two places checked by hand during anomaly investigations.
    Returns {"remarks": str or None, "footnotes": {id: text}}.
    """
    remarks_match = re.search(r"<remarks>(.*?)</remarks>", xml_content, re.DOTALL)
    remarks = remarks_match.group(1).strip() if remarks_match else None

    footnotes = {}
    for match in re.finditer(r'<footnote id="([^"]+)">(.*?)</footnote>', xml_content, re.DOTALL):
        footnotes[match.group(1)] = match.group(2).strip()

    return {"remarks": remarks, "footnotes": footnotes}