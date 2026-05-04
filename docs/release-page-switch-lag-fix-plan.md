# 发布页切换卡顿问题定位与修复方案

日期：2026-05-04  
对象：`git_manager.qt_app` / 发布页面 Release 列表

## 1. 问题结论

发布页切换慢半拍的直接原因是：页面切换时仍在 Qt 主线程同步执行 Release 数据读取。

当前代码在 `switch_page(4)` 时执行：

```python
self.stack.setCurrentIndex(index)
self.sidebar.select(index)
if index == 4:
    QTimer.singleShot(0, self.refresh_release_info)
```

`QTimer.singleShot(0, ...)` 只能把 `refresh_release_info()` 排到事件循环的下一次调度，并不会把它放到后台线程。Qt 官方文档说明，0ms timer 会尽快触发，其处理函数应快速返回，以便 Qt 继续向 UI 分发事件；文档也提示这类重工作逐渐应由 `QThread` 替代。  
Source: Qt for Python, `QTimer` detailed description  
https://doc.qt.io/qtforpython-6.8/PySide6/QtCore/QTimer.html

而 `refresh_release_info()` 会立即调用：

```python
releases, release_error = list_release_info(path, repo_name)
```

`list_release_info()` 又会同步运行：

```python
gh release list --repo <repo> --limit 20
```

GitHub CLI 官方文档说明 `gh release list` 会列出仓库 releases，并支持 `--repo`、`--limit` 等参数。这个命令属于外部进程 + GitHub CLI 查询，不应阻塞 UI 切页。  
Source: GitHub CLI manual, `gh release list`  
https://cli.github.com/manual/gh_release_list

因此，上一次启动优化把 Release 查询从启动阶段延后到了“进入发布页时”，启动变快了，但卡顿被转移到了发布页切换这一刻。

## 2. 本地代码证据

### 2.1 页面切换触发同步刷新

位置：`git_manager/qt_app.py`

```python
def switch_page(self, index: int) -> None:
    self.stack.setCurrentIndex(index)
    self.sidebar.select(index)
    # Lazy-load release info when switching to the Release page
    if index == 4:
        QTimer.singleShot(0, self.refresh_release_info)
```

问题点：

- `setCurrentIndex()` 本身是毫秒级 UI 操作。
- 真正慢的是 `QTimer.singleShot(0, self.refresh_release_info)` 后紧跟着在主线程运行的 Release 查询。
- 每次进入发布页都会触发刷新，没有看到 `_release_loaded`、`_release_loading` 或缓存状态。

### 2.2 Release 查询函数阻塞 UI 主线程

位置：`git_manager/qt_app.py`

```python
def refresh_release_info(self) -> None:
    path = self.project_path()
    repo_name = sanitize_project_name(self.repo_name or path.name)
    releases, release_error = list_release_info(path, repo_name)
    self.release_page.table.setRowCount(0)
    ...
```

问题点：

- `list_release_info()` 执行完成前，函数不会返回。
- 它运行在 Qt 主线程，因此 UI 在这段时间内无法继续响应。
- 后续表格绘制本身不是主要问题，主要耗时来自查询。

### 2.3 后端 Release 查询包含外部命令

位置：`git_manager/git_backend.py`

```python
def list_release_info(project_path: Path, repo_name: str) -> tuple[list[ReleaseInfo], str | None]:
    repo = configured_repo_full_name(project_path, repo_name)
    gh = find_gh_executable()
    if gh:
        result = run_command(
            [gh, "release", "list", "--repo", repo, "--limit", "20"],
            project_path,
            timeout=20,
        )
        ...
```

`run_command()` 使用 `subprocess.run()` 并等待命令结束。Python 官方文档说明 `subprocess.run()` 会运行命令、等待其完成后返回；`timeout` 是秒级等待上限，且进程创建本身在很多平台上不能被 timeout 立即中断。  
Source: Python Docs, `subprocess.run()` and timeout behavior  
https://docs.python.org/3/library/subprocess.html

这解释了用户体感的 1-2 秒停顿：只要 `gh release list` 在当前网络、认证或 GitHub API 状态下耗时 1-2 秒，UI 主线程就会停 1-2 秒。

## 3. 复现与确认方法

### 3.1 直接测后端耗时

```powershell
.\.venv\Scripts\python.exe -c "import time; from pathlib import Path; from git_manager.git_backend import list_release_info; p=Path.cwd(); t=time.perf_counter(); releases, err=list_release_info(p, p.name); print(f'elapsed={time.perf_counter()-t:.3f}s releases={len(releases)} err={err!r}')"
```

