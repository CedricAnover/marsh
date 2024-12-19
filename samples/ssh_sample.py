"""
Important: This sample script can only run if you have Docker and Sysbox installed in your machine!!!
"""
import time

from marsh.processor_functions.printers import print_all_output_streams
from marsh.bash import BashFactory
from marsh.ssh import SshFactory
from marsh import (
    Conveyor,
    CmdRunDecorator,
)

# Setup Sysbox Container for SSH
output_stream_printer = CmdRunDecorator().add_processor(print_all_output_streams, before=False)
proc_func_print = CmdRunDecorator().add_processor(lambda stdout, _: print(stdout.decode().strip()), before=False)
stderr_printer = CmdRunDecorator().add_processor(lambda _, stderr: print(stderr.decode().strip()), before=False)
proc_sleeper = CmdRunDecorator().add_processor(lambda x, y: time.sleep(3), before=False)
script_create_container = r"""
docker run --runtime=sysbox-runc -it -d --rm \
    -p=127.0.0.1:2222:22 \
    --hostname=sysbox-jammy-host \
    --name=sysbox-jammy-container \
    cedricanover94/sysbox-jammy:latest
"""
bash_factory = BashFactory()
create_container = proc_sleeper.decorate(bash_factory.create_cmd_runner(script_create_container))
kill_container = bash_factory.create_cmd_runner("docker kill sysbox-jammy-container")

# Create a dummy command runner for simulating unix pipes
def dummy_cmd_runner(x_stdout: bytes, x_stderr: bytes, message: str) -> tuple[bytes, bytes]:
    return message.encode(), x_stderr

# Instantiate SSH Factory for creating command runners
# Note: Using Sysbox Container from https://github.com/CedricAnover/Sysbox-Development-Workstation
ssh_factory = SshFactory(
    fabric_config=None,
    connection_args=("developer@127.0.0.1:2222",),
    connection_kwargs=dict(connect_kwargs={"password": "developer"}),
)

try:
    # Run the Conveyor
    conveyor = Conveyor()\
        .add_cmd_runner(create_container)\
        .add_cmd_runner(dummy_cmd_runner, "line1\nline2\nline3")\
        .add_cmd_runner(ssh_factory.create_cmd_runner(["grep 2"], pipe_prev_stdout=True), cmd_runner_decorator=output_stream_printer)\
        .add_cmd_runner(ssh_factory.create_chained_cmd_runner(["echo Hello", "echo World"]), cmd_runner_decorator=output_stream_printer)

    conveyor()
except Exception as e:
    print(e)
finally:
    # Kill Container
    container_killer = Conveyor().add_cmd_runner(kill_container, cmd_runner_decorator=output_stream_printer)
    container_killer()
