#!/usr/bin/env python3
"""Unit tests for diff-scope-mutation.py. Run: python3 -m unittest -v
(from this directory) or `python3 test_diff_scope_mutation.py`."""
import importlib.util
import os
import unittest

# Load the hyphenated module by path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "dsm", os.path.join(_HERE, "diff-scope-mutation.py")
)
dsm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dsm)


class ParseDiffTests(unittest.TestCase):
    def test_single_file_added_lines(self):
        diff = (
            "diff --git a/src/Svc.cs b/src/Svc.cs\n"
            "--- a/src/Svc.cs\n"
            "+++ b/src/Svc.cs\n"
            "@@ -10,0 +11,3 @@\n"
            "+line a\n+line b\n+line c\n"
        )
        self.assertEqual(dsm.parse_unified_diff(diff), {"src/Svc.cs": {11, 12, 13}})

    def test_modified_single_line_default_count(self):
        diff = (
            "+++ b/src/A.cs\n"
            "@@ -5 +5 @@\n"
            "+changed\n"
        )
        self.assertEqual(dsm.parse_unified_diff(diff), {"src/A.cs": {5}})

    def test_pure_deletion_excluded(self):
        diff = (
            "+++ b/src/Gone.cs\n"
            "@@ -3,2 +2,0 @@\n"
            "-old1\n-old2\n"
        )
        # count == 0 on the new side → no new lines → file dropped
        self.assertEqual(dsm.parse_unified_diff(diff), {})

    def test_dev_null_new_file_side_ignored(self):
        diff = (
            "--- a/src/Removed.cs\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-a\n-b\n"
        )
        self.assertEqual(dsm.parse_unified_diff(diff), {})

    def test_multiple_files_and_hunks(self):
        diff = (
            "+++ b/src/One.cs\n"
            "@@ -1 +1,2 @@\n+x\n+y\n"
            "+++ b/src/Two.cs\n"
            "@@ -8,0 +9 @@\n+z\n"
        )
        self.assertEqual(
            dsm.parse_unified_diff(diff),
            {"src/One.cs": {1, 2}, "src/Two.cs": {9}},
        )


class GlobTierTests(unittest.TestCase):
    GLOBS = {
        "validators": ["**/Validators/**/*.cs", "**/*Validator.cs"],
        "services": ["**/Services/**/*.cs", "**/*Service.cs"],
        "controllers": ["**/Controllers/**/*.cs", "**/*Controller.cs"],
    }

    def test_service_tier(self):
        self.assertEqual(
            dsm.tier_for("sample/OrdersApi/src/OrdersApi/Services/PaymentService.cs", self.GLOBS),
            "services",
        )

    def test_controller_tier(self):
        self.assertEqual(
            dsm.tier_for("a/b/Controllers/OrdersController.cs", self.GLOBS),
            "controllers",
        )

    def test_validator_suffix(self):
        self.assertEqual(dsm.tier_for("x/y/AmountValidator.cs", self.GLOBS), "validators")

    def test_no_match_returns_none(self):
        self.assertIsNone(dsm.tier_for("src/Models/Order.cs", self.GLOBS))

    def test_no_substring_directory_false_positive(self):
        # 'NotControllers' must NOT match '**/Controllers/**'
        self.assertIsNone(dsm.tier_for("src/NotControllers/Foo.cs", self.GLOBS))
        self.assertIsNone(dsm.tier_for("src/ApiControllers/Helper.cs", self.GLOBS))
        # but a real Controllers segment still matches
        self.assertEqual(dsm.tier_for("src/Controllers/X.cs", self.GLOBS), "controllers")


def _mut(line, status):
    return {"status": status, "location": {"start": {"line": line}}}


