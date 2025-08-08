# Copyright (C) 2025 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

import markdown

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QUrl, QObject
from PyQt6.QtGui import QIcon, QFont, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout,
    QCompleter, QFileDialog, QStackedWidget, QTableWidgetItem,
    QButtonGroup, QTextBrowser, QScrollArea, QPushButton
)
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, SubtitleLabel, setFont,
    ComboBox, PushButton, InfoBar, InfoBarPosition, LineEdit,
    FluentIcon, Action, SegmentedWidget, CheckBox, BodyLabel,
    CaptionLabel, IndeterminateProgressRing, SpinBox, SwitchButton,
    TableWidget, MessageBox, EditableComboBox, RadioButton,
    HyperlinkLabel, ElevatedCardWidget, TitleLabel, SimpleCardWidget,
    IconWidget, TabBar, TabCloseButtonDisplayMode, MessageBoxBase,
    ScrollArea, PrimaryPushButton, TransparentPushButton, TextEdit,
    ProgressBar, ToolTipFilter, ToolTipPosition
)
from qfluentwidgets import FluentIcon as FIF

from modless_chat_trans.file_utils import get_path
from modless_chat_trans.i18n import supported_languages, _
from modless_chat_trans.logger import logger
from modless_chat_trans.translator import (
    service_supported_languages,
    TRADITIONAL_SERVICES,
    LLM_PROVIDERS
)


def set_tool_tip(widget, tip, duration=400, position=ToolTipPosition.TOP_LEFT):
    widget.setToolTip(tip)
    widget.installEventFilter(ToolTipFilter(widget, showDelay=duration, position=position))


@dataclass
class ProgramInfo:
    version: str
    author: str
    email: str
    github: str
    license: Tuple[str, str]


class DownloadWorker(QObject):
    """下载工作器，用于在线程中执行下载并发送进度信号"""
    progress_updated: pyqtSignal = pyqtSignal(int, int, float)  # downloaded, total, speed
    download_finished: pyqtSignal = pyqtSignal(str)  # file_path
    download_error: pyqtSignal = pyqtSignal(str)  # error_message
    thread_count_updated: pyqtSignal = pyqtSignal(int)  # thread_count

    def __init__(self, updater, release_info):
        super().__init__()
        self.updater = updater
        self.release_info = release_info
        self.is_cancelled = False
        self.speed_history = []
        self.max_history = 10

    def cancel(self):
        """取消下载"""
        self.is_cancelled = True

    def download(self):
        """执行下载"""
        try:
            def progress_callback(downloaded, total, speed):
                if self.is_cancelled:
                    return False

                # 添加速度到历史记录
                self.speed_history.append(speed)
                if len(self.speed_history) > self.max_history:
                    self.speed_history.pop(0)

                # 计算平均速度
                if self.speed_history:
                    weights = [i + 1 for i in range(len(self.speed_history))]
                    weighted_sum = sum(s * w for s, w in zip(self.speed_history, weights))
                    weight_total = sum(weights)
                    avg_speed = weighted_sum / weight_total
                else:
                    avg_speed = speed

                self.progress_updated.emit(downloaded, total, avg_speed)
                return True

            def thread_count_callback(count):
                """线程数回调"""
                self.thread_count_updated.emit(count)

            file_path = self.updater.download_update(self.release_info, progress_callback, thread_count_callback)

            if file_path:
                self.download_finished.emit(file_path)
            elif self.is_cancelled:
                self.download_finished.emit("")
            else:
                self.download_error.emit(_("下载失败"))

        except Exception as e:
            self.download_error.emit(str(e))


class LanguageLoaderThread(QThread):
    """用于异步加载语言列表的线程"""
    languages_loaded: pyqtSignal = pyqtSignal(list)
    error_occurred: pyqtSignal = pyqtSignal(str)

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def run(self):
        try:
            langs = service_supported_languages[self.service_name]
            self.languages_loaded.emit(langs)
        except Exception as e:
            self.error_occurred.emit(str(e))


class MessageCaptureInterface(QFrame):
    """消息捕获界面组件"""

    def __init__(self, parent, service_type):
        super().__init__(parent=parent)
        self.setObjectName("messageCapture")
        self.current_service_type = service_type
        self.init_ui(service_type)

    def init_ui(self, service_type):
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('消息捕获设置'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 表单网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        self.grid_layout.setColumnStretch(1, 1)

        # MC 日志位置
        log_label = BodyLabel(_('Minecraft 日志位置：'), self)
        self.log_location_edit = LineEdit(self)
        self.log_location_edit.setPlaceholderText(_("请选择Minecraft日志文件夹路径"))
        self.log_location_edit.setClearButtonEnabled(True)
        file_action = Action(FluentIcon.FOLDER, "", triggered=self.select_log_folder)
        self.log_location_edit.addAction(file_action, LineEdit.ActionPosition.TrailingPosition)
        self.grid_layout.addWidget(log_label, 0, 0)
        self.grid_layout.addWidget(self.log_location_edit, 0, 1)

        # 源/目标语言标签
        self.src_label = BodyLabel(_('源语言：'), self)
        self.tgt_label = BodyLabel(_('目标语言：'), self)
        self.grid_layout.addWidget(self.src_label, 1, 0)
        self.grid_layout.addWidget(self.tgt_label, 2, 0)

        # 语言控件
        self.create_all_language_widgets()

        # 日志编码
        log_encoding_label = BodyLabel(_('日志编码：'), self)
        set_tool_tip(log_encoding_label, _("建议选择自动检测（auto），如果无效可以尝试手动指定GBK等编码"))
        self.log_encoding_combo = EditableComboBox(self)
        self.log_encoding_combo.addItems(['auto', 'UTF-8', 'GBK', 'GB2312', 'GB18030', 'ISO-8859-1'])
        self.log_encoding_combo.setCurrentText('auto')

        # 监控模式
        monitor_mode_label = BodyLabel(_('监控模式：'), self)
        set_tool_tip(monitor_mode_label, _("建议优先尝试高效模式，若无法正常获取消息，再切换至兼容模式"))
        self.efficient_mode_radio = RadioButton(_('高效模式'), self)
        set_tool_tip(self.efficient_mode_radio, _("低版本 Minecraft 推荐使用"))
        self.compatible_mode_radio = RadioButton(_('兼容模式'), self)
        set_tool_tip(self.compatible_mode_radio, _("高版本 Minecraft 使用"))
        self.efficient_mode_radio.setChecked(True)

        self.monitor_mode_group = QButtonGroup(self)
        self.monitor_mode_group.addButton(self.efficient_mode_radio)
        self.monitor_mode_group.addButton(self.compatible_mode_radio)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.efficient_mode_radio)
        mode_layout.addWidget(self.compatible_mode_radio)
        mode_layout.addStretch()

        # 翻译设置
        self.translate_non_player_check = CheckBox(_('过滤服务器消息'), self)
        set_tool_tip(self.translate_non_player_check, _("不翻译不带玩家名称的服务器消息（系统消息）"))

        self.replace_garbled_check = CheckBox(_('替换乱码字符'), self)
        set_tool_tip(self.replace_garbled_check,
                     "将乱码字符（\\ufffd\\ufffd）替换为用于Minecraft格式化代码的分节符\u00A7（\\u00A7）")

        self.grid_layout.addWidget(log_encoding_label, 3, 0)
        self.grid_layout.addWidget(self.log_encoding_combo, 3, 1)
        self.grid_layout.addWidget(monitor_mode_label, 4, 0)
        self.grid_layout.addLayout(mode_layout, 4, 1)
        self.grid_layout.addWidget(self.translate_non_player_check, 5, 0, 1, 2)
        self.grid_layout.addWidget(self.replace_garbled_check, 6, 0, 1, 2)

        self.main_layout.addLayout(self.grid_layout)
        self.main_layout.addStretch()
        self.update_service_type(service_type)

    def create_all_language_widgets(self):
        # LLM 模式用的自由输入
        self.src_lang_edit = LineEdit(self)
        self.src_lang_edit.setPlaceholderText(_("请输入源语言（格式不限，AI可智能识别）"))
        self.src_lang_edit.setClearButtonEnabled(True)
        src_completer = QCompleter([], self.src_lang_edit)
        src_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.src_lang_edit.setCompleter(src_completer)

        self.tgt_lang_edit = LineEdit(self)
        self.tgt_lang_edit.setPlaceholderText(_("请输入目标语言（格式不限，AI可智能识别）"))
        self.tgt_lang_edit.setClearButtonEnabled(True)
        tgt_completer = QCompleter([], self.tgt_lang_edit)
        tgt_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tgt_lang_edit.setCompleter(tgt_completer)

        # 传统翻译服务用的下拉
        self.src_lang_combo = ComboBox(self)
        self.src_lang_combo.setPlaceholderText(_("请选择源语言"))
        self.src_lang_combo.setCurrentIndex(-1)

        self.tgt_lang_combo = ComboBox(self)
        self.tgt_lang_combo.setPlaceholderText(_("请选择目标语言"))
        self.tgt_lang_combo.setCurrentIndex(-1)

        # 添加到布局（先隐藏）
        self.grid_layout.addWidget(self.src_lang_edit, 1, 1)
        self.grid_layout.addWidget(self.src_lang_combo, 1, 1)
        self.grid_layout.addWidget(self.tgt_lang_edit, 2, 1)
        self.grid_layout.addWidget(self.tgt_lang_combo, 2, 1)
        self.src_lang_edit.hide()
        self.src_lang_combo.hide()
        self.tgt_lang_edit.hide()
        self.tgt_lang_combo.hide()

    def update_service_type(self, service_type):
        """切换 LLM / 传统 翻译服务时，显示对应的语言输入方式"""
        self.current_service_type = service_type
        self.src_lang_edit.hide()
        self.src_lang_combo.hide()
        self.tgt_lang_edit.hide()
        self.tgt_lang_combo.hide()
        if service_type == 0:
            self.src_lang_edit.show()
            self.tgt_lang_edit.show()
        else:
            self.src_lang_combo.show()
            self.tgt_lang_combo.show()

    def select_log_folder(self):
        folder = QFileDialog.getExistingDirectory(self)
        if folder:
            self.log_location_edit.setText(folder)


