"""
Git Manager - UI mockup implementation (PySide6)

This is a layout/visual implementation of the Git Manager UI.
Functionality (actual git operations) is intentionally NOT wired up - 
buttons just print their action so you can confirm the layout works.

Run:
    pip install PySide6
    python git_manager.py
"""

import sys
from PySide6.QtCore import Qt, QSize, QRectF, QPointF
from PySide6.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QPainterPath,
    QFontDatabase
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox, QFrame,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidget, QListWidgetItem, QSizePolicy, QScrollArea, QButtonGroup
)


# ----------------------------------------------------------------------------
# Design tokens
# ----------------------------------------------------------------------------
class C:
    # Brand
    PRIMARY        = "#2563eb"
    PRIMARY_HOVER  = "#1d4ed8"
    SUCCESS        = "#16a34a"
    SUCCESS_HOVER  = "#15803d"
    WARNING        = "#f59e0b"
    DANGER         = "#dc2626"

    # Neutrals
    SIDEBAR_BG     = "#0f172a"
    SIDEBAR_ACTIVE = "#1e293b"
    SIDEBAR_HOVER  = "#172033"
    SIDEBAR_BORDER = "#1e293b"

    PAGE_BG        = "#f8fafc"
    CARD_BG        = "#ffffff"
    BORDER         = "#e5e7eb"
    BORDER_STRONG  = "#d1d5db"
    INPUT_BG       = "#ffffff"

    TEXT_PRIMARY   = "#0f172a"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED     = "#94a3b8"
    TEXT_ON_DARK   = "#e2e8f0"
    TEXT_ON_DARK_M = "#94a3b8"


# ----------------------------------------------------------------------------
# Icon factory - draw simple monochrome icons with QPainter
# ----------------------------------------------------------------------------
def make_icon(name: str, color: str = "#ffffff", size: int = 20, weight: float = 2.0) -> QIcon:
    pix = QPixmap(size * 2, size * 2)   # 2x for sharpness
    pix.setDevicePixelRatio(2.0)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(weight)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    s = size  # logical size
    pad = 3

    if name == "plus":
        p.drawLine(s/2, pad, s/2, s - pad)
        p.drawLine(pad, s/2, s - pad, s/2)

    elif name == "grid":  # overview - 4 small rounded squares
        gap = 1.5
        cell = (s - pad*2 - gap) / 2
        for r in range(2):
            for c in range(2):
                x = pad + c * (cell + gap)
                y = pad + r * (cell + gap)
                p.drawRoundedRect(QRectF(x, y, cell, cell), 1.2, 1.2)

    elif name == "branch":  # two dots top-right and bottom-left + connector
        # vertical line
        p.drawLine(s*0.32, pad+1, s*0.32, s - pad - 1)
        # right node
        p.drawEllipse(QPointF(s*0.72, s*0.32), 1.8, 1.8)
        # left bottom node
        p.drawEllipse(QPointF(s*0.32, s - pad - 1), 1.8, 1.8)
        # left top node
        p.drawEllipse(QPointF(s*0.32, pad + 1), 1.8, 1.8)
        # branch curve from main to right node
        path = QPainterPath()
        path.moveTo(s*0.32, s*0.55)
        path.cubicTo(s*0.32, s*0.4, s*0.55, s*0.4, s*0.72, s*0.34)
        p.drawPath(path)

    elif name == "sync":  # circular arrows
        rect = QRectF(pad, pad, s - 2*pad, s - 2*pad)
        # two arcs
        p.drawArc(rect, 30 * 16, 200 * 16)
        p.drawArc(rect, 210 * 16, 200 * 16)
        # arrow heads
        p.setBrush(QColor(color))
        # top arrow head (pointing right at top)
        tri1 = QPainterPath()
        tri1.moveTo(s - pad - 1, s*0.30)
        tri1.lineTo(s - pad - 4.5, s*0.18)
        tri1.lineTo(s - pad - 4.5, s*0.42)
        tri1.closeSubpath()
        p.drawPath(tri1)
        # bottom arrow head
        tri2 = QPainterPath()
        tri2.moveTo(pad + 1, s*0.70)
        tri2.lineTo(pad + 4.5, s*0.58)
        tri2.lineTo(pad + 4.5, s*0.82)
        tri2.closeSubpath()
        p.drawPath(tri2)

    elif name == "tag":
        path = QPainterPath()
        path.moveTo(pad, s*0.45)
        path.lineTo(s*0.55, pad)
        path.lineTo(s - pad, pad)
        path.lineTo(s - pad, s*0.45)
        path.lineTo(s*0.45, s - pad)
        path.closeSubpath()
        p.drawPath(path)
        # hole
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(s*0.72, s*0.28), 1.4, 1.4)

    elif name == "check":  # checkmark inside circle
        p.drawEllipse(QRectF(pad, pad, s - 2*pad, s - 2*pad))
        p.drawPolyline([
            QPointF(s*0.32, s*0.52),
            QPointF(s*0.46, s*0.66),
            QPointF(s*0.70, s*0.38),
        ])

    elif name == "folder":
        # tab
        path = QPainterPath()
        path.moveTo(pad, s*0.32)
        path.lineTo(s*0.42, s*0.32)
        path.lineTo(s*0.50, s*0.22)
        path.lineTo(s - pad, s*0.22)
        path.lineTo(s - pad, s - pad)
        path.lineTo(pad, s - pad)
        path.closeSubpath()
        p.drawPath(path)

    elif name == "branch_up":  # up-arrow style branch (for 上游分支)
        p.drawLine(s/2, s - pad, s/2, pad + 2)
        # arrow head
        p.drawLine(s/2, pad + 2, s*0.32, pad + 6)
        p.drawLine(s/2, pad + 2, s*0.68, pad + 6)
        # small branch
        p.drawLine(s/2, s*0.55, s*0.72, s*0.42)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(s*0.72, s*0.42), 1.6, 1.6)

    p.end()
    return QIcon(pix)


