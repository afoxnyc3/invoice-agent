# Quality Check Skill

Run comprehensive quality gates before commits or deployments to ensure code meets project standards.

## Purpose

Automate the quality checks required by CLAUDE.md:
- Test coverage ≥60%
- All tests passing
- Black formatting
- Flake8 linting
- mypy type checking (strict mode)
- bandit security scanning
- Function line count validation (≤25 lines)

## Parameters

- `--mode`: Type of check (optional)
  - `pre-commit`: Fast checks before commit (default)
  - `pre-pr`: Full checks before pull request
  - `pre-deploy`: Comprehensive checks before deployment
- `--fix`: Auto-fix issues where possible (formatting, etc.)

## Instructions

When this skill is invoked, perform the following checks in order:

### 1. Test Suite
Run pytest with coverage requirements:
```bash
pytest --cov=functions --cov=shared --cov-fail-under=60 -v
```
- ✅ Report: X tests passing, Y% coverage
- ❌ Fail if coverage <60% or any tests fail

### 2. Code Formatting (Black)
Check code formatting:
```bash
black --check src/functions src/shared tests/
```
If --fix flag is provided:
```bash
black src/functions src/shared tests/
```
- ✅ Report: Code formatted correctly
- ❌ Report: X files need formatting (list them)

### 3. Linting (Flake8)
Run linting checks:
```bash
flake8 src/functions src/shared tests/
```
- ✅ Report: No linting errors
- ❌ Report: X linting errors (show first 10)

### 4. Type Checking (mypy)
Run type checking in strict mode:
```bash
mypy src/functions src/shared --strict
```
- ✅ Report: Type checking passed
- ❌ Report: X type errors (show first 10)

### 5. Security Scan (bandit)
Run security vulnerability scan:
```bash
bandit -r src/functions src/shared
```
- ✅ Report: No security issues
- ❌ Report: X security issues (list by severity)

### 6. Function Line Count Check (Optional for pre-deploy)
Find functions exceeding 25-line limit:
```bash
# Check Python functions for line count violations
find src/functions src/shared -name "*.py" -type f | while read file; do
  python3 << 'PYEOF'
import sys
import re

def check_function_length(filepath):
    violations = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    in_function = False
    func_start = 0
    func_name = ""
    indent_level = 0
    
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue
            
        # Detect function start
        if re.match(r'^(async\s+)?def\s+\w+', stripped):
            if in_function:
                # Previous function ended
                length = i - func_start - 1
                if length > 25:
                    violations.append(f"{filepath}:{func_start}: {func_name} ({length} lines)")
            
            in_function = True
            func_start = i
            func_name = re.search(r'def\s+(\w+)', stripped).group(1)
            indent_level = len(line) - len(stripped)
        
        # Detect function end (dedent or new function/class)
        elif in_function:
            current_indent = len(line) - len(stripped)
            if current_indent <= indent_level and stripped:
                if re.match(r'^(def|class|async\s+def)', stripped) or current_indent == 0:
                    length = i - func_start - 1
                    if length > 25:
                        violations.append(f"{filepath}:{func_start}: {func_name} ({length} lines)")
                    in_function = False
    
    # Check last function
    if in_function:
        length = len(lines) - func_start
        if length > 25:
            violations.append(f"{filepath}:{func_start}: {func_name} ({length} lines)")
    
    return violations

if __name__ == "__main__":
    for filepath in sys.argv[1:]:
        violations = check_function_length(filepath)
        for v in violations:
            print(v)
PYEOF
done
```
- ✅ Report: All functions ≤25 lines
- ⚠️ Report: X functions exceed 25 lines (list them)

## Output Format

Generate a summary report:

```
🔍 Quality Check Results (mode: {mode})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tests:        98/98 passing (96% coverage)
✅ Formatting:   All files formatted correctly
✅ Linting:      No issues found
❌ Type Check:   3 errors in src/functions/MailIngest/__init__.py
✅ Security:     No vulnerabilities detected
⚠️  Functions:    2 functions exceed 25 lines
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Action Required:
1. Fix type errors in MailIngest (see details above)
2. Refactor long functions:
   - src/functions/ExtractEnrich/__init__.py:45 (32 lines)
   - src/shared/graph_client.py:120 (28 lines)

Overall: ❌ FAILED (2 blockers)
```

## Success Criteria

- **pre-commit mode**: Tests + formatting must pass
- **pre-pr mode**: All checks must pass except function length (warnings OK)
- **pre-deploy mode**: All checks must pass (no warnings)

## Notes

- If --fix is provided, automatically fix formatting issues
- Always run from repository root
- Set PYTHONPATH=./src before running (pytest.ini handles this)
- Use existing make commands if available (make test, make lint)
- For pre-commit, can skip bandit and function length checks for speed
