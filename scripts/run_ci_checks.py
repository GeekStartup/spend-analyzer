import argparse
import shutil
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

Step = tuple[str, list[str]]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INSTALL_STEPS: tuple[Step, ...] = (
    (
        "Upgrade pip",
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
    ),
    (
        "Install runtime dependencies",
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    ),
    (
        "Install development dependencies",
        [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
    ),
)

NON_COMPOSE_CHECK_STEPS: tuple[Step, ...] = (
    (
        "Run Ruff lint",
        [sys.executable, "-m", "ruff", "check", "--output-format=github", "."],
    ),
    (
        "Run Ruff format check",
        [sys.executable, "-m", "ruff", "format", "--check", "."],
    ),
    ("Run Bandit security scan", [sys.executable, "-m", "bandit", "-r", "app"]),
    (
        "Audit runtime Python dependencies",
        [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"],
    ),
    (
        "Audit development Python dependencies",
        [sys.executable, "-m", "pip_audit", "-r", "requirements-dev.txt"],
    ),
    (
        "Run tests with coverage",
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=app",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=json:coverage.json",
        ],
    ),
    (
        "Check coverage thresholds",
        [sys.executable, "scripts/check_coverage.py", "coverage.json", "95", "95"],
    ),
)


@contextmanager
def prepare_compose_env_file(
    project_root: Path = PROJECT_ROOT,
) -> Iterator[Path]:
    local_env_file = project_root / ".env"

    if local_env_file.is_file():
        yield local_env_file
        return

    example_env_file = project_root / ".env.example"

    if not example_env_file.is_file():
        raise FileNotFoundError("Neither .env nor .env.example exists")

    shutil.copyfile(example_env_file, local_env_file)

    try:
        yield local_env_file
    finally:
        local_env_file.unlink(missing_ok=True)


def build_check_steps(env_file: Path) -> tuple[Step, ...]:
    env_file_argument = str(env_file)

    compose_check_steps: tuple[Step, ...] = (
        (
            "Validate normal Docker Compose configuration",
            [
                "docker",
                "compose",
                "--env-file",
                env_file_argument,
                "config",
                "--quiet",
            ],
        ),
        (
            "Validate observability Docker Compose configuration",
            [
                "docker",
                "compose",
                "--env-file",
                env_file_argument,
                "--profile",
                "observability",
                "config",
                "--quiet",
            ],
        ),
        (
            "Validate test Docker Compose configuration",
            [
                "docker",
                "compose",
                "--env-file",
                env_file_argument,
                "-f",
                "docker-compose.test.yml",
                "config",
                "--quiet",
            ],
        ),
    )

    return compose_check_steps + NON_COMPOSE_CHECK_STEPS


def run_command(name: str, command: Sequence[str]) -> int:
    print(f"\n==> {name}")
    print("$ " + " ".join(command))
    completed_process = subprocess.run(
        command,
        check=False,
        cwd=PROJECT_ROOT,
    )
    return completed_process.returncode


def run_steps(steps: Sequence[Step]) -> int:
    for name, command in steps:
        exit_code = run_command(name, command)
        if exit_code != 0:
            print(f"\nFailed: {name}")
            return exit_code

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the same checks as the GitHub Actions build."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip dependency installation and run checks only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_install:
        install_exit_code = run_steps(INSTALL_STEPS)
        if install_exit_code != 0:
            return install_exit_code

    try:
        with prepare_compose_env_file() as env_file:
            check_exit_code = run_steps(build_check_steps(env_file))
    except FileNotFoundError as error:
        print(f"\nFailed: {error}")
        return 1

    if check_exit_code != 0:
        return check_exit_code

    print("\nAll local CI checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
