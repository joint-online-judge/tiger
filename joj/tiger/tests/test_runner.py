# modified from https://github.com/eecs-autograder/autograder-sandbox/blob/develop/autograder_sandbox/tests.py
# Copyright eecs-autograder under GNU Lesser General Public License v3.0
import itertools
import multiprocessing
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from collections import OrderedDict
from typing import IO, Callable, Optional, TypeVar
from unittest import mock

from joj.tiger.runner import Runner

# from joj.tiger.runner import (
#     Runner,
#     RunnerCommandError,
#     RUNNER_USERNAME,
#     RUNNER_HOME_DIR_NAME,
# )


def output_size_performance_test(
    output_size: int, *, stderr: bool = True, truncate: Optional[int] = None
) -> None:
    _PRINT_PROG = """
    import sys
    output_size = {}
    repeat_str = 'a' * 1000
    num_repeats = output_size // 1000
    remainder = output_size % 1000
    for i in range(num_repeats):
        sys.{stream}.write(repeat_str)
        sys.{stream}.flush()
    sys.{stream}.write('a' * remainder)
    sys.{stream}.flush()
    """
    with Runner() as runner:
        start = time.time()
        result = runner.run_command(
            ["python3", "-c", _PRINT_PROG.format(output_size, stream="stdout")],
            truncate_stdout=truncate,
            truncate_stderr=truncate,
            check=True,
        )
        print(
            "Ran command that printed {} bytes to stdout in {}".format(
                output_size, time.time() - start
            )
        )
        stdout_size = os.path.getsize(result.stdout.name)
        print(stdout_size)
        if truncate is None:
            assert stdout_size == output_size
        else:
            assert stdout_size == truncate

    if stderr:
        with Runner() as runner:
            start = time.time()
            result = runner.run_command(
                ["python3", "-c", _PRINT_PROG.format(output_size, stream="stderr")],
                truncate_stdout=truncate,
                truncate_stderr=truncate,
                check=True,
            )
            print(
                "Ran command that printed {} bytes to stderr in {}".format(
                    output_size, time.time() - start
                )
            )
            stderr_size = os.path.getsize(result.stderr.name)
            print(stderr_size)
            if truncate is None:
                assert stderr_size == output_size
            else:
                assert stderr_size == truncate


def kb_to_bytes(num_kb: int) -> int:
    return 1000 * num_kb


def mb_to_bytes(num_mb: int) -> int:
    return 1000 * kb_to_bytes(num_mb)


def gb_to_bytes(num_gb: int) -> int:
    return 1000 * mb_to_bytes(num_gb)


class RunnerInitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.name = "awexome_container{}".format(uuid.uuid4().hex)
        self.environment_variables = OrderedDict({"spam": "egg", "sausage": "42"})

    def test_default_init(self) -> None:
        runner = Runner()
        self.assertIsNotNone(runner.name)
        self.assertFalse(runner.allow_network_access)
        self.assertEqual({}, runner.environment_variables)
        self.assertEqual(
            "ghcr.io/joint-online-judge/buildpack-deps:focal", runner.docker_image
        )

    def test_non_default_init(self) -> None:
        docker_image = "waaaaluigi"
        runner = Runner(
            name=self.name,
            docker_image=docker_image,
            allow_network_access=True,
            environment_variables=self.environment_variables,
        )
        self.assertEqual(self.name, runner.name)
        self.assertEqual(docker_image, runner.docker_image)
        self.assertTrue(runner.allow_network_access)
        self.assertEqual(self.environment_variables, runner.environment_variables)


class RunnerBasicRunCommandTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = Runner()

        self.root_cmd = ["touch", "/"]

    def test_run_legal_command_non_root(self) -> None:
        stdout_content = "hello world"
        expected_output = stdout_content.encode() + b"\n"
        with self.runner:
            cmd_result = self.runner.run_command(["echo", stdout_content])
            self.assertEqual(0, cmd_result.return_code)
            self.assertEqual(expected_output, cmd_result.stdout)

    # def test_run_illegal_command_non_root(self) -> None:
    #     with self.runner:
    #         cmd_result = self.runner.run_command(self.root_cmd)
    #         self.assertNotEqual(0, cmd_result.return_code)
    #         self.assertNotEqual("", cmd_result.stderr)

    # def test_run_command_as_root(self) -> None:
    #     with self.runner:
    #         cmd_result = self.runner.run_command(self.root_cmd, as_root=True)
    #         self.assertEqual(0, cmd_result.return_code)
    #         self.assertEqual(b"", cmd_result.stderr)

    # def test_run_command_raise_on_error(self) -> None:
    #     """
    #     Tests that an exception is thrown only when check is True
    #     and the command exits with nonzero status.
    #     """
    #     with self.runner:
    #         # No exception should be raised.
    #         cmd_result = self.runner.run_command(
    #             self.root_cmd, as_root=True, check=True
    #         )
    #         self.assertEqual(0, cmd_result.return_code)

    #         with self.assertRaises(RunnerCommandError):
    #             self.runner.run_command(self.root_cmd, check=True)

    # def test_run_command_executable_does_not_exist_no_error(self) -> None:
    #     with self.runner:
    #         cmd_result = self.runner.run_command(["not_an_exe"])
    #         self.assertNotEqual(0, cmd_result.return_code)


class RunnerMiscTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.name = "awexome_container{}".format(uuid.uuid4().hex)
        self.environment_variables = OrderedDict({"spam": "egg", "sausage": "42"})

        self.stdin = tempfile.NamedTemporaryFile()
        self.stdout = tempfile.NamedTemporaryFile()
        self.stderr = tempfile.NamedTemporaryFile()

    def tearDown(self) -> None:
        self.stdin.close()
        self.stdout.close()
        self.stderr.close()

    def _write_and_seek(self, file_obj: IO[bytes], content: bytes) -> None:
        file_obj.write(content)
        file_obj.seek(0)

    # def test_very_large_io_no_truncate(self) -> None:
    #     output_size_performance_test(10 ** 9)

    # def test_truncate_very_large_io(self) -> None:
    #     output_size_performance_test(10 ** 9, truncate=10**7)

    # def test_truncate_stdout(self) -> None:
    #     truncate_length = 9
    #     long_output = b"a" * 100
    #     expected_output = long_output[:truncate_length]
    #     self._write_and_seek(self.stdin, long_output)
    #     with Runner() as runner:
    #         result = runner.run_command(
    #             ["cat"], stdin=self.stdin, truncate_stdout=truncate_length
    #         )
    #         self.assertEqual(expected_output, result.stdout)
    #         self.assertTrue(result.stdout_truncated)
    #         self.assertFalse(result.stderr_truncated)

    # def test_truncate_stderr(self) -> None:
    #     truncate_length = 13
    #     long_output = b"a" * 100
    #     expected_output = long_output[:truncate_length]
    #     self._write_and_seek(self.stdin, long_output)
    #     with Runner() as runner:
    #         result = runner.run_command(
    #             ["bash", "-c", ">&2 cat"],
    #             stdin=self.stdin,
    #             truncate_stderr=truncate_length,
    #         )
    #         self.assertEqual(expected_output, result.stderr)
    #         self.assertTrue(result.stderr_truncated)
    #         self.assertFalse(result.stdout_truncated)

    # def test_run_command_with_input(self) -> None:
    #     expected_stdout = b"spam egg sausage spam"
    #     self._write_and_seek(self.stdin, expected_stdout)
    #     with Runner() as runner:
    #         result = runner.run_command(["cat"], stdin=self.stdin)
    #         self.assertEqual(expected_stdout, result.stdout)

    def test_command_tries_to_read_from_stdin_when_stdin_arg_is_none(self) -> None:
        with Runner() as runner:
            result = runner.run_command(
                ["python3", "-c", "import sys; sys.stdin; print('done')"],
                max_stack_size=10000000,
                max_virtual_memory=500000000,
                timeout=2,
            )
            self.assertFalse(result.timed_out)
            self.assertEqual(0, result.return_code)

    def test_return_code_reported_and_stderr_recorded(self) -> None:
        with Runner() as runner:
            result = runner.run_command(["ls", "definitely not a file"])
            self.assertNotEqual(0, result.return_code)
            self.assertNotEqual("", result.stderr)

    def test_context_manager(self) -> None:
        with Runner(name=self.name) as runner:
            self.assertEqual(self.name, runner.name)
            # If the container was created successfully, we
            # should get an error if we try to create another
            # container with the same name.
            with self.assertRaises(subprocess.CalledProcessError):
                with Runner(name=self.name):
                    pass

        # The container should have been deleted at this point,
        # so we should be able to create another with the same name.
        with Runner(name=self.name):
            pass

    # def test_runner_environment_variables_set(self) -> None:
    #     print_env_var_script = "echo ${}".format(" $".join(self.environment_variables))

    #     runner = Runner(environment_variables=self.environment_variables)
    #     with runner, tempfile.NamedTemporaryFile("w+") as f:
    #         f.write(print_env_var_script)
    #         f.seek(0)
    #         runner.add_files(f.name)
    #         result = runner.run_command(["bash", os.path.basename(f.name)])
    #         expected_output = " ".join(
    #             str(val) for val in self.environment_variables.values()
    #         )
    #         expected_output += "\n"
    #         self.assertEqual(expected_output, result.stdout.decode())

    # def test_home_env_var_set_in_preexec(self) -> None:
    #     with Runner() as runner:
    #         result = runner.run_command(["bash", "-c", "printf $HOME"])
    #         self.assertEqual(RUNNER_HOME_DIR_NAME, result.stdout.decode())

    #         result = runner.run_command(["bash", "-c", "printf $USER"])
    #         self.assertEqual(RUNNER_USERNAME, result.stdout.decode())

    #         result = runner.run_command(["bash", "-c", "printf $HOME"], as_root=True)
    #         self.assertEqual("/root", result.stdout.decode())

    # def test_reset(self) -> None:
    #     with Runner() as runner:
    #         file_to_add = os.path.abspath(__file__)
    #         runner.add_files(file_to_add)

    #         ls_result = runner.run_command(["ls"]).stdout
    #         self.assertEqual(
    #             os.path.basename(file_to_add) + "\n", ls_result.decode()
    #         )

    #         runner.reset()
    #         self.assertEqual("", runner.run_command(["ls"]).stdout.decode())

    # def test_restart_added_files_preserved(self) -> None:
    #     with Runner() as runner:
    #         file_to_add = os.path.abspath(__file__)
    #         runner.add_files(file_to_add)

    #         ls_result = runner.run_command(["ls"]).stdout.decode()
    #         print(ls_result)
    #         self.assertEqual(os.path.basename(file_to_add) + "\n", ls_result)

    #         runner.restart()

    #         ls_result = runner.run_command(["ls"]).stdout.decode()
    #         self.assertEqual(os.path.basename(file_to_add) + "\n", ls_result)

    # def test_entire_process_tree_killed_on_timeout(self) -> None:
    #     for program_str in _PROG_WITH_SUBPROCESS_STALL, _PROG_WITH_PARENT_PROC_STALL:
    #         with Runner() as runner:
    #             ps_result = runner.run_command(["ps", "-aux"]).stdout.decode()
    #             print(ps_result)
    #             num_ps_lines = len(ps_result.split("\n"))
    #             print(num_ps_lines)

    #             script_file = _add_string_to_runner_as_file(
    #                 program_str, ".py", runner
    #             )

    #             start_time = time.time()
    #             result = runner.run_command(["python3", script_file], timeout=1)
    #             self.assertTrue(result.timed_out)

    #             time_elapsed = time.time() - start_time
    #             self.assertLess(
    #                 time_elapsed,
    #                 _SLEEP_TIME // 2,
    #                 msg="Killing processes took too long",
    #             )

    #             ps_result_after_cmd = (
    #                 runner.run_command(["ps", "-aux"]).stdout.decode()
    #             )
    #             print(ps_result_after_cmd)
    #             num_ps_lines_after_cmd = len(ps_result_after_cmd.split("\n"))
    #             self.assertEqual(num_ps_lines, num_ps_lines_after_cmd)

    # def test_command_can_leave_child_process_running(self) -> None:
    #     with Runner() as runner:
    #         ps_result = runner.run_command(["ps", "-aux"]).stdout.decode()
    #         print(ps_result)
    #         num_ps_lines = len(ps_result.split("\n"))
    #         print(num_ps_lines)

    #         script_file = _add_string_to_runner_as_file(
    #             _PROG_THAT_FORKS, ".py", runner
    #         )

    #         result = runner.run_command(["python3", script_file], timeout=1)
    #         self.assertFalse(result.timed_out)

    #         ps_result_after_cmd = (
    #             runner.run_command(["ps", "-aux"]).stdout.decode()
    #         )
    #         print(ps_result_after_cmd)
    #         num_ps_lines_after_cmd = len(ps_result_after_cmd.split("\n"))
    #         self.assertEqual(num_ps_lines + 1, num_ps_lines_after_cmd)

    # def test_try_to_change_cmd_runner(self) -> None:
    #     runner_path = "/usr/local/bin/cmd_runner.py"
    #     with Runner() as runner:
    #         # Make sure the file path above is correct
    #         runner.run_command(["cat", runner_path], check=True)
    #         with self.assertRaises(RunnerCommandError):
    #             runner.run_command(["touch", runner_path], check=True)

    @mock.patch("subprocess.run")
    @mock.patch("subprocess.check_call")
    def test_container_create_timeout(
        self, mock_check_call: mock.Mock, *args: object
    ) -> None:
        with Runner(debug=True):
            args, kwargs = mock_check_call.call_args
            self.assertIsNone(kwargs["timeout"])

        timeout = 42
        with Runner(container_create_timeout=timeout):
            args, kwargs = mock_check_call.call_args
            self.assertEqual(timeout, kwargs["timeout"])


class RunnerEncodeDecodeIOTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.non_utf = b"\x80 and some other stuff just because\n"
        with self.assertRaises(UnicodeDecodeError):
            self.non_utf.decode()
        self.file_to_print = "non-utf.txt"
        with open(self.file_to_print, "wb") as f:
            f.write(self.non_utf)

    def tearDown(self) -> None:
        os.remove(self.file_to_print)

    # def test_non_unicode_chars_in_normal_output(self) -> None:
    #     with Runner() as runner:
    #         runner.add_files(self.file_to_print)

    #         result = runner.run_command(["cat", self.file_to_print])
    #         stdout = result.stdout
    #         print(stdout)
    #         self.assertEqual(self.non_utf, stdout)

    #         result = runner.run_command(
    #             ["bash", "-c", ">&2 cat " + self.file_to_print]
    #         )
    #         stderr = result.stderr
    #         print(stderr)
    #         self.assertEqual(self.non_utf, stderr)

    # def test_non_unicode_chars_in_output_command_timed_out(self) -> None:
    #     with Runner() as runner:
    #         runner.add_files(self.file_to_print)

    #         result = runner.run_command(
    #             ["bash", "-c", "cat {}; sleep 5".format(self.file_to_print)], timeout=1
    #         )
    #         self.assertTrue(result.timed_out)
    #         self.assertEqual(self.non_utf, result.stdout)

    #     with Runner() as runner:
    #         runner.add_files(self.file_to_print)

    #         result = runner.run_command(
    #             ["bash", "-c", ">&2 cat {}; sleep 5".format(self.file_to_print)],
    #             timeout=1,
    #         )
    #         self.assertTrue(result.timed_out)
    #         self.assertEqual(self.non_utf, result.stderr)

    # def test_non_unicode_chars_in_output_on_process_error(self) -> None:
    #     with Runner() as runner:
    #         runner.add_files(self.file_to_print)

    #         with self.assertRaises(RunnerCommandError) as cm:
    #             runner.run_command(
    #                 ["bash", "-c", "cat {}; exit 1".format(self.file_to_print)],
    #                 check=True,
    #             )
    #         self.assertIn(
    #             self.non_utf.decode("utf-8", "surrogateescape"), str(cm.exception)
    #         )

    #     with Runner() as runner:
    #         runner.add_files(self.file_to_print)

    #         with self.assertRaises(RunnerCommandError) as cm:
    #             runner.run_command(
    #                 ["bash", "-c", ">&2 cat {}; exit 1".format(self.file_to_print)],
    #                 check=True,
    #             )
    #         self.assertIn(
    #             self.non_utf.decode("utf-8", "surrogateescape"), str(cm.exception)
    #         )


