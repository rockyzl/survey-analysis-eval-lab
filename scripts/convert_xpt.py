"""Convert the BRFSS LLCP XPT file to parquet (all columns, float64), recording row/col counts."""
import sys, time
from pathlib import Path
import pandas as pd

src = Path(sys.argv[1]); dst = Path(sys.argv[2])
t0 = time.time()
chunks = []
for ch in pd.read_sas(src, format="xport", chunksize=50000):
    chunks.append(ch)
df = pd.concat(chunks, ignore_index=True)
for c in df.columns:
    if df[c].dtype == object:
        df[c] = df[c].apply(lambda v: v.decode("latin-1").strip() if isinstance(v, bytes) else v)
df.to_parquet(dst, index=False)
print(df.shape, round(time.time() - t0, 1), "s")
