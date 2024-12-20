# Marsh

Marsh is a lightweight, extensible Python library for building, managing, and executing command workflows. It allows
users to chain multiple commands, define custom pre/post processing logic, and create flexible command grammars to
structure CLI commands. With built-in support for local execution and an API for extending to remote, Docker-based, or
Python expression execution, it simplifies automating workflows and integrating external processes. Whether you’re
running shell commands, orchestrating pipelines, or customizing execution flows, Marsh provides a powerful and
declarative way to streamline command management.

---

## Basic Usage Examples

### Creating Custom Command Runner Functions and Conveyor

```python
from marsh import Conveyor


def my_cmd_runner_1(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
    # ... Do something ...
    return x_stdout, x_stderr


def my_cmd_runner_2(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
    # ... Do something ...
    return x_stdout, x_stderr


# Create a Conveyor (To linearly chain the command runners)
conveyor = Conveyor()\
    .add_cmd_runner(my_cmd_runner_1)\
    .add_cmd_runner(my_cmd_runner_2)

# Run the Conveyor
res_stdout, res_stderr = conveyor(x_stdout=b"demo-stdout", x_stderr=b"demo-stderr")
print("Result stdout:", res_stdout)
print("Result stderr:", res_stderr)
```

**Result**

```text
Result stdout: b'demo-stdout'
Result stderr: b'demo-stderr'
```

The main use-case of `Conveyor` is to encapsulate a chain of _command runners_ into one callable object that can be
composed and reused.

### Decorating Command Runners with Pre/Post Processors

The above sample is nice but there may be some tasks that needs to be done before or after evaluating the command runner
functions.

For example: custom validation logic before passing the previous command runner's `(stdout, stderr)`,
printing or logging the result of the command runner, validating and/or raising error if the command runner's
result is invalid, etc. These are **_Pre/Post Processors_**. The signature is `(bytes, bytes, ...) => None`.

```python
def proc_func_1(x_stdout: bytes, x_stderr: bytes) -> None:
    if x_stderr.strip():
        # ... Do some validation ...
        print("Raising Error:", x_stderr.decode().strip())

def proc_func_2(x_stdout: bytes, x_stderr: bytes) -> None:
    if x_stdout.strip():
        # ... Log or Print ...
        print("STDOUT:", x_stdout.decode().strip())
```

There are few approaches to apply these **_processor_** functions to a command runner:

1. Using `CmdRunDecorator` class
    ```python
    from marsh import CmdRunDecorator
    
    cmd_run_decorator = CmdRunDecorator()\
        .add_processor(proc_func_1, before=True)\
        .add_processor(proc_func_2, before=False)
    
    def my_cmd_runner(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
        # ... Do something ...
        return x_stdout, x_stderr
    
    decorated_cmd_runner = cmd_run_decorator.decorate(my_cmd_runner)
    stdout, stderr = decorated_cmd_runner(b"Hello", b"World")
    ```

2. Using `@add_processors_and_modifiers` to a command runner function
    ```python
    from marsh import add_processors_and_modifiers
    
    @add_processors_and_modifiers(
        ("proc", True, proc_func_1),
        ("proc", False, proc_func_2),
    )
    def my_cmd_runner(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
        # ... Do something ...
        return x_stdout, x_stderr
    
    stdout, stderr = my_cmd_runner(b"Hello", b"World")
    ```

3. Passing a `CmdRunDecorator` object to `cmd_runner_decorator` parameter of `Conveyor().add_cmd_runner` method.

    ```python
    cmd_run_decorator = CmdRunDecorator()\
        .add_processor(proc_func_1, before=True)\
        .add_processor(proc_func_2, before=False)
    
    conveyor = Conveyor().add_cmd_runner(cmd_runner, cmd_runner_decorator=cmd_run_decorator)
    ```
    This would automatically use the `decorate()` method to decorate the registered command runner.

### Decorating Command Runners with Pre/Post Modifiers

**_Modifiers_** are similar to processors but can transform data before or after the command runner. _Modifier_ follows
the signature: `(bytes, bytes, ...) => (bytes, bytes)`. The main use-case is ETL for Data Transformations. Note that
_Modifiers_ are more general than _Processors_, but has the strict requirement of returning `tuple[bytes, bytes]`.

**Registering to `CmdRunDecorator`:**
```python
from marsh import CmdRunDecorator

cmd_run_decorator = CmdRunDecorator()\
    .add_mod_processor(mod_func_1, before=True)\
    .add_mod_processor(mod_func_2, before=False)

decorated_cmd_runner = cmd_run_decorator.decorate(cmd_runner)
```

**Using `@add_processors_and_modifiers`:**
```python
from marsh import add_processors_and_modifiers

@add_processors_and_modifiers(
    ("mod", True, mod_func_1),
    ("mod", False, mod_func_2),
)
def my_cmd_runner(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
    # ... Do something ...
    return x_stdout, x_stderr
```

