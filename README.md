# Marsh

**Marsh** is a lightweight Python library for building, managing, and executing command workflows. It allows chaining
commands, defining custom pre/post processing logic, creating DAG workflows, and structuring flexible CLI workflows.
With support for local, remote, Docker-based, and Python execution, Marsh simplifies automating pipelines and
integrating external processes.

---

## Installation

Install Marsh via pip:
```text
pip install marsh-lib
```

---

## Key Features

- **Command Chains:** Chain multiple commands into reusable workflows.
- **Pre/Post Processors:** Add validation, logging, or error handling without modifying data.
- **Pre/Post Modifiers:** Transform input/output data during command execution.
- **Execution Options:** Local, Remote, Docker, Python, and custom runners.
- **DAG Workflows:** Support for DAG to define and run task dependencies.

---

## Quick Start

### Workflow with `Conveyor`

```python
from marsh import Conveyor

def cmd_1(stdout, stderr): return stdout.upper(), stderr
def cmd_2(stdout, stderr): return stdout, stderr.lower()

# Chain commands with Conveyor
conveyor = Conveyor().add_cmd_runner(cmd_1).add_cmd_runner(cmd_2)
stdout, stderr = conveyor(b"input", b"ERROR")
print(stdout, stderr)
```

**Output:**  
```text
INPUT error
```

---

### Pre/Post Processors: Validating or Logging Data

**Processors** perform actions (e.g., logging, validation) without modifying data.

```python
from marsh import CmdRunDecorator

def validate(stdout, stderr): assert not stderr.strip()      # Validate no errors
def log(stdout, stderr): print(f"LOG: {stdout.decode()}")    # Log output

decorator = CmdRunDecorator().add_processor(validate, before=True).add_processor(log, before=False)

def cmd_runner(stdout, stderr): return stdout, stderr
decorated_runner = decorator.decorate(cmd_runner)
stdout, stderr = decorated_runner(b"Hello", b"")
```

**Output:**  
```text
LOG: Hello
```

---

### Pre/Post Modifiers: Transforming Data

**Modifiers** transform the data before or after a command runs. Unlike processors, modifiers must return `(stdout, stderr)`.

```python
def to_upper(stdout, stderr): return stdout.upper(), stderr
def add_prefix(stdout, stderr): return b"Prefix: " + stdout, stderr

decorator = CmdRunDecorator().add_mod_processor(to_upper, before=True).add_mod_processor(add_prefix, before=False)

def cmd_runner(stdout, stderr): return stdout, stderr
decorated_runner = decorator.decorate(cmd_runner)
stdout, stderr = decorated_runner(b"hello", b"")
print(stdout.decode())
```

**Output:**  
```text
Prefix: HELLO
```

**Key Difference:**  
- **Processors** act on data without altering it.  
- **Modifiers** transform the data and return new values.

⚠️ **IMPORTANT:**  
> **Order of Evaluation for Processors and Modifiers**
> 
> 1. **Pre-Modifiers**  
> 2. **Pre-Processors**  
> 3. **Command Runner**  
> 4. **Post-Modifiers**  
> 5. **Post-Processors**  

---

### Using `@add_processors_and_modifiers` for decorating command runners

```python
from marsh import add_processors_and_modifiers


@add_processors_and_modifiers(
    ("mod", True, pre_mod_func, arg_tuple, kwg_dict),      # Pre-Modifier
    ("proc", True, pre_proc_func, arg_tuple, kwg_dict),    # Pre-Processor
    ("mod", False, post_mod_func, arg_tuple, kwg_dict),    # Post-Modifier
    ("proc", False, post_proc_func, arg_tuple, kwg_dict),  # Post-Processor
)
def cmd_runner(x_stdout: bytes, x_stderr: bytes):
    ...
    return b"stdout", b"stderr"
```

---

### Running Local Commands with `BashFactory`

#### Simple Local Command
```python
from marsh.bash import BashFactory

bash = BashFactory()
cmd = bash.create_cmd_runner(r'echo "Hello, $NAME"', env={"NAME": "World"})
stdout, stderr = cmd(b"", b"")
```

