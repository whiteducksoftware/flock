"""This module provides tools for interacting with GitHub repositories."""

import base64
import os

import httpx


def create_user_stories_as_github_issue(title: str, body: str) -> str:
    """Create a new GitHub issue representing a user story.

    This function creates an issue in a GitHub repository using the specified title and body.
    The title is used as the issue title, and the body should contain the full user story
    description along with a formatted list of acceptance criteria. The following
    environment variables must be set for this function to work correctly:

      - GITHUB_PAT: Personal Access Token for GitHub API authentication.
      - GITHUB_REPO: Repository identifier in the format "owner/repo".

    Parameters:
        title (str): The title for the GitHub issue (user story).
        body (str): The detailed description including acceptance criteria.

    Returns:
        str: A message indicating whether the issue was created successfully or not.
    """
    github_pat = os.getenv("GITHUB_PAT")
    github_repo = os.getenv("GITHUB_REPO")

    url = f"https://api.github.com/repos/{github_repo}/issues"
    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Accept": "application/vnd.github+json",
    }
    issue_title = title
    issue_body = body

    payload = {"title": issue_title, "body": issue_body}
    response = httpx.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        return "Issue created successfully."
    else:
        return "Failed to create issue. Please try again later."


def upload_readme(content: str):
    """Upload or update the README.md file in a GitHub repository.

    This function uses the GitHub API to either create a new README.md file or update an
    existing one in the specified repository. It encodes the provided content to base64 before
    sending it via the API. The function requires the following environment variables to be set:

      - GITHUB_USERNAME: Your GitHub username.
      - GITHUB_REPO: The name of the repository.
      - GITHUB_PAT: Your GitHub Personal Access Token for authentication.

    Parameters:
        content (str): The text content to be written into the README.md file.

    Raises:
        ValueError: If any of the required environment variables are missing.
    """
    GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
    REPO_NAME = os.getenv("GITHUB_REPO")
    GITHUB_TOKEN = os.getenv("GITHUB_PAT")

    if not GITHUB_USERNAME or not REPO_NAME or not GITHUB_TOKEN:
        raise ValueError(
            "Missing environment variables: GITHUB_USERNAME, GITHUB_REPO, or GITHUB_PAT"
        )

    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/README.md"

    encoded_content = base64.b64encode(content.encode()).decode()

    with httpx.Client() as client:
        response = client.get(
            GITHUB_API_URL,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        data = response.json()
        sha = data.get("sha", None)

        payload = {
            "message": "Updating README.md",
            "content": encoded_content,
            "branch": "main",
        }

        if sha:
            payload["sha"] = sha

        response = client.put(
            GITHUB_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        if response.status_code in [200, 201]:
            print("README.md successfully uploaded/updated!")
        else:
            print("Failed to upload README.md:", response.json())


def create_files(file_paths) -> str:
    """Create multiple files in a GitHub repository with a predefined content.

    This function iterates over a list of file paths (relative to the repository root) and creates
    each file in the specified GitHub repository with the content "#created by flock". For each file,
    it checks whether the file already exists; if it does, that file is skipped. The function
    uses the following environment variables for authentication and repository information:

      - GITHUB_USERNAME: Your GitHub username.
      - GITHUB_REPO: The name of the repository.
      - GITHUB_PAT: Your GitHub Personal Access Token for authentication.

    Parameters:
        file_paths (list of str): A list of file paths (relative to the repository root) to be created.

    Returns:
        str: A message indicating whether the files were created successfully or if there was a failure.
    """
    try:
        GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
        REPO_NAME = os.getenv("GITHUB_REPO")
        GITHUB_TOKEN = os.getenv("GITHUB_PAT")

        if not GITHUB_USERNAME or not REPO_NAME or not GITHUB_TOKEN:
            raise ValueError(
                "Missing environment variables: GITHUB_USERNAME, GITHUB_REPO, or GITHUB_PAT"
            )

        encoded_content = base64.b64encode(b"#created by flock").decode()

        with httpx.Client() as client:
            for file_path in file_paths:
                GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"

                response = client.get(
                    GITHUB_API_URL,
                    headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )

                data = response.json()
                sha = data.get("sha", None)

                payload = {
                    "message": f"Creating {file_path}",
                    "content": encoded_content,
                    "branch": "main",
                }

                if sha:
                    print(f"Skipping {file_path}, file already exists.")
                    continue

                response = client.put(
                    GITHUB_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )

                if response.status_code in [200, 201]:
                    print(f"{file_path} successfully created!")
                else:
                    print(f"Failed to create {file_path}:", response.json())

        return "Files created successfully."

    except Exception:
        return "Failed to create file. Please try again later."
