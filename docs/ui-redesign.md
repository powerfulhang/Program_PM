# Git Manager UI Redesign

## Design Sources & References

- **Windows 11 Fluent Design**: Rounded corners, card-based layouts, Mica/Acrylic material, Segoe UI typeface
- **GitHub Desktop**: Sidebar navigation, clean status cards, inline action buttons
- **VS Code**: Activity bar + sidebar pattern, status bar, panel system
- **SourceGit / GitKraken**: Git-specific UI patterns — branch visualization, commit history, staging area
- **Modern Python GUI**: ttkbootstrap (Bootstrap-themed ttk) for Fluent-style appearance with zero C dependencies

---

## Current UI Problems

1. **Tab overload**: "项目管理" tab crams branch management, commit workflow, and release publishing into one dense two-column layout
2. **No visual hierarchy**: All buttons look identical — primary actions (push, commit) have the same weight as secondary ones (检测远程)
3. **Fixed size**: 1060x700, not resizable, wastes space on large screens or feels cramped on small ones
4. **Information overload**: Status metrics, branch list, release list, release form, and 12+ action buttons are all visible simultaneously
5. **No feedback loop**: Operations show popup dialogs that interrupt workflow; no inline progress or status updates
6. **Flat styling**: clam theme with manually-set colors looks dated compared to modern Windows apps

---

## New Design: Sidebar Navigation + Card Layout

### Architecture

```
+------------------------------------------------------+
|  [icon] Git Manager              [_] [□] [X]         |
+--------+---------------------------------------------+
|        |  Header: project path + repo name + status  |
|  Nav   +---------------------------------------------+
|  Bar   |                                             |
|        |  Main Content Area (card grid)              |
|  [+]   |                                             |
|  [!]   |  Changes dynamically based on nav selection |
|  [B]   |                                             |
|  [C]   |                                             |
|  [R]   |                                             |
|        +---------------------------------------------+
|        |  Status Bar: branch | sync | last action    |
+--------+---------------------------------------------+
```

### Navigation Sidebar (Left, 56px)

A narrow icon-based sidebar (like VS Code activity bar):

| Icon | View | Description |
|------|------|-------------|
| `+` | 新建项目 | Project creation with template selection |
| `!` | 概览 | Project overview — status cards, quick actions |
| `B` | 分支 | Branch list, checkout, create, merge |
| `C` | 提交 | Commit history, add, commit, push, pull |
| `R` | 发布 | Release list, create release |

Benefits:
- Each view has focused space instead of cramming everything together
- Icons are always visible — one click to switch
- Active view is highlighted with accent color

### View 1: 新建项目 (Create Project)

```
+--------------------------------------------------+
|  Create New Project                              |
+--------------------------------------------------+
|                                                  |
|  [Card: Project Details]                         |
|    创建位置: [________________________] [选择]   |
|    项目名称: [________________________]          |
|    [x] 创建后初始化 Git                          |
|                                                  |
|  [Card: ModuleFiles]                             |
|    [全选] [全不选] [刷新]                        |
|    +------------------------------------------+  |
|    | [x] .gitignore                           |  |
|    | [x] .gitattributes                       |  |
|    | [ ] README.md                            |  |
|    | [ ] requirements.txt                     |  |
|    +------------------------------------------+  |
|                                                  |
|                            [创建项目 (Accent)]   |
+--------------------------------------------------+
```

### View 2: 概览 (Overview)

```
+--------------------------------------------------+
|  Overview                                        |
+--------------------------------------------------+
|                                                  |
|  [Card Row: Status Cards]                        |
|  +----------+ +----------+ +----------+ +------+ |
|  | 当前分支  | | 上游分支  | | 同步状态  | | 工作区| |
|  | main     | | origin/  | | 已同步    | | 干净  | |
|  |          | | main     | |           | |      | |
|  +----------+ +----------+ +----------+ +------+ |
|                                                  |
|  [Card: Quick Actions]                           |
|  [添加全部] [提交] [推送] [拉取] [获取] [记录]   |
|                                                  |
|  [Card: Recent Activity]                         |
|  +------------------------------------------+    |
|  | abc1234 Update project    2026-05-04     |    |
|  | def5678 Fix login bug     2026-05-03     |    |
|  +------------------------------------------+    |
|                                                  |
+--------------------------------------------------+
```

