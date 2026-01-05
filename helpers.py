import requests

repo_sync_status_codes = ["idle", "running", "completed", "failed"]
topic_status_codes = ["pending", "in_progress", "completed"]

def CheckTokenRateLimit(token):
    # Validate input
    if not token or not isinstance(token, str) or len(token.strip()) == 0:
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
        response.raise_for_status()  # Raise exception for bad status codes
        
        data = response.json()
        
        # Validate response structure
        if 'data' not in data or data['data'] is None:
            print(f"Error: Invalid API response - {data.get('errors', 'Unknown error')}")
            return None
            
        if 'rateLimit' not in data['data']:
            print("Error: rateLimit not found in API response")
            return None
            
        rate = data['data']['rateLimit']

        print(data) #print raw response for debugging only

        # Return in your format
        return {
            "TotalRequests": rate["limit"],
            "UsedRequests": rate["used"],
            "RemainingRequests": rate["remaining"],
            "ResetTime": rate["resetAt"] #return as ISO 8601 string not datetime object
        }
    except requests.exceptions.Timeout:
        print("Error: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Network request failed - {e}")
        return None
    except KeyError as e:
        print(f"Error: Missing key in response - {e}")
        return None
    except Exception as e:
        print(f"Error: Unexpected error occurred - {e}")
        return None

def maskKey(value):
    return value[:3] + "****" + value[-3:] if value else None

def get_total_apikeys(env_dict, prefix="githubApiKey"):

    matching_keys = [k for k in env_dict.keys() if k.startswith(prefix)]

    print("Total matching keys:", len(matching_keys))
    print("Available keys:")
    for key in matching_keys:
        print("-", key)
    return len(matching_keys), matching_keys

"""
@param key_names: List of API key names
@return: Dictionary with key names as keys and their rate limits as values
@type of limits:
 key used, remaining requests, reset time, total limit.
"""
def get_keys_rate_limits(env_dict, key_names):
    # Validate inputs
    if not env_dict or not isinstance(env_dict, dict):
        print("Error: Invalid env_dict provided")
        return {}
    
    if not key_names or not isinstance(key_names, list):
        print("Error: Invalid key_names provided")
        return {}
    
    limits = {}
    for key in key_names:
        token = env_dict.get(key)
        if token:
            limits[key] = CheckTokenRateLimit(token) # Fetch and store rate limit info
        else:
            print(f"Warning: Key '{key}' not found in env_dict")
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