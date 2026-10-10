"""Deterministically recheck saved source anchors for stage 2B evidence."""
from __future__ import annotations
import json, re
from pathlib import Path
from html import unescape
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]

def source_text(source: dict) -> str:
    path=ROOT/source["capture"]["local_path"]
    if source["content_format"] == "pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    raw=path.read_text(encoding="utf-8", errors="replace")
    return unescape(re.sub(r"<[^>]+>", " ", raw))

def norm(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("，",",")

def main() -> int:
    sources={}
    for line in (ROOT/"data/research/source_records.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip(): sources[json.loads(line)["source_id"]]=json.loads(line)
    texts={sid:norm(source_text(src)) for sid,src in sources.items() if src.get("capture",{}).get("status")=="captured" and src["source_id"] in {"SRC_UG_CREDENTIAL_DEGREE_20210317","SRC_UG_CREDENTIAL_DIPLOMA_20210317","SRC_UG_STUDENT_CARD_20190418","SRC_UG_COURSE_SELECTION_20190419","SRC_UG_LEAVE_FORM_PDF_202504","SRC_UG_MAJOR_CHANGE_EXTERNAL_PDF_20250716"}}
    checked=[]; failures=[]
    for line in (ROOT/"data/research/evidence_units.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        evidence=json.loads(line)
        if evidence["item_id"] not in {"UG_CREDENTIAL_REISSUE","UG_STUDENT_CARD_REISSUE","UG_COURSE_SELECTION","UG_LEAVE_REQUEST","UG_MAJOR_CHANGE"}: continue
        haystack=texts.get(evidence["source_id"],"")
        anchor=norm(evidence["source_locator"]["anchor_text"])
        verbatim=norm(evidence["verbatim_text"])
        ok=bool(anchor and verbatim and anchor in haystack and verbatim in haystack)
        checked.append(evidence["evidence_id"])
        if not ok: failures.append((evidence["evidence_id"],evidence["source_id"],evidence["source_locator"]["anchor_text"]))
    print(json.dumps({"checked":len(checked),"failures":failures},ensure_ascii=False))
    return 1 if failures else 0
if __name__ == "__main__": raise SystemExit(main())
