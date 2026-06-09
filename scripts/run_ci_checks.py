import argparse
import subprocess
import sys
from collections.abc import Sequence

Step = tuple[str, list[str]]


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

CHECK_STEPS: tuple[Step, ...] = (
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


def run_command(name: str, command: Sequence[str]) -> int:
    print(f"\n==> {name}")
    print("$ " + " ".join(command))
    completed_process = subprocess.run(command, check=False)
    return completed_process.returncode


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
    steps = CHECK_STEPS if args.skip_install else INSTALL_STEPS + CHECK_STEPS

    for name, command in steps:
        exit_code = run_command(name, command)
        if exit_code != 0:
            print(f"\nFailed: {name}")
            return exit_code

    print("\nAll local CI checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
