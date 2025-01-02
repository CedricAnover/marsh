from threading import Timer
from typing import Optional

import docker
from docker.models.containers import Container
from docker.errors import DockerException, NotFound

from marsh import Executor


class DockerContainer:
    def __init__(self,
                 image: str,
                 *create_args,
                 client_args=(),
                 client_kwargs=None,
                 name: str = "ephemeral-container",
                 timeout: int = 600,  # in seconds
                 **create_kwargs
                 ):
        client_kwargs = client_kwargs or {}

        self._image = image
        self._name = name

        self._timeout = timeout
        self._timeout_event = False  # Timeout Event Flag
        self._timer: Timer | None = None

        self._container: Optional[Container] = None
        self._client = docker.DockerClient(*client_args, **client_kwargs)
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

            # Set the Timer to stop the container on timeout
            self._timer = Timer(self._timeout, self._stop_container)
            self._timer.start()

        # except (ImageNotFound, APIError) as e:
        except DockerException as e:
            self._clean()
            raise

        return self._container

    def __exit__(self, exc_type, exc_value, traceback):
        # Clean the resources
        self._clean()

        if exc_type is not None:
            return False

        return True

    def _stop_container(self) -> None:
        self._timeout_event = True
        try:
            self._clean()
            raise RuntimeError(f" Timeout reached for container '{self._name}'.")
        except RuntimeError as err:
            self.__logger.error(f"{err}")
            raise

    def _clean(self) -> None:
        # Cancel the Timer
        if self._timer:
            self._timer.cancel()

        # Remove the Container
        if self._container:
            try:
                self._container.remove(force=True)
            except DockerException as err:
                pass

        all_containers: list[Container] = self._client.containers.list(all=True)
        for container in all_containers:
            if container.name == self._name:
                try:
                    container.stop(timeout=0)
                except NotFound:
                    # This occurs when timeout event occurred.
                    pass
                except DockerException as err:
                    raise

        # Close the docker client
        try:
            self._client.close()
        except DockerException as err:
            raise


class DockerCommandExecutor(Executor):
    def __init__(self,
                 image: str,
                 timeout: int = 600,
                 container_name: str = "ephemeral-container",
                 client_args: tuple = (),
                 client_kwargs: dict | None = None,
                 pipe_prev_stdout: bool = False,
                 *create_args,
                 **create_kwargs,
                 ):

        self._client_args = client_args
        self._client_kwargs = client_kwargs or {}

        self._create_args = create_args
        self._create_kwargs = create_kwargs

        self._container_name = container_name
        self.timeout = timeout
        self.image = image  # Docker container image

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
                if isinstance(command, str):
                    command += f" {x_stdout.decode().strip()}"
                else:
                    command = command + [x_stdout.decode().strip()]

            # Run a command in the container
            result = container.exec_run(command, **run_kwargs)

            # Check exit code and update output streams
            if result.exit_code == 0:
                # Update STDOUT (no strip)
                stdout = result.output
            else:
                # Update STDERR (no strip)
                stderr = result.output

        return stdout, stderr
