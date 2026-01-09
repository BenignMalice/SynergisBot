import glob
import re


def test_registry_register_present():
    """Scan repository for `registry.register(` usages and fail if none found.

    This is a lightweight check to ensure tools are being registered via the
    `registry.register(...)` decorator/pattern. It intentionally skips files
    under `tests/` to avoid the test finding itself.
    """
    py_files = [f for f in glob.glob("**/*.py", recursive=True) if not f.startswith(".git")]
    pattern = re.compile(r"\bregistry\.register\(")
    matches = []
    for path in py_files:
        if path.startswith("tests/"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except Exception:
            continue
        if pattern.search(content):
            matches.append(path)

    assert matches, (
        "No `registry.register(...)` occurrences found in repository. "
        "Ensure tools are exposed via `@registry.register(...)` in `desktop_agent.py` or similar modules."
    )
