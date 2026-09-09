#!/usr/bin/env python3
"""Render the shipped reference histograms as a single panel for the
README. Run separately from the test pipeline because matplotlib
isn't a hard dependency of the analyser.

Usage:
    pip install matplotlib
    python scripts/plot_histograms.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from analyze_histogram import load_histogram  # noqa: E402

try:
    import matplotlib.pyplot as plt
except ImportError:
    print('matplotlib is required for plotting; install with: pip install matplotlib')
    sys.exit(1)


REPO = os.path.dirname(_HERE)
DATA = os.path.join(REPO, 'data')

FILES = [
    ('phase3_histogram.txt', 'Phase 3 — cache eliminated, volatile retained'),
    ('phase4_histogram.txt', 'Phase 4 — volatile dropped'),
    ('phase5_histogram.txt', 'Phase 5 — ALU dependency chain injected'),
]


def main():
    fig, axes = plt.subplots(len(FILES), 1, figsize=(10, 9), sharey=False)
    for ax, (name, title) in zip(axes, FILES):
        hist = load_histogram(os.path.join(DATA, name))
        xs = sorted(hist.keys())
        ys = [hist[x] for x in xs]
        ax.bar(xs, ys, width=1.0)
        ax.set_title(title)
        ax.set_xlabel('cycles')
        ax.set_ylabel('count')
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = os.path.join(REPO, 'data', 'histograms.png')
    fig.savefig(out, dpi=120)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
