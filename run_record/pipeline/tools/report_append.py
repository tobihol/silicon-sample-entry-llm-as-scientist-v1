#!/usr/bin/env python
"""Append one line to a shared markdown file under the harness's cross-process lock.

    /opt/kernel/venv/bin/python tools/report_append.py REPORT.md "Arm partisan session ..."

Two arms may write REPORT.md concurrently. `ssb.gates.exclusive` holds an advisory flock for the
whole read -> append -> write cycle and `ssb.gates._atomic_write` replaces the file through a temp
file in the same directory, so a concurrent reader can never see a partial file and neither writer
can lose the other's line. Refuses to add a line that is already present, so a re-run is a no-op.
"""
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402


def main(target: str, line: str) -> int:
    p = RUN / target
    with ssb.gates.exclusive("report"):
        cur = p.read_text() if p.exists() else ""
        if line.strip() in cur:
            print("already present, no write")
            return 0
        new = cur.rstrip("\n") + "\n\n" + line.rstrip("\n") + "\n"
        ssb.gates._atomic_write(p, new)
    print(f"appended 1 line to {target} under lock 'report' ({len(new)} bytes)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
