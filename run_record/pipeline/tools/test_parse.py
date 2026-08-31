#!/usr/bin/env python
"""Adversarial test of ssb.predict.parse, run BEFORE any budget is spent.

    /opt/kernel/venv/bin/python tools/test_parse.py

The stub predictor emits perfectly formed CSV, so every dry run has tested the parser against
the one input it will never see in production. tools/practice.py ABORTS on an unparsed cell -
correct, but an abort after the batch has been paid for teaches nothing. This suite builds
realistic malformed completions from the TARGET's own condition and outcome names and reports,
per failure mode, how many of the 208 cells survive.

A mode is only "fixed" here if the fix cannot change a well-formed parse: this file is also the
regression test that the hardening did not move the good case.
"""
import re
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402


def grid():
    b = ssb.predict.target_brief()
    conds = [a["title"] for a in b["arms"]]
    outs = [o["name"] for o in b["outcomes"]]
    return conds, outs


def clean(conds, outs, fmt="{c},{o},{v}"):
    lines = ["condition,outcome,ate"]
    for i, c in enumerate(conds):
        for j, o in enumerate(outs):
            lines.append(fmt.format(c=c, o=o, v=round((i - j) * 0.1, 2)))
    return "\n".join(lines)


MODES = {}


def mode(name):
    def deco(f):
        MODES[name] = f
        return f
    return deco


@mode("well_formed")
def _(c, o): return clean(c, o)


@mode("markdown_fence")
def _(c, o): return "```csv\n" + clean(c, o) + "\n```"


@mode("prose_before_and_after")
def _(c, o):
    return ("Here are my predicted average treatment effects. I have reasoned about each message's\n"
            "mechanism and the plausibility of its effect on each outcome.\n\n" + clean(c, o) +
            "\n\nNote that most effects are small, consistent with the megastudy literature.")


@mode("signed_values_with_plus")
def _(c, o): return clean(c, o, "{c},{o},{v:+}").replace("+0.0", "+0.00")


@mode("unit_suffix_pp")
def _(c, o): return clean(c, o, "{c},{o},{v} pp")


@mode("percent_suffix")
def _(c, o): return clean(c, o, "{c},{o},{v}%")


@mode("quoted_fields")
def _(c, o): return clean(c, o, '"{c}","{o}",{v}')


@mode("markdown_table")
def _(c, o):
    lines = ["| condition | outcome | ate |", "|---|---|---|"]
    for i, cc in enumerate(c):
        for j, oo in enumerate(o):
            lines.append("| %s | %s | %s |" % (cc, oo, round((i - j) * 0.1, 2)))
    return "\n".join(lines)


@mode("semicolon_separated")
def _(c, o): return clean(c, o, "{c};{o};{v}")


@mode("tab_separated")
def _(c, o): return clean(c, o, "{c}\t{o}\t{v}")


@mode("trailing_whitespace_and_case")
def _(c, o): return clean(c, o, "{c} , {o} , {v}").upper()


@mode("extra_column")
def _(c, o): return clean(c, o, "{c},{o},{v},small effect")


@mode("na_cells")
def _(c, o): return clean(c, o).replace(",0.0", ",N/A")


@mode("thousands_separator")
def _(c, o): return clean(c, o, "{c},{o},{v}").replace("-1.0", "-1,000")


@mode("typographic_characters_retyped")
def _(c, o):
    """MEASURED in a paid batch (session 8), not anticipated: an arm titled
    `Outpartisans’ Experiences of Harm` came back with a STRAIGHT apostrophe and lost all 9 of
    its cells - the parser is right to refuse a name it was not given, and the cost of being right
    was an aborted arm. The target's own grid carries no curly punctuation, so the same class is
    exercised here in the opposite direction: the answer retypes every space as a non-breaking
    space and every hyphen as an en-dash. Both are the same character in a different encoding."""
    out = []
    for line in clean(c, o).splitlines():
        head, _, val = line.rpartition(",")            # only the NAME fields are retyped
        out.append(head.replace(" ", " ").replace("-", "–") + "," + val)
    return "\n".join(out)


