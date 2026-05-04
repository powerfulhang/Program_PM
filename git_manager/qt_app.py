from __future__ import annotations

import argparse
import ctypes
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from git_manager.git_backend import (
    AUTO_GENERATED_CONFIG_FILES,
    DEFAULT_BRANCH,
    GITHUB_USER,
    MODULEFILES_DIR,
    REMOTE_NAME,
    backup_first_pull_conflicts,
    configure_git_remote,
    configured_or_default_remote,
    configured_repo_full_name,
    copy_module_file,
    current_git_branch,
    current_git_upstream,
    ensure_gitattributes,
    ensure_gitignore,
    explain_remote_result,
    find_gh_executable,
    git_ahead_behind,
    git_dirty_count,
    github_remote,
    has_local_commits,
    initialize_git_repository,
    list_branches,
    list_module_files,
    list_release_info,
    remote_default_branch,
    repository_name_from_remote_url,
    restore_backups,
    run_command,
    sanitize_project_name,
    summarize_git_log,
    summarize_git_status,
    summarize_simple_git_result,
)


SIDEBAR_WIDTH = 102
CONTENT_LEFT_GAP = 16
PAGE_TOP_GAP = 18


class C:
    PRIMARY = "#2563eb"
    PRIMARY_HOVER = "#1d4ed8"
    SUCCESS = "#16a34a"
    SUCCESS_HOVER = "#15803d"
    WARNING = "#f59e0b"
    DANGER = "#dc2626"
    SIDEBAR_BG = "#0f172a"
    SIDEBAR_ACTIVE = "#1e293b"
    SIDEBAR_HOVER = "#172033"
    PAGE_BG = "#f8fafc"
    CARD_BG = "#ffffff"
    BORDER = "#e5e7eb"
    BORDER_STRONG = "#d1d5db"
    INPUT_BG = "#ffffff"
    TEXT_PRIMARY = "#0f172a"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED = "#94a3b8"


def make_icon(name: str, color: str = "#ffffff", size: int = 20, weight: float = 2.0) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    pix.setDevicePixelRatio(2.0)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(weight)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    s = size
    pad = 3
    if name == "plus":
        painter.drawLine(s / 2, pad, s / 2, s - pad)
        painter.drawLine(pad, s / 2, s - pad, s / 2)
    elif name == "grid":
        gap = 1.5
        cell = (s - pad * 2 - gap) / 2
        for row in range(2):
            for col in range(2):
                x = pad + col * (cell + gap)
                y = pad + row * (cell + gap)
                painter.drawRoundedRect(QRectF(x, y, cell, cell), 1.2, 1.2)
    elif name == "branch":
        painter.drawLine(s * 0.32, pad + 1, s * 0.32, s - pad - 1)
        painter.drawEllipse(QPointF(s * 0.72, s * 0.32), 1.8, 1.8)
        painter.drawEllipse(QPointF(s * 0.32, s - pad - 1), 1.8, 1.8)
        painter.drawEllipse(QPointF(s * 0.32, pad + 1), 1.8, 1.8)
        path = QPainterPath()
        path.moveTo(s * 0.32, s * 0.55)
        path.cubicTo(s * 0.32, s * 0.4, s * 0.55, s * 0.4, s * 0.72, s * 0.34)
        painter.drawPath(path)
    elif name == "sync":
        rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
        painter.drawArc(rect, 30 * 16, 200 * 16)
        painter.drawArc(rect, 210 * 16, 200 * 16)
    elif name == "tag":
        path = QPainterPath()
        path.moveTo(pad, s * 0.45)
        path.lineTo(s * 0.55, pad)
        path.lineTo(s - pad, pad)
        path.lineTo(s - pad, s * 0.45)
        path.lineTo(s * 0.45, s - pad)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawEllipse(QPointF(s * 0.72, s * 0.28), 1.4, 1.4)
    elif name == "check":
        painter.drawEllipse(QRectF(pad, pad, s - 2 * pad, s - 2 * pad))
        painter.drawPolyline(
            [
                QPointF(s * 0.32, s * 0.52),
                QPointF(s * 0.46, s * 0.66),
                QPointF(s * 0.70, s * 0.38),
            ]
        )
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(pad, s * 0.32)
        path.lineTo(s * 0.42, s * 0.32)
        path.lineTo(s * 0.50, s * 0.22)
        path.lineTo(s - pad, s * 0.22)
        path.lineTo(s - pad, s - pad)
        path.lineTo(pad, s - pad)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "branch_up":
        painter.drawLine(s / 2, s - pad, s / 2, pad + 2)
        painter.drawLine(s / 2, pad + 2, s * 0.32, pad + 6)
        painter.drawLine(s / 2, pad + 2, s * 0.68, pad + 6)
        painter.drawLine(s / 2, s * 0.55, s * 0.72, s * 0.42)
        painter.drawEllipse(QPointF(s * 0.72, s * 0.42), 1.6, 1.6)

    painter.end()
    return QIcon(pix)


def make_button(text: str, kind: str = "secondary", min_width: int | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.PointingHandCursor)
    button.setObjectName(f"btn_{kind}")
    button.setMinimumHeight(34)
    if min_width:
        button.setMinimumWidth(min_width)
    return button


class CardFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")


