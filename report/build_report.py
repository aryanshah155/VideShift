"""Generate the VibeShift mini-project report as a Word document.

Formatting follows the submission guidelines: Times New Roman throughout,
16 pt bold chapter headings, 14 pt bold section headings, 12 pt bold sub-section
headings, 12 pt justified body text at 1.5 line spacing, 1-inch margins, figure
captions below the figure, table captions above the table, and a formal in-text
reference for every figure and table.

    cd backend && .venv/Scripts/python ../report/build_report.py

Reads the recorded run data from report/data/*.json and, when present,
report/pagemap.json (page numbers measured by Word, see report/word_pagemap.ps1)
to fill in the contents and the lists of figures and tables.
"""

from __future__ import annotations

import io
import json
import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "VibeShift_MiniProject_Report.docx")

TITLE = "VibeShift: Big Data Analytics for Acoustic Vibe-Shift Discovery in Popular Music"
STUDENTS = [("Aryan Shah", "30", "232155"), ("Saish Sawant", "25", "232148"),
            ("Nikhil Sharma", "33", "232157")]
GUIDE = "Prof. ________"
DEPARTMENT = "Department of Computer Engineering"
INSTITUTE = "St. Francis Institute of Technology"
AFFILIATION = "An Autonomous Institute, Affiliated to University of Mumbai"
YEAR = "2025-2026"

TBL_FONT = 9


def L(name: str) -> dict:
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


DATASET = L("dataset.json")
RESULTS = L("results.json")
STATUS = L("status.json")
CONCEPTS = L("concepts.json")
BDA = RESULTS["bda"]
DATA_ROWS = int(DATASET.get("rows") or 0)
SILHOUETTE = float(RESULTS.get("silhouette") or 0.0)
ROWS_CLEAN = int(RESULTS["rows_clean"])
TOTAL_SECONDS = float(RESULTS["total_seconds"])

CONTEXT: dict = {"chapter": 0, "figure": {}, "table": {}, "headings": []}


def pagemap() -> dict:
    path = os.path.join(HERE, "pagemap.json")
    if os.path.exists(path):
        with io.open(path, encoding="utf-8-sig") as fh:  # tolerate a PowerShell BOM
            return json.load(fh)
    return {"headings": {}, "figures": {}, "tables": {}, "pages": 0}


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
def _set_font(style, name="Times New Roman"):
    style.font.name = name
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), name)


def setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    _set_font(normal)
    normal.font.size = Pt(12)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(4)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    specs = {
        "Heading 1": (16, WD_ALIGN_PARAGRAPH.CENTER, 10, 6),
        "Heading 2": (14, WD_ALIGN_PARAGRAPH.LEFT, 8, 3),
        "Heading 3": (12, WD_ALIGN_PARAGRAPH.LEFT, 6, 2),
        "Title": (18, WD_ALIGN_PARAGRAPH.CENTER, 0, 6),
    }
    for name, (size, align, before, after) in specs.items():
        style = doc.styles[name]
        _set_font(style)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.alignment = align
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.keep_with_next = True

    caption = doc.styles["Caption"]
    _set_font(caption)
    caption.font.size = Pt(11)
    caption.font.bold = False
    caption.font.italic = True
    caption.font.color.rgb = RGBColor(0, 0, 0)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.line_spacing = 1.0
    caption.paragraph_format.space_before = Pt(2)
    caption.paragraph_format.space_after = Pt(6)


def page_setup(section) -> None:
    section.page_width = Inches(8.27)      # A4
    section.page_height = Inches(11.69)
    for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, attr, Inches(1))


def add_page_number_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instr, end):
        run._r.append(node)