# ----------------------------------------------------------------------------
# Reusable widgets
# ----------------------------------------------------------------------------
class SidebarButton(QPushButton):
    def __init__(self, icon_name: str, label: str):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(make_icon(icon_name, "#ffffff", 24, weight=2.4))
        self.setIconSize(QSize(24, 24))
        self.setText(label)
        self.setFixedHeight(72)
        self.setObjectName("sidebarBtn")


class SectionTitle(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("sectionTitle")


class CardFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("card")


class StatCard(QFrame):
    """Card used on Overview page (current branch / upstream / sync / workspace)."""
    def __init__(self, icon_name: str, icon_color: str, caption: str,
                 value: str, value_color: str = None):
        super().__init__()
        self.setObjectName("statCard")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(make_icon(icon_name, icon_color, 28).pixmap(28, 28))
        icon_lbl.setAlignment(Qt.AlignCenter)

        caption_lbl = QLabel(caption)
        caption_lbl.setObjectName("statCaption")
        caption_lbl.setAlignment(Qt.AlignCenter)

        value_lbl = QLabel(value)
        value_lbl.setObjectName("statValue")
        value_lbl.setAlignment(Qt.AlignCenter)
        if value_color:
            value_lbl.setStyleSheet(f"color: {value_color};")

        layout.addWidget(icon_lbl)
        layout.addWidget(caption_lbl)
        layout.addWidget(value_lbl)


# Helper to build labeled buttons with icon + text in two lines (used elsewhere)
def make_button(text: str, kind: str = "secondary", min_width: int = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setObjectName(f"btn_{kind}")
    btn.setMinimumHeight(34)
    if min_width:
        btn.setMinimumWidth(min_width)
    return btn


# ----------------------------------------------------------------------------
# Top bar (project path + repo info) - shared across pages
# ----------------------------------------------------------------------------
class TopBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("topBar")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 14)
        outer.setSpacing(10)

        # Row 1 - 项目路径
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        lbl = QLabel("项目路径")
        lbl.setObjectName("formLabel")
        lbl.setFixedWidth(56)
        self.path_input = QLineEdit("F:\\Working Files\\Coding\\Program_PM")
        self.path_input.setMinimumHeight(32)
        choose_btn = make_button("选择", "primary", 64)

        row1.addWidget(lbl)
        row1.addWidget(self.path_input, 1)
        row1.addWidget(choose_btn)

        # Row 2 - 仓库 / 分支 / 同步 + 刷新
        row2 = QHBoxLayout()
        row2.setSpacing(20)

        repo_lbl = QLabel()
        repo_lbl.setText('<span style="color:#475569;">仓库:</span> '
                         '<b style="color:#0f172a;">Program_PM</b>')
        branch_lbl = QLabel()
        branch_lbl.setText('<span style="color:#475569;">分支:</span> '
                           '<span style="color:#0f172a;">master</span>')
        sync_lbl = QLabel()
        sync_lbl.setText('<span style="color:#475569;">同步:</span> '
                         '<span style="color:#16a34a;">已同步</span>')

        refresh_btn = make_button("刷新", "secondary", 64)

        row2.addWidget(repo_lbl)
        row2.addWidget(branch_lbl)
        row2.addWidget(sync_lbl)
        row2.addStretch(1)
        row2.addWidget(refresh_btn)

        outer.addLayout(row1)
        outer.addLayout(row2)


# ----------------------------------------------------------------------------
# Status bar at bottom
# ----------------------------------------------------------------------------
class FooterBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("footerBar")
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        parts = [
            ("Git 本地状态",  "#475569", False),
            ("|",             "#cbd5e1", False),
            ("分支:",         "#475569", False),
            ("master",        "#0f172a", False),
            ("|",             "#cbd5e1", False),
            ("origin:",       "#475569", False),
            ("ssh://git@ssh.github.com:443/powerfulhang/Program_PM.git",
                              "#0f172a", False),
        ]
        for text, color, _ in parts:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            layout.addWidget(lbl)
        layout.addStretch(1)


# ----------------------------------------------------------------------------
# Page 1 - 新建 (New project)
# ----------------------------------------------------------------------------
class NewPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 16)
        layout.setSpacing(16)

        # ---- LEFT card: 项目信息 ----
        left = CardFrame()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 18, 20, 18)
        ll.setSpacing(12)
        ll.addWidget(SectionTitle("项目信息"))

        ll.addWidget(self._form_label("创建位置"))
        loc_row = QHBoxLayout()
        loc_row.setSpacing(8)
        loc_input = QLineEdit("F:\\Working Files\\Coding\\Program_PM")
        loc_input.setMinimumHeight(32)
        browse = make_button("浏览", "secondary", 64)
        loc_row.addWidget(loc_input, 1)
        loc_row.addWidget(browse)
        ll.addLayout(loc_row)

        ll.addWidget(self._form_label("项目名称"))
        name_input = QLineEdit("Program_PM")
        name_input.setMinimumHeight(32)
        ll.addWidget(name_input)

        ll.addSpacing(4)
        cb = QCheckBox("创建后初始化 Git 仓库")
        cb.setObjectName("formCheckbox")
        ll.addWidget(cb)

        create_btn = QPushButton("创建项目")
        create_btn.setObjectName("btn_primary")
        create_btn.setMinimumHeight(40)
        create_btn.setCursor(Qt.PointingHandCursor)
        ll.addWidget(create_btn)

        helper = QLabel("ⓘ  模板文件会复制到新项目目录中；\n     复制后不再跟踪源模板自动更新。")
        helper.setObjectName("helperText")
        helper.setWordWrap(True)
        ll.addWidget(helper)
        ll.addStretch(1)

        # ---- RIGHT card: 模板文件 (ModuleFiles) ----
        right = CardFrame()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 18, 20, 18)
        rl.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(SectionTitle("模板文件 (ModuleFiles)"))
        head.addStretch(1)
        for t in ("全选", "全不选", "刷新"):
            head.addWidget(make_button(t, "secondary", 60))
        rl.addLayout(head)

        files = [
            ".gitattributes", ".gitignore", "AGENTS.md", "README.md",
            "CHANGELOG.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "LICENSE",
        ]
        files_list = QWidget()
        fl = QVBoxLayout(files_list)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.setSpacing(8)
        for f in files:
            chk = QCheckBox(f)
            chk.setChecked(True)
            chk.setObjectName("fileCheckbox")
            fl.addWidget(chk)
        fl.addStretch(1)
        rl.addWidget(files_list, 1)

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

    @staticmethod
    def _form_label(text):
        lbl = QLabel(text)
        lbl.setObjectName("formLabel")
        return lbl


