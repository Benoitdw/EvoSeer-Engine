"""Load the observed target distribution from ISIC 2024 data."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def load_target(cfg: dict) -> list[float]:
    DATA = Path(cfg["data_dir"])
    meta = pl.read_csv(DATA / "metadata.csv", columns=["isic_id", "tbp_lv_areaMM2"])
    sup = pl.read_csv(
        DATA / "ISIC_2024_Training_Supplement.csv", columns=["isic_id", "iddx_1"]
    )
    return (
        meta.join(sup, on="isic_id", how="left")
        .filter(pl.col("iddx_1") == "Benign")["tbp_lv_areaMM2"]
        .drop_nulls()
        .to_list()
    )
