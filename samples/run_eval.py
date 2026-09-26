"""Run every sample label through the real extractor + rules and compare to the expected verdict.

Usage: python samples/run_eval.py [--provider claude|ocr]
Reports accuracy and per-label latency (Sarah's bar: ~5 seconds).
"""

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction import get_extractor  # noqa: E402
from app.imaging import prepare_image  # noqa: E402
from app.models import ApplicationData, Status  # noqa: E402
from app.verification.verifier import build_result  # noqa: E402

LABELS = Path(__file__).parent / "labels"


async def run_one(extractor, row):
    image, media_type = prepare_image((LABELS / row["filename"]).read_bytes())
    app = ApplicationData(**{k: (row[k] or None) for k in ApplicationData.model_fields if k in row})
    start = time.perf_counter()
    label = await extractor.extract(image, media_type)
    elapsed = time.perf_counter() - start
    return row, build_result(app, label, extractor.name, int(elapsed * 1000)), elapsed


async def main(provider: str):
    extractor = get_extractor(provider)
    rows = list(csv.DictReader(open(LABELS / "applications.csv", encoding="utf-8")))
    results = await asyncio.gather(*(run_one(extractor, r) for r in rows))

    correct = 0
    for row, result, elapsed in results:
        ok = result.overall.value == row["expected_result"]
        correct += ok
        print(f"{'OK  ' if ok else 'MISS'} {row['filename']:<32} expected={row['expected_result']:<6} "
              f"got={result.overall.value:<6} {elapsed:5.1f}s")
        for f in result.fields:
            if f.status in (Status.FAIL, Status.REVIEW):
                print(f"       - {f.label}: {f.status.value}. {f.message}")
    times = sorted(e for _, _, e in results)
    print(f"\n{correct}/{len(results)} correct | latency median {times[len(times) // 2]:.1f}s, max {times[-1]:.1f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="claude")
    asyncio.run(main(p.parse_args().provider))
