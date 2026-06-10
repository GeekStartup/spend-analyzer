from pathlib import Path

import pytest

from scripts.run_ci_checks import build_check_steps, select_compose_env_file


def test_select_compose_env_file_prefers_local_env(tmp_path: Path):
    local_env_file = tmp_path / ".env"
    example_env_file = tmp_path / ".env.example"
    local_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")
    example_env_file.write_text("APP_PORT=9000\n", encoding="utf-8")

    assert select_compose_env_file(tmp_path) == local_env_file


def test_select_compose_env_file_falls_back_to_example(tmp_path: Path):
    example_env_file = tmp_path / ".env.example"
    example_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")

    assert select_compose_env_file(tmp_path) == example_env_file


def test_select_compose_env_file_requires_an_env_source(tmp_path: Path):
    with pytest.raises(
        FileNotFoundError,
        match=r"Neither \.env nor \.env\.example exists",
    ):
        select_compose_env_file(tmp_path)


def test_build_check_steps_uses_selected_env_file(tmp_path: Path):
    example_env_file = tmp_path / ".env.example"
    example_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")

    steps = dict(build_check_steps(tmp_path))

    assert steps["Validate normal Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(example_env_file),
        "config",
        "--quiet",
    ]
    assert steps["Validate observability Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(example_env_file),
        "--profile",
        "observability",
        "config",
        "--quiet",
    ]
    assert steps["Validate test Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(example_env_file),
        "-f",
        "docker-compose.test.yml",
        "config",
        "--quiet",
    ]
