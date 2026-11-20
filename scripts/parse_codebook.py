"""Parse the BRFSS LLCP codebook HTML into catalog/codebook.json.

Output: {SAS variable name: {label, section, question, values: {code_or_range: value label}}}.
Only the 'values' table rows are parsed (value, value label, frequency, %, weighted %).
"""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

src = Path(sys.argv[1]); out = Path(sys.argv[2])
soup = BeautifulSoup(src.read_text(encoding="latin-1"), "html.parser")


def clean(s: str) -> str:
    s = s.replace("â\x80\x94", " - ").replace("ï¬\x81", "fi").replace("â\x80\x99", "'").replace("Â´", "'").replace("Â", "")
    return re.sub(r"\s+", " ", s).strip()


vars_ = {}
for tbl in soup.find_all("table"):
    head = tbl.find_previous(string=re.compile("SAS Variable Name"))
    # header text sits in the table's first cell block in this codebook layout
    hdr = clean(tbl.get_text(" ")) if False else None
    txt = clean(tbl.get_text(" "))
    m = re.search(r"SAS Variable Name:\s*(\S+)", txt)
    if not m:
        continue
    name = m.group(1)
    lab = re.search(r"Label:\s*(.*?)\s*Section Name:", txt)
    sec = re.search(r"Section Name:\s*(.*?)\s*Section Number", txt)
    q = re.search(r"Question:\s*(.*?)\s*Value Value Label", txt)
    rec = vars_.setdefault(name, {"name": name, "label": lab.group(1) if lab else "",
                                  "section": sec.group(1) if sec else "",
                                  "question": q.group(1) if q else "", "values": {}})
    for tr in tbl.find_all("tr"):
        cells = [clean(td.get_text(" ")) for td in tr.find_all("td")]
        if len(cells) == 5 and re.fullmatch(r"HIDDEN|BLANK|[\d.]+( - [\d.]+)?", cells[0]):
            rec["values"][cells[0]] = cells[1]
ADMIN_SECTIONS = {"Record Identification", "Land Line Introduction", "Cell Phone Introduction"}
KEEP = {"_STATE", "_PSU"}
vars_ = {k: v for k, v in vars_.items()
         if k in KEEP or (v["section"] not in ADMIN_SECTIONS and k[:3] not in ("QST",) and "QSTV" not in k)}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(vars_, indent=1, ensure_ascii=False))
print(len(vars_), "variables")