#### Examples with `BashFactory`
```python
from pathlib import Path
from marsh.bash import BashFactory

bash = BashFactory()

# Inject Environment Variables
cmd1 = bash.create_cmd_runner(
    r'echo "($ENV_VAR_1, $ENV_VAR_2)"',
    env={
        "ENV_VAR_1": "value1",
        "ENV_VAR_2": "value2"
    }
)

# Change Working Directory
cmd2 = bash.create_cmd_runner(r'echo "CWD: $PWD"', cwd=str(Path.cwd().parent))

# Unix Pipes
cmd3 = bash.create_cmd_runner(r'echo -e "Line1\nLine2\nLine3"')
cmd4 = bash.create_cmd_runner(r'grep 2 | sort', executor_kwargs={"pipe_prev_stdout": True})

# Python Command
cmd5 = bash.create_cmd_runner(r'python -c "print(\"Hello Python\")"')

# Custom Callback
import subprocess
def custom_callback(popen: subprocess.Popen, stdout, stderr):
    return popen.communicate(input=b"Custom Input")
cmd6 = bash.create_cmd_runner(r'xargs echo', callback=custom_callback)

# Combine in Conveyor
from marsh import Conveyor
conveyor = Conveyor()\
    .add_cmd_runner(cmd1)\
    .add_cmd_runner(cmd2)\
    .add_cmd_runner(cmd3)\
    .add_cmd_runner(cmd4)\
    .add_cmd_runner(cmd5)\
    .add_cmd_runner(cmd6)

stdout, stderr = conveyor()
```

---

### Running Remote Commands with `SshFactory`

```python
from marsh import Conveyor
from marsh.ssh import SshFactory

ssh = SshFactory(("user@host:port",), {"connect_kwargs": {"password": "the_ssh_password"}})
cmd1 = ssh.create_cmd_runner("echo Hello, Remote World")
cmd2 = ssh.create_chained_cmd_runner(["echo Hi", "echo there"])
conveyor = Conveyor().add_cmd_runner(cmd1).add_cmd_runner(cmd2)
stdout, stderr = conveyor()
```

---

### Running Commands with `DockerCommandExecutor`

```python
from marsh.docker.docker_executor import DockerCommandExecutor

docker_executor = DockerCommandExecutor("bash:latest", ...)

stdout, stderr = docker_executor.run(
    b"x_stdout", b"x_stderr",
    environment=dict(ENV_VAR_1="value1", ENV_VAR_2="value2"),
    workdir="/app"
)
```

---

### Running Commands with `PythonExecutor`

#### `eval` mode for evaluating python expressions

```python
from marsh import PythonExecutor

py_code = """x + y"""     # Python Evaluatable Expression

python_executor = PythonExecutor(
    py_code,
    mode="eval",
    namespace=dict(x=1, y=2),
    use_pickle=False,
)

stdout, stderr = python_executor.run(b"x_stdout", b"x_stderr", ...)

```

#### `exec` mode for executing python statements

```python
from marsh import PythonExecutor

py_code = """
import os
import sys

prev_stdout = x_stdout    #<-- Use `x_stdout` to get the previous STDOUT
prev_stderr = x_stderr    #<-- Use `x_stderr` to get the previous STDERR
exec_result = x + y       #<-- Use `exec_result` for storing results and passing to STDOUT
"""

python_executor = PythonExecutor(
    py_code,
    mode="exec",
    namespace=dict(x=1, y=2),
    use_pickle=False,
)

stdout, stderr = python_executor.run(b"x_stdout", b"x_stderr", ...)

```

**Note:** `eval` mode also have access to `x_stdout` and `x_stderr` but not `exec_result`.

---

### DAG Workflow

The DAG extends the capabilities of the core components by allowing non-linear dependencies between tasks.

The DAG subpackage has two main components: `Node` and `Dag`. The `Node` encapsulates a `Conveyor` that represents a
_task_ in the workflow, while the `Dag` represents the whole workflow and task dependencies.

Note that the `Dag` manages `Startable` objects, which is the abstract base class for both `Node` and `Dag`. This means
that a `Dag` can contain both `Node` objects and other `Dag` objects.

**Different kinds of `Dag`'s:**

- `SyncDag`
- `AsyncDag`
- `ThreadDag`
- `ThreadPoolDag`
- `MultiprocessDag`
- `ProcessPoolDag`

#### Defining Nodes

```python
from marsh import Conveyor
from marsh.dag import Node

conveyor = Conveyor().add_cmd_runner(cmd_runner, ...)
node = Node("node_name", conveyor, **run_kwargs)
```

#### Defining and Running a Dag

```python
from marsh.dag import SyncDag

dag = SyncDag("dag_name")

# Register Nodes
dag.do(node_a)
dag.do(node_a).then(node_b, node_c)       # A --> {B, C}
dag.do(node_a).when(node_b, node_c)       # {B, C} --> A
dag.do(other_dag).then(node_a)            # Register other Dag
...

result_dict = dag.start()                 # Run the Dag
result = result_dict["node_or_dag_name"]  # Get result from individual startables
```

⚠️ **IMPORTANT:**

- `MultiprocessDag` and `ProcessPoolDag` requires the `start()` method to run in scope of `if __name__ == "__main__"`.
    ```python
    from marsh.dag import MultiprocessDag, ProcessPoolDag
    
    ...
    
    if __name__ == "__main__":
        ...
        dag.start()
        ...
    ```
- As of the latest version, marsh DAG does not support **_result passing_** between task dependencies.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