# ----------------------------------------------------------------------------
# Page 2 - 概览 (Overview)
# ----------------------------------------------------------------------------
class OverviewPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 16)
        layout.setSpacing(16)

        # 4 status cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.addWidget(StatCard("branch",    C.PRIMARY, "当前分支",   "master"))
        cards_row.addWidget(StatCard("branch_up", C.PRIMARY, "上游分支",   "origin/master"))
        cards_row.addWidget(StatCard("check",     C.SUCCESS, "同步状态",   "已同步", C.SUCCESS))
        cards_row.addWidget(StatCard("folder",    C.WARNING, "工作区",     "14 项改动", C.WARNING))
        layout.addLayout(cards_row)

        # 仓库配置
        repo_card = CardFrame()
        rcl = QVBoxLayout(repo_card)
        rcl.setContentsMargins(20, 18, 20, 18)
        rcl.setSpacing(12)
        rcl.addWidget(SectionTitle("仓库配置"))

        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addWidget(self._lbl("仓库名"), 0, 0)
        form.addWidget(self._lbl("默认分支"), 0, 1)
        e1 = QLineEdit("Program_PM"); e1.setMinimumHeight(32)
        e2 = QLineEdit("master");     e2.setMinimumHeight(32)
        form.addWidget(e1, 1, 0)
        form.addWidget(e2, 1, 1)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        rcl.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        for t in ("刷新", "检测远程", "重置 Git", "状态详情"):
            btn_row.addWidget(make_button(t, "secondary"))
        rcl.addLayout(btn_row)
        layout.addWidget(repo_card)

        # 快捷入口
        quick_card = CardFrame()
        qcl = QVBoxLayout(quick_card)
        qcl.setContentsMargins(20, 18, 20, 18)
        qcl.setSpacing(12)
        qcl.addWidget(SectionTitle("快捷入口"))

        q_row = QHBoxLayout()
        q_row.setSpacing(16)
        q_row.addWidget(self._quick_btn("branch", C.PRIMARY, "分支管理", C.PRIMARY))
        q_row.addWidget(self._quick_btn("sync",   C.SUCCESS, "提交同步", C.SUCCESS))
        q_row.addWidget(self._quick_btn("tag",    "#7c3aed", "版本发布", "#7c3aed"))
        qcl.addLayout(q_row)
        layout.addWidget(quick_card)
        layout.addStretch(1)

    @staticmethod
    def _lbl(t):
        l = QLabel(t); l.setObjectName("formLabel"); return l

    @staticmethod
    def _quick_btn(icon, icon_color, text, text_color):
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(56)
        btn.setObjectName("quickBtn")
        btn.setStyleSheet(f"""
            QPushButton#quickBtn {{
                background: #ffffff;
                border: 1.5px solid {icon_color};
                border-radius: 6px;
                color: {text_color};
                font-size: 14px;
                font-weight: 600;
                padding: 0 18px;
            }}
            QPushButton#quickBtn:hover {{ background: #f8fafc; }}
        """)
        btn.setIcon(make_icon(icon, icon_color, 18))
        btn.setIconSize(QSize(18, 18))
        btn.setText("  " + text)
        return btn