def restart_page_numbering(section) -> None:
    sect_pr = section._sectPr
    pg = sect_pr.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        sect_pr.append(pg)
    pg.set(qn("w:start"), "1")


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #
def para(doc, text: str, style: str | None = None, align=None, size=None,
         bold=False, space_after=None):
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def bullets(doc, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(1)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def chapter(doc, number: int, title: str, first: bool = False) -> None:
    """Chapter heading; chapters flow continuously to respect the page budget."""
    CONTEXT["chapter"] = number
    heading = doc.add_heading(f"Chapter {number}: {title}", level=1)
    if first:
        heading.paragraph_format.page_break_before = True
    CONTEXT["headings"].append((1, str(number), title))


def section(doc, number: str, title: str) -> None:
    doc.add_heading(f"{number} {title}", level=2)
    CONTEXT["headings"].append((2, number, title))


def subsection(doc, number: str, title: str) -> None:
    doc.add_heading(f"{number} {title}", level=3)
    CONTEXT["headings"].append((3, number, title))


def _next_key(store: dict) -> str:
    prefix = f"{CONTEXT['chapter']}."
    return f"{CONTEXT['chapter']}.{sum(1 for k in store if k.startswith(prefix)) + 1}"


def figure(doc, filename: str, caption: str, width: float = 5.2) -> str:
    key = _next_key(CONTEXT["figure"])
    CONTEXT["figure"][key] = caption
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(os.path.join(ASSETS, filename), width=Inches(width))
    cap = doc.add_paragraph(style="Caption")
    cap.add_run(f"Figure {key}: {caption}")
    return key


def table(doc, caption: str, header: list[str], rows: list[list[str]],
          widths=None, font: int = TBL_FONT) -> str:
    key = _next_key(CONTEXT["table"])
    CONTEXT["table"][key] = caption

    cap = doc.add_paragraph(style="Caption")
    cap.add_run(f"Table {key}: {caption}")
    cap.paragraph_format.space_after = Pt(2)
    cap.paragraph_format.keep_with_next = True

    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True
    for i, text in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(font)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        _shade(cell, "EDEDED")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.add_run(str(text)).font.size = Pt(font)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Inches(w)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    spacer.paragraph_format.line_spacing = 1.0
    return key


def _shade(cell, hex_fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _mini_table(doc, header: list[str], rows: list[list[str]], font: int = 9) -> None:
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, text in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(font)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        _shade(cell, "EDEDED")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.add_run(str(text)).font.size = Pt(font)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)


# --------------------------------------------------------------------------- #
# Front matter
# --------------------------------------------------------------------------- #
def front_matter(doc: Document) -> None:
    para(doc, TITLE, style="Title", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "BDA mini project submitted in partial fulfillment of the requirements of the "
              "degree of", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "B. E.  Computer Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    para(doc, "By", align=WD_ALIGN_PARAGRAPH.CENTER)

    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    for i, head in enumerate(("Name", "Roll No", "PID No")):
        p = t.rows[0].cells[i].paragraphs[0]
        run = p.add_run(head)
        run.bold = True
        run.font.size = Pt(12)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _shade(t.rows[0].cells[i], "EDEDED")
    for name, roll, pid in STUDENTS:
        cells = t.add_row().cells
        for i, value in enumerate((name, roll, pid)):
            p = cells[i].paragraphs[0]
            p.add_run(value).font.size = Pt(12)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, "", space_after=2)
    para(doc, f"Name of the Guide: {GUIDE}", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "Designation: Assistant Professor", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "", space_after=2)
    para(doc, DEPARTMENT, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, INSTITUTE, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, "(Engineering College)", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, AFFILIATION, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, YEAR, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)

    # ---- certificate ----------------------------------------------------- #
    doc.add_page_break()
    para(doc, "CERTIFICATE", style="Heading 1")

    names = ", ".join(f"{n} (Roll No. {r}, PID {p})" for n, r, p in STUDENTS)
    para(doc, f"This is to certify that the mini project entitled \u201c{TITLE}\u201d is a bonafide work "
              f"of {names}, submitted to the University of Mumbai in partial fulfillment of the "
              "requirement for the Big Data Analytics (CSC702) subject in the final year of "
              "Computer Engineering. The work was carried out under my supervision and has not "
              "been submitted to any other university for the award of any degree or diploma.")
    para(doc, "", space_after=14)
    para(doc, "Ms. ______________________        Guide", align=WD_ALIGN_PARAGRAPH.RIGHT)

    # ---- declaration (same page) ----------------------------------------- #
    para(doc, "DECLARATION", style="Heading 1")
    para(doc, "We declare that this written submission represents our ideas in our own words and "
              "that where others' ideas or words have been included, we have adequately cited and "
              "referenced the original sources. We further declare that we have adhered to all "
              "principles of academic honesty and integrity and have not misrepresented, "
              "fabricated or falsified any idea, data, fact or source in this submission.")
    for name, roll, _pid in STUDENTS:
        para(doc, f"______________________    {name}   (Roll No. {roll})",
             align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=2)
    para(doc, "Date:", align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=2)

    # the abstract gets its own page so it is never split across two
    doc.add_page_break()
    para(doc, "ABSTRACT", style="Heading 1")
    para(doc, f"VibeShift is a full-stack big data analytics application that quantifies how the "
              f"acoustic character of popular music has shifted across release decades. The corpus "
              f"is the public Spotify \u201c1.2M+ Songs\u201d dataset: {DATA_ROWS:,} tracks described "
              f"by 24 attributes, of which eight audio features form the analysis vector. Rows are "
              f"cleaned, standardised, clustered with K-Means and projected with PCA; the per-track "
              f"assignments are aggregated into a decade \u00d7 cluster matrix that exposes the vibe "
              f"shift, and each cluster is named from its own measured profile. A background runner "
              f"executes fifteen instrumented stages per run and streams their timings to the "
              f"browser. Beyond the clustering pipeline the project implements a Big Data Analytics "
              f"suite mapped to the CSC702 laboratory manual: an in-process MapReduce runtime with "
              f"per-phase counters, MongoDB persistence of schemaless run documents, statistical "
              f"profiling and visualization, an HDFS placement simulation, a Bloom-filter membership "
              f"index, similarity-graph mining, streaming micro-batches and supervised model "
              f"selection. The core portion of this report is MapReduce (Experiments 4 and 5), "
              f"MongoDB/NoSQL (Experiment 3) and statistics with visualization (Experiment 8); the "
              f"remaining analyses run on every execution and are reported as supporting evidence. A "
              f"full-corpus run finishes in {TOTAL_SECONDS:.0f} seconds on one machine and reaches a "
              f"silhouette score of {SILHOUETTE:.3f} for five clusters.")


def lists_and_contents(doc: Document, pm: dict) -> None:
    pages = pm.get("headings", {})

    doc.add_page_break()
    para(doc, "CONTENTS", style="Heading 1")
    _mini_table(doc, ["Chapter / Section", "Title", "Page"],
                [[("" if level == 3 else number), title, str(pages.get(
                    f"Chapter {number}: {title}" if level == 1 else f"{number} {title}", ""))]
                 for level, number, title in CONTEXT["headings"]
                 ] + [["References", "", str(pages.get("REFERENCES", ""))],
                      ["Acknowledgements", "", str(pages.get("ACKNOWLEDGEMENTS", ""))]],
                font=10)

    doc.add_page_break()
    para(doc, "LIST OF FIGURES", style="Heading 1", size=14)
    _mini_table(doc, ["Fig. No.", "Figure Caption", "Page"],
                [[k, CONTEXT["figure"][k], str(pm.get("figures", {}).get(k, ""))]
                 for k in sorted(CONTEXT["figure"], key=_key_sort)], font=9)

    para(doc, "LIST OF TABLES", style="Heading 1", size=14)
    _mini_table(doc, ["Table No.", "Table Caption", "Page"],
                [[k, CONTEXT["table"][k], str(pm.get("tables", {}).get(k, ""))]
                 for k in sorted(CONTEXT["table"], key=_key_sort)], font=9)

    para(doc, "LIST OF ABBREVIATIONS", style="Heading 1", size=14)
    _mini_table(doc, ["Sr. No.", "Abbreviation", "Expanded form"],
                [[str(i), short, long_form] for i, (short, long_form) in enumerate([
                    ("API", "Application Programming Interface"),
                    ("BDA", "Big Data Analytics"),
                    ("DFD", "Data Flow Diagram"),
                    ("HDFS", "Hadoop Distributed File System"),
                    ("k-NN", "k-Nearest Neighbours"),
                    ("NoSQL", "Not Only SQL"),
                    ("PCA", "Principal Component Analysis"),
                    ("REST", "Representational State Transfer"),
                    ("SPA", "Single Page Application"),
                ], start=1)], font=9)


def _key_sort(key: str):
    major, minor = key.split(".")
    return int(major), int(minor)


# --------------------------------------------------------------------------- #
# Chapters
# --------------------------------------------------------------------------- #
def chapter_1(doc) -> None:
    chapter(doc, 1, "Introduction", first=True)

    section(doc, "1.1", "Description")
    para(doc, "Popular music changes character over time: recordings from the 1960s are dominated by "
              "acoustic, low-energy material, while the 2010s are dominated by loud, electronic, "
              "high-energy productions. Streaming platforms describe every track with a numeric "
              "audio feature vector, which makes that change measurable at corpus scale. VibeShift "
              "ingests a public Spotify corpus, clusters its tracks by acoustic similarity and "
              "presents the resulting decade-by-decade \u201cvibe shift\u201d as interactive "
              "dashboards. It is a three-tier system: a React single page application, a FastAPI "
              "service that executes the pipeline on a background worker, and a persistence layer "
              "that keeps every run as a MongoDB document beside columnar Parquet files. Alongside "
              "the clustering pipeline it implements the techniques of the CSC702 laboratory manual "
              "\u2013 distributed storage, MapReduce, NoSQL, probabilistic data structures, graph "
              "mining, stream processing, supervised learning and visualization \u2013 and shows the "
              "live evidence each of them produces.")

    section(doc, "1.2", "Problem Formulation")
    para(doc, "Given a corpus of tracks D = {(x_i, y_i)}, where x_i is the feature vector of track "
              "i and y_i its release year, the task is to partition the corpus into k acoustically "
              "coherent groups, express the composition of each release decade as a distribution "
              "over those groups, and present the movement of those distributions over time with "
              "the evidence of every technique used to obtain it. The clustering step therefore "
              "minimises the within-cluster sum of squares over k centroids after standardisation, "
              "and the aggregation step computes P(decade | cluster) as a percentage matrix. Three "
              "practical difficulties must be handled: the corpus is large enough that a naive "
              "implementation is wasteful, it is dirty (malformed years, duplicate identifiers, "
              "quoted fields containing commas), and the clusters K-Means returns are unlabelled "
              "integers whose meaning has to be derived before anything can be reported.")

    section(doc, "1.3", "Motivation")
    para(doc, "The project began as a Colab notebook that ran the same pipeline interactively. The "
              "analytics were correct, but every parameter change required re-running cells, no "
              "result was persisted and none of the distributed techniques of the manual were "
              "exercised. The motivation was to turn that notebook into a system whose runs are "
              "configurable, persisted and auditable, and to make the analytics themselves the "
              "subject of the application.")

    section(doc, "1.4", "Proposed Solution")
    para(doc, "A run is submitted from the dashboard and executed by a background worker in fifteen "
              "stages: ingest, clean, assemble, K-Means, PCA, aggregate, benchmark and eight Big "
              "Data Analytics analyses. Each stage writes progress, counters and timings into the "
              "run document, so the browser can show a live console and the results page can "
              "justify every number it displays. The pipeline is engine-agnostic: a PySpark MLlib "
              "implementation is used when Spark is importable and a single-node pandas and "
              "scikit-learn implementation with stage-for-stage parity otherwise, with the active "
              "engine and the reason for the choice shown on the dashboard.")

    section(doc, "1.5", "Scope of the Project")
    para(doc, "In line with the selected scope, MapReduce (Experiments 4 and 5), NoSQL persistence "
              "with MongoDB (Experiment 3) and statistical computing with visualization "
              "(Experiment 8) form the core portion of the project and receive the detailed "
              "treatment in this report. The remaining analyses \u2013 HDFS simulation, Bloom "
              "filter, similarity-graph mining, streaming windows and supervised learning \u2013 stay "
              "implemented, run on every execution and are reported as supporting evidence. A "
              "single-node deployment, the public corpus, reproducible notebook export and the web "
              "interface are in scope; a multi-node cluster, live streaming from a production "
              "broker, user accounts and paid infrastructure are out of scope.")


def chapter_2(doc) -> None:
    chapter(doc, 2, "Review of Literature")
    para(doc, "The project draws on three literatures: the programming models used to process "
              "large datasets, the unsupervised learning used to summarise them, and the "
              "visualization that makes the summary readable. Dean and Ghemawat introduced "
              "MapReduce, showing that a restricted map/shuffle/reduce interface can be "
              "parallelised automatically while retaining fault tolerance [1]; Hadoop packaged it "
              "with the Hadoop Distributed File System, which splits files into fixed-size blocks "
              "and replicates them rack-aware across DataNodes [2]; Spark kept intermediate data "
              "in memory and exposed MLlib, whose K-Means and PCA implementations underlie the "
              "pipeline used here [3]. For the analytical core, MacQueen's k-means formulation [4] "
              "and the treatment of principal component analysis in Hastie et al. [5] provide the "
              "basis, while the silhouette criterion reported for cluster quality comes from "
              "Rousseeuw [6]. Similarity analysis is more recent: Newman's modularity [7] underlies "
              "the community detection and PageRank [8] supplies the centrality measure; Bloom's "
              "probabilistic structure [9] indexes the corpus vocabulary, and the event-time "
              "windowing model follows the Dataflow abstraction of Akidau et al. [10].")
    para(doc, "On the storage side the MongoDB manual documents the document model, reflection, "
              "queries and the aggregation pipeline [11], and Kleppmann [12] analyses the "
              "trade-offs that motivate keeping schemaless run records beside columnar track "
              "files. Commercial services such as the Spotify audio-features API [13] expose "
              "per-track descriptors but leave cross-decade aggregation to the consumer. Table 2.1 "
              "compares the available approaches with VibeShift.")
    table(doc, "Comparison of related approaches with VibeShift",
          ["Approach", "Processing model", "Cross-decade analysis", "Evidence of techniques"],
          [["Colab notebook (baseline)", "Single-node, manual cells", "Ad hoc tables and plots",
            "None \u2013 results are not persisted"],
           ["Spark MLlib clustering", "Distributed K-Means / PCA", "Requires custom aggregation",
            "Cluster metrics only"],
           ["Spotify audio-features API", "Hosted per-track lookup", "Not provided", "Not applicable"],
           ["VibeShift (this project)", "Engine-agnostic 15-stage runner", "Decade \u00d7 cluster shares",
            "Per-technique counters in the UI"]],
          widths=[1.7, 1.7, 1.6, 1.4])


def chapter_3(doc) -> None:
    chapter(doc, 3, "System Analysis")

    section(doc, "3.1", "Functional Requirements")
    para(doc, "The functional requirements follow the workflow of the analyst who uses the "
              "application: inspect the corpus, configure a run, watch it execute, study the "
              "results and export the evidence. Table 3.1 lists them with the interface element or "
              "service that satisfies each one.")
    table(doc, "Functional requirements",
          ["ID", "Requirement", "Satisfied by"],
          [["FR1", "Detect the corpus and report its size, row/column count and real year range",
            "Dataset status API"],
           ["FR2", "Configure k, the year window (bounded by the dataset), features, best-k sweep and sampling",
            "Dashboard run configuration"],
           ["FR3", "Execute the pipeline asynchronously and stream per-stage status, log and timings",
            "Runner thread and run status API"],
           ["FR4", "Cluster the corpus, project it with PCA and aggregate decade \u00d7 cluster shares",
            "clean / assemble / kmeans / pca / aggregate stages"],
           ["FR5", "Execute the Big Data Analytics suite and record a counter for every analysis",
            "Eight analytics stages"],
           ["FR6", "Map each concept to its experiment and show the live metric it produced",
            "Concepts API and page"],
           ["FR7", "Browse and filter tracks, persist runs, export a Colab notebook",
            "Track store, run store, notebook route"]],
          widths=[0.45, 3.6, 2.1])

    section(doc, "3.2", "Non-Functional Requirements")
    subsection(doc, "3.2.1", "Performance Requirements")
    para(doc, f"A full-corpus run must finish within two minutes on one machine; the recorded run "
              f"over {DATA_ROWS:,} rows took {TOTAL_SECONDS:.1f} seconds, of which "
              f"{RESULTS['timings']['kmeans']:.1f} seconds were K-Means and "
              f"{BDA['summary']['seconds']:.1f} seconds the eight analyses. The API must never "
              f"block while a run executes, and quadratic work must be bounded: silhouette scoring "
              f"uses a random sample of 8,000 rows and the analytics use capped samples whose "
              f"sizes are reported in the interface. Vectorised aggregation is benchmarked against "
              f"a naive row loop on every run, which measured a "
              f"{RESULTS['benchmark']['speedup']:.1f}\u00d7 speed-up here.")
    bullets(doc, [
        "Responsiveness: status polling stays well under a second while a run executes.",
        "Reliability: a failing analytics stage must not fail the run.",
        "Portability: the pipeline runs with or without PySpark on the same instruction set.",
        "Reproducibility: fixed seeds and an exportable notebook for every run.",
    ])
    subsection(doc, "3.2.2", "Software Quality Attributes")
    para(doc, "Usability is addressed by a task-oriented interface with a live console, so a long "
              "analysis never looks stalled. Auditability is treated as a first-class attribute: "
              "every displayed number is traceable to a stage counter and the concepts page names "
              "the JSON path holding each metric. Correctness is protected by tests of the cleaning "
              "rules, the engine contract, the CSV reader, the label derivation and the API "
              "lifecycle.")

    section(doc, "3.3", "Specific Requirements")
    table(doc, "Hardware and software requirements",
          ["Category", "Requirement"],
          [["Processor and memory",
            "x86-64 dual-core minimum, quad-core recommended; 8 GB RAM minimum, 16 GB recommended "
            "(the 330 MB CSV expands to about 2 GB in memory)"],
           ["Storage", "2 GB free for the corpus, run artefacts and dependencies"],
           ["Operating system", "Windows 10/11, Linux or macOS with a Python 3.11+ runtime"],
           ["Runtime and libraries",
            "Python with FastAPI, pandas, NumPy, scikit-learn and pymongo; Node.js with React and Vite"],
           ["Database and tooling",
            "MongoDB Community Server with JSON fallback; optional JDK for the PySpark engine"]],
          widths=[1.4, 4.7])

    para(doc, "Table 3.2 lists the hardware and software the implementation requires at run time.")

    section(doc, "3.4", "Use-Case Diagram and Description")
    para(doc, "Figure 3.1 shows the actors and use cases. The researcher drives every use case; the "
              "corpus and the persistence layer are supporting actors. The use cases drawn in green "
              "\u2013 inspecting MapReduce statistics, querying the MongoDB run documents and "
              "reading the visualization dashboards \u2013 are the core portion of this project.")
    figure(doc, "fig_usecase.png", "Use-case diagram of VibeShift", width=4.5)
    para(doc, "The primary use case is the scenario exercised whenever the application answers an "
              "analytical question. It is triggered by submitting a run configuration; its main "
              "flow shows the corpus profile, accepts k and the year window, streams the fifteen "
              "stage updates and renders the heatmaps, the PCA map and the analytics panels. If a "
              "stage fails, the run is marked failed with its traceback while the remaining "
              "analyses still complete, and the post-condition is that the run document, the "
              "Parquet track store and the exported notebook are persisted.")


def chapter_4(doc) -> None:
    chapter(doc, 4, "Analysis Modeling")

    section(doc, "4.1", "Class Diagram and Activity Diagram")
    para(doc, "Figure 4.1 shows the static structure of the backend. The FastAPI routers translate "
              "HTTP requests into calls on two collaborating components: the runner, which owns the "
              "worker pool and the run documents, and the engine, which performs the numerical "
              "work. The analytics suite is a third component that consumes the labelled track "
              "frame, so no analysis depends on the internals of the clustering implementation, and "
              "the store isolates persistence, which is why the application still works with a JSON "
              "fallback when MongoDB is unavailable. In time, a run follows the same decomposition: "
              "ingestion, cleaning, vector assembly, clustering, projection and aggregation execute "
              "in sequence, then the eight analyses branch from the labelled frame and write their "
              "evidence into the same run document; Section 6.1 records the measured cost of each "
              "stage.")
    figure(doc, "fig_class.png", "Class diagram of the backend components", width=4.7)

    section(doc, "4.2", "Functional Modelling")
    para(doc, "The data-flow view in Figure 4.2 shows the same system at two levels. At level 0 the "
              "researcher supplies a run configuration and receives heatmaps, metrics and concept "
              "evidence, while the corpus supplies audio features. At level 1 the processing is "
              "decomposed into ingestion and cleaning, vector assembly and clustering, decade "
              "aggregation and the analytics suite; data stores D1 (the corpus), D2 (the run "
              "documents) and D3 (the per-run Parquet track store) hold the artefacts that flow "
              "between them.")
    figure(doc, "fig_dfd.png", "Data-flow diagram: context (level 0) and decomposition (level 1)",
           width=4.7)


def chapter_5(doc) -> None:
    chapter(doc, 5, "Design")

    section(doc, "5.1", "Architectural Design")
    para(doc, "VibeShift is designed as a three-tier application, shown in Figure 5.1. The "
              "presentation tier holds no analytical logic: it renders what the API reports and "
              "polls run status while a job is in flight. The application tier owns the pipeline, "
              "the engines and the analytics suite, exposes a small REST surface and keeps "
              "long-running work off the request path. The data tier separates three artefact types "
              "by access pattern \u2013 the immutable corpus, the schemaless run documents and the "
              "columnar per-run track store \u2013 so the track explorer can filter a million rows "
              "without reading run metadata. Three decisions deserve justification: the engine "
              "abstraction makes the same configuration runnable with or without a JVM; stages "
              "write structured counters rather than log text, which is what lets the concepts page "
              "quote a live metric; and the analytics stages fail in isolation, so an unavailable "
              "MongoDB degrades one panel instead of failing the run.")
    figure(doc, "fig_architecture.png", "Overall system architecture of VibeShift", width=5.0)
    para(doc, "Table 5.1 summarises the technology chosen for each layer.")
    table(doc, "Technology stack",
          ["Layer", "Technology", "Role in the system"],
          [["Front end", "React 18, Vite, Tailwind CSS, Recharts",
            "Dashboard, results, concepts and explorer pages"],
           ["API and execution", "FastAPI on uvicorn [15], worker thread pool",
            "REST endpoints, asynchronous stage execution and status"],
           ["Engines", "PySpark MLlib (primary), pandas and scikit-learn [14] (fallback)",
            "Vector assembly, standardisation, K-Means and PCA"],
           ["Analytics suite", "In-project MapReduce, Bloom, graph, streaming and ML modules",
            "Laboratory-manual techniques applied to the real records"],
           ["Persistence", "MongoDB with JSON fallback, Parquet",
            "Run documents, track store and notebook export"]],
          widths=[1.2, 2.6, 2.3])

    section(doc, "5.2", "User Interface Design")
    para(doc, "The interface is organised around the lifecycle of an experiment rather than around "
              "the code structure. Figure 5.2 shows the dashboard: the corpus card reports the real "
              "profile of the dataset, including the year bounds the configuration inputs inherit, "
              "the engine card explains which engine will execute the run, and the configuration "
              "card exposes k, the year window, feature toggles and sampling; panel (d) shows the "
              "live console and the run history, so a completed experiment can be reopened instead "
              "of repeated.")
    figure(doc, "fig_ui_dashboard.png",
           "Dashboard: corpus profile, run configuration, live console and run history", width=5.6)
    para(doc, "Figure 5.3 shows the results page, the analytical centre of the application. The "
              "decade \u00d7 cluster heatmap in panel (b) is the primary visualization: each row is "
              "a release decade, each column a cluster and each cell the percentage of that "
              "decade's tracks the cluster contains. Panel (c) documents what each cluster means "
              "through its mean feature profile and size, and panel (d) shows the PCA projection "
              "and the per-decade feature trends that corroborate the heatmap.")
    figure(doc, "fig_ui_results.png",
           "Results page: headline metrics, vibe-shift heatmap, cluster profiles and projection",
           width=5.6)


def chapter_6(doc) -> None:
    chapter(doc, 6, "Implementation")
    ds, rs, bda = DATASET, RESULTS, BDA
    nosql, eda = bda["nosql"], bda["eda"]

    section(doc, "6.1", "Working of the Project")
    para(doc, f"A run begins by reading the corpus. The recorded run ingested {rs['rows_ingested']:,} "
              f"rows from a {ds['size_mb']:.0f} MB CSV file and retained {rs['rows_clean']:,} rows "
              f"after cleaning. Cleaning performs the fixes the corpus demands: years are cast "
              f"through a float so values such as 2004.0 parse, non-positive years are dropped, "
              f"features are coerced to numeric with malformed values becoming missing, rows with "
              f"missing features are removed, duplicate track identifiers are collapsed and a "
              f"decade column is derived. Vector assembly standardises the eight features with the "
              f"population standard deviation to match Spark's StandardScaler, so both engines "
              f"cluster identical matrices. Table 6.1 describes the corpus and Table 6.2 records "
              f"the measured cost of each stage with the headline metrics of the run.")
    table(doc, "Description of the corpus used for the recorded run",
          ["Property", "Value"],
          [["Source", "Public Spotify \u201c1.2M+ Songs\u201d dataset (tracks_features.csv)"],
           ["Size and shape", f"{ds['size_mb']} MB, {ds['rows']:,} rows, {ds['columns']} columns"],
           ["Release years",
            f"{ds['year_min']}\u2013{ds['year_max']} for valid rows ({ds['year_invalid_rows']} "
            f"invalid years excluded); 99% of tracks fall in {ds['year_p01']}\u2013{ds['year_p99']}"],
           ["Clustering features",
            "danceability, energy, valence, tempo, acousticness, instrumentalness, loudness, speechiness"],
           ["Analysed rows", f"{rs['rows_ingested']:,} ingested, {rs['rows_clean']:,} clean"]],
          widths=[1.4, 4.7])
    table(doc, "Measured pipeline cost and headline metrics for the recorded run",
          ["Stage", "Measure", "Value"],
          [["ingest", "rows read from the CSV file", f"{rs['rows_ingested']:,}"],
           ["clean", "rows retained after cleaning", f"{rs['rows_clean']:,}"],
           ["assemble", "standardised matrix assembly", f"{rs['timings']['assemble']:.2f} s"],
           ["k-means", "fit time for k = 5", f"{rs['timings']['kmeans']:.2f} s"],
           ["pca and aggregate", "projection and decade \u00d7 cluster aggregation",
            f"{rs['timings']['pca']:.2f} s and {rs['timings']['aggregate']:.2f} s"],
           ["benchmark", "vectorised versus naive loop aggregation",
            f"{rs['benchmark']['speedup']:.1f}\u00d7 faster"],
           ["analytics suite", "eight analyses",
            f"{bda['summary']['seconds']:.1f} s, {bda['summary']['analyses_ok']} of "
            f"{bda['summary']['analyses_total']} successful"],
           ["whole run", "runner wall time", f"{rs['total_seconds']:.1f} s"],
           ["quality", "silhouette and inertia for k = 5",
            f"{rs['silhouette']:.3f} and {rs['inertia']:,.0f}"]],
          widths=[1.3, 2.7, 2.1])

    section(doc, "6.2", "MapReduce \u2013 Core Portion (Experiments 4 and 5)")
    word, agg = bda["mapreduce"]["jobs"][0], bda["mapreduce"]["jobs"][1]
    para(doc, "The MapReduce implementation is an in-process runtime with the phases a distributed "
              "job would exhibit: each map task emits key-value pairs, a combiner aggregates them "
              "locally, pairs are partitioned by crc32(key) modulo the reducer count, and each "
              "reducer receives one partition. Every phase is timed and counted, which is what "
              f"makes the inspector in Figure 6.3(a) an inspection rather than a description. "
              f"Figure 6.1 shows the model with the counters recorded for the word-count job. The word-count "
              f"job over track titles emitted {word['stats']['map_output_pairs']:,} map output "
              f"pairs and the combiner cut them to {word['stats']['combine_output_pairs']:,}, "
              f"removing {word['stats']['combine_saved_pct']:.1f}% of the shuffle volume; the "
              f"per-decade aggregate job absorbed {agg['stats']['combine_saved_pct']:.2f}% of its "
              f"pairs. Five jobs run over a {bda['mapreduce']['input_rows']:,}-row sample on every "
              f"run, so the runtime stays bounded while the statistics remain real. The same "
              f"framework implements the map-side join that attaches cluster labels, a top-N "
              f"ranking by energy and the inverted index that backs the search box.")
    figure(doc, "fig_mapreduce.png",
           "MapReduce execution model with the counters recorded for the word-count job", width=5.1)

    section(doc, "6.3", "NoSQL Persistence with MongoDB \u2013 Core Portion (Experiment 3)")
    para(doc, f"Every run is persisted as one document in the {nosql['database']}."
              f"{nosql['collection']} collection, which held {nosql['stats']['documents']} documents "
              f"of {nosql['stats']['avg_obj_size']:,} bytes on average in the recorded run "
              f"(backend {nosql['backend']}, connected = {str(nosql['connected']).lower()}). The "
              f"document model is a deliberate NoSQL decision: a run has a nested array of stage "
              f"records whose length grows as the pipeline grows, an embedded configuration whose "
              f"shape differs between runs with and without the best-k sweep, and a log array, none "
              f"of which maps cleanly onto fixed relational columns. The console in Figure 6.3(b) "
              f"reflects over the collection to enumerate the field paths and their types, reports "
              f"live collection statistics, shows a sample document and lists the queries and "
              f"aggregation stages the application issues. It is read-only, so an inspection cannot "
              f"mutate the store, and when MongoDB is unavailable the same panel is served from the "
              f"JSON fallback.")

    section(doc, "6.4", "Statistical Computing and Visualization \u2013 Core Portion (Experiment 8)")
    strongest = eda["strongest_pairs"]
    para(doc, f"The statistics module profiles all eight features over the {eda['rows']:,} clean rows "
              f"\u2013 count, mean, standard deviation, quartiles, skewness and kurtosis \u2013 and "
              f"computes the full Pearson correlation matrix. The strongest relationships are "
              f"{strongest[0]['a']}\u2013{strongest[0]['b']} (r = {strongest[0]['r']:.2f}), "
              f"{strongest[1]['a']}\u2013{strongest[1]['b']} (r = {strongest[1]['r']:.2f}) and "
              f"{strongest[2]['a']}\u2013{strongest[2]['b']} (r = {strongest[2]['r']:.2f}); the "
              f"last two are two views of the same signal, and together they explain why the "
              f"acoustic and high-energy clusters separate so cleanly in feature space. The module "
              f"also reports outlier counts on a robust z-score criterion and re-scores the "
              f"features by variance contribution.")
    para(doc, "Visualization is where the analyses meet the clustering results. Figure 6.2(a) "
              "reproduces the correlation heatmap rendered from those statistics and Figure 6.2(b) "
              "plots the cluster sizes beside the stacked decade composition, which is the heatmap "
              "of Figure 5.3(b) expressed as a distribution. Together they show the finding the "
              "project was built to measure: the acoustic and instrumental clusters dominate the "
              "earliest decades, their share falls after the 1970s, and the high-energy electronic "
              "cluster grows from a marginal presence in the 1960s to the largest single share of "
              "the 2010s.")
    figure(doc, "fig_analytics.png",
           "Statistics and visualization: correlation matrix and cluster/decade composition", width=5.6)

    section(doc, "6.5", "Additional Big Data Analytics Analyses")
    para(doc, "The remaining techniques of the manual are executed on every run and reported as "
              "supporting evidence. The HDFS analysis models the corpus as a replicated file on a "
              "four-node, two-rack cluster and reports the block map and DataNode occupancy. The "
              "Bloom filter indexes the artist vocabulary with a "
              f"{bda['bloom']['production']['m']:,}-bit array and "
              f"{bda['bloom']['production']['k']} hash functions; probing it with 2,000 terms "
              f"produced no false negatives, which is what makes it safe for the membership verdict "
              f"in the track explorer. The graph analysis builds a k-nearest-neighbour similarity "
              f"graph and detects communities, reporting degree, modularity and PageRank "
              f"centralities. The streaming analysis replays the corpus as an event-time stream in "
              f"{bda['streaming']['stats']['batches']} micro-batches with a sliding window and "
              f"detects {bda['streaming']['stats']['drift_count']} drift points, a quantitative "
              f"statement about when the corpus stops being stationary. The supervised analysis "
              f"frames \u201cis this track modern?\u201d as a classification task and selects "
              f"between three models by F1 and ROC AUC, and retains "
              f"{bda['ml']['supervised']['best']['name']} as the best with an accuracy of "
              f"{bda['ml']['supervised']['best']['accuracy']:.3f}. Table 6.3 lists the analyses "
              f"with the metric each produced, and Figure 6.3 shows their interface panels.")
    table(doc, "Big Data Analytics analyses executed in the recorded run",
          ["Analysis", "Exp.", "Technique", "Evidence produced"],
          [["HDFS and Hadoop", "1", "Block splitting, 3\u00d7 replication, rack-aware placement",
            f"{bda['hdfs']['file']['blocks']} blocks, {bda['hdfs']['file']['size_human']}"],
           ["MapReduce", "4 and 5", "map, partition, combine, shuffle, reduce",
            f"5 jobs, {sum(j['stats']['map_output_pairs'] for j in bda['mapreduce']['jobs']):,} map output pairs"],
           ["Bloom filter", "6", "Bit array with k hash functions, tunable false-positive rate",
            f"m = {bda['bloom']['production']['m']:,}, k = {bda['bloom']['production']['k']}, "
            f"empirical FPR {bda['bloom']['production']['empirical_fpr']}, no false negatives"],
           ["Graph mining", "7", "k-NN similarity graph, communities, PageRank",
            f"{bda['graph']['stats']['nodes']} nodes, {bda['graph']['stats']['edges']} edges, "
            f"modularity {bda['graph']['stats']['modularity']:.3f}"],
           ["Stream processing", "CO4", "Event-time micro-batches, sliding window, drift detection",
            f"{bda['streaming']['stats']['batches']} batches, {bda['streaming']['stats']['drift_count']} drift points"],
           ["Supervised learning", "2", "Train/test split, three models, F1 and ROC AUC",
            f"best {bda['ml']['supervised']['best']['name']}, accuracy "
            f"{bda['ml']['supervised']['best']['accuracy']:.3f}"],
           ["NoSQL (MongoDB)", "3", "Schemaless documents, reflection, queries, aggregation",
            f"{nosql['stats']['documents']} documents in {nosql['database']}.{nosql['collection']}"],
           ["Statistics and visualization", "8", "Descriptive statistics, correlation, charts",
            f"{len(eda['stats'])} feature profiles, correlation matrix over "
            f"{eda['rows']:,} rows"]],
          widths=[1.35, 0.6, 2.15, 2.0], font=8)
    figure(doc, "fig_ui_bda.png",
           "Big Data Analytics suite: MapReduce inspector, NoSQL console, statistics panel and "
           "additional analyses", width=5.6)

    section(doc, "6.6", "Concept Catalogue and Track Explorer")
    cov = CONCEPTS["coverage"]
    para(doc, f"The interface also makes the coverage of the manual explicit. The catalogue holds "
              f"{cov['concepts']} concepts across {cov['experiments']} experiment groups; "
              f"{cov['with_evidence']} carry a live metric from the selected run and "
              f"{cov['core_concepts']} are marked as the core portion of this project. Each concept "
              f"is listed with its experiment, what it means, how it is implemented and the number "
              f"it produced, followed by the JSON path holding the evidence so a reviewer can "
              f"verify it. The track explorer filters the per-track cluster assignments by cluster "
              f"or decade and searches by title; the search box issues a Bloom-filter membership "
              f"query on the server and prints the verdict with the probability of a false "
              f"positive, connecting the probabilistic data structure to a visible feature.")


def chapter_7(doc) -> None:
    chapter(doc, 7, "Conclusion")
    para(doc, f"VibeShift converts an exploratory Colab notebook into a reproducible analytics "
              f"system. A single run over {DATA_ROWS:,} tracks is executed by fifteen instrumented "
              f"stages, produces five acoustic clusters with a silhouette score of "
              f"{SILHOUETTE:.3f}, and expresses the change in popular music as a decade \u00d7 "
              f"cluster distribution; the recorded run completed in {TOTAL_SECONDS:.1f} seconds on "
              f"one machine. Each cluster is named from its own measured profile, so the labels in "
              f"the interface are derived rather than assumed, and the pipeline work \u2013 reading, "
              f"cleaning, standardising, clustering, projecting, aggregating and benchmarking \u2013 "
              f"is separable from the analytics that follow it.")
    para(doc, "The core portion is MapReduce, NoSQL persistence and statistical visualization. "
              "MapReduce is a runtime whose phases are counted and timed, so the combiner's effect "
              "on shuffle volume is measurable rather than assumed; MongoDB stores each run as a "
              "schemaless document and the application demonstrates the document model, reflection, "
              "queries and the aggregation pipeline on live data while staying read-only; and "
              "statistical profiling with visualization carries the result to the reader, where the "
              "correlation matrix, the vibe-shift heatmap and the stacked decade composition "
              "together show the acoustic-to-electronic transition. The five remaining analyses "
              "run on every execution and are exposed as additional evidence.")
    para(doc, "The limitations define the next steps. The pipeline runs on a single node, so the "
              "distributed engine is only used when a JVM is available, and deploying the same "
              "configuration on a Spark cluster would make the shuffle and partitioning behaviour "
              "directly comparable with the in-process model. The MapReduce, graph and streaming "
              "analyses work on bounded samples whose sizes are reported rather than hidden. "
              "Replacing the stream replay with a live broker would turn drift detection into an "
              "operational signal, learned track embeddings in place of the eight curated features "
              "would let the clustering discover similarity the feature set cannot express, and "
              "authentication with per-user history would turn the application into a shared tool "
              "rather than a local one.")


def back_matter(doc) -> None:
    heading = doc.add_heading("REFERENCES", level=1)
    heading.paragraph_format.page_break_before = True
    refs = [
        "J. Dean and S. Ghemawat, \u201cMapReduce: Simplified Data Processing on Large Clusters,\u201d "
        "Proceedings of the 6th Symposium on Operating Systems Design and Implementation (OSDI), 2004.",
        "K. Shvachko, H. Kuang, S. Radia and R. Chansler, \u201cThe Hadoop Distributed File "
        "System,\u201d Proceedings of the 26th IEEE Symposium on Mass Storage Systems and "
        "Technologies (MSST), 2010.",
        "M. Zaharia et al., \u201cApache Spark: A Unified Engine for Big Data Processing,\u201d "
        "Communications of the ACM, vol. 59, no. 11, 2016.",
        "J. MacQueen, \u201cSome Methods for Classification and Analysis of Multivariate "
        "Observations,\u201d Proceedings of the 5th Berkeley Symposium on Mathematical Statistics "
        "and Probability, 1967.",
        "T. Hastie, R. Tibshirani and J. Friedman, The Elements of Statistical Learning: Data "
        "Mining, Inference and Prediction, 2nd ed., Springer, 2009.",
        "P. J. Rousseeuw, \u201cSilhouettes: A Graphical Aid to the Interpretation and Validation "
        "of Cluster Analysis,\u201d Journal of Computational and Applied Mathematics, vol. 20, 1987.",
        "M. E. J. Newman, \u201cModularity and Community Structure in Networks,\u201d Proceedings of "
        "the National Academy of Sciences, vol. 103, no. 23, 2006.",
        "L. Page, S. Brin, R. Motwani and T. Winograd, \u201cThe PageRank Citation Ranking: "
        "Bringing Order to the Web,\u201d Stanford InfoLab Technical Report, 1999.",
        "B. H. Bloom, \u201cSpace/Time Trade-offs in Hash Coding with Allowable Errors,\u201d "
        "Communications of the ACM, vol. 13, no. 7, 1970.",
        "T. Akidau et al., \u201cThe Dataflow Model: A Practical Approach to Balancing Correctness, "
        "Latency and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing,\u201d Proceedings "
        "of the VLDB Endowment, vol. 8, no. 12, 2015.",
        "MongoDB Inc., MongoDB Manual: Documents, Queries and Aggregation Pipeline, 2024. "
        "[Online]. Available: https://www.mongodb.com/docs/manual/",
        "M. Kleppmann, Designing Data-Intensive Applications, O'Reilly Media, 2017.",
        "Spotify, \u201cAudio Features and Track Analysis,\u201d Spotify for Developers "
        "documentation, 2024. [Online]. Available: "
        "https://developer.spotify.com/documentation/web-api/reference/",
        "F. Pedregosa et al., \u201cScikit-learn: Machine Learning in Python,\u201d Journal of "
        "Machine Learning Research, vol. 12, 2011.",
        "S. Ram\u00edrez, \u201cFastAPI documentation,\u201d 2024. [Online]. Available: "
        "https://fastapi.tiangolo.com/",
    ]
    for i, ref in enumerate(refs, start=1):
        p = doc.add_paragraph()
        p.add_run(f"[{i}]  {ref}").font.size = Pt(11)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.left_indent = Inches(0.35)
        p.paragraph_format.first_line_indent = Inches(-0.35)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_heading("ACKNOWLEDGEMENTS", level=1)
    para(doc, "We thank our guide for the guidance and feedback that shaped this project and the "
              "Department of Computer Engineering for the laboratory and computing facilities. We "
              "also acknowledge the maintainers of the public Spotify corpus and of the "
              "open-source libraries used here \u2013 pandas, scikit-learn, PySpark, FastAPI, React "
              "and MongoDB \u2013 whose documentation made the implementation practical, and our "
              "classmates who reviewed early versions of the interface.")


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def reset_context() -> None:
    CONTEXT["chapter"] = 0
    CONTEXT["figure"] = {}
    CONTEXT["table"] = {}
    CONTEXT["headings"] = []


def render_body(doc) -> None:
    chapter_1(doc)
    chapter_2(doc)
    chapter_3(doc)
    chapter_4(doc)
    chapter_5(doc)
    chapter_6(doc)
    chapter_7(doc)
    back_matter(doc)


def build(pm: dict) -> None:
    # pass 1 - discover the outline, figure and table lists
    reset_context()
    probe = Document()
    page_setup(probe.sections[0])
    setup_styles(probe)
    render_body(probe)
    collected = {
        "headings": list(CONTEXT["headings"]),
        "figure": dict(CONTEXT["figure"]),
        "table": dict(CONTEXT["table"]),
    }

    # pass 2 - the real document
    reset_context()
    doc = Document()
    setup_styles(doc)
    page_setup(doc.sections[0])
    doc.sections[0].footer.is_linked_to_previous = False

    CONTEXT.update(collected)          # front matter lists need the discovered names
    front_matter(doc)
    lists_and_contents(doc, pm)
    CONTEXT.update({"figure": {}, "table": {}, "headings": [], "chapter": 0})

    body = doc.add_section(WD_SECTION.NEW_PAGE)
    page_setup(body)
    restart_page_numbering(body)
    body.footer.is_linked_to_previous = False
    footer_p = body.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number_field(footer_p)

    render_body(doc)

    assert CONTEXT["figure"] == collected["figure"], "figure numbering changed between passes"
    assert CONTEXT["table"] == collected["table"], "table numbering changed between passes"

    doc.save(OUT)
    print(f"wrote {OUT}")
    print(f"  headings: {len(collected['headings'])}  figures: {len(collected['figure'])}  "
          f"tables: {len(collected['table'])}")
    if pm.get("pages"):
        print(f"  last Word measurement: {pm['pages']} pages")


if __name__ == "__main__":
    build(pagemap())
