"""Pure backend functions for Git Manager.

This module contains all Git operations, data structures, and constants.
It has NO dependency on any GUI toolkit (tkinter, ttkbootstrap, PySide6).
Both the Qt UI (qt_app.py) and legacy Tk UI (app.py) import from here.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODULEFILES_DIR = Path(r"F:\Working Files\Coding\ModuleFiles")
GITHUB_USER = "powerfulhang"
GITHUB_EMAIL = "hangshi1023@gmail.com"
DEFAULT_BRANCH = "main"
REMOTE_NAME = "origin"
AUTO_GENERATED_CONFIG_FILES = [".gitignore", ".gitattributes"]
GH_CANDIDATES = [
    Path(r"C:\tmp\gh_2.92.0_windows_amd64\bin\gh.exe"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class BranchInfo:
    name: str
    upstream: str
    commit: str
    date: str
    subject: str
    is_current: bool = False
    is_remote: bool = False


@dataclass
class ReleaseInfo:
    title: str
    status: str
    tag: str
    published_at: str
    source: str = "GitHub"


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------
def run_command(command: list[str], cwd: Path, timeout: int = 60) -> CommandResult:
    """Run an external command and capture output.

    Ref: Python Standard Library, subprocess.run:
    https://docs.python.org/3/library/subprocess.html#subprocess.run
    """
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        return CommandResult(command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(command, 124, exc.stdout or "", exc.stderr or "Timed out")
    return CommandResult(command, result.returncode, result.stdout, result.stderr)


# ---------------------------------------------------------------------------
# Project / naming helpers
# ---------------------------------------------------------------------------
def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name.strip())
    cleaned = cleaned.strip(" .-")
    if cleaned:
        return cleaned
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"Project-{stamp}"


# ---------------------------------------------------------------------------
# ModuleFiles
# ---------------------------------------------------------------------------
def list_module_files() -> list[Path]:
    """List direct files in the ModuleFiles directory."""
    if not MODULEFILES_DIR.exists():
        return []
    return sorted(path for path in MODULEFILES_DIR.iterdir() if path.is_file())


def copy_module_file(source: Path, destination: Path) -> None:
    """Copy a ModuleFiles template file to the project directory."""
    destination.write_bytes(source.read_bytes())


# ---------------------------------------------------------------------------
# Git config files
# ---------------------------------------------------------------------------
def _ensure_config_file(file_path: Path, lines: list[str]) -> None:
    """Create or extend a config file with the given lines."""
    existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    missing = [line for line in lines if line and line not in existing]
    if not file_path.exists():
        file_path.write_text("\n".join(lines), encoding="utf-8")
        return
    if missing:
        suffix = "" if existing.endswith("\n") else "\n"
        file_path.write_text(existing + suffix + "\n".join(missing) + "\n", encoding="utf-8")


def ensure_gitignore(project_path: Path) -> None:
    """Create or extend .gitignore with defaults."""
    _ensure_config_file(
        project_path / ".gitignore",
        [
            "# ModuleFiles links and local automation",
            "AGENTS*.md",
            "",
            "# Python temporary files",
            "__pycache__/",
            "*.py[cod]",
            ".pytest_cache/",
            ".mypy_cache/",
            ".ruff_cache/",
            "",
            "# Virtual environments",
            ".venv/",
            "venv/",
            "*-venv/",
            "",
            "# Editor and OS files",
            ".idea/",
            ".vscode/",
            ".DS_Store",
            "Thumbs.db",
            "",
        ],
    )


def ensure_gitattributes(project_path: Path) -> None:
    """Create .gitattributes to keep line endings predictable on Windows."""
    _ensure_config_file(
        project_path / ".gitattributes",
        [
            "* text=auto",
            "*.py text eol=lf",
            "*.toml text eol=lf",
            "*.md text eol=lf",
            "*.ps1 text eol=crlf",
            "*.cmd text eol=crlf",
            "",
        ],
    )


# ---------------------------------------------------------------------------
# GitHub remote helpers
# ---------------------------------------------------------------------------
def github_remote(repo_name: str) -> str:
    return f"ssh://git@ssh.github.com:443/{GITHUB_USER}/{repo_name}.git"


def find_gh_executable() -> str | None:
    """Return a usable GitHub CLI executable when one is available."""
    found = shutil.which("gh")
    if found:
        return found
    for candidate in GH_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def repository_name_from_remote_url(remote_url: str) -> str | None:
    """Extract a GitHub repository name from common remote URL forms."""
    url = remote_url.strip()
    if not url:
        return None

    path = ""
    if "://" in url:
        parsed = urlparse(url)
        path = parsed.path
    elif ":" in url and "@" in url.split(":", 1)[0]:
        path = url.split(":", 1)[1]
    else:
        path = url

    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    repo_name = parts[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return sanitize_project_name(repo_name) or None


def repository_owner_name_from_remote_url(remote_url: str) -> str | None:
    """Extract owner/repo from common GitHub remote URL forms."""
    url = remote_url.strip()
    if not url:
        return None

    path = ""
    if "://" in url:
        path = urlparse(url).path
    elif ":" in url and "@" in url.split(":", 1)[0]:
        path = url.split(":", 1)[1]
    else:
        path = url

    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    owner = parts[-2]
    repo = parts[-1][:-4] if parts[-1].endswith(".git") else parts[-1]
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def configured_repo_full_name(project_path: Path, repo_name: str) -> str:
    remote = configured_or_default_remote(project_path, repo_name)
    return repository_owner_name_from_remote_url(remote) or f"{GITHUB_USER}/{repo_name}"


def configured_or_default_remote(project_path: Path, repo_name: str) -> str:
    current = run_command(["git", "remote", "get-url", REMOTE_NAME], project_path)
    if current.returncode == 0 and current.stdout.strip():
        return current.stdout.strip()
    return github_remote(repo_name)


def explain_remote_result(result: CommandResult, repo_name: str) -> tuple[bool, str]:
    detail = (result.stderr or result.stdout).strip()
    detail_lower = detail.lower()
    if result.returncode == 0:
        return True, "远程连接成功：SSH 443 可用，GitHub 仓库可访问。"
    if "repository not found" in detail_lower:
        return (
            False,
            "远程连接失败：SSH 443 已能连到 GitHub，但仓库不存在或当前 SSH 密钥"
            f"没有权限。请先在 GitHub 创建仓库 {GITHUB_USER}/{repo_name}。",
        )
    if "permission denied" in detail_lower:
        return (
            False,
            "远程连接失败：GitHub 拒绝了当前 SSH 密钥。"
            "请检查 SSH key 是否已添加到 GitHub 账户。",
        )
    if "could not resolve hostname" in detail_lower:
        return False, "远程连接失败：无法解析 GitHub SSH 主机名，请检查网络或 DNS。"
    if "connection timed out" in detail_lower:
        return False, "远程连接失败：连接超时，可能是网络或防火墙拦截。"
    return False, f"远程连接失败：{detail or '未知错误'}"


# ---------------------------------------------------------------------------
# Git status / log formatting
# ---------------------------------------------------------------------------
def summarize_git_status(status_text: str) -> str:
    lines = [line for line in status_text.splitlines() if line.strip()]
    if not lines:
        return "状态详情：没有未提交的文件改动。"

    summary: list[str] = []
    changes: list[str] = []
    for line in lines:
        if line.startswith("## "):
            branch = line[3:]
            branch = branch.replace("...", " 跟踪 ")
            summary.append(f"当前分支：{branch}")
            continue

        code = line[:2]
        path = line[3:] if len(line) > 3 else line
        if code == "??":
            changes.append(f"未跟踪：{path}")
        elif code[0] != " " and code[1] != " ":
            changes.append(f"已暂存且又有新改动：{path}")
        elif code[0] != " ":
            changes.append(f"已暂存：{path}")
        elif code[1] != " ":
            changes.append(f"未暂存：{path}")
        else:
            changes.append(f"有改动：{path}")

    if not changes:
        summary.append("文件状态：没有未提交的文件改动。")
    else:
        summary.append(f"文件状态：共 {len(changes)} 项改动。")
        summary.extend(f"- {change}" for change in changes)
    return "\n".join(summary)


def summarize_git_log(log_text: str) -> str:
    lines = [line for line in log_text.splitlines() if line.strip()]
    if not lines:
        return "最近提交：当前仓库还没有提交记录。"

    summary = ["最近提交："]
    for line in lines:
        parts = line.split("\t", 2)
        if len(parts) == 3:
            commit_hash, refs, subject = parts
            refs_text = f" [{refs}]" if refs else ""
            summary.append(f"- {commit_hash}{refs_text}: {subject}")
        else:
            summary.append(f"- {line}")
    return "\n".join(summary)


def summarize_simple_git_result(action: str, result: CommandResult) -> str:
    detail = (result.stderr or result.stdout).strip()
    if result.returncode == 0:
        if action == "add":
            warning = "；Git 提示了换行符转换警告" if detail else ""
            return f"添加完成：当前改动已加入暂存区{warning}。"
        if action == "commit":
            if "nothing to commit" in detail.lower():
                return "提交未创建：当前没有可提交的暂存改动。"
            first_line = detail.splitlines()[0] if detail else ""
            suffix = f"（{first_line}）" if first_line else ""
            return f"提交成功：已创建本地提交{suffix}。"
        if action == "fetch":
            return "获取完成：已从远程仓库更新分支信息，本地文件没有被修改。"
        if action == "pull":
            return "拉取完成：远程更新已合并到当前分支。"
    return f"操作失败：{detail or 'Git 返回了非零状态。'}"


# ---------------------------------------------------------------------------
# Git branch / status queries
# ---------------------------------------------------------------------------
def current_git_branch(project_path: Path) -> tuple[str | None, str | None]:
    """Return the current branch name for push/pull."""
    branch_result = run_command(["git", "branch", "--show-current"], project_path)
    if branch_result.returncode == 0 and branch_result.stdout.strip():
        return branch_result.stdout.strip(), None

    result = run_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        project_path,
    )
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()
    branch = result.stdout.strip()
    if not branch or branch == "HEAD":
        return None, "当前仓库处于 detached HEAD 状态，无法确定要推送的分支。"
    return branch, None


def current_git_upstream(project_path: Path) -> str:
    result = run_command(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        project_path,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_dirty_count(project_path: Path) -> int:
    result = run_command(["git", "status", "--short"], project_path)
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def git_ahead_behind(project_path: Path) -> tuple[int | None, int | None]:
    upstream = current_git_upstream(project_path)
    if not upstream:
        return None, None
    result = run_command(
        ["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
        project_path,
    )
    if result.returncode != 0:
        return None, None
    parts = result.stdout.split()
    if len(parts) != 2:
        return None, None
    return int(parts[0]), int(parts[1])


def list_branches(project_path: Path) -> list[BranchInfo]:
    """List local and origin branches with upstream and commit context."""
    current, _error = current_git_branch(project_path)
    result = run_command(
        [
            "git",
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short)|%(upstream:short)|%(objectname:short)|%(committerdate:short)|%(subject)",
            "refs/heads",
            f"refs/remotes/{REMOTE_NAME}",
        ],
        project_path,
    )
    if result.returncode != 0:
        return []

    branches: list[BranchInfo] = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        name, upstream, commit, date, subject = parts
        if name == f"{REMOTE_NAME}/HEAD":
            continue
        is_remote = name.startswith(f"{REMOTE_NAME}/")
        local_name = name[len(f"{REMOTE_NAME}/"):] if is_remote else name
        branches.append(
            BranchInfo(
                name=name,
                upstream=upstream,
                commit=commit,
                date=date,
                subject=subject,
                is_current=local_name == current and not is_remote,
                is_remote=is_remote,
            )
        )
    return branches


def list_release_info(project_path: Path, repo_name: str) -> tuple[list[ReleaseInfo], str | None]:
    """Read GitHub releases through gh, falling back to local tags."""
    repo = configured_repo_full_name(project_path, repo_name)
    gh = find_gh_executable()
    if gh:
        result = run_command(
            [gh, "release", "list", "--repo", repo, "--limit", "20"],
            project_path,
            timeout=20,
        )
        if result.returncode == 0:
            releases: list[ReleaseInfo] = []
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    releases.append(
                        ReleaseInfo(
                            title=parts[0],
                            status=parts[1],
                            tag=parts[2],
                            published_at=parts[3],
                        )
                    )
            return releases, None
        gh_error = (result.stderr or result.stdout).strip()
        tags = run_command(["git", "tag", "--list", "--sort=-creatordate"], project_path)
        if tags.returncode == 0 and tags.stdout.strip():
            releases = [
                ReleaseInfo(tag, "local tag", tag, "", source="Git")
                for tag in tags.stdout.splitlines()
                if tag.strip()
            ]
            return releases, f"GitHub release 读取失败，已退回本地 tag：{gh_error}"
        return [], gh_error

    tags = run_command(["git", "tag", "--list", "--sort=-creatordate"], project_path)
    if tags.returncode != 0:
        return [], (tags.stderr or tags.stdout).strip()
    releases = [
        ReleaseInfo(tag, "local tag", tag, "", source="Git")
        for tag in tags.stdout.splitlines()
        if tag.strip()
    ]
    return releases, "未找到 GitHub CLI，只显示本地 tag。"


def has_local_commits(project_path: Path) -> bool:
    """Return whether HEAD points to an existing commit."""
    result = run_command(["git", "rev-parse", "--verify", "HEAD"], project_path)
    return result.returncode == 0


def remote_default_branch(project_path: Path) -> str | None:
    """Return origin's default branch after fetch/ls-remote when possible."""
    symbolic = run_command(
        ["git", "symbolic-ref", "--short", f"refs/remotes/{REMOTE_NAME}/HEAD"],
        project_path,
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        name = symbolic.stdout.strip()
        prefix = f"{REMOTE_NAME}/"
        return name[len(prefix):] if name.startswith(prefix) else name

    remote_head = run_command(
        ["git", "ls-remote", "--symref", REMOTE_NAME, "HEAD"],
        project_path,
    )
    for line in remote_head.stdout.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            return line.split("refs/heads/", 1)[1].split("\t", 1)[0]
    return None


# ---------------------------------------------------------------------------
# Backup helpers for first-pull conflicts
# ---------------------------------------------------------------------------
def untracked_file_exists(project_path: Path, relative_path: str) -> bool:
    result = run_command(["git", "status", "--porcelain", "--", relative_path], project_path)
    return result.returncode == 0 and result.stdout.startswith("?? ")


def remote_file_exists(project_path: Path, branch: str, relative_path: str) -> bool:
    result = run_command(
        ["git", "cat-file", "-e", f"{REMOTE_NAME}/{branch}:{relative_path}"],
        project_path,
    )
    return result.returncode == 0


def backup_first_pull_conflicts(project_path: Path, branch: str) -> list[Path]:
    """Move auto-generated config files away before a first pull."""
    conflicts = [
        relative_path
        for relative_path in AUTO_GENERATED_CONFIG_FILES
        if (project_path / relative_path).exists()
        and untracked_file_exists(project_path, relative_path)
        and remote_file_exists(project_path, branch, relative_path)
    ]
    if not conflicts:
        return []

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = project_path / ".git" / "git-manager-backups"
    backup_dir = backup_root / f"first-pull-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: list[Path] = []
    for relative_path in conflicts:
        source = project_path / relative_path
        target = backup_dir / relative_path
        source.replace(target)
        backups.append(target)
    return backups


def restore_backups(project_path: Path, backups: list[Path]) -> None:
    for backup in backups:
        target = project_path / backup.name
        if not target.exists():
            backup.replace(target)


# ---------------------------------------------------------------------------
# Git remote / repository initialization
# ---------------------------------------------------------------------------
def configure_git_remote(project_path: Path, remote_url: str) -> CommandResult:
    """Add or update the Git remote URL."""
    current = run_command(["git", "remote", "get-url", REMOTE_NAME], project_path)
    command = (
        ["git", "remote", "set-url", REMOTE_NAME, remote_url]
        if current.returncode == 0
        else ["git", "remote", "add", REMOTE_NAME, remote_url]
    )
    return run_command(command, project_path)


def initialize_git_repository(
    project_path: Path,
    repo_name: str,
    branch: str,
) -> list[CommandResult]:
    """Initialize Git with local defaults and a GitHub SSH 443 remote."""
    ensure_gitignore(project_path)
    ensure_gitattributes(project_path)
    remote_url = github_remote(repo_name)
    inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], project_path)
    init_result = (
        CommandResult(["git", "init", "-b", branch], 0, "Already a Git repository", "")
        if inside.returncode == 0
        else run_command(["git", "init", "-b", branch], project_path)
    )
    results = [
        init_result,
        run_command(["git", "config", "user.name", GITHUB_USER], project_path),
        run_command(["git", "config", "user.email", GITHUB_EMAIL], project_path),
        configure_git_remote(project_path, remote_url),
    ]
    return results
