"""Bloom filter (Exp.6, CO4-LO4).

A real bit-array Bloom filter with ``k`` hash functions derived by double hashing
(``h_i = (h1 + i*h2) mod m``) over blake2b + sha256 digests. It is used twice:

1. **Production** - a membership index over the artist vocabulary, so a track
   search can be answered as "definitely absent" without touching the Parquet
   store (the "turned an O(n) scan into a lookup" argument).
2. **The lab exercise** - a small filter with an insert/test table that reports
   True positive / False positive / Not present per word, with ASCII values and
   bit positions, exactly as the manual's steps 1-5 describe.

The manual's literal 11-bit / 10-word configuration is also run, because it
demonstrates *why* a bigger filter is used here: 10 words saturate 11 bits and
every subsequent test becomes a false positive.
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import Any

import numpy as np
import pandas as pd

EXPERIMENT = "Exp.6 / CO4-LO4"
TITLE = "Bloom filter: membership testing in O(k) with tunable false positives"

DEFAULT_FPR = 0.01


class BloomFilter:
    """Bit-array Bloom filter with double hashing."""

    def __init__(self, m_bits: int, k: int) -> None:
        self.m = max(1, int(m_bits))
        self.k = max(1, int(k))
        self._bits = bytearray((self.m + 7) // 8)
        self.inserted = 0

    # ---- sizing ------------------------------------------------------- #
    @staticmethod
    def optimal_m(n: int, p: float = DEFAULT_FPR) -> int:
        n = max(1, int(n))
        return int(math.ceil(-n * math.log(p) / (math.log(2) ** 2)))

    @staticmethod
    def optimal_k(m: int, n: int) -> int:
        n = max(1, int(n))
        return max(1, int(round((m / n) * math.log(2))))

    # ---- hashing ------------------------------------------------------ #
    def positions(self, item: Any) -> list[int]:
        data = str(item).encode("utf-8", "ignore")
        h1 = int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "big")
        h2 = int.from_bytes(hashlib.sha256(data).digest()[:8], "big") | 1
        return [((h1 + i * h2) % self.m) for i in range(self.k)]

    # ---- operations --------------------------------------------------- #
    def add(self, item: Any) -> list[int]:
        pos = self.positions(item)
        for p in pos:
            self._bits[p >> 3] |= 1 << (p & 7)
        self.inserted += 1
        return pos

    def contains(self, item: Any) -> bool:
        return all(self._bits[p >> 3] & (1 << (p & 7)) for p in self.positions(item))

    # ---- metrics ------------------------------------------------------ #
    def bits_set(self) -> int:
        return sum(bin(byte).count("1") for byte in self._bits)

    def fill_pct(self) -> float:
        return 100.0 * self.bits_set() / self.m

    def theoretical_fpr(self) -> float:
        return (1.0 - math.exp(-self.k * self.inserted / self.m)) ** self.k

    def bit_string(self, limit: int | None = None) -> str:
        upto = self.m if limit is None else min(limit, self.m)
        return "".join(
            "1" if self._bits[i >> 3] & (1 << (i & 7)) else "0" for i in range(upto)
        )

    def memory_kb(self) -> float:
        return round(len(self._bits) / 1024.0, 3)


def _artist_vocabulary(df: pd.DataFrame, cap: int = 40_000) -> tuple[list[str], int]:
    """Distinct artist names from the ``artists`` column (split multi-credit rows).

    Returns ``(vocabulary, total_distinct)``: the vocabulary is capped so the
    filter stays small, but the *total* distinct count is still reported so the
    cap is never hidden.
    """
    from .mapreduce import _artist_tokens  # local import keeps module import cheap

    seen: set[str] = set()
    for value in df.get("artists", pd.Series(dtype=object)).tolist():
        for name in _artist_tokens(value):
            seen.add(name)
    ordered = sorted(seen)
    return ordered[:cap], len(ordered)


def _lab_table(
    words: list[str], tests: list[str], bits: int, k: int
) -> dict[str, Any]:
    """Run the manual's insert/test table on a small filter."""
    bf = BloomFilter(bits, k)
    inserted_rows = []
    for word in words:
        pos = bf.add(word)
        inserted_rows.append(
            {
                "word": word,
                "ascii": [ord(ch) for ch in word],
                "ascii_sum": sum(ord(ch) for ch in word),
                "bit_positions": pos,
                "bits": [1 if bf._bits[p >> 3] & (1 << (p & 7)) else 0 for p in pos],
            }
        )
    test_rows = []
    for word in tests:
        hit = bf.contains(word)
        if word in words:
            status = "True positive"
        elif hit:
            status = "False positive"
        else:
            status = "Not present"
        test_rows.append(
            {
                "word": word,
                "ascii": [ord(ch) for ch in word],
                "ascii_sum": sum(ord(ch) for ch in word),
                "bit_positions": bf.positions(word),
                "bits": [1 if bf._bits[p >> 3] & (1 << (p & 7)) else 0 for p in bf.positions(word)],
                "result": hit,
                "status": status,
            }
        )
    return {
        "bits": bits,
        "hashes": k,
        "inserted": inserted_rows,
        "tests": test_rows,
        "bit_string": bf.bit_string(),
        "bits_set": bf.bits_set(),
        "fill_pct": round(bf.fill_pct(), 2),
        "theoretical_fpr": round(bf.theoretical_fpr(), 4),
        "true_positives": sum(1 for r in test_rows if r["status"] == "True positive"),
        "false_positives": sum(1 for r in test_rows if r["status"] == "False positive"),
        "true_negatives": sum(1 for r in test_rows if r["status"] == "Not present"),
        "false_negatives": 0,
    }


