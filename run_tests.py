#!/usr/bin/env python3
"""
Local test runner that works without complex dependencies
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_unit_tests():
    """Run unit tests"""
    print("Running unit tests...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/unit/", 
            "-v", 
            "-x",
            "--tb=short"
        ], cwd=project_root, capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running unit tests: {e}")
        return False

def run_integration_tests():
    """Run integration tests"""
    print("Running integration tests...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/integration/test_api_routes_simple.py", 
            "-v", 
            "-x",
            "--tb=short"
        ], cwd=project_root, capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running integration tests: {e}")
        return False

def run_simple_tests():
    """Run the simple test suite"""
    print("Running simple functionality tests...")
    try:
        result = subprocess.run([
            sys.executable, "simple_test.py"
        ], cwd=project_root, capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running simple tests: {e}")
        return False

def main():
    """Run all available tests"""
    print("🧪 Starting Local Test Suite")
    print("=" * 50)
    
    results = {}
    
    # Run simple tests first
    results['simple'] = run_simple_tests()
    print()
    
    # Try to run pytest-based tests
    if os.system("python -c 'import pytest' 2>/dev/null") == 0:
        print("pytest available, running pytest-based tests...")
        results['unit'] = run_unit_tests()
        print()
        
        results['integration'] = run_integration_tests()
        print()
    else:
        print("pytest not available, skipping pytest-based tests")
        print("Install pytest with: pip install pytest pytest-mock")
        results['unit'] = None
        results['integration'] = None
    
    # Summary
    print("=" * 50)
    print("🏁 Test Results Summary:")
    
    for test_type, result in results.items():
        if result is True:
            print(f"  ✅ {test_type.title()} tests: PASSED")
        elif result is False:
            print(f"  ❌ {test_type.title()} tests: FAILED")
        else:
            print(f"  ⏸️  {test_type.title()} tests: SKIPPED")
    
    # Return overall status
    failed_tests = [k for k, v in results.items() if v is False]
    if failed_tests:
        print(f"\n❌ Some tests failed: {', '.join(failed_tests)}")
        return 1
    elif all(v is not False for v in results.values()):
        print("\n🎉 All available tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests were skipped due to missing dependencies")
        return 0

if __name__ == "__main__":
    sys.exit(main())