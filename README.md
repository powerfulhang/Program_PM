# Program PM

Windows 项目管理 GUI 工具，用于：

- 从任意目录启动后，在当前目录创建新项目；
- 从 `F:\Working Files\Coding\AgentFiles` 勾选 AGENTS 文件并创建链接；
- 新建项目时可同步初始化 Git；
- 在 GUI 中执行常见 Git/GitHub 操作；
- 默认使用 GitHub SSH 443 端口远程地址。

在 Windows 上，即使当前账户属于管理员组，普通启动的程序也不一定拥有创建符号链接的权限。
工具会优先创建符号链接；如果系统拒绝，会自动退回为硬链接。硬链接同样会共享同一份文件内容，
适合本工具引用 AGENTS 文件的场景。

如果“创建位置”的最后一级目录名已经等于“项目名称”，工具会直接把该目录作为项目目录，
不会再创建一层同名子目录。

## 运行

无需第三方依赖：

```powershell
.\.venv\Scripts\python.exe -m program_pm
```

也可以直接运行：

```powershell
.\program-pm.cmd
```

把本目录加入 `PATH` 后，就可以在任意目录运行：

```powershell
program-pm
```

也可以运行安装脚本，它会在 `%USERPROFILE%\bin` 下创建启动器并加入用户 PATH：

```powershell
.\install-program-pm.ps1
```

安装后请新开一个 PowerShell 再运行 `program-pm`。如果想在当前 PowerShell 会话里立刻测试：

```powershell
$env:Path = "$HOME\bin;$env:Path"
program-pm
```

## GitHub 约定

- GitHub 用户：`powerfulhang`
- 邮箱：`hangshi1023@gmail.com`
- 新项目默认初始化分支：`main`
- 默认远程：`ssh://git@ssh.github.com:443/powerfulhang/<repo>.git`

如果 GitHub 侧仓库还不存在，工具会在检测远程时提示先创建仓库。

新建项目页的“创建后初始化 Git”和项目管理页的“重置 Git 配置”都会完成：

- 生成或更新 `.gitignore`
- 生成或更新 `.gitattributes`，减少 Windows 下 LF/CRLF 警告
- 设置 Git 用户名和邮箱
- 设置 GitHub SSH 443 端口远程地址

“推送”会先检测远程仓库。如果 GitHub 侧仓库不存在或 SSH key 无权限，
工具会停止推送并给出明确提示。
推送和拉取会动态读取当前 Git 分支，不再写死 `main` 或 `master`。
如果本地仓库刚初始化、还没有任何提交，“拉取”会自动进入首次拉取流程：
先获取远端信息，再识别远端默认分支并拉取。
如果 `.gitignore` / `.gitattributes` 是工具刚自动生成的未跟踪文件，而远端已有同名文件，
工具会先把本地版本备份到 `.git/program-pm-backups/`，再拉取远端版本。

如果项目尚未初始化 Git，“重置 Git 配置”会提示当前没有 Git 配置，并执行初始化流程。

在项目管理页切换项目路径后，“刷新本地 Git 状态”会优先从 `origin` 远程地址读取
真实 GitHub 仓库名；如果没有 `origin` 或解析失败，才按当前项目文件夹名自动更新仓库名。
如果 `origin` 与仓库名推导出的 GitHub 地址不一致，状态栏会提示使用“重置 Git 配置”更新。
