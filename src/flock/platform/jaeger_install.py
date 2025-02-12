import socket
import subprocess
from urllib.parse import urlparse


class JaegerInstaller:
    jaeger_endpoint: str = None
    jaeger_transport: str = "grpc"

    def _check_jaeger_running(self):
        """Check if Jaeger is reachable by attempting a socket connection.
        For HTTP transport, we parse the URL; for gRPC, we expect "host:port".
        """
        try:
            if self.jaeger_transport == "grpc":
                host, port = self.jaeger_endpoint.split(":")
                port = int(port)
            elif self.jaeger_transport == "http":
                parsed = urlparse(self.jaeger_endpoint)
                host = parsed.hostname
                port = parsed.port if parsed.port else 80
            else:
                return False

            # Try connecting to the host and port.
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            return False

    def _is_jaeger_container_running(self):
        """Check if a Jaeger container (using the official all-in-one image) is running.
        This uses 'docker ps' to filter for containers running the Jaeger image.
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "ancestor=jaegertracing/all-in-one:latest",
                    "--format",
                    "{{.ID}}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _provision_jaeger_container(self):
        """Provision a Jaeger container using Docker."""
        try:
            print("Provisioning Jaeger container using Docker...")
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    "jaeger",
                    "-p",
                    "16686:16686",
                    "-p",
                    "14250:14250",
                    "-p",
                    "14268:14268",
                    "jaegertracing/all-in-one:latest",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                print("Jaeger container started successfully.")
                return True
            else:
                print(
                    f"Failed to start Jaeger container. Error: {result.stderr}"
                )
                return False
        except Exception as e:
            print(f"Exception when provisioning Jaeger container: {e}")
            return False
