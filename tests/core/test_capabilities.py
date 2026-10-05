from marsh.core.providers import (
    CapabilityRequirement,
    LocalProvider,
    ProviderRegistry,
)


def test_capability_requirement_normalizes_deterministically():
    requirement = CapabilityRequirement([" process.wait ", "process.start"])
    assert requirement.required == frozenset({"process.wait", "process.start"})


def test_capability_negotiation_reports_missing_without_mutation():
    registry = ProviderRegistry({"local": LocalProvider()})

    match = registry.negotiate("local", ["process.wait", "process.stream"])

    assert match.provider == "local"
    assert match.required == frozenset({"process.wait", "process.stream"})
    assert "process.stream" in match.missing
    assert match.satisfied is False
    assert registry.get("local") is not None


def test_capability_negotiation_is_explicit_for_unknown_provider():
    registry = ProviderRegistry({"local": LocalProvider()})

    match = registry.negotiate("missing", ["process.wait"])

    assert match.provider == "missing"
    assert match.available == frozenset()
    assert match.missing == frozenset({"process.wait"})
    assert match.satisfied is False
