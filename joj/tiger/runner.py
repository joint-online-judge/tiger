# modified from https://github.com/eecs-autograder/autograder-sandbox/blob/develop/autograder_sandbox/autograder_sandbox.py
# Copyright eecs-autograder under GNU Lesser General Public License v3.0
import asyncio
import os
import subprocess
import tarfile
import tempfile
import uuid
from typing import IO, AnyStr, Iterator, List, Mapping, NoReturn, Optional, Sequence

import msgpack

from joj.tiger.schemas import CompletedCommand

RUNNER_HOME_DIR_NAME = "/root"
RUNNER_WORKING_DIR_NAME = RUNNER_HOME_DIR_NAME
RUNNER_USERNAME = "root"
RUNNER_DOCKER_IMAGE = os.environ.get(
    "RUNNER_DOCKER_IMAGE", "jameslp/ag-ubuntu-16:latest"
)

RUNNER_PIDS_LIMIT = int(os.environ.get("RUNNER_PIDS_LIMIT", 512))
RUNNER_MEM_LIMIT = os.environ.get("RUNNER_MEM_LIMIT", "4g")
RUNNER_MIN_FALLBACK_TIMEOUT = int(os.environ.get("RUNNER_MIN_FALLBACK_TIMEOUT", 60))

RUNNER_PATH = "/root/runner"


class RunnerCommandError(Exception):
    """
    An exception to be raised when a call to Runner.run_command
    doesn't finish normally.
    """


