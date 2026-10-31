"""External file-completion accounting; no video/model IO."""
import pytest
from scripts.summarize_fresh_no_log import completion_intervals


def sample(t,seconds,inspected=True):
    return dict(target_timestamp=t,completion_epoch_ns=10_000_000_000+int(seconds*1e9),inspected=inspected)


def test_startup_second_bins_partial_tail_and_global_packaging_are_separate():
    rows,tail=completion_intervals([sample(0,2),sample(.5,3),sample(1,7),sample(1.5,8,False),sample(2,9)],2.25,10_000_000_000,15)
    assert [r['acquisition_completion_interval_seconds'] for r in rows]==[3,5,1]
    assert [r['detailed_frames'] for r in rows]==[2,1,1]
    assert rows[-1]['acquisition_seconds_per_video_second']==4
    assert tail==6 and sum(r['acquisition_completion_interval_seconds'] for r in rows)+tail==15


def test_missing_sample_second_is_unknown_not_fabricated_zero_cost():
    rows,tail=completion_intervals([sample(0,2),sample(2,8)],3,10_000_000_000,10)
    assert rows[1]['acquisition_completion_interval_seconds'] is None
    assert rows[2]['acquisition_completion_interval_seconds']==6 and tail==2


@pytest.mark.parametrize('samples',[ [sample(0,2),sample(.5,1)], [sample(0,1),sample(0,2)], [sample(3,1)] ])
def test_invalid_clock_order_duplicate_cells_or_out_of_range_are_not_reported(samples):
    with pytest.raises(ValueError):completion_intervals(samples,3,10_000_000_000,10)


def test_completion_after_measured_cli_end_is_not_reported():
    with pytest.raises(ValueError):completion_intervals([sample(0,11)],1,10_000_000_000,10)
