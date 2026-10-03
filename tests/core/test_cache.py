from marsh.core.cache import CachePolicy, MemoryCache, cache_key_for_task
from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Task


def test_cache_key_is_deterministic_for_equivalent_task_definitions():
    left = Task(
        id="task",
        operation=ProcessSpec(executable="python", arguments=("-c", "print('ok')")),
        inputs={"b": 2, "a": 1},
    )
    right = Task(
        id="task",
        operation=ProcessSpec(executable="python", arguments=("-c", "print('ok')")),
        inputs={"a": 1, "b": 2},
    )

    assert cache_key_for_task(left, {}) == cache_key_for_task(right, {})


def test_cache_is_opt_in_and_preserves_structured_result():
    policy = CachePolicy(enabled=True)
    cache = MemoryCache()
    result = Result(stdout=b"ok", status=ProcessStatus.COMPLETED)

    assert policy.enabled
    key = cache_key_for_task(
        Task(id="task", operation=ProcessSpec(executable="python")),
        {},
        namespace=policy.namespace,
    )
    cache.put(key, result)

    assert cache.get(key) == result


def test_callable_operations_are_not_cacheable():
    task = Task(id="task", operation=lambda *_: Result())
    assert cache_key_for_task(task, {}) is None
