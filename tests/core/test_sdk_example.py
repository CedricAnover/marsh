import runpy
from pathlib import Path


def test_workflow_ir_sample_runs_end_to_end(capsys):
    sample = Path(__file__).parents[2] / "samples" / "workflow_ir_sample.py"

    runpy.run_path(str(sample), run_name="__main__")

    output = capsys.readouterr().out
    assert "workflow: example" in output
    assert "task: greet" in output
    assert "hello from Marsh" in output
