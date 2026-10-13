"""Ingestion tests - the CSV reader must not drop well-formed rows."""

from __future__ import annotations

import pandas as pd

from app.pipeline.ingest import read_csv_safe


def test_read_csv_safe_keeps_quoted_commas(tmp_path):
    """Quoted titles/artist lists contain commas; none of those rows may vanish.

    Regression test: the reader used ``quoting=3`` (QUOTE_NONE) plus
    ``on_bad_lines='skip'``, which silently discarded every quoted line that
    contained a comma - 28% of the real 1.2M-row corpus.
    """
    csv = tmp_path / "tracks_features.csv"
    csv.write_text(
        "id,name,artists,year,danceability,energy,valence,tempo,acousticness,"
        "instrumentalness,loudness,speechiness\n"
        't1,"Hello, Goodbye",["The Beatles"],1967,0.5,0.6,0.7,120,0.2,0.0,-8,0.05\n'
        't2,"Time, Love and Tenderness","[\'Michael Bolton\', \'Someone Else\']",'
        "1991,0.6,0.7,0.5,110,0.3,0.0,-9,0.06\n"
        "t3,Plain Title,['Plain Artist'],2001,0.4,0.5,0.4,100,0.5,0.1,-10,0.04\n",
        encoding="utf-8",
    )

    df = read_csv_safe(csv)

    assert len(df) == 3, "rows with commas inside quotes must be kept"
    assert df.loc[0, "name"] == "Hello, Goodbye"
    assert df.loc[1, "artists"] == "['Michael Bolton', 'Someone Else']"
    assert df["year"].tolist() == [1967, 1991, 2001]


def test_read_csv_safe_survives_an_unterminated_quote(tmp_path):
    """A truncated quote aborts the C parser; the loader must still return data.

    Rows before the damaged record have to survive, and the call must not raise -
    a single bad line at the end of a 330 MB file cannot be allowed to fail a run.
    """
    csv = tmp_path / "broken.csv"
    csv.write_text(
        "id,name,year\n"
        "t1,ok,1999\n"
        't2,"unterminated,2000\n',
        encoding="utf-8",
    )

    df = read_csv_safe(csv)

    assert isinstance(df, pd.DataFrame)
    assert "t1" in df["id"].tolist(), "well-formed rows must be kept"
