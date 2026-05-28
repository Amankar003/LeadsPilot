import sys
import os
import traceback

# Reconfigure standard streams to UTF-8 for cross-platform emoji support
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import test modules
from tests import test_hash_utils
from tests import test_mailforge_enrichment
from tests import test_mailforge_generator
from tests import test_mailforge_suppression
from tests import test_app_imports
from tests import test_type_utils
from tests import test_dork_optimizer

def run_module_tests(module, name):
    print(f"\n======================================")
    print(f" Running: {name}")
    print(f"======================================")
    
    passed = 0
    failed = 0
    
    # Find all test functions in the module
    test_funcs = [getattr(module, x) for x in dir(module) if x.startswith("test_")]
    
    for func in test_funcs:
        func_name = func.__name__
        try:
            # Clean up DB or mock environments if needed
            func()
            print(f"✅ {func_name} - PASSED")
            passed += 1
        except Exception as e:
            print(f"❌ {func_name} - FAILED")
            traceback.print_exc()
            failed += 1
            
    return passed, failed

if __name__ == "__main__":
    print("🚀 LeadPilot AI & MailForge Custom Test Suite Runner 🚀")
    
    modules = [
        (test_app_imports, "App Imports & Compiler Safety"),
        (test_hash_utils, "Centralized Hash Utils"),
        (test_mailforge_enrichment, "MailForge Lead Enrichment"),
        (test_mailforge_generator, "MailForge AI Copywriting"),
        (test_mailforge_suppression, "MailForge Suppression Lists"),
        (test_type_utils, "Safe Type Conversion Utilities"),
        (test_dork_optimizer, "Dork Optimizer Discovery Pipeline")
    ]
    
    total_passed = 0
    total_failed = 0
    
    for mod, name in modules:
        p, f = run_module_tests(mod, name)
        total_passed += p
        total_failed += f
        
    print("\n======================================")
    print("               SUMMARY                ")
    print("======================================")
    print(f"Total Tests Run: {total_passed + total_failed}")
    print(f"Total Passed:    {total_passed}")
    print(f"Total Failed:    {total_failed}")
    
    if total_failed > 0:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
