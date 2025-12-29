import requests

QUERY="""
query($topic: String!, $first: Int = 10, $after: String) {
  topic(name: $topic) {
    name
    repositories(first: $first, after: $after, orderBy: {field: STARGAZERS, direction: DESC}) {
      edges {
        cursor # Cursor for pagination
        node {
          id
          nameWithOwner # Full repository name (owner/repo)
          description # Description
          url # GitHub URL
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

headers = {
    "Authorization": f"Bearer {github_token}",
    "Content-Type": "application/json"
}

variables = {
    "topic": topic_name,   # Change to any GitHub topic
    "first": 50,
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