# -*- coding: utf-8 -*-
# dashboard_module.py
# 仪表盘模块 (Phase 20 Step 3 Fixed: Real-time Priority & Status Monitor)
# 职责：实时波形显示、系统状态概览、通道配置、灵敏度控制
# 修复：
# 1. 解决真实数据无法打断演示模式的问题（增加 blockSignals 强制切换）
# 2. 新增数据流采样率监控 (Hz)，帮助判断是否有数据进入
# 3. 消除连接按钮歧义

import numpy as np
import time
from collections import deque

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout, QCheckBox, QLabel
)

# --- Fluent Widgets ---
from qfluentwidgets import (
    CardWidget, SimpleCardWidget, ElevatedCardWidget,
    PrimaryPushButton, PushButton, ComboBox, ProgressBar, ToggleButton, LineEdit,
    DoubleSpinBox, SpinBox,
    TitleLabel, SubtitleLabel, CaptionLabel, StrongBodyLabel, BodyLabel,
    InfoBadge, InfoLevel, IconWidget, FluentIcon as FIF,
    setTheme, Theme
)

# --- Plotting Libs ---
try:
    import pyqtgraph as pg

    # 适配 Light 主题配置
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    pg.setConfigOption('antialias', True)
except ImportError:
    pg = None
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure


