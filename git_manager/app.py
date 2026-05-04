from __future__ import annotations

import argparse
import datetime as dt
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable
from urllib.parse import urlparse

import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


MODULEFILES_DIR = Path(r"F:\Working Files\Coding\ModuleFiles")
GITHUB_USER = "powerfulhang"
GITHUB_EMAIL = "hangshi1023@gmail.com"
DEFAULT_BRANCH = "main"
REMOTE_NAME = "origin"
AUTO_GENERATED_CONFIG_FILES = [".gitignore", ".gitattributes"]
GH_CANDIDATES = [
    Path(r"C:\tmp\gh_2.92.0_windows_amd64\bin\gh.exe"),
]

WINDOW_SIZE = (1024, 660)
WINDOW_MIN_SIZE = (980, 620)
SIDEBAR_WIDTH = 72
STATUS_MAX_CHARS = 135
NAV_ITEMS = [
    ("＋", "新建"),
    ("▦", "概览"),
    ("⑂", "分支"),
    ("✓", "提交"),
    ("◇", "发布"),
]
NAV_MAP = {"新建": "新建项目", "概览": "概览", "分支": "分支", "提交": "提交", "发布": "发布"}


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


def run_command(command: list[str], cwd: Path, timeout: int = 60) -> CommandResult:
    """Run an external command and capture output.

    Ref: Python Standard Library, subprocess.run:
    https://docs.python.org/3/library/subprocess.html#subprocess.run
    `capture_output` and `text` require Python 3.7+.
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


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name.strip())
    cleaned = cleaned.strip(" .-")
    if cleaned:
        return cleaned
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"Project-{stamp}"


def list_module_files() -> list[Path]:
    """List direct files in the ModuleFiles directory.

    Ref: Python Standard Library, pathlib.Path.iterdir:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir
    """
    if not MODULEFILES_DIR.exists():
        return []
    return sorted(path for path in MODULEFILES_DIR.iterdir() if path.is_file())


def copy_module_file(source: Path, destination: Path) -> None:
    """Copy a ModuleFiles template file to the project directory.

    Ref: Python Standard Library, pathlib.Path.read_bytes/write_bytes:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.read_bytes
    """
    destination.write_bytes(source.read_bytes())


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


def github_remote(repo_name: str) -> str:
    return f"ssh://git@ssh.github.com:443/{GITHUB_USER}/{repo_name}.git"


def find_gh_executable() -> str | None:
    """Return a usable GitHub CLI executable when one is available.

    Ref: GitHub CLI manual, `gh release` manages releases:
    https://cli.github.com/manual/gh_release
    """
    found = shutil.which("gh")
    if found:
        return found
    for candidate in GH_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def repository_name_from_remote_url(remote_url: str) -> str | None:
    """Extract a GitHub repository name from common remote URL forms.

    Ref: Python Standard Library, urllib.parse.urlparse:
    https://docs.python.org/3/library/urllib.parse.html#urllib.parse.urlparse
    """
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


def current_git_branch(project_path: Path) -> tuple[str | None, str | None]:
    """Return the current branch name for push/pull.

    Ref: Git branch manual, --show-current:
    https://git-scm.com/docs/git-branch
    Ref: Git rev-parse manual, --abbrev-ref:
    https://git-scm.com/docs/git-rev-parse
    """
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
    """List local and origin branches with upstream and commit context.

    Ref: Git for-each-ref manual, `--format` prints selected ref fields:
    https://git-scm.com/docs/git-for-each-ref
    """
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
        local_name = name[len(f"{REMOTE_NAME}/") :] if is_remote else name
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
        return name[len(prefix) :] if name.startswith(prefix) else name

    remote_head = run_command(
        ["git", "ls-remote", "--symref", REMOTE_NAME, "HEAD"],
        project_path,
    )
    for line in remote_head.stdout.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            return line.split("refs/heads/", 1)[1].split("\t", 1)[0]
    return None


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
    """Move auto-generated config files away before a first pull.

    Ref: Python Standard Library, pathlib.Path.replace:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.replace
    """
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


def configure_git_remote(project_path: Path, remote_url: str) -> CommandResult:
    """Add or update the Git remote URL.

    Ref: Python Standard Library, subprocess.run:
    https://docs.python.org/3/library/subprocess.html#subprocess.run
    """
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


class Tooltip:
    """Small hover tooltip for Tk widgets.

    Ref: Python Standard Library, tkinter widget bindings:
    https://docs.python.org/3/library/tkinter.html
    """

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, _event: tk.Event | None = None) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=360,
        )
        label.pack()

    def hide(self, _event: tk.Event | None = None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class GitManagerApp(ttkb.Window):
    def __init__(self, start_dir: Path) -> None:
        super().__init__(title="Git Manager", themename="cosmo", size=WINDOW_SIZE)
        self.minsize(*WINDOW_MIN_SIZE)
        self.configure(background="#f8fafc")
        self.start_dir = start_dir
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.dialog_title = "操作结果"
        self.dialog_lines: list[str] = []
        self.module_vars: dict[Path, tk.BooleanVar] = {}
        self._current_view = ""
        self._views: dict[str, ttk.Frame] = {}
        self._nav_buttons: dict[str, tk.Button] = {}
        self._nav_indicators: dict[str, tk.Frame] = {}

        # Shared variables
        self.project_path_var = tk.StringVar(value=str(self.start_dir))
        self.repo_name_var = tk.StringVar(value=self.start_dir.name)
        self.branch_var = tk.StringVar(value=DEFAULT_BRANCH)
        self.commit_message_var = tk.StringVar(value="Update project")
        self.current_branch_var = tk.StringVar(value="-")
        self.upstream_var = tk.StringVar(value="-")
        self.sync_state_var = tk.StringVar(value="-")
        self.worktree_state_var = tk.StringVar(value="-")
        self.latest_release_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Ready")
        self.status_display_var = tk.StringVar(value="Ready")
        self.status_var.trace_add("write", self._sync_status_display)

        self._build_ui()
        self._load_module_files()
        self._poll_output()
        self.refresh_git_status()
        self._show_view("概览")

    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        Tooltip(widget, text)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self)
        shell.pack(fill=BOTH, expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)

        # Main container
        main = ttk.Frame(shell)
        main.grid(row=0, column=0, sticky=NSEW)

        # Sidebar
        self._build_sidebar(main)

        # Content area (right side)
        content = ttk.Frame(main)
        content.pack(side=LEFT, fill=BOTH, expand=True)

        # Header bar
        self._build_header(content)

        # View frames
        views_container = ttk.Frame(content)
        views_container.pack(fill=BOTH, expand=True)

        self._views["新建项目"] = self._build_new_project_view(views_container)
        self._views["概览"] = self._build_overview_view(views_container)
        self._views["分支"] = self._build_branches_view(views_container)
        self._views["提交"] = self._build_commits_view(views_container)
        self._views["发布"] = self._build_releases_view(views_container)

        for frame in self._views.values():
            frame.place(relwidth=1, relheight=1)

        # Status bar spans the full app width, matching the concept layout.
        self._build_status_bar(shell)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        sidebar = tk.Frame(parent, bg="#0f172a", width=SIDEBAR_WIDTH)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(sidebar, bg="#ffffff", height=68)
        logo_frame.pack(fill=X)
        logo_frame.pack_propagate(False)
        logo = tk.Label(
            logo_frame, text="GM", bg="#ffffff", fg="#111827",
            font=("Segoe UI", 15, "bold"),
        )
        logo.pack(expand=True)

        nav_frame = tk.Frame(sidebar, bg="#1e293b")
        nav_frame.pack(fill=BOTH, expand=True)

        for icon, label in NAV_ITEMS:
            row = tk.Frame(nav_frame, bg="#1e293b")
            row.pack(fill=X)
            row.grid_columnconfigure(1, weight=1)

            # Left accent indicator bar
            indicator = tk.Frame(row, bg="#1e293b", width=3)
            indicator.grid(row=0, column=0, sticky=NS)
            self._nav_indicators[label] = indicator

            btn = tk.Button(
                row,
                text=f"{icon}\n{label}",
                bg="#1e293b",
                fg="#94a3b8",
                activebackground="#334155",
                activeforeground="#38bdf8",
                font=("Microsoft YaHei UI", 9),
                relief=FLAT,
                anchor=CENTER,
                padx=2,
                pady=7,
                cursor="hand2",
                command=lambda l=label: self._show_view(l),
            )
            btn.grid(row=0, column=1, sticky=NSEW)
            row.configure(height=58)
            row.grid_propagate(False)
            self._nav_buttons[label] = btn
            btn.bind("<Enter>", lambda e, b=btn, l=label: self._on_nav_hover(b, l, True))
            btn.bind("<Leave>", lambda e, b=btn, l=label: self._on_nav_hover(b, l, False))

    def _on_nav_hover(self, btn: tk.Button, label: str, entering: bool) -> None:
        if self._current_view == label:
            return
        btn.configure(fg="#e2e8f0" if entering else "#94a3b8")

    def _show_view(self, nav_label: str) -> None:
        view_name = NAV_MAP.get(nav_label, nav_label)
        # Update sidebar highlighting with accent bar
        for label, btn in self._nav_buttons.items():
            indicator = self._nav_indicators[label]
            if label == nav_label:
                btn.configure(bg="#334155", fg="#38bdf8")
                indicator.configure(bg="#38bdf8")
            else:
                btn.configure(bg="#1e293b", fg="#94a3b8")
                indicator.configure(bg="#1e293b")

        # Show selected view
        for label, frame in self._views.items():
            if label == view_name:
                frame.lift()
        self._current_view = nav_label

    def _sync_status_display(self, *_args: object) -> None:
        text = " ".join(self.status_var.get().split())
        if len(text) > STATUS_MAX_CHARS:
            text = text[: STATUS_MAX_CHARS - 1].rstrip() + "..."
        self.status_display_var.set(text or "Ready")

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, padding=(16, 12, 16, 8))
        header.pack(fill=X)
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, minsize=58)

        # Row 1: path + browse
        path_row = ttk.Frame(header)
        path_row.grid(row=0, column=0, sticky=EW)
        path_row.columnconfigure(0, weight=1)
        ttk.Label(
            path_row,
            text="Git Manager",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, sticky=W)
        ttk.Label(path_row, text="项目路径", font=("Microsoft YaHei UI", 9), foreground="#64748b").grid(row=1, column=0, sticky=W, pady=(8, 0))
        ttk.Entry(path_row, textvariable=self.project_path_var).grid(row=2, column=0, sticky=EW, pady=(4, 0))

        header_buttons = ttk.Frame(header)
        header_buttons.grid(row=0, column=1, rowspan=2, sticky=NE, padx=(8, 0), pady=(35, 0))
        ttk.Button(
            header_buttons, text="选择", command=self.choose_project_path, bootstyle="outline",
        ).grid(row=0, column=0, sticky=EW)
        ttk.Button(
            header_buttons, text="刷新", command=self.refresh_git_status_with_output, bootstyle="outline",
        ).grid(row=1, column=0, sticky=EW, pady=(8, 0))

        # Row 2: repo / branch / sync / refresh toolbar
        toolbar = ttk.Frame(header)
        toolbar.grid(row=1, column=0, sticky=EW, pady=(10, 0))

        self._header_repo = ttk.Label(toolbar, text="仓库: -", font=("Microsoft YaHei UI", 9, "bold"))
        self._header_repo.pack(side=LEFT, padx=(0, 16))
        self._header_branch = ttk.Label(toolbar, text="分支: -", font=("Microsoft YaHei UI", 9))
        self._header_branch.pack(side=LEFT, padx=(0, 16))
        self._header_sync = ttk.Label(toolbar, text="同步: -", font=("Microsoft YaHei UI", 9))
        self._header_sync.pack(side=LEFT, padx=(0, 16))

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.grid(row=1, column=0, sticky=EW)
        sep = ttk.Separator(bar)
        sep.pack(fill=X)
        inner = ttk.Frame(bar)
        inner.pack(fill=X, padx=16, pady=4)
        inner.columnconfigure(1, weight=1)
        ttk.Label(
            inner,
            text="状态",
            font=("Microsoft YaHei UI", 9, "bold"),
            foreground="#334155",
        ).grid(row=0, column=0, sticky=W, padx=(0, 10))
        status_label = ttk.Label(
            inner,
            textvariable=self.status_display_var,
            font=("Microsoft YaHei UI", 9),
            foreground="#475569",
            anchor=W,
        )
        status_label.grid(row=0, column=1, sticky=EW)
        self.add_tooltip(status_label, "完整结果会在操作完成后通过弹窗或状态详情显示。")

    def _make_card(
        self,
        parent: ttk.Frame,
        title: str,
        row: int,
        column: int = 0,
        *,
        columnspan: int = 1,
        sticky: str = EW,
        padding: int = 10,
        bootstyle: str = "default",
        pady: tuple[int, int] = (0, 10),
    ) -> ttkb.Labelframe:
        card = ttkb.Labelframe(parent, text=title, padding=padding, bootstyle=bootstyle)
        card.grid(row=row, column=column, columnspan=columnspan, sticky=sticky, pady=pady)
        return card

    def _button_grid(
        self,
        parent: ttk.Frame,
        items: list[tuple[str, Callable[[], None], str]],
        *,
        columns: int,
        primary: set[str] | None = None,
    ) -> None:
        primary = primary or set()
        for col in range(columns):
            parent.columnconfigure(col, weight=1, uniform="buttons")
        for index, (label, command, tip) in enumerate(items):
            button = ttk.Button(
                parent,
                text=label,
                command=command,
                bootstyle="primary" if label in primary else "outline",
            )
            button.grid(
                row=index // columns,
                column=index % columns,
                sticky=EW,
                padx=(0 if index % columns == 0 else 8, 0),
                pady=(0 if index < columns else 8, 0),
            )
            self.add_tooltip(button, tip)

    # ── New Project View ──────────────────────────────────────────

    def _build_new_project_view(self, parent: ttk.Frame) -> ttk.Frame:
        view = ttk.Frame(parent, padding=(14, 10, 14, 12))
        view.columnconfigure(0, weight=2)
        view.columnconfigure(1, weight=3)
        view.rowconfigure(0, weight=1)

        details = self._make_card(
            view,
            "新建项目",
            0,
            0,
            sticky=NSEW,
            pady=(0, 0),
            padding=12,
        )
        details.columnconfigure(1, weight=1)

        ttk.Label(details, text="创建位置").grid(row=0, column=0, sticky=E, padx=(0, 8), pady=4)
        self.create_base_var = tk.StringVar(value=str(self.start_dir))
        ttk.Entry(details, textvariable=self.create_base_var).grid(row=0, column=1, sticky=EW, pady=4)
        ttk.Button(details, text="选择", command=self.choose_create_base, bootstyle="outline").grid(
            row=0, column=2, padx=(8, 0), pady=4
        )

        ttk.Label(details, text="项目名称").grid(row=1, column=0, sticky=E, padx=(0, 8), pady=4)
        self.project_name_var = tk.StringVar()
        ttk.Entry(details, textvariable=self.project_name_var).grid(
            row=1, column=1, columnspan=2, sticky=EW, pady=4
        )

        self.init_git_on_create_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            details, text="创建后初始化 Git",
            variable=self.init_git_on_create_var,
        ).grid(row=2, column=1, columnspan=2, sticky=W, pady=(8, 4))

        ttk.Label(
            details,
            text="模板文件会复制到新项目目录中；复制后不再跟随源模板自动更新。",
            foreground="#6b7280",
            font=("Microsoft YaHei UI", 9),
            wraplength=340,
        ).grid(row=3, column=0, columnspan=3, sticky=EW, pady=(8, 14))

        ttk.Button(
            details,
            text="创建项目",
            command=self.create_project,
            bootstyle="primary",
        ).grid(row=4, column=1, columnspan=2, sticky=EW)

        templates = self._make_card(
            view,
            "ModuleFiles 模板",
            0,
            1,
            sticky=NSEW,
            pady=(0, 0),
            padding=12,
        )
        templates.columnconfigure(0, weight=1)
        templates.rowconfigure(1, weight=1)

        btn_row = ttk.Frame(templates)
        btn_row.grid(row=0, column=0, sticky=EW, pady=(0, 8))
        ttk.Button(btn_row, text="全选", command=self.select_all_modules, bootstyle="outline").pack(side=LEFT)
        ttk.Button(btn_row, text="全不选", command=self.clear_modules, bootstyle="outline").pack(side=LEFT, padx=8)
        ttk.Button(btn_row, text="刷新", command=self._load_module_files, bootstyle="outline").pack(side=RIGHT)

        module_frame = ttk.Frame(templates)
        module_frame.grid(row=1, column=0, sticky=NSEW)
        module_frame.columnconfigure(0, weight=1)
        module_frame.rowconfigure(0, weight=1)
        self.module_canvas = tk.Canvas(module_frame, highlightthickness=0, height=360)
        scrollbar = ttk.Scrollbar(module_frame, orient=VERTICAL, command=self.module_canvas.yview)
        self.module_inner = ttk.Frame(self.module_canvas)
        self.module_inner.bind(
            "<Configure>",
            lambda _e: self.module_canvas.configure(scrollregion=self.module_canvas.bbox("all")),
        )
        self.module_canvas.create_window((0, 0), window=self.module_inner, anchor=NW)
        self.module_canvas.configure(yscrollcommand=scrollbar.set)
        self.module_canvas.grid(row=0, column=0, sticky=NSEW)
        scrollbar.grid(row=0, column=1, sticky=NS)

        return view

    # ── Overview View ─────────────────────────────────────────────

    def _build_overview_view(self, parent: ttk.Frame) -> ttk.Frame:
        view = ttk.Frame(parent, padding=(14, 10, 14, 12))
        view.columnconfigure(0, weight=1)
        view.columnconfigure(1, weight=1)
        view.rowconfigure(2, weight=1)

        # Status cards
        cards = ttk.Frame(view)
        cards.grid(row=0, column=0, columnspan=2, sticky=EW, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1)

        self._make_status_card(cards, 0, "当前分支", self.current_branch_var)
        self._make_status_card(cards, 1, "上游分支", self.upstream_var)
        self._make_status_card(cards, 2, "同步状态", self.sync_state_var)
        self._make_status_card(cards, 3, "工作区", self.worktree_state_var)

        # Repo config
        config_card = self._make_card(view, "仓库配置", 1, 0, sticky=NSEW, pady=(0, 10))
        config_card.columnconfigure(1, weight=1)
        config_card.columnconfigure(3, weight=1)

        ttk.Label(config_card, text="仓库名").grid(row=0, column=0, sticky=E, padx=(0, 8), pady=4)
        repo_entry = ttk.Entry(config_card, textvariable=self.repo_name_var)
        repo_entry.grid(row=0, column=1, sticky=EW, padx=(0, 16), pady=4)
        repo_entry.bind("<FocusOut>", lambda _e: self.refresh_git_status())
        repo_entry.bind("<Return>", lambda _e: self.refresh_git_status())

        ttk.Label(config_card, text="默认分支").grid(row=0, column=2, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(config_card, textvariable=self.branch_var).grid(row=0, column=3, sticky=EW, pady=4)

        config_btns = ttk.Frame(config_card)
        config_btns.grid(row=1, column=0, columnspan=4, sticky=EW, pady=(8, 0))
        self._button_grid(
            config_btns,
            [
                ("刷新", self.refresh_git_status_with_output, "重新读取项目状态。"),
                ("检测远程", self.check_remote, "检查 GitHub 远程仓库连接。"),
                ("重置 Git", self.reset_git_config, "重置 Git 身份、忽略规则和远程地址。"),
                ("状态详情", self.git_status_detail, "查看当前 Git 状态详情。"),
            ],
            columns=4,
        )

        actions_card = self._make_card(view, "快捷入口", 1, 1, sticky=NSEW, pady=(0, 10))
        for col in range(3):
            actions_card.columnconfigure(col, weight=1, uniform="overview_nav")
        for col, (label, nav, style) in enumerate(
            [
                ("分支管理", "分支", "outline"),
                ("提交同步", "提交", "success"),
                ("版本发布", "发布", "success"),
            ]
        ):
            ttk.Button(
                actions_card,
                text=label,
                command=lambda n=nav: self._show_view(n),
                bootstyle=style,
            ).grid(row=0, column=col, sticky=EW, padx=(0 if col == 0 else 8, 0), ipady=4)

        tips_card = self._make_card(view, "工作流提示", 2, 0, columnspan=2, sticky=NSEW, pady=(0, 0))
        tips_card.columnconfigure(0, weight=1)
        ttk.Label(
            tips_card,
            text=(
                "概览页只展示仓库整体状态和常用入口。具体操作请进入左侧菜单："
                "新建项目负责模板复制和初始化；分支页负责切换/创建分支；"
                "提交页负责暂存、提交、同步和历史；发布页负责 GitHub Release 与资产上传。"
            ),
            wraplength=900,
            foreground="#4b5563",
            font=("Microsoft YaHei UI", 10),
        ).grid(row=0, column=0, sticky=NW)

        return view

    def _make_status_card(self, parent: ttk.Frame, col: int, title: str, var: tk.StringVar) -> None:
        card = ttkb.Labelframe(parent, text=title, padding=10, bootstyle="default")
        card.grid(row=0, column=col, padx=4, sticky=EW)
        ttk.Label(card, textvariable=var, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=W)

    # ── Branches View ─────────────────────────────────────────────

    def _build_branches_view(self, parent: ttk.Frame) -> ttk.Frame:
        view = ttk.Frame(parent, padding=(14, 10, 14, 12))
        view.columnconfigure(0, weight=1)
        view.rowconfigure(1, weight=1)

        # Branch controls
        controls = self._make_card(view, "分支操作", 0, 0, sticky=EW, pady=(0, 12))
        controls.columnconfigure(0, minsize=70)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, minsize=128)

        ttk.Label(controls, text="切换到").grid(row=0, column=0, sticky=E, padx=(0, 8), pady=4)
        self.branch_select_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(controls, textvariable=self.branch_select_var, state="readonly")
        self.branch_combo.grid(row=0, column=1, sticky=EW, padx=(0, 8), pady=4)
        ttk.Button(controls, text="切换", command=self.checkout_selected_branch, bootstyle="primary").grid(row=0, column=2, sticky=EW, pady=4)

        ttk.Label(controls, text="新分支").grid(row=1, column=0, sticky=E, padx=(0, 8), pady=4)
        self.new_branch_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.new_branch_var).grid(row=1, column=1, sticky=EW, padx=(0, 8), pady=4)
        ttk.Button(controls, text="创建并切换", command=self.create_branch, bootstyle="outline").grid(row=1, column=2, sticky=EW, pady=4)

        ttk.Label(
            controls,
            text="本地分支可直接切换；origin/* 是远端引用，切换时会创建或切到对应的本地跟踪分支。",
            font=("Microsoft YaHei UI", 9), foreground="#6b7280",
        ).grid(row=2, column=0, columnspan=3, sticky=W, pady=(6, 0))

        # Branch list
        list_card = self._make_card(view, "分支列表", 1, 0, sticky=NSEW, padding=8, pady=(0, 12))
        list_card.grid(row=1, column=0, sticky=NSEW)
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(0, weight=1)

        self.branch_tree = ttk.Treeview(
            list_card,
            columns=("name", "kind", "upstream", "commit", "date", "subject"),
            show="headings",
        )
        for column, heading, width, stretch in [
            ("name", "分支", 170, False),
            ("kind", "类型", 58, False),
            ("upstream", "上游", 150, False),
            ("commit", "提交", 76, False),
            ("date", "日期", 88, False),
            ("subject", "说明", 300, True),
        ]:
            self.branch_tree.heading(column, text=heading)
            self.branch_tree.column(column, width=width, minwidth=width, anchor=W, stretch=stretch)

        branch_scroll_y = ttk.Scrollbar(list_card, orient=VERTICAL, command=self.branch_tree.yview)
        branch_scroll_x = ttk.Scrollbar(list_card, orient=HORIZONTAL, command=self.branch_tree.xview)
        self.branch_tree.configure(yscrollcommand=branch_scroll_y.set, xscrollcommand=branch_scroll_x.set)
        self.branch_tree.grid(row=0, column=0, sticky=NSEW)
        branch_scroll_y.grid(row=0, column=1, sticky=NS)
        branch_scroll_x.grid(row=1, column=0, sticky=EW)

        git_card = self._make_card(view, "远程与配置", 2, 0, sticky=EW, pady=(0, 0))
        self._button_grid(
            git_card,
            [
                ("获取远程", self.git_fetch, "获取远程分支信息。"),
                ("检测远程", self.check_remote, "检查 GitHub 远程连接。"),
                ("重置 Git", self.reset_git_config, "重置当前项目的 Git 配置。"),
                ("状态详情", self.git_status_detail, "查看当前分支和文件状态。"),
            ],
            columns=4,
        )

        return view

    # ── Commits View ──────────────────────────────────────────────

    def _build_commits_view(self, parent: ttk.Frame) -> ttk.Frame:
        view = ttk.Frame(parent, padding=(14, 10, 14, 12))
        view.columnconfigure(0, weight=1)
        view.columnconfigure(1, weight=1)
        view.rowconfigure(1, weight=1)

        # Commit card
        commit_card = self._make_card(view, "提交", 0, 0, sticky=EW, pady=(0, 12))
        commit_card.columnconfigure(1, weight=1)
        commit_card.columnconfigure(2, minsize=92)
        commit_card.columnconfigure(3, minsize=92)

        ttk.Label(commit_card, text="提交信息").grid(row=0, column=0, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(commit_card, textvariable=self.commit_message_var).grid(row=0, column=1, sticky=EW, padx=(0, 8), pady=4)
        ttk.Button(commit_card, text="添加全部", command=self.git_add_all, bootstyle="outline").grid(row=0, column=2, sticky=EW, padx=(0, 8), pady=4)
        ttk.Button(commit_card, text="提交", command=self.git_commit, bootstyle="primary").grid(row=0, column=3, sticky=EW, pady=4)

        # Sync card
        sync_card = self._make_card(view, "同步", 0, 1, sticky=EW, pady=(0, 12))
        for col in range(3):
            sync_card.columnconfigure(col, weight=1, uniform="sync_actions")

        self._button_grid(
            sync_card,
            [
                ("推送", self.git_push, "推送当前分支到远程。"),
                ("拉取", self.git_pull, "从上游拉取更新。"),
                ("获取", self.git_fetch, "获取远程分支信息。"),
            ],
            columns=3,
            primary={"推送"},
        )

        # History card
        history_card = self._make_card(view, "提交历史 / 操作记录", 1, 0, columnspan=2, sticky=NSEW, padding=8, pady=(0, 0))
        history_card.columnconfigure(0, weight=1)
        history_card.rowconfigure(0, weight=1)

        self.log_text = tk.Text(history_card, height=10, wrap=WORD, font=("Consolas", 9), state=DISABLED)
        log_scroll = ttk.Scrollbar(history_card, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky=NSEW)
        log_scroll.grid(row=0, column=1, sticky=NS)

        ttk.Button(history_card, text="刷新最近提交", command=self.git_log, bootstyle="outline").grid(row=1, column=0, sticky=W, pady=(8, 0))

        return view

    # ── Releases View ─────────────────────────────────────────────

    def _build_releases_view(self, parent: ttk.Frame) -> ttk.Frame:
        view = ttk.Frame(parent, padding=(14, 10, 14, 12))
        view.columnconfigure(0, weight=1)
        view.rowconfigure(0, weight=1)

        # Release list
        list_card = self._make_card(view, "Release 列表", 0, 0, sticky=NSEW, padding=8, pady=(0, 12))
        list_card.grid(row=0, column=0, sticky=NSEW, pady=(0, 12))
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(1, weight=1)

        ttk.Label(list_card, textvariable=self.latest_release_var, font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky=W, pady=(0, 4))

        self.release_tree = ttk.Treeview(
            list_card,
            columns=("title", "status", "tag", "published", "source"),
            show="headings",
        )
        for column, heading, width, stretch in [
            ("title", "Release", 160, True),
            ("status", "状态", 70, False),
            ("tag", "Tag", 100, False),
            ("published", "发布时间", 145, False),
            ("source", "来源", 60, False),
        ]:
            self.release_tree.heading(column, text=heading)
            self.release_tree.column(column, width=width, minwidth=width, anchor=W, stretch=stretch)

        release_scroll_y = ttk.Scrollbar(list_card, orient=VERTICAL, command=self.release_tree.yview)
        release_scroll_x = ttk.Scrollbar(list_card, orient=HORIZONTAL, command=self.release_tree.xview)
        self.release_tree.configure(yscrollcommand=release_scroll_y.set, xscrollcommand=release_scroll_x.set)
        self.release_tree.grid(row=1, column=0, sticky=NSEW)
        release_scroll_y.grid(row=1, column=1, sticky=NS)
        release_scroll_x.grid(row=2, column=0, sticky=EW)

        # Create release form
        form_card = self._make_card(view, "创建 Release", 1, 0, sticky=EW, pady=(0, 0))
        form_card.grid(row=1, column=0, sticky=EW)
        form_card.columnconfigure(1, weight=1)
        form_card.columnconfigure(3, weight=1)

        self.release_tag_var = tk.StringVar(value="v1.0.0")
        self.release_title_var = tk.StringVar()
        self.release_notes_var = tk.StringVar()
        self.release_assets_var = tk.StringVar()
        self.release_draft_var = tk.BooleanVar(value=False)
        self.release_prerelease_var = tk.BooleanVar(value=False)

        ttk.Label(form_card, text="Tag").grid(row=0, column=0, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(form_card, textvariable=self.release_tag_var).grid(row=0, column=1, sticky=EW, padx=(0, 16), pady=3)
        ttk.Label(form_card, text="标题").grid(row=0, column=2, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(form_card, textvariable=self.release_title_var).grid(row=0, column=3, sticky=EW, pady=3)

        ttk.Label(form_card, text="说明").grid(row=1, column=0, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(form_card, textvariable=self.release_notes_var).grid(row=1, column=1, columnspan=3, sticky=EW, pady=3)

        ttk.Label(form_card, text="资产").grid(row=2, column=0, sticky=E, padx=(0, 8), pady=4)
        ttk.Entry(form_card, textvariable=self.release_assets_var).grid(row=2, column=1, columnspan=2, sticky=EW, pady=3)
        ttk.Button(form_card, text="选择文件", command=self.choose_release_assets, bootstyle="outline").grid(row=2, column=3, sticky=EW, padx=(8, 0), pady=3)

        opts = ttk.Frame(form_card)
        opts.grid(row=3, column=0, columnspan=4, sticky=EW, pady=(8, 0))
        opts.columnconfigure(2, weight=1)
        ttk.Checkbutton(opts, text="Draft", variable=self.release_draft_var).grid(row=0, column=0, sticky=W)
        ttk.Checkbutton(opts, text="Prerelease", variable=self.release_prerelease_var).grid(row=0, column=1, sticky=W, padx=(16, 0))
        ttk.Button(opts, text="发布 Release", command=self.create_release, bootstyle="primary").grid(row=0, column=3, sticky=E)

        return view

    # ── Module Files ──────────────────────────────────────────────

    def _load_module_files(self) -> None:
        for child in self.module_inner.winfo_children():
            child.destroy()
        self.module_vars.clear()
        module_files = list_module_files()
        if not module_files:
            ttk.Label(
                self.module_inner,
                text=f"未找到 ModuleFiles: {MODULEFILES_DIR}",
            ).pack(anchor=W, padx=8, pady=8)
            return
        for path in module_files:
            var = tk.BooleanVar(value=False)
            self.module_vars[path] = var
            ttk.Checkbutton(
                self.module_inner,
                text=f"{path.name}  ->  {path}",
                variable=var,
            ).pack(anchor=W, padx=8, pady=3)

    def select_all_modules(self) -> None:
        for var in self.module_vars.values():
            var.set(True)

    def clear_modules(self) -> None:
        for var in self.module_vars.values():
            var.set(False)

    def choose_create_base(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.create_base_var.get())
        if selected:
            self.create_base_var.set(selected)

    def choose_project_path(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.project_path_var.get())
        if selected:
            self.project_path_var.set(selected)
            self.sync_repo_name_from_git_context()
            self.refresh_git_status()

    def create_project(self) -> None:
        base = Path(self.create_base_var.get().strip()).expanduser()
        project_name = sanitize_project_name(self.project_name_var.get())
        base_name = sanitize_project_name(base.name)
        use_base_as_project = base_name == project_name
        project_path = base if use_base_as_project else base / project_name
        selected = [path for path, var in self.module_vars.items() if var.get()]

        dir_created = False
        try:
            if project_path.exists():
                if not use_base_as_project or not project_path.is_dir():
                    messagebox.showerror("创建失败", f"目录已存在：{project_path}")
                    return
            else:
                project_path.mkdir(parents=False, exist_ok=False)
                dir_created = True
            for source in selected:
                copy_module_file(source, project_path / source.name)
        except FileExistsError:
            messagebox.showerror("创建失败", f"目录已存在：{project_path}")
            return
        except OSError as exc:
            if dir_created:
                try:
                    for child in project_path.iterdir():
                        child.unlink()
                    project_path.rmdir()
                except OSError:
                    pass
            messagebox.showerror("拷贝失败", f"无法将模板文件拷贝到项目目录。\n\n{exc}")
            return

        file_summary = f"已拷贝 {len(selected)} 个文件" if selected else "未拷贝文件"
        self.project_path_var.set(str(project_path))
        self.repo_name_var.set(project_path.name)
        if self.init_git_on_create_var.get():
            results = initialize_git_repository(
                project_path,
                project_path.name,
                self.branch_var.get().strip() or DEFAULT_BRANCH,
            )
            failed = next((result for result in results if result.returncode != 0), None)
            if failed:
                messagebox.showwarning(
                    "项目已创建，Git 初始化未完成",
                    f"已创建项目：{project_path}\n\nGit 初始化失败：{failed.stderr or failed.stdout}",
                )
            else:
                messagebox.showinfo("完成", f"已创建项目并初始化 Git：{project_path}\n{file_summary}")
        else:
            messagebox.showinfo("完成", f"已创建项目：{project_path}\n{file_summary}")
        self.refresh_git_status()

    # ── Git Operations ────────────────────────────────────────────

    def project_path(self) -> Path:
        return Path(self.project_path_var.get()).expanduser()

    def sync_repo_name_from_git_context(self) -> tuple[str | None, str]:
        project_path = self.project_path()
        remote = run_command(["git", "remote", "get-url", REMOTE_NAME], project_path)
        remote_name = (
            repository_name_from_remote_url(remote.stdout)
            if remote.returncode == 0
            else None
        )
        source = "origin"
        project_name = remote_name
        if not project_name:
            project_name = sanitize_project_name(project_path.name)
            source = "项目文件夹名"
        if not project_name:
            return None, source
        old_name = self.repo_name_var.get().strip()
        if old_name != project_name:
            self.repo_name_var.set(project_name)
            return project_name, source
        return None, source

    def refresh_branch_and_release_views(self) -> None:
        if not hasattr(self, "branch_tree"):
            return
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)

        if not path.exists():
            self.current_branch_var.set("-")
            self.upstream_var.set("-")
            self.sync_state_var.set("-")
            self.worktree_state_var.set("路径不存在")
            return

        inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
        if inside.returncode != 0:
            self.current_branch_var.set("-")
            self.upstream_var.set("-")
            self.sync_state_var.set("未初始化")
            self.worktree_state_var.set("不是 Git 仓库")
            self.branch_combo["values"] = []
            self.branch_tree.delete(*self.branch_tree.get_children())
            self.release_tree.delete(*self.release_tree.get_children())
            self.latest_release_var.set("-")
            return

        branch, branch_error = current_git_branch(path)
        upstream = current_git_upstream(path)
        dirty_count = git_dirty_count(path)
        ahead, behind = git_ahead_behind(path)
        self.current_branch_var.set(branch or "(detached)")
        self.upstream_var.set(upstream or "未设置")
        if ahead is None or behind is None:
            self.sync_state_var.set("未跟踪")
        elif ahead == 0 and behind == 0:
            self.sync_state_var.set("已同步")
        else:
            self.sync_state_var.set(f"ahead {ahead} / behind {behind}")
        self.worktree_state_var.set(
            "干净" if dirty_count == 0 else f"{dirty_count} 项改动"
        )
        if branch_error and not branch:
            self.status_var.set(branch_error)

        branches = list_branches(path)
        self.branch_tree.delete(*self.branch_tree.get_children())
        combo_values: list[str] = []
        for item in branches:
            display = f"* {item.name}" if item.is_current else item.name
            combo_values.append(item.name)
            kind = "远端" if item.is_remote else "本地"
            self.branch_tree.insert(
                "", tk.END,
                values=(display, kind, item.upstream, item.commit, item.date, item.subject),
            )
        self.branch_combo["values"] = combo_values
        if branch and branch in combo_values:
            self.branch_select_var.set(branch)
        elif combo_values:
            self.branch_select_var.set(combo_values[0])

        releases, release_error = list_release_info(path, repo_name)
        self.release_tree.delete(*self.release_tree.get_children())
        if releases:
            latest = releases[0]
            self.latest_release_var.set(f"{latest.tag} | {latest.title} | {latest.status}")
        else:
            self.latest_release_var.set(release_error or "暂无 release/tag")
        for release in releases:
            self.release_tree.insert(
                "", tk.END,
                values=(release.title, release.status, release.tag, release.published_at, release.source),
            )

    def checkout_selected_branch(self) -> None:
        target = self.branch_select_var.get().strip()
        if not target:
            messagebox.showerror("切换失败", "请先选择一个分支。")
            return
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("切换分支")
            if target.startswith(f"{REMOTE_NAME}/"):
                local_name = target[len(f"{REMOTE_NAME}/"):]
                local_exists = run_command(["git", "show-ref", "--verify", f"refs/heads/{local_name}"], path)
                command = (
                    ["git", "switch", local_name]
                    if local_exists.returncode == 0
                    else ["git", "switch", "--track", target]
                )
            else:
                command = ["git", "switch", target]
            result = run_command(command, path)
            if result.returncode == 0:
                self.enqueue(f"已切换到分支：{target}\n")
            else:
                self.enqueue(f"切换失败：{result.stderr or result.stdout}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def create_branch(self) -> None:
        branch_name = self.new_branch_var.get().strip()
        if not branch_name:
            messagebox.showerror("创建失败", "请输入新分支名。")
            return
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("创建并切换分支")
            check = run_command(["git", "check-ref-format", "--branch", branch_name], path)
            if check.returncode != 0:
                self.enqueue(f"分支名无效：{check.stderr or check.stdout}\n")
                self.append_command_done()
                return
            result = run_command(["git", "switch", "-c", branch_name], path)
            if result.returncode == 0:
                self.enqueue(f"已创建并切换到分支：{branch_name}\n")
                self.after(0, lambda: self.new_branch_var.set(""))
            else:
                self.enqueue(f"创建失败：{result.stderr or result.stdout}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def choose_release_assets(self) -> None:
        filenames = filedialog.askopenfilenames(
            initialdir=str(self.project_path()),
            title="选择 Release 附件",
        )
        if filenames:
            self.release_assets_var.set("; ".join(filenames))

    def create_release(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)
        repo = configured_repo_full_name(path, repo_name)
        tag = self.release_tag_var.get().strip()
        title = self.release_title_var.get().strip() or tag
        notes = self.release_notes_var.get().strip()
        assets = [item.strip() for item in self.release_assets_var.get().split(";") if item.strip()]
        if not tag:
            messagebox.showerror("发布失败", "请输入 release tag。")
            return
        gh = find_gh_executable()
        if not gh:
            messagebox.showerror("发布失败", "未找到 GitHub CLI，无法创建 GitHub Release。")
            return
        branch, branch_error = current_git_branch(path)
        if not branch:
            messagebox.showerror("发布失败", branch_error or "无法读取当前分支。")
            return
        dirty_count = git_dirty_count(path)
        if dirty_count and not messagebox.askyesno(
            "工作区有改动", f"当前工作区还有 {dirty_count} 项未提交改动，仍然继续发布？",
        ):
            return

        def worker() -> None:
            self.append_command_start("发布 Release")
            command = [
                gh, "release", "create", tag, *assets,
                "--repo", repo, "--target", branch, "--title", title,
            ]
            if notes:
                command.extend(["--notes", notes])
            else:
                command.append("--generate-notes")
            if self.release_draft_var.get():
                command.append("--draft")
            if self.release_prerelease_var.get():
                command.append("--prerelease")
            result = run_command(command, path, timeout=180)
            if result.returncode == 0:
                self.enqueue(f"Release 已发布：{repo} {tag}\n")
                if result.stdout.strip():
                    self.enqueue(result.stdout)
                fetch_tags = run_command(["git", "fetch", "--tags", REMOTE_NAME], path, 120)
                if fetch_tags.returncode == 0:
                    self.enqueue("已同步远端 tags 到本地。\n")
            else:
                self.enqueue(f"发布失败：{result.stderr or result.stdout}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    # ── Async Output ──────────────────────────────────────────────

    def append_command_start(self, command_name: str) -> None:
        self.output_queue.put(("start", command_name))

    def append_command_done(self) -> None:
        self.output_queue.put(("done", None))

    def enqueue(self, text: str) -> None:
        self.output_queue.put(("text", text))

    def _poll_output(self) -> None:
        try:
            while True:
                kind, text = self.output_queue.get_nowait()
                if kind == "start":
                    self.dialog_title = text or "操作结果"
                    self.dialog_lines = []
                elif kind == "text":
                    if text:
                        self.dialog_lines.append(text)
                elif kind == "done":
                    self.show_operation_dialog()
        except queue.Empty:
            pass
        self.after(100, self._poll_output)

    def show_operation_dialog(self) -> None:
        body = "".join(self.dialog_lines).strip() or "操作完成。"
        self.status_var.set(body.splitlines()[0])
        # Update log text in commits view
        if hasattr(self, "log_text"):
            self.log_text.configure(state=NORMAL)
            self.log_text.insert(END, body + "\n")
            self.log_text.see(END)
            self.log_text.configure(state=DISABLED)
        if "失败" in body or "已停止" in body or "[exit" in body:
            messagebox.showerror(self.dialog_title, body)
        elif "提示" in body or "警告" in body:
            messagebox.showwarning(self.dialog_title, body)
        else:
            messagebox.showinfo(self.dialog_title, body)
        self.dialog_lines = []

    def run_git_async(
        self,
        commands: list[list[str]],
        after: Callable[[], None] | None = None,
    ) -> None:
        cwd = self.project_path()

        def worker() -> None:
            for command in commands:
                result = run_command(command, cwd=cwd, timeout=120)
                self.enqueue(f"\n> {' '.join(command)}\n")
                if result.stdout:
                    self.enqueue(result.stdout)
                if result.stderr:
                    self.enqueue(result.stderr)
                if result.returncode != 0:
                    self.enqueue(f"[exit {result.returncode}]\n")
                    self.enqueue(">\n")
                    break
                self.enqueue(">\n")
            if after:
                self.after(0, after)

        threading.Thread(target=worker, daemon=True).start()

    def collect_git_status_text(self) -> str:
        path = self.project_path()
        if not path.exists():
            return f"路径不存在：{path}"
        inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
        if inside.returncode != 0:
            return "当前路径尚未初始化 Git。可点击“重置 Git 配置”执行初始化。"
        branch = run_command(["git", "branch", "--show-current"], path)
        remote = run_command(["git", "remote", "get-url", REMOTE_NAME], path)
        status = run_command(["git", "status", "--short", "--branch"], path)
        remote_text = remote.stdout.strip() if remote.returncode == 0 else "未设置"
        branch_text = branch.stdout.strip() or "(detached)"
        status_lines = [line for line in status.stdout.splitlines() if line.strip() and not line.startswith("## ")]
        dirty_text = (
            f"有 {len(status_lines)} 项未提交文件改动"
            if status_lines
            else "没有未提交的文件改动"
        )
        expected_remote = github_remote(
            sanitize_project_name(self.repo_name_var.get() or path.name)
        )
        remote_note = ""
        if remote.returncode == 0 and remote_text != expected_remote:
            remote_note = " | 注意：origin 与仓库名推导地址不一致，可点“重置 Git 配置”更新"
        branch_note = ""
        branch_line = next(
            (line for line in status.stdout.splitlines() if line.startswith("## ")),
            "",
        )
        if "ahead" in branch_line or "behind" in branch_line:
            branch_note = f" | 同步状态：{branch_line[3:]}"
        return (
            f"Git 本地状态 | 分支：{branch_text} | "
            f"origin：{remote_text} | 文件：{dirty_text}"
            f"{branch_note}{remote_note}"
        )

    def refresh_git_status(self) -> None:
        self.status_var.set(self.collect_git_status_text())
        self.refresh_branch_and_release_views()
        self._update_header_labels()

    def _update_header_labels(self) -> None:
        if hasattr(self, "_header_repo"):
            self._header_repo.configure(text=f"仓库: {self.repo_name_var.get()}")
        if hasattr(self, "_header_branch"):
            self._header_branch.configure(text=f"分支: {self.current_branch_var.get()}")
        if hasattr(self, "_header_sync"):
            sync = self.sync_state_var.get()
            self._header_sync.configure(text=f"同步: {sync}")

    def refresh_git_status_with_output(self) -> None:
        self.append_command_start("刷新本地 Git 状态")
        synced_name, source = self.sync_repo_name_from_git_context()
        if synced_name:
            self.enqueue(
                f"已按{source}更新仓库名：{synced_name}。\n"
                "后续远程检测、重置 Git 配置和推送都会使用这个仓库名。\n"
            )
        status_text = self.collect_git_status_text()
        self.status_var.set(status_text)
        self.enqueue(f"{status_text}\n")
        self.append_command_done()

    def reset_git_config(self) -> None:
        branch = self.branch_var.get().strip() or DEFAULT_BRANCH
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)

        def worker() -> None:
            self.append_command_start("重置 Git 配置")
            inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
            if inside.returncode != 0:
                self.enqueue("当前项目尚未初始化 Git；现在将执行初始化流程。\n")
            else:
                self.enqueue("当前项目已有 Git 配置；现在将按界面参数重置配置。\n")
            self.enqueue("将更新 .gitignore、.gitattributes、Git 身份和 GitHub 443 远程地址。\n")
            try:
                results = initialize_git_repository(path, repo_name, branch)
            except OSError as exc:
                self.enqueue(f"重置失败：{exc}\n")
                self.append_command_done()
                return
            failed = next((result for result in results if result.returncode != 0), None)
            if failed:
                self.enqueue(f"重置失败：{failed.stderr or failed.stdout}\n")
            else:
                self.enqueue(
                    "重置完成：Git 身份、忽略规则、换行规则和 443 远程地址已更新。\n"
                    f"当前 origin：{github_remote(repo_name)}\n"
                )
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def check_remote(self) -> None:
        repo_name = sanitize_project_name(self.repo_name_var.get())
        remote_url = configured_or_default_remote(self.project_path(), repo_name)

        def worker() -> None:
            self.append_command_start("检测远程连接")
            self.enqueue("正在检测 GitHub 远程连接...\n")
            result = run_command(["git", "ls-remote", remote_url], self.project_path())
            ok, message = explain_remote_result(result, repo_name)
            self.enqueue(f"{message}\n")
            if ok and not result.stdout.strip():
                self.enqueue("提示：远程仓库目前没有可列出的提交或分支，空仓库也属于可访问。\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_add_all(self) -> None:
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("添加全部")
            result = run_command(["git", "add", "-A"], path)
            self.enqueue(f"{summarize_simple_git_result('add', result)}\n")
            detail = (result.stderr or result.stdout).strip()
            if result.returncode == 0 and detail:
                self.enqueue("提示：如果仍看到换行符警告，重新添加一次通常会按 .gitattributes 归一化。\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_status_detail(self) -> None:
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("状态详情")
            result = run_command(["git", "status", "--short", "--branch"], path)
            if result.returncode == 0:
                self.enqueue(f"{summarize_git_status(result.stdout)}\n")
            else:
                self.enqueue(f"状态读取失败：{result.stderr or result.stdout}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_commit(self) -> None:
        message = self.commit_message_var.get().strip() or "Update project"
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("提交")
            result = run_command(["git", "commit", "-m", message], path)
            self.enqueue(f"{summarize_simple_git_result('commit', result)}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_fetch(self) -> None:
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("获取")
            result = run_command(["git", "fetch", REMOTE_NAME], path)
            self.enqueue(f"{summarize_simple_git_result('fetch', result)}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_pull(self) -> None:
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("拉取")
            branch, branch_error = current_git_branch(path)
            if not branch:
                self.enqueue(f"拉取已停止：{branch_error or '无法读取当前分支。'}\n")
                self.append_command_done()
                self.after(0, self.refresh_git_status)
                return

            local_branch = branch
            first_pull = not has_local_commits(path)
            if first_pull:
                self.enqueue("当前仓库还没有本地提交，将按首次拉取流程处理。\n")
                fetch_result = run_command(["git", "fetch", REMOTE_NAME], path, 120)
                if fetch_result.returncode != 0:
                    self.enqueue(f"首次拉取失败：无法获取远端信息。{fetch_result.stderr or fetch_result.stdout}\n")
                    self.append_command_done()
                    self.after(0, self.refresh_git_status)
                    return
                remote_branch = remote_default_branch(path)
                if remote_branch:
                    branch = remote_branch
                    self.enqueue(f"已识别远端默认分支为 {branch}。\n")
                    if local_branch != branch:
                        rename_result = run_command(["git", "branch", "-M", branch], path)
                        if rename_result.returncode == 0:
                            self.enqueue(f"已将本地初始化分支从 {local_branch} 改为 {branch}。\n")
                        else:
                            self.enqueue(f"首次拉取失败：无法重命名本地分支。{rename_result.stderr or rename_result.stdout}\n")
                            self.append_command_done()
                            self.after(0, self.refresh_git_status)
                            return
                else:
                    self.enqueue(f"未能识别远端默认分支，将尝试拉取当前初始化分支 {branch}。\n")

            backups: list[Path] = []
            if first_pull:
                try:
                    backups = backup_first_pull_conflicts(path, branch)
                except OSError as exc:
                    self.enqueue(f"首次拉取失败：无法备份本地初始化配置文件。{exc}\n")
                    self.append_command_done()
                    self.after(0, self.refresh_git_status)
                    return
                if backups:
                    backup_folder = backups[0].parent
                    names = "、".join(backup.name for backup in backups)
                    self.enqueue(
                        f"检测到远端已有 {names}，已先备份本地自动生成版本到：{backup_folder}\n"
                    )

            upstream = current_git_upstream(path)
            if upstream:
                self.enqueue(f"当前将从上游分支 {upstream} 拉取更新。\n")
                result = run_command(["git", "pull"], path, 120)
            else:
                self.enqueue(f"当前将从 origin/{branch} 拉取更新。\n")
                result = run_command(["git", "pull", REMOTE_NAME, branch], path, 120)
            self.enqueue(f"{summarize_simple_git_result('pull', result)}\n")
            detail = (result.stderr or result.stdout).strip()
            if result.returncode == 0 and first_pull:
                checkout_result = run_command(["git", "branch", "--set-upstream-to", f"{REMOTE_NAME}/{branch}"], path)
                if checkout_result.returncode == 0:
                    self.enqueue(f"已把当前分支设置为跟踪 origin/{branch}。\n")
                if backups:
                    self.enqueue("远端版本已拉取完成，本地自动生成配置已保留为备份。\n")
            if result.returncode == 0 and detail:
                self.enqueue(f"Git 详情：{detail}\n")
            elif result.returncode != 0:
                if backups:
                    try:
                        restore_backups(path, backups)
                        self.enqueue("拉取失败，已恢复刚才备份的本地初始化配置文件。\n")
                    except OSError as exc:
                        self.enqueue(f"拉取失败，且恢复备份时出错：{exc}\n")
                if "untracked working tree files would be overwritten" in detail.lower():
                    self.enqueue(
                        "提示：远端文件会覆盖当前目录中的未跟踪文件。"
                        "如果这是刚创建的空项目，可先删除或移走冲突文件后再拉取。\n"
                    )
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_push(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)

        def worker() -> None:
            self.append_command_start("推送")
            branch, branch_error = current_git_branch(path)
            if not branch:
                self.enqueue(f"推送已停止：{branch_error or '无法读取当前分支。'}\n")
                self.append_command_done()
                self.after(0, self.refresh_git_status)
                return
            try:
                ensure_gitignore(path)
                ensure_gitattributes(path)
            except OSError as exc:
                self.enqueue(f"\n推送已停止：无法更新忽略/换行配置：{exc}\n")
                self.append_command_done()
                return

            remote_url = configured_or_default_remote(path, repo_name)
            self.enqueue("正在推送前检查 GitHub 远程仓库...\n")
            check_result = run_command(["git", "ls-remote", remote_url], path)
            remote_ok, remote_message = explain_remote_result(check_result, repo_name)
            if not remote_ok:
                self.enqueue(
                    f"{remote_message}\n"
                    "推送已停止：请先创建 GitHub 仓库或修复权限后再推送。\n"
                )
                self.append_command_done()
                self.after(0, self.refresh_git_status)
                return

            configure_result = configure_git_remote(path, remote_url)
            if configure_result.returncode != 0:
                self.enqueue(f"推送已停止：无法配置 origin。{configure_result.stderr or configure_result.stdout}\n")
                self.append_command_done()
                self.after(0, self.refresh_git_status)
                return
            self.enqueue(f"远程仓库可访问，开始推送当前分支 {branch}...\n")
            push_result = run_command(["git", "push", "-u", REMOTE_NAME, branch], path, 120)
            if push_result.returncode == 0:
                self.enqueue("推送成功：本地提交已上传到 GitHub。\n")
                if push_result.stdout.strip():
                    self.enqueue(push_result.stdout)
                if push_result.stderr.strip():
                    self.enqueue(push_result.stderr)
            else:
                push_ok, push_message = explain_remote_result(push_result, repo_name)
                if push_ok:
                    push_message = "推送失败：Git 返回了非零状态。"
                self.enqueue(f"{push_message}\n")
                detail = (push_result.stderr or push_result.stdout).strip()
                if detail and "repository not found" not in detail.lower():
                    self.enqueue(f"Git 详情：{detail}\n")
            self.append_command_done()
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_log(self) -> None:
        path = self.project_path()

        def worker() -> None:
            self.append_command_start("最近提交")
            result = run_command(
                ["git", "log", "--pretty=format:%h%x09%D%x09%s", "-n", "20"],
                path,
            )
            if result.returncode == 0:
                self.enqueue(f"{summarize_git_log(result.stdout)}\n")
            else:
                self.enqueue(f"提交记录读取失败：{result.stderr or result.stdout}\n")
            self.append_command_done()

        threading.Thread(target=worker, daemon=True).start()


def parse_args() -> argparse.Namespace:
    """Parse command-line options.

    Ref: Python Standard Library, argparse:
    https://docs.python.org/3/library/argparse.html
    """
    parser = argparse.ArgumentParser(description="Git Manager GUI")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=None,
        help="Project directory to open (used by right-click context menu).",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=Path.cwd(),
        help="Directory used as the initial project location.",
    )
    return parser.parse_args()


def resource_path(relative_name: str) -> Path:
    """Resolve resource path for both dev and PyInstaller frozen mode."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent
    return base / relative_name


def main() -> None:
    args = parse_args()
    if args.path is not None:
        start_dir = args.path.expanduser().resolve()
    else:
        start_dir = args.cwd.expanduser().resolve()
    os.chdir(start_dir)

    app = GitManagerApp(start_dir=start_dir)

    icon_path = resource_path("git_manager.ico")
    if icon_path.exists():
        try:
            app.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    app.mainloop()
