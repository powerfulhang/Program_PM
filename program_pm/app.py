from __future__ import annotations

import argparse
import datetime as dt
import os
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable
from urllib.parse import urlparse


MODULEFILES_DIR = Path(r"F:\Working Files\Coding\ModuleFiles")
GITHUB_USER = "powerfulhang"
GITHUB_EMAIL = "hangshi1023@gmail.com"
DEFAULT_BRANCH = "main"
REMOTE_NAME = "origin"
AUTO_GENERATED_CONFIG_FILES = [".gitignore", ".gitattributes"]
GH_CANDIDATES = [
    Path(r"C:\tmp\gh_2.92.0_windows_amd64\bin\gh.exe"),
]


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
    backup_root = project_path / ".git" / "program-pm-backups"
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


class ProgramPmApp(tk.Tk):
    def __init__(self, start_dir: Path) -> None:
        super().__init__()
        self.title("Program PM")
        self.geometry("1180x760")
        self.minsize(1040, 680)
        self.start_dir = start_dir
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.module_vars: dict[Path, tk.BooleanVar] = {}

        self._configure_style()
        self._build_ui()
        self._load_module_files()
        self._poll_output()
        self.refresh_git_status()

    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        Tooltip(widget, text)

    def make_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        tooltip: str,
    ) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        self.add_tooltip(button, tooltip)
        return button

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(background="#f6f7f9")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff", relief=tk.FLAT)
        style.configure("TLabel", background="#f6f7f9", foreground="#1f2937")
        style.configure("Panel.TLabel", background="#ffffff", foreground="#1f2937")
        style.configure(
            "Section.TLabel",
            background="#ffffff",
            foreground="#111827",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background="#ffffff",
            foreground="#6b7280",
            font=("Microsoft YaHei UI", 9),
        )
        style.configure("TButton", padding=(10, 5))
        style.configure("Accent.TButton", padding=(12, 6))
        style.configure("Panel.TCheckbutton", background="#ffffff", foreground="#1f2937")
        style.configure("Treeview", rowheight=26, fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.new_project_tab = ttk.Frame(notebook)
        self.git_tab = ttk.Frame(notebook)
        notebook.add(self.new_project_tab, text="新建项目")
        notebook.add(self.git_tab, text="项目管理")

        self._build_new_project_tab()
        self._build_git_tab()

    def _build_new_project_tab(self) -> None:
        top = ttk.Frame(self.new_project_tab)
        top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top, text="创建位置").grid(row=0, column=0, sticky=tk.W)
        self.create_base_var = tk.StringVar(value=str(self.start_dir))
        ttk.Entry(top, textvariable=self.create_base_var).grid(
            row=0, column=1, sticky=tk.EW, padx=8
        )
        self.make_button(
            top,
            "选择",
            self.choose_create_base,
            "选择新项目要创建在哪个目录下。",
        ).grid(row=0, column=2)

        ttk.Label(top, text="项目名称").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.project_name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.project_name_var).grid(
            row=1, column=1, sticky=tk.EW, padx=8, pady=(8, 0)
        )
        self.init_git_on_create_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top,
            text="创建后初始化 Git（生成 .gitignore、设置身份、设置 443 远程）",
            variable=self.init_git_on_create_var,
        ).grid(row=2, column=1, sticky=tk.W, padx=8, pady=(8, 0))
        top.columnconfigure(1, weight=1)

        actions = ttk.Frame(self.new_project_tab)
        actions.pack(fill=tk.X, padx=10)
        self.make_button(
            actions,
            "全选",
            self.select_all_modules,
            "勾选所有 ModuleFiles。未勾选任何文件时，创建项目时不会拷贝任何文件。",
        ).pack(side=tk.LEFT)
        self.make_button(
            actions,
            "全不选",
            self.clear_modules,
            "清空当前勾选。",
        ).pack(side=tk.LEFT, padx=8)
        self.make_button(
            actions,
            "刷新 ModuleFiles",
            self._load_module_files,
            f"重新扫描 {MODULEFILES_DIR} 下的模板文件。",
        ).pack(side=tk.LEFT)
        self.make_button(
            actions,
            "创建项目",
            self.create_project,
            "在创建位置下新建项目目录，拷贝选中的 ModuleFiles 模板文件，并可同步初始化 Git。",
        ).pack(side=tk.RIGHT)

        list_frame = ttk.LabelFrame(self.new_project_tab, text="ModuleFiles")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.module_canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.module_canvas.yview
        )
        self.module_inner = ttk.Frame(self.module_canvas)
        self.module_inner.bind(
            "<Configure>",
            lambda _event: self.module_canvas.configure(
                scrollregion=self.module_canvas.bbox("all")
            ),
        )
        self.module_canvas.create_window((0, 0), window=self.module_inner, anchor=tk.NW)
        self.module_canvas.configure(yscrollcommand=scrollbar.set)
        self.module_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_git_tab(self) -> None:
        shell = ttk.Frame(self.git_tab)
        shell.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(2, weight=1)

        top = ttk.Frame(shell, style="Panel.TFrame")
        top.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="项目路径", style="Panel.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(12, 8), pady=12
        )
        self.project_path_var = tk.StringVar(value=str(self.start_dir))
        ttk.Entry(top, textvariable=self.project_path_var).grid(
            row=0, column=1, sticky=tk.EW, padx=8
        )
        self.make_button(
            top,
            "选择",
            self.choose_project_path,
            "选择要管理的现有项目目录。",
        ).grid(row=0, column=2, padx=(0, 12))

        status_panel = ttk.Frame(shell, style="Panel.TFrame")
        status_panel.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        for column in range(4):
            status_panel.columnconfigure(column, weight=1)
        self.repo_name_var = tk.StringVar(value=self.start_dir.name)
        self.branch_var = tk.StringVar(value=DEFAULT_BRANCH)
        self.commit_message_var = tk.StringVar(value="Update project")
        self.current_branch_var = tk.StringVar(value="-")
        self.upstream_var = tk.StringVar(value="-")
        self.sync_state_var = tk.StringVar(value="-")
        self.worktree_state_var = tk.StringVar(value="-")
        self.latest_release_var = tk.StringVar(value="-")

        self._make_metric(status_panel, 0, "当前分支", self.current_branch_var)
        self._make_metric(status_panel, 1, "上游分支", self.upstream_var)
        self._make_metric(status_panel, 2, "同步状态", self.sync_state_var)
        self._make_metric(status_panel, 3, "工作区", self.worktree_state_var)

        left = ttk.Frame(shell, style="Panel.TFrame")
        left.grid(row=2, column=0, sticky=tk.NSEW, padx=(0, 6))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        right = ttk.Frame(shell, style="Panel.TFrame")
        right.grid(row=2, column=1, sticky=tk.NSEW, padx=(6, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        ttk.Label(left, text="分支管理", style="Section.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=12, pady=(12, 4)
        )
        branch_controls = ttk.Frame(left, style="Panel.TFrame")
        branch_controls.grid(row=1, column=0, sticky=tk.EW, padx=12, pady=(4, 8))
        branch_controls.columnconfigure(1, weight=1)
        self.branch_select_var = tk.StringVar()
        ttk.Label(branch_controls, text="切换到", style="Panel.TLabel").grid(
            row=0, column=0, sticky=tk.W
        )
        self.branch_combo = ttk.Combobox(
            branch_controls,
            textvariable=self.branch_select_var,
            state="readonly",
            width=34,
        )
        self.branch_combo.grid(row=0, column=1, sticky=tk.EW, padx=8)
        self.make_button(
            branch_controls,
            "切换",
            self.checkout_selected_branch,
            "切换到列表中选中的本地或远端分支。",
        ).grid(row=0, column=2)

        self.new_branch_var = tk.StringVar()
        ttk.Label(branch_controls, text="新分支", style="Panel.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(8, 0)
        )
        ttk.Entry(branch_controls, textvariable=self.new_branch_var).grid(
            row=1, column=1, sticky=tk.EW, padx=8, pady=(8, 0)
        )
        self.make_button(
            branch_controls,
            "创建并切换",
            self.create_branch,
            "从当前 HEAD 创建新分支并切换过去。",
        ).grid(row=1, column=2, pady=(8, 0))

        self.branch_tree = ttk.Treeview(
            left,
            columns=("name", "kind", "upstream", "commit", "date", "subject"),
            show="headings",
            height=11,
        )
        for column, heading, width in [
            ("name", "分支", 170),
            ("kind", "类型", 70),
            ("upstream", "上游", 150),
            ("commit", "提交", 80),
            ("date", "日期", 90),
            ("subject", "说明", 260),
        ]:
            self.branch_tree.heading(column, text=heading)
            self.branch_tree.column(column, width=width, anchor=tk.W)
        self.branch_tree.grid(row=2, column=0, sticky=tk.NSEW, padx=12, pady=(0, 10))

        git_actions = ttk.Frame(left, style="Panel.TFrame")
        git_actions.grid(row=3, column=0, sticky=tk.EW, padx=12, pady=(0, 12))
        for label, command, tooltip in [
            ("刷新", self.refresh_git_status_with_output, "重新读取分支、状态和 release 信息。"),
            ("检测远程", self.check_remote, "检查当前 origin 或仓库名对应的 GitHub SSH 443 远程。"),
            ("重置 Git", self.reset_git_config, "按当前仓库名重置 Git 身份、忽略规则和远程地址。"),
            ("获取", self.git_fetch, "从远程仓库获取最新分支信息，但不修改本地文件。"),
            ("拉取", self.git_pull, "从当前分支的上游或 origin 同名分支拉取更新。"),
            ("推送当前分支", self.git_push, "先确认远程仓库可访问，再推送当前分支并设置上游。"),
            ("状态详情", self.git_status_detail, "显示当前分支、跟踪分支和文件改动列表。"),
            ("最近提交", self.git_log, "显示最近 20 条提交记录。"),
        ]:
            self.make_button(git_actions, label, command, tooltip).pack(
                side=tk.LEFT, padx=(0, 6), pady=3
            )

        ttk.Label(right, text="提交与发布", style="Section.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=12, pady=(12, 4)
        )
        commit_panel = ttk.Frame(right, style="Panel.TFrame")
        commit_panel.grid(row=1, column=0, sticky=tk.EW, padx=12, pady=(4, 10))
        commit_panel.columnconfigure(1, weight=1)
        ttk.Label(commit_panel, text="仓库名", style="Panel.TLabel").grid(row=0, column=0)
        repo_entry = ttk.Entry(commit_panel, textvariable=self.repo_name_var, width=24)
        repo_entry.grid(row=0, column=1, sticky=tk.EW, padx=8)
        repo_entry.bind("<FocusOut>", lambda _event: self.refresh_git_status())
        repo_entry.bind("<Return>", lambda _event: self.refresh_git_status())
        ttk.Label(commit_panel, text="新项目默认分支", style="Panel.TLabel").grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Entry(commit_panel, textvariable=self.branch_var, width=14).grid(
            row=0, column=3, padx=(8, 0)
        )
        ttk.Label(commit_panel, text="提交信息", style="Panel.TLabel").grid(
            row=1, column=0, pady=(8, 0)
        )
        ttk.Entry(commit_panel, textvariable=self.commit_message_var).grid(
            row=1, column=1, columnspan=3, sticky=tk.EW, padx=8, pady=(8, 0)
        )
        self.make_button(commit_panel, "添加全部", self.git_add_all, "暂存当前项目所有改动。").grid(
            row=2, column=2, sticky=tk.E, pady=(8, 0)
        )
        self.make_button(commit_panel, "提交", self.git_commit, "用上方提交信息创建本地提交。").grid(
            row=2, column=3, sticky=tk.E, padx=(8, 0), pady=(8, 0)
        )

        release_panel = ttk.Frame(right, style="Panel.TFrame")
        release_panel.grid(row=2, column=0, sticky=tk.NSEW, padx=12, pady=(0, 10))
        release_panel.columnconfigure(0, weight=1)
        release_panel.rowconfigure(2, weight=1)
        ttk.Label(release_panel, text="Latest Release", style="Muted.TLabel").grid(
            row=0, column=0, sticky=tk.W
        )
        ttk.Label(release_panel, textvariable=self.latest_release_var, style="Panel.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(0, 8)
        )
        self.release_tree = ttk.Treeview(
            release_panel,
            columns=("title", "status", "tag", "published", "source"),
            show="headings",
            height=8,
        )
        for column, heading, width in [
            ("title", "Release", 170),
            ("status", "状态", 90),
            ("tag", "Tag", 120),
            ("published", "发布时间", 160),
            ("source", "来源", 70),
        ]:
            self.release_tree.heading(column, text=heading)
            self.release_tree.column(column, width=width, anchor=tk.W)
        self.release_tree.grid(row=2, column=0, sticky=tk.NSEW)

        release_form = ttk.Frame(right, style="Panel.TFrame")
        release_form.grid(row=3, column=0, sticky=tk.EW, padx=12, pady=(0, 12))
        release_form.columnconfigure(1, weight=1)
        self.release_tag_var = tk.StringVar(value="v1.0.0")
        self.release_title_var = tk.StringVar()
        self.release_notes_var = tk.StringVar()
        self.release_draft_var = tk.BooleanVar(value=False)
        self.release_prerelease_var = tk.BooleanVar(value=False)
        ttk.Label(release_form, text="Tag", style="Panel.TLabel").grid(row=0, column=0)
        ttk.Entry(release_form, textvariable=self.release_tag_var, width=16).grid(
            row=0, column=1, sticky=tk.EW, padx=8
        )
        ttk.Label(release_form, text="标题", style="Panel.TLabel").grid(row=0, column=2)
        ttk.Entry(release_form, textvariable=self.release_title_var, width=22).grid(
            row=0, column=3, sticky=tk.EW, padx=(8, 0)
        )
        ttk.Label(release_form, text="说明", style="Panel.TLabel").grid(
            row=1, column=0, pady=(8, 0)
        )
        ttk.Entry(release_form, textvariable=self.release_notes_var).grid(
            row=1, column=1, columnspan=3, sticky=tk.EW, padx=8, pady=(8, 0)
        )
        ttk.Checkbutton(
            release_form,
            text="Draft",
            variable=self.release_draft_var,
            style="Panel.TCheckbutton",
        ).grid(row=2, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Checkbutton(
            release_form,
            text="Prerelease",
            variable=self.release_prerelease_var,
            style="Panel.TCheckbutton",
        ).grid(row=2, column=2, sticky=tk.W, pady=(8, 0))
        self.make_button(
            release_form,
            "发布 Release",
            self.create_release,
            "用 GitHub CLI 在当前分支或提交上创建 GitHub Release。",
        ).grid(row=2, column=3, sticky=tk.E, pady=(8, 0))

        bottom = ttk.Frame(shell, style="Panel.TFrame")
        bottom.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW, pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)
        self.status_var = tk.StringVar(value="未检测")
        ttk.Label(bottom, textvariable=self.status_var, style="Panel.TLabel").grid(
            row=0, column=0, sticky=tk.EW, padx=12, pady=(10, 6)
        )
        self.output = ScrolledText(bottom, height=8, wrap=tk.WORD)
        self.output.grid(row=1, column=0, sticky=tk.NSEW, padx=12, pady=(0, 12))

    def _make_metric(
        self,
        parent: tk.Widget,
        column: int,
        title: str,
        variable: tk.StringVar,
    ) -> None:
        cell = ttk.Frame(parent, style="Panel.TFrame")
        cell.grid(row=0, column=column, sticky=tk.EW, padx=12, pady=10)
        ttk.Label(cell, text=title, style="Muted.TLabel").pack(anchor=tk.W)
        ttk.Label(cell, textvariable=variable, style="Section.TLabel").pack(anchor=tk.W)

    def _load_module_files(self) -> None:
        for child in self.module_inner.winfo_children():
            child.destroy()
        self.module_vars.clear()
        module_files = list_module_files()
        if not module_files:
            ttk.Label(
                self.module_inner,
                text=f"未找到 ModuleFiles: {MODULEFILES_DIR}",
            ).pack(anchor=tk.W, padx=8, pady=8)
            return
        for path in module_files:
            var = tk.BooleanVar(value=False)
            self.module_vars[path] = var
            ttk.Checkbutton(
                self.module_inner,
                text=f"{path.name}  ->  {path}",
                variable=var,
            ).pack(anchor=tk.W, padx=8, pady=3)

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
            messagebox.showerror(
                "拷贝失败",
                f"无法将模板文件拷贝到项目目录。\n\n{exc}",
            )
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
                    f"已创建项目：{project_path}\n\n"
                    f"Git 初始化失败：{failed.stderr or failed.stdout}",
                )
            else:
                messagebox.showinfo(
                    "完成",
                    f"已创建项目并初始化 Git：{project_path}\n"
                    f"{file_summary}",
                )
        else:
            messagebox.showinfo(
                "完成",
                f"已创建项目：{project_path}\n"
                f"{file_summary}",
            )
        self.refresh_git_status()

    def project_path(self) -> Path:
        return Path(self.project_path_var.get()).expanduser()

    def sync_repo_name_from_git_context(self) -> tuple[str | None, str]:
        """Set the repository name from origin, falling back to the folder name.

        Ref: Python Standard Library, pathlib.PurePath.name:
        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.name
        """
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
                "",
                tk.END,
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
                "",
                tk.END,
                values=(
                    release.title,
                    release.status,
                    release.tag,
                    release.published_at,
                    release.source,
                ),
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
                local_name = target[len(f"{REMOTE_NAME}/") :]
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

    def create_release(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)
        repo = configured_repo_full_name(path, repo_name)
        tag = self.release_tag_var.get().strip()
        title = self.release_title_var.get().strip() or tag
        notes = self.release_notes_var.get().strip()
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
            "工作区有改动",
            f"当前工作区还有 {dirty_count} 项未提交改动，仍然继续发布？",
        ):
            return

        def worker() -> None:
            self.append_command_start("发布 Release")
            # Ref: GitHub CLI manual, gh release create supports --target,
            # --title, --notes, --draft, --prerelease, and --generate-notes.
            command = [
                gh,
                "release",
                "create",
                tag,
                "--repo",
                repo,
                "--target",
                branch,
                "--title",
                title,
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

    def append_output(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def append_command_start(self, command_name: str) -> None:
        self.enqueue(f"\n> {command_name}\n")

    def append_command_done(self) -> None:
        self.enqueue(">\n")

    def enqueue(self, text: str) -> None:
        self.output_queue.put(text)

    def _poll_output(self) -> None:
        try:
            while True:
                self.append_output(self.output_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_output)

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
    parser = argparse.ArgumentParser(description="Program PM GUI")
    parser.add_argument(
        "--cwd",
        type=Path,
        default=Path.cwd(),
        help="Directory used as the initial project location.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_dir = args.cwd.expanduser().resolve()
    os.chdir(start_dir)
    app = ProgramPmApp(start_dir=start_dir)
    app.mainloop()
