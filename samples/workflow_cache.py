"""Reuse a successful ProcessSpec result with an in-memory cache."""

import sys

from marsh import CachePolicy, ExecutionPolicy, MemoryCache, ProcessSpec, Task, Workflow, execute_workflow


workflow = Workflow(
    id="cache-demo",
    tasks=(
        Task(
            id="cached",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('computed once')"),
            ),
        ),
    ),
)

cache = MemoryCache()
policy = ExecutionPolicy(cache=CachePolicy(enabled=True, namespace="sample"))

first = execute_workflow(workflow, policy=policy, cache=cache)["cached"]
second = execute_workflow(workflow, policy=policy, cache=cache)["cached"]

if not first.ok or not second.ok:
    raise RuntimeError(first.error or second.error)

print("first:", first.stdout.decode().strip())
print("second:", second.stdout.decode().strip())
print("same result:", first == second)
