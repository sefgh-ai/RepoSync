"""
Test script for KeyManager - simulates key rotation
"""
from dotenv import dotenv_values
from helpers import KeyManager, get_total_apikeys

print("=" * 60)
print("🧪 TESTING KEY MANAGER")
print("=" * 60)

# Load keys
env = dotenv_values(".env")
_, key_names = get_total_apikeys(env, prefix="githubApiKey")

# Initialize KeyManager
km = KeyManager(env, key_names)

print("\n📊 Initial Status:")
print(km.get_status())

# Test 1: Get a key normally
print("\n" + "-" * 40)
print("TEST 1: Get key normally")
token = km.get_key()
print(f"Got token: {token[:10]}...{token[-5:]}")

# Test 2: Simulate key exhaustion
print("\n" + "-" * 40)
print("TEST 2: Simulate first key exhaustion")
first_key = list(km.keys.keys())[0]
km.keys[first_key]["remaining"] = 0  # Exhaust first key
print(f"Set {first_key} remaining = 0")

print("\n📊 Status after exhaustion:")
print(km.get_status())

# Now get_key() should rotate to next key
print("\nCalling get_key()...")
token = km.get_key()
print(f"Got token: {token[:10]}...{token[-5:]}")

print("\n📊 Final Status:")
print(km.get_status())

# Test 3: Check if it's actually a different key
print("\n" + "-" * 40)
print("TEST 3: Verify rotation happened")
print(f"Current key is now: {km.current_key}")

# Test 4: Simulate ALL keys exhausted (won't actually wait, just show logic)
print("\n" + "-" * 40)
print("TEST 4: What happens when ALL keys exhausted?")
print("(Skipping actual wait - just showing the scenario)")
for key_name in km.keys:
    km.keys[key_name]["remaining"] = 0
print("\n📊 All keys exhausted:")
print(km.get_status())
print("\n⚠️  If you call get_key() now, it would wait for reset...")
print("(Not calling to avoid waiting)")

print("\n" + "=" * 60)
print("✅ KEY MANAGER TESTS COMPLETE")
print("=" * 60)
