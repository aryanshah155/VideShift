"""Simplified Spotify track schema shared by ingestion, engines, and notebook export."""

from __future__ import annotations

TRACK_ID = "id"
TRACK_NAME = "name"
TRACK_ARTISTS = "artists"
TRACK_YEAR = "year"
TRACK_RELEASE_DATE = "release_date"

META_COLS = [TRACK_ID, TRACK_NAME, TRACK_ARTISTS, TRACK_YEAR, TRACK_RELEASE_DATE]

# Numerical acoustic feature vector used for clustering.
FEATURE_COLS = [
    "danceability",
    "energy",
    "valence",
    "tempo",
    "acousticness",
    "instrumentalness",
    "loudness",
    "speechiness",
]

ALL_COLS = META_COLS + FEATURE_COLS
