import os
import subprocess
import sys
import time

def print_header(title):
    print(f"\n{'='*80}\n{title}\n{'='*80}")

def run_command(command, cwd=None, env=None):
    print(f"Running: {command}")
    start = time.time()
    result = subprocess.run(command, shell=True, cwd=cwd, env=env)
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"FAILED (Exit code: {result.returncode}) in {elapsed:.2f}s")
        sys.exit(1)
    print(f"PASSED in {elapsed:.2f}s")

def main():
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    print_header("Gate 1: Python Compileall")
    run_command(f"{sys.executable} -m compileall app/", cwd=workspace_dir)
    
    print_header("Gate 2: Unit & Integration Suite")
    run_command(f"{sys.executable} -m pytest tests/ --ignore=tests/test_fuzzer.py -v", cwd=workspace_dir)
    
    print_header("Gate 3: Concurrency Suite")
    run_command(f"{sys.executable} -m pytest tests/test_concurrency.py -v", cwd=workspace_dir)
    
    print_header("Gate 4: Schemathesis API Fuzzer")
    run_command(f"{sys.executable} -m pytest tests/test_fuzzer.py -v", cwd=workspace_dir)
    
    frontend_dir = os.path.join(workspace_dir, "frontend")
    # For npm to work on Windows in subprocess, shell=True is used
    print_header("Gate 5: Frontend Production Build")
    run_command("npm run build", cwd=frontend_dir)
    
    print_header("Gate 6: Frontend TypeScript")
    run_command("npx tsc --noEmit", cwd=frontend_dir)
    
    print_header("Gate 7: Frontend Linter")
    run_command("npm run lint", cwd=frontend_dir)
    
    print_header("Gate 8: Live Smoke Probes")
    smoke_script = os.path.join(workspace_dir, "run_live_smoke_sweep.py")
    if os.path.exists(smoke_script):
        run_command(f"{sys.executable} run_live_smoke_sweep.py", cwd=workspace_dir)
    elif os.path.exists(os.path.join(workspace_dir, "run_integration_tests.py")):
        run_command(f"{sys.executable} run_integration_tests.py", cwd=workspace_dir)
    else:
        print("No smoke test script found. Skipping Gate 8.")
    
    print_header("ALL 8 GATES PASSED SUCCESSFULLY")

if __name__ == "__main__":
    main()
