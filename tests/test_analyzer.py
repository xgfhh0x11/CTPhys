"""Regression tests for the histogram analyser.

The shipped phase histograms have well-defined qualitative properties
(modality, tail behaviour). These tests pin those properties so a
future contributor can compare a fresh run to the committed reference.
"""
import os

import pytest

from analyze_histogram import load_histogram, summarise, _peaks


_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(os.path.dirname(_HERE), 'data')


# --- parser ---

def test_loader_skips_blank_and_comment_lines(tmp_path):
    p = tmp_path / 'h.txt'
    p.write_text(
        "# comment\n"
        "\n"
        "100 5\n"
        "# another comment\n"
        "101 3\n"
    )
    h = load_histogram(str(p))
    assert h == {100: 5, 101: 3}


def test_loader_rejects_malformed_line(tmp_path):
    p = tmp_path / 'h.txt'
    p.write_text('100 5\nbad line here\n')
    with pytest.raises(ValueError, match='expected two columns'):
        load_histogram(str(p))


def test_loader_drops_nonpositive_counts(tmp_path):
    p = tmp_path / 'h.txt'
    p.write_text('100 5\n101 0\n102 3\n')
    assert load_histogram(str(p)) == {100: 5, 102: 3}


# --- summary statistics ---

def test_summary_on_empty_histogram():
    s = summarise({})
    assert s.samples == 0
    assert s.median == 0
    assert s.peak_count == 0


def test_median_on_handcrafted_histogram():
    # 100 occurrences at cycle 50, 100 at cycle 60. Median falls at 50.
    s = summarise({50: 100, 60: 100})
    assert s.samples == 200
    assert s.median == 50


def test_peak_count_unimodal():
    # A clean Gaussian-ish unimodal distribution centred on 68.
    hist = {
        64: 100, 65: 500, 66: 1500, 67: 3000, 68: 5000,
        69: 3000, 70: 1500, 71: 500, 72: 100,
    }
    s = summarise(hist)
    assert s.peak_count == 1


def test_peak_count_bimodal():
    hist = {
        # Mode 1 around 60.
        58: 100, 59: 500, 60: 2000, 61: 500, 62: 100,
        # Mode 2 around 95 (well-separated, equally prominent).
        93: 100, 94: 500, 95: 2000, 96: 500, 97: 100,
    }
    s = summarise(hist)
    assert s.peak_count == 2


# --- shipped data: regression on qualitative properties ---

def _load_shipped(name: str):
    return load_histogram(os.path.join(_DATA, name))


def test_phase3_histogram_is_multimodal():
    s = summarise(_load_shipped('phase3_histogram.txt'))
    assert s.peak_count >= 2, (
        f'phase 3 should be multi-modal; analyser found peak_count={s.peak_count}'
    )


def test_phase3_has_wider_tail_than_phase4():
    s3 = summarise(_load_shipped('phase3_histogram.txt'))
    s4 = summarise(_load_shipped('phase4_histogram.txt'))
    # The qualitative regression: phase 3's tail is more elongated than
    # phase 4's (which collapsed after the volatile removal).
    assert s3.tail_factor > s4.tail_factor


def test_phase4_histogram_is_unimodal():
    s = summarise(_load_shipped('phase4_histogram.txt'))
    assert s.peak_count == 1, (
        f'phase 4 should be unimodal; analyser found peak_count={s.peak_count}'
    )


def test_phase4_short_tail():
    s = summarise(_load_shipped('phase4_histogram.txt'))
    # Phase 4's distribution is narrow.
    assert s.tail_factor < 1.3


def test_phase5_histogram_is_multimodal_again():
    s = summarise(_load_shipped('phase5_histogram.txt'))
    assert s.peak_count >= 2, (
        f'phase 5 should be multi-modal; analyser found peak_count={s.peak_count}'
    )


def test_phase_sample_counts_are_substantial():
    """Each shipped histogram represents a large-N campaign; the
    minimum count here ensures the analyser's percentile/MAD outputs
    are well-defined."""
    for name in ('phase3_histogram.txt', 'phase4_histogram.txt',
                 'phase5_histogram.txt'):
        s = summarise(_load_shipped(name))
        assert s.samples >= 50_000, (
            f'{name}: sample count {s.samples} too small for the statistics '
            'pinned by the other tests in this file to be meaningful'
        )


def test_peaks_helper_handles_constant_floor():
    """The peak detector must not crash on a near-flat histogram."""
    hist = {i: 100 for i in range(50, 60)}
    peaks = _peaks(hist)
    # Either one peak or none; the property under test is just
    # "doesn't crash" + "returns a list".
    assert isinstance(peaks, list)
