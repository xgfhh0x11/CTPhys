#!/usr/bin/env python3
"""Histogram analyser for CTPhys cycle-count outputs.

Reads a `cycles count` two-column text file (lines starting with `#`
are comments) and reports:

    samples       : total number of measured iterations
    median        : median cycle count
    mad           : median absolute deviation (Huber, 1981)
    p99           : 99th-percentile cycle count
    peak_count    : number of local maxima above the prominence floor;
                    a crude modality estimator
    tail_factor   : p99 / median, indicating tail elongation

Usage:
    python scripts/analyze_histogram.py data/phase3_histogram.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass(frozen=True)
class HistogramSummary:
    samples: int
    median: int
    mad: float
    p99: int
    peak_count: int
    tail_factor: float


def load_histogram(path: str) -> Dict[int, int]:
    """Parse a `cycles count` file into {cycles: count}."""
    out: Dict[int, int] = {}
    with open(path, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            parts = stripped.split()
            if len(parts) != 2:
                raise ValueError(f'{path}:{lineno}: expected two columns, got {stripped!r}')
            try:
                cycles = int(parts[0])
                count = int(parts[1])
            except ValueError as e:
                raise ValueError(
                    f'{path}:{lineno}: expected two integer columns, got {stripped!r}'
                ) from e
            if cycles < 0:
                raise ValueError(f'{path}:{lineno}: negative cycle count')
            if count <= 0:
                continue
            out[cycles] = out.get(cycles, 0) + count
    return out


def _quantile(sorted_pairs, total: int, q: float) -> int:
    """Quantile in cycle-space from a sorted (cycle, count) list and the
    aggregate total."""
    if total == 0:
        return 0
    target = q * total
    seen = 0
    for cycles, count in sorted_pairs:
        seen += count
        if seen >= target:
            return cycles
    return sorted_pairs[-1][0]


def _median(sorted_pairs, total: int) -> int:
    return _quantile(sorted_pairs, total, 0.5)


def _mad(sorted_pairs, total: int, median: int) -> float:
    """MAD of the cycle distribution: median absolute deviation from
    the median, computed in original units."""
    devs: List[tuple] = sorted(((abs(c - median), n) for c, n in sorted_pairs))
    return float(_quantile(devs, total, 0.5))


def _peaks(hist: Dict[int, int],
           prominence_frac: float = 0.05,
           min_gap: int = 5) -> List[int]:
    """Crude peak detector: a point `c` is a peak if its count is at
    least `prominence_frac * max(counts)` and is the local maximum within
    `±min_gap` cycles."""
    if not hist:
        return []
    floor = max(hist.values()) * prominence_frac
    cycles_sorted = sorted(hist.keys())
    cycle_set = set(cycles_sorted)
    peaks: List[int] = []
    for c in cycles_sorted:
        if hist[c] < floor:
            continue
        # Check that c is a local max within ±min_gap.
        is_peak = True
        for d in range(1, min_gap + 1):
            if (c - d) in cycle_set and hist[c - d] > hist[c]:
                is_peak = False
                break
            if (c + d) in cycle_set and hist[c + d] > hist[c]:
                is_peak = False
                break
        if not is_peak:
            continue
        # Merge with previous peak if within min_gap.
        if peaks and (c - peaks[-1]) <= min_gap:
            if hist[c] > hist[peaks[-1]]:
                peaks[-1] = c
            continue
        peaks.append(c)
    return peaks


def summarise(hist: Dict[int, int]) -> HistogramSummary:
    if not hist:
        return HistogramSummary(0, 0, 0.0, 0, 0, 0.0)
    sorted_pairs = sorted(hist.items())
    total = sum(c for _, c in sorted_pairs)
    median = _median(sorted_pairs, total)
    mad = _mad(sorted_pairs, total, median)
    p99 = _quantile(sorted_pairs, total, 0.99)
    peaks = _peaks(hist)
    tail = (p99 / median) if median > 0 else 0.0
    return HistogramSummary(
        samples=total,
        median=median,
        mad=mad,
        p99=p99,
        peak_count=len(peaks),
        tail_factor=tail,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='histogram file (cycles count, # comments OK)')
    ap.add_argument('--json', action='store_true', help='emit JSON only')
    args = ap.parse_args(argv)

    try:
        hist = load_histogram(args.path)
    except (ValueError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2

    summary = summarise(hist)

    if args.json:
        print(json.dumps(asdict(summary), indent=2))
    else:
        print(f'samples       : {summary.samples}')
        print(f'median        : {summary.median}')
        print(f'mad           : {summary.mad:.2f}')
        print(f'p99           : {summary.p99}')
        print(f'peak_count    : {summary.peak_count}')
        print(f'tail_factor   : {summary.tail_factor:.2f}')
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
