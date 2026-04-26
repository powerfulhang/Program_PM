from __future__ import annotations

import argparse
import datetime as dt
import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable


AGENTFILES_DIR = Path(r"F:\Working Files\Coding\AgentFiles")
GITHUB_USER = "powerfulhang"
GITHUB_EMAIL = "hangshi1023@gmail.com"
DEFAULT_BRANCH = "master"
REMOTE_NAME = "origin"


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


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


def list_agent_files() -> list[Path]:
    """List direct files in the AgentFiles directory.

    Ref: Python Standard Library, pathlib.Path.iterdir:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir
    """
    if not AGENTFILES_DIR.exists():
        return []
    return sorted(path for path in AGENTFILES_DIR.iterdir() if path.is_file())


def create_link(source: Path, destination: Path) -> None:
    """Create a symlink so AgentFiles updates are reflected in projects.

    Ref: Python Standard Library, pathlib.Path.symlink_to:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.symlink_to
    """
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    destination.symlink_to(source)


def ensure_gitignore(project_path: Path) -> None:
    """Create or extend .gitignore with defaults.

    Ref: Python Standard Library, pathlib.Path.read_text/write_text:
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.read_text
    """
    gitignore = project_path / ".gitignore"
    required = [
        "# AgentFiles links and local automation",
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
    ]
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lines_to_add = [line for line in required if line and line not in existing]
    if not gitignore.exists():
        gitignore.write_text("\n".join(required), encoding="utf-8")
        return
    if lines_to_add:
        suffix = "" if existing.endswith("\n") else "\n"
        gitignore.write_text(
            existing + suffix + "\n".join(required) + "\n",
            encoding="utf-8",
        )


def github_remote(repo_name: str) -> str:
    return f"ssh://git@ssh.github.com:443/{GITHUB_USER}/{repo_name}.git"


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


