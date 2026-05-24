import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: python scripts/check_coverage.py "
            "<coverage-json> <min-line-percent> <min-branch-percent>"
        )
        return 2

    coverage_file = Path(sys.argv[1])
    min_line_percent = float(sys.argv[2])
    min_branch_percent = float(sys.argv[3])

    coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
    totals = coverage["totals"]

    line_percent = float(totals["percent_covered"])
    covered_branches = int(totals.get("covered_branches", 0))
    num_branches = int(totals.get("num_branches", 0))
    branch_percent = (
        100.0 if num_branches == 0 else covered_branches / num_branches * 100
    )

    print(f"Line coverage: {line_percent:.2f}%")
    print(f"Branch coverage: {branch_percent:.2f}%")

    failed = False

    if line_percent < min_line_percent:
        print(
            f"Line coverage {line_percent:.2f}% is below required "
            f"{min_line_percent:.2f}%"
        )
        failed = True

    if branch_percent < min_branch_percent:
        print(
            f"Branch coverage {branch_percent:.2f}% is below required "
            f"{min_branch_percent:.2f}%"
        )
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
