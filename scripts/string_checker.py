"""
To check if all calls to t("key", ...) in the source code have the correct substitution arguments as per strings.yaml.
"""

import ast
import string
import sys
from pathlib import Path

import yaml


def _flatten_strings(data, prefix=""):
    for k, v in data.items():
        key = f"{prefix}{k}" if prefix == "" else f"{prefix}.{k}"
        if isinstance(v, str):
            yield key, v
        elif isinstance(v, dict):
            yield from _flatten_strings(v, key)


def _placeholders_from_string(s: str) -> set[str]:
    fmt = string.Formatter()
    names = set()
    for _, field_name, _, _ in fmt.parse(s):
        if field_name:
            names.add(field_name)
    return names


def main():
    # Load strings.yaml
    root = Path(__file__).resolve().parents[1]
    strings_path = root / "strings.yaml"
    data = yaml.safe_load(strings_path.read_text(encoding="utf-8"))

    strings_map = dict(_flatten_strings(data))
    placeholders_map = {k: _placeholders_from_string(v) for k, v in strings_map.items()}

    # Find all calls to t("key", ... ) in the src tree
    src_root = root / "src"
    calls: list[tuple[str, int, str, set[str]]] = []  # file, lineno, key, kwargs
    used_keys = set()

    for pyfile in src_root.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            # skip files that can't be parsed by ast
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "t":
                    # first arg must be a literal key
                    if (
                        node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                    ):
                        key = node.args[0].value
                        kw_names = {
                            kw.arg for kw in node.keywords if kw.arg is not None
                        }
                        calls.append(
                            (str(pyfile.relative_to(root)), node.lineno, key, kw_names)
                        )
                        used_keys.add(key)

    # Find unused keys in YAML
    unused_keys = set(strings_map.keys()) - used_keys

    issues = []
    errors = []

    # Report unused YAML keys
    if unused_keys:
        issues.append("Unused string keys in strings.yaml:")
        for key in sorted(unused_keys):
            issues.append(f"  - {key}")
        issues.append("")

    # Check all code calls for correctness
    for fname, lineno, key, kw_names in calls:
        if key not in placeholders_map:
            errors.append(f"{fname}:{lineno} - ERROR: unknown string key '{key}'")
            continue
        expected = placeholders_map[key]
        missing = expected - kw_names
        extra = kw_names - expected
        if missing:
            errors.append(
                f"{fname}:{lineno} - ERROR: t('{key}') missing substitutions: {sorted(missing)}"
            )
        if extra:
            errors.append(
                f"{fname}:{lineno} - ERROR: t('{key}') extra kwargs passed: {sorted(extra)}"
            )

    if issues:
        print("\n".join(issues))

    if errors:
        print("Code errors found:")
        for error in errors:
            print(f"  {error}")
        return False

    if not issues and not errors:
        print("✓ All string substitutions are valid and all keys are used.")

    return len(errors) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