class ProgramPmApp(tk.Tk):
    def __init__(self, start_dir: Path) -> None:
        super().__init__()
        self.title("Program PM")
        self.geometry("980x680")
        self.minsize(880, 560)
        self.start_dir = start_dir
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.agent_vars: dict[Path, tk.BooleanVar] = {}

        self._build_ui()
        self._load_agent_files()
        self._poll_output()
        self.refresh_git_status()

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
        ttk.Button(top, text="选择", command=self.choose_create_base).grid(
            row=0, column=2
        )

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
        ttk.Button(actions, text="全选", command=self.select_all_agents).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="全不选", command=self.clear_agents).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(actions, text="刷新 AgentFiles", command=self._load_agent_files).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="初始化当前项目 Git", command=self.git_init).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(actions, text="创建项目", command=self.create_project).pack(
            side=tk.RIGHT
        )

        list_frame = ttk.LabelFrame(self.new_project_tab, text="AgentFiles")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.agent_canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.agent_canvas.yview
        )
        self.agent_inner = ttk.Frame(self.agent_canvas)
        self.agent_inner.bind(
            "<Configure>",
            lambda _event: self.agent_canvas.configure(
                scrollregion=self.agent_canvas.bbox("all")
            ),
        )
        self.agent_canvas.create_window((0, 0), window=self.agent_inner, anchor=tk.NW)
        self.agent_canvas.configure(yscrollcommand=scrollbar.set)
        self.agent_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_git_tab(self) -> None:
        top = ttk.Frame(self.git_tab)
        top.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(top, text="项目路径").grid(row=0, column=0, sticky=tk.W)
        self.project_path_var = tk.StringVar(value=str(self.start_dir))
        ttk.Entry(top, textvariable=self.project_path_var).grid(
            row=0, column=1, sticky=tk.EW, padx=8
        )
        ttk.Button(top, text="选择", command=self.choose_project_path).grid(
            row=0, column=2
        )
        top.columnconfigure(1, weight=1)

        info = ttk.Frame(self.git_tab)
        info.pack(fill=tk.X, padx=10)
        self.repo_name_var = tk.StringVar(value=self.start_dir.name)
        self.branch_var = tk.StringVar(value=DEFAULT_BRANCH)
        self.commit_message_var = tk.StringVar(value="Update project")
        ttk.Label(info, text="仓库名").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(info, textvariable=self.repo_name_var, width=28).grid(
            row=0, column=1, sticky=tk.W, padx=8
        )
        ttk.Label(info, text="默认分支").grid(row=0, column=2, sticky=tk.W, padx=(18, 0))
        ttk.Entry(info, textvariable=self.branch_var, width=16).grid(
            row=0, column=3, sticky=tk.W, padx=8
        )
        ttk.Label(info, text="提交信息").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Entry(info, textvariable=self.commit_message_var).grid(
            row=1, column=1, columnspan=3, sticky=tk.EW, padx=8, pady=(8, 0)
        )
        info.columnconfigure(1, weight=1)

        buttons = ttk.Frame(self.git_tab)
        buttons.pack(fill=tk.X, padx=10, pady=10)
        for label, command in [
            ("刷新本地 Git 状态", self.refresh_git_status),
            ("检测远程连接", self.check_remote),
            ("状态详情", self.git_status_detail),
            ("添加全部", self.git_add_all),
            ("提交", self.git_commit),
            ("获取", self.git_fetch),
            ("拉取", self.git_pull),
            ("推送", self.git_push),
            ("最近提交", self.git_log),
        ]:
            ttk.Button(buttons, text=label, command=command).pack(
                side=tk.LEFT, padx=(0, 6), pady=3
            )

        self.status_var = tk.StringVar(value="未检测")
        ttk.Label(self.git_tab, textvariable=self.status_var).pack(
            fill=tk.X, padx=10, pady=(0, 8)
        )
        self.output = ScrolledText(self.git_tab, height=20, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def _load_agent_files(self) -> None:
        for child in self.agent_inner.winfo_children():
            child.destroy()
        self.agent_vars.clear()
        agent_files = list_agent_files()
        if not agent_files:
            ttk.Label(
                self.agent_inner,
                text=f"未找到 AgentFiles: {AGENTFILES_DIR}",
            ).pack(anchor=tk.W, padx=8, pady=8)
            return
        for path in agent_files:
            var = tk.BooleanVar(value=False)
            self.agent_vars[path] = var
            ttk.Checkbutton(
                self.agent_inner,
                text=f"{path.name}  ->  {path}",
                variable=var,
            ).pack(anchor=tk.W, padx=8, pady=3)

    def select_all_agents(self) -> None:
        for var in self.agent_vars.values():
            var.set(True)

    def clear_agents(self) -> None:
        for var in self.agent_vars.values():
            var.set(False)

    def choose_create_base(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.create_base_var.get())
        if selected:
            self.create_base_var.set(selected)

    def choose_project_path(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.project_path_var.get())
        if selected:
            self.project_path_var.set(selected)
            self.repo_name_var.set(Path(selected).name)
            self.refresh_git_status()

    def create_project(self) -> None:
        base = Path(self.create_base_var.get()).expanduser()
        project_name = sanitize_project_name(self.project_name_var.get())
        project_path = base / project_name
        selected = [path for path, var in self.agent_vars.items() if var.get()]
        if not selected:
            selected = list(self.agent_vars.keys())

        try:
            project_path.mkdir(parents=False, exist_ok=False)
            for source in selected:
                create_link(source, project_path / source.name)
        except FileExistsError:
            messagebox.showerror("创建失败", f"目录已存在：{project_path}")
            return
        except OSError as exc:
            messagebox.showerror(
                "链接创建失败",
                "Windows 可能未允许当前用户创建符号链接。\n"
                "可开启 Developer Mode，或用管理员权限运行终端后重试。\n\n"
                f"{exc}",
            )
            return

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
                    f"已创建项目并初始化 Git：{project_path}",
                )
        else:
            messagebox.showinfo("完成", f"已创建项目：{project_path}")
        self.refresh_git_status()

    def project_path(self) -> Path:
        return Path(self.project_path_var.get()).expanduser()

    def append_output(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

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
                    break
            if after:
                self.after(0, after)

        threading.Thread(target=worker, daemon=True).start()

    def refresh_git_status(self) -> None:
        path = self.project_path()
        if not path.exists():
            self.status_var.set(f"路径不存在：{path}")
            return
        inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
        if inside.returncode != 0:
            self.status_var.set("当前路径尚未初始化 Git")
            return
        branch = run_command(["git", "branch", "--show-current"], path)
        remote = run_command(["git", "remote", "get-url", REMOTE_NAME], path)
        status = run_command(["git", "status", "--short"], path)
        remote_text = remote.stdout.strip() if remote.returncode == 0 else "未设置"
        branch_text = branch.stdout.strip() or "(detached)"
        dirty_text = "有未提交更改" if status.stdout.strip() else "工作区干净"
        self.status_var.set(
            f"Git 已连接本地仓库 | 分支：{branch_text} | "
            f"remote：{remote_text} | {dirty_text}"
        )

    def git_init(self) -> None:
        branch = self.branch_var.get().strip() or DEFAULT_BRANCH
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name_var.get() or path.name)

        def worker() -> None:
            self.enqueue("\n正在初始化 Git：生成 .gitignore、设置身份、设置 443 远程...\n")
            try:
                results = initialize_git_repository(path, repo_name, branch)
            except OSError as exc:
                self.enqueue(f"Git 初始化失败：{exc}\n")
                return
            failed = next((result for result in results if result.returncode != 0), None)
            if failed:
                self.enqueue(f"Git 初始化失败：{failed.stderr or failed.stdout}\n")
            else:
                self.enqueue(
                    "Git 初始化完成：已生成 .gitignore，"
                    f"身份为 {GITHUB_USER} <{GITHUB_EMAIL}>，"
                    f"远程为 {github_remote(repo_name)}。\n"
                )
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def create_gitignore(self) -> None:
        try:
            ensure_gitignore(self.project_path())
        except OSError as exc:
            messagebox.showerror("失败", str(exc))
            return
        self.append_output("\n已生成或更新 .gitignore\n")
        self.refresh_git_status()

    def configure_identity(self) -> None:
        self.run_git_async(
            [
                ["git", "config", "user.name", GITHUB_USER],
                ["git", "config", "user.email", GITHUB_EMAIL],
            ],
            after=self.refresh_git_status,
        )

    def configure_remote(self) -> None:
        repo_name = sanitize_project_name(self.repo_name_var.get())
        remote_url = github_remote(repo_name)
        result = configure_git_remote(self.project_path(), remote_url)
        if result.returncode == 0:
            self.append_output(f"\n已设置 443 远程：{remote_url}\n")
        else:
            self.append_output(f"\n设置 443 远程失败：{result.stderr or result.stdout}\n")
        self.refresh_git_status()

    def check_remote(self) -> None:
        repo_name = sanitize_project_name(self.repo_name_var.get())
        remote_url = github_remote(repo_name)

        def worker() -> None:
            self.enqueue("\n正在检测 GitHub 远程连接...\n")
            result = run_command(["git", "ls-remote", remote_url], self.project_path())
            detail = (result.stderr or result.stdout).strip()
            detail_lower = detail.lower()
            if result.returncode == 0:
                self.enqueue(
                    "远程连接成功：SSH 443 可用，GitHub 仓库可访问。\n"
                )
            elif "repository not found" in detail_lower:
                self.enqueue(
                    "远程连接失败：SSH 443 已能连到 GitHub，"
                    "但仓库不存在或当前 SSH 密钥没有权限。"
                    f"请先在 GitHub 创建仓库 {GITHUB_USER}/{repo_name}。\n"
                )
            elif "permission denied" in detail_lower:
                self.enqueue(
                    "远程连接失败：GitHub 拒绝了当前 SSH 密钥。"
                    "请检查 SSH key 是否已添加到 GitHub 账户。\n"
                )
            elif "could not resolve hostname" in detail_lower:
                self.enqueue(
                    "远程连接失败：无法解析 GitHub SSH 主机名，"
                    "请检查网络或 DNS。\n"
                )
            elif "connection timed out" in detail_lower:
                self.enqueue(
                    "远程连接失败：连接超时，可能是网络或防火墙拦截。\n"
                )
            else:
                self.enqueue(f"远程连接失败：{detail or '未知错误'}\n")
            self.after(0, self.refresh_git_status)

        threading.Thread(target=worker, daemon=True).start()

    def git_add_all(self) -> None:
        self.run_git_async([["git", "add", "-A"]], after=self.refresh_git_status)

    def git_status_detail(self) -> None:
        self.run_git_async([["git", "status", "--short", "--branch"]])

    def git_commit(self) -> None:
        message = self.commit_message_var.get().strip() or "Update project"
        self.run_git_async([["git", "commit", "-m", message]], after=self.refresh_git_status)

    def git_fetch(self) -> None:
        self.run_git_async([["git", "fetch", REMOTE_NAME]], after=self.refresh_git_status)

    def git_pull(self) -> None:
        branch = self.branch_var.get().strip() or DEFAULT_BRANCH
        self.run_git_async(
            [["git", "pull", REMOTE_NAME, branch]],
            after=self.refresh_git_status,
        )

    def git_push(self) -> None:
        branch = self.branch_var.get().strip() or DEFAULT_BRANCH
        self.create_gitignore()
        self.run_git_async(
            [["git", "push", "-u", REMOTE_NAME, branch]],
            after=self.refresh_git_status,
        )

    def git_log(self) -> None:
        self.run_git_async([["git", "log", "--oneline", "--decorate", "-n", "20"]])


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