# ----------------------------------------------------------------------------
# Page 3 - 分支 (Branches)
# ----------------------------------------------------------------------------
class BranchPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 16)
        layout.setSpacing(16)

        # 分支操作
        op_card = CardFrame()
        ocl = QVBoxLayout(op_card)
        ocl.setContentsMargins(20, 18, 20, 18)
        ocl.setSpacing(10)
        ocl.addWidget(SectionTitle("分支操作"))

        # 切换到 row
        r1 = QHBoxLayout(); r1.setSpacing(10)
        l1 = QLabel("切换到"); l1.setObjectName("formLabel"); l1.setFixedWidth(56)
        cb = QComboBox(); cb.addItems(["master", "main", "origin/master", "origin/main"])
        cb.setMinimumHeight(32)
        switch_btn = make_button("切换", "primary", 80)
        r1.addWidget(l1); r1.addWidget(cb, 1); r1.addWidget(switch_btn)
        ocl.addLayout(r1)

        # 新分支 row
        r2 = QHBoxLayout(); r2.setSpacing(10)
        l2 = QLabel("新分支"); l2.setObjectName("formLabel"); l2.setFixedWidth(56)
        new_input = QLineEdit(); new_input.setPlaceholderText("输入新分支名"); new_input.setMinimumHeight(32)
        create_sw = make_button("创建并切换", "primary", 110)
        r2.addWidget(l2); r2.addWidget(new_input, 1); r2.addWidget(create_sw)
        ocl.addLayout(r2)

        helper = QLabel("ⓘ  本地分支可以直接切换；origin/* 是远端引用，切换时会创建跟踪到对应的本地跟踪分支。")
        helper.setObjectName("helperText")
        helper.setWordWrap(True)
        ocl.addWidget(helper)
        layout.addWidget(op_card)

        # 分支列表
        list_card = CardFrame()
        lcl = QVBoxLayout(list_card)
        lcl.setContentsMargins(20, 18, 20, 18)
        lcl.setSpacing(12)
        lcl.addWidget(SectionTitle("分支列表"))

        table = QTableWidget(4, 6)
        table.setHorizontalHeaderLabels(["分支", "类型", "上游", "提交", "日期", "说明"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col in range(5):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        table.setColumnWidth(0, 160)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 160)
        table.setColumnWidth(3, 100)
        table.setColumnWidth(4, 120)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setMinimumHeight(180)

        rows = [
            ("* master",       "本地", "origin/master", "0fb8fb4", "2026-05-02", "Update proj..."),
            ("origin/master",  "远端", "origin/master", "0fb8fb4", "2026-05-02", "Update proj..."),
            ("main",           "本地", "origin/main",   "2d8e8e1", "2026-05-02", "Update proj..."),
            ("origin/main",    "远端", "origin/main",   "2d8e8e1", "2026-05-02", "Update proj..."),
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                if c == 0 and val.startswith("*"):
                    f = item.font(); f.setBold(True); item.setFont(f)
                    item.setForeground(QColor(C.PRIMARY))
                table.setItem(r, c, item)
        lcl.addWidget(table)

        b_row = QHBoxLayout(); b_row.setSpacing(10)
        for t in ("获取远程", "检测远程", "重置 Git", "状态详情"):
            b_row.addWidget(make_button(t, "secondary"))
        lcl.addLayout(b_row)
        layout.addWidget(list_card, 1)


# ----------------------------------------------------------------------------
# Page 4 - 提交 (Commit)
# ----------------------------------------------------------------------------
class CommitPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 16)
        layout.setSpacing(16)

        # 提交
        commit_card = CardFrame()
        ccl = QVBoxLayout(commit_card)
        ccl.setContentsMargins(20, 18, 20, 18)
        ccl.setSpacing(10)
        ccl.addWidget(SectionTitle("提交"))

        row = QHBoxLayout(); row.setSpacing(10)
        l = QLabel("提交信息"); l.setObjectName("formLabel"); l.setFixedWidth(64)
        msg = QLineEdit("Update project"); msg.setMinimumHeight(32)
        add_all = make_button("添加全部", "secondary", 80)
        commit_btn = make_button("提交", "primary", 80)
        row.addWidget(l); row.addWidget(msg, 1); row.addWidget(add_all); row.addWidget(commit_btn)
        ccl.addLayout(row)
        layout.addWidget(commit_card)

        # 同步
        sync_card = CardFrame()
        scl = QVBoxLayout(sync_card)
        scl.setContentsMargins(20, 18, 20, 18)
        scl.setSpacing(10)
        scl.addWidget(SectionTitle("同步"))

        srow = QHBoxLayout(); srow.setSpacing(12)
        push_btn = make_button("推送", "success");      push_btn.setMinimumHeight(40)
        pull_btn = make_button("拉取", "secondary");    pull_btn.setMinimumHeight(40)
        fetch_btn = make_button("获取", "secondary");   fetch_btn.setMinimumHeight(40)
        srow.addWidget(push_btn, 1)
        srow.addWidget(pull_btn, 1)
        srow.addWidget(fetch_btn, 1)
        scl.addLayout(srow)
        layout.addWidget(sync_card)

        # 提交历史
        hist_card = CardFrame()
        hcl = QVBoxLayout(hist_card)
        hcl.setContentsMargins(20, 18, 20, 18)
        hcl.setSpacing(10)
        hcl.addWidget(SectionTitle("提交历史 / 操作记录"))

        hist = QListWidget()
        hist.setObjectName("historyList")
        hist.setFrameShape(QFrame.NoFrame)
        entries = [
            ("0fb8fb4", "2026-05-02", "Update project"),
            ("2d8e8e1", "2026-05-02", "Update project"),
            ("76fa26d", "2026-05-02", "Improve help menu and documentation"),
            ("a1b2c3d", "2026-04-30", "Initial commit"),
        ]
        for sha, date, msg in entries:
            txt = f"  {sha:<12}{date:<14}{msg}"
            it = QListWidgetItem(txt)
            f = QFont("Consolas, Menlo, monospace"); f.setPointSize(10)
            it.setFont(f)
            hist.addItem(it)
        hist.setMinimumHeight(160)
        hcl.addWidget(hist, 1)

        refresh_row = QHBoxLayout()
        refresh_row.addWidget(make_button("刷新日志", "secondary", 80))
        refresh_row.addStretch(1)
        hcl.addLayout(refresh_row)
        layout.addWidget(hist_card, 1)


# ----------------------------------------------------------------------------
# Page 5 - 发布 (Release)
# ----------------------------------------------------------------------------
class ReleasePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 16)
        layout.setSpacing(16)

        # Release 列表
        list_card = CardFrame()
        lcl = QVBoxLayout(list_card)
        lcl.setContentsMargins(20, 18, 20, 18)
        lcl.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(SectionTitle("Release 列表"))
        head.addStretch(1)
        lcl.addLayout(head)

        sub = QLabel()
        sub.setText('<span style="color:#475569;">Latest Release:</span> '
                    '<b style="color:#0f172a;">v1.0.0</b> '
                    '<span style="color:#94a3b8;">|</span> '
                    '<span style="color:#16a34a;">Latest</span>')
        lcl.addWidget(sub)

        table = QTableWidget(1, 5)
        table.setHorizontalHeaderLabels(["Release", "状态", "Tag", "发布时间", "来源"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setShowGrid(False)
        table.setMinimumHeight(90)
        table.setMaximumHeight(110)
        for col in range(4):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 160)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 100)
        table.setColumnWidth(3, 160)
        row = ("Calculator v1.0.0", "Latest", "v1.0.0", "2026-05-02 01:58:31", "GitHub")
        for c, v in enumerate(row):
            item = QTableWidgetItem(v)
            if c == 1:
                item.setForeground(QColor(C.SUCCESS))
            table.setItem(0, c, item)
        table.verticalHeader().setDefaultSectionSize(36)
        lcl.addWidget(table)

        layout.addWidget(list_card)

        # 创建 Release
        create_card = CardFrame()
        ccl = QVBoxLayout(create_card)
        ccl.setContentsMargins(20, 18, 20, 18)
        ccl.setSpacing(10)
        ccl.addWidget(SectionTitle("创建 Release"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        grid.addWidget(self._lbl("Tag"),   0, 0)
        grid.addWidget(self._lbl("标题"),  0, 2)
        e_tag = QLineEdit("v1.0.0");                e_tag.setMinimumHeight(32)
        e_title = QLineEdit("Calculator v1.0.0");   e_title.setMinimumHeight(32)
        grid.addWidget(e_tag,   1, 0, 1, 2)
        grid.addWidget(e_title, 1, 2, 1, 2)

        grid.addWidget(self._lbl("说明"), 2, 0)
        e_desc = QLineEdit("Update project"); e_desc.setMinimumHeight(32)
        grid.addWidget(e_desc, 3, 0, 1, 4)

        grid.addWidget(self._lbl("资产"), 4, 0)
        asset_row = QHBoxLayout(); asset_row.setSpacing(8)
        e_asset = QLineEdit("F:\\Working Files\\Coding\\Program_PM\\dist\\Program_PM.zip")
        e_asset.setMinimumHeight(32)
        browse = make_button("浏览", "secondary", 64)
        asset_row.addWidget(e_asset, 1); asset_row.addWidget(browse)
        wrap = QWidget(); wrap.setLayout(asset_row)
        grid.addWidget(wrap, 5, 0, 1, 4)

        grid.setColumnStretch(0, 0); grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0); grid.setColumnStretch(3, 1)
        ccl.addLayout(grid)

        bot_row = QHBoxLayout(); bot_row.setSpacing(20)
        cb1 = QCheckBox("Draft"); cb1.setObjectName("formCheckbox")
        cb2 = QCheckBox("Prerelease"); cb2.setObjectName("formCheckbox")
        bot_row.addWidget(cb1); bot_row.addWidget(cb2); bot_row.addStretch(1)
        publish = make_button("发布 Release", "primary", 130)
        publish.setMinimumHeight(36)
        bot_row.addWidget(publish)
        ccl.addLayout(bot_row)

        layout.addWidget(create_card, 1)

    @staticmethod
    def _lbl(t):
        l = QLabel(t); l.setObjectName("formLabel"); return l


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
class Sidebar(QWidget):
    def __init__(self, on_change):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(76)
        self.on_change = on_change

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 18, 0, 12)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("GM")
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedHeight(64)
        layout.addWidget(logo)

        # Buttons
        items = [
            ("plus",   "新建"),
            ("grid",   "概览"),
            ("branch", "分支"),
            ("sync",   "提交"),
            ("tag",    "发布"),
        ]
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (icon, label) in enumerate(items):
            btn = SidebarButton(icon, label)
            self.group.addButton(btn, i)
            layout.addWidget(btn)

        layout.addStretch(1)
        self.group.idClicked.connect(self.on_change)

    def select(self, index: int):
        btn = self.group.button(index)
        if btn:
            btn.setChecked(True)


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Manager")
        self.resize(1080, 720)
        self.setMinimumSize(960, 640)

        # central layout: sidebar | (top + stacked + footer)
        central = QWidget()
        central.setObjectName("centralRoot")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(self._switch)
        root.addWidget(self.sidebar)

        right = QWidget()
        right.setObjectName("rightPane")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        self.topbar = TopBar()
        rl.addWidget(self.topbar)

        # divider line under top bar
        divider = QFrame(); divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"color:{C.BORDER}; background:{C.BORDER}; max-height:1px;")
        divider.setFixedHeight(1)
        rl.addWidget(divider)

        # stacked pages
        self.stack = QStackedWidget()
        self.stack.addWidget(NewPage())       # 0
        self.stack.addWidget(OverviewPage())  # 1
        self.stack.addWidget(BranchPage())    # 2
        self.stack.addWidget(CommitPage())    # 3
        self.stack.addWidget(ReleasePage())   # 4
        rl.addWidget(self.stack, 1)

        # footer
        rl.addWidget(self._make_divider())
        self.footer = FooterBar()
        rl.addWidget(self.footer)

        root.addWidget(right, 1)
        self.setCentralWidget(central)

        self.sidebar.select(0)
        self.stack.setCurrentIndex(0)

    @staticmethod
    def _make_divider():
        d = QFrame(); d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(f"color:{C.BORDER}; background:{C.BORDER}; max-height:1px;")
        d.setFixedHeight(1)
        return d

    def _switch(self, idx):
        self.stack.setCurrentIndex(idx)