class TranslationServiceInterface(QFrame):
    """翻译服务界面组件"""

    # 添加服务类型改变信号
    service_type_changed: pyqtSignal = pyqtSignal(int)
    # 新增：发送消息服务类型改变信号
    send_service_type_changed: pyqtSignal = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("translationService")

        self.init_ui()

    def init_ui(self):
        # 创建主网格布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('翻译服务设置'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 创建内容容器
        self.content_widget = QFrame(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(20)

        # 创建TabBar（初始隐藏）
        self.tab_bar = TabBar(self)
        self.tab_bar.setAddButtonVisible(False)
        self.tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)
        # 设置TabBar的最小宽度，使其更长
        self.tab_bar.setMinimumWidth(600)

        # 美化TabBar
        self.tab_bar.setTabShadowEnabled(True)  # 启用阴影效果
        # 设置选中标签的背景色（浅色主题/深色主题）
        self.tab_bar.setTabSelectedBackgroundColor(
            QColor(230, 230, 230),  # 浅色主题下的选中背景
            QColor(60, 60, 60)  # 深色主题下的选中背景
        )

        self.tab_bar.hide()

        # 创建堆叠窗口用于切换不同的标签页内容
        self.tab_stacked_widget = QStackedWidget(self)

        # 创建玩家消息服务界面
        self.player_service_widget = self.create_service_widget("player")
        self.tab_stacked_widget.addWidget(self.player_service_widget)

        # 创建发送消息服务界面（初始不添加）
        self.send_service_widget = None

        # 添加第一个标签
        self.tab_bar.addTab(
            routeKey="playerService",
            text=_("玩家消息翻译服务"),
            onClick=lambda: self.switch_tab(0)
        )

        # 创建TabBar容器，用于居左显示
        self.tab_container = QFrame(self)
        tab_container_layout = QHBoxLayout(self.tab_container)
        tab_container_layout.setContentsMargins(0, 0, 0, 10)  # 底部留出一些间距
        tab_container_layout.addWidget(self.tab_bar)
        tab_container_layout.addStretch()  # 添加弹性空间，让TabBar居左

        # 添加到内容布局
        self.content_layout.addWidget(self.tab_container)
        self.content_layout.addWidget(self.tab_stacked_widget)

        # 添加内容到主布局
        self.main_layout.addWidget(self.content_widget)
        self.main_layout.addStretch()

        # 添加独立设置复选框到底部
        self.independent_service_check = CheckBox(_('独立设置消息发送翻译服务'), self)
        self.independent_service_check.toggled.connect(self.on_independent_service_toggled)

        # 创建底部容器
        bottom_container = QFrame(self)
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.independent_service_check)
        bottom_layout.addStretch()

        self.main_layout.addWidget(bottom_container)

    def create_service_widget(self, service_id):
        """创建服务配置界面"""
        widget = QFrame(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(20)

        # 创建分段导航控件
        segmented_widget = SegmentedWidget(widget)

        # 创建堆叠窗口用于切换不同服务类型
        stacked_widget = QStackedWidget(widget)

        # 创建LLM服务界面
        llm_service_widget = self.create_llm_service_widget(widget, service_id)
        stacked_widget.addWidget(llm_service_widget)

        # 创建传统翻译服务界面
        traditional_service_widget = self.create_traditional_service_widget(widget, service_id)
        stacked_widget.addWidget(traditional_service_widget)

        # 添加服务类型选项
        segmented_widget.addItem(
            routeKey=f"llm_service_{service_id}",
            text=_("                AI翻译                "),
            onClick=lambda: self.switch_service_type(stacked_widget, 0, service_id)
        )
        segmented_widget.addItem(
            routeKey=f"traditional_service_{service_id}",
            text=_("                传统翻译                "),
            onClick=lambda: self.switch_service_type(stacked_widget, 1, service_id)
        )

        # 设置默认选择
        segmented_widget.setCurrentItem(f"llm_service_{service_id}")
        stacked_widget.setCurrentIndex(0)

        # 保存引用
        widget.segmented_widget = segmented_widget
        widget.stacked_widget = stacked_widget
        widget.service_id = service_id

        layout.addWidget(segmented_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(stacked_widget)

        return widget

    def on_independent_service_toggled(self, checked):
        """处理独立设置复选框状态变化"""
        if checked:
            # 显示TabBar
            self.tab_container.show()

            # 添加第二个标签页
            if self.send_service_widget is None:
                self.send_service_widget = self.create_service_widget("send")
                self.tab_stacked_widget.addWidget(self.send_service_widget)

            # 添加第二个标签
            if self.tab_bar.count() == 1:
                self.tab_bar.addTab(
                    routeKey="sendService",
                    text=_("消息发送翻译服务"),
                    onClick=lambda: self.switch_tab(1)
                )

            # 显示TabBar
            self.tab_bar.show()
        else:
            # 隐藏TabBar
            self.tab_bar.hide()
            self.tab_container.hide()

            # 移除第二个标签页
            if self.tab_bar.count() > 1:
                self.tab_bar.removeTab(1)

            # 切换回第一个标签
            self.tab_bar.setCurrentTab("playerService")
            self.tab_stacked_widget.setCurrentIndex(0)

    def switch_tab(self, index):
        """切换标签页"""
        self.tab_stacked_widget.setCurrentIndex(index)

    def switch_service_type(self, stacked_widget, service_type, service_id):
        """切换服务类型"""
        stacked_widget.setCurrentIndex(service_type)

        # 根据service_id发射不同的信号
        if service_id == "player":
            self.service_type_changed.emit(service_type)
        elif service_id == "send":
            self.send_service_type_changed.emit(service_type)

    def create_llm_service_widget(self, parent, service_id):
        """创建LLM服务界面"""
        widget = QFrame(parent)
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(15)

        # 服务选择
        service_label = BodyLabel(_('选择服务：'), widget)
        llm_service_combo = ComboBox(widget)
        llm_service_combo.addItems(LLM_PROVIDERS)
        llm_service_combo.setPlaceholderText(_("请选择翻译服务"))
        llm_service_combo.setCurrentIndex(-1)
        llm_service_combo.setFixedWidth(200)

        layout.addWidget(service_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(llm_service_combo, 0, 1)

        # API Key输入
        api_key_label = BodyLabel(_('API Key：'), widget)
        llm_api_key_edit = LineEdit(widget)
        llm_api_key_edit.setPlaceholderText(_("请输入您的API Key"))
        llm_api_key_edit.setFixedWidth(300)

        layout.addWidget(api_key_label, 1, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(llm_api_key_edit, 1, 1)

        # API URL输入
        llm_api_url_label = BodyLabel(_('API地址：'), widget)
        llm_api_url_edit = EditableComboBox(widget)
        llm_api_url_edit.addItems([_("默认端点")])
        llm_api_url_edit.setCurrentText(_("默认端点"))
        llm_api_url_edit.setFixedWidth(300)

        layout.addWidget(llm_api_url_label, 2, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(llm_api_url_edit, 2, 1)

        # 模型代号输入
        model_label = BodyLabel(_('模型代号：'), widget)
        llm_model_edit = LineEdit(widget)
        llm_model_edit.setPlaceholderText(_("请输入模型代号，如：gpt-3.5-turbo"))
        llm_model_edit.setClearButtonEnabled(True)
        llm_model_edit.setFixedWidth(300)

        layout.addWidget(model_label, 3, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(llm_model_edit, 3, 1)

        # 添加弹性空间
        layout.setColumnStretch(2, 1)
        layout.setRowStretch(5, 1)

        # 保存控件引用
        widget.llm_service_combo = llm_service_combo
        widget.llm_api_key_edit = llm_api_key_edit
        widget.llm_api_url_label = llm_api_url_label
        widget.llm_api_url_edit = llm_api_url_edit
        widget.llm_model_edit = llm_model_edit
        widget.service_id = service_id

        return widget

    def create_traditional_service_widget(self, parent, service_id):
        """创建传统翻译服务界面"""
        widget = QFrame(parent)
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(15)

        # 服务选择
        service_label = BodyLabel(_('选择服务：'), widget)

        # 创建一个水平布局来容纳ComboBox和加载动画
        service_container = QFrame(widget)
        service_layout = QHBoxLayout(service_container)
        service_layout.setContentsMargins(0, 0, 0, 0)
        service_layout.setSpacing(10)

        traditional_service_combo = ComboBox(service_container)
        traditional_service_combo.addItems(TRADITIONAL_SERVICES)
        traditional_service_combo.setPlaceholderText(_("请选择翻译服务"))
        traditional_service_combo.setCurrentIndex(-1)
        traditional_service_combo.setFixedWidth(200)

        # 创建加载动画
        loading_spinner = IndeterminateProgressRing(service_container)
        loading_spinner.setFixedSize(24, 24)
        loading_spinner.setStrokeWidth(3)
        loading_spinner.hide()

        service_layout.addWidget(traditional_service_combo)
        service_layout.addWidget(loading_spinner)
        service_layout.addStretch()

        layout.addWidget(service_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(service_container, 0, 1)

        # API Key标签和输入
        traditional_api_key_label = BodyLabel(_('API Key：'), widget)
        traditional_api_key_edit = EditableComboBox(widget)
        traditional_api_key_edit.addItems([_("不使用")])
        traditional_api_key_edit.setCurrentText(_("不使用"))
        traditional_api_key_edit.setFixedWidth(300)

        layout.addWidget(traditional_api_key_label, 1, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(traditional_api_key_edit, 1, 1)

        # 添加弹性空间
        layout.setColumnStretch(2, 1)
        layout.setRowStretch(3, 1)

        # 保存控件引用
        widget.traditional_service_combo = traditional_service_combo
        widget.loading_spinner = loading_spinner
        widget.traditional_api_key_label = traditional_api_key_label
        widget.traditional_api_key_edit = traditional_api_key_edit
        widget.service_id = service_id

        # 连接信号
        # noinspection PyUnresolvedReferences
        traditional_service_combo.currentTextChanged.connect(
            lambda text: self.parent().on_traditional_service_changed(text, service_id)
            if hasattr(self.parent(), 'on_traditional_service_changed') else None
        )

        return widget

    def show_loading_spinner(self, show: bool, service_id: str = "player"):
        """显示或隐藏加载动画"""
        # 根据service_id获取对应的widget
        if service_id == "player":
            widget = self.player_service_widget
        elif service_id == "send" and self.send_service_widget:
            widget = self.send_service_widget
        else:
            return

        if widget and hasattr(widget, 'stacked_widget'):
            service_widget = widget.stacked_widget.currentWidget()
            if hasattr(service_widget, 'loading_spinner'):
                if show:
                    service_widget.loading_spinner.show()
                    if hasattr(service_widget, 'traditional_service_combo'):
                        service_widget.traditional_service_combo.setEnabled(False)

                    # 根据service_id锁定对应的界面
                    if service_id == "player":
                        # 锁定 MessageCaptureInterface 的语言下拉框
                        message_capture = self.parent().findChild(MessageCaptureInterface)
                        if message_capture and hasattr(message_capture, 'src_lang_combo'):
                            message_capture.src_lang_combo.setEnabled(False)
                            # noinspection PyUnresolvedReferences
                            message_capture.tgt_lang_combo.setEnabled(False)
                    elif service_id == "send":
                        # 锁定 MessageSendInterface 的语言下拉框
                        message_send = self.parent().findChild(MessageSendInterface)
                        if message_send and hasattr(message_send, 'src_lang_combo'):
                            message_send.src_lang_combo.setEnabled(False)
                            # noinspection PyUnresolvedReferences
                            message_send.tgt_lang_combo.setEnabled(False)
                else:
                    service_widget.loading_spinner.hide()
                    if hasattr(service_widget, 'traditional_service_combo'):
                        service_widget.traditional_service_combo.setEnabled(True)

                    # 根据service_id解锁对应的界面
                    if service_id == "player":
                        # 解锁 MessageCaptureInterface 的语言下拉框
                        message_capture = self.parent().findChild(MessageCaptureInterface)
                        if message_capture and hasattr(message_capture, 'src_lang_combo'):
                            message_capture.src_lang_combo.setEnabled(True)
                            # noinspection PyUnresolvedReferences
                            message_capture.tgt_lang_combo.setEnabled(True)
                    elif service_id == "send":
                        # 解锁 MessageSendInterface 的语言下拉框
                        message_send = self.parent().findChild(MessageSendInterface)
                        if message_send and hasattr(message_send, 'src_lang_combo'):
                            message_send.src_lang_combo.setEnabled(True)
                            # noinspection PyUnresolvedReferences
                            message_send.tgt_lang_combo.setEnabled(True)

    def get_current_service_type(self, service_id: str = "player"):
        """获取当前服务类型"""
        if service_id == "player" and self.player_service_widget:
            if hasattr(self.player_service_widget, 'stacked_widget'):
                return self.player_service_widget.stacked_widget.currentIndex()
        elif service_id == "send" and self.send_service_widget:
            if hasattr(self.send_service_widget, 'stacked_widget'):
                return self.send_service_widget.stacked_widget.currentIndex()
        return 0

    def get_current_service(self, service_id: str = "player"):
        """获取当前选择的服务"""
        widget = None
        if service_id == "player":
            widget = self.player_service_widget
        elif service_id == "send" and self.send_service_widget:
            widget = self.send_service_widget

        if widget and hasattr(widget, 'stacked_widget'):
            current_widget = widget.stacked_widget.currentWidget()
            if hasattr(current_widget, 'llm_service_combo'):
                return current_widget.llm_service_combo.currentText()
            elif hasattr(current_widget, 'traditional_service_combo'):
                return current_widget.traditional_service_combo.currentText()
        return None

    def get_current_api_key(self, service_id: str = "player"):
        """获取当前API Key"""
        widget = None
        if service_id == "player":
            widget = self.player_service_widget
        elif service_id == "send" and self.send_service_widget:
            widget = self.send_service_widget

        if widget and hasattr(widget, 'stacked_widget'):
            current_widget = widget.stacked_widget.currentWidget()
            if hasattr(current_widget, 'llm_api_key_edit'):
                return current_widget.llm_api_key_edit.text()
            elif hasattr(current_widget, 'traditional_api_key_edit'):
                return current_widget.traditional_api_key_edit.currentText()
        return None

    def get_current_api_url(self, service_id: str = "player"):
        """获取当前API URL（仅LLM服务）"""
        widget = None
        if service_id == "player":
            widget = self.player_service_widget
        elif service_id == "send" and self.send_service_widget:
            widget = self.send_service_widget

        if widget and hasattr(widget, 'stacked_widget'):
            current_widget = widget.stacked_widget.currentWidget()
            if hasattr(current_widget, 'llm_api_url_edit'):
                return current_widget.llm_api_url_edit.currentText()
        return None

    def get_current_model(self, service_id: str = "player"):
        """获取当前模型代号（仅LLM服务）"""
        widget = None
        if service_id == "player":
            widget = self.player_service_widget
        elif service_id == "send" and self.send_service_widget:
            widget = self.send_service_widget

        if widget and hasattr(widget, 'stacked_widget'):
            current_widget = widget.stacked_widget.currentWidget()
            if hasattr(current_widget, 'llm_model_edit'):
                return current_widget.llm_model_edit.text()
        return None


class MessagePresentationInterface(QFrame):
    """翻译结果呈现界面组件"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("messagePresentation")

        self.init_ui()

    def init_ui(self):
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('翻译结果显示'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 创建网格布局用于表单
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)

        # 网页端口
        self.web_port_label = BodyLabel(_('网页端口：'), self)
        self.web_port_spin = SpinBox(self)
        self.web_port_spin.setRange(1024, 65535)
        self.web_port_spin.setValue(8080)

        self.grid_layout.addWidget(self.web_port_label, 0, 0)
        self.grid_layout.addWidget(self.web_port_spin, 0, 1)

        self.main_layout.addLayout(self.grid_layout)
        self.main_layout.addStretch()


class MessageSendInterface(QFrame):
    """消息发送界面组件"""

    def __init__(self, parent, service_type):
        super().__init__(parent=parent)
        self.setObjectName("messageSend")
        self.current_service_type = service_type
        self.init_ui(service_type)

    def init_ui(self, service_type):
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('消息发送设置'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 表单网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        self.grid_layout.setColumnStretch(1, 1)

        # 是否监控剪切板
        self.clipboard_monitor_check = CheckBox(_('监控剪切板'), self)
        set_tool_tip(self.clipboard_monitor_check, _("从剪切板获取要发送的消息"))
        self.grid_layout.addWidget(self.clipboard_monitor_check, 0, 0, 1, 2)

        # 源/目标语言标签
        src_label = BodyLabel(_('源语言：'), self)
        tgt_label = BodyLabel(_('目标语言：'), self)
        self.grid_layout.addWidget(src_label, 1, 0)
        self.grid_layout.addWidget(tgt_label, 2, 0)

        # 语言控件
        self.create_all_language_widgets()

        self.main_layout.addLayout(self.grid_layout)
        self.main_layout.addStretch()
        self.update_service_type(service_type)

    def create_all_language_widgets(self):
        # LLM 模式
        self.src_lang_edit = LineEdit(self)
        self.src_lang_edit.setPlaceholderText(_("请输入源语言（格式不限，AI可智能识别）"))
        self.src_lang_edit.setClearButtonEnabled(True)
        src_completer = QCompleter([], self.src_lang_edit)
        src_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.src_lang_edit.setCompleter(src_completer)

        self.tgt_lang_edit = LineEdit(self)
        self.tgt_lang_edit.setPlaceholderText(_("请输入目标语言（格式不限，AI可智能识别）"))
        self.tgt_lang_edit.setClearButtonEnabled(True)
        tgt_completer = QCompleter([], self.tgt_lang_edit)
        tgt_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tgt_lang_edit.setCompleter(tgt_completer)

        # 传统翻译服务
        self.src_lang_combo = ComboBox(self)
        self.src_lang_combo.setPlaceholderText(_("请选择源语言"))
        self.src_lang_combo.setCurrentIndex(-1)

        self.tgt_lang_combo = ComboBox(self)
        self.tgt_lang_combo.setPlaceholderText(_("请选择目标语言"))
        self.tgt_lang_combo.setCurrentIndex(-1)

        # 添加到布局（先隐藏）
        self.grid_layout.addWidget(self.src_lang_edit, 1, 1)
        self.grid_layout.addWidget(self.src_lang_combo, 1, 1)
        self.grid_layout.addWidget(self.tgt_lang_edit, 2, 1)
        self.grid_layout.addWidget(self.tgt_lang_combo, 2, 1)
        self.src_lang_edit.hide()
        self.src_lang_combo.hide()
        self.tgt_lang_edit.hide()
        self.tgt_lang_combo.hide()

    def update_service_type(self, service_type):
        """切换 LLM / 传统 翻译服务时，显示对应的语言输入方式"""
        self.current_service_type = service_type
        self.src_lang_edit.hide()
        self.src_lang_combo.hide()
        self.tgt_lang_edit.hide()
        self.tgt_lang_combo.hide()
        if service_type == 0:
            self.src_lang_edit.show()
            self.tgt_lang_edit.show()
        else:
            self.src_lang_combo.show()
            self.tgt_lang_combo.show()


class GlossaryInterface(QFrame):
    """术语表界面组件"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("glossary")
        self.parent_ref = parent

        # 状态变量
        self.selected_row = -1
        self.glossary_rules = {}

        self.init_ui()
        self.load_glossary_data()

    def init_ui(self):
        # 主布局
        self.main_layout = QGridLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('术语表管理'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title, 0, 0, 1, 4)

        # 输入区域
        input_frame = QFrame(self)
        input_layout = QGridLayout(input_frame)
        input_layout.setSpacing(10)

        # 源术语输入
        src_label = BodyLabel(_('源术语：'), input_frame)
        self.src_edit = LineEdit(input_frame)
        self.src_edit.setPlaceholderText(_("请输入源术语"))
        self.src_edit.setClearButtonEnabled(True)

        input_layout.addWidget(src_label, 0, 0)
        input_layout.addWidget(self.src_edit, 0, 1)

        # 目标术语输入
        tgt_label = BodyLabel(_('目标术语：'), input_frame)
        self.tgt_edit = LineEdit(input_frame)
        self.tgt_edit.setPlaceholderText(_("请输入目标术语"))
        self.tgt_edit.setClearButtonEnabled(True)

        input_layout.addWidget(tgt_label, 1, 0)
        input_layout.addWidget(self.tgt_edit, 1, 1)

        # 操作按钮
        self.add_update_button = PushButton(_('添加/更新术语'), input_frame)
        self.add_update_button.clicked.connect(self.add_update_term)
        input_layout.addWidget(self.add_update_button, 0, 2, 1, 1)

        # 清空输入按钮移动到添加/更新术语下方
        self.clear_button = PushButton(_('清空输入'), input_frame)
        self.clear_button.clicked.connect(self.clear_inputs)
        input_layout.addWidget(self.clear_button, 1, 2, 1, 1)

        input_layout.setColumnStretch(1, 1)
        self.main_layout.addWidget(input_frame, 1, 0, 1, 4)

        # 术语表表格
        self.table = TableWidget(self)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([_('源术语'), _('目标术语')])
        self.table.verticalHeader().hide()
        self.table.setSelectRightClickedRow(True)

        # 连接选择变化信号
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        self.main_layout.addWidget(self.table, 2, 0, 1, 4)

        # 底部操作按钮
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.delete_button = PushButton(_('删除选中术语'), button_frame)
        self.delete_button.clicked.connect(self.delete_selected_term)
        self.delete_button.setEnabled(False)

        self.clear_all_button = PushButton(_('清空术语'), button_frame)
        self.clear_all_button.clicked.connect(self.clear_all_terms)

        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_all_button)

        self.main_layout.addWidget(button_frame, 3, 0, 1, 4)

        # 设置行拉伸
        self.main_layout.setRowStretch(2, 1)

    def load_glossary_data(self):
        """从配置加载术语表数据"""
        try:
            if hasattr(self.parent_ref, 'config') and hasattr(self.parent_ref.config, 'glossary'):
                if isinstance(self.parent_ref.config.glossary, dict):
                    self.glossary_rules = self.parent_ref.config.glossary.copy()
                    logger.info(f"Loaded glossary rules: {len(self.glossary_rules)}")
                else:
                    logger.warning("Glossary in config is not a dictionary. Initializing as empty.")
                    self.glossary_rules = {}
            else:
                logger.info("No glossary found in config. Initializing as empty.")
                self.glossary_rules = {}
        except Exception as e:
            logger.error(f"Error loading glossary data: {e}")
            self.glossary_rules = {}

        self.update_table_display()

    def update_table_display(self):
        """更新表格显示"""
        self.table.setRowCount(len(self.glossary_rules))

        if not self.glossary_rules:
            # 表格为空时，设置两列各占一半
            self._set_equal_column_widths()
            return

        # 按源术语排序显示
        sorted_items = sorted(self.glossary_rules.items())

        for row, (src, tgt) in enumerate(sorted_items):
            src_item = QTableWidgetItem(src)
            tgt_item = QTableWidgetItem(tgt)

            self.table.setItem(row, 0, src_item)
            self.table.setItem(row, 1, tgt_item)

        # 智能调整列宽
        self._adjust_column_widths()

    def _set_equal_column_widths(self):
        """设置两列等宽"""
        table_width = self.table.viewport().width()
        half_width = (table_width - 20) // 2  # 减去20像素作为边距
        self.table.setColumnWidth(0, half_width)
        self.table.setColumnWidth(1, half_width)

    def _adjust_column_widths(self):
        """智能调整列宽度"""
        # 先按内容调整列宽
        self.table.resizeColumnsToContents()

        # 获取表格总宽度（减去滚动条等）
        table_width = self.table.viewport().width()

        # 获取当前列宽
        col0_width = self.table.columnWidth(0)
        col1_width = self.table.columnWidth(1)

        # 计算总内容宽度
        total_content_width = col0_width + col1_width

        # 如果内容总宽度小于表格宽度的80%，则平分宽度
        if total_content_width < table_width * 0.8:
            self._set_equal_column_widths()
        else:
            # 内容较长时，保持resizeColumnsToContents的结果
            # 但确保不超过合理范围
            max_col_width = table_width * 0.7  # 单列最大不超过70%

            if col0_width > max_col_width:
                self.table.setColumnWidth(0, int(max_col_width))
            if col1_width > max_col_width:
                self.table.setColumnWidth(1, int(max_col_width))

    def on_selection_changed(self):
        """表格选择变化时的处理"""
        selected_items = self.table.selectedItems()

        if selected_items:
            # 获取选中行
            self.selected_row = selected_items[0].row()

            # 获取选中行的数据
            src_item = self.table.item(self.selected_row, 0)
            tgt_item = self.table.item(self.selected_row, 1)

            if src_item and tgt_item:
                # 填充输入框
                self.src_edit.setText(src_item.text())
                self.tgt_edit.setText(tgt_item.text())

                # 启用删除按钮
                self.delete_button.setEnabled(True)
        else:
            self.selected_row = -1
            self.delete_button.setEnabled(False)

    def add_update_term(self):
        """添加或更新术语"""
        src_text = self.src_edit.text().strip()
        tgt_text = self.tgt_edit.text().strip()

        if not src_text:
            InfoBar.warning(
                title=_('输入错误'),
                content=_('源术语不能为空'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # 检查是否是更新现有术语
        old_src = None
        if self.selected_row >= 0:
            old_src_item = self.table.item(self.selected_row, 0)
            if old_src_item:
                old_src = old_src_item.text()

        # 如果源术语已存在且不是当前编辑的术语，询问是否覆盖
        if src_text in self.glossary_rules and src_text != old_src:
            w = MessageBox(
                _("确认覆盖"),
                _('源术语 “{}” 已存在，是否覆盖？').format(src_text),
                self.window()
            )
            if not w.exec():
                return

        # 如果是编辑现有术语且源术语发生变化，先删除旧的
        if old_src and old_src != src_text and old_src in self.glossary_rules:
            del self.glossary_rules[old_src]

        # 添加或更新术语
        self.glossary_rules[src_text] = tgt_text

        action = _("更新") if old_src else _("添加")
        logger.info(f"Term {action}: '{src_text}' -> '{tgt_text}'")

        # 显示成功信息
        InfoBar.success(
            title=_('术语{}成功').format(action),
            content=f'"{src_text}" -> "{tgt_text}"',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

        # 更新显示
        self.update_table_display()
        self.clear_inputs()

    def delete_selected_term(self):
        """删除选中的术语"""
        if self.selected_row < 0:
            return

        src_item = self.table.item(self.selected_row, 0)
        if not src_item:
            return

        src_text = src_item.text()

        # 直接删除，不需要确认
        if src_text in self.glossary_rules:
            del self.glossary_rules[src_text]
            logger.info(f"Term deleted: {src_text}")

            InfoBar.success(
                title=_('删除成功'),
                content=_('术语 “{}” 已删除').format(src_text),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

            self.update_table_display()
            self.clear_inputs()

    def clear_inputs(self):
        """清空输入框"""
        self.src_edit.clear()
        self.tgt_edit.clear()
        self.table.clearSelection()
        self.selected_row = -1
        self.delete_button.setEnabled(False)

    def clear_all_terms(self):
        """清空所有术语"""
        if not self.glossary_rules:
            InfoBar.info(
                title=_('提示'),
                content=_('术语表为空，无需清空'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        w = MessageBox(
            _("确认清空"),
            _("确定要清空所有术语吗？此操作不可恢复。"),
            self.window()  # 设置父级为主窗口
        )

        if w.exec():
            # 确认清空
            count = len(self.glossary_rules)
            self.glossary_rules.clear()
            logger.info(f"Glossary cleared, deleted {count} terms")

            InfoBar.success(
                title=_('清空成功'),
                content=_('已清空 {} 个术语').format(count),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

            self.update_table_display()
            self.clear_inputs()

    def get_glossary_data(self):
        """获取当前术语表数据，供保存时使用"""
        return self.glossary_rules.copy()

    def resizeEvent(self, event):
        """窗口大小改变时重新调整列宽"""
        super().resizeEvent(event)
        # 延迟调整，确保布局已经完成
        if hasattr(self, 'table'):
            self.table.viewport().update()
            # 使用QTimer延迟调整，避免在resize过程中频繁调整
            if self.table.rowCount() > 0:
                QTimer.singleShot(100, self._adjust_column_widths)
            else:
                QTimer.singleShot(100, self._set_equal_column_widths)


class StartInterface(QFrame):
    """启动界面组件"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("start")
        self.init_ui()

    def init_ui(self):
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('启动'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 启动按钮
        self.start_button = PushButton(_('获取并打印所有配置'), self)
        self.start_button.clicked.connect(self.print_all_configs)
        self.main_layout.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignCenter)

        # 添加弹性空间
        self.main_layout.addStretch()

    # noinspection PyUnresolvedReferences
    def print_all_configs(self):
        """获取并打印所有配置"""
        print("\n" + "=" * 60)
        print("所有配置信息")
        print("=" * 60)

        # 获取主窗口引用
        main_window = self.window()

        # 1. 消息捕获配置
        print("\n【消息捕获配置】")
        msg_capture = main_window.message_capture_interface
        print(f"MC日志位置: {msg_capture.log_location_edit.text()}")

        # 根据服务类型获取语言设置
        if msg_capture.current_service_type == 0:  # LLM模式
            print(f"源语言: {msg_capture.src_lang_edit.text()}")
            print(f"目标语言: {msg_capture.tgt_lang_edit.text()}")
        else:  # 传统翻译模式
            print(f"源语言: {msg_capture.src_lang_combo.currentText()}")
            print(f"目标语言: {msg_capture.tgt_lang_combo.currentText()}")

        print(f"日志编码: {msg_capture.log_encoding_combo.currentText()}")
        print(f"监控模式: {'高效模式' if msg_capture.efficient_mode_radio.isChecked() else '兼容模式'}")
        print(f"翻译非玩家消息: {msg_capture.translate_non_player_check.isChecked()}")
        print(f"替换乱码字符: {msg_capture.replace_garbled_check.isChecked()}")

        # 2. 翻译服务配置
        print("\n【翻译服务配置】")
        trans_service = main_window.translation_service_interface
        print(f"独立设置玩家消息和发送消息服务: {trans_service.independent_service_check.isChecked()}")

        # 玩家消息服务配置
        print("\n  [玩家消息翻译服务]")
        player_service_type = trans_service.get_current_service_type("player")
        print(f"  服务类型: {'LLM' if player_service_type == 0 else '传统翻译'}")

        player_widget = trans_service.player_service_widget
        if player_widget and hasattr(player_widget, 'stacked_widget'):
            current_widget = player_widget.stacked_widget.currentWidget()

            if player_service_type == 0:  # LLM
                if hasattr(current_widget, 'llm_service_combo'):
                    print(f"  选择服务: {current_widget.llm_service_combo.currentText()}")
                    print(f"  API Key: {current_widget.llm_api_key_edit.text()}")
                    print(f"  API URL: {current_widget.llm_api_url_edit.currentText()}")
                    print(f"  模型代号: {current_widget.llm_model_edit.text()}")
            else:  # 传统翻译
                if hasattr(current_widget, 'traditional_service_combo'):
                    print(f"  选择服务: {current_widget.traditional_service_combo.currentText()}")
                    print(f"  API Key: {current_widget.traditional_api_key_edit.currentText()}")

        # 发送消息服务配置（如果启用独立设置）
        if trans_service.independent_service_check.isChecked() and trans_service.send_service_widget:
            print("\n  [发送消息翻译服务]")
            send_service_type = trans_service.get_current_service_type("send")
            print(f"  服务类型: {'LLM' if send_service_type == 0 else '传统翻译'}")

            send_widget = trans_service.send_service_widget
            if send_widget and hasattr(send_widget, 'stacked_widget'):
                current_widget = send_widget.stacked_widget.currentWidget()

                if send_service_type == 0:  # LLM
                    if hasattr(current_widget, 'llm_service_combo'):
                        print(f"  选择服务: {current_widget.llm_service_combo.currentText()}")
                        print(f"  API Key: {current_widget.llm_api_key_edit.text()}")
                        print(f"  API URL: {current_widget.llm_api_url_edit.currentText()}")
                        print(f"  模型代号: {current_widget.llm_model_edit.text()}")
                else:  # 传统翻译
                    if hasattr(current_widget, 'traditional_service_combo'):
                        print(f"  选择服务: {current_widget.traditional_service_combo.currentText()}")
                        print(f"  API Key: {current_widget.traditional_api_key_edit.currentText()}")

        # 3. 翻译结果呈现配置
        print("\n【翻译结果呈现配置】")
        msg_presentation = main_window.message_presentation_interface
        print("展示方式: 图形界面 + Web页面（同时启用）")
        print(f"图形界面 - 最大消息数: {msg_presentation.max_messages_spin.value()}")
        print(f"图形界面 - 始终置顶: {msg_presentation.always_on_top_switch.isChecked()}")
        print(f"Web页面 - 网页端口: {msg_presentation.web_port_spin.value()}")

        # 4. 消息发送配置
        print("\n【消息发送配置】")
        msg_send = main_window.message_send_interface
        print(f"监控剪切板: {msg_send.clipboard_monitor_check.isChecked()}")

        # 根据服务类型获取语言设置
        if msg_send.current_service_type == 0:  # LLM模式
            print(f"源语言: {msg_send.src_lang_edit.text()}")
            print(f"目标语言: {msg_send.tgt_lang_edit.text()}")
        else:  # 传统翻译模式
            print(f"源语言: {msg_send.src_lang_combo.currentText()}")
            print(f"目标语言: {msg_send.tgt_lang_combo.currentText()}")

        # 5. 术语表配置
        print("\n【术语表配置】")
        glossary = main_window.glossary_interface
        print(f"术语表规则数量: {len(glossary.glossary_rules)}")
        if glossary.glossary_rules:
            print("术语表内容:")
            for src, tgt in sorted(glossary.glossary_rules.items()):
                print(f"  {src} -> {tgt}")

        # 6. 设置配置
        print("\n【设置配置】")
        setting = main_window.setting_interface
        print(f"界面语言: {setting.language_combo.currentText()} ({setting.language_combo.currentData()})")

        print("\n" + "=" * 60)
        print("配置获取完成")
        print("=" * 60 + "\n")

        # 显示成功提示
        InfoBar.success(
            title='配置获取完成',
            content='所有配置已打印到控制台',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )


class AboutInterface(QFrame):
    """关于界面组件"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("about")
        self.init_ui()

    def init_ui(self):
        # 主布局
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(40, 40, 40, 40)
        vbox.setSpacing(24)

        # 标题卡片
        title_card = self.create_title_card()
        vbox.addWidget(title_card)

        # 信息卡片
        info_card = self.create_info_card()
        vbox.addWidget(info_card)

        # 链接卡片
        links_card = self.create_links_card()
        vbox.addWidget(links_card)

        # 许可证卡片
        license_card = self.create_license_card()
        vbox.addWidget(license_card)

        vbox.addStretch()

    def create_title_card(self):
        """创建标题卡片"""
        card = ElevatedCardWidget(self)
        card.setFixedHeight(120)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(8)

        # 应用图标和标题
        title_layout = QHBoxLayout()

        # 图标
        icon = IconWidget(FluentIcon.INFO, card)
        icon.setFixedSize(32, 32)
        title_layout.addWidget(icon)

        title_layout.addSpacing(12)

        # 标题
        title = TitleLabel('Modless Chat Trans', card)
        setFont(title, 28, weight=QFont.Weight.Bold)
        title_layout.addWidget(title)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 副标题
        subtitle = CaptionLabel('ModlessChatTransは、高性能ですから！', card)
        subtitle.setStyleSheet("color: rgb(96, 96, 96);")
        setFont(subtitle, 18, weight=QFont.Weight.Bold)
        layout.addWidget(subtitle)

        return card

    def create_info_card(self):
        """创建基本信息卡片"""
        card = SimpleCardWidget(self)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 卡片标题
        card_title = SubtitleLabel(_('应用信息'), card)
        setFont(card_title, 16, weight=QFont.Weight.DemiBold)
        layout.addWidget(card_title)

        # 信息项目
        # noinspection PyUnresolvedReferences
        info_items = [
            (FluentIcon.TAG, _("版本"), self.parent().info.version),
            (FluentIcon.PEOPLE, _("作者"), self.parent().info.author),
            (FluentIcon.MAIL, _("邮箱"), self.parent().info.email)
        ]

        for icon, label_text, value in info_items:
            item_layout = self.create_info_item(icon, label_text, value, card)
            layout.addLayout(item_layout)

        return card

    def create_info_item(self, icon, label_text, value, parent):
        """创建信息项目"""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # 图标
        icon_widget = IconWidget(icon, parent)
        icon_widget.setFixedSize(20, 20)
        layout.addWidget(icon_widget)

        # 标签
        label = BodyLabel(label_text, parent)
        label.setFixedWidth(60)
        setFont(label, 12, weight=QFont.Weight.DemiBold)
        layout.addWidget(label)

        # 值
        value_label = BodyLabel(value, parent)
        setFont(value_label, 12)
        layout.addWidget(value_label)

        layout.addStretch()
        return layout

    def create_links_card(self):
        """创建链接卡片"""
        card = SimpleCardWidget(self)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 卡片标题
        card_title = SubtitleLabel(_('相关链接'), card)
        setFont(card_title, 16, weight=QFont.Weight.DemiBold)
        layout.addWidget(card_title)

        # GitHub 链接
        github_layout = QHBoxLayout()
        github_layout.setSpacing(12)

        github_icon = IconWidget(FluentIcon.GITHUB, card)
        github_icon.setFixedSize(20, 20)
        github_layout.addWidget(github_icon)

        github_label = BodyLabel("GitHub", card)
        github_label.setFixedWidth(60)
        setFont(github_label, 12, weight=QFont.Weight.DemiBold)
        github_layout.addWidget(github_label)

        # noinspection PyUnresolvedReferences
        github_link = HyperlinkLabel(
            QUrl(self.parent().info.github),
            self.parent().info.github
        )
        setFont(github_link, 12)
        github_layout.addWidget(github_link)

        github_layout.addStretch()
        layout.addLayout(github_layout)

        return card

    def create_license_card(self):
        """创建许可证卡片"""
        card = SimpleCardWidget(self)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 卡片标题
        card_title = SubtitleLabel(_('许可证'), card)
        setFont(card_title, 16, weight=QFont.Weight.DemiBold)
        layout.addWidget(card_title)

        # 许可证信息
        license_layout = QHBoxLayout()
        license_layout.setSpacing(12)

        license_icon = IconWidget(FluentIcon.CERTIFICATE, card)
        license_icon.setFixedSize(20, 20)
        license_layout.addWidget(license_icon)

        # noinspection PyUnresolvedReferences
        license_link = HyperlinkLabel(
            QUrl(self.parent().info.license[1]),
            self.parent().info.license[0]
        )
        setFont(license_link, 12)
        license_layout.addWidget(license_link)

        license_layout.addStretch()
        layout.addLayout(license_layout)

        return card


class UpdateDialog(MessageBoxBase):
    """更新对话框"""

    def __init__(self, latest_release, current_version, parent=None):
        super().__init__(parent)
        self.latest_release = latest_release
        self.current_version = current_version

        # 设置标题
        self.titleLabel = SubtitleLabel(_('发现新版本'), self)
        self.viewLayout.addWidget(self.titleLabel)

        try:
            # 创建内容区域
            self.content_widget = QFrame(self)
            self.content_layout = QVBoxLayout(self.content_widget)
            self.content_layout.setContentsMargins(0, 16, 0, 0)
            self.content_layout.setSpacing(16)

            # 版本信息卡片
            self.version_card = self.create_version_card()
            self.content_layout.addWidget(self.version_card)

            # Release Note 卡片
            self.release_note_card = self.create_release_note_card()
            self.content_layout.addWidget(self.release_note_card)

            self.viewLayout.addWidget(self.content_widget)

            # 设置对话框大小
            self.widget.setMinimumSize(700, 500)

        except Exception as e:
            logger.error(f"Error creating update dialog content: {e}")
            # 如果创建内容失败，显示简单的错误信息
            error_label = BodyLabel(_('创建更新对话框时出错: {}').format(str(e)), self)
            self.viewLayout.addWidget(error_label)

        self.yesButton.setText(_("下载更新"))
        self.cancelButton.setText(_("暂不更新"))

        # 连接按钮信号
        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def create_version_card(self):
        """创建版本信息卡片"""
        card = SimpleCardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题
        title = BodyLabel(_('版本信息'), card)
        setFont(title, 14, weight=QFont.Weight.DemiBold)
        layout.addWidget(title)

        # 版本对比
        version_layout = QGridLayout()
        version_layout.setSpacing(12)

        # 当前版本
        current_label = CaptionLabel(_('当前版本：'), card)
        current_version = BodyLabel(f'v{self.current_version}', card)
        current_version.setStyleSheet("color: #666666;")

        # 最新版本
        latest_label = CaptionLabel(_('最新版本：'), card)
        latest_version_text = self.latest_release.get('tag_name', _('未知'))
        latest_version = BodyLabel(latest_version_text, card)
        latest_version.setStyleSheet("color: #0078d4; font-weight: bold;")

        # 发布时间
        date_label = CaptionLabel(_('发布时间：'), card)
        published_at = self.latest_release.get('published_at', _('未知'))
        if published_at != _('未知'):
            # 格式化日期
            try:
                dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                published_at = dt.strftime('%Y-%m-%d %H:%M')
            except Exception as e:
                logger.warning(f"Error formatting date: {e}")
        date_value = BodyLabel(published_at, card)

        # 发布者 - 安全地获取嵌套字典值
        author_label = CaptionLabel(_('发布者：'), card)
        author_data = self.latest_release.get('author', {})
        author_name = author_data.get('login', _('未知')) if isinstance(author_data, dict) else _('未知')
        author_value = BodyLabel(author_name, card)

        # 添加到布局
        version_layout.addWidget(current_label, 0, 0)
        version_layout.addWidget(current_version, 0, 1)
        version_layout.addWidget(latest_label, 1, 0)
        version_layout.addWidget(latest_version, 1, 1)
        version_layout.addWidget(date_label, 2, 0)
        version_layout.addWidget(date_value, 2, 1)
        version_layout.addWidget(author_label, 3, 0)
        version_layout.addWidget(author_value, 3, 1)

        # 预发布标记
        if self.latest_release.get('prerelease', False):
            prerelease_label = CaptionLabel(_('版本类型：'), card)
            prerelease_value = BodyLabel(_('预发布版本'), card)
            prerelease_value.setStyleSheet("color: #ff6b6b;")
            version_layout.addWidget(prerelease_label, 4, 0)
            version_layout.addWidget(prerelease_value, 4, 1)

        version_layout.setColumnStretch(2, 1)
        layout.addLayout(version_layout)

        return card

    def create_release_note_card(self):
        """创建 Release Note 卡片"""
        card = SimpleCardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题
        title = BodyLabel(_('更新说明'), card)
        setFont(title, 14, weight=QFont.Weight.DemiBold)
        layout.addWidget(title)

        # Release Note 内容
        self.note_browser = QTextBrowser(card)
        self.note_browser.setOpenExternalLinks(True)
        self.note_browser.setMinimumHeight(200)

        # 获取 Release Note
        release_body = self.latest_release.get('body', _('暂无更新说明'))

        # 尝试将 Markdown 转换为 HTML
        try:
            html_content = markdown.markdown(
                release_body,
                extensions=['extra', 'nl2br']
            )

            # 添加基础样式
            styled_html = f"""
            <style>
                body {{ 
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; 
                    font-size: 13px;
                    line-height: 1.6;
                    color: #333;
                    margin: 8px;
                }}
                h1, h2, h3, h4, h5, h6 {{ 
                    font-weight: bold; 
                    margin-top: 12px; 
                    margin-bottom: 8px;
                }}
                h1 {{ font-size: 20px; }}
                h2 {{ font-size: 18px; }}
                h3 {{ font-size: 16px; }}
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }}
                pre {{
                    background-color: #f4f4f4;
                    padding: 10px;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                ul, ol {{
                    margin-left: 20px;
                }}
                a {{
                    color: #0078d4;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
            <body>{html_content}</body>
            """

            self.note_browser.setHtml(styled_html)
        except Exception as e:
            logger.error(f"Error processing release note: {e}")
            self.note_browser.setPlainText(release_body)

        layout.addWidget(self.note_browser)

        # 查看完整说明链接
        html_url = self.latest_release.get('html_url', '')
        if html_url:
            link_layout = QHBoxLayout()
            link_layout.addStretch()

            github_link = HyperlinkLabel(
                QUrl(html_url),
                _('在 GitHub 上查看完整说明')
            )
            link_layout.addWidget(github_link)

            layout.addLayout(link_layout)

        return card


class DownloadProgressDialog(MessageBoxBase):
    """下载进度对话框"""

    def __init__(self, release_info, parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self._is_cancelled = False
        self.worker = None

        self.titleLabel = SubtitleLabel(_('正在下载更新'), self)
        self.viewLayout.addWidget(self.titleLabel)

        # 隐藏默认的确认按钮
        self.yesButton.hide()

        # 设置取消按钮文本
        self.cancelButton.setText(_("取消"))
        self.cancelButton.clicked.connect(self.on_cancel_clicked)

        # 版本信息
        version_label = BodyLabel(
            _('正在下载版本 {}...').format(release_info.get("tag_name", _("未知"))),
            self
        )
        self.viewLayout.addWidget(version_label)

        # 进度条
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.viewLayout.addWidget(self.progress_bar)

        # 进度信息容器
        info_frame = QFrame(self)
        info_layout = QGridLayout(info_frame)
        info_layout.setContentsMargins(0, 10, 0, 10)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(5)

        # 百分比
        self.percent_label = BodyLabel('0%', info_frame)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setFont(self.percent_label, 16, weight=QFont.Weight.DemiBold)
        info_layout.addWidget(self.percent_label, 0, 0, 2, 1)

        # 下载大小信息
        size_label = CaptionLabel(_('下载进度：'), info_frame)
        self.size_info_label = BodyLabel('0 KiB / 0 KiB', info_frame)
        info_layout.addWidget(size_label, 0, 1, Qt.AlignmentFlag.AlignRight)
        info_layout.addWidget(self.size_info_label, 0, 2, Qt.AlignmentFlag.AlignLeft)

        # 下载速度
        speed_label = CaptionLabel(_('下载速度：'), info_frame)
        self.speed_label = BodyLabel('0 KiB/s', info_frame)
        info_layout.addWidget(speed_label, 1, 1, Qt.AlignmentFlag.AlignRight)
        info_layout.addWidget(self.speed_label, 1, 2, Qt.AlignmentFlag.AlignLeft)

        # 剩余时间
        time_label = CaptionLabel(_('剩余时间：'), info_frame)
        self.time_label = BodyLabel(_('计算中...'), info_frame)
        info_layout.addWidget(time_label, 2, 1, Qt.AlignmentFlag.AlignRight)
        info_layout.addWidget(self.time_label, 2, 2, Qt.AlignmentFlag.AlignLeft)

        # 下载线程数
        thread_label = CaptionLabel(_('下载方式：'), info_frame)
        self.thread_info_label = BodyLabel(_('检测中...'), info_frame)
        info_layout.addWidget(thread_label, 3, 1, Qt.AlignmentFlag.AlignRight)
        info_layout.addWidget(self.thread_info_label, 3, 2, Qt.AlignmentFlag.AlignLeft)

        info_layout.setColumnStretch(0, 1)
        info_layout.setColumnStretch(3, 1)

        self.viewLayout.addWidget(info_frame)

        self.widget.setMinimumWidth(500)

    def set_worker(self, worker):
        """设置下载工作器"""
        self.worker = worker
        # 连接线程数更新信号
        worker.thread_count_updated.connect(self.update_thread_count)

    def update_thread_count(self, count):
        """更新线程数显示"""
        if count > 1:
            self.thread_info_label.setText(_('{} 线程下载').format(count))
        else:
            self.thread_info_label.setText(_('单线程下载'))

    def update_progress(self, downloaded, total, speed):
        """更新下载进度"""
        if self._is_cancelled:
            return

        # 计算百分比
        if total > 0:
            percent = int(downloaded * 100 / total)
            self.progress_bar.setValue(percent)
            self.percent_label.setText(f'{percent}%')

            # 格式化文件大小显示
            def format_size(bytes_size):
                """格式化文件大小为合适的单位"""
                if bytes_size < 1024:
                    return f"{bytes_size} B"
                elif bytes_size < 1024 * 1024:
                    return f"{bytes_size / 1024:.1f} KiB"
                elif bytes_size < 1024 * 1024 * 1024:
                    return f"{bytes_size / (1024 * 1024):.1f} MiB"
                else:
                    return f"{bytes_size / (1024 * 1024 * 1024):.2f} GiB"

            # 显示下载大小
            self.size_info_label.setText(f'{format_size(downloaded)} / {format_size(total)}')

            # 格式化速度显示
            def format_speed(bytes_per_sec):
                """格式化下载速度"""
                if bytes_per_sec < 1024:
                    return f"{bytes_per_sec:.0f} B/s"
                elif bytes_per_sec < 1024 * 1024:
                    return f"{bytes_per_sec / 1024:.1f} KiB/s"
                else:
                    return f"{bytes_per_sec / (1024 * 1024):.1f} MiB/s"

            self.speed_label.setText(format_speed(speed))

            # 计算剩余时间
            if speed > 0 and percent < 100:
                remaining_bytes = total - downloaded
                remaining_seconds = remaining_bytes / speed

                # 格式化时间显示
                def format_time(seconds):
                    """格式化剩余时间"""
                    if seconds < 60:
                        return _('{} 秒').format(int(seconds))
                    elif seconds < 3600:
                        minutes = int(seconds / 60)
                        secs = int(seconds % 60)
                        if secs > 0:
                            return _('{} 分 {} 秒').format(minutes, secs)
                        else:
                            return _('{} 分钟').format(minutes)
                    else:
                        hours = int(seconds / 3600)
                        minutes = int((seconds % 3600) / 60)
                        if minutes > 0:
                            return _('{} 小时 {} 分').format(hours, minutes)
                        else:
                            return _('{} 小时').format(hours)

                self.time_label.setText(format_time(remaining_seconds))
            elif percent >= 100:
                self.time_label.setText(_('完成'))
            else:
                self.time_label.setText(_('计算中...'))

    def on_cancel_clicked(self):
        """处理取消按钮点击"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self.cancelButton.setEnabled(False)
            self.cancelButton.setText(_("正在取消..."))
            if self.worker:
                self.worker.cancel()

    def set_error(self, error_msg):
        """设置错误状态"""
        self.progress_bar.error()
        self.titleLabel.setText(_('下载失败'))
        self.percent_label.setText(_('错误'))
        self.size_info_label.setText(error_msg)
        self.cancelButton.setText(_("关闭"))
        self.cancelButton.setEnabled(True)


class SettingInterface(QFrame):
    """设置界面组件"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("setting")
        self.parent_window = parent
        self.init_ui()

        # noinspection PyUnresolvedReferences
        self.updater = parent.updater

    def init_ui(self):
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 标题
        title = SubtitleLabel(_('设置'), self)
        setFont(title, 24)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # 创建滚动区域以防内容过多
        scroll_widget = QFrame(self)
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # 语言设置卡片
        language_card = self.create_language_card()
        scroll_layout.addWidget(language_card)

        # 更新设置卡片
        update_card = self.create_update_card()
        scroll_layout.addWidget(update_card)

        scroll_layout.addStretch()
        self.main_layout.addWidget(scroll_widget)

    def create_language_card(self):
        """创建语言设置卡片"""
        card = SimpleCardWidget(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        # 卡片标题
        card_title = SubtitleLabel(_('语言设置'), card)
        setFont(card_title, 16, weight=QFont.Weight.DemiBold)
        card_layout.addWidget(card_title)

        # 语言设置内容区域
        content_frame = QFrame(card)
        content_layout = QGridLayout(content_frame)
        content_layout.setContentsMargins(0, 8, 0, 0)
        content_layout.setHorizontalSpacing(16)
        content_layout.setVerticalSpacing(12)

        # 界面语言
        lang_label = BodyLabel(_('界面语言：'), content_frame)
        self.language_combo = ComboBox(content_frame)
        for lang_name, lang_code in supported_languages:
            self.language_combo.addItem(lang_name, userData=lang_code)
        self.language_combo.setCurrentIndex(0)
        self.language_combo.setFixedWidth(200)

        content_layout.addWidget(lang_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(self.language_combo, 0, 1)

        # 应用按钮
        self.save_lang_button = PushButton(_('保存'), content_frame)
        self.save_lang_button.clicked.connect(self.apply_language_setting)
        content_layout.addWidget(self.save_lang_button, 0, 2)

        # 提示信息
        tip_label = CaptionLabel(_('* 语言更改将在重启后生效'), content_frame)
        tip_label.setStyleSheet("color: #888888;")
        content_layout.addWidget(tip_label, 1, 1, 1, 2)

        # 设置列拉伸
        content_layout.setColumnStretch(3, 1)

        card_layout.addWidget(content_frame)
        return card

    def create_update_card(self):
        """创建更新设置卡片"""
        card = SimpleCardWidget(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        # 卡片标题
        card_title = SubtitleLabel(_('更新设置'), card)
        setFont(card_title, 16, weight=QFont.Weight.DemiBold)
        card_layout.addWidget(card_title)

        # 更新设置内容区域
        content_frame = QFrame(card)
        content_layout = QGridLayout(content_frame)
        content_layout.setContentsMargins(0, 8, 0, 0)
        content_layout.setHorizontalSpacing(16)
        content_layout.setVerticalSpacing(16)

        # 自动检查更新
        auto_check_label = BodyLabel(_('自动检查：'), content_frame)
        self.update_frequency_combo = ComboBox(content_frame)
        self.update_frequency_combo.addItems([_('启动时'), _('每天'), _('每周'), _('每月'), _('从不')])
        self.update_frequency_combo.setCurrentIndex(0)
        self.update_frequency_combo.setFixedWidth(200)

        content_layout.addWidget(auto_check_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(self.update_frequency_combo, 0, 1)

        # 包含预发布版本
        prerelease_label = BodyLabel(_('预发布版本：'), content_frame)
        self.include_prerelease_check = CheckBox(_('包含预发布版本'), content_frame)

        content_layout.addWidget(prerelease_label, 1, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(self.include_prerelease_check, 1, 1)

        # 手动检查更新
        check_label = BodyLabel(_('手动检查：'), content_frame)

        # 按钮和加载动画容器
        check_container = QFrame(content_frame)
        check_layout = QHBoxLayout(check_container)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.setSpacing(8)

        self.check_update_button = PushButton(_('检查更新'), check_container)
        self.check_update_button.setIcon(FIF.UPDATE)
        self.check_update_button.clicked.connect(self.check_for_updates)

        self.update_loading_spinner = IndeterminateProgressRing(check_container)
        self.update_loading_spinner.setFixedSize(20, 20)
        self.update_loading_spinner.setStrokeWidth(2)
        self.update_loading_spinner.hide()

        check_layout.addWidget(self.check_update_button)
        check_layout.addWidget(self.update_loading_spinner)
        check_layout.addStretch()

        content_layout.addWidget(check_label, 2, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(check_container, 2, 1)

        # 当前版本信息
        version_label = BodyLabel(_('当前版本：'), content_frame)
        current_version_label = BodyLabel(
            f'v{self.parent_window.updater.current_version if hasattr(self.parent_window, "updater") and self.parent_window.updater else _("未知")}',
            content_frame)
        # current_version_label.setStyleSheet("color: #666666;")

        content_layout.addWidget(version_label, 3, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(current_version_label, 3, 1)

        # 设置列拉伸
        content_layout.setColumnStretch(2, 1)

        card_layout.addWidget(content_frame)
        return card

    def apply_language_setting(self):
        """应用语言设置"""
        current_data = self.language_combo.currentData()
        current_text = self.language_combo.currentText()

        logger.info(f"Language setting applied: {current_text} ({current_data})")

        # 这里应该调用保存配置的函数
        # save_config(interface_lang=current_data)

        # 显示成功提示
        InfoBar.success(
            title=_('设置已保存'),
            content=_('界面语言已设置为 {}，重启后生效。').format(current_text),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def check_for_updates(self):
        """手动检查更新"""
        if not hasattr(self.parent_window, 'updater') or self.updater is None:
            InfoBar.error(
                title=_('错误'),
                content=_('更新器未初始化'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # 显示加载动画，禁用按钮
        self.check_update_button.setEnabled(False)
        self.update_loading_spinner.show()

        # 设置是否包含预发布版本
        self.updater.include_prerelease = self.include_prerelease_check.isChecked()

        # 创建检查更新的线程
        check_thread = QThread()

        def run_check():
            try:
                latest_release = self.updater.check_update()
                check_thread.latest_release = latest_release
            except Exception as e:
                check_thread.error = str(e)
                check_thread.latest_release = None

        check_thread.run = run_check
        # noinspection PyUnresolvedReferences
        check_thread.finished.connect(lambda: self.on_update_check_finished(check_thread))
        check_thread.start()

        # 保存线程引用，防止被垃圾回收
        self.update_check_thread = check_thread

    def on_update_check_finished(self, thread):
        """更新检查完成的回调"""
        # 隐藏加载动画，启用按钮
        self.update_loading_spinner.hide()
        self.check_update_button.setEnabled(True)

        if hasattr(thread, 'error'):
            # 检查过程出错
            InfoBar.error(
                title=_('检查更新失败'),
                content=_('错误: {}').format(thread.error),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        elif thread.latest_release:
            try:
                # 发现新版本，显示更新对话框
                dialog = UpdateDialog(
                    thread.latest_release,
                    self.updater.current_version,
                    self.window()
                )

                if dialog.exec():
                    self.start_download(thread.latest_release)
                else:
                    logger.info("User chose to skip update")

            except Exception as e:
                logger.error(f"Error showing update dialog: {e}")
                # 如果详细对话框失败，使用简单的消息框
                latest_version = thread.latest_release.get("tag_name", _("未知版本"))
                w = MessageBox(
                    _('发现新版本'),
                    _('最新版本: {}\n当前版本: v{}\n\n是否在浏览器中查看？').format(latest_version,
                                                                                   self.updater.current_version),
                    self.window()
                )

                if w.exec():
                    release_url = thread.latest_release.get("html_url")
                    if release_url:
                        webbrowser.open(release_url)
        else:
            # 已是最新版本
            InfoBar.success(
                title=_('您是最新的'),
                content=_('当前版本 v{} 已是最新版本').format(self.updater.current_version),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        # 清理线程引用
        self.update_check_thread = None

    def on_download_confirmed(self, dialog, latest_release):
        """用户确认下载"""
        dialog.accept()  # 关闭对话框
        self.start_download(latest_release)

    def start_download(self, latest_release):
        """开始下载更新"""
        # 显示下载进度对话框
        progress_dialog = DownloadProgressDialog(latest_release, self.window())

        # 创建工作线程和工作器
        download_thread = QThread()
        worker = DownloadWorker(self.updater, latest_release)
        worker.moveToThread(download_thread)

        # 设置worker到对话框
        progress_dialog.set_worker(worker)

        # 连接信号
        # noinspection PyUnresolvedReferences
        download_thread.started.connect(worker.download)
        worker.progress_updated.connect(progress_dialog.update_progress)
        worker.thread_count_updated.connect(progress_dialog.update_thread_count)  # 添加这行
        worker.download_finished.connect(lambda path: self.on_download_finished(path, progress_dialog, download_thread))
        worker.download_error.connect(lambda error: self.on_download_error(error, progress_dialog, download_thread))

        # 保存引用防止被垃圾回收
        self.download_thread = download_thread
        self.download_worker = worker

        # 启动下载
        download_thread.start()

        # 显示进度对话框
        progress_dialog.exec()

    def on_download_finished(self, file_path, progress_dialog, thread):
        """下载完成的回调"""
        thread.quit()
        thread.wait()

        progress_dialog.close()

        if file_path:
            # 下载成功
            MessageBox(
                _('下载完成'),
                _('更新文件已下载到:\n{}\n\n请手动安装更新。').format(file_path),
                self.window()
            )
        else:
            # 下载被取消
            InfoBar.info(
                title=_('下载已取消'),
                content=_('更新下载已取消'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        # 清理引用
        self.download_thread = None
        self.download_worker = None

    def on_download_error(self, error_msg, progress_dialog, thread):
        """下载出错的回调"""
        thread.quit()
        thread.wait()

        progress_dialog.set_error(error_msg)

        # 清理引用
        self.download_thread = None
        self.download_worker = None


class MainWindow(FluentWindow):
    def __init__(self, info: ProgramInfo, updater_object):
        super().__init__()

        self.info = info
        self.updater = updater_object

        self.setWindowIcon(QIcon(get_path("icon.ico")))

        self.message_capture_interface = MessageCaptureInterface(self, 0)
        self.translation_service_interface = TranslationServiceInterface(self)
        self.message_presentation_interface = MessagePresentationInterface(self)
        self.message_send_interface = MessageSendInterface(self, 0)
        self.glossary_interface = GlossaryInterface(self)
        self.start_interface = StartInterface(self)
        self.about_interface = AboutInterface(self)
        self.setting_interface = SettingInterface(self)

        # 连接服务类型改变信号
        self.translation_service_interface.service_type_changed.connect(
            self.message_capture_interface.update_service_type
        )
        # 当复选框未启用时，玩家消息服务也控制发送消息界面
        self.translation_service_interface.service_type_changed.connect(
            self.on_player_service_type_changed
        )
        self.translation_service_interface.send_service_type_changed.connect(
            self.message_send_interface.update_service_type
        )

        # 创建独立的加载状态和线程
        self.player_language_loading = False
        self.send_language_loading = False
        self.player_language_loader_thread = None
        self.send_language_loader_thread = None

        # 监听所有服务的传统翻译服务变化
        self.connect_traditional_service_signals()

        self.init_navigation()
        self.init_window()

    def on_player_service_type_changed(self, service_type):
        """当玩家消息服务类型改变时，检查是否需要同步更新发送消息界面"""
        if not self.translation_service_interface.independent_service_check.isChecked():
            # 如果未启用独立设置，则同步更新发送消息界面
            self.message_send_interface.update_service_type(service_type)

    def connect_traditional_service_signals(self):
        """连接所有传统翻译服务变化信号"""
        # 监听玩家消息服务
        if hasattr(self.translation_service_interface, 'player_service_widget'):
            player_widget = self.translation_service_interface.player_service_widget
            if hasattr(player_widget, 'stacked_widget'):
                for i in range(player_widget.stacked_widget.count()):
                    widget = player_widget.stacked_widget.widget(i)
                    if hasattr(widget, 'traditional_service_combo'):
                        widget.traditional_service_combo.currentTextChanged.connect(
                            lambda text: self.on_traditional_service_changed(text, "player")
                        )

        # 连接独立设置改变信号，以便在创建发送服务时连接信号
        self.translation_service_interface.independent_service_check.toggled.connect(
            self.on_independent_service_toggled
        )

    def on_independent_service_toggled(self, checked):
        """当独立设置改变时"""
        if checked and self.translation_service_interface.send_service_widget:
            # 连接发送消息服务的信号
            send_widget = self.translation_service_interface.send_service_widget
            if hasattr(send_widget, 'stacked_widget'):
                for i in range(send_widget.stacked_widget.count()):
                    widget = send_widget.stacked_widget.widget(i)
                    if hasattr(widget, 'traditional_service_combo'):
                        # 先断开可能存在的连接，避免重复
                        try:
                            widget.traditional_service_combo.currentTextChanged.disconnect()
                        except:
                            pass
                        # 连接新信号
                        widget.traditional_service_combo.currentTextChanged.connect(
                            lambda text: self.on_traditional_service_changed(text, "send")
                        )
        else:
            # 如果取消勾选，同步当前玩家服务的设置到发送消息界面
            player_service_type = self.translation_service_interface.get_current_service_type("player")
            self.message_send_interface.update_service_type(player_service_type)

            # 如果是传统翻译服务，还需要同步语言列表
            if player_service_type == 1:
                player_service = self.translation_service_interface.get_current_service("player")
                if player_service:
                    # 触发语言加载以同步到发送消息界面
                    self.on_traditional_service_changed(player_service, "player")

    def init_window(self):
        self.resize(900, 700)
        self.setWindowTitle(f"Modless Chat Trans {self.info.version}")
        logger.info("Main Window initialized successfully")

    def init_navigation(self):
        # 添加主要功能界面
        self.addSubInterface(self.message_capture_interface, FIF.MESSAGE, _('消息捕获'))
        self.addSubInterface(self.translation_service_interface, FIF.LANGUAGE, _('翻译服务'))
        self.addSubInterface(self.message_presentation_interface, FIF.VIEW, _('翻译结果显示'))
        self.addSubInterface(self.message_send_interface, FIF.SEND, _('发送消息'))
        self.addSubInterface(self.glossary_interface, FIF.DICTIONARY, _('术语表'))
        self.addSubInterface(self.start_interface, FIF.POWER_BUTTON, _('启动'))

        # 添加底部设置界面
        self.addSubInterface(self.about_interface, FluentIcon.INFO, _('关于'), NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.setting_interface, FIF.SETTING, _('设置'), NavigationItemPosition.BOTTOM)

    def on_traditional_service_changed(self, service_name, service_id):
        """统一处理传统翻译服务变更"""
        if not service_name:
            return

        # 检查对应的加载状态
        if service_id == "player" and self.player_language_loading:
            return
        elif service_id == "send" and self.send_language_loading:
            return

        # 标记正在加载
        if service_id == "player":
            self.player_language_loading = True
        else:
            self.send_language_loading = True

        # 显示加载动画
        self.translation_service_interface.show_loading_spinner(True, service_id)

        # 清空对应界面的语言列表
        if service_id == "player":
            self.message_capture_interface.src_lang_combo.clear()
            self.message_capture_interface.tgt_lang_combo.clear()
            # 如果未启用独立设置，也清空发送消息界面
            if not self.translation_service_interface.independent_service_check.isChecked():
                self.message_send_interface.src_lang_combo.clear()
                self.message_send_interface.tgt_lang_combo.clear()
        else:
            self.message_send_interface.src_lang_combo.clear()
            self.message_send_interface.tgt_lang_combo.clear()

        # 创建并启动对应的线程
        language_loader_thread = LanguageLoaderThread(service_name)
        language_loader_thread.languages_loaded.connect(
            lambda langs: self.on_languages_loaded(langs, service_id)
        )
        language_loader_thread.error_occurred.connect(
            lambda error: self.on_language_error(error, service_id)
        )

        if service_id == "player":
            self.player_language_loader_thread = language_loader_thread
        else:
            self.send_language_loader_thread = language_loader_thread

        language_loader_thread.start()

    def on_languages_loaded(self, langs, service_id):
        """语言列表加载完成，更新对应界面"""
        if service_id == "player":
            # 更新 MessageCaptureInterface
            self.message_capture_interface.src_lang_combo.addItems(langs)
            self.message_capture_interface.tgt_lang_combo.addItems(l for l in langs if l != 'auto')

            # 如果未启用独立设置，也更新 MessageSendInterface
            if not self.translation_service_interface.independent_service_check.isChecked():
                self.message_send_interface.src_lang_combo.addItems(langs)
                self.message_send_interface.tgt_lang_combo.addItems(l for l in langs if l != 'auto')
        else:
            # 更新 MessageSendInterface（仅在独立设置时）
            self.message_send_interface.src_lang_combo.addItems(langs)
            self.message_send_interface.tgt_lang_combo.addItems(l for l in langs if l != 'auto')

        # 隐藏加载动画
        self.translation_service_interface.show_loading_spinner(False, service_id)

        # 重置对应的加载标志
        if service_id == "player":
            self.player_language_loading = False
        else:
            self.send_language_loading = False

    def on_language_error(self, error_msg, service_id):
        """语言列表加载失败"""
        logger.error(f"Failed to get supported languages ({service_id}): {error_msg}")
        self.translation_service_interface.show_loading_spinner(False, service_id)

        if service_id == "player":
            self.player_language_loading = False
        else:
            self.send_language_loading = False

        # 添加错误提示信息
        InfoBar.error(
            title=_('语言加载错误'),
            content=_("获取支持语言失败 ({service_id}): {error_msg}").format(service_id=service_id,
                                                                             error_msg=error_msg),
            orient=Qt.Orientation.Vertical,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=-1,
            parent=self
        )
