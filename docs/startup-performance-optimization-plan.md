# Git Manager 启动性能优化方案

日期：2026-05-04  
对象：`GitManager.exe` / `git_manager.qt_app`

## 1. 结论摘要

当前打开缓慢很可能不是单点问题，而是三个因素叠加：

1. 当前打包脚本使用 PyInstaller `--onefile`。PyInstaller 官方文档说明，onefile 程序启动时会先创建 `_MEI...` 临时目录，并把嵌入的依赖解压进去；官方也明确写到 onefile 会比 one-folder 启动稍慢。因此当前 `dist/GitManager.exe` 的启动速度天然受自解压影响。
2. 新 Qt UI 仍从旧 `git_manager.app` 导入后端函数，而旧模块顶层导入了 `tkinter`、`ttkbootstrap`。本地 `python -X importtime -c "import git_manager.qt_app"` 显示 `git_manager.app` 又导入了 `_tkinter`、`tkinter`、`ttkbootstrap`、`PIL`，这会增加启动导入成本，也会扩大 PyInstaller 依赖图。
3. 主窗口构造阶段立即执行 `refresh_git_status()`，它会继续刷新分支和 Release 页面，并调用 `list_release_info()`。该函数会优先调用 `gh release list --repo ... --limit 20`，属于可能触发外部进程和网络/认证状态检查的工作，不适合阻塞首屏。

建议优先做两类优化：先把旧 Tk UI 依赖从 Qt 启动路径剥离，再把启动时的 Git/GitHub 查询改为首屏后异步或按页懒加载。打包层面建议将默认发行物改成 `onedir`，保留 `onefile` 作为便携版。

## 2. 本地现状证据

### 2.1 打包方式

`scripts/build.py` 当前 PyInstaller 参数包含：

```text
--onefile
--windowed
--icon=...
--name GitManager
```

当前 `dist/GitManager.exe` 大小约 `57,004,414` 字节，约 54.4 MiB。

### 2.2 Qt UI 导入旧 Tk UI 模块

`git_manager/qt_app.py` 第 50 行开始从 `git_manager.app` 导入大量后端函数：

```python
from git_manager.app import (
    ...
    list_release_info,
    ...
)
```

但 `git_manager/app.py` 顶层存在：

```python
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
```

本地导入耗时采样命令：

```powershell
.\.venv\Scripts\python.exe -X importtime -c "import git_manager.qt_app" 2>&1 |
  Select-String -Pattern 'git_manager|PySide6|tkinter|ttkbootstrap|PIL'
```

关键结果：

```text
PySide6.QtCore        cumulative ~57 ms
PySide6.QtGui         cumulative ~3.7 ms
PySide6.QtWidgets     cumulative ~1.8 ms
tkinter               cumulative ~6.8 ms
ttkbootstrap          cumulative ~46.4 ms
git_manager.app       cumulative ~72.8 ms
git_manager.qt_app    cumulative ~183.7 ms
```

这说明 Qt UI 的导入路径确实包含旧 Tk/ttkbootstrap/PIL 依赖。开发态的毫秒级差异在 PyInstaller onefile 中会被放大，因为更多二进制和资源需要被分析、打包、解压、加载。

### 2.3 启动阶段同步刷新过重

`git_manager/qt_app.py` 主窗口初始化阶段：

```python
self._build_ui()
self._connect_actions()
self.load_module_files()
...
self.refresh_git_status()
self.switch_page(1)
```

`refresh_git_status()` 会调用：

```python
self.refresh_branch_and_release_views()
```

而 `refresh_branch_and_release_views()` 会执行分支列表刷新，并调用：

```python
releases, release_error = list_release_info(path, repo_name)
```

`git_manager/app.py` 中 `list_release_info()` 会优先查找 `gh`，然后运行：

```python
[gh, "release", "list", "--repo", repo, "--limit", "20"]
```

这类外部命令和 GitHub CLI 查询不应该卡在窗口首次显示前。

### 2.4 异常处理也会引入 Tk 打包依赖