class Runner:
    """
    This class wraps Docker functionality to provide an interface for
    running untrusted programs in a secure, isolated environment.

    Docker documentation and installation instructions can be
    found at: https://www.docker.com/

    Instances of this class are intended to be used with a context
    manager. The underlying docker container to be used is created and
    destroyed when the context manager is entered and exited,
    respectively.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        docker_image: str = RUNNER_DOCKER_IMAGE,
        allow_network_access: bool = False,
        environment_variables: Optional[Mapping[str, str]] = None,
        container_create_timeout: Optional[int] = None,
        pids_limit: int = RUNNER_PIDS_LIMIT,
        memory_limit: str = RUNNER_MEM_LIMIT,
        min_fallback_timeout: int = RUNNER_MIN_FALLBACK_TIMEOUT,
        debug: bool = False,
    ):
        """
        :param name: A human-readable name that can be used to identify
            this runner instance. This value must be unique across all
            runner instances, otherwise starting the runner will fail.
            If no value is specified, a random name will be generated
            automatically.

        :param docker_image: The name of the docker image to create the
            runner from. Note that in order to function properly, all
            custom docker images must extend a supported base image (see README).

            The default value for this parameter can be changed by
            setting the RUNNER_DOCKER_IMAGE environment variable.

        :param allow_network_access: When True, programs running inside
            the runner will have unrestricted access to external
            IP addresses. When False, programs will not be able
            to contact any external IPs.

        :param environment_variables: A dictionary of (variable_name:
            value) pairs that should be set as environment variables
            inside the runner.

        :param container_create_timeout: A time limit to be placed on
            creating the underlying Docker container for this runner.
            If the time limit is exceeded, subprocess.CalledProcessError
            will be raised. A value of None indicates no time limit.

        :param pids_limit: Passed to "docker create" with the
            --pids-limit flag. This will limit the number of processes
            that can be created.
            See https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v1/pids.html
            for more information on limiting pids with cgroups.

            We recommend leaving this value set to the default of 512
            and using the max_num_processes argument to run_command
            if you want to impose a strict limit on a particular command.

            The default value for this parameter can be changed by
            setting the RUNNER_PIDS_LIMIT environment variable.

        :param memory_limit: Passed to "docker create" with the --memory,
            --memory-swap, and --oom-kill-disable arguments. This will
            limit the amount of memory that processes running in the
            runner can use.

            We choose to disable the OOM killer to prevent the runner's
            main process from being killed by the OOM killer (which would
            cause the whole container to exit). This means, however, that
            a command that hits the memory limit may time out.

            In general we recommend setting this value as high as is safe
            for your host machine and additionally using the max_virtual_memory
            argument to run_command to set a tighter limit on the command's
            address space size.

            The default value for this parameter can be changed by
            setting the RUNNER_MEM_LIMIT environment variable.

            See https://docs.docker.com/config/containers/resource_constraints/
                    #limit-a-containers-access-to-memory
            for more information.

        :param min_fallback_timeout: The timeout argument to run_command
            is primarily enforced by cmd_runner.py. When that argument is
            not None, a timeout of either twice the timeout argument to
            run_command or this value, whichever is larger, will be applied
            to the subprocess call to cmd_runner.py itself.

            The default value for this parameter can be changed by
            setting the RUNNER_MIN_FALLBACK_TIMEOUT environment variable.

        :param debug: Whether to print additional debugging information.
        """
        if name is None:
            self._name = "runner-{}".format(uuid.uuid4().hex)
        else:
            self._name = name

        self._docker_image = docker_image
        self._allow_network_access = allow_network_access
        self._environment_variables = environment_variables
        self._is_running = False
        self._container_create_timeout = container_create_timeout
        self._pids_limit = pids_limit
        self._memory_limit = memory_limit
        self._min_fallback_timeout = min_fallback_timeout
        self.debug = debug

    def __enter__(self) -> "Runner":
        self._create_and_start()
        return self

    def __exit__(self, *args: object) -> None:
        self._destroy()

    def reset(self) -> None:
        """
        Destroys, re-creates, and restarts the runner. As a side
        effect, this will effectively kill any processes running inside
        the runner and reset the runner's filesystem.
        """
        self._destroy()
        self._create_and_start()

    def restart(self) -> None:
        """
        Restarts the runner without destroying it.
        """
        self._stop()
        subprocess.check_call(["docker", "start", self.name])

    def _create_and_start(self) -> None:
        create_args = [
            "docker",
            "run",
            "--name=" + self.name,
            "-i",  # Run in interactive mode (for input redirection)
            "-t",  # Allocate psuedo tty
            "-d",  # Detached
            "--privileged",
            "--pids-limit",
            str(self._pids_limit),
            "--memory",
            self._memory_limit,
            "--memory-swap",
            self._memory_limit,
            "--oom-kill-disable",
        ]

        if not self.allow_network_access:
            # Create the container without a network stack.
            create_args += ["--net", "none"]

        if self.environment_variables:
            for key, value in self.environment_variables.items():
                create_args += ["-e", "{}={}".format(key, value)]

        # Override any CMD or ENTRYPOINT directives used in custom images.
        # This restriction is in place to avoid situations where a custom
        # entrypoint exits prematurely, therefore stopping the container.
        # https://docs.docker.com/engine/reference/run/#overriding-dockerfile-image-defaults
        create_args += ["--entrypoint", ""]
        create_args.append(self.docker_image)  # Image to use
        create_args.append("/bin/bash")

        subprocess.check_call(
            create_args,
            timeout=self._container_create_timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            cmd_runner_source = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "..",
                "runner",
                "main",
            )
            subprocess.run(
                [
                    "docker",
                    "cp",
                    cmd_runner_source,
                    "{}:{}".format(self.name, RUNNER_PATH),
                ],
                check=True,
            )
            subprocess.run(
                ["docker", "exec", "-i", self.name, "chmod", "555", RUNNER_PATH],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            if self.debug:
                print(e.stdout)
                print(e.stderr)

            self._destroy()
            raise

        self._is_running = True

    def _destroy(self) -> None:
        self._stop()
        subprocess.check_call(["docker", "rm", self.name], stdout=subprocess.DEVNULL)
        self._is_running = False

    def _stop(self) -> None:
        subprocess.check_call(
            ["docker", "stop", "--time", "1", self.name], stdout=subprocess.DEVNULL
        )

    @property
    def name(self) -> str:
        """
        The name used to identify this runner. (Read only)
        """
        return self._name

    @property
    def docker_image(self) -> str:
        """
        The name of the docker image to create the runner from.
        """
        return self._docker_image

    @property
    def allow_network_access(self) -> bool:
        """
        Whether network access is allowed by this runner.
        If an attempt to set this value is made while the runner is
        running, ValueError will be raised.
        """
        return self._allow_network_access

    @allow_network_access.setter
    def allow_network_access(self, value: bool) -> None:
        """
        Raises ValueError if this runner instance is currently running.
        """
        if self._is_running:
            raise ValueError(
                "Cannot change network access settings on a running runner"
            )

        self._allow_network_access = value

    @property
    def environment_variables(self) -> Mapping[str, str]:
        """
        A dictionary of environment variables to be set inside the
        runner (Read only).
        """
        if not self._environment_variables:
            return {}

        return dict(self._environment_variables)

    def run_command(
        self,
        args: List[str],
        block_process_spawn: bool = False,
        max_stack_size: Optional[int] = None,
        max_virtual_memory: Optional[int] = None,
        as_root: bool = False,
        stdin: Optional[IO[AnyStr]] = None,
        timeout: Optional[int] = None,
        check: bool = False,
        truncate_stdout: Optional[int] = None,
        truncate_stderr: Optional[int] = None,
    ) -> CompletedCommand:
        """
        Runs a command inside the runner and returns the results.

        :param args: A list of strings that specify which command should
            be run inside the runner.

        :param block_process_spawn: If true, prevent the command from
            spawning child processes by setting the nproc limit to 0.

        :param max_stack_size: The maximum stack size, in bytes, allowed
            for the command.

        :param max_virtual_memory: The maximum amount of memory, in
            bytes, allowed for the command.

        :param as_root: Whether to run the command as a root user.

        :param stdin: A file object to be redirected as input to the
            command's stdin. If this is None, /dev/null is sent to the
            command's stdin.

        :param timeout: The time limit for the command.

        :param check: Causes CalledProcessError to be raised if the
            command exits nonzero or times out.

        :param truncate_stdout: When not None, stdout from the command
            will be truncated after this many bytes.

        :param truncate_stderr: When not None, stderr from the command
            will be truncated after this many bytes.
        """
        cmd = ["docker", "exec", "-i", self.name, RUNNER_PATH]

        # if stdin is None:
        #     cmd.append('--stdin_devnull')

        # if block_process_spawn:
        #     cmd += ['--block_process_spawn']

        # if max_stack_size is not None:
        #     cmd += ['--max_stack_size', str(max_stack_size)]

        # if max_virtual_memory is not None:
        #     cmd += ['--max_virtual_memory', str(max_virtual_memory)]

        # if timeout is not None:
        #     cmd += ['--timeout', str(timeout)]

        # if truncate_stdout is not None:
        #     cmd += ['--truncate_stdout', str(truncate_stdout)]

        # if truncate_stderr is not None:
        #     cmd += ['--truncate_stderr', str(truncate_stderr)]

        # if as_root:
        #     cmd += ['--as_root']

        cmd += args

        if self.debug:
            print("running: {}".format(cmd), flush=True)

        with tempfile.TemporaryFile() as runner_stdout, tempfile.TemporaryFile() as runner_stderr:
            fallback_timeout = (
                max(timeout * 2, self._min_fallback_timeout)
                if timeout is not None
                else None
            )
            try:
                subprocess.run(
                    cmd,
                    stdin=stdin,
                    stdout=runner_stdout,
                    stderr=runner_stderr,
                    check=True,
                    timeout=fallback_timeout,
                )
                runner_stdout.seek(0)
                runner_stdout_bytes = runner_stdout.read().strip()
                results_msgpack = msgpack.unpackb(runner_stdout_bytes)

                result = CompletedCommand(
                    return_code=results_msgpack["ReturnCode"],
                    timed_out=results_msgpack["TimedOut"],
                    stdout=results_msgpack["Stdout"],
                    stderr=results_msgpack["Stderr"],
                    stdout_truncated=False,
                    stderr_truncated=False,
                    time=results_msgpack["Time"],
                    memory=results_msgpack["Memory"],
                )

                if (result.return_code != 0 or results_msgpack["TimedOut"]) and check:
                    self._raise_runner_command_error(
                        stdout=runner_stdout, stderr=runner_stderr
                    )

                return result
            except subprocess.TimeoutExpired:
                return CompletedCommand(
                    return_code=None,
                    timed_out=True,
                    stdout=b"",
                    stderr=b"The command exceeded the fallback timeout. "
                    b"If this occurs frequently, contact your system administrator.\n",
                    stdout_truncated=False,
                    stderr_truncated=True,
                    time=0,
                    memory=0,
                )
            except subprocess.CalledProcessError as e:
                # For some reason mypy wants us to return, even though
                # _raise_runner_command_error is NoReturn
                return self._raise_runner_command_error(
                    stdout=runner_stdout, stderr=runner_stderr, original_error=e
                )

    async def async_run_command(
        self,
        args: List[str],
        block_process_spawn: bool = False,
        max_stack_size: Optional[int] = None,
        max_virtual_memory: Optional[int] = None,
        as_root: bool = False,
        stdin: Optional[IO[AnyStr]] = None,
        timeout: Optional[int] = None,
        check: bool = False,
        truncate_stdout: Optional[int] = None,
        truncate_stderr: Optional[int] = None,
    ) -> CompletedCommand:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.run_command,
            args,
            block_process_spawn,
            max_stack_size,
            max_virtual_memory,
            as_root,
            stdin,
            timeout,
            check,
            truncate_stdout,
            truncate_stderr,
        )

    def _raise_runner_command_error(
        self,
        *,
        stdout: IO[bytes],
        stderr: IO[bytes],
        original_error: Optional[Exception] = None
    ) -> NoReturn:
        stdout.seek(0)
        stderr.seek(0)
        new_error = RunnerCommandError(
            stdout.read().decode("utf-8", "surrogateescape")
            + "\n"
            + stderr.read().decode("utf-8", "surrogateescape")
        )

        if original_error is not None:
            raise new_error from original_error
        raise new_error

    def add_files(
        self, *filenames: str, owner: str = RUNNER_USERNAME, read_only: bool = False
    ) -> None:
        """
        Copies the specified files into the working directory of this
        runner.
        The filenames specified can be absolute paths or relative paths
        to the current working directory.

        :param owner: The name of a user who should be granted ownership of
            the newly added files.
            Must be either Runner.RUNNER_USERNAME or 'root',
            otherwise ValueError will be raised.
        :param read_only: If true, the new files' permissions will be set to
            read-only.
        """
        if owner != RUNNER_USERNAME and owner != "root":
            raise ValueError('Invalid value for parameter "owner": {}'.format(owner))

        with tempfile.TemporaryFile() as f, tarfile.TarFile(
            fileobj=f, mode="w"
        ) as tar_file:
            for filename in filenames:
                tar_file.add(filename, arcname=os.path.basename(filename))

            f.seek(0)
            subprocess.check_call(
                ["docker", "cp", "-", self.name + ":" + RUNNER_WORKING_DIR_NAME],
                stdin=f,
            )

            file_basenames = [os.path.basename(filename) for filename in filenames]
            if owner == RUNNER_USERNAME:
                self._chown_files(file_basenames)

            if read_only:
                chmod_cmd = ["chmod", "444"] + file_basenames
                self.run_command(chmod_cmd, as_root=True)

    def add_and_rename_file(self, filename: str, new_filename: str) -> None:
        """
        Copies the specified file into the working directory of this
        runner and renames it to new_filename.
        """
        dest = os.path.join(self.name + ":" + RUNNER_WORKING_DIR_NAME, new_filename)
        subprocess.check_call(["docker", "cp", filename, dest])
        self._chown_files([new_filename])

    def _chown_files(self, filenames: Sequence[str]) -> None:
        chown_cmd = ["chown", "{}:{}".format(RUNNER_USERNAME, RUNNER_USERNAME)]
        chown_cmd += filenames
        self.run_command(chown_cmd, as_root=True)


# Generator that reads amount_to_read bytes from file_obj, yielding
# one chunk at a time.
def _chunked_read(
    file_obj: IO[bytes], amount_to_read: int, chunk_size: int = 1024 * 16
) -> Iterator[bytes]:
    num_reads = amount_to_read // chunk_size
    for _ in range(num_reads):
        yield file_obj.read(chunk_size)

    remainder = amount_to_read % chunk_size
    if remainder:
        yield file_obj.read(remainder)
