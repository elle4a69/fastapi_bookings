"""Anti-Mock Scanner engine for AGENTS.md Rule 3 Enforcement.

Rule 3: Absolute Prohibition of Mock Implementations
- No synthetic setTimeout handlers simulating backend processing or delays.
- No fake, hardcoded frontend state masquerading as real backend data (INITIAL_*, SAMPLE_*, fake_*, mock_*).
- No components returning hardcoded dummy states without calling real backend API clients.
- No stub endpoints returning fake success without mutating real database state.
"""

from dataclasses import dataclass
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set

CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

EXCLUDED_DIR_PATTERNS = [
    re.compile(r"(?:^|[/\\])(?:tests|test|__tests__)(?:[/\\]|$)"),
    re.compile(r"(?:^|[/\\])(?:node_modules|\.git|\.venv|venv|env|dist|build|artifacts|docs|\.agent|\.agents|onboarding-setup|scratch|dev-dashboard)(?:[/\\]|$)"),
    re.compile(r"(?:^|[/\\])scripts[/\\]hooks(?:[/\\]|$)"),
]

EXCLUDED_FILE_PATTERNS = [
    re.compile(r"(?:^|[/\\])(?:test_[^/\\]+\.py|[^/\\]+\.(?:test|spec)\.[tj]sx?)$"),
    re.compile(r"(?:^|[/\\])scripts[/\\]verify_[^/\\]+\.py$"),
    re.compile(r"(?:^|[/\\])scripts[/\\](?:index_living_docs|query_docs)\.py$"),
    re.compile(r"(?:^|[/\\])scripts[/\\](?:seed_demo_structured_catalog|seed_clean_numbered_data)\.py$"),
]


@dataclass
class MockViolation:
    file_path: str
    line_number: int
    pattern_type: str
    message: str
    snippet: str

    def to_summary(self) -> str:
        rel_path = os.path.normpath(self.file_path)
        return f"{rel_path}:{self.line_number} [{self.pattern_type}] {self.message}"


def read_stdin_payload(timeout_ms: int = 200) -> Dict[str, Any]:
    """Safely reads JSON payload from stdin without hanging when stdin is an open empty pipe."""
    try:
        if sys.stdin.isatty():
            return {}
    except Exception:
        pass

    # Windows named pipe / handle non-blocking inspection
    if sys.platform == "win32":
        try:
            import ctypes
            import msvcrt

            handle = msvcrt.get_osfhandle(0)
            file_type = ctypes.windll.kernel32.GetFileType(handle)
            if file_type == 1:  # FILE_TYPE_DISK (redirected from file)
                content = sys.stdin.read()
                return json.loads(content) if content.strip() else {}
            elif file_type == 3:  # FILE_TYPE_PIPE
                start_time = time.time()
                accumulated = []
                while (time.time() - start_time) < (timeout_ms / 1000.0):
                    avail = ctypes.c_ulong(0)
                    success = ctypes.windll.kernel32.PeekNamedPipe(
                        handle, None, 0, None, ctypes.byref(avail), None
                    )
                    if not success or avail.value == 0:
                        if accumulated:
                            break
                        time.sleep(0.01)
                        continue
                    chunk = sys.stdin.read(avail.value)
                    accumulated.append(chunk)
                    time.sleep(0.01)
                content = "".join(accumulated).strip()
                if content:
                    return json.loads(content)
                return {}
        except Exception:
            pass

    # Unix / POSIX non-blocking select
    try:
        import select

        if select.select([sys.stdin], [], [], timeout_ms / 1000.0)[0]:
            content = sys.stdin.read().strip()
            if content:
                return json.loads(content)
    except Exception:
        pass

    return {}


