"""Silicon Sample Benchmark harness. See SKILL.md and /workspace/run/DESIGN.md."""
from . import spec, card, score, synth, task, predict, deposit, gates  # noqa: F401


def run(what: str = "status") -> str:
    """Report harness status: spec selftest, run inventory, scoreboard tail.

    `what` is one of: status, spec, runs, scoreboard.
    """
    from . import gates as g
    if what == "spec":
        return spec.selftest()
    if what == "runs":
        return g.list_runs()
    if what == "scoreboard":
        return g.scoreboard_tail()
    return "\n".join([spec.selftest(), g.list_runs(), g.scoreboard_tail()])