class DashboardPage(QWidget):
    """主界面 (Dashboard) - 实时数据优先版"""

    # --- 信号定义 ---
    info = pyqtSignal(str)
    request_start_trial = pyqtSignal()
    request_abort_trial = pyqtSignal()
    quick_send = pyqtSignal(str)
    request_connect_device = pyqtSignal()
    request_disconnect_device = pyqtSignal()

    def __init__(self, username: str = "用户"):
        super().__init__()
        self.username = username

        # --- 基础配置 ---
        self.fs = 250  # 默认采样率
        self.win_sec = 5.0  # 默认显示 5 秒
        self.n_channels = 8  # 默认通道数
        self.scale_factor = 50.0  # 默认通道间距 (Sensitivity)

        # 动态计算 buffer 长度
        self._update_buf_len()

        # --- 通道可视化配置 ---
        self.default_map = "Fz, C3, Cz, C4, Pz, O1, O2, P3"
        self.ch_names = [x.strip() for x in self.default_map.split(',')]
        while len(self.ch_names) < self.n_channels:
            self.ch_names.append(f"Ch{len(self.ch_names) + 1}")

        self.ch_vis = [True] * self.n_channels

        # 初始化缓冲区
        self._reset_buffers()

        # 内部引用
        self._task_module = None
        self._eeg_module = None
        self._device_page = None

        # 状态标志
        self.demo_eeg = False
        self.packet_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0

        self._init_ui()
        self._init_chart()

        # 绘图定时器 (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

        # 演示数据定时器
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self._demo_step)
        self.demo_phase = 0.0

        # FPS 统计定时器 (1s)
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_fps_stat)
        self.fps_timer.start(1000)

    def _update_buf_len(self):
        self.buf_len = int(self.fs * self.win_sec)

    def _reset_buffers(self):
        self.buffers = [deque([0.0] * self.buf_len, maxlen=self.buf_len) for _ in range(self.n_channels)]

    def _init_ui(self):
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(20, 20, 20, 20)
        self.v_layout.setSpacing(16)

        # =================================================
        # 1. Header Card
        # =================================================
        self.header_card = SimpleCardWidget(self)
        self.header_card.setFixedHeight(88)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(24, 0, 24, 0)
        h_layout.setSpacing(16)

        icon = IconWidget(FIF.PEOPLE)
        icon.setFixedSize(40, 40)

        text_l = QVBoxLayout()
        text_l.setAlignment(Qt.AlignVCenter)
        title = TitleLabel(f"欢迎回来，{self.username}", self)
        subtitle = CaptionLabel("NeuroPilot 脑机接口康复系统 - 就绪", self)
        subtitle.setTextColor(QColor(96, 96, 96), QColor(200, 200, 200))
        text_l.addWidget(title)
        text_l.addWidget(subtitle)

        # 状态徽章
        self.badge_task = InfoBadge.info("任务: 未选择")
        self.badge_stage = InfoBadge.attension("环节: 待机")
        self.badge_device = InfoBadge.error("外设: 未连接")

        h_layout.addWidget(icon)
        h_layout.addLayout(text_l)
        h_layout.addStretch(1)
        h_layout.addWidget(self.badge_task)
        h_layout.addWidget(self.badge_stage)
        h_layout.addWidget(self.badge_device)

        # =================================================
        # 2. Chart Card (Elevated)
        # =================================================
        self.chart_card = ElevatedCardWidget(self)
        self.chart_card.setBorderRadius(10)
        chart_l = QVBoxLayout(self.chart_card)
        chart_l.setContentsMargins(16, 12, 16, 16)

        # Header
        chart_header = QHBoxLayout()
        chart_title = SubtitleLabel("实时脑电监测", self)

        # 数据流状态指示器
        self.lbl_fps = CaptionLabel("数据流: 等待EEG设备连接", self)
        self.lbl_fps.setTextColor(QColor(150, 150, 150), QColor(150, 150, 150))

        self.btn_demo = ToggleButton(self)
        self.btn_demo.setText("演示模式")
        self.btn_demo.toggled.connect(self._toggle_demo_ui)

        chart_header.addWidget(chart_title)
        chart_header.addSpacing(16)
        chart_header.addWidget(self.lbl_fps)
        chart_header.addStretch(1)
        chart_header.addWidget(self.btn_demo)

        # Container
        self.plot_container = QWidget()

        chart_l.addLayout(chart_header)
        chart_l.addWidget(self.plot_container, 1)

        # =================================================
        # 3. Visual Config Card
        # =================================================
        self.vis_card = SimpleCardWidget(self)
        vis_l = QVBoxLayout(self.vis_card)
        vis_l.setContentsMargins(24, 16, 24, 16)
        vis_l.setSpacing(12)

        vis_l.addWidget(StrongBodyLabel("通道与显示配置", self))

        # Row 1: Name Mapping & Scaling
        row_cfg = QHBoxLayout()

        row_cfg.addWidget(CaptionLabel("通道映射:", self))
        self.ed_ch_map = LineEdit(self)
        self.ed_ch_map.setText(self.default_map)
        self.ed_ch_map.setPlaceholderText("Fz, C3, Cz...")
        self.ed_ch_map.textChanged.connect(self._update_ch_names)
        row_cfg.addWidget(self.ed_ch_map, 2)

        row_cfg.addSpacing(20)

        row_cfg.addWidget(CaptionLabel("垂直缩放 (uV):", self))
        self.spin_scale = DoubleSpinBox(self)
        self.spin_scale.setRange(0.1, 100000.0)  # 扩大范围以适应不同设备
        self.spin_scale.setValue(50.0)
        self.spin_scale.setSingleStep(10.0)
        self.spin_scale.valueChanged.connect(self._update_scale)
        row_cfg.addWidget(self.spin_scale)

        row_cfg.addWidget(CaptionLabel("时间窗口 (s):", self))
        self.spin_win = DoubleSpinBox(self)
        self.spin_win.setRange(1.0, 30.0)
        self.spin_win.setValue(5.0)
        self.spin_win.setSingleStep(1.0)
        self.spin_win.valueChanged.connect(self._update_time_window)
        row_cfg.addWidget(self.spin_win)

        vis_l.addLayout(row_cfg)

        # Row 2: Visibility Toggles
        self.chk_container = QWidget()
        self.chk_layout = QGridLayout(self.chk_container)
        self.chk_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_list = []

        self._refresh_checkboxes()

        vis_l.addWidget(CaptionLabel("通道筛选:", self))
        vis_l.addWidget(self.chk_container)

        # =================================================
        # 3.5. Spectrum Card (NEW)
        # =================================================
        self.spectrum_card = ElevatedCardWidget(self)
        self.spectrum_card.setBorderRadius(10)
        spec_l = QVBoxLayout(self.spectrum_card)
        spec_l.setContentsMargins(16, 12, 16, 16)

        # Header
        spec_header = QHBoxLayout()
        spec_title = SubtitleLabel("频谱分析 (FFT)", self)
        
        # 频率范围控制
        self.lbl_freq_range = CaptionLabel("频率范围: 0-50 Hz", self)
        self.lbl_freq_range.setTextColor(QColor(100, 100, 100), QColor(150, 150, 150))
        
        spec_header.addWidget(spec_title)
        spec_header.addSpacing(16)
        spec_header.addWidget(self.lbl_freq_range)
        spec_header.addStretch(1)

        # 频率范围滑块
        freq_ctrl = QHBoxLayout()
        freq_ctrl.addWidget(CaptionLabel("最大频率:", self))
        self.spin_max_freq = SpinBox(self)
        self.spin_max_freq.setRange(10, 125)
        self.spin_max_freq.setValue(50)
        self.spin_max_freq.setSuffix(" Hz")
        self.spin_max_freq.valueChanged.connect(self._update_freq_range)
        freq_ctrl.addWidget(self.spin_max_freq)
        freq_ctrl.addStretch(1)

        # Spectrum plot container
        self.spectrum_container = QWidget()
        self.spectrum_container.setMinimumHeight(250)

        spec_l.addLayout(spec_header)
        spec_l.addLayout(freq_ctrl)
        spec_l.addWidget(self.spectrum_container, 1)

        # =================================================
        # 4. Control Card
        # =================================================
        self.control_card = CardWidget(self)
        self.control_card.setFixedHeight(120)
        ctrl_l = QHBoxLayout(self.control_card)
        ctrl_l.setContentsMargins(24, 16, 24, 16)
        ctrl_l.setSpacing(24)

        # A. 任务
        task_l = QVBoxLayout()
        task_l.setSpacing(8)
        task_title = StrongBodyLabel("任务控制", self)
        self.cmb_task = ComboBox(self)
        self.cmb_task.addItems(["左手抓握", "右手抓握"])
        self.cmb_task.setFixedWidth(160)

        btn_box = QHBoxLayout()
        self.btn_start = PrimaryPushButton(FIF.CARE_RIGHT_SOLID, "开始", self)
        self.btn_stop = PushButton(FIF.PAUSE, "中止", self)
        self.btn_start.setFixedWidth(75)
        self.btn_stop.setFixedWidth(75)
        self.btn_start.clicked.connect(self._start_clicked)
        self.btn_stop.clicked.connect(self._stop_clicked)
        btn_box.addWidget(self.btn_start)
        btn_box.addWidget(self.btn_stop)

        task_l.addWidget(task_title)
        task_l.addWidget(self.cmb_task)
        task_l.addLayout(btn_box)

        # B. 进度
        prog_l = QVBoxLayout()
        prog_l.setSpacing(8)
        prog_title = StrongBodyLabel("当前环节进度", self)
        self.progress = ProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(280)
        self.lab_result = CaptionLabel("上次预测: —", self)

        prog_l.addWidget(prog_title)
        prog_l.addWidget(self.progress)
        prog_l.addWidget(self.lab_result)

        # C. 外设
        dev_l = QVBoxLayout()
        dev_l.setSpacing(8)
        # [修改] 重命名为外设连接，避免用户误以为是 EEG 连接
        dev_title = StrongBodyLabel("外设/机械手连接", self)

        dev_r1 = QHBoxLayout()
        self.btn_conn = PushButton(FIF.IOT, "连接外设", self)
        self.btn_disc = PushButton(FIF.CANCEL, "断开外设", self)
        dev_r1.addWidget(self.btn_conn)
        dev_r1.addWidget(self.btn_disc)

        dev_r2 = QHBoxLayout()
        self.btn_L = PushButton("发左(L)", self)
        self.btn_R = PushButton("发右(R)", self)
        dev_r2.addWidget(self.btn_L)
        dev_r2.addWidget(self.btn_R)

        self.btn_conn.clicked.connect(lambda: self.request_connect_device.emit())
        self.btn_disc.clicked.connect(lambda: self.request_disconnect_device.emit())
        self.btn_L.clicked.connect(lambda: self._quick("left"))
        self.btn_R.clicked.connect(lambda: self._quick("right"))

        dev_l.addWidget(dev_title)
        dev_l.addLayout(dev_r1)
        dev_l.addLayout(dev_r2)

        ctrl_l.addLayout(task_l)
        line1 = QFrame()
        line1.setFrameShape(QFrame.VLine)
        line1.setStyleSheet("color: #E5E5E5;")
        ctrl_l.addWidget(line1)

        ctrl_l.addLayout(prog_l)
        line2 = QFrame()
        line2.setFrameShape(QFrame.VLine)
        line2.setStyleSheet("color: #E5E5E5;")
        ctrl_l.addWidget(line2)

        ctrl_l.addLayout(dev_l)
        ctrl_l.addStretch(1)

        self.v_layout.addWidget(self.header_card)
        self.v_layout.addWidget(self.chart_card, 1)
        self.v_layout.addWidget(self.spectrum_card, 1)  # New spectrum card
        self.v_layout.addWidget(self.vis_card)
        self.v_layout.addWidget(self.control_card)

    def _init_chart(self):
        layout = QVBoxLayout(self.plot_container)
        layout.setContentsMargins(0, 0, 0, 0)

        if pg:
            self.pg_plot = pg.PlotWidget()
            self.pg_plot.setBackground('#FFFFFF')
            self.pg_plot.showGrid(x=True, y=True, alpha=0.15)
            self.pg_plot.getViewBox().setBorder(None)
            self.pg_plot.setMouseEnabled(x=True, y=True)
            self.pg_plot.enableAutoRange(enable=False)

            self.pg_plot.setLabel('bottom', 'Time (s)', color='#666666')

            layout.addWidget(self.pg_plot)
            self.pg_curves = []
            self._recreate_curves()
        else:
            self.pg_plot = None
            self.fig = Figure(figsize=(8, 3), tight_layout=True)
            self.fig.patch.set_facecolor('#FFFFFF')
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas)
            self.ax = self.fig.gca()
            self.lines = []
            self._recreate_lines_mpl()

        # Initialize spectrum plot
        self._init_spectrum_chart()

    def _init_spectrum_chart(self):
        """初始化频谱图"""
        layout = QVBoxLayout(self.spectrum_container)
        layout.setContentsMargins(0, 0, 0, 0)

        if pg:
            self.pg_spectrum = pg.PlotWidget()
            self.pg_spectrum.setBackground('#FFFFFF')
            self.pg_spectrum.showGrid(x=True, y=True, alpha=0.15)
            self.pg_spectrum.getViewBox().setBorder(None)
            self.pg_spectrum.setLabel('bottom', 'Frequency (Hz)', color='#666666')
            self.pg_spectrum.setLabel('left', 'Power (uV²/Hz)', color='#666666')
            self.pg_spectrum.setLogMode(x=False, y=True)  # 对数Y轴

            layout.addWidget(self.pg_spectrum)
            self.pg_spectrum_curves = []
            self._recreate_spectrum_curves()
        else:
            self.pg_spectrum = None
            self.spec_fig = Figure(figsize=(8, 3), tight_layout=True)
            self.spec_fig.patch.set_facecolor('#FFFFFF')
            self.spec_canvas = FigureCanvas(self.spec_fig)
            layout.addWidget(self.spec_canvas)
            self.spec_ax = self.spec_fig.gca()
            self.spec_lines = []
            self._recreate_spectrum_lines_mpl()

    def _recreate_spectrum_curves(self):
        """创建频谱曲线（pyqtgraph）"""
        if not pg: return
        self.pg_spectrum.clear()
        self.pg_spectrum_curves = []
        colors = ['#2196F3', '#F44336', '#4CAF50', '#FF9800', '#9C27B0', '#00BCD4', '#607D8B', '#E91E63']
        for i in range(self.n_channels):
            pen = pg.mkPen(color=colors[i % len(colors)], width=1.5)
            curve = self.pg_spectrum.plot(pen=pen)
            self.pg_spectrum_curves.append(curve)

    def _recreate_spectrum_lines_mpl(self):
        """创建频谱曲线（matplotlib）"""
        if pg: return
        self.spec_ax.clear()
        self.spec_lines = []
        for i in range(self.n_channels):
            line, = self.spec_ax.plot([], [], linewidth=1.5, label=self.ch_names[i])
            self.spec_lines.append(line)
        self.spec_ax.set_xlabel("Frequency (Hz)")
        self.spec_ax.set_ylabel("Power (uV²/Hz)")
        self.spec_ax.set_yscale('log')
        self.spec_ax.grid(True, alpha=0.2)
        self.spec_ax.legend(loc='upper right', fontsize=8)

    def _recreate_curves(self):
        if not pg: return
        self.pg_plot.clear()
        self.pg_curves = []
        colors = ['#2196F3', '#F44336', '#4CAF50', '#FF9800', '#9C27B0', '#00BCD4', '#607D8B', '#E91E63']
        for i in range(self.n_channels):
            pen = pg.mkPen(color=colors[i % len(colors)], width=1.2)
            curve = self.pg_plot.plot(pen=pen)
            self.pg_curves.append(curve)

    def _recreate_lines_mpl(self):
        if pg: return
        self.ax.clear()
        self.lines = []
        t = np.linspace(-self.win_sec, 0, self.buf_len)
        for i in range(self.n_channels):
            line, = self.ax.plot(t, np.zeros_like(t), linewidth=1)
            self.lines.append(line)
        self.ax.set_xlabel("Time (s)")
        self.ax.grid(True, alpha=0.2)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

    def _refresh_checkboxes(self):
        for i in reversed(range(self.chk_layout.count())):
            self.chk_layout.itemAt(i).widget().setParent(None)
        self.chk_list = []

        for i in range(self.n_channels):
            name = self.ch_names[i] if i < len(self.ch_names) else f"Ch{i + 1}"
            chk = QCheckBox(name)
            chk.setChecked(True)
            chk.stateChanged.connect(self._update_visibility)
            self.chk_layout.addWidget(chk, 0 if i < 4 else 1, i % 4)
            self.chk_list.append(chk)

    # ======================================================
    # Data Ingestion (Fix: Robust Real-time Switch)
    # ======================================================

    def feed_eeg_samples(self, values):
        """
        接收 EEG 数据块。
        """
        # [调试信息] 记录数据接收情况
        # print(f"[Dashboard] 接收到数据: {type(values)}, shape: {getattr(values, 'shape', 'N/A')}")

        # [关键修复] 检测到真实数据时，强制关闭演示模式
        # 使用 blockSignals 防止信号递归调用，确保状态被原子性地重置
        if self.demo_eeg:
            print("[Dashboard] 检测到真实数据，自动关闭演示模式")
            self.demo_eeg = False
            self.demo_timer.stop()

            self.btn_demo.blockSignals(True)
            self.btn_demo.setChecked(False)
            self.btn_demo.setText("演示模式")
            self.btn_demo.blockSignals(False)

            # 清空缓冲区中的演示正弦波，避免与真实数据混合
            self._reset_buffers()
            self.info.emit("切换到实时数据模式")

        # 数据校验与格式转换
        if not isinstance(values, np.ndarray):
            values = np.array(values)
        if values.ndim == 1:
            values = values.reshape(1, -1)

        n_samples, n_ch_in = values.shape

        # 统计数据包用于计算 FPS
        self.packet_count += n_samples

        # 写入缓冲区
        limit = min(self.n_channels, n_ch_in)
        for i in range(limit):
            self.buffers[i].extend(values[:, i])

    def _update_fps_stat(self):
        """每秒更新一次数据流状态标签"""
        now = time.time()
        # 计算 SPS (Samples Per Second)
        # 简单估算：packet_count 在这里代表样本总点数/通道数?
        # feed_eeg_samples 中 packet_count += n_samples (行数)
        # 所以 packet_count 就是过去 1s 内的采样点数

        self.current_fps = self.packet_count
        self.packet_count = 0

        if self.demo_eeg:
            status_text = f"数据流: 演示模式 ({self.fs} Hz)"
            color = "#FF9800"  # Orange
        elif self.current_fps > 0:
            status_text = f"数据流: 实时 ({self.current_fps} Hz)"
            color = "#4CAF50"  # Green
        else:
            status_text = "数据流: 0 Hz (未连接或无数据)"
            color = "#9E9E9E"  # Grey

        self.lbl_fps.setText(status_text)
        self.lbl_fps.setTextColor(QColor(color), QColor(color))

    # ======================================================
    # Plotting
    # ======================================================

    def _tick(self):
        """定时刷新绘图"""
        if not self.isVisible(): return

        visible_indices = [i for i, vis in enumerate(self.ch_vis) if vis]

        if pg:
            t = np.linspace(-self.win_sec, 0, self.buf_len)
            ticks = []

            for i, curve in enumerate(self.pg_curves):
                if i in visible_indices:
                    stack_idx = visible_indices.index(i)
                    offset = stack_idx * self.scale_factor

                    data = np.array(self.buffers[i])

                    # 去直流 (防止漂移)
                    if len(data) > 0:
                        mean_val = np.mean(data)
                        if not np.isnan(mean_val) and not np.isinf(mean_val):
                            data = data - mean_val

                    # 补齐长度
                    if len(data) < self.buf_len:
                        pad = np.zeros(self.buf_len - len(data))
                        data = np.concatenate([pad, data])

                    # 安全检查：防止 NaN 导致绘图崩溃
                    data = np.nan_to_num(data)

                    curve.setData(t, data + offset)
                    curve.setVisible(True)
                    ticks.append((offset, self.ch_names[i]))
                else:
                    curve.setData([], [])
                    curve.setVisible(False)

            # 更新 Y 轴范围和标签
            if ticks:
                min_y = ticks[0][0] - self.scale_factor
                max_y = ticks[-1][0] + self.scale_factor
                self.pg_plot.setYRange(min_y, max_y, padding=0.1)
                self.pg_plot.getPlotItem().getAxis('left').setTicks([ticks])

        else:
            # Matplotlib Fallback
            t = np.linspace(-self.win_sec, 0, self.buf_len)
            yticks = []
            yticklabels = []

            for i, line in enumerate(self.lines):
                if i in visible_indices:
                    stack_idx = visible_indices.index(i)
                    offset = stack_idx * self.scale_factor

                    data = np.array(self.buffers[i])
                    if len(data) > 0:
                        mean_val = np.mean(data)
                        if not np.isnan(mean_val):
                            data = data - mean_val
                    if len(data) < self.buf_len:
                        data = np.pad(data, (self.buf_len - len(data), 0), mode='edge')

                    line.set_data(t, data + offset)
                    line.set_visible(True)

                    yticks.append(offset)
                    yticklabels.append(self.ch_names[i])
                else:
                    line.set_visible(False)

            if yticks:
                self.ax.set_yticks(yticks)
                self.ax.set_yticklabels(yticklabels)
                self.ax.set_ylim(yticks[0] - self.scale_factor, yticks[-1] + self.scale_factor)

            self.canvas.draw_idle()
        
        # 更新频谱图
        self._update_spectrum()

    def _compute_spectrum(self, channel_idx):
        """计算单个通道的功率谱密度"""
        data = np.array(self.buffers[channel_idx])
        
        if len(data) < 64:  # 数据太少，不计算
            return None, None
        
        # 去直流
        data = data - np.mean(data)
        
        # 应用汉宁窗减少频谱泄露
        window = np.hanning(len(data))
        data_windowed = data * window
        
        # FFT（实频FFT）
        fft_result = np.fft.rfft(data_windowed)
        
        # 功率谱密度 (PSD)
        psd = (np.abs(fft_result) ** 2) / len(data)
        
        # 频率轴
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.fs)
        
        return freqs, psd

    def _update_spectrum(self):
        """更新频谱图显示"""
        if not self.isVisible(): return
        
        max_freq = self.spin_max_freq.value()
        visible_indices = [i for i, vis in enumerate(self.ch_vis) if vis]
        
        if pg:
            for i, curve in enumerate(self.pg_spectrum_curves):
                if i in visible_indices:
                    freqs, psd = self._compute_spectrum(i)
                    if freqs is not None and psd is not None:
                        # 只显示指定频率范围
                        mask = freqs <= max_freq
                        freqs_show = freqs[mask]
                        psd_show = psd[mask]
                        
                        # 避免对数坐标轴问题：添加小值
                        psd_show = np.maximum(psd_show, 1e-10)
                        
                        curve.setData(freqs_show, psd_show)
                        curve.setVisible(True)
                    else:
                        curve.setVisible(False)
                else:
                    curve.setData([], [])
                    curve.setVisible(False)
            
            # 设置X轴范围
            self.pg_spectrum.setXRange(0, max_freq, padding=0.02)
        
        else:
            # Matplotlib fallback
            for i, line in enumerate(self.spec_lines):
                if i in visible_indices:
                    freqs, psd = self._compute_spectrum(i)
                    if freqs is not None and psd is not None:
                        mask = freqs <= max_freq
                        freqs_show = freqs[mask]
                        psd_show = psd[mask]
                        psd_show = np.maximum(psd_show, 1e-10)
                        
                        line.set_data(freqs_show, psd_show)
                        line.set_visible(True)
                    else:
                        line.set_visible(False)
                else:
                    line.set_visible(False)
            
            self.spec_ax.set_xlim(0, max_freq)
            self.spec_ax.relim()
            self.spec_ax.autoscale_view(scalex=False, scaley=True)
            self.spec_canvas.draw_idle()

    # ======================================================
    # Logic & Signals
    # ======================================================

    def _toggle_demo_ui(self, on: bool):
        """UI 按钮触发的演示模式切换"""
        self.demo_eeg = on
        if on:
            self.demo_phase = 0.0
            self.demo_timer.start(20)
            self.btn_demo.setText("停止演示")
            # 开启演示时，重置 buffer 以展示清晰的正弦波
            self._reset_buffers()
        else:
            self.demo_timer.stop()
            self.btn_demo.setText("演示模式")
            # 关闭演示时，也重置 buffer，避免正弦波残留
            self._reset_buffers()

    def _demo_step(self):
        t = self.demo_phase
        vals = []
        for i in range(self.n_channels):
            # 振幅根据 Scale 动态调整，保证演示效果总是可见的
            amp = self.scale_factor * 0.4
            base = np.sin(2 * np.pi * 10 * t) * amp
            noise = np.random.randn() * (amp * 0.1)
            vals.append(base + noise)

        for i in range(self.n_channels):
            self.buffers[i].extend([vals[i]])

        self.demo_phase += 1.0 / self.fs

    # --- 其他配置函数 ---
    def _update_scale(self):
        self.scale_factor = self.spin_scale.value()

    def _update_time_window(self):
        self.win_sec = self.spin_win.value()
        self._update_buf_len()
        self._reset_buffers()
        if not pg: self._recreate_lines_mpl()

    def _update_ch_names(self):
        text = self.ed_ch_map.text()
        names = [x.strip() for x in text.split(',') if x.strip()]
        while len(names) < self.n_channels:
            names.append(f"Ch{len(names) + 1}")
        self.ch_names = names[:self.n_channels]

        for i, chk in enumerate(self.chk_list):
            if i < len(self.ch_names):
                chk.setText(self.ch_names[i])

    def _update_visibility(self):
        for i, chk in enumerate(self.chk_list):
            if i < len(self.ch_vis):
                self.ch_vis[i] = chk.isChecked()

    def _update_freq_range(self):
        """更新频率范围显示"""
        max_freq = self.spin_max_freq.value()
        self.lbl_freq_range.setText(f"频率范围: 0-{max_freq} Hz")

    # --- 绑定函数 (保持原样) ---
    def bind_eeg_module(self, eeg_page):
        self._eeg_module = eeg_page
        eeg_page.raw_data_ready.connect(self.feed_eeg_samples)
        eeg_page.trial_result.connect(self.on_trial_result)
        eeg_page.info.connect(lambda s: self.info.emit(s))

    def bind_task_module(self, task_page):
        self._task_module = task_page
        self.cmb_task.currentIndexChanged.connect(lambda idx: self._sync_task(idx))
        task_page.stage.connect(self.on_stage_changed)
        task_page.info.connect(lambda s: self.info.emit(s))

    def bind_device_control(self, device_page):
        self._device_page = device_page
        self.request_connect_device.connect(lambda: self._safe_click(getattr(device_page, "btn_connect", None)))
        self.request_disconnect_device.connect(lambda: self._safe_click(getattr(device_page, "btn_disconnect", None)))
        self.quick_send.connect(lambda lab: self._quick_dev(device_page, lab))
        device_page.device_feedback.connect(self.on_device_feedback)
        device_page.send_result.connect(self.on_device_send_result)
        device_page.info.connect(lambda s: self.info.emit(s))

    def _sync_task(self, idx):
        if self._task_module and hasattr(self._task_module, "task"):
            self._task_module.task.setCurrentIndex(idx)
        name = "左手" if idx == 0 else "右手"
        self.badge_task.setText(f"任务: {name}")

    def _start_clicked(self):
        if self._task_module and hasattr(self._task_module, "start_trial"):
            self._task_module.start_trial()
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def _stop_clicked(self):
        if self._task_module and hasattr(self._task_module, "abort_trial"):
            self._task_module.abort_trial()

    def _quick(self, label):
        self.quick_send.emit(label)

    def _quick_dev(self, page, label):
        if hasattr(page, "_send_cmd"):
            page._send_cmd(label)

    def _safe_click(self, btn):
        if btn: btn.click()

    # --- 状态更新 ---
    def on_stage_changed(self, stage: str, idx: int):
        self.badge_stage.setText(f"环节: {stage}")
        if stage == "运动想象":
            try:
                self.badge_stage.setLevel(InfoLevel.WARNING)
            except:
                pass
        elif stage == "休息":
            try:
                self.badge_stage.setLevel(InfoLevel.SUCCESS)
            except:
                pass

        progress = int((idx + 1) / 4.0 * 100)
        self.progress.setValue(progress)
        if stage in ["休息结束", "已中止"]:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def on_trial_result(self, pred, success):
        icon = "✅" if success else "❌"
        label = "左手" if pred == "left" else ("右手" if pred == "right" else "未知")
        self.lab_result.setText(f"上次预测: {label} {icon}")

    def on_device_send_result(self, ok, msg):
        self.badge_device.setText("发送成功" if ok else "发送失败")
        try:
            self.badge_device.setLevel(InfoLevel.SUCCESS if ok else InfoLevel.ERROR)
        except:
            pass

    def on_device_feedback(self, msg):
        self.badge_device.setText(f"反馈: {msg}")