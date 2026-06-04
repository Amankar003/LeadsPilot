import time
import sys
import builtins
import importlib

# Override the built-in __import__ to profile imports
original_import = builtins.__import__
import_times = {}

def profile_import(name, globals=None, locals=None, fromlist=(), level=0):
    start = time.perf_counter()
    module = original_import(name, globals, locals, fromlist, level)
    duration = time.perf_counter() - start
    
    # We only care about top-level or slow imports to avoid spam
    if duration > 0.05 and name not in import_times:
        import_times[name] = duration
        
    return module

builtins.__import__ = profile_import

print("Starting profile of app.py execution...")
main_start = time.perf_counter()

# We need to mock streamlit slightly or just run it via import
try:
    import app
except Exception as e:
    print(f"App execution ended with (expected in non-streamlit env): {e}")

main_duration = time.perf_counter() - main_start

# Restore original import
builtins.__import__ = original_import

print(f"\n--- Profiling Results ---")
print(f"Total time: {main_duration:.2f}s")
print("\nSlowest imports (>0.05s):")
sorted_imports = sorted(import_times.items(), key=lambda x: x[1], reverse=True)
for name, duration in sorted_imports[:15]:
    print(f"  {name}: {duration:.3f}s")
