# Marsh

**Marsh** is a lightweight Python library for building, managing, and executing command workflows. It allows chaining commands, defining custom pre/post processing logic, and structuring flexible CLI workflows. With support for local, remote, Docker-based, and Python expression execution, Marsh simplifies automating pipelines and integrating external processes.

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
- **Execution Options:** Local, remote (via SSH), Docker, and custom runners.

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

def validate(stdout, stderr): assert not stderr.strip()  # Validate no errors
def log(stdout, stderr): print(f"LOG: {stdout.decode()}")  # Log output

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
cmd1 = bash.create_cmd_runner(r'echo "($ENV_VAR_1, $ENV_VAR_2)"', env={"ENV_VAR_1": "value1", "ENV_VAR_2": "value2"})

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
