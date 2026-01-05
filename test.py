import os
import requests
from dotenv import load_dotenv

load_dotenv()

QUERY = """
query($topic: String!, $first: Int = 10, $after: String) {
  topic(name: $topic) {
    name
    repositories(
      first: $first,
      after: $after,
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      edges {
        cursor
        node {
          id
          nameWithOwner
          description
          url
          stargazerCount
          forkCount
          createdAt
          updatedAt
          isArchived
          isFork
          homepageUrl
          licenseInfo {
            name
          }
          repositoryTopics(first: 10) {
            nodes {
              topic {
                name
              }
            }
          }
          languages(first: 10) {
            nodes {
              name
            }
          }
          issues(states: [OPEN]) {
            totalCount
          }
          fundingLinks {
            url
            platform
          }
          owner {
            __typename
          }
        }
      }
    }
  }
  rateLimit {
    cost
    remaining
    resetAt
    limit
  }
}
"""


GITHUB_API_URL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.getenv("githubApiKey1")

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json"
}

variables = {
    "topic": "python",   # Change to any GitHub topic
    "first": 10,
    "after": None
}

response = requests.post(
    GITHUB_API_URL,
    json={
        "query": QUERY,
        "variables": variables
    },
    headers=headers
)

response.raise_for_status()
data = response.json()

print(data)
