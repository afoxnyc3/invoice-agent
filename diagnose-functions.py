#!/usr/bin/env python3
"""
Diagnose why Azure Functions aren't being discovered in production.
"""

import json
import os
from pathlib import Path


def check_function_structure():
    """Validate the function app structure."""
    issues = []
    src_path = Path("src")

    # Check if src directory exists
    if not src_path.exists():
        issues.append("❌ src directory not found")
        return issues

    print("🔍 Checking Azure Functions structure...\n")

    # Check host.json
    host_json = src_path / "host.json"
    if not host_json.exists():
        issues.append("❌ host.json not found in src/")
    else:
        try:
            with open(host_json) as f:
                host_config = json.load(f)
                print(f"✅ host.json found - version: {host_config.get('version', 'NOT SET')}")
        except json.JSONDecodeError as e:
            issues.append(f"❌ host.json is invalid JSON: {e}")

    # Check each function
    functions_dir = src_path / "functions"
    if not functions_dir.exists():
        issues.append("❌ functions directory not found")
        return issues

    function_names = ["MailIngest", "ExtractEnrich", "PostToAP", "Notify", "AddVendor"]

    for func_name in function_names:
        func_path = functions_dir / func_name
        print(f"\n📦 Checking {func_name}:")

        # Check directory exists
        if not func_path.exists():
            issues.append(f"❌ {func_name} directory not found")
            continue

        # Check __init__.py
        init_file = func_path / "__init__.py"
        if not init_file.exists():
            issues.append(f"❌ {func_name}/__init__.py not found")
        else:
            # Check if it has a main function
            with open(init_file) as f:
                content = f.read()
                if "def main(" not in content:
                    issues.append(f"❌ {func_name}/__init__.py missing 'main' function")
                else:
                    print(f"  ✅ __init__.py with main function")

        # Check function.json
        func_json = func_path / "function.json"
        if not func_json.exists():
            issues.append(f"❌ {func_name}/function.json not found")
        else:
            try:
                with open(func_json) as f:
                    func_config = json.load(f)
                    bindings = func_config.get("bindings", [])
                    if not bindings:
                        issues.append(f"❌ {func_name}/function.json has no bindings")
                    else:
                        # Check scriptFile if specified
                        script_file = func_config.get("scriptFile")
                        if script_file and script_file != "__init__.py":
                            issues.append(f"⚠️  {func_name}/function.json has non-standard scriptFile: {script_file}")

                        # Display binding types
                        binding_types = [b.get("type", "unknown") for b in bindings]
                        print(f"  ✅ function.json with bindings: {', '.join(binding_types)}")
            except json.JSONDecodeError as e:
                issues.append(f"❌ {func_name}/function.json is invalid JSON: {e}")

    # Check requirements.txt
    requirements_file = src_path / "requirements.txt"
    if not requirements_file.exists():
        issues.append("❌ requirements.txt not found in src/")
    else:
        with open(requirements_file) as f:
            deps = f.read()
            if "azure-functions" not in deps:
                issues.append("⚠️  azure-functions not in requirements.txt")
            else:
                print(f"\n✅ requirements.txt with azure-functions")

    return issues


def check_function_json_format():
    """Check if function.json files have the correct format."""
    print("\n🔧 Checking function.json format details...\n")

    functions_dir = Path("src/functions")
    for func_dir in functions_dir.iterdir():
        if func_dir.is_dir():
            func_json = func_dir / "function.json"
            if func_json.exists():
                with open(func_json) as f:
                    config = json.load(f)

                # Check if scriptFile is specified (it shouldn't be for Python)
                if "scriptFile" in config:
                    print(f"⚠️  {func_dir.name}: Has scriptFile='{config['scriptFile']}' (usually not needed)")

                # Check if disabled flag is set
                if config.get("disabled", False):
                    print(f"❌ {func_dir.name}: Function is DISABLED")

                # Check bindings
                bindings = config.get("bindings", [])
                if not bindings:
                    print(f"❌ {func_dir.name}: No bindings defined")
                else:
                    for binding in bindings:
                        if not binding.get("name"):
                            print(f"❌ {func_dir.name}: Binding missing 'name' field")
                        if not binding.get("type"):
                            print(f"❌ {func_dir.name}: Binding missing 'type' field")
                        if not binding.get("direction"):
                            print(f"❌ {func_dir.name}: Binding missing 'direction' field")


def main():
    print("=" * 60)
    print("Azure Functions Diagnostic Report")
    print("=" * 60)

    issues = check_function_structure()
    check_function_json_format()

    print("\n" + "=" * 60)
    if issues:
        print("❌ Issues Found:\n")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ All structural checks passed!")

    print("\n📋 Next Steps:")
    print("1. If all checks pass locally, the issue is in deployment")
    print("2. Check if .python_packages/ is included in deployment")
    print("3. Verify FUNCTIONS_WORKER_RUNTIME=python in App Settings")
    print("4. Check Application Insights for startup errors")
    print("=" * 60)


if __name__ == "__main__":
    main()