_SLEEP_TIME = 6

_PROG_THAT_FORKS = """
import subprocess
print('hello', flush=True)
subprocess.Popen(['sleep', '{}'])
print('goodbye', flush=True)
""".format(
    _SLEEP_TIME
)

_PROG_WITH_SUBPROCESS_STALL = """
import subprocess
print('hello', flush=True)
subprocess.call(['sleep', '{}'])
print('goodbye', flush=True)
""".format(
    _SLEEP_TIME
)

_PROG_WITH_PARENT_PROC_STALL = """
import subprocess
import time
print('hello', flush=True)
subprocess.Popen(['sleep', '{}'])
time.sleep({})
print('goodbye', flush=True)
""".format(
    _SLEEP_TIME * 2, _SLEEP_TIME
)


class RunnerResourceLimitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = Runner()

        self.small_virtual_mem_limit = mb_to_bytes(100)
        self.large_virtual_mem_limit = gb_to_bytes(1)

    def test_run_command_timeout_exceeded(self) -> None:
        with self.runner:
            result = self.runner.run_command(["sleep", "10"], timeout=1)
            self.assertTrue(result.timed_out)

    # def test_block_process_spawn(self) -> None:
    #     cmd = ["bash", "-c", "echo spam | cat > egg.txt"]
    #     with self.runner:
    #         # Spawning processes is allowed by default
    #         filename = _add_string_to_runner_as_file(
    #             _PROCESS_SPAWN_PROG_TMPL.format(num_processes=12, sleep_time=3),
    #             ".py",
    #             self.runner,
    #         )
    #         result = self.runner.run_command(["python3", filename])
    #         self.assertEqual(0, result.return_code)

    #         result = self.runner.run_command(
    #             ["python3", filename], block_process_spawn=True
    #         )
    #         stdout = result.stdout.decode()
    #         print(stdout)
    #         stderr = result.stderr.decode()
    #         print(stderr)
    #         self.assertNotEqual(0, result.return_code)
    #         self.assertIn("BlockingIOError", stderr)
    #         self.assertIn("Resource temporarily unavailable", stderr)

    # def test_command_exceeds_stack_size_limit(self) -> None:
    #     stack_size_limit = mb_to_bytes(5)
    #     mem_to_use = stack_size_limit * 2
    #     with self.runner:
    #         self._do_stack_resource_limit_test(
    #             mem_to_use, stack_size_limit, self.runner
    #         )

    # def test_command_doesnt_exceed_stack_size_limit(self) -> None:
    #     stack_size_limit = mb_to_bytes(30)
    #     mem_to_use = stack_size_limit // 2
    #     with self.runner:
    #         self._do_stack_resource_limit_test(
    #             mem_to_use, stack_size_limit, self.runner
    #         )

    # def test_command_exceeds_virtual_mem_limit(self) -> None:
    #     virtual_mem_limit = mb_to_bytes(100)
    #     mem_to_use = virtual_mem_limit * 2
    #     with self.runner:
    #         self._do_heap_resource_limit_test(
    #             mem_to_use, virtual_mem_limit, self.runner
    #         )

    # def test_command_doesnt_exceed_virtual_mem_limit(self) -> None:
    #     virtual_mem_limit = mb_to_bytes(100)
    #     mem_to_use = virtual_mem_limit // 2
    #     with self.runner:
    #         self._do_heap_resource_limit_test(
    #             mem_to_use, virtual_mem_limit, self.runner
    #         )

    # def test_run_subsequent_commands_with_different_resource_limits(self) -> None:
    #     with self.runner:
    #         # Under limit
    #         self._do_stack_resource_limit_test(
    #             mb_to_bytes(1), mb_to_bytes(10), self.runner
    #         )
    #         # Over previous limit
    #         self._do_stack_resource_limit_test(
    #             mb_to_bytes(20), mb_to_bytes(10), self.runner
    #         )
    #         # Limit raised
    #         self._do_stack_resource_limit_test(
    #             mb_to_bytes(20), mb_to_bytes(50), self.runner
    #         )
    #         # Over new limit
    #         self._do_stack_resource_limit_test(
    #             mb_to_bytes(40), mb_to_bytes(30), self.runner
    #         )

    #         # Under limit
    #         self._do_heap_resource_limit_test(
    #             mb_to_bytes(10), mb_to_bytes(100), self.runner
    #         )
    #         # Over previous limit
    #         self._do_heap_resource_limit_test(
    #             mb_to_bytes(200), mb_to_bytes(100), self.runner
    #         )
    #         # Limit raised
    #         self._do_heap_resource_limit_test(
    #             mb_to_bytes(200), mb_to_bytes(300), self.runner
    #         )
    #         # Over new limit
    #         self._do_heap_resource_limit_test(
    #             mb_to_bytes(250), mb_to_bytes(200), self.runner
    #         )

    def _do_stack_resource_limit_test(
        self, mem_to_use: int, mem_limit: int, runner: Runner
    ) -> None:
        prog_ret_code = _run_stack_usage_prog(mem_to_use, mem_limit, runner)

        self._check_resource_limit_test_result(prog_ret_code, mem_to_use, mem_limit)

    def _do_heap_resource_limit_test(
        self, mem_to_use: int, mem_limit: int, runner: Runner
    ) -> None:
        prog_ret_code = _run_heap_usage_prog(mem_to_use, mem_limit, runner)
        self._check_resource_limit_test_result(prog_ret_code, mem_to_use, mem_limit)

    def _check_resource_limit_test_result(
        self, ret_code: Optional[int], resource_used: int, resource_limit: int
    ) -> None:
        if resource_used > resource_limit:
            self.assertNotEqual(0, ret_code)
        else:
            self.assertEqual(0, ret_code)

    # def test_multiple_containers_dont_exceed_ulimits(self) -> None:
    #     """
    #     This is a sanity check to make sure that ulimits placed on
    #     different containers with the same UID don't conflict. All
    #     ulimits except for nproc are supposed to be process-linked
    #     rather than UID-linked.
    #     """
    #     self._do_parallel_container_stack_limit_test(
    #         16, mb_to_bytes(20), mb_to_bytes(30)
    #     )

    #     self._do_parallel_container_heap_limit_test(
    #         16, mb_to_bytes(300), mb_to_bytes(500)
    #     )

    def _do_parallel_container_stack_limit_test(
        self, num_containers: int, mem_to_use: int, mem_limit: int
    ) -> None:
        self._do_parallel_container_resource_limit_test(
            _run_stack_usage_prog, num_containers, mem_to_use, mem_limit
        )

    def _do_parallel_container_heap_limit_test(
        self, num_containers: int, mem_to_use: int, mem_limit: int
    ) -> None:
        self._do_parallel_container_resource_limit_test(
            _run_heap_usage_prog, num_containers, mem_to_use, mem_limit
        )

    def _do_parallel_container_resource_limit_test(
        self,
        func_to_run: Callable[[int, int, Runner], Optional[int]],
        num_containers: int,
        amount_to_use: int,
        resource_limit: int,
    ) -> None:
        with multiprocessing.Pool(processes=num_containers) as p:
            return_codes = p.starmap(
                func_to_run,
                itertools.repeat((amount_to_use, resource_limit, None), num_containers),
            )

        print(return_codes)
        for ret_code in return_codes:
            self.assertEqual(0, ret_code)


