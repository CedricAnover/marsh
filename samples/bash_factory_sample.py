import subprocess
from pathlib import Path

from marsh import Conveyor, CmdRunDecorator
from marsh.bash import BashFactory

# Create Custom Post-Processor for Printing STDOUT Result
proc_func_print = CmdRunDecorator().add_processor(lambda stdout, _: print(stdout.decode().strip()), before=False)

# Create a Bash Factory
bash_factory = BashFactory()

# Example: Injecting Environment Variables
cmd_runner_1 = bash_factory.create_cmd_runner(r'echo "($ENV_VAR_1, $ENV_VAR_2)"', env=dict(ENV_VAR_1="value1", ENV_VAR_2="value2"))
decorated_cmd_runner_1 = proc_func_print.decorate(cmd_runner_1)

# Example: Change Work Directory
cmd_runner_2 = bash_factory.create_cmd_runner(r'echo "CWD: $PWD"', cwd=str(Path.cwd().parent))
decorated_cmd_runner_2 = proc_func_print.decorate(cmd_runner_2)

# Example: Unix Pipes
cmd_runner_3 = bash_factory.create_cmd_runner(r'echo -e "Line24\\nLine22\\nLine25\\nLine55"')  # STDOUT as STDIN for next command runner
cmd_runner_4 = bash_factory.create_cmd_runner(r'grep 2 | sort', executor_kwargs=dict(pipe_prev_stdout=True))  # Add pipe_prev_stdout=True

# Example: Calling Python Interpreter
cmd_runner_5 = bash_factory.create_cmd_runner(r'python -c "print(\"Hello Python\")"')

# Example: Running with Custom Callback that takes subprocess.Popen as parameter
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
