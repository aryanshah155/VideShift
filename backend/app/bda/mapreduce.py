"""MapReduce framework simulation (Exp.4 & Exp.5, CO2-LO2).

A small but *real* MapReduce runtime: ``map -> partition -> combine -> shuffle ->
reduce``, instrumented per phase, executed over the same cleaned track records
the clusterer consumed. Five jobs cover the exercise list from the manual:

===========================  ==================  ==============================
job                          manual exercise     what it demonstrates
===========================  ==================  ==============================
``word_count``               Exp.4               word count on track titles
``aggregates``               Exp.5               per-decade feature means + combiner savings
``join``                     Exp.5               map-side (broadcast) join with the cluster table
``top_n``                    Exp.5               sorting / top-N artists
``inverted_index``           Exp.5               searching via an inverted index
===========================  ==================  ==============================

The phases are genuinely separate (each timed, each counted) so the UI can show
where the records go - the point of the exercise.
"""

from __future__ import annotations

import re
import time
import zlib
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd

EXPERIMENT = "Exp.4/Exp.5 / CO2-LO2"
TITLE = "MapReduce: word count, aggregates, joins, sorting, searching"

STOPWORDS = {
    "the", "a", "an", "and", "of", "to", "in", "on", "for", "with", "feat",
    "ft", "version", "mix", "remaster", "remastered", "edit", "radio", "song",
    "from", "you", "your", "me", "my", "it", "is", "be", "at", "as", "by",
    "or", "la", "le", "el", "de", "que", "no", "all", "that", "this",
}

TOKEN_RE = re.compile(r"[a-z']{3,}")


