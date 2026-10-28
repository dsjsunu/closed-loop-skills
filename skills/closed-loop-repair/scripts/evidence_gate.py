"""Evidence consistency gate. Does not execute tests or approve human acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_path(root, name):
    require(isinstance(name, str) and name.strip(), "Empty or invalid path")
    rel = Path(name)
    require(not rel.is_absolute() and ".." not in rel.parts, f"Unsafe path: {name}")
    path = root / rel
    require(path.resolve().is_relative_to(root), f"Path escapes project: {name}")
    for item in [path, *path.parents]:
        if item == root:
            break
        require(not item.is_symlink() and not getattr(item, "is_junction", lambda: False)(),
                f"Links are unsupported: {name}")
    return path


def read_json(root, name):
    return json.loads(safe_path(root, name).read_text(encoding="utf-8"))


def inventory(root, names):
    result = {}
    for name in names:
        base = safe_path(root, name)
        require(base.exists(), f"Missing tracked root: {name}")
        paths = [base] if base.is_file() else base.rglob("*")
        for path in paths:
            rel = path.relative_to(root).as_posix()
            safe_path(root, rel)
            if path.is_file():
                result[rel] = file_hash(path)
    return result


def validate_config(root, config):
    require(isinstance(config, dict), "Config must be an object")
    for key in ("source_roots", "protected_roots", "required_checks"):
        items = config.get(key)
        require(isinstance(items, list) and all(isinstance(x, str) and x.strip() for x in items),
                f"Invalid {key}")
        require(len(items) == len(set(items)), f"Duplicate {key}")
    require(config["source_roots"] and config["required_checks"], "Sources and checks cannot be empty")
    require(type(config.get("visual")) is bool, "visual must be boolean")
    if config["visual"]:
        require(config.get("visual_check") in config["required_checks"],
                "Visual tasks require a named visual_check in required_checks")
    sources = [safe_path(root, x).resolve() for x in config["source_roots"]]
    protected = [safe_path(root, x).resolve() for x in config["protected_roots"]]
    require(not any(a.is_relative_to(b) or b.is_relative_to(a) for a in sources for b in protected),
            "Source and protected roots overlap")


def capture(root, config, issue):
    validate_config(root, config)
    artifacts = {}
    require(isinstance(issue.get("artifacts"), dict), "artifacts must be an object")
    for role, name in issue["artifacts"].items():
        path = safe_path(root, name)
        if path.is_file():
            artifacts[role] = {"path": path.relative_to(root).as_posix(), "sha256": file_hash(path)}
    sources = inventory(root, config["source_roots"])
    require(sources, "No tracked source files")
    protected = inventory(root, config["protected_roots"])
    return {"version": 1, "config_digest": digest(config), "sources": sources,
            "protected": protected, "artifacts": artifacts,
            "source_digest": digest({"sources": sources, "protected": protected}),
            "artifacts_digest": digest(artifacts)}


def diagnosis(root, issue):
    cause = issue.get("root_cause")
    require(cause in ("data", "implementation", "mixed", "undetermined"), "Invalid root cause")
    require(isinstance(issue.get("diagnosis"), str) and issue["diagnosis"].strip(), "Missing diagnosis")
    evidence = issue.get("diagnosis_evidence")
    require(isinstance(evidence, list) and evidence, "Missing diagnosis evidence")
    for name in evidence:
        require(safe_path(root, name).is_file(), f"Missing evidence: {name}")
    return {"data": "reported_data_issue", "implementation": "awaiting_plan_confirmation",
            "mixed": "manual_review", "undetermined": "blocked"}[cause]


def ready(root, config, issue, baseline, candidate):
    diagnosis(root, issue)
    require(issue["root_cause"] == "implementation", "Only implementation repairs enter ready; split mixed tasks")
    plan = issue.get("plan")
    require(isinstance(plan, str) and plan.strip(), "Missing repair plan")
    approval = issue.get("approval")
    require(isinstance(approval, dict), "Missing user plan confirmation")
    require(approval.get("plan_sha256") == digest(plan), "Approval does not match plan")
    require(all(isinstance(approval.get(k), str) and approval[k].strip() for k in ("quote", "reference")),
            "Missing real confirmation quote/reference")
    current = capture(root, config, issue)
    require(candidate == current, "Candidate/source/input/evidence drift; rerun affected verification")
    require(baseline.get("version") == 1 and baseline.get("config_digest") == digest(config),
            "Baseline configuration mismatch")
    require(isinstance(baseline.get("sources"), dict) and isinstance(baseline.get("artifacts"), dict),
            "Invalid baseline")
    require(baseline.get("protected") == current["protected"], "Protected inputs changed")
    for role in (["baseline", "before"] if config["visual"] else ["baseline"]):
        require(role in baseline["artifacts"], f"Missing original {role} evidence")
        require(baseline["artifacts"][role] == current["artifacts"].get(role), f"Original {role} replaced")
    required_artifacts = ["baseline", "candidate"] + (["before", "after"] if config["visual"] else [])
    for role in required_artifacts:
        require(role in current["artifacts"], f"Missing {role} artifact")
    before, after = baseline["sources"], current["sources"]
    actual = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    declared = issue.get("changed_files")
    require(isinstance(declared, list) and all(isinstance(x, str) for x in declared), "Invalid changed_files")
    normalized = [safe_path(root, p).relative_to(root).as_posix() for p in declared]
    require(len(set(normalized)) == len(normalized), "Duplicate changed_files")
    require(actual and actual == set(normalized), "Declared changes do not match actual source changes")
    checks = issue.get("checks")
    require(isinstance(checks, dict), "Missing check reports")
    for name in config["required_checks"]:
        require(name in checks, f"Missing check: {name}")
        report = read_json(root, checks[name])
        require(report.get("status") == "PASS", f"Check did not pass: {name}")
        require(isinstance(report.get("summary"), str) and report["summary"].strip(), f"Missing check summary: {name}")
        require(report.get("source_digest") == current["source_digest"], f"Stale source report: {name}")
        require(report.get("artifacts_digest") == current["artifacts_digest"], f"Stale artifact report: {name}")
    return "ready_for_human"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capture", "check", "plan-hash"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--config")
    parser.add_argument("--out")
    parser.add_argument("--stage", choices=["diagnosis", "ready"], default="diagnosis")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        issue = read_json(root, args.issue)
        if args.command == "plan-hash":
            require(isinstance(issue.get("plan"), str) and issue["plan"].strip(), "Missing plan")
            print(digest(issue["plan"]))
            return 0
        if args.command == "check" and args.stage == "diagnosis":
            state = diagnosis(root, issue)
        else:
            require(args.config, "--config required")
            config = read_json(root, args.config)
            if args.command == "capture":
                require(args.out, "--out required")
                snapshot = capture(root, config, issue)
                out = safe_path(root, args.out)
                require(not out.exists(), "Snapshot exists; use a new revision path, do not overwrite")
                tracked = config["source_roots"] + config["protected_roots"]
                require(not any(out.resolve().is_relative_to(safe_path(root, p).resolve()) for p in tracked),
                        "Snapshot cannot be inside tracked inputs/source")
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open("x", encoding="utf-8") as stream:
                    json.dump(snapshot, stream, ensure_ascii=False, indent=2)
                print(json.dumps({"source_digest": snapshot["source_digest"],
                                  "artifacts_digest": snapshot["artifacts_digest"]}))
                return 0
            require(args.baseline and args.candidate, "--baseline and --candidate required")
            state = ready(root, config, issue, read_json(root, args.baseline), read_json(root, args.candidate))
        print(json.dumps({"status": "PASS" if state not in ("blocked", "manual_review") else "MANUAL_REVIEW",
                          "task_state": state}))
        return 1 if state in ("blocked", "manual_review") else 0
    except GateError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