`git_manager/main.py` 的异常兜底中导入了 `tkinter` 和 `messagebox`。虽然这是异常路径，但 PyInstaller 静态分析会看到这些 import。建议改为 Qt 弹窗或简单写日志后退出，避免为了异常弹窗额外拉入 Tk。

## 3. 官方资料依据

1. PyInstaller 会递归分析 import，并把脚本需要的模块和库收集进 bundle；它也支持 Qt/PySide、Tkinter 等 GUI 包的依赖收集。  
   Source: PyInstaller, “Analysis: Finding the Files Your Program Needs”  
   https://pyinstaller.org/en/v6.5.0/operating-mode.html

2. PyInstaller one-folder 是默认输出，便于调试；onefile 会生成单个可执行文件，但官方说明它会比 one-folder 启动稍慢。onefile 启动时会创建 `_MEI...` 临时目录并解压支持文件。  
   Source: PyInstaller, “Bundling to One Folder / Bundling to One File / How the One-File Program Works”  
   https://pyinstaller.org/en/v6.5.0/operating-mode.html

3. PyInstaller 会在 `build/name/xref-name.html` 写入依赖交叉引用图，可用来追踪某个模块为什么被打包；`--debug=imports` 可用于检查运行时导入。  
   Source: PyInstaller, “Build-Time Dependency Graph / Getting Python’s Verbose Imports”  
   https://www.pyinstaller.org/en/stable/when-things-go-wrong.html

4. PyInstaller 支持 `--exclude-module`，可以让指定模块被视为未找到；也提供 `--splash`，用于 onefile 大程序解压/启动期间显示启动图，但该 splash 基于 Tcl/Tk，会把 Tcl/Tk 动态库打进应用。  
   Source: PyInstaller, “Using PyInstaller”  
   https://www.pyinstaller.org/en/stable/usage.html

5. Python 官方 `-X importtime` 可以显示每个 import 的累计时间和自身时间，适合作为启动导入剖析工具；`PYTHONPROFILEIMPORTTIME` 是等价环境变量。  
   Source: Python Docs, “Command line and environment”  
   https://docs.python.org/3/using/cmdline.html

6. Qt for Python 官方部署文档列出 “冻结为单文件或目录” 作为部署方式，并推荐 `pyside6-deploy` 作为 PySide6 应用部署工具之一；`pyside6-deploy` 基于 Nuitka，配置中 `mode` 可选 `onefile` 或 `standalone`，其中 `standalone` 会生成包含 exe 和依赖文件的目录。  
   Source: Qt for Python, “Deployment” and “pyside6-deploy”  
   https://doc.qt.io/qtforpython-6.8/deployment/index.html  
   https://doc.qt.io/qtforpython-6.8/deployment/deployment-pyside6-deploy.html

## 4. 优化路线

### Phase 0：建立启动性能基线

目标：先知道慢在哪里，避免只靠体感判断。

建议增加一个开发用 profiling 开关，例如 `GIT_MANAGER_PROFILE=1`：

```text
t0 process start
t1 before importing PySide6
t2 after importing git_manager.qt_app
t3 QApplication created
t4 MainWindow constructed
t5 window shown
t6 first status refresh completed
```

同时保留两类测量：

```powershell
# 导入耗时
.\.venv\Scripts\python.exe -X importtime -c "import git_manager.qt_app"

# PyInstaller 依赖来源
.\.venv\Scripts\python.exe -m PyInstaller --log-level=DEBUG ...
```

验收标准：

- 文档化一次当前 source 启动、onedir 启动、onefile 启动的冷启动和热启动时间。
- `build/GitManager/xref-GitManager.html` 中能解释 Tk/ttkbootstrap/PIL 是从哪个顶层 import 进入的。

### Phase 1：拆分后端，移除 Qt 启动路径里的 Tk/ttkbootstrap

目标：让 `git_manager.qt_app` 不再 import 旧 UI 模块。

建议新建：

```text
git_manager/git_backend.py
```

迁移内容：

- 常量：`MODULEFILES_DIR`、`GITHUB_USER`、`REMOTE_NAME`、`DEFAULT_BRANCH` 等。
- 数据结构：`BranchInfo`、`ReleaseInfo` 等。
- 纯后端函数：`run_command()`、`list_branches()`、`list_release_info()`、`git_dirty_count()`、`initialize_git_repository()` 等。

