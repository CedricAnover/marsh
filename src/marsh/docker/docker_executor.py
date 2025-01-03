import uuid
import time
import threading
from typing import Optional

import docker
from docker.models.containers import Container
from docker.errors import DockerException, NotFound

from marsh.exceptions import DockerError, DockerClientError
from marsh import Executor
from .docker_command_grammar import DockerCommandGrammar


def generate_random_container_name(prefix="ephemeral-container"):
    return prefix + "-" + str(uuid.uuid4()).replace('-', '')[:8]


class DockerContainer:
    def __init__(self,
                 image: str,
                 *create_args,
                 client_args=(),
                 client_kwargs=None,
                 name: str | None = None,
                 timeout: int = 600,  # in seconds
                 start_timeout: int = 1.5,  # Wait for few seconds after a container started
                 **create_kwargs
                 ):
        client_kwargs = client_kwargs or {}

        self._image = image
        self._name = name or generate_random_container_name()

        self._start_timeout = start_timeout
        self._timeout = timeout
        self._timer: threading.Timer | None = None

        self._container: Optional[Container] = None

        try:
            self._client = docker.DockerClient(*client_args, **client_kwargs)
        except Exception as err:
            raise DockerClientError(err)

        self._create_args = create_args
        self._create_kwargs = create_kwargs

    def __enter__(self) -> Container:
        try:
            self._container = self._client.containers.create(
                self._image,
                *self._create_args,
                command="tail -f /dev/null",  # To run the container continuously
                name=self._name,
                detach=True,
                auto_remove=True,
                **self._create_kwargs
            )

            # Start the container
            self._container.start()
            time.sleep(self._start_timeout)  # Wait for few seconds

            # Set the Timer to stop the container on timeout
            self._timer = threading.Timer(self._timeout, self._throw_timeout_error)
            self._timer.start()

        except Exception as err:
            self._clean()
            raise DockerError(err)

        return self._container

    def __exit__(self, exc_type, exc_value, traceback):
        # Clean the resources
        self._clean()

        if exc_type is TimeoutError:
            return False

        return True

    def _throw_timeout_error(self) -> None:
        self._clean()
        raise TimeoutError(f"Timeout reached for container '{self._name}'.")

    def _clean(self) -> None:
        # 1. Cancel the Timer
        # 2. Remove the Container
        # 3. Close the Docker Client

        # Cancel the Timer
        if self._timer:
            self._timer.cancel()

        # Remove the Container
        all_containers: list[Container] = self._client.containers.list(all=True)
        for container in all_containers:
            if container.name == self._name:
                try:
                    container.stop(timeout=0)
                except NotFound as err:
                    # This occurs when timeout event occurred.
                    pass

        # Close the docker client
        try:
            self._client.close()
        except DockerException as err:
            raise  DockerClientError(err)


class DockerCommandExecutor(Executor):
    def __init__(self,
                 image: str,
                 *create_args,
                 container_name: str | None = None,
                 pipe_prev_stdout: bool = False,
                 timeout: int = 600,
                 shell_command="/bin/sh -c",
                 client_args: tuple = (),
                 client_kwargs: dict | None = None,
                 **create_kwargs,
                 ):

        self._client_args = client_args
        self._client_kwargs = client_kwargs or {}

        self._create_args = create_args
        self._create_kwargs = create_kwargs

        self._container_name = container_name
        self.timeout = timeout
        self.image = image  # Docker container image

        # Create a DockerCommandGrammar and clean the given command
        self._command_grammar = DockerCommandGrammar(shell_command=shell_command)

        self._pipe_prev_stdout = pipe_prev_stdout

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            command: str | list[str],
            **run_kwargs
            ) -> tuple[bytes, bytes]:

        stdout: bytes = b""
        stderr: bytes = b""

        with DockerContainer(self.image,
                             *self._create_args,
                             name=self._container_name,
                             timeout=self.timeout,
                             client_args=self._client_args,
                             client_kwargs=self._client_kwargs,
                             **self._create_kwargs,
                             ) as container:

            # Unix Pipes, if specified
            if self._pipe_prev_stdout:
                full_command = self._command_grammar.build_cmd(command, x_stdout)
            else:
                full_command = self._command_grammar.build_cmd(command)

            # Run a command in the container
            try:
                result = container.exec_run(full_command, **run_kwargs)
            except TimeoutError:
                raise

            # Check exit code and update output streams
            if result.exit_code == 0:
                # Update STDOUT (no strip)
                stdout = result.output
            else:
                # Update STDERR (no strip)
                stderr = result.output

        return stdout, stderr
