import shutil

BASH_PATH: str | None = shutil.which("bash")
SH_PATH: str | None = shutil.which("sh")
PY_PATH: str | None = shutil.which("python")