def _run_stack_usage_prog(
    mem_to_use: int, mem_limit: int, runner: Runner
) -> Optional[int]:
    def _run_prog(runner: Runner) -> Optional[int]:
        prog = _STACK_USAGE_PROG_TMPL.format(num_bytes_on_stack=mem_to_use)
        filename = _add_string_to_runner_as_file(prog, ".cpp", runner)
        exe_name = _compile_in_runner(runner, filename)
        result = runner.run_command(["./" + exe_name], max_stack_size=mem_limit)
        return result.return_code

    return _call_function_and_allocate_runner_if_needed(_run_prog, runner)


_STACK_USAGE_PROG_TMPL = """#include <iostream>
#include <thread>
#include <cstring>
using namespace std;
int main() {{
    char stacky[{num_bytes_on_stack}];
    for (int i = 0; i < {num_bytes_on_stack} - 1; ++i) {{
        stacky[i] = 'a';
    }}
    stacky[{num_bytes_on_stack} - 1] = '\\0';
    cout << "Sleeping" << endl;
    this_thread::sleep_for(chrono::seconds(2));
    cout << "Allocated " << strlen(stacky) + 1 << " bytes" << endl;
    return 0;
}}
"""


def _run_heap_usage_prog(
    mem_to_use: int, mem_limit: int, runner: Runner
) -> Optional[int]:
    def _run_prog(runner: Runner) -> Optional[int]:
        prog = _HEAP_USAGE_PROG_TMPL.format(num_bytes_on_heap=mem_to_use, sleep_time=2)
        filename = _add_string_to_runner_as_file(prog, ".cpp", runner)
        exe_name = _compile_in_runner(runner, filename)
        result = result = runner.run_command(
            ["./" + exe_name], max_virtual_memory=mem_limit
        )

        return result.return_code

    return _call_function_and_allocate_runner_if_needed(_run_prog, runner)