⚠️ **IMPORTANT:**  
> **Order of Evaluation for Processors and Modifiers**
> 
> 1. **Pre-Modifiers**  
> 2. **Pre-Processors**  
> 3. **Command Runner**  
> 4. **Post-Modifiers**  
> 5. **Post-Processors**  


### Running local commands with `BashFactory`

```python
import subprocess
from pathlib import Path

from marsh import Conveyor, CmdRunDecorator
from marsh.bash import BashFactory

# Create Custom Post-Processor for Printing STDOUT Result
proc_func_print = CmdRunDecorator()\
    .add_processor(lambda stdout, _: print(stdout.decode().strip()), before=False)

# Create a Bash Factory
bash_factory = BashFactory()

#=============== Example: Injecting Environment Variables
cmd_runner_1 = bash_factory.create_cmd_runner(r'echo "($ENV_VAR_1, $ENV_VAR_2)"', env=dict(ENV_VAR_1="value1", ENV_VAR_2="value2"))
decorated_cmd_runner_1 = proc_func_print.decorate(cmd_runner_1)

#=============== Example: Change Work Directory
cmd_runner_2 = bash_factory.create_cmd_runner(r'echo "CWD: $PWD"', cwd=str(Path.cwd().parent))
decorated_cmd_runner_2 = proc_func_print.decorate(cmd_runner_2)

#=============== Example: Unix Pipes
# STDOUT as STDIN for next command runner
cmd_runner_3 = bash_factory.create_cmd_runner(r'echo -e "Line24\\nLine22\\nLine25\\nLine55"')
# Add pipe_prev_stdout=True
cmd_runner_4 = bash_factory.create_cmd_runner(r'grep 2 | sort', executor_kwargs=dict(pipe_prev_stdout=True))

#=============== Example: Calling Python Interpreter
cmd_runner_5 = bash_factory.create_cmd_runner(r'python -c "print(\"Hello Python\")"')

#=============== Example: Running with Custom Callback that takes subprocess.Popen as parameter
def custom_callback(popen: subprocess.Popen, x_stdout, x_stderr):
    return popen.communicate(input=b"... stdin for xargs echo ...")
cmd_runner_6 = bash_factory.create_cmd_runner(r'xargs echo', callback=custom_callback)

# Create Conveyor and Run
coveyor = Conveyor()\
    .add_cmd_runner(decorated_cmd_runner_1)\
    .add_cmd_runner(decorated_cmd_runner_2)\
    .add_cmd_runner(cmd_runner_3)\
    .add_cmd_runner(cmd_runner_4, cmd_runner_decorator=proc_func_print)\
    .add_cmd_runner(cmd_runner_5, cmd_runner_decorator=proc_func_print)\
    .add_cmd_runner(cmd_runner_6, cmd_runner_decorator=proc_func_print)\
    .add_cmd_runner(bash_factory.create_cmd_runner(r'echo $ANOTHER_VAR'),
                    cmd_runner_decorator=proc_func_print,
                    env=dict(ANOTHER_VAR="another-var-value"))

coveyor()
```

**Output:**

```text
(value1, value2)
CWD: /path/to/some/directory
Line22
Line24
Line25
Hello Python
... stdin for xargs echo ...
another-var-value
```


### Running remote commands with `SshFactory`

**Note:** The following uses _Sysbox_ for demonstrating SSH with System Containers.

```python
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

# Instantiate SSH Factory
# Note: Using Sysbox Container from https://github.com/CedricAnover/Sysbox-Development-Workstation
ssh_factory = SshFactory(
    fabric_config=None,
    connection_args=("developer@127.0.0.1:2222",),
    connection_kwargs=dict(connect_kwargs={"password": "developer"}),
)

try:
    # Create Command Runners with `BashFactory.create_cmd_runner` and `BashFactory.create_chained_cmd_runner`
    remote_cmd_runner_1 = ssh_factory.create_cmd_runner(["grep 2"], pipe_prev_stdout=True)
    remote_cmd_runner_2 = ssh_factory.create_chained_cmd_runner(["echo Hello", "echo World"])

    # Create a Conveyor
    conveyor = Conveyor()\
        .add_cmd_runner(create_container)\
        .add_cmd_runner(dummy_cmd_runner, "line1\nline2\nline3")\
        .add_cmd_runner(remote_cmd_runner_1, cmd_runner_decorator=output_stream_printer)\
        .add_cmd_runner(remote_cmd_runner_2, cmd_runner_decorator=output_stream_printer)

    # Run the Conveyor
    conveyor()
except Exception as e:
    print(e)
finally:
    # Kill Container
    container_killer = Conveyor().add_cmd_runner(kill_container, cmd_runner_decorator=output_stream_printer)
    container_killer()
```

The components behind `SshFactory` uses [**_fabric_**](https://github.com/fabric/fabric).
