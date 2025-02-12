"""This module provides tools for interacting with GitHub repositories."""

import base64
import os

import httpx

from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def create_user_stories_as_github_issue(title: str, body: str) -> str:
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


@traced_and_logged
def upload_readme(content: str):
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


@traced_and_logged
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
