# Git Manager

Windows Git 项目管理 GUI 工具，用于：

- 从任意目录启动后，在当前目录创建新项目；
- 从 `F:\Working Files\Coding\ModuleFiles` 勾选模板文件并复制到新项目；
- 新建项目时可同步初始化 Git；
- 在 GUI 中管理当前项目的分支、提交、拉取、推送和最近提交；
- 读取本地 tag / GitHub release，并通过 GitHub CLI 发布 release 和上传附件；
- 默认使用 GitHub SSH 443 端口远程地址。

## 运行

### 方式一：直接运行 .exe（推荐）

从 [Releases](https://github.com/powerfulhang/Program_PM/releases) 页面下载 `GitManager.exe`，双击即可运行。

指定项目目录：

```powershell
.\GitManager.exe "F:\Working Files\Coding\MyProject"
```

### 方式二：安装到 PATH

运行安装脚本，将启动器加入 `%USERPROFILE%\bin` 并加入用户 PATH：

```powershell
.\install-git-manager.ps1
```

安装后请新开一个 PowerShell 再运行 `git-manager`。

### 方式三：通过 Python 运行（开发模式）

```powershell
.\.venv\Scripts\python.exe -m git_manager
```

或使用启动脚本：

```powershell
.\git-manager.cmd
```

## GitHub 约定

- GitHub 用户：`powerfulhang`
- 邮箱：`hangshi1023@gmail.com`
- 新项目默认初始化分支：`main`
- 默认远程：`ssh://git@ssh.github.com:443/powerfulhang/<repo>.git`

如果 GitHub 侧仓库还不存在，工具会在检测远程时提示先创建仓库。

新建项目页的"创建后初始化 Git"和项目管理页的"重置 Git 配置"都会完成：

- 生成或更新 `.gitignore`
- 生成或更新 `.gitattributes`，减少 Windows 下 LF/CRLF 警告
- 设置 Git 用户名和邮箱
- 设置 GitHub SSH 443 端口远程地址

## 模板文件

模板文件会被复制到新项目目录中；复制后不再跟随 `ModuleFiles` 中的源文件自动更新。

如果"创建位置"的最后一级目录名已经等于"项目名称"，工具会直接把该目录作为项目目录，
不会再创建一层同名子目录。

## 分支与发布

项目管理页会读取当前项目的真实 Git 状态，而不是把"新项目默认分支"当作当前分支。界面会显示：

- 当前分支、上游分支、ahead/behind 和工作区改动数量；
- 本地分支与 `origin/*` 远端分支列表；
- 当前仓库的 GitHub release 列表；如果找不到 GitHub CLI，则退回显示本地 tag。

分支操作支持：

- 切换到本地分支；
- 从 `origin/<branch>` 创建跟踪分支并切换；
- 从当前 HEAD 创建新分支；
- 推送当前分支并设置 upstream。

发布 release 依赖 GitHub CLI。工具会优先使用 PATH 中的 `gh`，也会识别本机已安装的
`C:\tmp\gh_2.92.0_windows_amd64\bin\gh.exe`。发布时会使用当前分支作为 `gh release create --target`
目标；如果未填写说明，则使用 GitHub 自动生成 release notes。Release 本身不是分支，而是绑定到
某个 tag 的 GitHub 发布记录；"资产"字段可以选择安装包、压缩包或其他文件，这些文件会作为
release assets 上传。