# ----------------------------------------------------------------------------
# Stylesheet (QSS)
# ----------------------------------------------------------------------------
QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
    color: {C.TEXT_PRIMARY};
}}

QWidget#centralRoot {{ background: {C.PAGE_BG}; }}
QWidget#rightPane    {{ background: {C.PAGE_BG}; }}

/* ---------------- Sidebar ---------------- */
QWidget#sidebar {{
    background: {C.SIDEBAR_BG};
}}
QWidget#sidebar QLabel#sidebarLogo {{
    color: #ffffff;
    background: {C.SIDEBAR_ACTIVE};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 1px;
    margin: 0 12px 8px 12px;
    border-radius: 6px;
    padding: 14px 0;
    qproperty-alignment: 'AlignCenter';
}}
QWidget#sidebar QPushButton#sidebarBtn {{
    background: transparent;
    color: #cbd5e1;
    border: none;
    border-left: 3px solid transparent;
    text-align: center;
    padding: 8px 0 6px 0;
    font-size: 12px;
    font-weight: 500;
}}
QWidget#sidebar QPushButton#sidebarBtn::menu-indicator {{ image: none; }}
QWidget#sidebar QPushButton#sidebarBtn:hover {{
    background: {C.SIDEBAR_HOVER};
    color: #ffffff;
}}
QWidget#sidebar QPushButton#sidebarBtn:checked {{
    background: {C.SIDEBAR_ACTIVE};
    color: #ffffff;
    border-left: 3px solid {C.PRIMARY};
}}

