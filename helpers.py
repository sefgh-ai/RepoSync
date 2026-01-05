import requests
from datetime import datetime, timezone
import time

repo_sync_status_codes = ["idle", "running", "completed", "failed"]
topic_status_codes = ["pending", "in_progress", "completed"]


# ============================================================
# KEY MANAGER - Handles API key rotation automatically
# ============================================================
class KeyManager:
    """
    Manages multiple GitHub API keys with automatic rotation.
    
    Usage:
        key_manager = KeyManager(env_dict, key_names)
        token = key_manager.get_key()           # Get best available key
        key_manager.update_from_response(rate_limit_data)  # Update after API call
    """
    
    def __init__(self, env_dict, key_names, validate_tokens=True):
        """Initialize with environment dict and list of key names."""
        self.keys = {}  # {key_name: {"token": "...", "remaining": 5000, "reset_at": datetime}}
        self.current_key = None
        
        loaded_keys = []
        missing_keys = []
        invalid_keys = []  # Keys that exist but fail validation
        
        for key_name in key_names:
            token = env_dict.get(key_name)
            if token:
                # Optionally validate the token by checking rate limit
                if validate_tokens:
                    rate_info = CheckTokenRateLimit(token)
                    if rate_info is None:
                        invalid_keys.append((key_name, "401 Unauthorized - Token invalid or expired"))
                        continue
                    self.keys[key_name] = {
                        "token": token,
                        "remaining": rate_info.get("RemainingRequests", 5000),
                        "reset_at": datetime.fromisoformat(rate_info["ResetTime"].replace("Z", "+00:00")) if rate_info.get("ResetTime") else None,
                        "limit": rate_info.get("TotalRequests", 5000)
                    }
                else:
                    self.keys[key_name] = {
                        "token": token,
                        "remaining": 5000,
                        "reset_at": None,
                        "limit": 5000
                    }
                loaded_keys.append(key_name)
            else:
                missing_keys.append((key_name, "Not found in .env file"))
        
        # Print clean summary
        total = len(key_names)
        success = len(loaded_keys)
        failed = len(missing_keys) + len(invalid_keys)
        
        print("\n" + "=" * 50)
        print("🔑 KeyManager Initialization")
        print("=" * 50)
        print(f"   Total Keys: {total} | ✅ Loaded: {success} | ❌ Failed: {failed}")
        
        if loaded_keys:
            print(f"\n   ✅ Active Keys:")
            for key_name in loaded_keys:
                remaining = self.keys[key_name]["remaining"]
                print(f"      • {key_name} ({remaining} requests available)")
        
        if missing_keys or invalid_keys:
            print(f"\n   ❌ Failed Keys:")
            for key_name, reason in missing_keys:
                print(f"      • {key_name}: {reason}")
            for key_name, reason in invalid_keys:
                print(f"      • {key_name}: {reason}")
        
        if not self.keys:
            print("=" * 50)
            raise ValueError("No valid API keys found!")
        
        # Set first key as current
        self.current_key = list(self.keys.keys())[0]
        print(f"\n   🎯 Starting with: {self.current_key}")
        print("=" * 50 + "\n")
    
    def get_key(self):
        """
        Get the best available API key token.
        - Returns key with most remaining requests
        - If all exhausted, waits for earliest reset
        """
        # Find key with most remaining requests
        best_key = None
        best_remaining = -1
        
        for key_name, info in self.keys.items():
            if info["remaining"] > best_remaining:
                best_remaining = info["remaining"]
                best_key = key_name
        
        # If best key has no remaining requests, wait for reset
        if best_remaining <= 0:
            self._wait_for_reset()
            return self.get_key()  # Retry after waiting
        
        # Switch key if needed
        if best_key != self.current_key:
            old_key = self.current_key
            self.current_key = best_key
            print(f"\n🔄 KEY ROTATION: {old_key} → {best_key}")
            print(f"   Reason: {old_key} exhausted, {best_key} has {best_remaining} remaining\n")
        
        return self.keys[self.current_key]["token"]
    
    def update_from_response(self, rate_limit_data):
        """
        Update key limits from API response's rateLimit field.
        
        Args:
            rate_limit_data: {"remaining": 4500, "resetAt": "2026-01-05T12:00:00Z", "limit": 5000, "cost": 1}
        """
        if not rate_limit_data or not self.current_key:
            return
        
        key_info = self.keys[self.current_key]
        key_info["remaining"] = rate_limit_data.get("remaining", key_info["remaining"])
        key_info["limit"] = rate_limit_data.get("limit", key_info["limit"])
        
        # Parse reset time
        reset_str = rate_limit_data.get("resetAt")
        if reset_str:
            key_info["reset_at"] = datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
        
        # Log when getting low
        if key_info["remaining"] < 100:
            print(f"   ⚠️  {self.current_key}: Only {key_info['remaining']} requests left!")
    
    def _wait_for_reset(self):
        """Wait for the earliest key to reset."""
        # Find earliest reset time
        earliest_reset = None
        earliest_key = None
        
        for key_name, info in self.keys.items():
            if info["reset_at"]:
                if earliest_reset is None or info["reset_at"] < earliest_reset:
                    earliest_reset = info["reset_at"]
                    earliest_key = key_name
        
        if earliest_reset is None:
            # No reset time known, wait 60 seconds as fallback
            print("\n⏳ All keys exhausted. Waiting 60s (no reset time known)...")
            time.sleep(60)
            # Reset all keys to try again
            for key_info in self.keys.values():
                key_info["remaining"] = 5000
            return
        
        # Calculate wait time
        now = datetime.now(timezone.utc)
        wait_seconds = (earliest_reset - now).total_seconds()
        
        if wait_seconds > 0:
            wait_minutes = wait_seconds / 60
            print(f"\n⏳ ALL KEYS EXHAUSTED!")
            print(f"   Waiting for {earliest_key} to reset...")
            print(f"   Reset at: {earliest_reset.strftime('%H:%M:%S UTC')}")
            print(f"   Wait time: {wait_minutes:.1f} minutes ({wait_seconds:.0f} seconds)")
            print()
            time.sleep(wait_seconds + 5)  # Add 5s buffer
        
        # Reset the key's remaining count
        self.keys[earliest_key]["remaining"] = self.keys[earliest_key]["limit"]
        print(f"   ✅ {earliest_key} has reset! Resuming...\n")
    
    def get_status(self):
        """Get current status of all keys (for logging)."""
        status = []
        for key_name, info in self.keys.items():
            marker = "→" if key_name == self.current_key else " "
            status.append(f"  {marker} {key_name}: {info['remaining']}/{info['limit']}")
        return "\n".join(status)