_HEAP_USAGE_PROG_TMPL = """#include <iostream>
#include <thread>
#include <cstring>
using namespace std;
const size_t num_bytes_on_heap = {num_bytes_on_heap};
int main() {{
    cout << "Allocating an array of " << num_bytes_on_heap << " bytes" << endl;
    char* heapy = new char[num_bytes_on_heap];
    for (size_t i = 0; i < num_bytes_on_heap - 1; ++i) {{
        heapy[i] = 'a';
    }}
    heapy[num_bytes_on_heap - 1] = '\\0';
    cout << "Sleeping" << endl;
    this_thread::sleep_for(chrono::seconds({sleep_time}));
    cout << "Allocated and filled " << strlen(heapy) + 1 << " bytes" << endl;
    return 0;
}}
"""


def _compile_in_runner(runner: Runner, *files_to_compile: str) -> str:
    exe_name = "prog"
    runner.run_command(
        ["g++", "--std=c++11", "-Wall", "-Werror"]
        + list(files_to_compile)
        + ["-o", exe_name],
        check=True,
    )
    return exe_name


_PROCESS_SPAWN_PROG_TMPL = """
import time
import subprocess
processes = []
for i in range({num_processes}):
    proc = subprocess.Popen(['sleep', '{sleep_time}'])
    processes.append(proc)
time.sleep({sleep_time})
for proc in processes:
    proc.communicate()
"""


def _add_string_to_runner_as_file(
    string: str, file_extension: str, runner: Runner
) -> str:
    with tempfile.NamedTemporaryFile("w+", suffix=file_extension) as f:
        f.write(string)
        f.seek(0)
        runner.add_files(f.name)

        return os.path.basename(f.name)


ReturnType = TypeVar("ReturnType")


def _call_function_and_allocate_runner_if_needed(
    func: Callable[[Runner], ReturnType], runner: Optional[Runner]
) -> ReturnType:
    if runner is None:
        runner = Runner()
        with runner:
            return func(runner)
    else:
        return func(runner)


# -----------------------------------------------------------------------------


class ContainerLevelResourceLimitTestCase(unittest.TestCase):
    ...
    # def test_pid_limit(self) -> None:
    #     with Runner() as runner:
    #         filename = _add_string_to_runner_as_file(
    #             _PROCESS_SPAWN_PROG_TMPL.format(num_processes=1000, sleep_time=5),
    #             ".py",
    #             runner,
    #         )

    #         # The limit should apply to all users, root or otherwise
    #         result = runner.run_command(["python3", filename], as_root=True)
    #         stdout = result.stdout.decode()
    #         print(stdout)
    #         stderr = result.stderr.decode()
    #         print(stderr)
    #         self.assertNotEqual(0, result.return_code)
    #         self.assertIn("BlockingIOError", stderr)
    #         self.assertIn("Resource temporarily unavailable", stderr)


#     def test_processes_created_and_finish_then_more_processes_spawned(self) -> None:
#         spawn_twice_prog = """
# import time
# import subprocess
# for i in range(2):
#     processes = []
#     print('spawing processes')
#     for i in range({num_processes}):
#         proc = subprocess.Popen(['sleep', '{sleep_time}'])
#         processes.append(proc)
#     time.sleep({sleep_time})
#     print('waiting for processes to finish')
#     for proc in processes:
#         proc.communicate()
# """
#         with Runner() as runner:
#             filename = _add_string_to_runner_as_file(
#                 spawn_twice_prog.format(num_processes=350, sleep_time=5), ".py", runner
#             )

#             result = runner.run_command(["python3", filename])
#             print(result.stdout.decode())
#             print(result.stderr.decode())
#             self.assertEqual(0, result.return_code)

# def test_fallback_time_limit_is_twice_timeout(self) -> None:
#     with Runner(min_fallback_timeout=4) as runner:
#         to_throw = subprocess.TimeoutExpired([], 10)
#         subprocess_run_mock = mock.Mock(side_effect=to_throw)
#         with mock.patch("subprocess.run", new=subprocess_run_mock):
#             result = runner.run_command(["sleep", "20"], timeout=5)
#             stdout = result.stdout.decode()
#             stderr = result.stderr.decode()
#             print(stdout)
#             print(stderr)

#             args, kwargs = subprocess_run_mock.call_args
#             self.assertEqual(10, kwargs["timeout"])

#             self.assertTrue(result.timed_out)
#             self.assertIsNone(result.return_code)
#             self.assertIn("fallback timeout", stderr)

