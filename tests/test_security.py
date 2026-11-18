"""Automated tests for NOVA's Security & Sandboxing Engine (Phase 4)."""

import pytest
from pathlib import Path
from local_agent.security import (
    PathSandbox,
    PathTraversalError,
    AccessDeniedError,
    TerminalAllowlist,
    BlockedCommandError,
    SecurityAuditLogger,
)


class TestPathSandbox:
    """Verify filesystem confinement and secret protection."""

    def test_valid_path_within_sandbox(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        test_file = tmp_path / "valid_doc.txt"
        test_file.write_text("hello", encoding="utf-8")

        resolved = sandbox.validate_path(test_file)
        assert resolved == test_file.resolve()

    def test_relative_path_resolved_in_primary_root(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        resolved = sandbox.validate_path("subfolder/file.txt")
        assert resolved == (tmp_path / "subfolder/file.txt").resolve()

    def test_directory_traversal_rejected(self, tmp_path: Path):
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        sandbox = PathSandbox(allowed_roots=[sandbox_dir])

        with pytest.raises(PathTraversalError, match="outside the permitted sandbox"):
            sandbox.validate_path(sandbox_dir / ".." / "outside.txt")

    def test_unc_path_rejected(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        with pytest.raises(PathTraversalError, match="UNC paths are forbidden"):
            sandbox.validate_path(r"\\192.168.1.1\c$\passwords.txt")

    def test_null_byte_rejected(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        with pytest.raises(PathTraversalError, match="Null bytes"):
            sandbox.validate_path("safe.txt\x00.exe")

    def test_sensitive_files_access_denied(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path])
        sensitive_names = [".env", ".env.local", "credentials.json", "secret_key.pem", "id_rsa"]

        for name in sensitive_names:
            target = tmp_path / name
            with pytest.raises(AccessDeniedError, match="forbidden"):
                sandbox.validate_path(target)

    def test_windows_system_directory_blocked(self, tmp_path: Path):
        sandbox = PathSandbox(allowed_roots=[tmp_path, "C:\\"])
        with pytest.raises(AccessDeniedError, match="protected system directory"):
            sandbox.validate_path(r"C:\Windows\System32\cmd.exe")


class TestTerminalAllowlist:
    """Verify shell command allowlist and dangerous pattern detection."""

    def test_allowed_commands_pass(self):
        allowlist = TerminalAllowlist()
        cmd, args = allowlist.validate_command("python --version")
        assert cmd.lower() in ("python", "python.exe")
        assert args == ["--version"]

        cmd, args = allowlist.validate_command("git status -s")
        assert cmd.lower() in ("git", "git.exe")
        assert args == ["status", "-s"]

    def test_unregistered_command_blocked(self):
        allowlist = TerminalAllowlist()
        with pytest.raises(BlockedCommandError, match="not in the approved command allowlist"):
            allowlist.validate_command("malicious_tool.exe --attack")

    def test_format_drive_blocked(self):
        allowlist = TerminalAllowlist()
        with pytest.raises(BlockedCommandError, match="prohibited or destructive pattern"):
            allowlist.validate_command("format C: /fs:ntfs")

    def test_recursive_delete_blocked(self):
        allowlist = TerminalAllowlist()
        with pytest.raises(BlockedCommandError, match="prohibited or destructive pattern"):
            allowlist.validate_command("del /s C:\\*.*")

    def test_encoded_powershell_blocked(self):
        allowlist = TerminalAllowlist()
        with pytest.raises(BlockedCommandError, match="prohibited or destructive pattern"):
            allowlist.validate_command("powershell -enc JABzACAAPQAg...")

    def test_git_force_destructive_flags_blocked(self):
        allowlist = TerminalAllowlist()
        with pytest.raises(BlockedCommandError, match="Force push/modify"):
            allowlist.validate_command("git push --force origin main")

        with pytest.raises(BlockedCommandError, match="Destructive Git operations"):
            allowlist.validate_command("git reset --hard HEAD~1")


class TestSecurityAuditLogger:
    """Verify tamper-evident audit logging."""

    def test_audit_log_written_and_read(self, tmp_path: Path):
        log_file = tmp_path / "logs" / "audit.jsonl"
        logger = SecurityAuditLogger(log_file)

        logger.log(
            action="file_read",
            resource="notes.txt",
            permission_level="SAFE",
            success=True,
            details={"bytes_read": 128},
        )
        logger.log(
            action="terminal_run",
            resource="format C:",
            permission_level="SENSITIVE",
            success=False,
            error="BlockedCommandError",
        )

        records = logger.read_records()
        assert len(records) == 2
        assert records[0].action == "file_read"
        assert records[0].success is True
        assert records[1].action == "terminal_run"
        assert records[1].success is False
        assert records[1].error == "BlockedCommandError"
