#!/usr/bin/env python3
"""
Environment checker - verifies that all dependencies are working
"""

import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"🐍 Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 8:
        print("  ✅ Python version is compatible")
        return True
    else:
        print("  ⚠️  Python 3.8+ recommended")
        return True  # Still allow older versions

def check_pip_packages():
    """Check if required packages are installed"""
    packages = {
        'fastapi': 'FastAPI web framework',
        'sqlalchemy': 'Database ORM',
        'pydantic': 'Data validation',
        'redis': 'Redis client',
        'requests': 'HTTP client',
        'celery': 'Task queue',
    }
    
    optional_packages = {
        'pytest': 'Testing framework',
        'pytest-mock': 'Pytest mocking',
        'fakeredis': 'Redis testing',
    }
    
    print("\n📦 Checking required packages:")
    all_required_ok = True
    
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"  ✅ {package} - {description}")
        except ImportError:
            print(f"  ❌ {package} - {description} (MISSING)")
            all_required_ok = False
    
    print("\n📦 Checking optional packages (for testing):")
    testing_available = True
    
    for package, description in optional_packages.items():
        try:
            __import__(package)
            print(f"  ✅ {package} - {description}")
        except ImportError:
            print(f"  ⚠️  {package} - {description} (optional, install with: pip install {package})")
            testing_available = False
    
    return all_required_ok, testing_available

def check_app_imports():
    """Check if our app modules can be imported"""
    print("\n🔧 Checking app modules:")
    
    modules = [
        'app.main',
        'app.core.config', 
        'app.models.models',
        'app.controllers.currency_controller',
        'app.controllers.exchange_rate_controller',
        'app.utils.cache_manager',
        'app.api.route',
    ]
    
    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module} - {str(e)}")
            all_ok = False
    
    return all_ok

def check_testing_setup():
    """Check if testing can work"""
    print("\n🧪 Testing setup:")
    
    # Check if basic tests can run
    try:
        result = subprocess.run([
            sys.executable, 'test_local.py'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("  ✅ Basic tests can run")
            basic_tests_ok = True
        else:
            print("  ❌ Basic tests failed")
            print(f"     Error: {result.stderr}")
            basic_tests_ok = False
    except Exception as e:
        print(f"  ❌ Could not run basic tests: {e}")
        basic_tests_ok = False
    
    # Check if pytest is available
    try:
        result = subprocess.run([
            sys.executable, '-c', 'import pytest; print("pytest available")'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ pytest is available")
            pytest_ok = True
        else:
            print("  ⚠️  pytest not available (install with: pip install pytest pytest-mock)")
            pytest_ok = False
    except Exception:
        print("  ⚠️  pytest not available")
        pytest_ok = False
    
    return basic_tests_ok, pytest_ok

def provide_recommendations(results):
    """Provide recommendations based on check results"""
    python_ok, (required_ok, testing_ok), app_ok, (basic_ok, pytest_ok) = results
    
    print("\n" + "="*60)
    print("🎯 RECOMMENDATIONS:")
    
    if not required_ok:
        print("\n❌ CRITICAL: Install missing required packages:")
        print("   pip install -r requirements.txt")
        return
    
    if not app_ok:
        print("\n❌ CRITICAL: App modules have import errors")
        print("   Check the error messages above and fix import issues")
        return
    
    if basic_ok:
        print("\n✅ GOOD NEWS: You can run tests!")
        print("   Run: python test_local.py")
        print("   Or:  make test-basic")
    
    if not pytest_ok:
        print("\n💡 OPTIONAL: For more comprehensive testing:")
        print("   pip install pytest pytest-mock fakeredis")
        print("   Then run: python run_tests.py")
    
    if python_ok and required_ok and app_ok and basic_ok:
        print("\n🎉 EXCELLENT: Your environment is ready!")
        print("   • Basic testing: python test_local.py")
        if pytest_ok:
            print("   • Full testing:  python run_tests.py")
        print("   • Start app:     uvicorn app.main:app --reload")

def main():
    """Run all checks"""
    print("🔍 ENVIRONMENT CHECK")
    print("="*60)
    
    # Change to project directory
    project_root = Path(__file__).parent
    import os
    os.chdir(project_root)
    
    # Add to Python path
    sys.path.insert(0, str(project_root))
    
    # Run checks
    python_ok = check_python_version()
    package_results = check_pip_packages()
    app_ok = check_app_imports()
    test_results = check_testing_setup()
    
    # Provide recommendations
    provide_recommendations((python_ok, package_results, app_ok, test_results))
    
    # Return exit code
    required_ok = package_results[0]
    basic_tests_ok = test_results[0]
    
    if required_ok and app_ok and basic_tests_ok:
        return 0  # Success
    else:
        return 1  # Issues found

if __name__ == "__main__":
    sys.exit(main())