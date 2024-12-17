import sys
import os
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.append(str(src_path))

from marsh.core.script import *

#-----------------------------------------------------------------
bash_ifelifelse_stmt = BashIfElifElseStatement()
bash_ifelifelse_stmt.add_if("condition1", "statement1")
bash_ifelifelse_stmt.add_elif("condition2", "statement2")
bash_ifelifelse_stmt.add_elif("condition3", "statement3")
bash_ifelifelse_stmt.add_elif("condition4", "statement4")
bash_ifelifelse_stmt.add_else("last_statement")
result = bash_ifelifelse_stmt.generate()
# print(result)
#-----------------------------------------------------------------
bash_export_envvar = BashExportEnvVarStatement()
result = bash_export_envvar.generate("env_var_1", "value1")
# print(result)
#-----------------------------------------------------------------
bash_cases = BashCaseStatement()
bash_cases.add_case("pattern1", "statement1")
bash_cases.add_case("pattern2", "statement2")
bash_cases.add_case("pattern3", "statement3")
result = bash_cases.generate("my_expr")
# print(result)
#-----------------------------------------------------------------
bash_script = BashScript()
result = bash_script.generate_from_statements(
    bash_export_envvar.generate("env_var_1", "value1"),
    bash_cases.generate("my_expr"),
    bash_ifelifelse_stmt.generate(),
    "echo 1",
    "echo 2",
    "echo 3",
)
print(result)
#-----------------------------------------------------------------
result = bash_script.generate("echo Hello World")
# print(result)
#-----------------------------------------------------------------
