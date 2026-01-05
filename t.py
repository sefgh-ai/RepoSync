import os
import requests
import time
import csv
from dotenv import load_dotenv

load_dotenv()

def save_repos_to_csv(repos, filename="repos.csv"):
    fieldnames = [
        "id",
        "nameWithOwner",
        "description",
        "stargazerCount",
        "forkCount",
        "createdAt",
        "updatedAt",
        "isArchived",
        "isFork",
        "homepageUrl",
        "license",
        "topics",
        "languages",
        "openIssues",
        "ownerType"
    ]

    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for repo in repos:
            writer.writerow({
                "id": repo.get("id"),
                "nameWithOwner": repo.get("nameWithOwner"),
                "description": repo.get("description"),
                "stargazerCount": repo.get("stargazerCount"),
                "forkCount": repo.get("forkCount"),
                "createdAt": repo.get("createdAt"),
                "updatedAt": repo.get("updatedAt"),
                "isArchived": repo.get("isArchived"),
                "isFork": repo.get("isFork"),
                "homepageUrl": repo.get("homepageUrl"),
                "license": (
                    repo["licenseInfo"]["name"]
                    if repo.get("licenseInfo") else None
                ),
                "topics": ", ".join(
                    t["topic"]["name"]
                    for t in repo["repositoryTopics"]["nodes"]
                ),
                "languages": ", ".join(
                    l["name"]
                    for l in repo["languages"]["nodes"]
                ),
                "openIssues": repo["issues"]["totalCount"],
                "ownerType": repo["owner"]["__typename"]
            })


QUERY = """
query($topic: String!, $first: Int = 10, $after: String) {
  topic(name: $topic) {
    name
    repositories(
      first: $first,
      after: $after,
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
        pageInfo {
            hasNextPage
            endCursor
        }
      edges {
        cursor
        node {
          id
          nameWithOwner
          description
        #   url
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

def fetch_all_repos_for_topic(topic, page_size=50):
    all_repos = []
    after_cursor = None

    while True:
        variables = {
            "topic": topic,
            "first": page_size,
            "after": after_cursor
        }

        response = requests.post(
            GITHUB_API_URL,
            json={"query": QUERY, "variables": variables},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            raise RuntimeError(result["errors"])

        repos_data = result["data"]["topic"]["repositories"]
        edges = repos_data["edges"]

        for edge in edges:
            all_repos.append(edge["node"])

        page_info = repos_data["pageInfo"]

        print(
            f"Fetched {len(edges)} repos "
            f"(total={len(all_repos)})"
        )

        if not page_info["hasNextPage"]:
            break

        after_cursor = page_info["endCursor"]

        # Optional: be polite to the API
        time.sleep(0.2)

    return all_repos



repos = fetch_all_repos_for_topic("developer-productivity", page_size=50)
save_repos_to_csv(repos, "developer_productivity_repos.csv")

print(f"Saved {len(repos)} repositories to developer_productivity_repos.csv")
