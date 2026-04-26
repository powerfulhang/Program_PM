# Program PM

Windows 项目管理 GUI 工具，用于：

- 从任意目录启动后，在当前目录创建新项目；
- 从 `F:\Working Files\Coding\AgentFiles` 勾选 AGENTS 文件并创建链接；
- 新建项目时可同步初始化 Git；
- 在 GUI 中执行常见 Git/GitHub 操作；
- 默认使用 GitHub SSH 443 端口远程地址。

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

## GitHub 约定

- GitHub 用户：`powerfulhang`
- 邮箱：`hangshi1023@gmail.com`
- 默认分支：`master`
- 默认远程：`ssh://git@ssh.github.com:443/powerfulhang/<repo>.git`

如果 GitHub 侧仓库还不存在，工具会在检测远程时提示先创建仓库。

“初始化 Git”会一次完成：

- 生成或更新 `.gitignore`
- 生成或更新 `.gitattributes`，减少 Windows 下 LF/CRLF 警告
- 设置 Git 用户名和邮箱
- 设置 GitHub SSH 443 端口远程地址

“推送”会先检测远程仓库。如果 GitHub 侧仓库不存在或 SSH key 无权限，
工具会停止推送并给出明确提示。