迁移原则：

- `git_backend.py` 只允许标准库和必要的业务依赖。
- 不允许导入 `tkinter`、`ttkbootstrap`、`PySide6`。
- `qt_app.py` 改为从 `git_backend.py` 导入。
- 旧 `app.py` 如果还需要保留 Tk 版本，则让它也从 `git_backend.py` 导入后端函数。
- 如果旧 Tk UI 不再需要，后续从 `pyproject.toml` 移除 `ttkbootstrap`。

预期收益：

- source import 阶段减少 Tk/ttkbootstrap/PIL 导入。
- PyInstaller 依赖图减少 Tk/ttkbootstrap/PIL 相关模块。
- onefile 解压内容减少，启动更轻。

验收标准：

```powershell
.\.venv\Scripts\python.exe -X importtime -c "import git_manager.qt_app" 2>&1 |
  Select-String -Pattern 'tkinter|ttkbootstrap|PIL'
```

优化后正常情况下不应再出现 `tkinter`、`ttkbootstrap`、`PIL`。

### Phase 2：首屏先显示，Git/GitHub 查询延后

目标：窗口先打开，再刷新状态。

建议改造顺序：

1. `MainWindow.__init__` 中只做 UI 构建、事件绑定、轻量本地字段初始化。
2. `main()` 中先 `window.show()`。
3. 用 `QTimer.singleShot(0, window.bootstrap_after_show)` 或 `QTimer.singleShot(100, ...)` 启动后续刷新。
4. `bootstrap_after_show()` 只刷新顶部仓库状态和概览卡片，不主动刷新 Release 列表。
5. Release 页面切换到“发布”页时再调用 `list_release_info()`。
6. 外部命令如 `gh release list` 放入 `QThread` / worker，完成后再更新 UI。

建议分层：

```text
首次显示前：
- 构造 Qt 控件
- 读取项目路径
- 显示缓存或占位状态

首次显示后 0-300 ms：
- git rev-parse
- 当前分支
- dirty count
- ahead/behind

用户进入对应页面时：
- release list
- 远程检测
- 较慢的 gh/GitHub 操作
```

预期收益：

- 首屏可见时间明显缩短。
- GitHub CLI 或网络状态异常不会拖慢应用打开。
- 用户会感觉程序“先打开了”，即使后台状态还在刷新。

验收标准：

- 没有 GitHub CLI、远程 release 查询阻塞首屏。
- Release 页首次进入时才显示加载状态并刷新列表。
- 主窗口显示后，底部状态栏可以提示“正在刷新 Git 状态...”。

### Phase 3：异常弹窗改用 Qt，避免 Tk 被异常路径打包

目标：消除 `git_manager/main.py` 中的 Tk 依赖。

建议：

- 在异常路径中创建最小 `QApplication`，使用 `QMessageBox.critical()` 显示错误。
- 或者在 `--windowed` 生产构建中只写 `~/git_manager_crash.log`，下次启动时在 Qt UI 内提示。
- 不再在入口文件导入 `tkinter`。

验收标准：

- `main.py` 不出现 `tkinter`。
- PyInstaller 分析结果不再因为异常兜底引入 Tk。

### Phase 4：打包策略调整

目标：默认包更快，便携包按需提供。

建议新增两种构建模式：

```powershell
.\.venv\Scripts\python.exe scripts\build.py --mode onedir
.\.venv\Scripts\python.exe scripts\build.py --mode onefile
```

推荐默认：

- `onedir`：主发行版本，适合日常使用和安装目录。
- `onefile`：便携版，适合单文件分发，但接受更慢启动。

PyInstaller 优化参数建议：

```text
--exclude-module tkinter
--exclude-module ttkbootstrap
--exclude-module PIL
```

注意：这些 exclude 只能在 Phase 1 和 Phase 3 完成后启用。否则可能把仍被使用的模块排除掉，导致运行失败。

不建议优先做：

