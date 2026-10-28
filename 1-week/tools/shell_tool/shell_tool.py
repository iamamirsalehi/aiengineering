import os
import re
import resource
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Collection
from pathlib import Path, PurePosixPath
from typing import Any

from tools.file_system.path_guard import PathGuard
from tools.tool import Tool


class ShellTool(Tool):
    """Run a single allowlisted command in an isolated local sandbox."""

    NAME = "run_shell"
    DEFAULT_ALLOWED_COMMANDS = frozenset(
        {
            "basename",
            "cat",
            "cut",
            "date",
            "dirname",
            "du",
            "echo",
            "grep",
            "head",
            "ls",
            "md5sum",
            "printf",
            "pwd",
            "sha256sum",
            "stat",
            "tail",
            "tr",
            "uniq",
            "wc",
        }
    )
    COMMAND_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    MAX_ALLOWED_COMMANDS = 64
    MAX_ARGUMENTS = 32
    MAX_ARGUMENT_LENGTH = 4_096
    MAX_TIMEOUT_SECONDS = 10
    MAX_OUTPUT_BYTES = 20_000
    PROCESS_OUTPUT_LIMIT_BYTES = 1_000_000
    ADDRESS_SPACE_LIMIT_BYTES = 512 * 1024 * 1024
    OPEN_FILE_LIMIT = 64

    def __init__(
        self,
        path_guard: PathGuard,
        allowed_commands: Collection[str] | None = None,
        bubblewrap_path: str | None = None,
    ) -> None:
        self.path_guard = path_guard
        self.allowed_commands = frozenset(
            allowed_commands
            if allowed_commands is not None
            else self._commands_from_environment()
        )
        self._validate_allowed_commands(self.allowed_commands)
        self.bubblewrap_path = bubblewrap_path or shutil.which(
            "bwrap", path="/usr/bin:/bin"
        )
        command_names = ", ".join(sorted(self.allowed_commands))
        self._definition = {
            "type": "function",
            "function": {
                "name": self.NAME,
                "description": (
                    "Run one non-interactive command in the sandboxed agent files "
                    "directory. Pass an argv array, not shell text: pipes, redirects, "
                    "command substitution, and chaining are not interpreted. Network "
                    "access and inherited environment secrets are unavailable. Use the "
                    "file tools for writes and deletion. Allowed commands: "
                    f"{command_names}."
                ),
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "description": (
                                "The executable name followed by its separate arguments."
                            ),
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": self.MAX_ARGUMENTS,
                        },
                        "working_directory": {
                            "type": "string",
                            "description": (
                                "Relative directory inside agent files, or '.' for root."
                            ),
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "description": "Execution timeout from 1 to 10 seconds.",
                            "minimum": 1,
                            "maximum": self.MAX_TIMEOUT_SECONDS,
                        },
                    },
                    "required": [
                        "argv",
                        "working_directory",
                        "timeout_seconds",
                    ],
                    "additionalProperties": False,
                },
            },
        }

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def definition(self) -> dict[str, Any]:
        return self._definition

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        argv, working_directory, timeout_seconds = self._validate_arguments(
            arguments
        )
        if self.bubblewrap_path is None:
            raise RuntimeError(
                "The run_shell tool requires Bubblewrap (the 'bwrap' executable)."
            )

        self.path_guard.ensure_root()
        host_working_directory = self.path_guard.resolve(
            working_directory,
            must_exist=True,
            allow_root=True,
        )
        if not host_working_directory.is_dir():
            raise ValueError("working_directory must be a directory.")

        trash_directory = self.path_guard.root / self.path_guard.RESERVED_DIRECTORY
        if trash_directory.is_symlink():
            raise RuntimeError("The protected trash path must not be a symbolic link.")
        try:
            trash_directory.mkdir(exist_ok=True)
        except OSError as error:
            raise RuntimeError(
                f"Could not prepare the protected trash directory: {error}"
            ) from error

        executable_path = self._resolve_executable(argv[0])
        sandbox_command = self._build_sandbox_command(
            executable_path,
            argv[1:],
            host_working_directory,
        )

        with (
            tempfile.TemporaryFile() as stdout_file,
            tempfile.TemporaryFile() as stderr_file,
        ):
            timed_out = False
            try:
                completed = subprocess.run(
                    sandbox_command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    check=False,
                    cwd="/",
                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                    timeout=timeout_seconds,
                    start_new_session=True,
                    preexec_fn=self._resource_limiter(timeout_seconds),
                )
                exit_code: int | None = completed.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = None
            except (OSError, subprocess.SubprocessError) as error:
                raise RuntimeError(
                    f"Could not start the shell sandbox: {error}"
                ) from error

            stdout, stdout_truncated = self._read_output(stdout_file)
            stderr, stderr_truncated = self._read_output(stderr_file)

        return {
            "argv": argv,
            "working_directory": self.path_guard.relative_name(
                host_working_directory
            ),
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "truncated": stdout_truncated or stderr_truncated,
        }

    @classmethod
    def _commands_from_environment(cls) -> Collection[str]:
        configured = os.environ.get("SHELL_ALLOWED_COMMANDS")
        if configured is None:
            return cls.DEFAULT_ALLOWED_COMMANDS
        commands = {command.strip() for command in configured.split(",")}
        commands.discard("")
        if not commands:
            raise ValueError("SHELL_ALLOWED_COMMANDS must contain at least one command.")
        return commands

    @classmethod
    def _validate_allowed_commands(cls, commands: Collection[str]) -> None:
        if not commands:
            raise ValueError("At least one shell command must be allowed.")
        if len(commands) > cls.MAX_ALLOWED_COMMANDS:
            raise ValueError(
                f"At most {cls.MAX_ALLOWED_COMMANDS} shell commands may be allowed."
            )
        invalid = [
            command
            for command in commands
            if not isinstance(command, str)
            or cls.COMMAND_NAME_PATTERN.fullmatch(command) is None
        ]
        if invalid:
            raise ValueError(
                "Allowed shell commands must be bare executable names of at most "
                "64 characters, without paths."
            )

    def _validate_arguments(
        self, arguments: dict[str, Any]
    ) -> tuple[list[str], str, int]:
        required = {"argv", "working_directory", "timeout_seconds"}
        if set(arguments) != required:
            raise ValueError(
                "Shell tool requires argv, working_directory, and timeout_seconds."
            )

        argv = arguments["argv"]
        working_directory = arguments["working_directory"]
        timeout_seconds = arguments["timeout_seconds"]

        if not isinstance(argv, list) or not 1 <= len(argv) <= self.MAX_ARGUMENTS:
            raise ValueError(
                f"argv must contain between 1 and {self.MAX_ARGUMENTS} strings."
            )
        if any(
            not isinstance(argument, str)
            or not argument
            or "\x00" in argument
            or len(argument) > self.MAX_ARGUMENT_LENGTH
            for argument in argv
        ):
            raise ValueError(
                "Every argv item must be a non-empty string of at most "
                f"{self.MAX_ARGUMENT_LENGTH} characters without null bytes."
            )
        if not isinstance(working_directory, str):
            raise ValueError("working_directory must be a relative path string.")
        if type(timeout_seconds) is not int or not (
            1 <= timeout_seconds <= self.MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"timeout_seconds must be an integer from 1 to {self.MAX_TIMEOUT_SECONDS}."
            )

        executable = argv[0]
        if self.COMMAND_NAME_PATTERN.fullmatch(executable) is None:
            raise ValueError("argv[0] must be a bare executable name without a path.")
        if executable not in self.allowed_commands:
            allowed = ", ".join(sorted(self.allowed_commands))
            raise ValueError(
                f"Command '{executable}' is not allowed. Allowed commands: {allowed}."
            )
        return argv, working_directory, timeout_seconds

    @staticmethod
    def _resolve_executable(executable: str) -> str:
        located = shutil.which(executable, path="/usr/bin:/bin")
        if located is None:
            raise ValueError(f"Allowed command is not installed: {executable}.")
        resolved = Path(located).resolve()
        try:
            resolved.relative_to("/usr")
        except ValueError as error:
            raise ValueError(
                f"Command must resolve inside /usr: {executable}."
            ) from error
        return resolved.as_posix()

    def _build_sandbox_command(
        self,
        executable_path: str,
        arguments: list[str],
        host_working_directory: Path,
    ) -> list[str]:
        relative_working_directory = host_working_directory.relative_to(
            self.path_guard.root
        )
        sandbox_working_directory = PurePosixPath("/workspace")
        if relative_working_directory.parts:
            sandbox_working_directory /= PurePosixPath(
                relative_working_directory.as_posix()
            )

        return [
            str(self.bubblewrap_path),
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib",
            "/lib64",
            "--dir",
            "/workspace",
            "--bind",
            self.path_guard.root.as_posix(),
            "/workspace",
            "--tmpfs",
            f"/workspace/{self.path_guard.RESERVED_DIRECTORY}",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--chdir",
            sandbox_working_directory.as_posix(),
            "--clearenv",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--",
            executable_path,
            *arguments,
        ]

    @classmethod
    def _resource_limiter(cls, timeout_seconds: int) -> Callable[[], None]:
        def apply_limits() -> None:
            limits = {
                resource.RLIMIT_CPU: timeout_seconds + 1,
                resource.RLIMIT_AS: cls.ADDRESS_SPACE_LIMIT_BYTES,
                resource.RLIMIT_FSIZE: cls.PROCESS_OUTPUT_LIMIT_BYTES,
                resource.RLIMIT_NOFILE: cls.OPEN_FILE_LIMIT,
            }
            for limit_type, desired_limit in limits.items():
                _, current_hard_limit = resource.getrlimit(limit_type)
                applied_limit = (
                    desired_limit
                    if current_hard_limit == resource.RLIM_INFINITY
                    else min(desired_limit, current_hard_limit)
                )
                resource.setrlimit(limit_type, (applied_limit, applied_limit))

        return apply_limits

    @classmethod
    def _read_output(cls, output_file: Any) -> tuple[str, bool]:
        output_file.seek(0)
        content = output_file.read(cls.MAX_OUTPUT_BYTES + 1)
        truncated = len(content) > cls.MAX_OUTPUT_BYTES
        return (
            content[: cls.MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            truncated,
        )
