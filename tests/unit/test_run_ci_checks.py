from pathlib import Path

import pytest
from scripts.run_ci_checks import build_check_steps, prepare_compose_env_file


def test_prepare_compose_env_file_preserves_existing_local_env(tmp_path: Path):
    local_env_file = tmp_path / ".env"
    example_env_file = tmp_path / ".env.example"
    local_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")
    example_env_file.write_text("APP_PORT=9000\n", encoding="utf-8")

    with prepare_compose_env_file(tmp_path) as env_file:
        assert env_file == local_env_file
        assert local_env_file.read_text(encoding="utf-8") == "APP_PORT=8000\n"

    assert local_env_file.is_file()
    assert local_env_file.read_text(encoding="utf-8") == "APP_PORT=8000\n"


def test_prepare_compose_env_file_preserves_existing_local_env_after_failure(
    tmp_path: Path,
):
    local_env_file = tmp_path / ".env"
    local_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")

    with (
        pytest.raises(RuntimeError, match="compose failed"),
        prepare_compose_env_file(tmp_path),
    ):
        raise RuntimeError("compose failed")

    assert local_env_file.is_file()
    assert local_env_file.read_text(encoding="utf-8") == "APP_PORT=8000\n"


def test_prepare_compose_env_file_temporarily_copies_example(tmp_path: Path):
    local_env_file = tmp_path / ".env"
    example_env_file = tmp_path / ".env.example"
    example_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")

    with prepare_compose_env_file(tmp_path) as env_file:
        assert env_file == local_env_file
        assert local_env_file.read_text(encoding="utf-8") == "APP_PORT=8000\n"

    assert not local_env_file.exists()


def test_prepare_compose_env_file_removes_generated_file_after_failure(
    tmp_path: Path,
):
    local_env_file = tmp_path / ".env"
    example_env_file = tmp_path / ".env.example"
    example_env_file.write_text("APP_PORT=8000\n", encoding="utf-8")

    with (
        pytest.raises(RuntimeError, match="compose failed"),
        prepare_compose_env_file(tmp_path),
    ):
        raise RuntimeError("compose failed")

    assert not local_env_file.exists()


def test_prepare_compose_env_file_requires_an_env_source(tmp_path: Path):
    with (
        pytest.raises(
            FileNotFoundError,
            match=r"Neither \.env nor \.env\.example exists",
        ),
        prepare_compose_env_file(tmp_path),
    ):
        pass


def test_build_check_steps_uses_prepared_local_env(tmp_path: Path):
    local_env_file = tmp_path / ".env"

    steps = dict(build_check_steps(local_env_file))

    assert steps["Validate normal Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(local_env_file),
        "config",
        "--quiet",
    ]
    assert steps["Validate observability Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(local_env_file),
        "--profile",
        "observability",
        "config",
        "--quiet",
    ]
    assert steps["Validate test Docker Compose configuration"] == [
        "docker",
        "compose",
        "--env-file",
        str(local_env_file),
        "-f",
        "docker-compose.test.yml",
        "config",
        "--quiet",
    ]
