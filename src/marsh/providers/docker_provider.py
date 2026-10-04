"""Docker-backed provider adapter for the canonical process contract."""

from __future__ import annotations

from dataclasses import dataclass

from marsh.core.domain import Machine, Process, ProcessSpec, ProcessStatus, Result, can_transition
from marsh.core.providers import (
    ProviderCapabilities,
    ProviderConfigurationError,
    ProviderError,
    ProviderUnavailableError,
)


@dataclass(frozen=True)
class DockerProviderConfig:
    """Configuration for Docker process materialization."""

    image: str
    client_kwargs: dict[str, object]

    def __init__(self, image: str, client_kwargs: dict[str, object] | None = None):
        image = image.strip()
        if not image:
            raise ProviderConfigurationError("docker image must be non-empty")
        object.__setattr__(self, "image", image)
        object.__setattr__(self, "client_kwargs", dict(client_kwargs or {}))


class DockerProcess:
    """Process contract backed by one Docker container."""

    def __init__(self, spec: ProcessSpec, config: DockerProviderConfig):
        self.spec = spec
        self.config = config
        self._status = ProcessStatus.CREATED
        self._result: Result | None = None
        self._container = None
        self._client = None

    @property
    def status(self) -> ProcessStatus:
        return self._status

    def _transition(self, target: ProcessStatus) -> None:
        if target is self._status:
            return
        if not can_transition(self._status, target):
            raise RuntimeError(
                f"invalid process transition: {self._status.value} -> {target.value}"
            )
        self._status = target

    def start(self) -> None:
        if self._status is not ProcessStatus.CREATED:
            raise RuntimeError(f"cannot start process in {self._status.value} state")
        if self.spec.stdin is not None:
            raise ProviderConfigurationError(
                "DockerProcess does not support ProcessSpec.stdin yet"
            )
        self._transition(ProcessStatus.STARTING)
        try:
            import docker
            from docker.errors import DockerException
        except ImportError as exc:
            self._transition(ProcessStatus.FAILED)
            raise ProviderUnavailableError(
                "Docker provider requires the 'docker' package"
            ) from exc

        try:
            self._client = docker.DockerClient(**self.config.client_kwargs)
            self._container = self._client.containers.create(
                self.config.image,
                command=[self.spec.executable, *self.spec.arguments],
                stdout=True,
                stderr=True,
                working_dir=self.spec.working_directory,
                environment=dict(self.spec.environment),
                detach=True,
                auto_remove=False,
            )
            self._container.start()
            self._transition(ProcessStatus.RUNNING)
        except DockerException as exc:
            self._transition(ProcessStatus.FAILED)
            self._result = Result(status=ProcessStatus.FAILED, error=str(exc))
            self._cleanup()
            raise ProviderUnavailableError(str(exc)) from exc
        except Exception as exc:
            self._transition(ProcessStatus.FAILED)
            self._result = Result(status=ProcessStatus.FAILED, error=str(exc))
            self._cleanup()
            raise ProviderError(str(exc)) from exc

    def wait(self) -> Result:
        if self._result is not None:
            return self._result
        if self._container is None:
            return Result(status=self._status, error="process was not started")
        try:
            status_code = self._container.wait(timeout=self.spec.timeout)["StatusCode"]
            stdout = self._container.logs(stdout=True, stderr=False)
            stderr = self._container.logs(stdout=False, stderr=True)
            status = (
                ProcessStatus.COMPLETED
                if status_code == 0
                else ProcessStatus.FAILED
            )
            error = (
                None
                if status is ProcessStatus.COMPLETED
                else f"process exited with code {status_code}"
            )
            self._transition(status)
            self._result = Result(
                stdout=stdout,
                stderr=stderr,
                exit_code=status_code,
                status=status,
                error=error,
            )
            return self._result
        except TimeoutError:
            self._transition(ProcessStatus.TIMED_OUT)
            self._result = Result(
                status=ProcessStatus.TIMED_OUT,
                error="process timed out",
            )
            return self._result
        except Exception as exc:
            if self._status is ProcessStatus.RUNNING:
                self._transition(ProcessStatus.FAILED)
            self._result = Result(status=ProcessStatus.FAILED, error=str(exc))
            raise ProviderError(str(exc)) from exc
        finally:
            self._cleanup()

    def poll(self) -> ProcessStatus:
        if self._container is None:
            return self._status
        self._container.reload()
        if self._container.status == "exited" and self._status is ProcessStatus.RUNNING:
            self._transition(
                ProcessStatus.COMPLETED
                if self._container.attrs["State"]["ExitCode"] == 0
                else ProcessStatus.FAILED
            )
        return self._status

    def stop(self) -> None:
        if self._container is not None and self._status is ProcessStatus.RUNNING:
            self._transition(ProcessStatus.STOPPING)
            self._container.stop(timeout=0)
            self._transition(ProcessStatus.CANCELLED)
            self._result = Result(status=ProcessStatus.CANCELLED)
            self._cleanup()

    def terminate(self) -> None:
        self.stop()

    def kill(self) -> None:
        if self._container is not None and self._status is ProcessStatus.RUNNING:
            self._transition(ProcessStatus.STOPPING)
            self._container.kill()
            self._transition(ProcessStatus.CANCELLED)
            self._result = Result(status=ProcessStatus.CANCELLED)
            self._cleanup()

    def cancel(self) -> None:
        if self._status is ProcessStatus.CREATED:
            self._transition(ProcessStatus.CANCELLED)
            self._result = Result(status=ProcessStatus.CANCELLED)
            return
        self.stop()

    def result(self) -> Result:
        return self.wait()

    def _cleanup(self) -> None:
        if self._container is not None:
            try:
                self._container.remove(force=True)
            except Exception:
                pass
            self._container = None
        if self._client is not None:
            self._client.close()
            self._client = None


class DockerMachine:
    """Machine that materializes Docker-backed processes."""

    def __init__(self, config: DockerProviderConfig):
        self.config = config

    def create_process(self, spec: ProcessSpec) -> DockerProcess:
        return DockerProcess(spec, self.config)


class DockerProvider:
    """Reference non-local provider; no Workflow semantics live here."""

    name = "docker"

    def __init__(self, image: str = "python:3.12-slim", client_kwargs=None):
        self.config = DockerProviderConfig(image, client_kwargs)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            {
                "machine.create",
                "process.start",
                "process.wait",
                "process.poll",
                "process.stop",
                "process.terminate",
                "process.kill",
                "process.cancel",
                "process.result",
            }
        )

    def create_machine(self, **kwargs) -> Machine:
        if kwargs:
            raise ProviderConfigurationError(
                f"unsupported docker provider options: {sorted(kwargs)}"
            )
        return DockerMachine(self.config)
