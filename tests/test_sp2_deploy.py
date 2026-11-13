from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sp2_deploy.sh"


def _script_for_fake_tree(tmp_path: Path, fake_repo: Path, fake_cam: Path) -> Path:
    text = SCRIPT.read_text()
    text = text.replace(
        "REPO=/glade/work/fillmore/CERES-SARB-CAM7",
        f"REPO={fake_repo}",
    )
    text = text.replace(
        "CAM=/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam",
        f"CAM={fake_cam}",
    )
    script = tmp_path / "sp2_deploy.sh"
    script.write_text(text)
    script.chmod(0o755)
    return script


def test_deploy_skips_patch_when_added_lines_exist_but_context_drifted(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_cam = tmp_path / "cam"
    (fake_repo / "src" / "cam").mkdir(parents=True)
    (fake_cam / "bld").mkdir(parents=True)
    (fake_cam / "src" / "control").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam7").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam").mkdir(parents=True)

    (fake_cam / "bld" / "build-namelist").write_text(
        "alpha\n"
        "add_default($nl, 'aod_optics_method');\n"
        "omega\n"
    )
    (fake_repo / "src" / "cam" / "build-namelist.diff").write_text(
        "diff --git a/bld/build-namelist b/bld/build-namelist\n"
        "--- a/bld/build-namelist\n"
        "+++ b/bld/build-namelist\n"
        "@@ -1,2 +1,3 @@\n"
        " alpha\n"
        "+add_default($nl, 'aod_optics_method');\n"
        " beta\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=fake_cam, check=True)
    subprocess.run(["git", "add", "bld/build-namelist"], cwd=fake_cam, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-qm", "base"],
        cwd=fake_cam,
        check=True,
    )

    script = _script_for_fake_tree(tmp_path, fake_repo, fake_cam)
    result = subprocess.run([str(script)], cwd=tmp_path, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "SKIP: build-namelist.diff changes already present" in result.stdout


def test_deploy_rejects_partial_patch_with_stale_removed_line(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_cam = tmp_path / "cam"
    (fake_repo / "src" / "cam").mkdir(parents=True)
    (fake_cam / "bld").mkdir(parents=True)
    (fake_cam / "src" / "control").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam7").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam").mkdir(parents=True)

    (fake_cam / "bld" / "build-namelist").write_text(
        "alpha\n"
        "old_call();\n"
        "omega\n"
        "new_call();\n"
    )
    (fake_repo / "src" / "cam" / "build-namelist.diff").write_text(
        "diff --git a/bld/build-namelist b/bld/build-namelist\n"
        "--- a/bld/build-namelist\n"
        "+++ b/bld/build-namelist\n"
        "@@ -1,3 +1,3 @@\n"
        " alpha\n"
        "-old_call();\n"
        "+new_call();\n"
        " beta\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=fake_cam, check=True)
    subprocess.run(["git", "add", "bld/build-namelist"], cwd=fake_cam, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-qm", "base"],
        cwd=fake_cam,
        check=True,
    )

    script = _script_for_fake_tree(tmp_path, fake_repo, fake_cam)
    result = subprocess.run([str(script)], cwd=tmp_path, text=True, capture_output=True)

    assert result.returncode != 0
    assert "ERROR: build-namelist.diff does not apply cleanly" in result.stdout


def test_deploy_postimage_fallback_handles_lines_starting_with_diff_markers(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_cam = tmp_path / "cam"
    (fake_repo / "src" / "cam").mkdir(parents=True)
    (fake_cam / "bld").mkdir(parents=True)
    (fake_cam / "src" / "control").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam7").mkdir(parents=True)
    (fake_cam / "src" / "physics" / "cam").mkdir(parents=True)

    (fake_cam / "bld" / "build-namelist").write_text("omega\n+new_line\n-new_line\nbeta\n")
    (fake_repo / "src" / "cam" / "build-namelist.diff").write_text(
        "diff --git a/bld/build-namelist b/bld/build-namelist\n"
        "--- a/bld/build-namelist\n"
        "+++ b/bld/build-namelist\n"
        "@@ -1,2 +1,4 @@\n"
        " alpha\n"
        "++new_line\n"
        "+-new_line\n"
        " beta\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=fake_cam, check=True)
    subprocess.run(["git", "add", "bld/build-namelist"], cwd=fake_cam, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-qm", "base"],
        cwd=fake_cam,
        check=True,
    )

    script = _script_for_fake_tree(tmp_path, fake_repo, fake_cam)
    result = subprocess.run([str(script)], cwd=tmp_path, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "SKIP: build-namelist.diff changes already present" in result.stdout
