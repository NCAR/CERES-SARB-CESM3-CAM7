from __future__ import annotations

from pathlib import Path

import pytest
import xarray as xr


def _touch_complete_group(indir: Path, stamp: str) -> None:
    from sp3_tests.check_sp3_outputs import DEFAULT_BANDS

    for band in DEFAULT_BANDS:
        (indir / f"AER_MAM4_{band}.{stamp}.nc").touch()


def test_h0i_pairs_match_on_off_case_names(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import h0i_pairs

    on_run = tmp_path / "on"
    off_run = tmp_path / "off"
    on_run.mkdir()
    off_run.mkdir()
    on_file = on_run / "sp3_verify10_on.cam.h0i.2008-07-01-00000.nc"
    off_file = off_run / "sp3_verify10_off.cam.h0i.2008-07-01-00000.nc"
    on_file.touch()
    off_file.touch()

    assert h0i_pairs(on_run, off_run) == [(on_file, off_file)]


def test_h0i_pairs_reject_missing_off_pair(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import h0i_pairs

    on_run = tmp_path / "on"
    off_run = tmp_path / "off"
    on_run.mkdir()
    off_run.mkdir()
    (on_run / "sp3_verify10_on.cam.h0i.2008-07-01-00000.nc").touch()

    with pytest.raises(AssertionError, match="missing OFF h0i pair"):
        h0i_pairs(on_run, off_run)


def test_h0i_pairs_reject_unexpected_pair_count(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import h0i_pairs

    on_run = tmp_path / "on"
    off_run = tmp_path / "off"
    on_run.mkdir()
    off_run.mkdir()
    (on_run / "sp3_verify10_on.cam.h0i.2008-07-01-00000.nc").touch()
    (off_run / "sp3_verify10_off.cam.h0i.2008-07-01-00000.nc").touch()

    with pytest.raises(AssertionError, match="expected 10 h0i pairs"):
        h0i_pairs(on_run, off_run, expected_count=10)


def test_h0i_pairs_check_expected_first_and_last_stamps(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import h0i_pairs

    on_run = tmp_path / "on"
    off_run = tmp_path / "off"
    on_run.mkdir()
    off_run.mkdir()
    for stamp in ("2008-07-02-00000", "2008-07-03-00000"):
        (on_run / f"sp3_verify10_on.cam.h0i.{stamp}.nc").touch()
        (off_run / f"sp3_verify10_off.cam.h0i.{stamp}.nc").touch()

    pairs = h0i_pairs(
        on_run,
        off_run,
        expected_count=2,
        expected_first_stamp="2008-07-02-00000",
        expected_last_stamp="2008-07-03-00000",
    )

    assert len(pairs) == 2
    with pytest.raises(AssertionError, match="expected first h0i stamp"):
        h0i_pairs(on_run, off_run, expected_first_stamp="2008-07-01-00000")


def test_assert_cprnc_identical_requires_every_log_to_be_identical(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_cprnc_identical

    good = tmp_path / "good.log"
    bad = tmp_path / "bad.log"
    good.write_text("files are IDENTICAL\n")
    bad.write_text("DIFFERENT\n")

    with pytest.raises(AssertionError, match="bad.log"):
        assert_cprnc_identical([good, bad])


def test_assert_cprnc_identical_accepts_real_success_summary(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_cprnc_identical

    good = tmp_path / "good.log"
    good.write_text(
        "          of which      0 had non-zero differences\n"
        "               and      0 had differences in fill patterns\n"
        "               and      0 had different dimension sizes\n"
        "               and      0 had different data types\n"
        "  diff_test: the two files seem to be IDENTICAL\n"
    )

    assert_cprnc_identical([good])


def test_assert_cprnc_identical_rejects_negative_identical_phrase(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_cprnc_identical

    bad = tmp_path / "bad.log"
    bad.write_text("files are not IDENTICAL\n")

    with pytest.raises(AssertionError, match="bad.log"):
        assert_cprnc_identical([bad])


def test_assert_cprnc_results_identical_requires_zero_returncode(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import CprncResult
    from sp3_tests.verify_sp3_t10 import assert_cprnc_results_identical

    result = CprncResult(
        on_file="on.nc",
        off_file="off.nc",
        log_file=str(tmp_path / "cprnc.log"),
        returncode=2,
        identical=True,
    )

    with pytest.raises(AssertionError, match="returncode=2"):
        assert_cprnc_results_identical([result])


def test_assert_sp3_directory_complete_checks_expected_group_count(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_sp3_directory_complete

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    (sp3 / "AER_MAM4_SW01.20080701.00000.nc").touch()

    with pytest.raises(AssertionError, match="expected 26 files"):
        assert_sp3_directory_complete(sp3, expected_groups=1)


def test_assert_sp3_directory_complete_checks_expected_window(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_sp3_directory_complete

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    _touch_complete_group(sp3, "20080701.00000")
    _touch_complete_group(sp3, "20080701.10800")

    summary = assert_sp3_directory_complete(
        sp3,
        expected_groups=2,
        expected_first_stamp="20080701.00000",
        expected_last_stamp="20080701.10800",
    )

    assert summary.first_stamp == "20080701.00000"
    with pytest.raises(AssertionError, match="expected last stamp"):
        assert_sp3_directory_complete(sp3, expected_groups=2, expected_last_stamp="20080702.00000")


def test_assert_no_sp3_files_rejects_off_output(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_no_sp3_files

    off = tmp_path / "off"
    off.mkdir()
    (off / "AER_MAM4_SW01.20080701.00000.nc").touch()

    with pytest.raises(AssertionError, match="expected no SP3 files"):
        assert_no_sp3_files(off)


def test_assert_no_sp3_files_treats_missing_directory_as_zero_files(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_no_sp3_files

    assert assert_no_sp3_files(tmp_path / "missing") == 0


def test_assert_sp3_attrs_checks_method_lut_and_nudged_attrs(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_sp3_attrs

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    path = sp3 / "AER_MAM4_SW05.20080701.10800.nc"
    xr.Dataset(attrs={"method": "lut", "lut_file": "table.nc", "nudged": 1}).to_netcdf(path)

    assert_sp3_attrs(sp3, expected_method="lut", expected_lut_file="table.nc", expected_nudged=1)


def test_assert_sp3_attrs_rejects_missing_sp3v2_lut_attrs(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3_t10 import assert_sp3_attrs

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    path = sp3 / "AER_MAM4_SW05.20080701.10800.nc"
    xr.Dataset(attrs={"nudged": 1}).to_netcdf(path)

    with pytest.raises(AssertionError, match="method"):
        assert_sp3_attrs(sp3, expected_method="lut", expected_lut_file="table.nc", expected_nudged=1)
