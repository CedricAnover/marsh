from marsh import Conveyor, CmdRunDecorator
from marsh.bash import BashFactory
from marsh.processor_functions import print_all_output_streams
from marsh.core.expression import *

# --------------------------------
output_decorator = CmdRunDecorator().add_processor(print_all_output_streams, before=False)

# Instantiate Bash Factory
bash_factory = BashFactory()

# Create Different Conveyors
cmdpipe_pass_1 = Conveyor().add_cmd_runner(output_decorator.decorate(bash_factory.create_cmd_runner("echo 1")))
cmdpipe_pass_2 = Conveyor().add_cmd_runner(output_decorator.decorate(bash_factory.create_cmd_runner("echo 2")))
cmdpipe_fail_1 = Conveyor().add_cmd_runner(output_decorator.decorate(bash_factory.create_cmd_runner("cho 1")))
cmdpipe_fail_2 = Conveyor().add_cmd_runner(output_decorator.decorate(bash_factory.create_cmd_runner("cho 1")))

# Create Commands from Conveyors
cmd_pass_1 = Command(cmdpipe_pass_1)
cmd_pass_2 = Command(cmdpipe_pass_2)
cmd_fail_1 = Command(cmdpipe_fail_1)
cmd_fail_2 = Command(cmdpipe_fail_2)

# Compose the Commands
pass_and_pass = cmd_pass_1 & cmd_pass_2
pass_and_fail = cmd_pass_1 & cmd_fail_1
fail_and_norun = cmd_fail_1 & cmd_pass_1
fail_or_fail = cmd_fail_1 | cmd_fail_2
fail_or_pass = cmd_fail_1 | cmd_pass_1
pass_or_norun = cmd_pass_1 | cmd_fail_1


# The following examples emulates unix syntax for `&&`, `||`, and Redirection (`>`, `>>`).
# command1 && command2
# command1 || command2
# command > file
# command >> file

# ---------------------------------------
# Uncomment the samples below and observe
# ---------------------------------------

# pass_and_pass()  #<-- Print 1 and Raise error
# fail_and_norun()  #<-- Raise error
# fail_or_fail()  #<-- Raise error
# fail_or_pass()  #<-- Print Error and Print 1
# pass_or_norun()  #<-- Print 1

# cmd_pass_1 > "results.txt"  # Overwrite
# cmd_pass_2 >> "results.txt"  # Append