def run_bloom(df: pd.DataFrame, *, test_pairs: int = 2_000) -> dict[str, Any]:
    t0 = time.perf_counter()

    vocabulary, total_distinct = _artist_vocabulary(df)
    n = len(vocabulary)
    m = BloomFilter.optimal_m(n, DEFAULT_FPR)
    k = BloomFilter.optimal_k(m, n)

    t1 = time.perf_counter()
    bf = BloomFilter(m, k)
    for item in vocabulary:
        bf.add(item)
    insert_seconds = time.perf_counter() - t1

    # Membership sanity: every inserted item must be reported present (no false
    # negatives is the one guarantee a Bloom filter makes).
    sample_hits = 0
    sample_probe = vocabulary[: min(500, n)]
    for item in sample_probe:
        sample_hits += int(bf.contains(item))

    # Empirical false-positive rate on strings that were never inserted.
    rng = np.random.default_rng(42)
    absent = [f"zz-absent-{i}-{int(rng.integers(1, 10**9))}" for i in range(test_pairs)]
    t2 = time.perf_counter()
    false_positives = sum(1 for item in absent if bf.contains(item))
    probe_seconds = time.perf_counter() - t2

    production = {
        "n": n,
        "vocabulary_total_distinct": total_distinct,
        "capped": total_distinct > n,
        "m": m,
        "k": k,
        "target_fpr": DEFAULT_FPR,
        "bits_set": bf.bits_set(),
        "fill_pct": round(bf.fill_pct(), 3),
        "theoretical_fpr": round(bf.theoretical_fpr(), 6),
        "empirical_fpr": round(false_positives / max(1, len(absent)), 6),
        "probes": len(absent),
        "false_positives": false_positives,
        "false_negatives": 0,
        "inserted_verified_present": f"{sample_hits}/{len(sample_probe)}",
        "memory_kb": bf.memory_kb(),
        "insert_seconds": round(insert_seconds, 4),
        "probe_seconds": round(probe_seconds, 4),
        "bits_vs_naive_kb_saved": round(len(vocabulary) * 16 / 1024 - bf.memory_kb(), 1),
        "bit_preview": bf.bit_string(512),
        "bit_preview_len": 512,
    }

    # ---- the lab exercise table (small filter, readable bit string) ------ #
    lab_words = ["hadoop", "spark", "mapreduce", "nosql", "bloom"]
    lab_tests = ["spark", "bloom", "cluster", "stream", "hbase"]
    lab_exercise = _lab_table(lab_words, lab_tests, bits=32, k=3)
    lab_exercise["note"] = (
        "Mirrors the manual's steps: words -> ASCII -> hash positions -> set bits, "
        "then 5 test words classified True positive / False positive / Not present."
    )

    # ---- the manual's literal 11-bit configuration ---------------------- #
    manual_words = ["hadoop", "map", "reduce", "spark", "hive", "pig", "hbase", "nosql", "data", "cloud"]
    manual_tests = ["storm", "kafka", "spark", "flink", "hdfs"]
    manual_11bit = _lab_table(manual_words, manual_tests, bits=11, k=2)
    manual_11bit["note"] = (
        "The manual's literal 11-bit filter with 10 inserted words saturates the "
        "array, so almost every test becomes a false positive - this is why the "
        "production filter above sizes m from the item count instead of guessing."
    )

    # ---- search pre-filter simulation ----------------------------------- #
    queries = (vocabulary[:6] + ["zz-definitely-not-an-artist", "qq-not-here"]) or ["x"]
    prefilter = []
    scans_avoided = 0
    for q in queries:
        hit = bf.contains(q)
        if not hit:
            scans_avoided += 1
        prefilter.append(
            {
                "query": q,
                "bloom_says": "might be present" if hit else "definitely absent",
                "parquet_scan": "needed" if hit else "skipped",
                "rows_scanned": "scan" if hit else 0,
            }
        )

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(time.perf_counter() - t0, 3),
        "production": production,
        "lab_exercise": lab_exercise,
        "manual_11bit": manual_11bit,
        "search_prefilter": {
            "indexed_items": n,
            "queries": prefilter,
            "scans_avoided": scans_avoided,
            "queries_total": len(prefilter),
        },
        "concepts": [
            "bit array of m bits + k independent hash functions",
            "double hashing h_i = (h1 + i*h2) mod m",
            "false positives possible, false negatives impossible",
            "optimal sizing m = -n ln p / (ln 2)^2, k = (m/n) ln 2",
            "membership pre-filter to skip expensive scans",
        ],
    }
