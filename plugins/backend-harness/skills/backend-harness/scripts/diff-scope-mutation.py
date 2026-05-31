#!/usr/bin/env python3
"""Diff-scoped mutation gate for the backend-harness.

The harness runs mutation testing as a FULL project run (Stryker's native
`--since` diff mode does not work inside git worktrees, which the harness always
uses). This script re-scopes the resulting report to only the mutants that fall
on lines the run actually changed, then applies the tiered thresholds from
`harness.config.json` per changed file.

Why diff-scoping: the gate should judge the quality of the work the harness
produced, not pre-existing tech debt it never touched. A whole-file score lets
well-tested new code dilute an untested neighbour in the same file; line-level
scoping measures exactly the changed lines.

Usage:
    diff-scope-mutation.py \
        --report path/to/mutation-report.json \
        --base <git-ref> \
        --config path/to/harness.config.json \
        --repo-root <abs path to git repo root>

Output: a JSON object on stdout:
    {
      "gate": "pass" | "fail",
      "files": [
        {"path","tier","threshold","score","killed","survived",
         "noCoverage","changedMutants","verdict"}
      ],
      "failing": ["<path>", ...]
    }

Exit code: 0 if gate passes (or nothing to gate), 1 if the gate fails,
2 on a usage/IO error.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys


# --- Pure functions (unit-tested) -------------------------------------------

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff_text: str) -> dict[str, set[int]]:
    """Parse `git diff --unified=0` output into {repo_relative_path: {new_lines}}.

    Only new-side line numbers (additions/modifications) are recorded — those are
    the lines the run is responsible for. Pure deletions contribute no new lines.
    """
    changed: dict[str, set[int]] = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            # "+++ b/path" or "+++ /dev/null"
            path = line[4:].strip()
            if path == "/dev/null":
                current = None
            else:
                # strip a leading "b/" (git prefix)
                current = path[2:] if path.startswith("b/") else path
                changed.setdefault(current, set())
            continue
        m = _HUNK_RE.match(line)
        if m and current is not None:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            # count == 0 means a pure deletion at this point: no new lines
            for ln in range(start, start + count):
                changed[current].add(ln)
    # drop files that ended up with no new lines (pure deletions)
    return {p: lines for p, lines in changed.items() if lines}


def tier_for(path: str, file_tier_globs: dict[str, list[str]]) -> str | None:
    """Return the tier whose glob matches `path`, checked validators→services→
    controllers order. Returns None if no glob matches."""
    for tier in ("validators", "services", "controllers"):
        for pattern in file_tier_globs.get(tier, []):
            # fnmatch with ** — translate ** to match across separators
            if _glob_match(path, pattern):
                return tier
    return None


def _glob_match(path: str, pattern: str) -> bool:
    """Match a path against a glob that may contain '**'."""
    # fnmatch treats '*' as not crossing '/', but our globs use '**'.
    # Convert the glob to an anchored regex. A leading '**/' in the pattern
    # provides the "match anywhere" semantics with proper '/' boundaries, so we
    # do NOT prepend a free '.*' (that would let a literal segment match
    # mid-component, e.g. 'NotControllers' matching '**/Controllers/**').
    regex = _glob_to_regex(pattern)
    return re.match(regex, path) is not None


def _glob_to_regex(pattern: str) -> str:
    i = 0
    out = ["^"]
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == ".":
            out.append(r"\.")
            i += 1
        elif c == "?":
            out.append(".")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return "".join(out)


def score_report(
    report: dict,
    changed: dict[str, set[int]],
    config: dict,
    repo_root: str,
) -> dict:
    """Compute the diff-scoped gate verdict.

    `report` is a parsed Stryker mutation-report.json. `changed` maps
    repo-relative paths to changed new-side line numbers. `config` is the parsed
    harness.config.json. Returns the output object documented in the module
    docstring.
    """
    thresholds = config.get("mutationThresholds", {})
    file_tier_globs = config.get("fileTierGlobs", {})
    lowest = min(thresholds.values()) if thresholds else 0

    files_out: list[dict] = []
    failing: list[str] = []

    for report_path, data in report.get("files", {}).items():
        rel = _to_repo_relative(report_path, repo_root)
        # find the changed-lines entry whose path matches this report file
        changed_lines = _match_changed(rel, changed)
        if not changed_lines:
            continue  # file not changed (or no new lines) → out of scope

        scoped = [
            m
            for m in data.get("mutants", [])
            if _mutant_line(m) in changed_lines
        ]
        if not scoped:
            continue  # changed lines carry no mutable code → nothing to gate

        killed = sum(1 for m in scoped if m.get("status") in ("Killed", "Timeout"))
        survived = sum(1 for m in scoped if m.get("status") == "Survived")
        nocov = sum(1 for m in scoped if m.get("status") == "NoCoverage")
        denom = killed + survived + nocov
        if denom == 0:
            continue  # only ignored mutants on changed lines → nothing to gate

        score = round(killed / denom * 100, 1)
        tier = tier_for(rel, file_tier_globs)
        threshold = thresholds.get(tier, lowest) if tier else lowest
        verdict = "pass" if score >= threshold else "fail"
        if verdict == "fail":
            failing.append(rel)

        files_out.append(
            {
                "path": rel,
                "tier": tier or "(default-lowest)",
                "threshold": threshold,
                "score": score,
                "killed": killed,
                "survived": survived,
                "noCoverage": nocov,
                "changedMutants": denom,
                "verdict": verdict,
            }
        )

    files_out.sort(key=lambda f: f["path"])
    return {
        "gate": "fail" if failing else "pass",
        "files": files_out,
        "failing": sorted(failing),
    }


def _mutant_line(mutant: dict) -> int:
    return (
        mutant.get("location", {})
        .get("start", {})
        .get("line", -1)
    )


def _to_repo_relative(report_path: str, repo_root: str) -> str:
    """Normalise a Stryker report file key to a repo-relative POSIX path."""
    p = report_path.replace("\\", "/")
    if os.path.isabs(p):
        try:
            return os.path.relpath(os.path.realpath(p), os.path.realpath(repo_root)).replace(
                "\\", "/"
            )
        except ValueError:
            return p.lstrip("/")
    return p


def _match_changed(rel_path: str, changed: dict[str, set[int]]) -> set[int]:
    """Find changed lines for a report file. Match on exact repo-relative path,
    else on longest shared path suffix (handles project-root vs repo-root path
    differences)."""
    if rel_path in changed:
        return changed[rel_path]
    rel_norm = os.path.normpath(rel_path).replace("\\", "/")
    for cpath, lines in changed.items():
        c_norm = os.path.normpath(cpath).replace("\\", "/")
        # Require the shorter path to be a path-segment-aligned suffix of the
        # longer (prefix each with '/' so 'Service.cs' does not match
        # 'xService.cs'). This handles repo-root vs project-root depth
        # differences without false positives across same-suffix filenames.
        if ("/" + rel_norm).endswith("/" + c_norm) or ("/" + c_norm).endswith("/" + rel_norm):
            return lines
    return set()


# --- IO / CLI ---------------------------------------------------------------

def compute_changed(base: str, repo_root: str) -> dict[str, set[int]]:
    """Run `git diff --unified=0 <base>` from the repo root and parse it."""
    result = subprocess.run(
        ["git", "-C", repo_root, "diff", "--unified=0", base],
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_unified_diff(result.stdout)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diff-scoped mutation gate")
    ap.add_argument("--report", required=True, help="path to mutation-report.json")
    ap.add_argument("--base", required=True, help="git ref to diff against")
    ap.add_argument("--config", required=True, help="path to harness.config.json")
    ap.add_argument("--repo-root", required=True, help="absolute git repo root")
    args = ap.parse_args(argv)

    try:
        with open(args.report) as f:
            report = json.load(f)
        with open(args.config) as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"gate": "error", "error": str(e)}))
        return 2

    try:
        changed = compute_changed(args.base, args.repo_root)
    except subprocess.CalledProcessError as e:
        print(json.dumps({"gate": "error", "error": f"git diff failed: {e.stderr}"}))
        return 2

    out = score_report(report, changed, config, args.repo_root)
    print(json.dumps(out, indent=2))
    return 1 if out["gate"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