class MapReduceJob:
    """A single map/combine/reduce job with per-phase instrumentation."""

    def __init__(
        self,
        name: str,
        *,
        map_fn: Callable[[dict], Iterable[tuple[Any, Any]]],
        reduce_fn: Callable[[Any, list[Any]], Any],
        combine_fn: Callable[[Any, list[Any]], Any] | None = None,
        partition_fn: Callable[[Any], int] | None = None,
        num_partitions: int = 4,
        row_formatter: Callable[[Any, Any], str] | None = None,
    ) -> None:
        self.name = name
        self.map_fn = map_fn
        self.reduce_fn = reduce_fn
        self.combine_fn = combine_fn
        self.partition_fn = partition_fn
        self.num_partitions = max(1, num_partitions)
        self.row_formatter = row_formatter or (lambda k, v: str(v))

    def _partition(self, key: Any) -> int:
        if self.partition_fn is not None:
            return self.partition_fn(key) % self.num_partitions
        return zlib.crc32(str(key).encode("utf-8")) % self.num_partitions

    def run(self, records: Sequence[dict]) -> dict[str, Any]:
        n_parts = self.num_partitions

        # ---- MAP ---------------------------------------------------------- #
        t0 = time.perf_counter()
        pairs: list[tuple[Any, Any]] = []
        for record in records:
            pairs.extend(self.map_fn(record))
        map_seconds = time.perf_counter() - t0
        map_output_pairs = len(pairs)

        # ---- SHUFFLE (partition + group by key) ---------------------------- #
        t0 = time.perf_counter()
        groups: list[dict[Any, list[Any]]] = [dict() for _ in range(n_parts)]
        part_pairs = [0] * n_parts
        for key, value in pairs:
            p = self._partition(key)
            groups[p].setdefault(key, []).append(value)
            part_pairs[p] += 1
        shuffle_seconds = time.perf_counter() - t0
        unique_keys = sum(len(g) for g in groups)

        # ---- COMBINE (local per map-task aggregation before the reduce) ---- #
        t0 = time.perf_counter()
        combine_output_pairs = 0
        if self.combine_fn is not None:
            for group in groups:
                for key, values in list(group.items()):
                    group[key] = [self.combine_fn(key, values)]
                    combine_output_pairs += 1
        else:
            combine_output_pairs = map_output_pairs
        combine_seconds = time.perf_counter() - t0

        # ---- REDUCE -------------------------------------------------------- #
        t0 = time.perf_counter()
        output: list[tuple[Any, Any]] = []
        for group in groups:
            for key, values in group.items():
                output.append((key, self.reduce_fn(key, values)))
        reduce_seconds = time.perf_counter() - t0

        saved_pct = 0.0
        if map_output_pairs:
            saved_pct = round(
                100.0 * (map_output_pairs - combine_output_pairs) / map_output_pairs, 2
            )

        return {
            "name": self.name,
            "stats": {
                "input_records": len(records),
                "map_tasks": n_parts,
                "map_output_pairs": map_output_pairs,
                "partition_pairs": part_pairs,
                "combine_input_pairs": map_output_pairs,
                "combine_output_pairs": combine_output_pairs,
                "combine_saved_pct": saved_pct,
                "shuffle_groups": unique_keys,
                "reduce_groups": unique_keys,
                "output_records": len(output),
                "reducers": n_parts,
                "timings": {
                    "map": round(map_seconds, 4),
                    "shuffle": round(shuffle_seconds, 4),
                    "combine": round(combine_seconds, 4),
                    "reduce": round(reduce_seconds, 4),
                    "total": round(
                        map_seconds + shuffle_seconds + combine_seconds + reduce_seconds, 4
                    ),
                },
            },
            "raw_output": output,
        }

    def rows(self, output: list[tuple[Any, Any]], top: int = 15) -> list[dict[str, Any]]:
        """Format the reduced output, highest-valued first.

        Reduce output arrives in partition/key order, so for the word-count and
        top-N jobs (whose whole point is a ranking) it has to be sorted by value.
        """

        def sort_key(item: tuple[Any, Any]) -> tuple[int, float, str]:
            _, value = item
            if isinstance(value, bool):
                return (0, 0.0, "")
            if isinstance(value, (int, float)):
                return (0, -float(value), "")
            if isinstance(value, dict):
                for field in ("count", "postings"):
                    if isinstance(value.get(field), (int, float)):
                        return (0, -float(value[field]), "")
            return (1, 0.0, str(value))

        ordered = sorted(output, key=sort_key)
        return [
            {"key": str(k), "value": _jsonable(v), "detail": self.row_formatter(k, v)}
            for k, v in ordered[:top]
        ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return round(float(value), 6)
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _tokenize(text: Any) -> list[str]:
    if text is None:
        return []
    if isinstance(text, float) and pd.isna(text):
        return []
    return [t for t in TOKEN_RE.findall(str(text).lower()) if t not in STOPWORDS]


def _artist_tokens(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    raw = str(value)
    raw = raw.strip().strip("[]").replace("'", "").replace('"', "")
    parts: list[str] = []
    for chunk in re.split(r"[;,]", raw):
        chunk = chunk.strip()
        if chunk and chunk.lower() not in {"nan", "none", ""}:
            parts.append(chunk)
    return parts


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #


def _job_word_count() -> MapReduceJob:
    return MapReduceJob(
        "word_count",
        map_fn=lambda r: [(t, 1) for t in _tokenize(r.get("name"))],
        combine_fn=lambda key, values: sum(values),
        reduce_fn=lambda key, values: sum(values),
        row_formatter=lambda k, v: f"{v:,}x",
    )


def _job_aggregates(feature_cols: list[str]) -> MapReduceJob:
    """Per-decade mean of four features - Exp.5 "Aggregates" with a combiner."""
    cols = feature_cols[:4]

    def map_fn(r: dict) -> list[tuple[Any, Any]]:
        vals = []
        for c in cols:
            v = r.get(c)
            try:
                vals.append(float(v))
            except Exception:
                vals.append(0.0)
        return [(int(r.get("decade") or 0), tuple([1, *vals]))]

    def combine_fn(key: Any, values: list[Any]) -> tuple:
        acc = [0.0] * (len(cols) + 1)
        for v in values:
            for i, item in enumerate(v):
                acc[i] += item
        return tuple(acc)

    def reduce_fn(key: Any, values: list[Any]) -> dict[str, Any]:
        acc = values[0]
        count = max(1, int(acc[0]))
        return {
            "count": int(acc[0]),
            **{c: round(acc[i + 1] / count, 4) for i, c in enumerate(cols)},
        }

    return MapReduceJob(
        "aggregates",
        map_fn=map_fn,
        combine_fn=combine_fn,
        reduce_fn=reduce_fn,
        row_formatter=lambda k, v: f"n={v['count']:,} " + " ".join(
            f"{c}={v[c]}" for c in cols
        ),
    )


def _job_join(labels: dict[int, str]) -> tuple[MapReduceJob, int]:
    """Map-side join: enrich each track with its cluster label, then count.

    The small relation (cluster -> label) is broadcast to every map task, which is
    exactly how a map-side join avoids a shuffle of the big table.
    """

    def map_fn(r: dict) -> list[tuple[Any, Any]]:
        cluster = r.get("cluster")
        if cluster is None:
            return []
        label = labels.get(int(cluster))
        if label is None:  # inner join: drop unmatched left rows
            return []
        return [(label, 1)]

    job = MapReduceJob(
        "join",
        map_fn=map_fn,
        combine_fn=lambda key, values: sum(values),
        reduce_fn=lambda key, values: sum(values),
        row_formatter=lambda k, v: f"{v:,} tracks",
    )
    return job, len(labels)


def _job_top_n(top: int = 15) -> MapReduceJob:
    """Sorting: artist frequency, reduce then sort by count."""

    def map_fn(r: dict) -> list[tuple[Any, Any]]:
        return [(a, 1) for a in _artist_tokens(r.get("artists"))]

    job = MapReduceJob(
        "top_n",
        map_fn=map_fn,
        combine_fn=lambda key, values: sum(values),
        reduce_fn=lambda key, values: sum(values),
        row_formatter=lambda k, v: f"{v:,} tracks",
    )
    job._top = top  # type: ignore[attr-defined]
    return job


def _job_inverted_index(posting_cap: int = 8) -> MapReduceJob:
    """Searching: token -> posting list of track ids (the classic inverted index)."""

    def map_fn(r: dict) -> list[tuple[Any, Any]]:
        rid = r.get("id")
        name = r.get("name")
        return [(t, str(rid)) for t in _tokenize(name)]

    def combine_fn(key: Any, values: list[Any]) -> list[str]:
        return values[:posting_cap]

    def reduce_fn(key: Any, values: list[Any]) -> dict[str, Any]:
        flat = list(values[0]) if values and isinstance(values[0], list) else values
        return {"postings": len(flat), "sample_ids": flat[:4]}

    return MapReduceJob(
        "inverted_index",
        map_fn=map_fn,
        combine_fn=combine_fn,
        reduce_fn=reduce_fn,
        row_formatter=lambda k, v: f"{v['postings']} postings -> {', '.join(v['sample_ids'][:3])}",
    )


def _row(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": entry["name"],
        "title": entry["title"],
        "experiment": entry["experiment"],
        "objective": entry["objective"],
        "pipeline": entry["pipeline"],
        "stats": entry["stats"],
        "output": entry["output"],
        "output_columns": entry["output_columns"],
        "note": entry.get("note", ""),
    }


def run_mapreduce(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    row_limit: int = 25_000,
    num_partitions: int = 4,
    top_n: int = 15,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    total_rows = int(len(df))
    if total_rows > row_limit:
        sample = df.sample(n=row_limit, random_state=42).reset_index(drop=True)
        sampled = True
    else:
        sample = df
        sampled = False
    records = sample.to_dict("records")
    cols = [c for c in feature_cols if c in df.columns]

    # Cluster -> label lookup table for the map-side join.
    labels: dict[int, str] = {}
    if "cluster" in df.columns:
        try:
            from ..pipeline.pandas_engine import _label_for

            for cid in sorted(df["cluster"].dropna().unique()):
                labels[int(cid)] = _label_for(int(cid))
        except Exception:
            for cid in sorted(df["cluster"].dropna().unique()):
                labels[int(cid)] = f"Cluster {int(cid)}"

    jobs: list[dict[str, Any]] = []
    timings: dict[str, float] = {}

    def _exec(entry_meta: dict[str, Any], job: MapReduceJob, top: int) -> None:
        outcome = job.run(records)
        jobs.append(
            _row(
                {
                    **entry_meta,
                    "stats": outcome["stats"],
                    "output": job.rows(outcome["raw_output"], top=top),
                }
            )
        )
        timings[job.name] = outcome["stats"]["timings"]["total"]

    # Exp.4 - word count
    _exec(
        {
            "name": "word_count",
            "title": "Word count over track titles",
            "experiment": "Exp.4 / CO2-LO2",
            "objective": "Implement the canonical MapReduce word count on real text",
            "pipeline": [
                "map(title) -> [(word, 1) for every token]",
                "combine(word, [1,1,..]) -> sum  (runs inside each map task)",
                "shuffle: partition by crc32(word) % reducers",
                "reduce(word, values) -> sum(values)",
            ],
            "output_columns": ["word", "occurrences"],
            "note": "Stopwords and tokens shorter than 3 characters are filtered during the map phase.",
        },
        _job_word_count(),
        top_n,
    )

    # Exp.5 - aggregates
    if cols:
        _exec(
            {
                "name": "aggregates",
                "title": f"Per-decade aggregates over {', '.join(cols[:4])}",
                "experiment": "Exp.5 / CO2-LO2",
                "objective": "MapReduce aggregates (sum + count -> mean) with a combiner",
                "pipeline": [
                    "map(record) -> [(decade, (1, feature_values...))]",
                    "combine(decade, tuples) -> element-wise sum  (combiner shrinks the shuffle)",
                    "reduce(decade, [sum_tuple]) -> mean = sum / count",
                ],
                "output_columns": ["decade", "counts + feature means"],
                "note": "The combiner is what makes this scalable: only one tuple per decade per map task crosses the network.",
            },
            _job_aggregates(cols),
            12,
        )

    # Exp.5 - join
    if labels:
        join_job, broadcast_size = _job_join(labels)
        outcome = join_job.run(records)
        jobs.append(
            _row(
                {
                    "name": "join",
                    "title": "Map-side join: tracks joined with the cluster label table",
                    "experiment": "Exp.5 / CO2-LO2",
                    "objective": "Join a large relation (tracks) with a small one (cluster labels)",
                    "pipeline": [
                        f"broadcast the {broadcast_size}-row cluster->label table to every map task",
                        "map(track) -> [(label, 1)] for matched rows (inner join semantics)",
                        "combine + reduce -> count of tracks per acoustic profile",
                    ],
                    "stats": outcome["stats"],
                    "output": join_job.rows(outcome["raw_output"], top=12),
                    "output_columns": ["cluster label", "tracks"],
                    "note": f"Broadcast table: {broadcast_size} rows. A map-side join avoids shuffling the {len(records):,}-row left side.",
                }
            )
        )
        timings["join"] = outcome["stats"]["timings"]["total"]

    # Exp.5 - sorting / top-N
    _exec(
        {
            "name": "top_n",
            "title": f"Sorting: top {top_n} artists by track count",
            "experiment": "Exp.5 / CO2-LO2",
            "objective": "MapReduce counting + sort for top-N reporting",
            "pipeline": [
                "map(track) -> [(artist, 1)] for every credited artist",
                "combine + reduce -> total tracks per artist",
                "sort the reduced output descending and cut the top N",
            ],
            "output_columns": ["artist", "tracks"],
            "note": "Split on ';' / ',' so multi-artist credits each get a vote.",
        },
        _job_top_n(top_n),
        top_n,
    )

    # Exp.5 - searching / inverted index
    index_job = _job_inverted_index()
    outcome = index_job.run(records)
    raw = outcome["raw_output"]
    by_postings = sorted(raw, key=lambda kv: kv[1]["postings"], reverse=True)
    query_terms = [k for k, _ in by_postings[:1]]
    query_result: dict[str, Any] | None = None
    if query_terms:
        term = str(query_terms[0])
        hit = dict(raw).get(term) or next((v for k, v in raw if k == term), None)
        query_result = {"term": term, "postings": hit["postings"] if hit else 0}
    jobs.append(
        _row(
            {
                "name": "inverted_index",
                "title": "Searching: inverted index (token -> posting list)",
                "experiment": "Exp.5 / CO2-LO2",
                "objective": "Build a searchable index without scanning every row per query",
                "pipeline": [
                    "map(track) -> [(token, track_id)] for every title token",
                    "combine(token, ids) -> first 8 postings (bounded, like a real posting cap)",
                    "reduce(token, ids) -> posting list metadata",
                ],
                "stats": outcome["stats"],
                "output": index_job.rows(by_postings, top=12),
                "output_columns": ["token", "posting list"],
                "note": "An index turns an O(n) scan per query into one lookup - the same idea as the Bloom pre-filter in Exp.6.",
            }
        )
    )
    timings["inverted_index"] = outcome["stats"]["timings"]["total"]

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(time.perf_counter() - t0, 3),
        "input_rows": len(records),
        "total_rows": total_rows,
        "sampled": sampled,
        "row_limit": row_limit,
        "sample_note": (
            f"Map phase executed over a {row_limit:,}-row sample of the "
            f"{total_rows:,}-row corpus to keep the in-process runtime bounded."
            if sampled
            else "Map phase executed over the whole corpus."
        ),
        "partitions": num_partitions,
        "jobs": jobs,
        "query_result": query_result,
        "job_timings": timings,
        "concepts": [
            "map / shuffle / combine / reduce phases",
            "key partitioning (crc32 hash partitioning)",
            "combiners reducing shuffle traffic",
            "map-side (broadcast) join",
            "sorting and top-N",
            "inverted index for search",
        ],
    }