### View 3: 分支 (Branches)

```
+--------------------------------------------------+
|  Branches                                        |
+--------------------------------------------------+
|                                                  |
|  [Card: Branch Actions]                          |
|    切换到: [main         v] [切换]               |
|    新分支: [____________]  [创建并切换]           |
|                                                  |
|  [Card: Branch List]                             |
|  +------------------------------------------+    |
|  | * main    本地  origin/main  abc  05-04  |    |
|  |   feature 本地              def  05-03   |    |
|  |   origin/dev 远端           ghi  05-02   |    |
|  +------------------------------------------+    |
|                                                  |
|  [Card: Git Config]                              |
|  [检测远程] [重置 Git] [状态详情]                |
|                                                  |
+--------------------------------------------------+
```

### View 4: 提交 (Commits)

```
+--------------------------------------------------+
|  Commits                                         |
+--------------------------------------------------+
|                                                  |
|  [Card: Commit]                                  |
|    提交信息: [Update project_________________]   |
|    [添加全部] [提交]                             |
|                                                  |
|  [Card: Sync]                                    |
|    [推送] [拉取] [获取]                          |
|                                                  |
|  [Card: History]                                 |
|  +------------------------------------------+    |
|  | abc1234 [HEAD -> main] Update project    |    |
|  | def5678 Fix login bug                     |    |
|  | ghi9012 Initial commit                    |    |
|  +------------------------------------------+    |
|                                                  |
+--------------------------------------------------+
```

### View 5: 发布 (Releases)

```
+--------------------------------------------------+
|  Releases                                        |
+--------------------------------------------------+
|                                                  |
|  [Card: Release List]                            |
|  +------------------------------------------+    |
|  | v1.0.0  Latest  Published  2026-05-01    |    |
|  | v0.9.0  Draft   Draft       2026-04-28   |    |
|  +------------------------------------------+    |
|                                                  |
|  [Card: Create Release]                          |
|    Tag:   [v1.0.0____]  标题: [___________]      |
|    说明:  [_______________________________]      |
|    资产:  [_______________________________] [选择]|
|    [x] Draft  [x] Prerelease                     |
|                              [发布 Release]       |
|                                                  |
+--------------------------------------------------+
```

### Status Bar (Bottom, 28px)

```
+--------------------------------------------------+
|  main | origin/main | synced | clean | Ready     |
+--------------------------------------------------+
```

Shows: current branch | upstream | sync state | workspace state | last operation result

---

## Color Scheme

### Light Theme (Default)

| Element | Color | Usage |
|---------|-------|-------|
| Background | `#f9fafb` | Window background |
| Surface | `#ffffff` | Card backgrounds |
| Sidebar BG | `#1e293b` | Dark sidebar (like VS Code) |
| Sidebar Icon | `#94a3b8` | Inactive nav icons |
| Sidebar Active | `#38bdf8` | Active nav icon + accent |
| Text Primary | `#111827` | Main text |
| Text Secondary | `#6b7280` | Muted text, labels |
| Accent | `#2563eb` | Primary buttons, links |
| Accent Hover | `#1d4ed8` | Button hover state |
| Success | `#16a34a` | Synced, clean states |
| Warning | `#f59e0b` | Ahead/behind states |
| Error | `#dc2626` | Failed operations |
| Border | `#e5e7eb` | Card borders |
| Status Bar BG | `#f1f5f9` | Bottom bar |

### Dark Theme (Optional, Phase 2)

| Element | Color |
|---------|-------|
| Background | `#0f172a` |
| Surface | `#1e293b` |
| Sidebar BG | `#0f172a` |
| Text Primary | `#f1f5f9` |
| Text Secondary | `#94a3b8` |
| Accent | `#38bdf8` |
| Border | `#334155` |

---

## Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Window Title | Segoe UI | 12px | Semibold |
| Section Title | Segoe UI | 11px | Semibold |
| Body Text | Segoe UI | 10px | Regular |
| Muted Text | Segoe UI | 9px | Regular |
| Status Bar | Segoe UI | 9px | Regular |
| Code/Mono | Cascadia Code / Consolas | 10px | Regular |

Fallback: Microsoft YaHei UI (for Chinese text rendering)

---

## Spacing & Layout

| Property | Value |
|----------|-------|
| Window min size | 960 x 640 |
| Window default size | 1100 x 720 |
| Window resizable | Yes (min 960x640) |
| Sidebar width | 56px (fixed) |
| Card padding | 16px |
| Card border-radius | 8px |
| Card gap | 12px |
| Section gap | 16px |
| Button padding | 8px 16px |
| Status bar height | 28px |

---

## Technology Choice

### Recommended: ttkbootstrap

| Criteria | ttkbootstrap | customtkinter | Raw ttk |
|----------|-------------|---------------|---------|
| Migration effort | Low (drop-in ttk wrapper) | High (new widget API) | None |
| Modern look | High (Bootstrap themes) | Very High (custom widgets) | Low |
| Dark mode | Built-in themes | Built-in | Manual |
| Dependencies | 1 (pip install) | 1 (pip install) | 0 |
| Stability | High (mature) | High | High |

**ttkbootstrap** is the best choice because:
- Drop-in replacement for ttk — minimal code changes
- Provides Fluent-style themes: `cosmo` (light), `darkly` (dark)
- Built-in accent button styles, card-like frames, modern scrollbars
- Single pip dependency, no native binaries
- Works with PyInstaller

### Theme Selection

- **Light**: `cosmo` — clean, minimal, Bootstrap-inspired
- **Dark**: `darkly` — dark surface with good contrast

---

## Implementation Phases

### Phase 1: Visual Refresh (Low Risk)
- Install ttkbootstrap
- Replace `ttk.Style()` with ttkbootstrap theme
- Apply accent button styles to primary actions
- Add card-like styling to panels
- Keep existing layout structure

### Phase 2: Sidebar Navigation (Medium Risk)
- Replace `ttk.Notebook` with custom sidebar + frame switching
- Split "项目管理" into 概览/分支/提交/发布 views
- Add status bar at bottom

### Phase 3: Responsive Layout (Low Risk)
- Make window resizable with min size
- Card grid adapts to window width
- Scrollable content areas

### Phase 4: Dark Mode (Low Risk)
- Add theme toggle in sidebar or title bar
- Persist preference

---

## File Changes Required

| File | Change |
|------|--------|
| `pyproject.toml` | Add `ttkbootstrap` dependency |
| `git_manager/app.py` | Major refactor — new layout, sidebar, views |
| `git_manager/main.py` | No change |
| `scripts/build.py` | No change |

---

## Preview Mockup (ASCII)

```
+-------+----------------------------------------------------+
| [GM]  |  F:\Projects\MyRepo                    [?] [x]     |
+-------+----------------------------------------------------+
|       |  MyRepo  |  main  |  origin/main  |  synced  | clean|
|  [+]  +----------------------------------------------------+
|       |                                                    |
|  [!]  |  +------------+  +------------+  +----------+     |
|       |  | 当前分支    |  | 上游分支    |  | 同步状态  |     |
|  [B]  |  | main       |  | origin/main |  | 已同步    |     |
|       |  +------------+  +------------+  +----------+     |
|  [C]  |                                                    |
|       |  [添加全部] [提交] [推送] [拉取] [获取] [记录]      |
|  [R]  |                                                    |
|       |  Recent Commits                                    |
|       |  +----------------------------------------------+ |
|       |  | abc1234 [main] Update project   05-04        | |
|       |  | def5678 Fix login bug           05-03        | |
|       |  +----------------------------------------------+ |
|       |                                                    |
+-------+----------------------------------------------------+
|  main  |  origin/main  |  synced  |  clean  |  Ready      |
+-------+----------------------------------------------------+
```
