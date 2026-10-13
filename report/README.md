# VibeShift mini-project report

Deliverables:

- `VibeShift_MiniProject_Report.docx` — the report (Times New Roman, 16/14/12 pt
  headings, 12 pt justified body at 1.5 spacing, 1-inch margins, 19 pages)
- `VibeShift_MiniProject_Report.pdf` — the same document exported through Word
- `assets/` — every figure, regenerated from the running application
- `data/` — the JSON payloads of the recorded run that the report quotes

## Regenerating

Everything is scripted, so the report can be rebuilt after any code change.

```bash
# 1. start the API and the web app
cd backend && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --host 127.0.0.1 --port 5180

# 2. launch a full-corpus run and save its payloads into report/data/
#    (see the run id in the dashboard, then:)
curl -s "http://127.0.0.1:8000/api/runs/<run-id>/results" -o report/data/results.json

# 3. rebuild the figures
cd backend
.venv/Scripts/python ../report/make_diagrams.py       # diagrams (matplotlib)
node ../report/capture_screenshots.js <run-id>        # UI screenshots (playwright-core)
.venv/Scripts/python ../report/make_montages.py       # multi-panel composites

# 4. build the document, measure it with Word, build again with real page numbers
.venv/Scripts/python ../report/build_report.py
powershell -ExecutionPolicy Bypass -File ../report/word_pagemap.ps1 -Pdf
.venv/Scripts/python ../report/build_report.py
.venv/Scripts/python ../report/verify_report.py       # guideline checks
```

`capture_screenshots.js` needs `playwright-core` and a local Chrome install; set
`PW_ROOT` to the directory that has `node_modules/playwright-core` if it is not
`C:/Users/PC-15/shots`.

## Notes

- The guide's name and the certificate signature blocks are placeholders.
- `word_pagemap.ps1` uses the Word COM interface, so it requires Microsoft Word;
  without it the contents and lists simply build with empty page numbers.