- 优先使用 PyInstaller `--splash` 解决慢启动。官方文档说明 splash 基于 Tcl/Tk，会把 Tcl/Tk 动态库打进应用；本项目当前优化目标正是减少 Tk 依赖。
- 盲目启用 UPX。PyInstaller 文档说明 UPX 会压缩收集到的二进制，且可用 `--noupx` 禁用；但 Qt 插件与 UPX 相关兼容性需要谨慎，是否启用必须以实测为准。

### Phase 5：可选评估 pyside6-deploy / Nuitka

目标：如果 PyInstaller onedir 优化后仍不满意，再评估替代部署链。

Qt 官方文档推荐 `pyside6-deploy`，它基于 Nuitka，并提供 `onefile` / `standalone` 模式。建议只作为实验分支：

```powershell
pyside6-deploy git_manager/main.py --dry-run
```

评估指标：

- 首屏时间。
- 产物大小。
- 是否能正确包含 icon。
- Windows 机器上是否免安装运行。
- 构建时间和 CI 复杂度。

不要默认迁移到 Nuitka，除非实测明显优于 PyInstaller，并且构建维护成本可接受。

## 5. 建议实施顺序

1. 新增 profiling 日志，记录当前启动基线。
2. 新建 `git_manager/git_backend.py`，把纯后端从 `app.py` 拆出来。
3. `qt_app.py` 改为只依赖 `git_backend.py`。
4. `main.py` 异常弹窗改为 Qt 或日志，不再导入 Tk。
5. Release 列表改为进入发布页后懒加载。
6. 首次 Git 状态刷新改为 `show()` 后异步执行。
7. 新增 `onedir` 构建模式，并将 `onedir` 设为默认。
8. 验证 Tk/ttkbootstrap/PIL 不再进入 PyInstaller 依赖图后，再加 `--exclude-module`。
9. 重新打包并对比 source / onedir / onefile 启动时间。

## 6. 预期验收指标

建议先设定可测目标：

| 指标 | 当前状态 | 目标 |
| --- | --- | --- |
| `import git_manager.qt_app` 是否引入 Tk | 是 | 否 |
| PyInstaller 默认模式 | onefile | onedir |
| 首屏前是否调用 `gh release list` | 是 | 否 |
| Release 列表刷新 | 启动时同步刷新 | 进入发布页后异步刷新 |
| Tk/ttkbootstrap/PIL 是否进入主包依赖图 | 是 | 否 |
| onefile 是否保留 | 是 | 仅作为便携版 |

性能目标建议：

- source 运行：主窗口可见时间控制在 1 秒内。
- onedir 热启动：主窗口可见时间控制在 1-2 秒内。
- onefile 冷启动：允许慢于 onedir，但应显示启动反馈或清晰状态。

具体数字需要 Phase 0 的基线测量确认。

## 7. 风险和回退

1. 后端拆分风险：`app.py` 和 `qt_app.py` 可能共同依赖同一批函数。拆分时应先迁移纯函数和 dataclass，再逐步调整 import。
2. 打包排除风险：`--exclude-module` 必须在确认代码路径不再需要对应模块后使用。
3. onedir 分发风险：用户不再是双击单一 exe，而是双击目录中的 `GitManager.exe`。可以通过快捷方式、安装脚本或 zip 包解决。
4. 异步刷新风险：后台线程不能直接更新 Qt 控件，必须通过 signal/slot 或主线程回调更新 UI。
5. GitHub CLI 风险：`gh` 未登录、网络不可用、GitHub API 慢，都不能影响首屏打开。

## 8. 下一步落地建议

最先动手的代码任务建议是：

```text
Task 1: 新建 git_manager/git_backend.py，迁移纯后端，qt_app.py 改 import。
Task 2: main.py 移除 tkinter 异常弹窗。
Task 3: Release 页懒加载，启动时不调用 list_release_info。
Task 4: scripts/build.py 增加 --mode onedir/onefile，并默认 onedir。
Task 5: 重新运行 importtime 和 PyInstaller xref，记录优化前后对比。
```

这组改动风险较低，且基本正中当前慢启动的根因。