# ============================================================

def CheckTokenRateLimit(token, silent=True):
    """Check token rate limit. Set silent=False to see debug output."""
    if not token or not isinstance(token, str) or len(token.strip()) == 0:
        if not silent:
            print("Error: Invalid or empty token provided")
        return None

    try:
        url = "https://api.github.com/graphql"
        headers = {"Authorization": f"Bearer {token}"}

        RateLimitCheckQuery = """
        {
            rateLimit {
                limit
                remaining
                resetAt
                used
                }
        }
        """

        response = requests.post(url, json={'query': RateLimitCheckQuery}, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' not in data or data['data'] is None:
            if not silent:
                print(f"Error: Invalid API response - {data.get('errors', 'Unknown error')}")
            return None
            
        if 'rateLimit' not in data['data']:
            if not silent:
                print("Error: rateLimit not found in API response")
            return None
            
        rate = data['data']['rateLimit']

        return {
            "TotalRequests": rate["limit"],
            "UsedRequests": rate["used"],
            "RemainingRequests": rate["remaining"],
            "ResetTime": rate["resetAt"]
        }
    except requests.exceptions.Timeout:
        if not silent:
            print("Error: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        if not silent:
            print(f"Error: Network request failed - {e}")
        return None
    except KeyError as e:
        if not silent:
            print(f"Error: Missing key in response - {e}")
        return None
    except Exception as e:
        if not silent:
            print(f"Error: Unexpected error occurred - {e}")
        return None

def maskKey(value):
    return value[:3] + "****" + value[-3:] if value else None

def get_total_apikeys(env_dict, prefix="githubApiKey"):
    """Get all API key names matching the prefix. Returns (count, key_names)."""
    matching_keys = [k for k in env_dict.keys() if k.startswith(prefix)]
    return len(matching_keys), matching_keys

"""
@param key_names: List of API key names
@return: Dictionary with key names as keys and their rate limits as values
@type of limits:
 key used, remaining requests, reset time, total limit.
"""
def get_keys_rate_limits(env_dict, key_names, silent=True):
    """Get rate limits for all keys. Set silent=False to see warnings."""
    if not env_dict or not isinstance(env_dict, dict):
        if not silent:
            print("Error: Invalid env_dict provided")
        return {}
    
    if not key_names or not isinstance(key_names, list):
        if not silent:
            print("Error: Invalid key_names provided")
        return {}
    
    limits = {}
    for key in key_names:
        token = env_dict.get(key)
        if token:
            limits[key] = CheckTokenRateLimit(token)
        else:
            limits[key] = None
    return limits


# Define your dynamic query and pass topic_name as a variable
def fetch_repo_count(topic_name, github_token):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
    }
    query = """
    query GetRepoCount($topic: String!) {
        topic(name: $topic) {
            repositories {
                totalCount
            }
        }
    }
    """
    variables = {"topic": topic_name}
    response = requests.post(
        url, json={"query": query, "variables": variables}, headers=headers
    )

    # Check the response
    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print("GraphQL Errors:", data["errors"])
            return None
        return data["data"]["topic"]["repositories"]["totalCount"] if data["data"]["topic"] else print("Topic not found")
    else:
        print("HTTP Error:", response.status_code, response.text)
        return None