# def test_fallback_time_limit_is_min_fallback_timeout(self) -> None:
#     with Runner(min_fallback_timeout=60) as runner:
#         to_throw = subprocess.TimeoutExpired([], 60)
#         subprocess_run_mock = mock.Mock(side_effect=to_throw)
#         with mock.patch("subprocess.run", new=subprocess_run_mock):
#             result = runner.run_command(["sleep", "20"], timeout=10)
#             stdout = result.stdout.decode()
#             stderr = result.stderr.decode()

#             args, kwargs = subprocess_run_mock.call_args
#             self.assertEqual(60, kwargs["timeout"])

#             self.assertTrue(result.timed_out)
#             self.assertIsNone(result.return_code)
#             self.assertIn("fallback timeout", stderr)

# # Since we disable the OOM killer for the container, we expect
# # commands to time out while waiting for memory to be paged
# # in and out.
# def test_memory_limit_no_oom_kill(self) -> None:
#     program_str = _HEAP_USAGE_PROG_TMPL.format(
#         num_bytes_on_heap=4 * 10**9, sleep_time=0
#     )
#     with Runner(memory_limit="2g") as runner:
#         filename = _add_string_to_runner_as_file(program_str, ".cpp", runner)
#         exe_name = _compile_in_runner(runner, filename)
#         # The limit should apply to all users, root or otherwise
#         result = runner.run_command(["./" + exe_name], timeout=20, as_root=True)

#         print(result.return_code)
#         print(result.stdout.decode())
#         print(result.stderr.decode())
#         self.assertTrue(result.timed_out)


# -----------------------------------------------------------------------------


_BAIDU_IP_ADDR = "220.181.38.251"


class RunnerNetworkAccessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.baidu_ping_cmd = ["ping", "-c", "5", _BAIDU_IP_ADDR]

    # def test_networking_disabled(self) -> None:
    #     with Runner() as runner:
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertNotEqual(0, result.return_code)

    # def test_networking_enabled(self) -> None:
    #     with Runner(allow_network_access=True) as runner:
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertEqual(0, result.return_code)

    # def test_set_allow_network_access(self) -> None:
    #     runner = Runner()
    #     self.assertFalse(runner.allow_network_access)
    #     with runner:
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertNotEqual(0, result.return_code)

    #     runner.allow_network_access = True
    #     self.assertTrue(runner.allow_network_access)
    #     with runner:
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertEqual(0, result.return_code)

    #     runner.allow_network_access = False
    #     self.assertFalse(runner.allow_network_access)
    #     with runner:
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertNotEqual(0, result.return_code)

    # def test_error_set_allow_network_access_while_running(self) -> None:
    #     with Runner() as runner:
    #         with self.assertRaises(ValueError):
    #             runner.allow_network_access = True

    #         self.assertFalse(runner.allow_network_access)
    #         result = runner.run_command(self.baidu_ping_cmd)
    #         self.assertNotEqual(0, result.return_code)