# --- reasoning prefixes: the shapes the `reason`/`reason_rank` prompt variants invite -------
# The frozen argv sets MAX_THINKING_TOKENS=0, so in-text reasoning is the only reasoning channel
# this pipeline has, and a variant that asks for it changes what a completion LOOKS like before it
# changes anything else. Tested here, before that batch is priced, in both directions: the CSV must
# still parse at 208/208 AND prose that names a cell in passing must not overwrite the table (the
# parser keeps the FIRST occurrence, so the dangerous case is prose BEFORE the table).


@mode("reason_then_separator_then_csv")
def _(c, o):
    return ("Analysis:\n- %s: values-based, small positive; I expect it to beat %s.\n"
            "- %s: strongest evidence cue here.\n\n---\n" % (c[0], c[1], c[2])) + clean(c, o)


@mode("ranking_then_csv")
def _(c, o):
    return ("RANKING:\n" + "\n".join(c) + "\nOutcomes: %s moves most, %s least.\n---\n"
            % (o[0], o[-1])) + clean(c, o)


@mode("reasoning_prose_naming_numbers_then_csv")
def _(c, o):
    return ("I expect %s to move %s by about 9.9 pp and %s by 8.8 pp overall.\n\n"
            % (c[0], o[0], c[1])) + clean(c, o)


@mode("csv_then_trailing_prose_naming_a_cell")
def _(c, o):
    return clean(c, o) + "\n\nIn words: %s,%s,9.9 is the headline." % (c[0], o[0])


# ---------------------------------------------------------------------------------------------
# NEGATIVE CONTROLS. A parser that recovers every malformed answer is worthless if it also
# invents cells out of prose. Each of these has an EXPECTED count and the script fails on a miss.
# ---------------------------------------------------------------------------------------------

NEGATIVE = {}


def negative(name, expected):
    def deco(f):
        NEGATIVE[name] = (f, expected)
        return f
    return deco


@negative("prose_only_no_table", 0)
def _(c, o):
    return ("I do not think I can give a responsible estimate for every cell here. Broadly, the\n"
            "consensus messages should help a little and the doom-framing messages may backfire.\n"
            "Most effects will be under one percentage point.")


@negative("prose_sentence_naming_a_cell", 0)
def _(c, o):
    return "In my view %s moves %s by about 2 pp, which is large for this literature." % (c[0], o[0])


@negative("refusal", 0)
def _(c, o):
    return "I'm sorry, but I can't predict the results of an unpublished study."


@negative("wrong_condition_names", 0)
def _(c, o):
    return "\n".join("Arm %d,%s,1.0" % (i, oo) for i in range(3) for oo in o)


@negative("wrong_outcome_names", 0)
def _(c, o):
    return "\n".join("%s,made_up_outcome_%d,1.0" % (cc, j) for cc in c for j in range(3))


@negative("header_only", 0)
def _(c, o):
    return "condition,outcome,ate"


