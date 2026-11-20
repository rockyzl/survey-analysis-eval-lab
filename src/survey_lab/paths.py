from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CATALOG = ROOT / "catalog"
GOLD = ROOT / "gold"
RESULTS = ROOT / "results"
LLCP_PARQUET = RAW / "brfss2025" / "llcp2025.parquet"
SLIM_PARQUET = PROCESSED / "llcp2025_slim.parquet"
PT_SNAPSHOT = RAW / "cdc_pt" / "cdc_pt_2025.csv"
