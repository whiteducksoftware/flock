from flock.core.interpreter.python_interpreter import PythonInterpreter
from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def code_evaluate_math(expression: str) -> float:
    try:
        result = PythonInterpreter(
            {},
            [
                "os",
                "math",
                "random",
                "datetime",
                "time",
                "string",
                "collections",
                "itertools",
                "functools",
                "typing",
                "enum",
                "json",
                "ast",
            ],
            verbose=True,
        ).execute(expression)
        return result
    except Exception:
        raise


@traced_and_logged
def code_code_eval(python_code: str) -> str:
    """A Python code evaluation tool that executes Python code and returns the result.
    
    The code may not be markdown-escaped with triple backticks.
    It is expected to be a valid Python code snippet that can be executed directly.
    The code is executed in a controlled environment with a limited set of libraries.
    It allows the use of the following libraries:
                "os",
                "math",
                "random",
                "datetime",
                "time",
                "string",
                "collections",
                "itertools",
                "functools",
                "typing",
                "enum",
                "json",
                "ast",
                "numpy",
                "sympy",
                "pandas",
                "httpx",
    """
    try:
        result = PythonInterpreter(
            {},
            [
                "os",
                "math",
                "random",
                "datetime",
                "time",
                "string",
                "collections",
                "itertools",
                "functools",
                "typing",
                "enum",
                "json",
                "ast",
                "numpy",
                "sympy",
                "pandas",
            ],
            verbose=True,
        ).execute(python_code)
        return result
    except Exception:
        raise


@traced_and_logged
def docker_code_execute(python_code: str) -> str:
    """Execute Python code in a sandboxed Docker container."""
    import ast
    import os
    import pathlib
    import platform
    import shutil
    import textwrap
    import uuid

    import docker
    def _auto_print_last_expr(code: str) -> str:
        """If the last top-level statement is a bare expression,
        append a print() so script mode surfaces its value.
        """
        tree = ast.parse(code, mode="exec")
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            # Re-extract the exact source of that expression
            expr_src = textwrap.dedent(
                code.splitlines()[tree.body[-1].lineno - 1]
            )
            code += f"\nprint({expr_src})"
        return code
    # --- 1. Figure out a base directory that exists on this OS ----------
    if platform.system() == "Windows":
        base_dir = pathlib.Path(os.getenv("SANDBOX_BASE_DIR", r"C:\sandboxes"))
    else:  # Linux, macOS, WSL2
        base_dir = pathlib.Path(os.getenv("SANDBOX_BASE_DIR", "/var/sandboxes"))

    base_dir.mkdir(parents=True, exist_ok=True)

    sandbox_id = f"sbox-{uuid.uuid4()}"
    workdir = base_dir / sandbox_id
    workdir.mkdir(parents=True, exist_ok=False)

    # Docker’s HTTP API always wants POSIX‐style paths (“/”, drive letter allowed).
    host_path = workdir.resolve().as_posix()        # e.g. "C:/sandboxes/…"

    client = docker.from_env()
    image = "python:3.12-slim"

    # --- 2. Decide whether we can / should request the gVisor runtime ---
    runtime_args = {}
    if platform.system() != "Windows" and shutil.which("runsc"):
        runtime_args["runtime"] = "runsc"           # gVisor on Linux & macOS

    container = client.containers.run(
        image,
        name=sandbox_id,
        command=["sleep", "infinity"],
        user="65534:65534",                # nobody
        network_mode="none",
        volumes={host_path: {"bind": "/workspace", "mode": "rw"}},
        mem_limit="4g",
        cpu_period=100_000,
        cpu_quota=200_000,                 # 2 vCPU
        security_opt=["no-new-privileges"],
        detach=True,
        **runtime_args,
    )

    try:
        def exec_code(cmd: list[str], timeout: int = 30) -> str:
            exec_id = client.api.exec_create(
                container.id, cmd, workdir="/workspace"
            )["Id"]
            return client.api.exec_start(
                exec_id, stream=False, demux=False, tty=False,
            ).decode()

        # --- 3. Copy code in and execute --------------------------------
        (workdir / "main.py").write_text(_auto_print_last_expr(python_code), encoding="utf-8")
        stdout = exec_code(["python", "main.py"], timeout=30)
        return stdout.strip()

    finally:
        # --- 4. Tear everything down ------------------------------------
        container.remove(force=True)
        shutil.rmtree(workdir, ignore_errors=True)