@negative("half_the_grid", None)          # expected = half, computed at run time
def _(c, o):
    return clean(c[: len(c) // 2], o)


# --- numbered arms: the shape task 7 (hackenburg2025, 73 LLM-written messages) forces ---------
# The raw arm ids name the model that wrote each message, so the arms are titled `Message 01`..
# `Message 73` and the id map never reaches a brief. A model that retypes `Message 01` as
# `Message 1` would have lost 4 cells per arm, silently, in a PAID batch - the same class of
# defect as session 8's typographic apostrophe, found here before the money instead of after it.

def numbered_grid(n=73, k=4):
    return ["Message %02d" % (i + 1) for i in range(n)], ["oppose_ban_%d" % (j + 1) for j in range(k)]


def numbered_cases():
    c, o = numbered_grid()
    cases = {
        "numbered_arms_exact": clean(c, o),
        "numbered_arms_leading_zero_dropped": clean([x.replace(" 0", " ") for x in c], o),
        # MEASURED on a paid batch: claude-fable-5 answered every row `message_01,...`
        "numbered_arms_underscored_lowercase": clean(
            [x.replace(" ", "_").lower() for x in c], o),
        "numbered_arms_hyphen_and_no_zero": clean(
            [x.replace(" ", "-").replace("-0", "-") for x in c], o),
        "numbered_arms_mixed": "\n".join(
            line if i % 2 else line.replace("Message 0", "Message ")
            for i, line in enumerate(clean(c, o).splitlines())),
    }
    return c, o, cases


def ambiguity_case():
    """The fold must never merge two arms. If a task ever carries BOTH `Message 01` and
    `Message 1`, the folded key is dropped and only the exact name parses."""
    c = ["Message 01", "Message 1", "Message 02"]
    o = ["oppose_ban_1"]
    return c, o, "Message 1,oppose_ban_1,1.0\nMessage 02,oppose_ban_1,2.0"


def digit_cases():
    """MEASURED on a paid batch (session 11): `claude-sonnet-5` answered task 7's 73 numbered arms
    as `msg01..msg73` and lost ALL 292 cells. `msg` is an abbreviation of `Message`, not a
    re-encoding of it, so `_numfold` cannot reach it and no general abbreviation rule is safe. The
    narrow rule that IS safe is `_digitfold_map`: fold on the number alone, but only when every arm
    is numbered, the numbers are unique, and the arm names share ONE stem - i.e. when the number is
    the identity. The three negatives below are the cases where it must refuse."""
    c, o = numbered_grid()
    pos = {
        "abbreviated_stem_msg01": clean(["msg%02d" % (i + 1) for i in range(len(c))], o),
        "bare_numbers": clean([str(i + 1) for i in range(len(c))], o),
        "hash_numbers": clean(["#%d" % (i + 1) for i in range(len(c))], o),
        # the dangerous shape: INTEGER values, where a digit fold on the OUTCOME map would let the
        # value column masquerade as an outcome name
        "integer_values": clean(c, o, "{c},{o},{v:.0f}"),
    }
    return c, o, pos


def digit_refusal_cases():
    """(names, outcomes, answer, how many cells may parse) - the fold must NOT fire."""
    return [
        ("mixed_stems_must_not_fold",
         ["Message 01", "Control 2", "Message 03"], ["PA"], "1,PA,1.0\n2,PA,2.0\n3,PA,3.0", 0),
        ("repeated_number_must_not_fold",
         ["Message 1", "Frame 1"], ["PA"], "1,PA,1.0", 0),
        ("unnumbered_arm_must_not_fold",
         ["Message 01", "Message 02", "Control"], ["PA"], "1,PA,1.0\n2,PA,2.0", 0),
    ]


def punctuated_cases():
    """MEASURED on a paid batch (session 11): `claude-sonnet-5` answered a 26-arm task in
    run-together CamelCase - `Outpartisans' Willingness to Learn` came back as
    `OutpartisansWillingnessToLearn` - and the two arms whose titles carry an apostrophe lost all
    their cells while the unpunctuated ones parsed. Dropping the spaces is one re-encoding the fold
    already knew; dropping the punctuation with them is the same class and is now folded too.

    The one case that is NOT here on purpose is a name with a WORD missing
    (`Bipartisan Joint Trivia Quiz` -> `BipartisanJointTrivia`). That is not an encoding, and a
    prefix rule would be the parser inventing which arm was meant (finding 70)."""
    c = ["Outpartisans' Willingness to Learn", "Party Overlap on Policies",
         "Pro-Democracy Inparty Elite Cues", "Alternative Control"]
    o = ["PA", "ADA"]
    def camel(x):
        return "".join(w[:1].upper() + w[1:] for w in re.sub(r"[^A-Za-z0-9 ]", "", x).split())
    return c, o, {
        "camelcase_run_together": clean([camel(x) for x in c], o),
        "apostrophe_dropped_only": clean([x.replace("'", "") for x in c], o),
        "lower_snake_no_punctuation": clean(
            [re.sub(r"[^a-z0-9]+", "_", x.lower()).strip("_") for x in c], o),
    }


def punct_ambiguity_case():
    """Two arms that differ ONLY by punctuation fold to one key, so the fold must refuse both and
    leave the exact names to do the work. Otherwise the recovery above could merge two arms."""
    c = ["It's Time", "Its Time", "Other Arm"]
    o = ["PA"]
    return c, o, "Its Time,PA,1.0\nOther Arm,PA,2.0"


def main():
    conds, outs = grid()
    total = len(conds) * len(outs)
    print("target grid: %d conditions x %d outcomes = %d cells\n" % (len(conds), len(outs), total))
    print("%-32s%8s%8s%s" % ("failure mode", "parsed", "pct", "  verdict"))
    res = {}
    for name, f in MODES.items():
        d = ssb.predict.parse(f(conds, outs), conds, outs)
        n = int(d.ate.notna().sum())
        res[name] = n
        v = "ok" if n == total else ("TOTAL LOSS" if n == 0 else "partial")
        if name == "na_cells":
            v = "ok (NaN is the CORRECT answer for an N/A cell)"
        print("%-32s%8d%7.1f%%  %s" % (name, n, 100 * n / total, v))
    bad = [k for k, v in res.items() if v < total and k != "na_cells"]
    print("\n%d of %d modes lose cells: %s" % (len(bad), len(MODES), bad))

    print("\n%-32s%8s%8s%s" % ("negative control", "parsed", "want", "  verdict"))
    fails = []
    for name, (f, want) in NEGATIVE.items():
        d = ssb.predict.parse(f(conds, outs), conds, outs)
        n = int(d.ate.notna().sum())
        want = (len(conds) // 2) * len(outs) if want is None else want
        ok = n == want
        fails += [] if ok else [name]
        print("%-32s%8d%8d  %s" % (name, n, want, "ok" if ok else "INVENTED CELLS"))
    # numbered arms (task 7's shape)
    print("\n%-40s%8s%8s%s" % ("numbered-arm case", "parsed", "want", "  verdict"))
    nc, no, cases = numbered_cases()
    ntot = len(nc) * len(no)
    for name, txt in cases.items():
        n = int(ssb.predict.parse(txt, nc, no).ate.notna().sum())
        fails += [] if n == ntot else [name]
        print("%-40s%8d%8d  %s" % (name, n, ntot, "ok" if n == ntot else "LOSES CELLS"))
    print("\n%-40s%8s%8s%s" % ("numbered-by-DIGIT case", "parsed", "want", "  verdict"))
    dc, do, dcases = digit_cases()
    dtot = len(dc) * len(do)
    for name, txt in dcases.items():
        n = int(ssb.predict.parse(txt, dc, do).ate.notna().sum())
        fails += [] if n == dtot else [name]
        print("%-40s%8d%8d  %s" % (name, n, dtot, "ok" if n == dtot else "LOSES CELLS"))
    for name, cc, oo, txt, want in digit_refusal_cases():
        n = int(ssb.predict.parse(txt, cc, oo).ate.notna().sum())
        fails += [] if n == want else [name]
        print("%-40s%8d%8d  %s" % (name, n, want, "ok (refused)" if n == want else "FOLDED ANYWAY"))

    print("\n%-40s%8s%8s%s" % ("punctuated-name case", "parsed", "want", "  verdict"))
    pc, po, pcases = punctuated_cases()
    ptot = len(pc) * len(po)
    for name, txt in pcases.items():
        n = int(ssb.predict.parse(txt, pc, po).ate.notna().sum())
        fails += [] if n == ptot else [name]
        print("%-40s%8d%8d  %s" % (name, n, ptot, "ok" if n == ptot else "LOSES CELLS"))
    qc, qo, qtxt = punct_ambiguity_case()
    q = ssb.predict.parse(qtxt, qc, qo)
    qgot = dict(zip(q.condition, q.ate))
    qok = qgot.get("Its Time") == 1.0 and qgot.get("Other Arm") == 2.0 and pd.isna(qgot.get("It's Time"))
    fails += [] if qok else ["punctuation_fold_must_not_merge"]
    print("%-40s%8s%8s  %s" % ("ambiguous fold (It's Time / Its Time)", "-", "-",
                               "ok (no merge)" if qok else "MERGED TWO ARMS"))
    ac, ao, atxt = ambiguity_case()
    d = ssb.predict.parse(atxt, ac, ao)
    got = dict(zip(d.condition, d.ate))
    ok = got.get("Message 1") == 1.0 and got.get("Message 02") == 2.0 and pd.isna(got.get("Message 01"))
    fails += [] if ok else ["ambiguous_fold_must_not_merge"]
    print("%-40s%8s%8s  %s" % ("ambiguous fold (01 and 1 both present)", "-", "-",
                               "ok (no merge)" if ok else "MERGED TWO ARMS"))

    if fails or bad:
        raise SystemExit("\nFAIL: recovery %s / invention %s" % (bad, fails))
    print("\nparser PASS: %d recovery modes at full coverage, %d negative controls clean, "
          "%d numbered-arm cases + the ambiguity red path"
          % (len(MODES) - 1, len(NEGATIVE), len(cases)))
    return res


if __name__ == "__main__":
    main()