/* ---------------- Top bar ---------------- */
QWidget#topBar {{
    background: {C.PAGE_BG};
}}

/* ---------------- Footer ---------------- */
QWidget#footerBar {{
    background: {C.PAGE_BG};
}}

/* ---------------- Cards & sections ---------------- */
QFrame#card, QFrame#statCard {{
    background: {C.CARD_BG};
    border: 1px solid {C.BORDER};
    border-radius: 8px;
}}
QLabel#sectionTitle {{
    color: {C.TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 2px;
}}
QLabel#formLabel {{
    color: {C.TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#helperText {{
    color: {C.TEXT_MUTED};
    font-size: 11px;
    padding-top: 4px;
}}
QLabel#statCaption {{
    color: {C.TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#statValue {{
    color: {C.TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
}}

/* ---------------- Inputs ---------------- */
QLineEdit, QComboBox {{
    background: {C.INPUT_BG};
    border: 1px solid {C.BORDER_STRONG};
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 13px;
    selection-background-color: {C.PRIMARY};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {C.PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C.TEXT_SECONDARY};
    margin-right: 8px;
}}

/* ---------------- Checkboxes ---------------- */
QCheckBox {{
    color: {C.TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid {C.BORDER_STRONG};
    border-radius: 3px;
    background: #ffffff;
}}
QCheckBox::indicator:hover {{ border-color: {C.PRIMARY}; }}
QCheckBox::indicator:checked {{
    background: {C.PRIMARY};
    border-color: {C.PRIMARY};
    image: none;
}}
QCheckBox#formCheckbox {{ color: {C.TEXT_SECONDARY}; }}
QCheckBox#fileCheckbox {{ color: {C.TEXT_PRIMARY}; font-size: 13px; }}

/* ---------------- Buttons ---------------- */
QPushButton#btn_primary {{
    background: {C.PRIMARY};
    color: #ffffff;
    border: 1px solid {C.PRIMARY};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_primary:hover  {{ background: {C.PRIMARY_HOVER}; border-color: {C.PRIMARY_HOVER}; }}
QPushButton#btn_primary:pressed {{ background: #1e40af; }}

QPushButton#btn_success {{
    background: {C.SUCCESS};
    color: #ffffff;
    border: 1px solid {C.SUCCESS};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_success:hover  {{ background: {C.SUCCESS_HOVER}; border-color: {C.SUCCESS_HOVER}; }}

QPushButton#btn_secondary {{
    background: #ffffff;
    color: {C.PRIMARY};
    border: 1px solid {C.PRIMARY};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_secondary:hover  {{ background: #eff6ff; }}
QPushButton#btn_secondary:pressed {{ background: #dbeafe; }}

QPushButton#btn_danger {{
    background: #ffffff;
    color: {C.DANGER};
    border: 1px solid {C.DANGER};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_danger:hover {{ background: #fef2f2; }}

/* ---------------- Tables ---------------- */
QTableWidget {{
    background: #ffffff;
    border: 1px solid {C.BORDER};
    border-radius: 4px;
    gridline-color: {C.BORDER};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background: #eff6ff;
    color: {C.TEXT_PRIMARY};
}}
QHeaderView::section {{
    background: #f1f5f9;
    color: {C.TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {C.BORDER};
    padding: 8px;
    font-weight: 600;
    font-size: 12px;
}}

/* ---------------- List widget (history) ---------------- */
QListWidget#historyList {{
    background: #ffffff;
    border: 1px solid {C.BORDER};
    border-radius: 4px;
    font-size: 12px;
}}
QListWidget#historyList::item {{
    padding: 6px 8px;
    border-bottom: 1px solid #f1f5f9;
}}
QListWidget#historyList::item:selected {{
    background: #eff6ff;
    color: {C.TEXT_PRIMARY};
}}

/* ---------------- Scrollbars ---------------- */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #cbd5e1; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: #94a3b8; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
"""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    # Default font
    f = QFont("Microsoft YaHei UI", 10)
    app.setFont(f)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
