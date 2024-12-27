import time

from marsh.docker.docker_executor import (
    DockerCommandExecutor,
    DockerContainer
)

#===============================================================
# Example: DockerContainer
with DockerContainer("cedricanover94/sysbox-jammy:latest",
                     timeout=10,
                     runtime="sysbox-runc",
                     hostname="sysbox-host",
                     ) as container:
    time.sleep(2)  # wait for sysbox init

    result = container.exec_run(
        ["bash", "-c",
         'echo "Message: Hello World" && echo "CWD: $(pwd)" && echo "USER: $(whoami)" && echo "HOST: $(hostname)"'
         ],
        user="developer",
        workdir="/home/developer",
    )

    if result.exit_code == 0:
        print(result.output.decode().strip())
    if result.exit_code > 0:
        print(result.output.decode().strip())

#===============================================================
# Example: DockerCommandExecutor
print("=" * 70)
dock = DockerCommandExecutor(
    "bash:latest",
    timeout=5,
    pipe_prev_stdout=False,
    working_dir="/app",
)

stdout, stderr = dock.run(
    b"", b"",
    ["bash", "-c", "echo Hello World && echo $(pwd) && echo $ENV_VAR_1"],
    environment=dict(ENV_VAR_1="value1"),
    workdir="/app"
)

if stdout.strip():
    stdout_str = stdout.decode().strip()
    print(stdout_str)

if stderr.strip():
    stderr_str = stderr.decode().strip()
    print(stderr_str)