def find_repo_root(start_dir: Optional[str] = None, workspace_paths: Optional[List[str]] = None) -> str:
    """Finds the Git repository root directory."""
    if workspace_paths:
        for p in workspace_paths:
            if p and os.path.isdir(p):
                try:
                    res = subprocess.run(
                        ["git", "rev-parse", "--show-toplevel"],
                        cwd=p,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        return os.path.abspath(res.stdout.strip())
                except Exception:
                    pass
                if os.path.exists(os.path.join(p, ".git")):
                    return os.path.abspath(p)

    target_dir = start_dir or os.getcwd()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return os.path.abspath(res.stdout.strip())
    except Exception:
        pass

    curr = os.path.abspath(target_dir)
    while curr:
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    return os.path.abspath(target_dir)


def is_path_excluded(rel_or_abs_path: str) -> bool:
    """Checks whether a given path is excluded from mock scanning."""
    normalized = rel_or_abs_path.replace("\\", "/")
    for pattern in EXCLUDED_DIR_PATTERNS:
        if pattern.search(normalized):
            return True
    for pattern in EXCLUDED_FILE_PATTERNS:
        if pattern.search(normalized):
            return True
    return False


def get_modified_code_files(repo_root: str) -> List[str]:
    """Finds all code files that have been created, modified, or untracked in Git."""
    found_files: Set[str] = set()

    try:
        diff_res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if diff_res.returncode == 0:
            for line in diff_res.stdout.splitlines():
                line = line.strip().strip('"').strip("'")
                if line:
                    found_files.add(os.path.join(repo_root, line))
    except Exception:
        pass

    try:
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if status_res.returncode == 0:
            for raw_line in status_res.stdout.splitlines():
                if len(raw_line) < 4:
                    continue
                path_part = raw_line[3:].strip().strip('"').strip("'")
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip().strip('"').strip("'")

                abs_path = os.path.join(repo_root, path_part)
                if os.path.isdir(abs_path):
                    for root, _, files in os.walk(abs_path):
                        for f in files:
                            found_files.add(os.path.join(root, f))
                else:
                    found_files.add(abs_path)
    except Exception:
        pass

    valid_code_files: List[str] = []
    for file_path in sorted(found_files):
        if not os.path.isfile(file_path):
            continue
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in CODE_EXTENSIONS:
            continue
        rel_path = os.path.relpath(file_path, repo_root)
        if is_path_excluded(rel_path):
            continue
        valid_code_files.append(os.path.abspath(file_path))

    return valid_code_files


# --- Violation Detectors ---

# Pattern 1: Synthetic setTimeout handlers masquerading as backend processing
RE_SYNTHETIC_PROMISE_DELAY = re.compile(
    r"(?:new\s+Promise\s*(?:<[^>]+>)?\s*\(\s*(?:\(?\s*(?:resolve|res|r)\s*\)?)\s*=>\s*setTimeout\s*\("
    r"|await\s+new\s+Promise\s*(?:<[^>]+>)?\s*\(\s*(?:resolve|res|r)\s*=>\s*setTimeout\b)",
    re.IGNORECASE,
)

RE_SETTIMEOUT_STATE_MUTATION = re.compile(
    r"setTimeout\s*\(\s*(?:async\s*)?(?:\(\s*\)|function\s*\(\s*\))\s*=>\s*\{[^}]*?\b("
    r"setLoading|setIsLoading|setSubmitting|setIsSubmitting|setSuccess|setSaved|setIsSaved|"
    r"setStatus\s*\(\s*['\"](?:success|saved|completed|done)['\"]"
    r")\b",
    re.DOTALL | re.IGNORECASE,
)

RE_ACTION_HANDLER_SETTIMEOUT = re.compile(
    r"(?:const\s+)?(handle[A-Z]\w*|on[A-Z]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{[^}]*?\bsetTimeout\s*\(",
    re.DOTALL,
)

# Pattern 2: Hardcoded static mock collections (INITIAL_*, SAMPLE_*, fake_*, mock_*)
RE_TS_MOCK_COLLECTION = re.compile(
    r"\b(?:const|let|var)\s+((?:INITIAL_|SAMPLE_|fake_|mock_)[A-Za-z0-9_]+)\s*=",
)

RE_PY_MOCK_COLLECTION = re.compile(
    r"^\s*((?:INITIAL_|SAMPLE_|fake_|mock_)[A-Za-z0-9_]+)\s*=\s*(?:\[|\{)",
    re.MULTILINE,
)

RE_EXPORT_MOCK_COLLECTION = re.compile(
    r"\bexport\s+(?:const|let|var|default)\s+((?:INITIAL_|SAMPLE_|fake_|mock_)[A-Za-z0-9_]+)\b",
)

RE_USESTATE_MOCK_REFERENCE = re.compile(
    r"useState\s*(?:<[^>]+>)?\s*\(\s*((?:INITIAL_|SAMPLE_|MOCK_|mock_|fake_)[A-Za-z0-9_]+)\s*\)",
)

RE_USESTATE_INLINE_DUMMY_ARRAY = re.compile(
    r"useState\s*(?:<[^>]+>)?\s*\(\s*\[\s*\{\s*(?:id|name|title|key)\s*:\s*['\"0-9]",
)

# Pattern 3: Components returning hardcoded dummy states without calling real backend API clients
RE_API_CLIENT_CALL = re.compile(
    r"\b(?:apiClient|axios|fetch|useQuery|useMutation|useApiClient|client\.(?:get|post|put|delete|patch)|api\.(?:get|post|put|delete|patch)|request\()\b"
)

RE_REACT_COMPONENT_SIGNATURE = re.compile(
    r"(?:export\s+(?:default\s+)?(?:function|const)\s+([A-Z][A-Za-z0-9_]*)|function\s+([A-Z][A-Za-z0-9_]*))"
)

RE_PYTHON_STUB_ROUTE = re.compile(
    r"@(?:router|app)\.(?:get|post|put|delete|patch)\s*\([^\)]*\)\s*[\r\n]+"
    r"\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\([^\)]*\)[^:]*:\s*[\r\n]+"
    r"(?:\s*(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?''')\s*[\r\n]+)?"
    r"\s*return\s+(?:\{|\[)[^\r\n]*(?:mock|dummy|fake|sample)",
    re.IGNORECASE,
)


def scan_content_for_mocks(file_path: str, content: str) -> List[MockViolation]:
    """Scans the text content of a file for AGENTS.md Rule 3 mock violations."""
    violations: List[MockViolation] = []
    lines = content.splitlines()

    def get_line_num_for_pos(char_pos: int) -> int:
        return content[:char_pos].count("\n") + 1

    def get_line_snippet(line_num: int) -> str:
        if 1 <= line_num <= len(lines):
            return lines[line_num - 1].strip()
        return ""

    # Check 1: Synthetic Promise delay
    for match in RE_SYNTHETIC_PROMISE_DELAY.finditer(content):
        line_num = get_line_num_for_pos(match.start())
        violations.append(
            MockViolation(
                file_path=file_path,
                line_number=line_num,
                pattern_type="Synthetic setTimeout / Fake Delay",
                message="Synthetic setTimeout delay detected masquerading as backend processing.",
                snippet=get_line_snippet(line_num),
            )
        )

    # Check 2: setTimeout with state mutation
    for match in RE_SETTIMEOUT_STATE_MUTATION.finditer(content):
        line_num = get_line_num_for_pos(match.start())
        state_setter = match.group(1)
        violations.append(
            MockViolation(
                file_path=file_path,
                line_number=line_num,
                pattern_type="Synthetic setTimeout State Mutation",
                message=f"setTimeout callback mutating state '{state_setter}' to simulate backend operation.",
                snippet=get_line_snippet(line_num),
            )
        )

    # Check 3: Action handler using setTimeout to fake processing
    for match in RE_ACTION_HANDLER_SETTIMEOUT.finditer(content):
        handler_name = match.group(1)
        line_num = get_line_num_for_pos(match.start())
        violations.append(
            MockViolation(
                file_path=file_path,
                line_number=line_num,
                pattern_type="Action Handler Mock Delay",
                message=f"Action handler '{handler_name}' uses setTimeout simulating processing instead of a real API call.",
                snippet=get_line_snippet(line_num),
            )
        )

    # Check 4: Hardcoded static mock collections (INITIAL_*, SAMPLE_*, fake_*, mock_*)
    is_python = file_path.endswith(".py")
    if is_python:
        for match in RE_PY_MOCK_COLLECTION.finditer(content):
            var_name = match.group(1)
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="Hardcoded Mock Collection",
                    message=f"Hardcoded static mock collection '{var_name}' masquerading as backend data.",
                    snippet=get_line_snippet(line_num),
                )
            )
    else:
        for match in RE_TS_MOCK_COLLECTION.finditer(content):
            var_name = match.group(1)
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="Hardcoded Mock Collection",
                    message=f"Hardcoded static mock collection '{var_name}' masquerading as backend data.",
                    snippet=get_line_snippet(line_num),
                )
            )

        for match in RE_EXPORT_MOCK_COLLECTION.finditer(content):
            var_name = match.group(1)
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="Exported Mock Collection",
                    message=f"Exporting static mock collection '{var_name}'. Real backend endpoints must be used.",
                    snippet=get_line_snippet(line_num),
                )
            )

        for match in RE_USESTATE_MOCK_REFERENCE.finditer(content):
            collection_name = match.group(1)
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="useState Mock Data Source",
                    message=f"Component state initialized with mock collection '{collection_name}' instead of backend API.",
                    snippet=get_line_snippet(line_num),
                )
            )

        for match in RE_USESTATE_INLINE_DUMMY_ARRAY.finditer(content):
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="Inline Dummy State Array",
                    message="Component state initialized with inline dummy records instead of querying real backend API.",
                    snippet=get_line_snippet(line_num),
                )
            )

    # Check 5: React component rendering dummy state without any API client
    if any(file_path.endswith(ext) for ext in [".tsx", ".jsx"]):
        has_api_client = bool(RE_API_CLIENT_CALL.search(content))
        has_component = bool(RE_REACT_COMPONENT_SIGNATURE.search(content))
        if has_component and not has_api_client:
            # Check if component defines hardcoded data lists
            dummy_list_match = re.search(
                r"\b(?:const|let)\s+([a-zA-Z0-9_]+)\s*=\s*\[\s*\{\s*(?:id|name|title)\s*:\s*['\"0-9]",
                content,
            )
            if dummy_list_match:
                var_name = dummy_list_match.group(1)
                line_num = get_line_num_for_pos(dummy_list_match.start())
                violations.append(
                    MockViolation(
                        file_path=file_path,
                        line_number=line_num,
                        pattern_type="Dummy Component Without Backend API",
                        message=f"Component contains hardcoded list '{var_name}' without calling real backend API clients.",
                        snippet=get_line_snippet(line_num),
                    )
                )

    # Check 6: Python stub route returning fake/mock data
    if is_python:
        for match in RE_PYTHON_STUB_ROUTE.finditer(content):
            route_name = match.group(1)
            line_num = get_line_num_for_pos(match.start())
            violations.append(
                MockViolation(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_type="Stub Endpoint Returning Fake Data",
                    message=f"Route '{route_name}' returns stub/mock dictionary without mutating or querying database.",
                    snippet=get_line_snippet(line_num),
                )
            )

    return violations


def scan_file_for_mocks(file_path: str) -> List[MockViolation]:
    """Reads and scans a single file for mock violations."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return scan_content_for_mocks(file_path, content)
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)
        return []


def scan_repository_for_mocks(
    repo_root: Optional[str] = None, workspace_paths: Optional[List[str]] = None
) -> List[MockViolation]:
    """Scans all modified/created code files in repository for mock violations."""
    root = repo_root or find_repo_root(workspace_paths=workspace_paths)
    code_files = get_modified_code_files(root)
    all_violations: List[MockViolation] = []

    for file_path in code_files:
        violations = scan_file_for_mocks(file_path)
        all_violations.extend(violations)

    return all_violations
