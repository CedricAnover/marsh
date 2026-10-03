"""Discover a provider by name and negotiate execution capabilities."""

from marsh import LocalProvider, ProviderRegistry


registry = ProviderRegistry({"local": LocalProvider()})

provider = registry.require(
    "local",
    capabilities=("machine.create", "process.start", "process.wait"),
)

machine = provider.create_machine()

print("provider:", "local")
print("supports process.result:", "process.result" in provider.capabilities)
print("machine:", type(machine).__name__)
