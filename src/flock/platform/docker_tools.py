import subprocess
import time


def _check_docker_running():
    """Check if Docker is running by calling 'docker info'."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _start_docker():
    """Attempt to start Docker.
    This example first tries 'systemctl start docker' and then 'service docker start'.
    Adjust as needed for your environment.
    """
    try:
        print("Attempting to start Docker...")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "docker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["sudo", "service", "docker", "start"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        # Give Docker a moment to start.
        time.sleep(3)
        if _check_docker_running():
            print("Docker is now running.")
            return True
        else:
            print("Docker did not start successfully.")
            return False
    except Exception as e:
        print(f"Exception when trying to start Docker: {e}")
        return False
