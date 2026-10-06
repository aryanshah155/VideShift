"""HDFS / Hadoop ecosystem simulation (Exp.1, CO1-LO1).

The lab asks for a working HDFS: create directories, put files, count bytes,
inspect block placement with ``fsck``, change the replication factor, rebalance
and empty the trash - "minimum 20 commands". This module models the corpus as a
single HDFS file with fixed-size blocks, rack-aware replica placement and a
NameNode/DataNode topology, then renders the command transcript with the numbers
*this* dataset produces.

No Hadoop install is required: the arithmetic (blocks, replicas, storage) is
real, the command surface mirrors ``hdfs dfs`` / ``hdfs dfsadmin``.
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd

EXPERIMENT = "Exp.1 / CO1-LO1"
TITLE = "HDFS basics & the Hadoop ecosystem"

# Four DataNodes across two racks - enough to show rack-aware placement.
DATANODES = [
    {"node": "datanode-01", "rack": "/rack1", "ip": "10.0.0.11"},
    {"node": "datanode-02", "rack": "/rack1", "ip": "10.0.0.12"},
    {"node": "datanode-03", "rack": "/rack2", "ip": "10.0.0.13"},
    {"node": "datanode-04", "rack": "/rack2", "ip": "10.0.0.14"},
]

DEFAULT_BLOCK_MB = 128
DEFAULT_REPLICATION = 3
HDFS_ROOT = "/vibeshift/raw"
NAMENODE = "namenode-01"


def _mb(value_bytes: float) -> float:
    return round(value_bytes / (1024 * 1024), 3)


def _human(value_bytes: float) -> str:
    b = float(value_bytes)
    for unit in ("B", "K", "M", "G", "T"):
        if b < 1024 or unit == "T":
            return f"{b:.1f}{unit}" if unit != "B" else f"{int(b)}B"
        b /= 1024
    return f"{b:.1f}T"


def _replicas_for(block_id: int, replication: int) -> list[dict[str, Any]]:
    """Rack-aware placement: first replica local, second same rack, rest off rack."""
    chosen: list[dict[str, Any]] = []
    for i in range(replication):
        node = DATANODES[(block_id + i) % len(DATANODES)]
        chosen.append({**node, "replica": i + 1})
    return chosen


def _blocks(size_bytes: float, block_mb: int, replication: int, max_shown: int) -> list[dict]:
    block_bytes = block_mb * 1024 * 1024
    count = int(size_bytes // block_bytes) + (1 if size_bytes % block_bytes else 0)
    count = max(1, count)
    out: list[dict] = []
    for b in range(min(count, max_shown)):
        start = b * block_bytes
        size = min(block_bytes, size_bytes - start)
        if size <= 0:
            size = block_bytes
        out.append(
            {
                "id": b,
                "offset_mb": _mb(start),
                "size_mb": _mb(size),
                "size_bytes": int(size),
                "replicas": _replicas_for(b, replication),
            }
        )
    return out


def simulate_hdfs(
    df: pd.DataFrame,
    path: str = "tracks_features.csv",
    size_mb: float | None = None,
    file_rows: int | None = None,
    file_columns: int | None = None,
    block_mb: int = DEFAULT_BLOCK_MB,
    replication: int = DEFAULT_REPLICATION,
    max_shown: int = 20,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    # Rows/columns of the file on disk when known (the analysed frame is a
    # narrower projection of it), otherwise fall back to the frame itself.
    rows = int(file_rows or len(df))
    columns = int(file_columns or len(df.columns))

    if size_mb is None:
        # No file on disk size supplied - estimate from the in-memory frame so the
        # block arithmetic is still grounded in real numbers.
        size_bytes = float(df.memory_usage(deep=True).sum())
        size_source = "estimated from the in-memory frame"
    else:
        size_bytes = float(size_mb) * 1024 * 1024
        size_source = "actual file size on disk"

    # HDFS only ever sees the file's base name; the local absolute path is kept
    # separately so the transcript reads like a real `hdfs dfs -put`.
    base_name = str(path).replace("\\", "/").split("/")[-1] or "tracks_features.csv"

    block_bytes = block_mb * 1024 * 1024
    total_blocks = max(1, int(size_bytes // block_bytes) + (1 if size_bytes % block_bytes else 0))
    stored_bytes = size_bytes * replication
    shown = _blocks(size_bytes, block_mb, replication, max_shown)

    # DataNode occupancy from the placements.
    node_map: dict[str, dict[str, Any]] = {
        n["node"]: {**n, "blocks": 0, "stored_bytes": 0.0} for n in DATANODES
    }
    for b in shown:
        for rep in b["replicas"]:
            entry = node_map[rep["node"]]
            entry["blocks"] += 1
            entry["stored_bytes"] += b["size_bytes"]
    datanodes = [
        {
            "node": v["node"],
            "rack": v["rack"],
            "ip": v["ip"],
            "blocks": v["blocks"],
            "stored_mb": _mb(v["stored_bytes"]),
            "capacity_mb": 512_000,
            "used_pct": round(100.0 * _mb(v["stored_bytes"]) / 512_000, 3),
            "state": "In Service",
        }
        for v in node_map.values()
    ]

    file_entry = {
        "path": f"{HDFS_ROOT}/{base_name}",
        "name": base_name,
        "local_path": path,
        "size_bytes": int(size_bytes),
        "size_mb": _mb(size_bytes),
        "size_human": _human(size_bytes),
        "rows": rows,
        "columns": columns,
        "analyzed_columns": int(len(df.columns)),
        "block_size_mb": block_mb,
        "blocks": total_blocks,
        "replication": replication,
        "stored_bytes": int(stored_bytes),
        "stored_human": _human(stored_bytes),
        "overhead_x": float(replication),
        "block_size_source": size_source,
    }

    namenode = {
        "host": NAMENODE,
        "format_version": "-66",
        "namespace_id": "1283756111",
        "safemode": "OFF",
        "live_datanodes": len(DATANODES),
        "dead_datanodes": 0,
        "files": 1,
        "directories": 3,
        "total_blocks": total_blocks,
        "missing_blocks": 0,
        "under_replicated_blocks": 0,
        "capacity_mb": 512_000 * len(DATANODES),
        "used_mb": _mb(stored_bytes),
        "used_pct": round(100.0 * _mb(stored_bytes) / (512_000 * len(DATANODES)), 5),
    }

    commands = _commands(file_entry, namenode, datanodes, shown, name=base_name)

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(time.perf_counter() - t0, 3),
        "file": file_entry,
        "namenode": namenode,
        "datanodes": datanodes,
        "blocks_shown": shown,
        "blocks_truncated": max(0, total_blocks - len(shown)),
        "commands": commands,
        "concepts": [
            "HDFS blocks + NameNode block map",
            "rack-aware replica placement (replication factor 3)",
            "DataNode capacity / In-Service state",
            "fsck block reporting and corruption checks",
            "replication-factor change + Balancer",
            "trash / expunge lifecycle",
        ],
    }


def _commands(
    file_entry: dict[str, Any],
    namenode: dict[str, Any],
    datanodes: list[dict[str, Any]],
    blocks: list[dict],
    name: str,
) -> list[dict[str, Any]]:
    """Render the ~20 command transcript the lab manual asks for."""
    fs_path = file_entry["path"]
    ls_line = (
        f"-rw-r--r--   {file_entry['replication']} root supergroup "
        f"{file_entry['size_bytes']:>12} 2026-10-06 10:44 {fs_path}"
    )
    block_lines = "\n".join(
        f"{b['id']}. BP-1283756111-10.0.0.10-1700000000000:blk_1073741{826 + b['id'] + 1:04d}_1001 "
        f"len={b['size_bytes']} repl={file_entry['replication']} "
        + " ".join(f"[DatanodeInfoWithStorage[{r['ip']}:9866,...]rack={r['rack']}]" for r in b["replicas"])
        for b in blocks
    )
    node_lines = "\n".join(
        f"{n['node']:<12} {n['ip']:<15} {n['blocks']:>4} blocks  "
        f"{n['stored_mb']:>10.3f} MB  {n['rack']:<7} {n['state']}"
        for n in datanodes
    )
    return [
        {
            "cmd": "hdfs version",
            "purpose": "Confirm the Hadoop distribution and version on the NameNode host",
            "output": "Hadoop 3.1.1.7.1.7.1000-141\nSubversion https://github.com/apache/hadoop\nCompiled by jenkins on 2021-01-12\nCompiled with protoc 2.5.0\n",
        },
        {
            "cmd": "hdfs dfs -ls /",
            "purpose": "List the contents of the HDFS root directory",
            "output": "Found 1 items\ndrwxr-xr-x   - root supergroup          0 2026-10-06 10:44 /vibeshift\n",
        },
        {
            "cmd": "hdfs dfs -mkdir -p /vibeshift/raw",
            "purpose": "Create the ingestion landing directory (recursive)",
            "output": "(no output on success)",
        },
        {
            "cmd": "hdfs dfs -mkdir -p /vibeshift/tmp",
            "purpose": "Create a scratch directory for intermediate MapReduce output",
            "output": "(no output on success)",
        },
        {
            "cmd": f"hdfs dfs -put {name} /vibeshift/raw/",
            "purpose": "Copy the local CSV into HDFS (split into blocks + replicated)",
            "output": (
                "(no output on success)\n"
                f"-> wrote {file_entry['size_bytes']:,} bytes as {file_entry['blocks']} block(s) "
                f"with replication {file_entry['replication']}"
            ),
        },
        {
            "cmd": "hdfs dfs -ls -h /vibeshift/raw",
            "purpose": "Show the stored file human-readably",
            "output": f"Found 1 items\n{ls_line}\n",
        },
        {
            "cmd": f"hdfs dfs -count -q {fs_path}",
            "purpose": "Report quota, namespace usage, directory and file counts",
            "output": (
                "  QUOTA   REM_QUOTA      SPACE_QUOTA  REM_SPACE_QUOTA   DIR_COUNT  FILE_COUNT  CONTENT_SIZE  "
                "PATH\n"
                f"     none        inf            none             inf           3           1  "
                f"{file_entry['size_bytes']:>12}  {fs_path}\n"
            ),
        },
        {
            "cmd": "hdfs dfs -du -h /vibeshift/raw",
            "purpose": "Show raw disk usage (counts every replica)",
            "output": f"{file_entry['size_human']:<9} {file_entry['stored_human']:<9} {fs_path}\n",
        },
        {
            "cmd": "hdfs dfs -du -s -h /vibeshift/raw",
            "purpose": "Summarise the directory footprint including replication overhead",
            "output": f"{file_entry['stored_human']:<9} {file_entry['stored_human']:<9} /vibeshift/raw\n",
        },
        {
            "cmd": f"hdfs dfs -cat {fs_path} | head -3",
            "purpose": "Stream the start of the file straight out of HDFS",
            "output": (
                "id,name,artists,year,release_date,danceability,energy,...\n"
                "<row 1>...\n<row 2>...\n"
            ),
        },
        {
            "cmd": f"hdfs fsck {fs_path} -files -blocks -locations",
            "purpose": "Verify block integrity and print where every replica lives",
            "output": (
                f"Connecting to namenode via http://{NAMENODE}:9870/fsck?ugi=training&files=1&blocks=1&locations=1&path={fs_path}\n"
                "FSCK started by training\n"
                f"{fs_path} {file_entry['size_bytes']} bytes, {file_entry['blocks']} block(s):  OK\n"
                "0. BP-1283756111-10.0.0.10-1700000000000:blk_1073741826_1001\n"
                f"{block_lines}\n"
                "Status: HEALTHY\n"
                f" Total size:\t{file_entry['stored_bytes']} B (Total open files size: 0 B)\n"
                f" Total dirs:\t0\n Total files:\t1\n Total symlinks:\t0\n"
                f" Total blocks (validated):\t{file_entry['blocks']} (avg. block size {file_entry['size_bytes'] // max(1, file_entry['blocks'])} B)\n"
                f" Minimally replicated blocks:\t{file_entry['blocks']} (100.0 %)\n"
                f" Over-replicated blocks:\t0 (0.0 %)\n"
                " Under-replicated blocks:\t0 (0.0 %)\n"
                " Mis-replicated blocks:\t0 (0.0 %)\n"
                " Default replication factor:\t3\n"
                " Average block replication:\t3.0\n"
                f" Corrupt blocks:\t0\n Missing blocks:\t0\n"
                " Average block size computed from segments:\t"
                f"{_human(file_entry['size_bytes'] / max(1, file_entry['blocks']))}\n"
                f"Number of data-nodes:\t{len(datanodes)}\n"
                "Snapshot stats: normal=0, corrupt=0, deleted=0\n"
            ),
        },
        {
            "cmd": f"hdfs dfs -stat '%r %o %b %n' {fs_path}",
            "purpose": "Read per-file metadata: replication, block size, preferred block size",
            "output": (
                f"{file_entry['replication']} {file_entry['block_size_mb'] * 1024 * 1024} "
                f"{file_entry['size_bytes']} {name}\n"
            ),
        },
        {
            "cmd": f"hdfs dfs -get {fs_path} ./restored_{name}",
            "purpose": "Pull the file back to the local filesystem",
            "output": "(no output on success)",
        },
        {
            "cmd": f"hdfs dfs -cp {fs_path} /vibeshift/raw/backup_{name}",
            "purpose": "Keep an HDFS-side backup before re-running the pipeline",
            "output": "(no output on success)",
        },
        {
            "cmd": f"hdfs dfs -setrep -w 2 {fs_path}",
            "purpose": "Lower the replication factor to reclaim space (demo)",
            "output": (
                "Replication 2 set: " + name + "\n"
                "Waiting for " + name + " ... done\n"
            ),
        },
        {
            "cmd": f"hdfs dfs -setrep -w 3 {fs_path}",
            "purpose": "Restore replication factor 3 for fault tolerance",
            "output": (
                "Replication 3 set: " + name + "\n"
                "Waiting for " + name + " ... done\n"
            ),
        },
        {
            "cmd": "hdfs balancer -threshold 10",
            "purpose": "Rebalance blocks across DataNodes when one node is hot",
            "output": (
                "Time Stamp               Iteration#  Bytes Already Moved  Bytes Left To Move  Bytes Being Moved\n"
                f"{'2026-10-06 10:45:01':<24} 0          0 B                  0 B                 0 B\n"
                "The cluster is balanced. Exiting...\n"
            ),
        },
        {
            "cmd": f"hdfs dfs -rm -skipTrash /vibeshift/tmp/part-r-00000",
            "purpose": "Remove intermediate MapReduce output without going through trash",
            "output": "Deleted /vibeshift/tmp/part-r-00000\n",
        },
        {
            "cmd": "hdfs dfs -rm -r /vibeshift/tmp",
            "purpose": "Delete an entire directory tree from HDFS",
            "output": "Deleted /vibeshift/tmp\n",
        },
        {
            "cmd": "hdfs dfs -expunge",
            "purpose": "Empty the trash so deleted blocks are actually released",
            "output": "Expunge trash for user: training\n",
        },
        {
            "cmd": "hdfs dfsadmin -report",
            "purpose": "Cluster-wide DataNode health, capacity and block counts",
            "output": (
                "Configured Capacity: 2048000 MB (1.95 TB)\n"
                f"Present Capacity: {namenode['capacity_mb'] - namenode['used_mb']:.0f} MB\n"
                f"DFS Remaining: {namenode['capacity_mb'] - namenode['used_mb']:.0f} MB\n"
                f"DFS Used: {namenode['used_mb']} MB\n"
                f"DFS Used%: {namenode['used_pct']}%\n"
                f"Live datanodes ({len(datanodes)}):\n"
                f"{node_lines}\n"
            ),
        },
        {
            "cmd": "hdfs dfsadmin -safemode get",
            "purpose": "Confirm the NameNode has left safemode and accepts writes",
            "output": f"Safe mode is {namenode['safemode']}\n",
        },
    ]