如果这里显示 `elapsed=1.0s` 到 `2.0s`，就与切换发布页的卡顿体感一致。

### 3.2 单独测 GitHub CLI

```powershell
Measure-Command {
  gh release list --repo powerfulhang/Program_PM --limit 20 | Out-Null
}
```

说明：

- 当前 Codex 沙箱里 GitHub API 访问被限制，测得很快失败，不能代表你的真实桌面环境。
- 你本机正常联网时，`gh release list` 成功访问 GitHub API 的耗时才是发布页卡顿的真实来源。

### 3.3 临时验证判断

可以临时把 `switch_page()` 里的这一段注释掉：

```python
if index == 4:
    QTimer.singleShot(0, self.refresh_release_info)
```

如果发布页切换立刻变成无感知，则根因坐实。这个验证只用于定位，不是最终修复。

## 4. 推荐修复方案

核心原则：页面切换只负责切页，Release 数据加载必须后台化，并且需要缓存与防重入。

### 4.1 新增 Release 加载状态

在 `MainWindow.__init__` 中新增：

```python
self._release_loading = False
self._release_loaded = False
self._release_cache_key: tuple[str, str] | None = None
self._release_cache: tuple[list[ReleaseInfo], str | None] | None = None
self._release_request_id = 0
```

含义：

- `_release_loading`：防止快速重复点击发布页时启动多个 `gh release list`。
- `_release_loaded`：同一仓库已加载过则直接显示缓存。
- `_release_cache_key`：以项目路径 + 仓库名区分缓存。
- `_release_request_id`：避免旧请求晚到后覆盖新仓库的 UI。

### 4.2 切页时只触发后台加载

把当前逻辑：

```python
if index == 4:
    QTimer.singleShot(0, self.refresh_release_info)
```

改为：

```python
if index == 4:
    self.ensure_release_info_async(force=False)
```

`ensure_release_info_async()` 应该立即返回，不能在里面直接调用 `list_release_info()`。

### 4.3 后台线程读取 Release

项目中已经有 `threading.Thread` 和 `output_queue` 模式，可以先沿用这套机制，改动量比引入完整 `QThread` 更小。但需要注意：后台线程不能直接更新 Qt 控件，只能把结果放入队列，由主线程的 `_poll_output()` 消费后更新 UI。

Qt 官方文档说明，`QThread` 可用于执行 expensive/blocking operation，并通过 signal 把结果交回 UI；跨线程 signal/slot 是安全的 queued connections。  
Source: Qt for Python, `QThread` detailed description  
https://doc.qt.io/qtforpython-6.8/PySide6/QtCore/QThread.html

如果保持现有 `threading + queue`，建议结构如下：

```python
def ensure_release_info_async(self, force: bool = False) -> None:
    path = self.project_path()
    repo_name = sanitize_project_name(self.repo_name or path.name)
    cache_key = (str(path.resolve()), repo_name)

    if not force and self._release_cache_key == cache_key and self._release_cache:
        releases, error = self._release_cache
        self.render_release_info(releases, error)
        return

    if self._release_loading:
        return

    self._release_loading = True
    self._release_request_id += 1
    request_id = self._release_request_id
    self.release_page.latest_label.setText("正在读取 release/tag...")

    def worker() -> None:
        releases, error = list_release_info(path, repo_name)
        self.output_queue.put(("release_info", {
            "request_id": request_id,
            "cache_key": cache_key,
            "releases": releases,
            "error": error,
        }))

    threading.Thread(target=worker, daemon=True).start()
```

然后在 `_poll_output()` 中处理：

```python
elif kind == "release_info":
    if payload["request_id"] != self._release_request_id:
        return
    self._release_loading = False
    self._release_cache_key = payload["cache_key"]
    self._release_cache = (payload["releases"], payload["error"])
    self.render_release_info(payload["releases"], payload["error"])
```

`render_release_info()` 只做 UI 绘制：

```python
def render_release_info(self, releases: list[ReleaseInfo], release_error: str | None) -> None:
    self.release_page.table.setRowCount(0)
    ...
```

### 4.4 避免每次进入发布页都刷新

当前逻辑每次点发布都会触发查询。建议改成：

- 第一次进入发布页：后台加载。
- 后续进入同一仓库发布页：直接显示缓存。
- 用户点击刷新按钮：强制刷新。
- 发布 Release 成功后：强制刷新。

