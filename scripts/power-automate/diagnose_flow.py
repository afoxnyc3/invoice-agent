#!/usr/bin/env python3
"""
Diagnose common issues in Power Automate flow exports.

Analyzes flow definition JSON to identify:
- Parse JSON schema mismatches
- Incorrect trigger configurations
- Common adaptive card issues
- Missing error handling

Usage:
    python diagnose_flow.py <flow_export.json>
    python diagnose_flow.py <flow_folder>/definition.json

Input:
    - Exported flow package (unzipped, point to definition.json)
    - Or the workflow.json from flow export
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any


def load_flow_definition(path: str) -> dict:
    """Load flow definition from file."""
    file_path = Path(path)
    
    # If directory, look for definition.json
    if file_path.is_dir():
        candidates = [
            file_path / "definition.json",
            file_path / "workflow.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                file_path = candidate
                break
        else:
            raise FileNotFoundError(
                f"No definition.json or workflow.json found in {path}"
            )
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_trigger(definition: dict) -> List[dict]:
    """Analyze trigger configuration."""
    issues = []
    
    triggers = definition.get("triggers", {})
    
    for name, config in triggers.items():
        trigger_type = config.get("type", "Unknown")
        trigger_kind = config.get("kind", "")
        
        # Check for Teams webhook trigger
        if trigger_kind == "Teams" or "TeamsWebhook" in trigger_type:
            schema = config.get("inputs", {}).get("schema", {})
            
            if not schema:
                issues.append({
                    "severity": "warning",
                    "component": f"Trigger: {name}",
                    "issue": "No schema defined for trigger input",
                    "suggestion": "Define schema to validate incoming payloads"
                })
            else:
                # Check for expected properties
                props = schema.get("properties", {})
                if "type" not in props:
                    issues.append({
                        "severity": "info",
                        "component": f"Trigger: {name}",
                        "issue": "Schema missing 'type' property",
                        "suggestion": "Webhook payloads should have type='message'"
                    })
                if "attachments" not in props:
                    issues.append({
                        "severity": "warning",
                        "component": f"Trigger: {name}",
                        "issue": "Schema missing 'attachments' property",
                        "suggestion": "Add attachments array to schema for adaptive cards"
                    })
    
    return issues


def analyze_actions(definition: dict) -> List[dict]:
    """Analyze action configurations."""
    issues = []
    
    actions = definition.get("actions", {})
    
    for name, config in actions.items():
        action_type = config.get("type", "Unknown")
        
        # Check Parse JSON actions
        if "ParseJson" in action_type or name.lower().startswith("parse"):
            schema = config.get("inputs", {}).get("schema", {})
            
            if not schema or schema == {}:
                issues.append({
                    "severity": "error",
                    "component": f"Action: {name}",
                    "issue": "Parse JSON has empty or missing schema",
                    "suggestion": "Use 'Generate from sample' with actual payload"
                })
            
            # Check if schema expects array vs object
            schema_type = schema.get("type")
            if schema_type == "array":
                issues.append({
                    "severity": "info",
                    "component": f"Action: {name}",
                    "issue": "Schema expects array - verify input is actually array",
                    "suggestion": "If input might be null, use if() expression"
                })
        
        # Check Teams post actions
        if "Teams" in action_type and "Post" in action_type:
            inputs = config.get("inputs", {})
            
            # Check for hardcoded vs dynamic content
            message_body = inputs.get("body", {}).get("messageBody", "")
            if isinstance(message_body, str) and "@{" not in message_body:
                if len(message_body) > 100:
                    issues.append({
                        "severity": "info",
                        "component": f"Action: {name}",
                        "issue": "Using hardcoded message body",
                        "suggestion": "Consider using dynamic content for flexibility"
                    })
        
        # Check for missing runAfter (error handling)
        run_after = config.get("runAfter", {})
        if run_after:
            for dep, statuses in run_after.items():
                if "Failed" in statuses or "TimedOut" in statuses:
                    # This is error handling - good!
                    pass
    
    # Check for Scope actions (Try/Catch pattern)
    has_try_catch = False
    for name, config in actions.items():
        if config.get("type") == "Scope":
            run_after = config.get("runAfter", {})
            for dep, statuses in run_after.items():
                if "Failed" in statuses:
                    has_try_catch = True
                    break
    
    if not has_try_catch and len(actions) > 3:
        issues.append({
            "severity": "warning",
            "component": "Flow structure",
            "issue": "No error handling detected (Try/Catch pattern)",
            "suggestion": "Add Scope actions with runAfter: Failed for error handling"
        })
    
    return issues


def analyze_expressions(definition: dict) -> List[dict]:
    """Check for problematic expressions."""
    issues = []
    
    def check_value(value: Any, path: str):
        if isinstance(value, str):
            # Check for common expression issues
            if "@{triggerBody()}" in value and "?" not in value:
                issues.append({
                    "severity": "warning",
                    "component": path,
                    "issue": "Using triggerBody() without null-safe accessor",
                    "suggestion": "Use triggerBody()? for null-safe access"
                })
            
            if "body('Parse_JSON')" in value and "?" not in value:
                issues.append({
                    "severity": "warning",
                    "component": path,
                    "issue": "Accessing Parse JSON output without null-safe accessor",
                    "suggestion": "Use body('Parse_JSON')? for null-safe access"
                })
            
            # Check for potential JSON in string
            if '"type"' in value and '"AdaptiveCard"' in value:
                if "json(" not in value.lower():
                    issues.append({
                        "severity": "info",
                        "component": path,
                        "issue": "Adaptive card JSON may be string instead of object",
                        "suggestion": "Use json() function if posting dynamic card"
                    })
        
        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}")
        
        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{path}[{i}]")
    
    check_value(definition, "root")
    
    return issues


def analyze_flow(definition: dict) -> List[dict]:
    """Run all analyses on flow definition."""
    all_issues = []
    
    # Get the actual definition if wrapped
    if "definition" in definition:
        definition = definition["definition"]
    
    all_issues.extend(analyze_trigger(definition))
    all_issues.extend(analyze_actions(definition))
    all_issues.extend(analyze_expressions(definition))
    
    return all_issues


def print_results(issues: List[dict], verbose: bool = False):
    """Print analysis results."""
    print("\n" + "=" * 60)
    print("FLOW ANALYSIS RESULTS")
    print("=" * 60)
    
    if not issues:
        print("\n✅ No issues found!")
        print("=" * 60 + "\n")
        return
    
    # Group by severity
    by_severity = {"error": [], "warning": [], "info": []}
    for issue in issues:
        sev = issue.get("severity", "info")
        by_severity[sev].append(issue)
    
    # Print errors first
    if by_severity["error"]:
        print(f"\n🔴 ERRORS ({len(by_severity['error'])})")
        print("-" * 40)
        for issue in by_severity["error"]:
            print(f"\n  Component: {issue['component']}")
            print(f"  Issue: {issue['issue']}")
            print(f"  Fix: {issue['suggestion']}")
    
    # Then warnings
    if by_severity["warning"]:
        print(f"\n🟡 WARNINGS ({len(by_severity['warning'])})")
        print("-" * 40)
        for issue in by_severity["warning"]:
            print(f"\n  Component: {issue['component']}")
            print(f"  Issue: {issue['issue']}")
            print(f"  Suggestion: {issue['suggestion']}")
    
    # Info only if verbose
    if verbose and by_severity["info"]:
        print(f"\n🔵 INFO ({len(by_severity['info'])})")
        print("-" * 40)
        for issue in by_severity["info"]:
            print(f"\n  Component: {issue['component']}")
            print(f"  Note: {issue['issue']}")
            print(f"  Tip: {issue['suggestion']}")
    elif by_severity["info"]:
        print(f"\n(Hiding {len(by_severity['info'])} info items. Use --verbose to show)")
    
    print("\n" + "=" * 60)
    print(f"Summary: {len(by_severity['error'])} errors, "
          f"{len(by_severity['warning'])} warnings, "
          f"{len(by_severity['info'])} info")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose common issues in Power Automate flow exports"
    )
    parser.add_argument(
        "path",
        help="Path to flow definition.json or export folder"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all issues including info level"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    try:
        definition = load_flow_definition(args.path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in flow definition: {e}")
        sys.exit(1)
    
    issues = analyze_flow(definition)
    
    if args.json:
        print(json.dumps(issues, indent=2))
    else:
        print_results(issues, args.verbose)
    
    # Exit with error code if there are errors
    errors = [i for i in issues if i.get("severity") == "error"]
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