class SectionTitle(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("sectionTitle")


class AppCheckBox(QCheckBox):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setObjectName("appCheckBox")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(24)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(text_width + 34, 24)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return self.sizeHint()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        box_size = 17
        box_x = 0
        box_y = (self.height() - box_size) // 2
        border = QColor(C.PRIMARY if self.isChecked() else "#cbd5e1")
        fill = QColor("#ffffff")
        if not self.isEnabled():
            border = QColor("#d1d5db")
            fill = QColor("#f1f5f9")

        painter.setPen(QPen(border, 1.6))
        painter.setBrush(fill)
        painter.drawRoundedRect(box_x, box_y, box_size, box_size, 3, 3)

        if self.isChecked():
            painter.setPen(QPen(QColor(C.PRIMARY), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QPainterPath()
            path.moveTo(box_x + 4.2, box_y + 8.8)
            path.lineTo(box_x + 7.4, box_y + 12.0)
            path.lineTo(box_x + 13.0, box_y + 5.2)
            painter.drawPath(path)

        text_color = QColor(C.TEXT_PRIMARY if self.isEnabled() else C.TEXT_MUTED)
        painter.setPen(text_color)
        painter.setFont(self.font())
        text_rect = self.rect().adjusted(box_size + 9, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())


class SidebarButton(QPushButton):
    def __init__(self, icon_name: str, label: str) -> None:
        super().__init__(label)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(make_icon(icon_name, "#ffffff", 24, weight=2.4))
        self.setIconSize(QSize(24, 24))
        self.setFixedHeight(72)
        self.setObjectName("sidebarBtn")


class StatCard(QFrame):
    def __init__(self, icon_name: str, icon_color: str, caption: str) -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setMinimumHeight(120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon_name, icon_color, 28).pixmap(28, 28))
        icon_label.setAlignment(Qt.AlignCenter)
        caption_label = QLabel(caption)
        caption_label.setObjectName("statCaption")
        caption_label.setAlignment(Qt.AlignCenter)
        self.value_label = QLabel("-")
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_label)
        layout.addWidget(caption_label)
        layout.addWidget(self.value_label)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value_label.setText(text)
        self.value_label.setStyleSheet(f"color: {color};" if color else "")


class TopBar(QWidget):
    def __init__(self, start_dir: Path) -> None:
        super().__init__()
        self.setObjectName("topBar")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        logo_panel = QWidget()
        logo_panel.setObjectName("sidebarLogoPanel")
        logo_panel.setFixedWidth(SIDEBAR_WIDTH)
        logo_layout = QVBoxLayout(logo_panel)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(0)
        logo = QLabel("GM")
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo_layout.addWidget(logo, 1)
        root.addWidget(logo_panel)

        content_shell = QWidget()
        content_shell.setObjectName("topBarContentShell")
        shell_layout = QVBoxLayout(content_shell)
        shell_layout.setContentsMargins(CONTENT_LEFT_GAP, 10, 20, 10)
        shell_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("topBarContent")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(18, 12, 18, 12)
        outer.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        label = QLabel("项目路径")
        label.setObjectName("formLabel")
        label.setFixedWidth(56)
        self.path_input = QLineEdit(str(start_dir))
        self.path_input.setMinimumHeight(32)
        self.choose_btn = make_button("选择", "primary", 64)
        row1.addWidget(label)
        row1.addWidget(self.path_input, 1)
        row1.addWidget(self.choose_btn)

        row2 = QHBoxLayout()
        row2.setSpacing(20)
        self.repo_label = QLabel()
        self.branch_label = QLabel()
        self.sync_label = QLabel()
        self.refresh_btn = make_button("刷新", "secondary", 64)
        row2.addWidget(self.repo_label)
        row2.addWidget(self.branch_label)
        row2.addWidget(self.sync_label)
        row2.addStretch(1)
        row2.addWidget(self.refresh_btn)

        outer.addLayout(row1)
        outer.addLayout(row2)
        shell_layout.addWidget(content)
        root.addWidget(content_shell, 1)


class FooterBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("footerBar")
        self.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(12)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.status_label, 1)


