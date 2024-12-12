import random

from marsh import (
    Conveyor,
    CmdRunDecorator,
    add_processors_and_modifiers
)
from marsh.bash import BashFactory


# Simulated Storage
log_storage = {
    "stdout": [],
    "stderr": []
}

# Instantiate Factory for creating bash command runners
bash_factory = BashFactory()

# Define Custom Modifiers and Processors
def proc_func_logger(stdout: bytes, stderr: bytes):
    global log_storage
    if stdout.strip():
        log_storage["stdout"].append(stdout.decode().strip())
    if stderr.strip():
        log_storage["stderr"].append(stderr.decode().strip())

def proc_func_printer(stdout: bytes, stderr: bytes):
    if stdout.strip():
        print(stdout.decode().strip())
    if stderr.strip():
        print(stderr.decode().strip())

def proc_func_validator(stdout, stderr):
    if not isinstance(stdout, bytes) or not isinstance(stderr, bytes):
        raise TypeError("Output streams must be bytes.")

def mod_func_2_msg(stdout, stderr, msg1: str, msg2: str):  # Required Parameters for Modifiers and Processors
    assert isinstance(msg1, str) and isinstance(msg2, str)
    return (msg1 + " " + msg2).encode(), stderr

def mod_func_upper(stdout: bytes, stderr: bytes):  # Simulates ETL
    return stdout.upper(), stderr.upper()

def mod_func_lower(stdout: bytes, stderr: bytes):  # Simulates ETL
    stdout_lower, stderr_lower = stdout.lower(), stderr.lower()
    return stdout_lower, stderr_lower

def proc_func_rand_int(x_stdout, x_stderr, max_int=100):  # Optional Parameters for Modifiers and Processors
    rnd_int = random.randint(1, max_int)
    print("Random Integer:", rnd_int)


# Create a custom command runner decorator which can be passed to the optional parameter 
# `cmd_runner_decorator` from Conveyor.add_cmd_runner()
post_decor_rand_int_and_print = \
    CmdRunDecorator()\
        .add_processor(proc_func_rand_int, before=False, proc_kwargs=dict(max_int=3))\
        .add_processor(proc_func_printer, before=False)
# This can be used to create a decorated command runner.
# Generic Usage Example:
# decorated_cmd_runner = CmdRunDecorator().add_mod_processor(...).add_processor(...).decorate(cmd_runner)
# decorated_cmd_runner(b"<bytes>", b"<bytes>", ...)


# Example 1: Using @add_processors_and_modifiers for decorating command runners with proc_func and mod_func
@add_processors_and_modifiers(
    ("mod", True, mod_func_2_msg, ("Hello", "World")),  # Pre-Modifier
    ("proc", True, proc_func_validator),  # Pre-Processor
    ("mod", False, mod_func_lower),  # Post-Modifier
    ("proc", False, proc_func_printer),  # Post-Processor
    ("proc", False, proc_func_logger),  # Post-Processor
)
def my_custom_cmd_runner(x_stdout: bytes, x_stderr: bytes):
    print("Running my_custom_cmd_runner() ...")
    return x_stdout, b"Error"


# Example 2: Using CmdRunDecorator for decorating command runners with proc_func and mod_func
cmd_run_decorator = CmdRunDecorator()
cmd_run_decorator.add_processor(proc_func_validator, before=True)  # Pre-Processor
cmd_run_decorator.add_mod_processor(mod_func_upper, before=False)  # Post-Modifier
cmd_run_decorator.add_processor(proc_func_logger, before=False)  # Post-Processor
cmd_run_decorator.add_processor(proc_func_printer, before=False)  # Post-Processor
# Decorate a Bash Runner with processors and modifiers
decorated_bash_runner = cmd_run_decorator.decorate(bash_factory.create_cmd_runner("echo 'Running Command with Bash ...'"))


# Chain all the command runners using Conveyor
conveyor = Conveyor()\
    .add_cmd_runner(my_custom_cmd_runner)\
    .add_cmd_runner(decorated_bash_runner)\
    .add_cmd_runner(
        bash_factory.create_cmd_runner("echo terraform init && echo $ENV_VAR_1",
                                       env=dict(
                                           ENV_VAR_1="env_var_1_value"  #<-- Inject Environment Variables to Bash Command Runner (for subprocess.Popen)
                                           )
                                       ),
        cmd_runner_decorator=post_decor_rand_int_and_print  #<-- We can optionally add a command runner decorator in Conveyor.add_cmd_runner
    )

conveyor()


# Investigate the result_storage
print("=" * 70, "\n")
print("STDOUT\n------")
for stdout_result in log_storage["stdout"]:
    print(stdout_result)
print()
print("STDERR\n------")
for stderr_result in log_storage["stderr"]:
    print(stderr_result)
