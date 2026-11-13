from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
HELP_ARGUMENTS = ("help", "--help", "-h")


def project_skills() -> list[Path]:
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def help_section(text: str) -> str:
    marker = "## Help Mode"
    assert marker in text
    remainder = text.split(marker, maxsplit=1)[1]
    return remainder.split("\n## ", maxsplit=1)[0]


def test_every_project_skill_has_brief_no_side_effect_help_mode() -> None:
    skills = project_skills()
    assert skills

    for skill_path in skills:
        section = help_section(skill_path.read_text(encoding="utf-8"))
        normalized_section = " ".join(section.split())
        skill_name = skill_path.parent.name

        for argument in HELP_ARGUMENTS:
            assert f"${skill_name} {argument}" in normalized_section
        assert "Do not use tools" in normalized_section
        assert "then stop" in normalized_section

        bullets = [line for line in section.splitlines() if line.startswith("- ")]
        assert 4 <= len(bullets) <= 7
        assert all(len(bullet) <= 120 for bullet in bullets)


def test_project_skill_display_names_start_with_domain() -> None:
    expected_prefixes = {
        "closeout-ceres-runs": "CERES ",
        "configure-cesm3-runs": "CESM3 ",
        "postprocess-ceres-davinci": "CERES ",
        "preprocess-ceres-data": "CERES ",
    }

    for skill_name, prefix in expected_prefixes.items():
        metadata_path = SKILLS_ROOT / skill_name / "agents" / "openai.yaml"
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        assert metadata["interface"]["display_name"].startswith(prefix)