class RunnerCopyFilesTestCase(unittest.TestCase):
    # def test_copy_files_into_runner(self) -> None:
    #     files = []
    #     try:
    #         for i in range(10):
    #             f = tempfile.NamedTemporaryFile(mode="w+")
    #             f.write("this is file {}".format(i))
    #             f.seek(0)
    #             files.append(f)

    #         filenames = [file_.name for file_ in files]

    #         with Runner() as runner:
    #             runner.add_files(*filenames)

    #             ls_result = runner.run_command(["ls"]).stdout.decode()
    #             actual_filenames = [filename.strip() for filename in ls_result.split()]
    #             expected_filenames = [
    #                 os.path.basename(filename) for filename in filenames
    #             ]
    #             self.assertCountEqual(expected_filenames, actual_filenames)

    #             for file_ in files:
    #                 file_.seek(0)
    #                 expected_content = file_
    #                 actual_content = (
    #                     runner.run_command(["cat", os.path.basename(file_.name)])
    #                     .stdout
    #                     .decode()
    #                 )
    #                 self.assertEqual(expected_content, actual_content)
    #     finally:
    #         for file_ in files:
    #             file_.close()

    # def test_copy_and_rename_file_into_runner(self) -> None:
    #     expected_content = "this is a file"
    #     with tempfile.NamedTemporaryFile("w+") as f:
    #         f.write(expected_content)
    #         f.seek(0)

    #         with Runner() as runner:
    #             new_name = "new_filename.txt"
    #             runner.add_and_rename_file(f.name, new_name)

    #             ls_result = runner.run_command(["ls"]).stdout.decode()
    #             actual_filenames = [filename.strip() for filename in ls_result.split()]
    #             expected_filenames = [new_name]
    #             self.assertCountEqual(expected_filenames, actual_filenames)

    #             actual_content = (
    #                 runner.run_command(["cat", new_name]).stdout.decode()
    #             )
    #             self.assertEqual(expected_content, actual_content)

    # def test_add_files_root_owner_and_read_only(self) -> None:
    #     original_content = "some stuff you shouldn't change"
    #     overwrite_content = "lol I changed it anyway u nub"
    #     with tempfile.NamedTemporaryFile("w+") as f:
    #         f.write(original_content)
    #         f.seek(0)

    #         added_filename = os.path.basename(f.name)

    #         with Runner() as runner:
    #             runner.add_files(f.name, owner="root", read_only=True)

    #             actual_content = (
    #                 runner.run_command(["cat", added_filename], check=True)
    #                 .stdout
    #                 .decode()
    #             )
    #             self.assertEqual(original_content, actual_content)

    #             with self.assertRaises(RunnerCommandError):
    #                 runner.run_command(["touch", added_filename], check=True)

    #             with self.assertRaises(RunnerCommandError):
    #                 runner.run_command(
    #                     [
    #                         "bash",
    #                         "-c",
    #                         "printf '{}' > {}".format(
    #                             overwrite_content, added_filename
    #                         ),
    #                     ],
    #                     check=True,
    #                 )

    #             actual_content = (
    #                 runner.run_command(["cat", added_filename], check=True)
    #                 .stdout
    #                 .decode()
    #             )
    #             self.assertEqual(original_content, actual_content)

    #             root_touch_result = runner.run_command(
    #                 ["touch", added_filename], check=True, as_root=True
    #             )
    #             self.assertEqual(0, root_touch_result.return_code)

    #             runner.run_command(
    #                 [
    #                     "bash",
    #                     "-c",
    #                     "printf '{}' > {}".format(overwrite_content, added_filename),
    #                 ],
    #                 as_root=True,
    #                 check=True,
    #             )
    #             actual_content = (
    #                 runner.run_command(["cat", added_filename]).stdout.decode()
    #             )
    #             self.assertEqual(overwrite_content, actual_content)

    # def test_overwrite_non_read_only_file(self) -> None:
    #     original_content = "some stuff"
    #     overwrite_content = "some new stuff"
    #     with tempfile.NamedTemporaryFile("w+") as f:
    #         f.write(original_content)
    #         f.seek(0)

    #         added_filename = os.path.basename(f.name)

    #         with Runner() as runner:
    #             runner.add_files(f.name)

    #             actual_content = (
    #                 runner.run_command(["cat", added_filename], check=True)
    #                 .stdout
    #                 .decode()
    #             )
    #             self.assertEqual(original_content, actual_content)

    #             runner.run_command(
    #                 [
    #                     "bash",
    #                     "-c",
    #                     "printf '{}' > {}".format(overwrite_content, added_filename),
    #                 ]
    #             )
    #             actual_content = (
    #                 runner.run_command(["cat", added_filename], check=True)
    #                 .stdout
    #                 .decode()
    #             )
    #             self.assertEqual(overwrite_content, actual_content)

    def test_error_add_files_invalid_owner(self) -> None:
        with Runner() as runner:
            with self.assertRaises(ValueError):
                runner.add_files("steve", owner="not_an_owner")


class OverrideCmdAndEntrypointTestCase(unittest.TestCase):
    ...


#     def test_override_image_cmd(self) -> None:
#         dockerfile = """FROM jameslp/autograder-runner:3.1.2
# CMD ["echo", "goodbye"]
# """
#         tag = "runner_test_image_with_cmd"
#         with tempfile.TemporaryDirectory() as temp_dir:
#             with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
#                 f.write(dockerfile)
#             subprocess.run(
#                 "docker build -t {} {}".format(tag, temp_dir), check=True, shell=True
#             )

#         with Runner(docker_image=tag) as runner:
#             time.sleep(2)
#             result = runner.run_command(["echo", "hello"])
#             self.assertEqual(0, result.return_code)
#             self.assertEqual("hello\n", result.stdout.decode())

#     def test_override_image_entrypoint(self) -> None:
#         dockerfile = """FROM jameslp/autograder-runner:3.1.2
# ENTRYPOINT ["echo", "goodbye"]
# """
#         tag = "runner_test_image_with_entrypoint"
#         with tempfile.TemporaryDirectory() as temp_dir:
#             with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
#                 f.write(dockerfile)
#             subprocess.run(
#                 "docker build -t {} {}".format(tag, temp_dir), check=True, shell=True
#             )

#         with Runner(docker_image=tag) as runner:
#             time.sleep(2)
#             result = runner.run_command(["echo", "hello"])
#             self.assertEqual(0, result.return_code)
#             self.assertEqual("hello\n", result.stdout.decode())

#     def test_override_image_cmd_and_entrypoint(self) -> None:
#         dockerfile = """FROM jameslp/autograder-runner:3.1.2
# ENTRYPOINT ["echo", "goodbye"]
# CMD ["echo", "goodbye"]
# """
#         tag = "runner_test_image_with_cmd_and_entrypoint"
#         with tempfile.TemporaryDirectory() as temp_dir:
#             with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
#                 f.write(dockerfile)
#             subprocess.run(
#                 "docker build -t {} {}".format(tag, temp_dir), check=True, shell=True
#             )

#         with Runner(docker_image=tag) as runner:
#             time.sleep(2)
#             result = runner.run_command(["echo", "hello"])
#             self.assertEqual(0, result.return_code)
#             self.assertEqual("hello\n", result.stdout.decode())


if __name__ == "__main__":
    unittest.main()
