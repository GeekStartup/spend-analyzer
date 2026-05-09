import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_TEST_FILE = PROJECT_ROOT / "docker-compose.test.yml"


def run_docker_compose_command(*args: str) -> None:
    """
    Run docker compose using the test compose file.
    """
    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_TEST_FILE),
        *args,
    ]

    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def start_integration_stack() -> None:
    """
    Start all Docker services required for integration tests.
    """
    run_docker_compose_command("up", "-d", "--build")


def stop_integration_stack() -> None:
    """
    Stop and remove all Docker services used by integration tests.
    """
    run_docker_compose_command("down", "-v")
