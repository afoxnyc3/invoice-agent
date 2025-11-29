# Pipeline Monitor Skill

Monitor GitHub Actions CI/CD pipeline status, wait for completion, and report results with actionable fixes.

## Purpose

Provide real-time CI/CD pipeline monitoring after pushing code. Enables verification of pipeline health before creating PRs or merging. Integrates with `quality-check` skill for local remediation.

## Parameters

- `--branch`: Branch to monitor (default: current branch)
- `--wait`: Wait for completion (default: true)
- `--timeout`: Max wait in seconds (default: 600)
- `--pr`: PR number to check (alternative to branch)

## Instructions

When this skill is invoked, perform the following steps:

### 1. Prerequisites Check
Verify gh CLI is authenticated:
```bash
gh auth status
```
- ✅ Authenticated to github.com
- ❌ Run `gh auth login` to authenticate

### 2. Get Current Context
```bash
# Get branch name
BRANCH=$(git branch --show-current)
echo "Branch: $BRANCH"

# Check if branch has been pushed
git fetch origin
if ! git rev-parse --verify origin/$BRANCH >/dev/null 2>&1; then
  echo "Branch not pushed to remote yet"
  exit 1
fi

# Get latest commit SHA
COMMIT=$(git rev-parse HEAD)
echo "Commit: $COMMIT"
```

### 3. Wait for Workflow Run to Appear
```bash
# Poll until workflow appears (max 2 minutes)
echo "Waiting for workflow to start..."
for i in {1..24}; do
  RUN_ID=$(gh run list --limit 1 --branch "$BRANCH" --json databaseId,headSha -q ".[] | select(.headSha==\"$COMMIT\") | .databaseId")
  if [ -n "$RUN_ID" ]; then
    echo "Found run: $RUN_ID"
    break
  fi
  sleep 5
done

if [ -z "$RUN_ID" ]; then
  echo "No workflow run found for commit $COMMIT"
  exit 1
fi
```

### 4. Monitor Until Completion
```bash
echo "Monitoring run $RUN_ID..."
TIMEOUT=${TIMEOUT:-600}
ELAPSED=0
INTERVAL=30

while [ $ELAPSED -lt $TIMEOUT ]; do
  STATUS=$(gh run view $RUN_ID --json status -q '.status')
  CONCLUSION=$(gh run view $RUN_ID --json conclusion -q '.conclusion')

  echo "$(date +%H:%M:%S) Status: $STATUS, Conclusion: $CONCLUSION"

  if [ "$STATUS" = "completed" ]; then
    break
  fi

  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$STATUS" != "completed" ]; then
  echo "Timeout after ${TIMEOUT}s - pipeline still running"
  exit 1
fi
```

### 5. Report Results
```bash
# Get detailed job status
gh run view $RUN_ID --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'

# Get run URL
RUN_URL=$(gh run view $RUN_ID --json url -q '.url')
echo "Run URL: $RUN_URL"
```

### 6. On Failure - Analyze and Suggest Fixes
```bash
if [ "$CONCLUSION" != "success" ]; then
  echo ""
  echo "=== FAILURE ANALYSIS ==="

  # Get failed job logs
  gh run view $RUN_ID --log-failed 2>&1 | tail -100

  echo ""
  echo "=== SUGGESTED FIXES ==="
fi
```

## Common Failure Patterns and Fixes

| CI Job | Failure Pattern | Local Fix |
|--------|-----------------|-----------|
| Test and Quality Checks | `black --check` failed | `black src/ tests/` |
| Test and Quality Checks | `flake8` errors | Fix file:line shown in log |
| Test and Quality Checks | pytest failures | `PYTHONPATH=./src pytest -x` |
| Test and Quality Checks | coverage <60% | Add more tests |
| Build Azure Functions | Import errors | Use `from shared.*` not `from src.shared.*` |
| Deploy to staging | Bicep errors | Check infrastructure/bicep/ syntax |
| Smoke Tests | Health check failed | Check app settings in staging slot |

## Output Format

Generate a summary report:

```
🔄 Pipeline Monitor Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Branch:     feature/issue-42-new-feature
Commit:     abc1234
Run ID:     12345678
Duration:   3m 45s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Jobs:
✅ Test and Quality Checks    (2m 15s)
✅ Build Azure Functions      (1m 30s)
⏭️  Deploy to staging          (skipped - not main branch)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall: ✅ PASSED - Ready to merge

Run URL: https://github.com/org/repo/actions/runs/12345678
```

On failure:
```
🔄 Pipeline Monitor Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Branch:     feature/issue-42-new-feature
Commit:     abc1234
Run ID:     12345678
Duration:   1m 45s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Jobs:
❌ Test and Quality Checks    (1m 45s)
⏭️  Build Azure Functions      (skipped)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall: ❌ FAILED

Failure: Black formatting check failed
Files needing format:
  - src/functions/MailIngest/__init__.py
  - tests/unit/test_models.py

Suggested Fix:
  Run locally: black src/ tests/
  Then: git add -A && git commit -m "style: fix formatting" && git push

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Integration with quality-check Skill

When pipeline fails, recommend running quality-check locally first:

```
Before pushing again, run quality checks locally:
  /skill:quality-check --mode pre-commit --fix

This will:
1. Run tests and show failures
2. Auto-fix formatting issues
3. Show linting errors to fix
4. Prevent repeated CI failures
```

## Success Criteria

- Pipeline status is `completed` with `conclusion: success`
- All required jobs passed (test, build)
- No blocking failures

## Quick Reference Commands

```bash
# Check if pipeline started
gh run list --limit 3 --branch $(git branch --show-current)

# Watch specific run
gh run watch <run_id>

# Get PR check status
gh pr checks <pr_number>

# Re-run failed jobs
gh run rerun <run_id> --failed

# Get failed logs
gh run view <run_id> --log-failed
```

## Notes

- CI workflow (`ci.yml`) runs on PRs - tests only
- CI/CD workflow (`ci-cd.yml`) runs on main - full deployment
- Pipeline typically takes 3-5 minutes for test+build
- Staging deployment adds another 2-3 minutes
- If timeout occurs, pipeline may still complete - check GitHub UI
