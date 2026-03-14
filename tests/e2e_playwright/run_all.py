"""Runner: execute all E2E Playwright tests sequentially."""
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
TEST_FILES = sorted(TESTS_DIR.glob("test_*.py"))

print(f"Found {len(TEST_FILES)} test files\n")

total_passed = 0
total_failed = 0
results = []

for test_file in TEST_FILES:
    if test_file.name == "run_all.py":
        continue
    print(f"\n{'='*60}")
    print(f"Running: {test_file.name}")
    print(f"{'='*60}")

    result = subprocess.run(
        [sys.executable, str(test_file)],
        capture_output=False,
        text=True,
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    results.append((test_file.name, status))

print(f"\n\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
for name, status in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon}  {name}: {status}")

failed = sum(1 for _, s in results if s == "FAIL")
passed = sum(1 for _, s in results if s == "PASS")
print(f"\n  Total: {passed} passed, {failed} failed out of {len(results)} test files")

if failed > 0:
    sys.exit(1)