如果发布页目前没有专属刷新按钮，可以复用顶部刷新按钮：

```python
if self.stack.currentIndex() == 4:
    self.ensure_release_info_async(force=True)
else:
    self.refresh_git_status_with_output()
```

或在 Release 列表标题区增加一个小型“刷新”按钮。

### 4.5 可选：先显示本地 tag，再后台刷新 GitHub Release

为了让发布页立刻有内容，可以把 `list_release_info()` 拆成两层：

```text
list_local_tags(project_path)              # 快，立即显示
list_github_releases(project_path, repo)   # 慢，后台刷新
```

进入发布页时：

1. 立即读取本地 `git tag --list --sort=-creatordate`，填表，来源显示 `Git`。
2. 后台运行 `gh release list`。
3. 成功后用 GitHub Release 数据替换表格。
4. 失败时保留本地 tag，并在 label 或状态栏显示错误。

这样即使 GitHub API 慢，用户也不会看到空白页面。

### 4.6 可选：降低 Release 查询量

当前代码请求 `--limit 20`。GitHub CLI 官方文档说明 `--limit` 控制最大获取数量，默认值是 30。  
Source: GitHub CLI manual, `gh release list` options  
https://cli.github.com/manual/gh_release_list

如果 UI 只需要展示最近几个版本，建议改成：

```text
--limit 10
```

如果只需要 Latest label，可单独做 `--limit 1` 的轻量查询；完整表格刷新由用户点击刷新触发。

## 5. 不推荐的修复方式

### 5.1 不要只把 `QTimer.singleShot(0, ...)` 改成 `singleShot(100, ...)`

这只能把卡顿推迟 100ms，不能消除主线程阻塞。

### 5.2 不要在后台线程直接操作 Qt 控件

后台线程只负责调用 `list_release_info()` 和整理数据。表格、label、按钮状态必须回到主线程更新。Qt 官方文档强调跨线程交互需要谨慎，并推荐通过信号/槽等机制交回结果。

### 5.3 不要把超时从 20 秒简单降到 1 秒作为主方案

降低 timeout 可以减少最坏卡顿，但只要仍在主线程同步等待，500ms 都会被用户感知。正确主方案是后台化；timeout 只是兜底。

## 6. 建议实施顺序

1. 把 `refresh_release_info()` 拆成两部分：
   - `load_release_info()`：只返回数据，不碰 UI。
   - `render_release_info()`：只更新 UI。
2. 新增 `ensure_release_info_async(force=False)`，后台调用 `load_release_info()`。
3. 扩展 `_poll_output()`，处理 `release_info` 队列消息。
4. `switch_page(4)` 改为调用 `ensure_release_info_async(False)`。
5. 加 `_release_loading`、`_release_cache_key`、`_release_request_id` 防重入和防旧结果覆盖。
6. 发布成功后调用 `ensure_release_info_async(True)` 刷新 Release 列表。
7. 可选新增 Release 页刷新按钮，手动强制刷新。

## 7. 验收标准

修复完成后，应该满足：

| 场景 | 目标行为 |
| --- | --- |
| 从概览切到发布 | 页面立即切换，无 1-2 秒冻结 |
| GitHub CLI 查询中 | label 显示“正在读取 release/tag...”，UI 仍可点击其他页面 |
| 快速反复点击发布页 | 不启动多个并发 `gh release list` |
| 切换仓库路径后进发布页 | 使用新 cache key，重新后台加载 |
| GitHub CLI 慢或失败 | UI 不冻结，保留本地 tag 或显示错误提示 |
| 发布 Release 成功后 | 后台强制刷新发布列表 |

建议性能指标：

- `switch_page(4)` 自身耗时小于 50ms。
- 后台 Release 查询允许耗时 1-2 秒，但不阻塞 UI。
- 同一仓库第二次进入发布页直接使用缓存，体感应与其他页面一致。

## 8. 最小修复范围

优先只改这几个位置：

```text
git_manager/qt_app.py
- MainWindow.__init__
- switch_page
- refresh_release_info 拆分
- _poll_output
- create_release 成功后的刷新逻辑

git_manager/git_backend.py
- 可选拆分 list_release_info 为 local tag 与 GitHub release 两层
```

这次不需要调整 PyInstaller 打包，也不需要重新处理启动优化。问题已经从“启动慢”变成“发布页数据查询阻塞切页”，修复重点应放在 Release 页异步加载与缓存。