class NewPage(QWidget):
    def __init__(self, start_dir: Path) -> None:
        super().__init__()
        self.module_checks: dict[Path, QCheckBox] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(CONTENT_LEFT_GAP, PAGE_TOP_GAP, 20, 16)
        layout.setSpacing(16)

        left = CardFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 18, 20, 18)
        left_layout.setSpacing(12)
        left_layout.addWidget(SectionTitle("项目信息"))
        left_layout.addWidget(self._label("创建位置"))

        path_row = QHBoxLayout()
        self.base_input = QLineEdit(str(start_dir))
        self.base_input.setMinimumHeight(32)
        self.browse_btn = make_button("浏览", "secondary", 64)
        path_row.addWidget(self.base_input, 1)
        path_row.addWidget(self.browse_btn)
        left_layout.addLayout(path_row)

        left_layout.addWidget(self._label("项目名称"))
        self.name_input = QLineEdit(start_dir.name)
        self.name_input.setMinimumHeight(32)
        left_layout.addWidget(self.name_input)

        self.init_git_check = AppCheckBox("创建后初始化 Git 仓库")
        self.init_git_check.setObjectName("formCheckbox")
        self.init_git_check.setChecked(True)
        left_layout.addWidget(self.init_git_check)

        self.create_btn = make_button("创建项目", "primary")
        self.create_btn.setMinimumHeight(40)
        left_layout.addWidget(self.create_btn)
        helper = QLabel("模板文件会复制到新项目目录中；复制后不再跟踪源模板自动更新。")
        helper.setObjectName("helperText")
        helper.setWordWrap(True)
        left_layout.addWidget(helper)
        left_layout.addStretch(1)

        right = CardFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 18, 20, 18)
        right_layout.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(SectionTitle("模板文件 (ModuleFiles)"))
        head.addStretch(1)
        self.select_all_btn = make_button("全选", "secondary", 60)
        self.clear_btn = make_button("全不选", "secondary", 60)
        self.reload_btn = make_button("刷新", "secondary", 60)
        head.addWidget(self.select_all_btn)
        head.addWidget(self.clear_btn)
        head.addWidget(self.reload_btn)
        right_layout.addLayout(head)

        self.module_inner = QWidget()
        self.module_inner.setObjectName("moduleList")
        self.module_layout = QVBoxLayout(self.module_inner)
        self.module_layout.setContentsMargins(0, 4, 0, 0)
        self.module_layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setObjectName("moduleScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.module_inner)
        right_layout.addWidget(scroll, 1)

        layout.addWidget(left, 1)
        layout.addWidget(right, 1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label

    def set_modules(self, paths: list[Path]) -> None:
        while self.module_layout.count():
            item = self.module_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.module_checks.clear()
        if not paths:
            label = QLabel(f"未找到 ModuleFiles: {MODULEFILES_DIR}")
            label.setObjectName("helperText")
            self.module_layout.addWidget(label)
        for path in paths:
            checkbox = AppCheckBox(path.name)
            checkbox.setObjectName("fileCheckbox")
            self.module_checks[path] = checkbox
            self.module_layout.addWidget(checkbox)
        self.module_layout.addStretch(1)


class OverviewPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CONTENT_LEFT_GAP, PAGE_TOP_GAP, 20, 16)
        layout.setSpacing(16)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.branch_card = StatCard("branch", C.PRIMARY, "当前分支")
        self.upstream_card = StatCard("branch_up", C.PRIMARY, "上游分支")
        self.sync_card = StatCard("check", C.SUCCESS, "同步状态")
        self.worktree_card = StatCard("folder", C.WARNING, "工作区")
        for card in (self.branch_card, self.upstream_card, self.sync_card, self.worktree_card):
            cards.addWidget(card)
        layout.addLayout(cards)

        repo_card = CardFrame()
        repo_layout = QVBoxLayout(repo_card)
        repo_layout.setContentsMargins(20, 18, 20, 18)
        repo_layout.setSpacing(12)
        repo_layout.addWidget(SectionTitle("仓库配置"))
        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.addWidget(self._label("仓库名"), 0, 0)
        form.addWidget(self._label("默认分支"), 0, 1)
        self.repo_input = QLineEdit()
        self.branch_input = QLineEdit(DEFAULT_BRANCH)
        self.repo_input.setMinimumHeight(32)
        self.branch_input.setMinimumHeight(32)
        form.addWidget(self.repo_input, 1, 0)
        form.addWidget(self.branch_input, 1, 1)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        repo_layout.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.refresh_btn = make_button("刷新", "secondary")
        self.check_remote_btn = make_button("检测远程", "secondary")
        self.reset_btn = make_button("重置 Git", "secondary")
        self.status_btn = make_button("状态详情", "secondary")
        for button in (self.refresh_btn, self.check_remote_btn, self.reset_btn, self.status_btn):
            actions.addWidget(button)
        repo_layout.addLayout(actions)
        layout.addWidget(repo_card)

        quick_card = CardFrame()
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(20, 18, 20, 18)
        quick_layout.setSpacing(12)
        quick_layout.addWidget(SectionTitle("快捷入口"))
        quicks = QHBoxLayout()
        quicks.setSpacing(16)
        self.branch_nav_btn = self._quick_btn("branch", C.PRIMARY, "分支管理")
        self.commit_nav_btn = self._quick_btn("sync", C.SUCCESS, "提交同步")
        self.release_nav_btn = self._quick_btn("tag", "#7c3aed", "版本发布")
        quicks.addWidget(self.branch_nav_btn)
        quicks.addWidget(self.commit_nav_btn)
        quicks.addWidget(self.release_nav_btn)
        quick_layout.addLayout(quicks)
        layout.addWidget(quick_card)
        layout.addStretch(1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label

    @staticmethod
    def _quick_btn(icon: str, color: str, text: str) -> QPushButton:
        button = make_button("  " + text, "secondary")
        button.setIcon(make_icon(icon, color, 18))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(56)
        button.setStyleSheet(
            "QPushButton {"
            f"border: 1.5px solid {color}; color: {color};"
            "background: #ffffff; border-radius: 6px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #f8fafc; }"
        )
        return button


class BranchPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CONTENT_LEFT_GAP, PAGE_TOP_GAP, 20, 16)
        layout.setSpacing(16)

        controls = CardFrame()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(20, 18, 20, 18)
        controls_layout.setSpacing(10)
        controls_layout.addWidget(SectionTitle("分支操作"))
        row1 = QHBoxLayout()
        label = QLabel("切换到")
        label.setObjectName("formLabel")
        label.setFixedWidth(56)
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(32)
        self.switch_btn = make_button("切换", "primary", 80)
        row1.addWidget(label)
        row1.addWidget(self.branch_combo, 1)
        row1.addWidget(self.switch_btn)
        controls_layout.addLayout(row1)
        row2 = QHBoxLayout()
        new_label = QLabel("新分支")
        new_label.setObjectName("formLabel")
        new_label.setFixedWidth(56)
        self.new_branch_input = QLineEdit()
        self.new_branch_input.setPlaceholderText("输入新分支名")
        self.new_branch_input.setMinimumHeight(32)
        self.create_btn = make_button("创建并切换", "primary", 110)
        row2.addWidget(new_label)
        row2.addWidget(self.new_branch_input, 1)
        row2.addWidget(self.create_btn)
        controls_layout.addLayout(row2)
        helper = QLabel("本地分支可以直接切换；origin/* 是远端引用，切换时会创建跟踪分支。")
        helper.setObjectName("helperText")
        helper.setWordWrap(True)
        controls_layout.addWidget(helper)
        layout.addWidget(controls)

        list_card = CardFrame()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(20, 18, 20, 18)
        list_layout.setSpacing(12)
        list_layout.addWidget(SectionTitle("分支列表"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["分支", "类型", "上游", "提交", "日期", "说明"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for col, width in enumerate((180, 80, 160, 100, 120)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)
        list_layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.fetch_btn = make_button("获取远程", "secondary")
        self.check_remote_btn = make_button("检测远程", "secondary")
        self.reset_btn = make_button("重置 Git", "secondary")
        self.status_btn = make_button("状态详情", "secondary")
        for button in (self.fetch_btn, self.check_remote_btn, self.reset_btn, self.status_btn):
            buttons.addWidget(button)
        list_layout.addLayout(buttons)
        layout.addWidget(list_card, 1)


class CommitPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CONTENT_LEFT_GAP, PAGE_TOP_GAP, 20, 16)
        layout.setSpacing(16)
        commit_card = CardFrame()
        commit_layout = QVBoxLayout(commit_card)
        commit_layout.setContentsMargins(20, 18, 20, 18)
        commit_layout.setSpacing(10)
        commit_layout.addWidget(SectionTitle("提交"))
        row = QHBoxLayout()
        label = QLabel("提交信息")
        label.setObjectName("formLabel")
        label.setFixedWidth(64)
        self.message_input = QLineEdit("Update project")
        self.message_input.setMinimumHeight(32)
        self.add_btn = make_button("添加全部", "secondary", 80)
        self.commit_btn = make_button("提交", "primary", 80)
        row.addWidget(label)
        row.addWidget(self.message_input, 1)
        row.addWidget(self.add_btn)
        row.addWidget(self.commit_btn)
        commit_layout.addLayout(row)
        layout.addWidget(commit_card)

        sync_card = CardFrame()
        sync_layout = QVBoxLayout(sync_card)
        sync_layout.setContentsMargins(20, 18, 20, 18)
        sync_layout.addWidget(SectionTitle("同步"))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.push_btn = make_button("推送", "success")
        self.pull_btn = make_button("拉取", "secondary")
        self.fetch_btn = make_button("获取", "secondary")
        for button in (self.push_btn, self.pull_btn, self.fetch_btn):
            button.setMinimumHeight(40)
            row.addWidget(button, 1)
        sync_layout.addLayout(row)
        layout.addWidget(sync_card)

        history_card = CardFrame()
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(20, 18, 20, 18)
        history_layout.setSpacing(10)
        history_layout.addWidget(SectionTitle("提交历史 / 操作记录"))
        self.history = QListWidget()
        self.history.setObjectName("historyList")
        self.history.setFrameShape(QFrame.NoFrame)
        self.history.setMinimumHeight(160)
        history_layout.addWidget(self.history, 1)
        self.log_btn = make_button("刷新日志", "secondary", 80)
        history_layout.addWidget(self.log_btn, 0, Qt.AlignLeft)
        layout.addWidget(history_card, 1)

    def append_history(self, text: str) -> None:
        for line in text.splitlines():
            if line.strip():
                item = QListWidgetItem("  " + line)
                font = QFont("Consolas")
                font.setPointSize(10)
                item.setFont(font)
                self.history.addItem(item)
        self.history.scrollToBottom()


class ReleasePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CONTENT_LEFT_GAP, PAGE_TOP_GAP, 20, 16)
        layout.setSpacing(16)
        list_card = CardFrame()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(20, 18, 20, 18)
        list_layout.setSpacing(10)
        list_layout.addWidget(SectionTitle("Release 列表"))
        self.latest_label = QLabel("Latest Release: -")
        self.latest_label.setObjectName("helperText")
        list_layout.addWidget(self.latest_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Release", "状态", "Tag", "发布时间", "来源"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for col, width in enumerate((180, 90, 110, 170)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)
        list_layout.addWidget(self.table)
        layout.addWidget(list_card)

        form_card = CardFrame()
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 18, 20, 18)
        form_layout.setSpacing(10)
        form_layout.addWidget(SectionTitle("创建 Release"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.tag_input = QLineEdit("v1.0.0")
        self.title_input = QLineEdit()
        self.notes_input = QLineEdit("Update project")
        self.assets_input = QLineEdit()
        for widget in (self.tag_input, self.title_input, self.notes_input, self.assets_input):
            widget.setMinimumHeight(32)
        grid.addWidget(self._label("Tag"), 0, 0)
        grid.addWidget(self._label("标题"), 0, 2)
        grid.addWidget(self.tag_input, 1, 0, 1, 2)
        grid.addWidget(self.title_input, 1, 2, 1, 2)
        grid.addWidget(self._label("说明"), 2, 0)
        grid.addWidget(self.notes_input, 3, 0, 1, 4)
        grid.addWidget(self._label("资产"), 4, 0)
        self.asset_btn = make_button("浏览", "secondary", 64)
        grid.addWidget(self.assets_input, 5, 0, 1, 3)
        grid.addWidget(self.asset_btn, 5, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        form_layout.addLayout(grid)
        bottom = QHBoxLayout()
        self.draft_check = AppCheckBox("Draft")
        self.prerelease_check = AppCheckBox("Prerelease")
        self.publish_btn = make_button("发布 Release", "primary", 130)
        bottom.addWidget(self.draft_check)
        bottom.addWidget(self.prerelease_check)
        bottom.addStretch(1)
        bottom.addWidget(self.publish_btn)
        form_layout.addLayout(bottom)
        layout.addWidget(form_card, 1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label


class Sidebar(QWidget):
    def __init__(self, on_change: Callable[[int], None]) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_panel = QWidget()
        nav_panel.setObjectName("sidebarNav")
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for index, (icon, label) in enumerate(
            [("plus", "新建"), ("grid", "概览"), ("branch", "分支"), ("sync", "提交"), ("tag", "发布")]
        ):
            button = SidebarButton(icon, label)
            self.group.addButton(button, index)
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        layout.addWidget(nav_panel, 1)
        self.group.idClicked.connect(on_change)

    def select(self, index: int) -> None:
        button = self.group.button(index)
        if button:
            button.setChecked(True)


class MainWindow(QMainWindow):
    def __init__(self, start_dir: Path) -> None:
        super().__init__()
        self.start_dir = start_dir
        self.output_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.dialog_title = "操作结果"
        self.dialog_lines: list[str] = []
        self.repo_name = start_dir.name
        self.current_branch = "-"
        self.upstream = "-"
        self.sync_state = "-"
        self.worktree_state = "-"

        # Release async loading state
        self._release_loading = False
        self._release_cache_key: tuple[str, str] | None = None
        self._release_cache: tuple[list, str | None] | None = None
        self._release_request_id = 0

        self.setWindowTitle("Git Manager")
        self.resize(1080, 720)
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._connect_actions()
        self.load_module_files()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_output)
        self.poll_timer.start(100)
        self.switch_page(1)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.topbar = TopBar(self.start_dir)
        root.addWidget(self.topbar)
        root.addWidget(self._divider())

        body = QWidget()
        body.setObjectName("bodyPane")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.sidebar = Sidebar(self.switch_page)
        body_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.new_page = NewPage(self.start_dir)
        self.overview_page = OverviewPage()
        self.branch_page = BranchPage()
        self.commit_page = CommitPage()
        self.release_page = ReleasePage()
        for page in (
            self.new_page,
            self.overview_page,
            self.branch_page,
            self.commit_page,
            self.release_page,
        ):
            self.stack.addWidget(page)
        body_layout.addWidget(self.stack, 1)
        root.addWidget(body, 1)
        root.addWidget(self._divider())
        self.footer = FooterBar()
        root.addWidget(self.footer)
        self.setCentralWidget(central)

    @staticmethod
    def _divider() -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("dividerRow")
        wrapper.setFixedHeight(1)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(SIDEBAR_WIDTH + CONTENT_LEFT_GAP, 0, 20, 0)
        layout.setSpacing(0)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{C.BORDER}; background:{C.BORDER}; max-height:1px;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        return wrapper

    def _connect_actions(self) -> None:
        self.topbar.choose_btn.clicked.connect(self.choose_project_path)
        self.topbar.refresh_btn.clicked.connect(self.refresh_git_status_with_output)
        self.topbar.path_input.returnPressed.connect(self.on_path_changed)
        self.new_page.browse_btn.clicked.connect(self.choose_create_base)
        self.new_page.create_btn.clicked.connect(self.create_project)
        self.new_page.select_all_btn.clicked.connect(lambda: self.set_all_modules(True))
        self.new_page.clear_btn.clicked.connect(lambda: self.set_all_modules(False))
        self.new_page.reload_btn.clicked.connect(self.load_module_files)
        self.overview_page.refresh_btn.clicked.connect(self.refresh_git_status_with_output)
        self.overview_page.check_remote_btn.clicked.connect(self.check_remote)
        self.overview_page.reset_btn.clicked.connect(self.reset_git_config)
        self.overview_page.status_btn.clicked.connect(self.git_status_detail)
        self.overview_page.repo_input.editingFinished.connect(self.on_repo_changed)
        self.overview_page.branch_input.editingFinished.connect(self.refresh_git_status)
        self.overview_page.branch_nav_btn.clicked.connect(lambda: self.switch_page(2))
        self.overview_page.commit_nav_btn.clicked.connect(lambda: self.switch_page(3))
        self.overview_page.release_nav_btn.clicked.connect(lambda: self.switch_page(4))
        self.branch_page.switch_btn.clicked.connect(self.checkout_selected_branch)
        self.branch_page.create_btn.clicked.connect(self.create_branch)
        self.branch_page.fetch_btn.clicked.connect(self.git_fetch)
        self.branch_page.check_remote_btn.clicked.connect(self.check_remote)
        self.branch_page.reset_btn.clicked.connect(self.reset_git_config)
        self.branch_page.status_btn.clicked.connect(self.git_status_detail)
        self.commit_page.add_btn.clicked.connect(self.git_add_all)
        self.commit_page.commit_btn.clicked.connect(self.git_commit)
        self.commit_page.push_btn.clicked.connect(self.git_push)
        self.commit_page.pull_btn.clicked.connect(self.git_pull)
        self.commit_page.fetch_btn.clicked.connect(self.git_fetch)
        self.commit_page.log_btn.clicked.connect(self.git_log)
        self.release_page.asset_btn.clicked.connect(self.choose_release_assets)
        self.release_page.publish_btn.clicked.connect(self.create_release)

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.select(index)
        if index == 4:
            self.ensure_release_info_async()

    def project_path(self) -> Path:
        return Path(self.topbar.path_input.text().strip()).expanduser()

    def branch_name(self) -> str:
        return self.overview_page.branch_input.text().strip() or DEFAULT_BRANCH

    def on_path_changed(self) -> None:
        self._release_cache = None
        self._release_cache_key = None
        self.sync_repo_name_from_git_context()
        self.refresh_git_status()

    def on_repo_changed(self) -> None:
        self._release_cache = None
        self._release_cache_key = None
        self.repo_name = sanitize_project_name(self.overview_page.repo_input.text() or self.project_path().name)
        self.overview_page.repo_input.setText(self.repo_name)
        self.refresh_git_status()

    def set_status(self, text: str) -> None:
        text = " ".join(text.split())
        if len(text) > 180:
            text = text[:179].rstrip() + "..."
        self.footer.status_label.setText(text or "Ready")

    def append_command_start(self, title: str) -> None:
        self.output_queue.put(("start", title))

    def enqueue(self, text: str) -> None:
        self.output_queue.put(("text", text))

    def append_command_done(self) -> None:
        self.output_queue.put(("done", None))

    def _poll_output(self) -> None:
        try:
            while True:
                kind, text = self.output_queue.get_nowait()
                if kind == "start":
                    self.dialog_title = text or "操作结果"
                    self.dialog_lines = []
                    self.set_status(self.dialog_title)
                elif kind == "text" and text:
                    self.dialog_lines.append(text)
                elif kind == "done":
                    self.show_operation_dialog()
                elif kind == "refresh":
                    self.refresh_git_status()
                elif kind == "release_info":
                    payload = text  # actually a dict
                    if isinstance(payload, dict) and payload.get("request_id") == self._release_request_id:
                        self._release_loading = False
                        self._release_cache_key = payload["cache_key"]
                        self._release_cache = (payload["releases"], payload["error"])
                        self._render_release_info(payload["releases"], payload["error"])
        except queue.Empty:
            pass

    def show_operation_dialog(self) -> None:
        body = "".join(self.dialog_lines).strip() or "操作完成。"
        self.commit_page.append_history(body)
        self.set_status(body.splitlines()[0])
        if any(word in body for word in ("失败", "已停止", "[exit")):
            QMessageBox.critical(self, self.dialog_title, body)
        elif any(word in body for word in ("提示", "警告")):
            QMessageBox.warning(self, self.dialog_title, body)
        else:
            QMessageBox.information(self, self.dialog_title, body)
        self.dialog_lines = []

    def run_worker(self, title: str, worker: Callable[[], None]) -> None:
        def wrapped() -> None:
            self.append_command_start(title)
            worker()
            self.append_command_done()
            self.output_queue.put(("refresh", None))

        threading.Thread(target=wrapped, daemon=True).start()

    def load_module_files(self) -> None:
        self.new_page.set_modules(list_module_files())

    def set_all_modules(self, checked: bool) -> None:
        for checkbox in self.new_page.module_checks.values():
            checkbox.setChecked(checked)

    def choose_create_base(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择创建位置", self.new_page.base_input.text())
        if selected:
            self.new_page.base_input.setText(selected)

    def choose_project_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择项目路径", self.topbar.path_input.text())
        if selected:
            self.topbar.path_input.setText(selected)
            self.sync_repo_name_from_git_context()
            self.refresh_git_status()

    def choose_release_assets(self) -> None:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "选择 Release 附件",
            str(self.project_path()),
        )
        if files:
            self.release_page.assets_input.setText("; ".join(files))

    def sync_repo_name_from_git_context(self) -> tuple[str | None, str]:
        path = self.project_path()
        remote = run_command(["git", "remote", "get-url", REMOTE_NAME], path)
        remote_name = repository_name_from_remote_url(remote.stdout) if remote.returncode == 0 else None
        project_name = remote_name or sanitize_project_name(path.name)
        source = "origin" if remote_name else "项目文件夹名"
        if project_name and project_name != self.repo_name:
            self.repo_name = project_name
            self.overview_page.repo_input.setText(project_name)
            return project_name, source
        return None, source

    def collect_git_status_text(self) -> str:
        path = self.project_path()
        if not path.exists():
            return f"路径不存在：{path}"
        inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
        if inside.returncode != 0:
            return "当前路径尚未初始化 Git。可点击“重置 Git”执行初始化。"
        branch = run_command(["git", "branch", "--show-current"], path)
        remote = run_command(["git", "remote", "get-url", REMOTE_NAME], path)
        status = run_command(["git", "status", "--short", "--branch"], path)
        remote_text = remote.stdout.strip() if remote.returncode == 0 else "未设置"
        branch_text = branch.stdout.strip() or "(detached)"
        status_lines = [
            line for line in status.stdout.splitlines() if line.strip() and not line.startswith("## ")
        ]
        dirty_text = f"有 {len(status_lines)} 项未提交文件改动" if status_lines else "没有未提交的文件改动"
        return f"Git 本地状态 | 分支：{branch_text} | origin：{remote_text} | 文件：{dirty_text}"

    def refresh_git_status(self) -> None:
        status = self.collect_git_status_text()
        self.set_status(status)
        self.refresh_branch_and_release_views()
        self.update_header()

    def refresh_git_status_with_output(self) -> None:
        self.append_command_start("刷新本地 Git 状态")
        synced_name, source = self.sync_repo_name_from_git_context()
        if synced_name:
            self.enqueue(f"已按{source}更新仓库名：{synced_name}。\n")
        self.enqueue(self.collect_git_status_text() + "\n")
        self.append_command_done()
        self.refresh_git_status()

    def refresh_branch_and_release_views(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name or path.name)
        self.overview_page.repo_input.setText(repo_name)
        if self.overview_page.branch_input.text().strip() == "":
            self.overview_page.branch_input.setText(DEFAULT_BRANCH)

        if not path.exists():
            self.current_branch = "-"
            self.upstream = "-"
            self.sync_state = "-"
            self.worktree_state = "路径不存在"
            self.clear_repository_tables()
            self.update_overview_cards()
            return

        inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
        if inside.returncode != 0:
            self.current_branch = "-"
            self.upstream = "-"
            self.sync_state = "未初始化"
            self.worktree_state = "不是 Git 仓库"
            self.clear_repository_tables()
            self.update_overview_cards()
            return

        branch, branch_error = current_git_branch(path)
        self.current_branch = branch or "(detached)"
        self.upstream = current_git_upstream(path) or "未设置"
        dirty_count = git_dirty_count(path)
        ahead, behind = git_ahead_behind(path)
        if ahead is None or behind is None:
            self.sync_state = "未跟踪"
        elif ahead == 0 and behind == 0:
            self.sync_state = "已同步"
        else:
            self.sync_state = f"ahead {ahead} / behind {behind}"
        self.worktree_state = "干净" if dirty_count == 0 else f"{dirty_count} 项改动"
        if branch_error and not branch:
            self.set_status(branch_error)

        branches = list_branches(path)
        self.branch_page.branch_combo.clear()
        self.branch_page.table.setRowCount(0)
        for info in branches:
            self.branch_page.branch_combo.addItem(info.name)
            row = self.branch_page.table.rowCount()
            self.branch_page.table.insertRow(row)
            values = (
                f"* {info.name}" if info.is_current else info.name,
                "远端" if info.is_remote else "本地",
                info.upstream,
                info.commit,
                info.date,
                info.subject,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 0 and info.is_current:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(C.PRIMARY))
                self.branch_page.table.setItem(row, col, item)
        if branch:
            index = self.branch_page.branch_combo.findText(branch)
            if index >= 0:
                self.branch_page.branch_combo.setCurrentIndex(index)

        self.update_overview_cards()

    def ensure_release_info_async(self, force: bool = False) -> None:
        """Load release info in background thread. Uses cache when available."""
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name or path.name)
        cache_key = (str(path.resolve()), repo_name)

        if not force and self._release_cache_key == cache_key and self._release_cache:
            releases, error = self._release_cache
            self._render_release_info(releases, error)
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

    def _render_release_info(self, releases: list, release_error: str | None) -> None:
        """Update Release page UI with data. Must run on main thread."""
        self.release_page.table.setRowCount(0)
        if releases:
            latest = releases[0]
            self.release_page.latest_label.setText(
                f"Latest Release: {latest.tag} | {latest.title} | {latest.status}"
            )
        else:
            self.release_page.latest_label.setText(release_error or "暂无 release/tag")
        for release in releases:
            row = self.release_page.table.rowCount()
            self.release_page.table.insertRow(row)
            for col, value in enumerate(
                (release.title, release.status, release.tag, release.published_at, release.source)
            ):
                item = QTableWidgetItem(value)
                if col == 1 and "latest" in value.lower():
                    item.setForeground(QColor(C.SUCCESS))
                self.release_page.table.setItem(row, col, item)

    def clear_repository_tables(self) -> None:
        self.branch_page.branch_combo.clear()
        self.branch_page.table.setRowCount(0)
        self.release_page.table.setRowCount(0)
        self.release_page.latest_label.setText("暂无 release/tag")

    def update_overview_cards(self) -> None:
        self.overview_page.branch_card.set_value(self.current_branch)
        self.overview_page.upstream_card.set_value(self.upstream)
        sync_color = C.SUCCESS if self.sync_state == "已同步" else C.WARNING
        self.overview_page.sync_card.set_value(self.sync_state, sync_color)
        worktree_color = C.SUCCESS if self.worktree_state == "干净" else C.WARNING
        self.overview_page.worktree_card.set_value(self.worktree_state, worktree_color)

    def update_header(self) -> None:
        self.topbar.repo_label.setText(
            f'<span style="color:#475569;">仓库:</span> <b>{self.repo_name}</b>'
        )
        self.topbar.branch_label.setText(
            f'<span style="color:#475569;">分支:</span> <span>{self.current_branch}</span>'
        )
        color = C.SUCCESS if self.sync_state == "已同步" else C.WARNING
        self.topbar.sync_label.setText(
            f'<span style="color:#475569;">同步:</span> <span style="color:{color};">{self.sync_state}</span>'
        )

    def create_project(self) -> None:
        base = Path(self.new_page.base_input.text().strip()).expanduser()
        project_name = sanitize_project_name(self.new_page.name_input.text())
        base_name = sanitize_project_name(base.name)
        use_base_as_project = base_name == project_name
        project_path = base if use_base_as_project else base / project_name
        selected = [path for path, checkbox in self.new_page.module_checks.items() if checkbox.isChecked()]

        try:
            if project_path.exists():
                if not use_base_as_project or not project_path.is_dir():
                    QMessageBox.critical(self, "创建失败", f"目录已存在：{project_path}")
                    return
            else:
                project_path.mkdir(parents=False, exist_ok=False)
            for source in selected:
                copy_module_file(source, project_path / source.name)
        except (FileExistsError, OSError) as exc:
            QMessageBox.critical(self, "创建失败", f"无法创建或复制模板文件。\n\n{exc}")
            return

        self.topbar.path_input.setText(str(project_path))
        self.repo_name = project_path.name
        self.overview_page.repo_input.setText(project_path.name)
        if self.new_page.init_git_check.isChecked():
            results = initialize_git_repository(project_path, project_path.name, self.branch_name())
            failed = next((result for result in results if result.returncode != 0), None)
            if failed:
                QMessageBox.warning(
                    self,
                    "项目已创建，Git 初始化未完成",
                    f"已创建项目：{project_path}\n\nGit 初始化失败：{failed.stderr or failed.stdout}",
                )
            else:
                QMessageBox.information(self, "完成", f"已创建项目并初始化 Git：{project_path}")
        else:
            QMessageBox.information(self, "完成", f"已创建项目：{project_path}")
        self.refresh_git_status()

    def reset_git_config(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name or path.name)

        def worker() -> None:
            inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], path)
            if inside.returncode != 0:
                self.enqueue("当前项目尚未初始化 Git；现在将执行初始化流程。\n")
            else:
                self.enqueue("当前项目已有 Git 配置；现在将按界面参数重置配置。\n")
            results = initialize_git_repository(path, repo_name, self.branch_name())
            failed = next((result for result in results if result.returncode != 0), None)
            if failed:
                self.enqueue(f"重置失败：{failed.stderr or failed.stdout}\n")
            else:
                self.enqueue(f"重置完成：origin 已更新为 {github_remote(repo_name)}\n")

        self.run_worker("重置 Git 配置", worker)

    def check_remote(self) -> None:
        repo_name = sanitize_project_name(self.repo_name)
        path = self.project_path()
        remote_url = configured_or_default_remote(path, repo_name)

        def worker() -> None:
            self.enqueue("正在检测 GitHub 远程连接...\n")
            result = run_command(["git", "ls-remote", remote_url], path)
            ok, message = explain_remote_result(result, repo_name)
            self.enqueue(message + "\n")
            if ok and not result.stdout.strip():
                self.enqueue("提示：远程仓库目前没有可列出的提交或分支，空仓库也属于可访问。\n")

        self.run_worker("检测远程连接", worker)

    def git_add_all(self) -> None:
        path = self.project_path()

        def worker() -> None:
            result = run_command(["git", "add", "-A"], path)
            self.enqueue(summarize_simple_git_result("add", result) + "\n")

        self.run_worker("添加全部", worker)

    def git_status_detail(self) -> None:
        path = self.project_path()

        def worker() -> None:
            result = run_command(["git", "status", "--short", "--branch"], path)
            if result.returncode == 0:
                self.enqueue(summarize_git_status(result.stdout) + "\n")
            else:
                self.enqueue(f"状态读取失败：{result.stderr or result.stdout}\n")

        self.run_worker("状态详情", worker)

    def git_commit(self) -> None:
        message = self.commit_page.message_input.text().strip() or "Update project"
        path = self.project_path()

        def worker() -> None:
            result = run_command(["git", "commit", "-m", message], path)
            self.enqueue(summarize_simple_git_result("commit", result) + "\n")

        self.run_worker("提交", worker)

    def git_fetch(self) -> None:
        path = self.project_path()

        def worker() -> None:
            result = run_command(["git", "fetch", REMOTE_NAME], path)
            self.enqueue(summarize_simple_git_result("fetch", result) + "\n")

        self.run_worker("获取", worker)

    def git_pull(self) -> None:
        path = self.project_path()

        def worker() -> None:
            branch, branch_error = current_git_branch(path)
            if not branch:
                self.enqueue(f"拉取已停止：{branch_error or '无法读取当前分支。'}\n")
                return
            first_pull = not has_local_commits(path)
            if first_pull:
                self.enqueue("当前仓库还没有本地提交，将按首次拉取流程处理。\n")
                fetch_result = run_command(["git", "fetch", REMOTE_NAME], path, 120)
                if fetch_result.returncode != 0:
                    self.enqueue(f"首次拉取失败：{fetch_result.stderr or fetch_result.stdout}\n")
                    return
                remote_branch = remote_default_branch(path)
                if remote_branch:
                    branch = remote_branch
            backups: list[Path] = []
            if first_pull:
                try:
                    backups = backup_first_pull_conflicts(path, branch)
                except OSError as exc:
                    self.enqueue(f"首次拉取失败：无法备份本地初始化配置文件。{exc}\n")
                    return
            upstream = current_git_upstream(path)
            result = (
                run_command(["git", "pull"], path, 120)
                if upstream
                else run_command(["git", "pull", REMOTE_NAME, branch], path, 120)
            )
            self.enqueue(summarize_simple_git_result("pull", result) + "\n")
            detail = (result.stderr or result.stdout).strip()
            if result.returncode == 0 and first_pull:
                run_command(["git", "branch", "--set-upstream-to", f"{REMOTE_NAME}/{branch}"], path)
            elif result.returncode != 0 and backups:
                try:
                    restore_backups(path, backups)
                    self.enqueue("拉取失败，已恢复刚才备份的本地初始化配置文件。\n")
                except OSError as exc:
                    self.enqueue(f"拉取失败，且恢复备份时出错：{exc}\n")
            if detail:
                self.enqueue(f"Git 详情：{detail}\n")

        self.run_worker("拉取", worker)

    def git_push(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name or path.name)

        def worker() -> None:
            branch, branch_error = current_git_branch(path)
            if not branch:
                self.enqueue(f"推送已停止：{branch_error or '无法读取当前分支。'}\n")
                return
            try:
                ensure_gitignore(path)
                ensure_gitattributes(path)
            except OSError as exc:
                self.enqueue(f"推送已停止：无法更新忽略/换行配置：{exc}\n")
                return
            remote_url = configured_or_default_remote(path, repo_name)
            self.enqueue("正在推送前检查 GitHub 远程仓库...\n")
            check_result = run_command(["git", "ls-remote", remote_url], path)
            remote_ok, remote_message = explain_remote_result(check_result, repo_name)
            if not remote_ok:
                self.enqueue(f"{remote_message}\n推送已停止：请先创建 GitHub 仓库或修复权限后再推送。\n")
                return
            configure_result = configure_git_remote(path, remote_url)
            if configure_result.returncode != 0:
                self.enqueue(f"推送已停止：无法配置 origin。{configure_result.stderr or configure_result.stdout}\n")
                return
            push_result = run_command(["git", "push", "-u", REMOTE_NAME, branch], path, 120)
            if push_result.returncode == 0:
                self.enqueue("推送成功：本地提交已上传到 GitHub。\n")
                if push_result.stdout.strip():
                    self.enqueue(push_result.stdout)
                if push_result.stderr.strip():
                    self.enqueue(push_result.stderr)
            else:
                self.enqueue(f"推送失败：{push_result.stderr or push_result.stdout}\n")

        self.run_worker("推送", worker)

    def git_log(self) -> None:
        path = self.project_path()

        def worker() -> None:
            result = run_command(["git", "log", "--pretty=format:%h%x09%D%x09%s", "-n", "20"], path)
            if result.returncode == 0:
                self.enqueue(summarize_git_log(result.stdout) + "\n")
            else:
                self.enqueue(f"提交记录读取失败：{result.stderr or result.stdout}\n")

        self.run_worker("最近提交", worker)

    def checkout_selected_branch(self) -> None:
        target = self.branch_page.branch_combo.currentText().strip()
        if not target:
            QMessageBox.critical(self, "切换失败", "请先选择一个分支。")
            return
        path = self.project_path()

        def worker() -> None:
            if target.startswith(f"{REMOTE_NAME}/"):
                local_name = target[len(f"{REMOTE_NAME}/") :]
                exists = run_command(["git", "show-ref", "--verify", f"refs/heads/{local_name}"], path)
                command = ["git", "switch", local_name] if exists.returncode == 0 else ["git", "switch", "--track", target]
            else:
                command = ["git", "switch", target]
            result = run_command(command, path)
            if result.returncode == 0:
                self.enqueue(f"已切换到分支：{target}\n")
            else:
                self.enqueue(f"切换失败：{result.stderr or result.stdout}\n")

        self.run_worker("切换分支", worker)

    def create_branch(self) -> None:
        branch_name = self.branch_page.new_branch_input.text().strip()
        if not branch_name:
            QMessageBox.critical(self, "创建失败", "请输入新分支名。")
            return
        path = self.project_path()

        def worker() -> None:
            check = run_command(["git", "check-ref-format", "--branch", branch_name], path)
            if check.returncode != 0:
                self.enqueue(f"分支名无效：{check.stderr or check.stdout}\n")
                return
            result = run_command(["git", "switch", "-c", branch_name], path)
            if result.returncode == 0:
                self.enqueue(f"已创建并切换到分支：{branch_name}\n")
            else:
                self.enqueue(f"创建失败：{result.stderr or result.stdout}\n")

        self.run_worker("创建并切换分支", worker)
        self.branch_page.new_branch_input.clear()

    def create_release(self) -> None:
        path = self.project_path()
        repo_name = sanitize_project_name(self.repo_name or path.name)
        repo = configured_repo_full_name(path, repo_name)
        tag = self.release_page.tag_input.text().strip()
        title = self.release_page.title_input.text().strip() or tag
        notes = self.release_page.notes_input.text().strip()
        assets = [item.strip() for item in self.release_page.assets_input.text().split(";") if item.strip()]
        if not tag:
            QMessageBox.critical(self, "发布失败", "请输入 release tag。")
            return
        gh = find_gh_executable()
        if not gh:
            QMessageBox.critical(self, "发布失败", "未找到 GitHub CLI，无法创建 GitHub Release。")
            return
        branch, branch_error = current_git_branch(path)
        if not branch:
            QMessageBox.critical(self, "发布失败", branch_error or "无法读取当前分支。")
            return

        def worker() -> None:
            command = [
                gh,
                "release",
                "create",
                tag,
                *assets,
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
            if self.release_page.draft_check.isChecked():
                command.append("--draft")
            if self.release_page.prerelease_check.isChecked():
                command.append("--prerelease")
            result = run_command(command, path, timeout=180)
            if result.returncode == 0:
                self.enqueue(f"Release 已发布：{repo} {tag}\n")
                if result.stdout.strip():
                    self.enqueue(result.stdout)
                run_command(["git", "fetch", "--tags", REMOTE_NAME], path, 120)
                # Force-refresh release list after successful publish
                self._release_cache = None
                self._release_cache_key = None
            else:
                self.enqueue(f"发布失败：{result.stderr or result.stdout}\n")

        self.run_worker("发布 Release", worker)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Git Manager GUI")
    parser.add_argument("path", nargs="?", type=Path, default=None)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    return parser.parse_args()


def resource_path(relative_name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent
    return base / relative_name


def configure_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            "powerfulhang.gitmanager"
        )
    except (AttributeError, OSError):
        pass


_CONTEXT_MENU_KEY = r"Software\Classes\Directory\Background\shell\GitManager"


def ensure_context_menu() -> None:
    """Register Explorer right-click menu entry if not already present.

    Uses HKCU so no admin rights are needed. Runs silently on every launch;
    if the key already exists and points to the current exe, it is a no-op.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import winreg

        exe_path = str(Path(sys.executable))

        # Check if already registered with the correct path
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CONTEXT_MENU_KEY) as key:
                existing_cmd, _ = winreg.QueryValueEx(key, "")
                # command value format: "C:\path\GitManager.exe" "%V"
                if exe_path in existing_cmd:
                    return  # already registered correctly
        except FileNotFoundError:
            pass  # key does not exist yet

        # Create or update the shell key
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CONTEXT_MENU_KEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Open with Git Manager")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, exe_path)

        # Create or update the command subkey
        cmd_key_path = _CONTEXT_MENU_KEY + r"\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%V"')
    except Exception:
        pass  # silent failure — do not block app launch


def main() -> None:
    args = parse_args()
    start_dir = (args.path if args.path is not None else args.cwd).expanduser().resolve()
    os.chdir(start_dir)
    configure_windows_app_id()
    ensure_context_menu()
    app = QApplication(sys.argv)
    configure_light_palette(app)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    icon = QIcon(str(resource_path("git_manager.ico")))
    app.setWindowIcon(icon)
    window = MainWindow(start_dir)
    window.setWindowIcon(icon)
    window.show()
    # Defer git status refresh to after the window is visible
    QTimer.singleShot(0, window.refresh_git_status)
    sys.exit(app.exec())


def configure_light_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(C.PAGE_BG))
    palette.setColor(QPalette.WindowText, QColor(C.TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor(C.TEXT_PRIMARY))
    palette.setColor(QPalette.Text, QColor(C.TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor(C.TEXT_PRIMARY))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor(C.PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
    color: {C.TEXT_PRIMARY};
}}
QWidget#centralRoot,
QWidget#bodyPane,
QFrame#dividerRow,
QWidget#topBar,
QWidget#topBarContentShell,
QWidget#topBarContent,
QWidget#footerBar {{
    background: {C.PAGE_BG};
}}
QWidget#topBarContent {{
    background: #ffffff;
    border: 1px solid {C.BORDER};
    border-radius: 8px;
}}
QWidget#sidebar {{
    background: {C.SIDEBAR_BG};
}}
QWidget#sidebarNav {{
    background: {C.SIDEBAR_BG};
}}
QWidget#sidebarNav QWidget {{
    background: {C.SIDEBAR_BG};
}}
QWidget#sidebarLogoPanel {{
    background: {C.PAGE_BG};
}}
QLabel#sidebarLogo {{
    color: {C.TEXT_PRIMARY};
    background: {C.PAGE_BG};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 1px;
    border: none;
}}
QWidget#sidebarNav QPushButton#sidebarBtn {{
    background: {C.SIDEBAR_BG};
    color: #cbd5e1;
    border: none;
    border-left: 3px solid transparent;
    text-align: center;
    padding: 8px 0 6px 0;
    font-size: 12px;
    font-weight: 500;
}}
QWidget#sidebarNav QPushButton#sidebarBtn:hover {{
    background: {C.SIDEBAR_HOVER};
    color: #ffffff;
}}
QWidget#sidebarNav QPushButton#sidebarBtn:checked {{
    background: {C.SIDEBAR_ACTIVE};
    color: #ffffff;
    border-left: 3px solid {C.PRIMARY};
}}
QScrollArea#moduleScroll,
QScrollArea#moduleScroll > QWidget,
QScrollArea#moduleScroll QWidget#moduleList {{
    background: #ffffff;
    color: {C.TEXT_PRIMARY};
}}
QWidget#moduleList QCheckBox {{
    background: #ffffff;
    color: {C.TEXT_PRIMARY};
}}
QMessageBox, QFileDialog, QDialog {{
    background: {C.PAGE_BG};
    color: {C.TEXT_PRIMARY};
}}
QMessageBox QLabel, QFileDialog QLabel, QDialog QLabel {{
    color: {C.TEXT_PRIMARY};
    background: transparent;
}}
QMessageBox QTextEdit, QFileDialog QTextEdit, QDialog QTextEdit {{
    background: #ffffff;
    color: {C.TEXT_PRIMARY};
}}
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
QLabel#helperText, QLabel#statCaption {{
    color: {C.TEXT_MUTED};
    font-size: 11px;
}}
QLabel#statValue {{
    color: {C.TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
}}
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
QCheckBox {{
    color: {C.TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}
QCheckBox#appCheckBox {{
    background: transparent;
    color: {C.TEXT_PRIMARY};
    spacing: 0;
}}
QPushButton#btn_primary {{
    background: {C.PRIMARY};
    color: #ffffff;
    border: 1px solid {C.PRIMARY};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_primary:hover {{
    background: {C.PRIMARY_HOVER};
    border-color: {C.PRIMARY_HOVER};
}}
QPushButton#btn_success {{
    background: {C.SUCCESS};
    color: #ffffff;
    border: 1px solid {C.SUCCESS};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_success:hover {{
    background: {C.SUCCESS_HOVER};
    border-color: {C.SUCCESS_HOVER};
}}
QPushButton#btn_secondary {{
    background: #ffffff;
    color: {C.PRIMARY};
    border: 1px solid {C.PRIMARY};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#btn_secondary:hover {{
    background: #eff6ff;
}}
QTableWidget, QListWidget#historyList {{
    background: #ffffff;
    border: 1px solid {C.BORDER};
    border-radius: 4px;
    font-size: 12px;
}}
QTableWidget::item, QListWidget#historyList::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected, QListWidget#historyList::item:selected {{
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
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


if __name__ == "__main__":
    main()
