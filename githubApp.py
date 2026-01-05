import time
import requests

# Retry configuration
INITIAL_DELAY = 10
MAX_DELAY = 90  # Cap at 90 seconds

QUERY="""
query($topic: String!, $first: Int = 10, $after: String) {
  topic(name: $topic) {
    name
    repositories(first: $first, after: $after, orderBy: {field: STARGAZERS, direction: DESC}) {
        pageInfo {
            hasNextPage
            endCursor
        }
      edges {
        cursor # Cursor for pagination
        node {
          id
          databaseId
          nameWithOwner # Full repository name (owner/repo)
          description # Description
        #   url # GitHub URL
          stargazerCount # Stars
          forkCount # Forks
          createdAt # Date created
          updatedAt # Date last updated
          isArchived # Is the repository archived
          isFork # Is the repository a fork
          homepageUrl # Associated homepage URL
          licenseInfo {
            name # Name of the license
          }
          repositoryTopics(first: 10) {
            nodes {
              topic {
                name # Related topics
              }
            }
          }
          languages(first: 10) {
            nodes {
              name # Languages used in the repo
            }
          }
          issues(states: [OPEN]) {
            totalCount # Number of open issues
          }
          fundingLinks {
            url # Links for funding
            platform # Platform for funding links
          }
        #   collaborators {
        #     totalCount # Total collaborators (accessible for public repositories)
        #   }
          owner {
            __typename # Owner type (User or Organization)
          }
        }
      }
    }
  }

  rateLimit{
      cost,
      remaining,    
      resetAt,
      limit
  }
}
"""

def fetch_repos(topic, github_token, page_size=50, after_cursor=None,GITHUB_API_URL="https://api.github.com/graphql"):
    
    headers = {
    "Authorization": f"Bearer {github_token}",
    "Content-Type": "application/json"
    }

    variables = {
            "topic": topic,
            "first": page_size,
            "after": after_cursor
        }
    
    attempt = 0
    current_delay = INITIAL_DELAY
    while True:
        attempt += 1
        try:
            response = requests.post(
                    GITHUB_API_URL,
                    json={"query": QUERY, "variables": variables},
                    headers=headers,
                    timeout=30  # Set a timeout for the request
                )
            
            # Success
            if response.status_code == 200:
                result = response.json()
                
                # Check for GraphQL errors
                if "errors" in result:
                    error_msg = result["errors"][0].get("message", "Unknown GraphQL error")
                    
                    if "rate limit" in error_msg.lower():
                        print(f"[Attempt {attempt}] Rate limited (GraphQL). Waiting 60s...")
                        time.sleep(60)
                        continue
                    
                    raise print(f"GraphQL Error: {error_msg}")
                
                return result
            
            # Rate limit (403 or 429) - wait and retry forever
            elif response.status_code in [403, 429]:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"[Attempt {attempt}] Rate limited (HTTP {response.status_code}). Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            # Auth error (401) - fatal
            elif response.status_code == 401:
                 print("Authentication failed (HTTP 401). Check your GitHub token.")

            # Server error (5xx) - retry forever
            elif 500 <= response.status_code < 600:
                print(f"[Attempt {attempt}] Server error (HTTP {response.status_code}). Waiting {current_delay}s...")
                time.sleep(current_delay)
                current_delay = min(current_delay * 2, MAX_DELAY)
                continue

            
            # Handle HTTP errors
        except requests.exceptions.ConnectionError as e:
            print(f"[Attempt {attempt}] Connection error: {e}")
            print(f"Retrying in {current_delay}s...")
            time.sleep(current_delay)
            current_delay = min(current_delay * 2, MAX_DELAY)  # Exponential backoff, cap at 90s
            continue

        except requests.exceptions.Timeout as e:
            print(f"[Attempt {attempt}] Timeout: {e}")
            print(f"Retrying in {current_delay}s...")
            time.sleep(current_delay)
            current_delay = min(current_delay * 2, MAX_DELAY)  # Exponential backoff, cap at 90s
            continue

        except Exception as e:
            print(f"[Attempt {attempt}] Unexpected error: {type(e).__name__}: {e}")
            print(f"Retrying in {current_delay}s...")
            time.sleep(current_delay)
            current_delay = min(current_delay * 2, MAX_DELAY)
            continue