class ScoreReportTests(unittest.TestCase):
    CONFIG = {
        "mutationThresholds": {"validators": 80, "services": 70, "controllers": 60},
        "fileTierGlobs": {
            "services": ["**/Services/**/*.cs", "**/*Service.cs"],
            "controllers": ["**/Controllers/**/*.cs", "**/*Controller.cs"],
        },
    }

    def test_dilution_is_eliminated(self):
        """The core scenario: a file whose CHANGED lines are undertested must
        FAIL even though the file as a whole scores well. Charge (unchanged,
        lines 10-13) is well... irrelevant; only changed lines 20-23 count."""
        report = {
            "files": {
                "/abs/repo/src/Services/PaymentService.cs": {
                    "mutants": [
                        # Unchanged region (well killed) — must be ignored
                        _mut(10, "Killed"), _mut(11, "Killed"), _mut(12, "Killed"),
                        # Changed region (lines 20-23) — undertested
                        _mut(20, "Survived"), _mut(21, "NoCoverage"),
                        _mut(22, "Survived"), _mut(23, "Killed"),
                    ]
                }
            }
        }
        changed = {"src/Services/PaymentService.cs": {20, 21, 22, 23}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(out["gate"], "fail")
        f = out["files"][0]
        self.assertEqual(f["tier"], "services")
        self.assertEqual(f["changedMutants"], 4)   # only lines 20-23
        self.assertEqual(f["killed"], 1)
        self.assertEqual(f["score"], 25.0)         # 1/4
        self.assertEqual(f["verdict"], "fail")

    def test_well_tested_changed_lines_pass_despite_untested_neighbours(self):
        """Mirror image: changed lines are well-tested → PASS, even if the file
        has survivors on UNCHANGED lines (pre-existing debt, out of scope)."""
        report = {
            "files": {
                "/abs/repo/src/Services/PaymentService.cs": {
                    "mutants": [
                        # Unchanged, untested (pre-existing) — ignored
                        _mut(10, "Survived"), _mut(11, "NoCoverage"),
                        # Changed lines 30-33 — well tested
                        _mut(30, "Killed"), _mut(31, "Killed"),
                        _mut(32, "Killed"), _mut(33, "Killed"),
                    ]
                }
            }
        }
        changed = {"src/Services/PaymentService.cs": {30, 31, 32, 33}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(out["gate"], "pass")
        self.assertEqual(out["files"][0]["score"], 100.0)

    def test_unchanged_file_excluded(self):
        report = {"files": {"/abs/repo/src/Services/OtherService.cs": {
            "mutants": [_mut(5, "Survived")]}}}
        changed = {"src/Services/PaymentService.cs": {30}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(out["files"], [])
        self.assertEqual(out["gate"], "pass")

    def test_changed_lines_without_mutants_not_gated(self):
        # changed lines 99-100 carry no mutants → nothing to gate
        report = {"files": {"/abs/repo/src/Services/PaymentService.cs": {
            "mutants": [_mut(30, "Killed")]}}}
        changed = {"src/Services/PaymentService.cs": {99, 100}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(out["files"], [])
        self.assertEqual(out["gate"], "pass")

    def test_controller_tier_threshold_applied(self):
        report = {"files": {"/abs/repo/src/Controllers/OrdersController.cs": {
            "mutants": [_mut(40, "Killed"), _mut(41, "Survived")]}}}  # 50%
        changed = {"src/Controllers/OrdersController.cs": {40, 41}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        f = out["files"][0]
        self.assertEqual(f["tier"], "controllers")
        self.assertEqual(f["threshold"], 60)
        self.assertEqual(f["score"], 50.0)
        self.assertEqual(f["verdict"], "fail")   # 50 < 60

    def test_timeout_counts_as_killed(self):
        report = {"files": {"/abs/repo/src/Services/PaymentService.cs": {
            "mutants": [_mut(30, "Timeout"), _mut(31, "Killed"),
                        _mut(32, "Killed"), _mut(33, "Killed")]}}}
        changed = {"src/Services/PaymentService.cs": {30, 31, 32, 33}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(out["files"][0]["killed"], 4)   # Timeout grouped with Killed
        self.assertEqual(out["files"][0]["score"], 100.0)

    def test_no_tier_match_uses_lowest_threshold(self):
        # a changed file matching no glob is held to the lowest configured threshold (60)
        report = {"files": {"/abs/repo/src/Models/Order.cs": {
            "mutants": [_mut(5, "Killed"), _mut(6, "Survived")]}}}  # 50%
        changed = {"src/Models/Order.cs": {5, 6}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        f = out["files"][0]
        self.assertEqual(f["tier"], "(default-lowest)")
        self.assertEqual(f["threshold"], 60)
        self.assertEqual(f["verdict"], "fail")   # 50 < 60

    def test_suffix_match_respects_path_boundary(self):
        # report path differs from diff path only by root depth → should match
        report = {"files": {"/abs/repo/proj/src/Services/PaymentService.cs": {
            "mutants": [_mut(30, "Killed")]}}}
        changed = {"src/Services/PaymentService.cs": {30}}
        out = dsm.score_report(report, changed, self.CONFIG, "/abs/repo")
        self.assertEqual(len(out["files"]), 1)
        # a same-suffix-but-different-file must NOT match
        report2 = {"files": {"/abs/repo/src/Services/OtherPaymentService.cs": {
            "mutants": [_mut(30, "Survived")]}}}
        changed2 = {"PaymentService.cs": {30}}
        out2 = dsm.score_report(report2, changed2, self.CONFIG, "/abs/repo")
        self.assertEqual(out2["files"], [])  # OtherPaymentService.cs != PaymentService.cs


if __name__ == "__main__":
    unittest.main(verbosity=2)
