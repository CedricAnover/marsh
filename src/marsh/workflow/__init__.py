"""Modern Workflow domain and authoring boundary."""

from marsh.core.configuration import TaskConfig, WorkflowConfig, normalize_workflow
from marsh.core.diagnostics import Diagnostic
from marsh.core.domain import ProcessStatus, Result, Task, Workflow
from marsh.core.validation import validate_workflow_diagnostics

__all__ = ["Diagnostic","ProcessStatus","Result","Task","TaskConfig","Workflow","WorkflowConfig","normalize_workflow","validate_workflow_diagnostics"]
