#!/usr/bin/env python3
"""
FITS图像查看器
用于显示和分析FITS文件
"""

import os
import sys
import subprocess
import platform
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import logging
from pathlib import Path
from typing import Optional, Tuple, Callable
from diff_orb_integration import DiffOrbIntegration

# 添加项目根目录到路径以导入dss_cds_downloader
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cds_dss_download.dss_cds_downloader import download_dss_rot

# 尝试导入ASTAP处理器
try:
    from astap_processor import ASTAPProcessor
except ImportError:
    ASTAPProcessor = None

# 导入WCS检查器
try:
    from wcs_checker import WCSChecker
except ImportError:
    WCSChecker = None


class FitsImageViewer:
    """FITS图像查看器"""

    def __init__(self, parent_frame, config_manager=None, get_download_dir_callback: Optional[Callable] = None,
                 get_template_dir_callback: Optional[Callable] = None,
                 get_diff_output_dir_callback: Optional[Callable] = None,
                 get_url_selections_callback: Optional[Callable] = None):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.current_fits_data = None
        self.current_header = None
        self.current_file_path = None
        self.selected_file_path = None  # 当前选中但未显示的文件
        self.first_refresh_done = False  # 标记是否已进行首次刷新

        # 回调函数
        self.get_download_dir_callback = get_download_dir_callback
        self.get_template_dir_callback = get_template_dir_callback
        self.get_diff_output_dir_callback = get_diff_output_dir_callback
        self.get_url_selections_callback = get_url_selections_callback

        # 设置日志
        self.logger = logging.getLogger(__name__)

        # 初始化diff_orb集成（传入GUI回调）
        # 注意：此时log_callback还未定义，将在后面设置
        self.diff_orb = DiffOrbIntegration()

        # 初始化ASTAP处理器
        self.astap_processor = None
        if ASTAPProcessor:
            try:
                # 构建配置文件的绝对路径
                # 从gui目录向上一级到项目根目录
                current_dir = os.path.dirname(os.path.abspath(__file__))  # gui目录
                project_root = os.path.dirname(current_dir)  # 项目根目录
                config_path = os.path.join(project_root, "config", "url_config.json")

                self.astap_processor = ASTAPProcessor(config_path)
                self.logger.info("ASTAP处理器初始化成功")
            except Exception as e:
                self.logger.warning(f"ASTAP处理器初始化失败: {str(e)}")

        # 初始化WCS检查器
        self.wcs_checker = None
        if WCSChecker:
            try:
                self.wcs_checker = WCSChecker()
                self.logger.info("WCS检查器初始化成功")
            except Exception as e:
                self.logger.warning(f"WCS检查器初始化失败: {str(e)}")

        # 创建界面
        self._create_widgets()

        # 从配置文件加载批量处理参数到控件
        self._load_batch_settings()

        # 绑定控件变化事件，自动保存到配置文件
        self._bind_batch_settings_events()

        # 延迟执行首次刷新（确保界面完全创建后）
        self.parent_frame.after(100, self._first_time_refresh)
        
    def _create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建工具栏容器
        toolbar_container = ttk.Frame(main_frame)
        toolbar_container.pack(fill=tk.X, pady=(0, 5))

        # 第一行工具栏
        toolbar_frame1 = ttk.Frame(toolbar_container)
        toolbar_frame1.pack(fill=tk.X, pady=(0, 2))

        # 文件信息标签
        self.file_info_label = ttk.Label(toolbar_frame1, text="未选择文件")
        self.file_info_label.pack(side=tk.LEFT)

        # 显示图像按钮
        self.display_button = ttk.Button(toolbar_frame1, text="显示图像",
                                       command=self._display_selected_image, state="disabled")
        self.display_button.pack(side=tk.LEFT, padx=(10, 0))

        # 降噪方式选择框架
        noise_frame = ttk.Frame(toolbar_frame1)
        noise_frame.pack(side=tk.LEFT, padx=(5, 0))

        # 降噪方式标签
        ttk.Label(noise_frame, text="降噪方式:").pack(side=tk.LEFT)

        # 降噪方式复选框
        self.outlier_var = tk.BooleanVar(value=False)  # 默认不选中outlier
        self.hot_cold_var = tk.BooleanVar(value=False)  # 默认不选中hot_cold
        self.adaptive_median_var = tk.BooleanVar(value=True)  # 默认选中adaptive_median

        self.outlier_checkbox = ttk.Checkbutton(noise_frame, text="Outlier",
                                              variable=self.outlier_var)
        self.outlier_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        self.hot_cold_checkbox = ttk.Checkbutton(noise_frame, text="Hot/Cold",
                                               variable=self.hot_cold_var)
        self.hot_cold_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        self.adaptive_median_checkbox = ttk.Checkbutton(noise_frame, text="Adaptive Median",
                                                      variable=self.adaptive_median_var)
        self.adaptive_median_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        # 去除亮线选项
        self.remove_lines_var = tk.BooleanVar(value=True)  # 默认选中去除亮线
        self.remove_lines_checkbox = ttk.Checkbutton(noise_frame, text="去除亮线",
                                                     variable=self.remove_lines_var)
        self.remove_lines_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        # 图像统计信息标签（放在第一行右侧）
        self.stats_label = ttk.Label(toolbar_frame1, text="")
        self.stats_label.pack(side=tk.RIGHT)

        # 第二行工具栏
        toolbar_frame2 = ttk.Frame(toolbar_container)
        toolbar_frame2.pack(fill=tk.X, pady=(2, 0))

        # 对齐方式选择框架
        alignment_frame = ttk.Frame(toolbar_frame2)
        alignment_frame.pack(side=tk.LEFT, padx=(0, 0))

        # 对齐方式标签
        ttk.Label(alignment_frame, text="对齐方式:").pack(side=tk.LEFT)

        # 对齐方式单选框
        self.alignment_var = tk.StringVar(value="wcs")  # 默认选择wcs

        alignment_methods = [
            ("Rigid", "rigid", "刚体变换（平移+旋转）"),
            ("WCS", "wcs", "基于WCS信息对齐")
        ]

        for text, value, tooltip in alignment_methods:
            rb = ttk.Radiobutton(alignment_frame, text=text,
                               variable=self.alignment_var, value=value)
            rb.pack(side=tk.LEFT, padx=(5, 0))
            # 可以考虑添加tooltip功能

        # diff操作按钮
        self.diff_button = ttk.Button(toolbar_frame2, text="执行Diff",
                                    command=self._execute_diff, state="disabled")
        self.diff_button.pack(side=tk.LEFT, padx=(10, 0))

        # ASTAP处理按钮
        self.astap_button = ttk.Button(toolbar_frame2, text="执行ASTAP",
                                     command=self._execute_astap, state="disabled")
        self.astap_button.pack(side=tk.LEFT, padx=(5, 0))

        # diff进度标签（放在第二行右侧）
        self.diff_progress_label = ttk.Label(toolbar_frame2, text="", foreground="blue", font=("Arial", 9))
        self.diff_progress_label.pack(side=tk.RIGHT, padx=(10, 0))

        # 第三行工具栏
        toolbar_frame3 = ttk.Frame(toolbar_container)
        toolbar_frame3.pack(fill=tk.X, pady=(2, 0))

        # 快速模式开关
        self.fast_mode_var = tk.BooleanVar(value=True)  # 默认开启快速模式
        self.fast_mode_checkbox = ttk.Checkbutton(toolbar_frame3, text="快速模式（减少中间文件）",
                                                  variable=self.fast_mode_var)
        self.fast_mode_checkbox.pack(side=tk.LEFT, padx=(0, 0))

        # 拉伸方法选择
        ttk.Label(toolbar_frame3, text="拉伸方法:").pack(side=tk.LEFT, padx=(20, 2))

        self.stretch_method_var = tk.StringVar(value="percentile")  # 默认百分位数拉伸
        stretch_methods = [
            ("峰值", "peak"),
            ("百分位数", "percentile")
        ]
        for text, value in stretch_methods:
            rb = ttk.Radiobutton(toolbar_frame3, text=text,
                               variable=self.stretch_method_var, value=value)
            rb.pack(side=tk.LEFT, padx=(5, 0))

        # 百分位数输入框
        percentile_label = ttk.Label(toolbar_frame3, text="百分位:")
        percentile_label.pack(side=tk.LEFT, padx=(10, 2))

        self.percentile_var = tk.StringVar(value="99.95")  # 默认99.95%
        self.percentile_entry = ttk.Entry(toolbar_frame3, textvariable=self.percentile_var, width=6)
        self.percentile_entry.pack(side=tk.LEFT, padx=(0, 2))

        percentile_unit = ttk.Label(toolbar_frame3, text="%")
        percentile_unit.pack(side=tk.LEFT, padx=(0, 5))

        # 检测结果导航按钮
        ttk.Label(toolbar_frame3, text="  |  ").pack(side=tk.LEFT, padx=(10, 5))

        self.prev_cutout_button = ttk.Button(toolbar_frame3, text="◀ 上一组",
                                            command=self._show_previous_cutout, state="disabled")
        self.prev_cutout_button.pack(side=tk.LEFT, padx=(0, 5))

        self.cutout_count_label = ttk.Label(toolbar_frame3, text="0/0", foreground="blue")
        self.cutout_count_label.pack(side=tk.LEFT, padx=(0, 5))

        self.next_cutout_button = ttk.Button(toolbar_frame3, text="下一组 ▶",
                                            command=self._show_next_cutout, state="disabled")
        self.next_cutout_button.pack(side=tk.LEFT, padx=(0, 5))

        # 检查DSS按钮
        self.check_dss_button = ttk.Button(toolbar_frame3, text="检查DSS",
                                          command=self._check_dss, state="disabled")
        self.check_dss_button.pack(side=tk.LEFT, padx=(0, 0))

        # 坐标显示区域（第四行工具栏）
        toolbar_frame4 = ttk.Frame(toolbar_container)
        toolbar_frame4.pack(fill=tk.X, pady=2)

        # 度数格式
        ttk.Label(toolbar_frame4, text="度数:").pack(side=tk.LEFT, padx=(5, 2))
        self.coord_deg_entry = ttk.Entry(toolbar_frame4, width=35)
        self.coord_deg_entry.pack(side=tk.LEFT, padx=(0, 10))

        # HMS:DMS格式
        ttk.Label(toolbar_frame4, text="HMS:DMS:").pack(side=tk.LEFT, padx=(5, 2))
        self.coord_hms_entry = ttk.Entry(toolbar_frame4, width=35)
        self.coord_hms_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 合并格式
        ttk.Label(toolbar_frame4, text="合并:").pack(side=tk.LEFT, padx=(5, 2))
        self.coord_compact_entry = ttk.Entry(toolbar_frame4, width=25)
        self.coord_compact_entry.pack(side=tk.LEFT, padx=(0, 5))

        # 如果ASTAP处理器不可用，禁用按钮
        if not self.astap_processor:
            self.astap_button.config(state="disabled", text="ASTAP不可用")

        # WCS检查按钮
        self.wcs_check_button = ttk.Button(toolbar_frame2, text="检查WCS",
                                         command=self._check_directory_wcs, state="disabled")
        self.wcs_check_button.pack(side=tk.LEFT, padx=(5, 0))

        # 如果WCS检查器不可用，禁用按钮
        if not self.wcs_checker:
            self.wcs_check_button.config(state="disabled", text="WCS检查不可用")

        # 打开目录按钮
        self.open_dir_button = ttk.Button(toolbar_frame2, text="打开下载目录",
                                        command=self._open_download_directory)
        self.open_dir_button.pack(side=tk.LEFT, padx=(5, 0))

        # 创建主要内容区域（左右分割）
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 创建左侧目录树区域
        self._create_directory_tree(content_frame)

        # 创建右侧图像显示区域
        self._create_image_display(content_frame)
        
    def _create_directory_tree(self, parent):
        """创建左侧目录树"""
        # 左侧框架
        left_frame = ttk.LabelFrame(parent, text="目录浏览", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
        left_frame.configure(width=300)  # 固定宽度

        # 刷新按钮
        refresh_frame = ttk.Frame(left_frame)
        refresh_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(refresh_frame, text="刷新目录", command=self._refresh_directory_tree).pack(side=tk.LEFT)
        ttk.Button(refresh_frame, text="展开全部", command=self._expand_all).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(refresh_frame, text="折叠全部", command=self._collapse_all).pack(side=tk.LEFT, padx=(5, 0))

        # 创建目录树
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # 目录树控件
        self.directory_tree = ttk.Treeview(tree_frame, show="tree")
        self.directory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 滚动条
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.directory_tree.yview)
        self.directory_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定选择事件
        self.directory_tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.directory_tree.bind('<Double-1>', self._on_tree_double_click)
        self.directory_tree.bind('<<TreeviewOpen>>', self._on_tree_open)

        # 绑定键盘左右键事件
        self.directory_tree.bind('<Left>', self._on_tree_left_key)
        self.directory_tree.bind('<Right>', self._on_tree_right_key)

        # 不在这里初始化目录树，等待首次刷新

    def _create_image_display(self, parent):
        """创建右侧图像显示区域"""
        # 右侧框架
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 创建图像显示区域 - 减小高度以确保控制按钮可见
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 创建控制面板容器
        control_container = ttk.Frame(right_frame)
        control_container.pack(fill=tk.X, pady=(5, 0))

        # 第一行控制面板：显示模式和颜色映射
        control_frame1 = ttk.Frame(control_container)
        control_frame1.pack(fill=tk.X, pady=(0, 2))

        # 显示模式选择
        ttk.Label(control_frame1, text="显示模式:").pack(side=tk.LEFT, padx=(0, 5))
        self.display_mode = tk.StringVar(value="linear")
        mode_combo = ttk.Combobox(control_frame1, textvariable=self.display_mode,
                                 values=["linear", "log", "sqrt", "asinh"],
                                 state="readonly", width=10)
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        mode_combo.bind('<<ComboboxSelected>>', self._on_display_mode_change)

        # 颜色映射选择
        ttk.Label(control_frame1, text="颜色映射:").pack(side=tk.LEFT, padx=(0, 5))
        self.colormap = tk.StringVar(value="gray")
        cmap_combo = ttk.Combobox(control_frame1, textvariable=self.colormap,
                                 values=["gray", "viridis", "plasma", "inferno", "hot", "cool"],
                                 state="readonly", width=10)
        cmap_combo.pack(side=tk.LEFT, padx=(0, 10))
        cmap_combo.bind('<<ComboboxSelected>>', self._on_colormap_change)

        # 第二行控制面板：操作按钮
        control_frame2 = ttk.Frame(control_container)
        control_frame2.pack(fill=tk.X)

        # 刷新按钮
        refresh_btn = ttk.Button(control_frame2, text="刷新显示", command=self._refresh_display)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 保存按钮
        save_btn = ttk.Button(control_frame2, text="保存图像", command=self._save_image)
        save_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 打开输出目录按钮
        self.last_output_dir = None  # 保存最后一次的输出目录
        self.open_output_dir_btn = ttk.Button(control_frame2, text="打开输出目录",
                                              command=self._open_last_output_directory,
                                              state="disabled")
        self.open_output_dir_btn.pack(side=tk.LEFT, padx=(0, 0))

    def _load_batch_settings(self):
        """从配置文件加载批量处理参数到控件"""
        if not self.config_manager:
            return

        try:
            batch_settings = self.config_manager.get_batch_process_settings()

            # 降噪方式
            noise_method = batch_settings.get('noise_method', 'median')
            # 重置所有降噪选项
            self.outlier_var.set(False)
            self.hot_cold_var.set(False)
            self.adaptive_median_var.set(False)

            if noise_method == 'median':
                self.adaptive_median_var.set(True)
            elif noise_method == 'gaussian':
                self.outlier_var.set(True)
            # 如果是'none'，所有选项都不选中

            # 对齐方式
            alignment_method = batch_settings.get('alignment_method', 'orb')
            if alignment_method == 'orb':
                self.alignment_var.set('rigid')
            elif alignment_method == 'ecc':
                self.alignment_var.set('wcs')
            else:
                self.alignment_var.set('rigid')

            # 去除亮线
            remove_bright_lines = batch_settings.get('remove_bright_lines', True)
            self.remove_lines_var.set(remove_bright_lines)

            # 快速模式
            fast_mode = batch_settings.get('fast_mode', True)
            self.fast_mode_var.set(fast_mode)

            # 拉伸方法
            stretch_method = batch_settings.get('stretch_method', 'percentile')
            if stretch_method == 'percentile':
                self.stretch_method_var.set('percentile')
            elif stretch_method == 'minmax':
                self.stretch_method_var.set('peak')
            elif stretch_method == 'asinh':
                self.stretch_method_var.set('peak')
            else:
                self.stretch_method_var.set('percentile')

            # 百分位参数
            percentile_low = batch_settings.get('percentile_low', 99.95)
            self.percentile_var.set(str(percentile_low))

            self.logger.info(f"批量处理参数已加载到控件: 降噪={noise_method}, 对齐={alignment_method}, 去亮线={remove_bright_lines}, 快速模式={fast_mode}, 拉伸={stretch_method}, 百分位={percentile_low}%")

        except Exception as e:
            self.logger.error(f"加载批量处理参数失败: {str(e)}")

    def _bind_batch_settings_events(self):
        """绑定批量处理参数控件的变化事件"""
        if not self.config_manager:
            return

        try:
            # 绑定降噪方式复选框
            self.outlier_var.trace('w', self._on_batch_settings_change)
            self.hot_cold_var.trace('w', self._on_batch_settings_change)
            self.adaptive_median_var.trace('w', self._on_batch_settings_change)

            # 绑定对齐方式单选框
            self.alignment_var.trace('w', self._on_batch_settings_change)

            # 绑定去除亮线复选框
            self.remove_lines_var.trace('w', self._on_batch_settings_change)

            # 绑定快速模式复选框
            self.fast_mode_var.trace('w', self._on_batch_settings_change)

            # 绑定拉伸方法单选框
            self.stretch_method_var.trace('w', self._on_batch_settings_change)

            # 绑定百分位输入框（使用延迟保存，避免每次按键都保存）
            self.percentile_var.trace('w', self._on_percentile_change)

            self.logger.info("批量处理参数控件事件已绑定")

        except Exception as e:
            self.logger.error(f"绑定批量处理参数事件失败: {str(e)}")

    def _on_batch_settings_change(self, *args):
        """批量处理参数变化时保存到配置文件"""
        if not self.config_manager:
            return

        try:
            # 确定降噪方式
            noise_method = 'none'
            if self.adaptive_median_var.get():
                noise_method = 'median'
            elif self.outlier_var.get():
                noise_method = 'gaussian'
            elif self.hot_cold_var.get():
                noise_method = 'gaussian'  # hot_cold也映射到gaussian

            # 确定对齐方式
            alignment_method = 'orb'
            if self.alignment_var.get() == 'rigid':
                alignment_method = 'orb'
            elif self.alignment_var.get() == 'wcs':
                alignment_method = 'ecc'

            # 确定拉伸方法
            stretch_method = 'percentile'
            if self.stretch_method_var.get() == 'peak':
                stretch_method = 'minmax'
            elif self.stretch_method_var.get() == 'percentile':
                stretch_method = 'percentile'

            # 保存到配置文件
            self.config_manager.update_batch_process_settings(
                noise_method=noise_method,
                alignment_method=alignment_method,
                remove_bright_lines=self.remove_lines_var.get(),
                fast_mode=self.fast_mode_var.get(),
                stretch_method=stretch_method
            )

            self.logger.info(f"批量处理参数已保存: 降噪={noise_method}, 对齐={alignment_method}, 去亮线={self.remove_lines_var.get()}, 快速模式={self.fast_mode_var.get()}, 拉伸={stretch_method}")

        except Exception as e:
            self.logger.error(f"保存批量处理参数失败: {str(e)}")

    def _on_percentile_change(self, *args):
        """百分位参数变化时保存到配置文件（延迟保存）"""
        if not self.config_manager:
            return

        # 取消之前的延迟保存任务
        if hasattr(self, '_percentile_save_timer'):
            self.parent_frame.after_cancel(self._percentile_save_timer)

        # 设置新的延迟保存任务（1秒后保存）
        self._percentile_save_timer = self.parent_frame.after(1000, self._save_percentile)

    def _save_percentile(self):
        """保存百分位参数到配置文件"""
        if not self.config_manager:
            return

        try:
            percentile_low = float(self.percentile_var.get())
            self.config_manager.update_batch_process_settings(percentile_low=percentile_low)
            self.logger.info(f"百分位参数已保存: {percentile_low}%")
        except ValueError:
            self.logger.warning(f"无效的百分位值: {self.percentile_var.get()}")
        except Exception as e:
            self.logger.error(f"保存百分位参数失败: {str(e)}")

    def _first_time_refresh(self):
        """首次打开时自动刷新目录树"""
        if not self.first_refresh_done:
            self.first_refresh_done = True
            self.logger.info("首次打开图像查看器，自动刷新目录树")
            self._refresh_directory_tree()

    def _refresh_directory_tree(self):
        """刷新目录树"""
        try:
            # 配置标签样式
            self.directory_tree.tag_configure("wcs_green", foreground="green")
            self.directory_tree.tag_configure("wcs_orange", foreground="orange")
            self.directory_tree.tag_configure("diff_blue", foreground="blue")

            # 清空现有树
            for item in self.directory_tree.get_children():
                self.directory_tree.delete(item)

            # 添加下载目录
            download_dir = None
            if self.get_download_dir_callback:
                download_dir = self.get_download_dir_callback()
                if download_dir and os.path.exists(download_dir):
                    download_node = self.directory_tree.insert("", "end", text="📁 下载目录",
                                                             values=(download_dir,), tags=("root_dir",))
                    self._build_directory_tree(download_dir, download_node)
                else:
                    self.directory_tree.insert("", "end", text="❌ 下载目录未设置或不存在", tags=("no_dir",))

            # 添加模板目录
            template_dir = None
            if self.get_template_dir_callback:
                template_dir = self.get_template_dir_callback()
                if template_dir and os.path.exists(template_dir):
                    template_node = self.directory_tree.insert("", "end", text="📋 模板目录",
                                                             values=(template_dir,), tags=("root_dir",))
                    self._build_template_directory_tree(template_dir, template_node)
                else:
                    self.directory_tree.insert("", "end", text="❌ 模板目录未设置或不存在", tags=("no_dir",))

            # 如果都没有设置
            if not download_dir and not template_dir:
                self.directory_tree.insert("", "end", text="❌ 请设置下载目录或模板目录", tags=("no_dir",))

        except Exception as e:
            self.logger.error(f"刷新目录树失败: {str(e)}")
            self.directory_tree.insert("", "end", text=f"错误: {str(e)}", tags=("error",))

    def _build_directory_tree(self, base_dir, parent_node=""):
        """构建目录树结构"""
        try:
            # 遍历望远镜目录
            for tel_name in sorted(os.listdir(base_dir)):
                tel_path = os.path.join(base_dir, tel_name)
                if not os.path.isdir(tel_path):
                    continue

                # 添加望远镜节点
                tel_node = self.directory_tree.insert(parent_node, "end", text=f"📡 {tel_name}",
                                                    values=(tel_path,), tags=("telescope",))

                # 遍历日期目录
                try:
                    for date_name in sorted(os.listdir(tel_path)):
                        date_path = os.path.join(tel_path, date_name)
                        if not os.path.isdir(date_path):
                            continue

                        # 添加日期节点
                        date_node = self.directory_tree.insert(tel_node, "end", text=f"📅 {date_name}",
                                                             values=(date_path,), tags=("date",))

                        # 遍历天区目录
                        try:
                            for k_name in sorted(os.listdir(date_path)):
                                k_path = os.path.join(date_path, k_name)
                                if not os.path.isdir(k_path):
                                    continue

                                # 统计FITS文件数量
                                fits_count = len([f for f in os.listdir(k_path)
                                                if f.lower().endswith(('.fits', '.fit', '.fts'))])

                                # 添加天区节点
                                k_text = f"🌌 {k_name} ({fits_count} 文件)"
                                k_node = self.directory_tree.insert(date_node, "end", text=k_text,
                                                                   values=(k_path,), tags=("region",))

                                # 添加FITS文件
                                self._add_fits_files_to_tree(k_node, k_path)

                        except PermissionError:
                            self.directory_tree.insert(date_node, "end", text="❌ 权限不足", tags=("error",))
                        except Exception as e:
                            self.directory_tree.insert(date_node, "end", text=f"❌ 错误: {str(e)}", tags=("error",))

                except PermissionError:
                    self.directory_tree.insert(tel_node, "end", text="❌ 权限不足", tags=("error",))
                except Exception as e:
                    self.directory_tree.insert(tel_node, "end", text=f"❌ 错误: {str(e)}", tags=("error",))

        except Exception as e:
            self.logger.error(f"构建目录树失败: {str(e)}")

    def _build_template_directory_tree(self, template_dir, parent_node):
        """构建模板目录树结构"""
        try:
            # 直接遍历模板目录中的所有文件和子目录
            for item_name in sorted(os.listdir(template_dir)):
                item_path = os.path.join(template_dir, item_name)

                if os.path.isdir(item_path):
                    # 子目录
                    dir_node = self.directory_tree.insert(parent_node, "end", text=f"📁 {item_name}",
                                                        values=(item_path,), tags=("template_dir",))
                    # 递归添加子目录内容
                    self._build_template_subdirectory(item_path, dir_node)
                elif item_name.lower().endswith(('.fits', '.fit', '.fts')):
                    # FITS文件
                    file_size = os.path.getsize(item_path)
                    size_str = self._format_file_size(file_size)
                    file_text = f"📄 {item_name} ({size_str})"
                    self.directory_tree.insert(parent_node, "end", text=file_text,
                                             values=(item_path,), tags=("fits_file",))

        except Exception as e:
            self.logger.error(f"构建模板目录树失败: {str(e)}")
            self.directory_tree.insert(parent_node, "end", text=f"❌ 错误: {str(e)}", tags=("error",))

    def _build_template_subdirectory(self, directory, parent_node):
        """递归构建模板子目录"""
        try:
            for item_name in sorted(os.listdir(directory)):
                item_path = os.path.join(directory, item_name)

                if os.path.isdir(item_path):
                    # 子目录
                    dir_node = self.directory_tree.insert(parent_node, "end", text=f"📁 {item_name}",
                                                        values=(item_path,), tags=("template_dir",))
                    # 递归添加
                    self._build_template_subdirectory(item_path, dir_node)
                elif item_name.lower().endswith(('.fits', '.fit', '.fts')):
                    # FITS文件
                    file_size = os.path.getsize(item_path)
                    size_str = self._format_file_size(file_size)
                    file_text = f"📄 {item_name} ({size_str})"
                    self.directory_tree.insert(parent_node, "end", text=file_text,
                                             values=(item_path,), tags=("fits_file",))

        except Exception as e:
            self.logger.error(f"构建模板子目录失败: {str(e)}")

    def _add_fits_files_to_tree(self, parent_node, directory):
        """添加FITS文件到树节点"""
        try:
            fits_files = []
            for filename in os.listdir(directory):
                if filename.lower().endswith(('.fits', '.fit', '.fts')):
                    file_path = os.path.join(directory, filename)
                    file_size = os.path.getsize(file_path)
                    fits_files.append((filename, file_path, file_size))

            # 按文件名排序
            fits_files.sort(key=lambda x: x[0])

            # 添加文件节点
            for filename, file_path, file_size in fits_files:
                size_str = self._format_file_size(file_size)
                file_text = f"📄 {filename} ({size_str})"
                self.directory_tree.insert(parent_node, "end", text=file_text,
                                         values=(file_path,), tags=("fits_file",))

        except Exception as e:
            self.logger.error(f"添加FITS文件失败: {str(e)}")

    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
        
    def load_fits_file(self, file_path: str) -> bool:
        """
        加载FITS文件
        
        Args:
            file_path (str): FITS文件路径
            
        Returns:
            bool: 是否加载成功
        """
        try:
            self.logger.info(f"加载FITS文件: {file_path}")
            
            with fits.open(file_path) as hdul:
                self.current_header = hdul[0].header
                self.current_fits_data = hdul[0].data
                
                if self.current_fits_data is None:
                    raise ValueError("无法读取图像数据")
                
                # 转换数据类型
                self.current_fits_data = self.current_fits_data.astype(np.float64)
                
                # 处理3D数据（取第一个切片）
                if len(self.current_fits_data.shape) == 3:
                    self.current_fits_data = self.current_fits_data[0]
                
                self.current_file_path = file_path
                
                # 更新界面
                self._update_file_info()
                self._update_image_display()
                
                self.logger.info(f"FITS文件加载成功: {self.current_fits_data.shape}")
                return True
                
        except Exception as e:
            self.logger.error(f"加载FITS文件失败: {str(e)}")
            messagebox.showerror("错误", f"加载FITS文件失败:\n{str(e)}")
            return False
    
    def _update_file_info(self):
        """更新文件信息显示"""
        if self.current_file_path:
            filename = os.path.basename(self.current_file_path)
            shape_str = f"{self.current_fits_data.shape[1]}×{self.current_fits_data.shape[0]}"
            self.file_info_label.config(text=f"文件: {filename} | 尺寸: {shape_str}")
        
        # 更新统计信息
        if self.current_fits_data is not None:
            mean, median, std = sigma_clipped_stats(self.current_fits_data, sigma=3.0)
            min_val = np.min(self.current_fits_data)
            max_val = np.max(self.current_fits_data)
            
            stats_text = f"均值: {mean:.2f} | 中位数: {median:.2f} | 标准差: {std:.2f} | 范围: [{min_val:.2f}, {max_val:.2f}]"
            self.stats_label.config(text=stats_text)
    
    def _update_image_display(self):
        """更新图像显示"""
        if self.current_fits_data is None:
            return
        
        try:
            # 清除之前的图像
            self.figure.clear()
            
            # 创建子图
            ax = self.figure.add_subplot(111)
            
            # 应用显示模式变换
            display_data = self._apply_display_transform(self.current_fits_data)
            
            # 显示图像
            im = ax.imshow(display_data, cmap=self.colormap.get(), origin='lower')
            
            # 添加颜色条
            self.figure.colorbar(im, ax=ax, shrink=0.8)
            
            # 设置标题
            if self.current_file_path:
                ax.set_title(os.path.basename(self.current_file_path))
            
            # 设置坐标轴标签
            ax.set_xlabel('X (像素)')
            ax.set_ylabel('Y (像素)')
            
            # 调整布局
            self.figure.tight_layout()
            
            # 刷新画布
            self.canvas.draw()
            
        except Exception as e:
            self.logger.error(f"更新图像显示失败: {str(e)}")
            messagebox.showerror("错误", f"更新图像显示失败:\n{str(e)}")
    
    def _apply_display_transform(self, data: np.ndarray) -> np.ndarray:
        """应用显示变换"""
        mode = self.display_mode.get()
        
        # 处理负值和零值
        data_min = np.min(data)
        if data_min <= 0 and mode in ['log', 'sqrt']:
            # 对于log和sqrt变换，需要处理负值
            data = data - data_min + 1e-10
        
        if mode == "linear":
            return data
        elif mode == "log":
            return np.log10(np.maximum(data, 1e-10))
        elif mode == "sqrt":
            return np.sqrt(np.maximum(data, 0))
        elif mode == "asinh":
            return np.arcsinh(data)
        else:
            return data
    
    def _on_display_mode_change(self, event=None):
        """显示模式改变事件"""
        self._update_image_display()
    
    def _on_colormap_change(self, event=None):
        """颜色映射改变事件"""
        self._update_image_display()
    
    def _refresh_display(self):
        """刷新显示"""
        self._update_image_display()
    
    def _save_image(self):
        """保存图像"""
        if self.current_fits_data is None:
            messagebox.showwarning("警告", "没有可保存的图像")
            return
        
        try:
            from tkinter import filedialog
            
            # 选择保存路径
            filename = filedialog.asksaveasfilename(
                title="保存图像",
                defaultextension=".png",
                filetypes=[
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg"),
                    ("PDF files", "*.pdf"),
                    ("All files", "*.*")
                ]
            )
            
            if filename:
                self.figure.savefig(filename, dpi=150, bbox_inches='tight')
                messagebox.showinfo("成功", f"图像已保存到:\n{filename}")
                
        except Exception as e:
            self.logger.error(f"保存图像失败: {str(e)}")
            messagebox.showerror("错误", f"保存图像失败:\n{str(e)}")
    
    def _on_tree_select(self, event):
        """目录树选择事件"""
        selection = self.directory_tree.selection()
        if not selection:
            self.selected_file_path = None
            self.display_button.config(state="disabled")
            self.diff_button.config(state="disabled")
            if self.astap_processor:
                self.astap_button.config(state="disabled")
            if self.wcs_checker:
                self.wcs_check_button.config(state="disabled")
            self.file_info_label.config(text="未选择文件")
            return

        item = selection[0]
        values = self.directory_tree.item(item, "values")
        tags = self.directory_tree.item(item, "tags")

        if values and "fits_file" in tags:
            # 选中的是FITS文件
            file_path = values[0]
            self.selected_file_path = file_path
            filename = os.path.basename(file_path)

            # 启用显示按钮
            self.display_button.config(state="normal")

            # 检查是否是下载目录中的文件（只有下载目录的文件才能执行diff）
            is_download_file = self._is_from_download_directory(file_path)
            can_diff = False

            if is_download_file and self.get_template_dir_callback:
                template_dir = self.get_template_dir_callback()
                if template_dir:
                    # 检查是否可以执行diff操作
                    can_process, status = self.diff_orb.can_process_file(file_path, template_dir)
                    can_diff = can_process

                    if can_diff:
                        self.logger.info(f"文件可以执行diff操作: {filename}")
                    else:
                        self.logger.info(f"文件不能执行diff操作: {status}")

            # 设置diff按钮状态
            self.diff_button.config(state="normal" if can_diff else "disabled")

            # 检查是否可以执行ASTAP操作（任何FITS文件都可以执行ASTAP）
            can_astap = self.astap_processor is not None
            self.astap_button.config(state="normal" if can_astap else "disabled")

            # 检查是否可以执行WCS检查（选择文件时检查其所在目录）
            can_wcs_check = self.wcs_checker is not None
            self.wcs_check_button.config(state="normal" if can_wcs_check else "disabled")

            # 更新状态标签
            status_text = f"已选择: {filename}"
            if is_download_file:
                status_text += " (下载文件)"
                if can_diff:
                    status_text += " [可执行Diff]"
                if can_astap:
                    status_text += " [可执行ASTAP]"
            else:
                status_text += " (模板文件)"
                if can_astap:
                    status_text += " [可执行ASTAP]"

            self.file_info_label.config(text=status_text)
            self.logger.info(f"已选择FITS文件: {filename}")

            # 如果是下载目录的文件，自动检查并加载diff结果
            if is_download_file:
                self._auto_load_diff_results(file_path)
        else:
            # 选中的不是FITS文件
            self.selected_file_path = None
            self.display_button.config(state="disabled")
            self.diff_button.config(state="disabled")
            if self.astap_processor:
                self.astap_button.config(state="disabled")
            if self.wcs_checker:
                self.wcs_check_button.config(state="disabled")
            self.file_info_label.config(text="未选择FITS文件")

    def _on_tree_double_click(self, event):
        """目录树双击事件"""
        selection = self.directory_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.directory_tree.item(item, "values")
        tags = self.directory_tree.item(item, "tags")

        if values and any(tag in tags for tag in ["telescope", "date", "region", "template_dir", "root_dir"]):
            # 双击目录节点，打开文件管理器
            directory = values[0]
            self._open_directory_in_explorer(directory)

    def _on_tree_open(self, event):
        """目录树展开事件"""
        self.logger.info("触发目录树展开事件")

        # 获取被展开的节点
        # TreeviewOpen事件中，需要从focus获取当前节点
        item = self.directory_tree.focus()

        if not item:
            self.logger.warning("展开事件：无法获取焦点节点")
            return

        text = self.directory_tree.item(item, "text")
        values = self.directory_tree.item(item, "values")
        tags = self.directory_tree.item(item, "tags")

        self.logger.info(f"展开节点: text={text}, tags={tags}")

        # 检查是否是天区目录（有region标签）
        if "region" in tags:
            if values:
                region_dir = values[0]
                self.logger.info(f"展开天区目录: {region_dir}")
                # 扫描该目录下的文件，标记已有diff结果的文件
                self._mark_files_with_diff_results(item, region_dir)
            else:
                self.logger.warning(f"天区目录没有values: {text}")
        else:
            self.logger.debug(f"不是天区目录，跳过: text={text}, tags={tags}")

    def _mark_files_with_diff_results(self, parent_item, region_dir):
        """
        标记已有diff结果的文件为蓝色

        Args:
            parent_item: 父节点（天区目录节点）
            region_dir: 天区目录路径
        """
        try:
            self.logger.info(f"扫描天区目录中的diff结果: {region_dir}")

            # 获取该天区目录下的所有子节点（文件）
            children = self.directory_tree.get_children(parent_item)
            self.logger.info(f"找到 {len(children)} 个子节点")

            marked_count = 0

            for child in children:
                child_text = self.directory_tree.item(child, "text")
                child_tags = self.directory_tree.item(child, "tags")
                child_values = self.directory_tree.item(child, "values")

                self.logger.info(f"检查节点: text={child_text}, tags={child_tags}, has_values={bool(child_values)}")

                # 只处理文件节点（fits_file标签）
                if "fits_file" in child_tags and child_values:
                    file_path = child_values[0]
                    filename = os.path.basename(file_path)

                    self.logger.info(f"检查文件: {filename}")
                    self.logger.info(f"  文件路径: {file_path}")

                    # 检查是否有对应的diff输出目录
                    # 输出目录在output目录下，而不是download目录
                    # 路径结构: E:/fix_data/output/系统名/日期/天区/文件名/detection_xxx

                    # 构建输出目录路径
                    # region_dir格式: E:/fix_data/download/GY5/20251002/K054
                    # 输出目录格式: E:/fix_data/output/GY5/20251002/K054/文件名/detection_xxx

                    self.logger.info(f"  原始region_dir: {region_dir}")

                    # 获取配置的输出目录
                    base_output_dir = None
                    if self.get_diff_output_dir_callback:
                        base_output_dir = self.get_diff_output_dir_callback()

                    if not base_output_dir or not os.path.exists(base_output_dir):
                        self.logger.warning(f"  输出目录未配置或不存在，跳过")
                        continue

                    self.logger.info(f"  输出根目录: {base_output_dir}")

                    # 从region_dir提取相对路径部分（系统名/日期/天区）
                    # 例如: E:/fix_data/download/GY5/20251002/K054 -> GY5/20251002/K054
                    download_dir = None
                    if self.get_download_dir_callback:
                        download_dir = self.get_download_dir_callback()

                    if download_dir:
                        # 标准化路径
                        normalized_region_dir = os.path.normpath(region_dir)
                        normalized_download_dir = os.path.normpath(download_dir)

                        # 获取相对路径
                        try:
                            relative_path = os.path.relpath(normalized_region_dir, normalized_download_dir)
                            self.logger.info(f"  相对路径: {relative_path}")

                            # 构建输出目录路径
                            output_region_dir = os.path.join(base_output_dir, relative_path)
                        except ValueError:
                            # 如果路径不在同一驱动器，使用备用方法
                            self.logger.warning(f"  无法计算相对路径，使用备用方法")
                            continue
                    else:
                        self.logger.warning(f"  下载目录未配置，跳过")
                        continue

                    self.logger.info(f"  输出天区目录: {output_region_dir}")

                    file_basename = os.path.splitext(filename)[0]
                    potential_output_dir = os.path.join(output_region_dir, file_basename)

                    self.logger.info(f"  检查输出目录: {potential_output_dir}")
                    self.logger.info(f"  目录是否存在: {os.path.exists(potential_output_dir)}")

                    # 检查是否存在detection目录
                    has_diff_result = False
                    if os.path.exists(potential_output_dir) and os.path.isdir(potential_output_dir):
                        self.logger.info(f"  输出目录存在，查找detection子目录...")
                        # 查找detection_开头的目录
                        try:
                            items = os.listdir(potential_output_dir)
                            self.logger.info(f"  输出目录内容: {items}")

                            for item_name in items:
                                item_path = os.path.join(potential_output_dir, item_name)
                                if os.path.isdir(item_path) and item_name.startswith('detection_'):
                                    has_diff_result = True
                                    self.logger.info(f"  ✓ 找到diff结果: {filename} -> {item_name}")
                                    break
                        except Exception as list_error:
                            self.logger.error(f"  列出目录内容失败: {list_error}")
                    else:
                        self.logger.debug(f"  输出目录不存在")

                    # 如果有diff结果，标记为蓝色
                    if has_diff_result:
                        current_tags = list(child_tags)
                        # 移除其他颜色标记
                        current_tags = [t for t in current_tags if t not in ["wcs_green", "wcs_orange", "diff_blue"]]
                        current_tags.append("diff_blue")
                        self.directory_tree.item(child, tags=current_tags)
                        marked_count += 1
                        self.logger.info(f"  ✓ 已标记为蓝色: {filename}")

            self.logger.info(f"完成天区目录diff结果扫描: {region_dir}，标记了 {marked_count} 个文件")

        except Exception as e:
            self.logger.error(f"标记diff结果文件时出错: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _display_selected_image(self):
        """显示选中的图像"""
        if not self.selected_file_path:
            messagebox.showwarning("警告", "请先选择一个FITS文件")
            return

        try:
            self.display_button.config(state="disabled", text="加载中...")
            self.parent_frame.update()  # 更新界面显示

            # 加载FITS文件
            success = self.load_fits_file(self.selected_file_path)

            if success:
                filename = os.path.basename(self.selected_file_path)
                self.file_info_label.config(text=f"已显示: {filename}")
                self.logger.info(f"已显示FITS文件: {filename}")
            else:
                self.file_info_label.config(text="加载失败")

        except Exception as e:
            self.logger.error(f"显示图像失败: {str(e)}")
            messagebox.showerror("错误", f"显示图像失败: {str(e)}")
        finally:
            self.display_button.config(state="normal", text="显示图像")

    def _expand_all(self):
        """展开所有节点"""
        def expand_recursive(item):
            self.directory_tree.item(item, open=True)
            for child in self.directory_tree.get_children(item):
                expand_recursive(child)

        for item in self.directory_tree.get_children():
            expand_recursive(item)

    def _collapse_all(self):
        """折叠所有节点"""
        def collapse_recursive(item):
            self.directory_tree.item(item, open=False)
            for child in self.directory_tree.get_children(item):
                collapse_recursive(child)

        for item in self.directory_tree.get_children():
            collapse_recursive(item)

    def _open_download_directory(self):
        """打开当前下载目录"""
        try:
            if not self.get_download_dir_callback or not self.get_url_selections_callback:
                messagebox.showwarning("警告", "无法获取下载目录信息")
                return

            base_dir = self.get_download_dir_callback()
            selections = self.get_url_selections_callback()

            if not base_dir or not os.path.exists(base_dir):
                messagebox.showwarning("警告", "下载根目录不存在")
                return

            # 构建目标目录：根目录/tel_name/YYYYMMDD
            tel_name = selections.get('telescope_name', '')
            date = selections.get('date', '')

            if tel_name and date:
                target_dir = os.path.join(base_dir, tel_name, date)
                if os.path.exists(target_dir):
                    self._open_directory_in_explorer(target_dir)
                    self.logger.info(f"已打开目录: {target_dir}")
                else:
                    # 如果具体目录不存在，打开上级目录
                    tel_dir = os.path.join(base_dir, tel_name)
                    if os.path.exists(tel_dir):
                        self._open_directory_in_explorer(tel_dir)
                        self.logger.info(f"目录不存在，已打开上级目录: {tel_dir}")
                    else:
                        self._open_directory_in_explorer(base_dir)
                        self.logger.info(f"已打开根目录: {base_dir}")
            else:
                self._open_directory_in_explorer(base_dir)
                self.logger.info(f"已打开根目录: {base_dir}")

        except Exception as e:
            self.logger.error(f"打开目录失败: {str(e)}")
            messagebox.showerror("错误", f"打开目录失败: {str(e)}")

    def _open_last_output_directory(self):
        """打开最后一次diff操作的输出目录"""
        if self.last_output_dir and os.path.exists(self.last_output_dir):
            try:
                self._open_directory_in_explorer(self.last_output_dir)
                self.logger.info(f"已打开输出目录: {self.last_output_dir}")
            except Exception as e:
                self.logger.error(f"打开输出目录失败: {str(e)}")
                messagebox.showerror("错误", f"打开输出目录失败: {str(e)}")
        else:
            messagebox.showwarning("警告", "没有可用的输出目录")

    def _open_directory_in_explorer(self, directory):
        """在文件管理器中打开目录"""
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(directory)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", directory])
            else:  # Linux
                subprocess.run(["xdg-open", directory])
        except Exception as e:
            self.logger.error(f"打开文件管理器失败: {str(e)}")
            messagebox.showerror("错误", f"打开文件管理器失败: {str(e)}")

    def clear_display(self):
        """清除显示"""
        self.current_fits_data = None
        self.current_header = None
        self.current_file_path = None
        self.selected_file_path = None

        self.figure.clear()
        self.canvas.draw()

        self.file_info_label.config(text="未选择文件")
        self.stats_label.config(text="")
        self.display_button.config(state="disabled")
        self.diff_button.config(state="disabled")
        if self.astap_processor:
            self.astap_button.config(state="disabled")

    def _is_from_download_directory(self, file_path: str) -> bool:
        """
        判断文件是否来自下载目录

        Args:
            file_path (str): 文件路径

        Returns:
            bool: 是否来自下载目录
        """
        if not self.get_download_dir_callback:
            return False

        download_dir = self.get_download_dir_callback()
        if not download_dir or not os.path.exists(download_dir):
            return False

        # 检查文件路径是否以下载目录开头
        try:
            file_path = os.path.abspath(file_path)
            download_dir = os.path.abspath(download_dir)

            return file_path.startswith(download_dir)
        except:
            return False

    def _execute_diff(self):
        """执行diff操作（启动后台线程）"""
        if not self.selected_file_path:
            messagebox.showwarning("警告", "请先选择一个FITS文件")
            return

        if not self.get_template_dir_callback:
            messagebox.showwarning("警告", "无法获取模板目录")
            return

        template_dir = self.get_template_dir_callback()
        if not template_dir or not os.path.exists(template_dir):
            messagebox.showwarning("警告", "模板目录不存在，请先设置模板目录")
            return

        # 检查是否是下载目录中的文件
        if not self._is_from_download_directory(self.selected_file_path):
            messagebox.showwarning("警告", "只能对下载目录中的文件执行diff操作")
            return

        # 禁用按钮并显示进度
        self.diff_button.config(state="disabled", text="处理中...")
        self.diff_progress_label.config(text="正在准备Diff操作...", foreground="blue")

        # 在后台线程中执行diff操作
        import threading
        thread = threading.Thread(target=self._execute_diff_thread, args=(template_dir,))
        thread.daemon = True
        thread.start()

    def _execute_diff_thread(self, template_dir):
        """在后台线程中执行diff操作"""
        try:
            # 更新进度：查找模板文件
            self.parent_frame.after(0, lambda: self.diff_progress_label.config(
                text="正在查找模板文件...", foreground="blue"))

            # 查找对应的模板文件
            template_file = self.diff_orb.find_template_file(self.selected_file_path, template_dir)

            if not template_file:
                self.parent_frame.after(0, lambda: messagebox.showwarning("警告", "未找到匹配的模板文件"))
                self.parent_frame.after(0, lambda: self.diff_button.config(state="normal", text="执行Diff"))
                self.parent_frame.after(0, lambda: self.diff_progress_label.config(text="", foreground="black"))
                return

            # 更新进度：准备输出目录
            self.parent_frame.after(0, lambda: self.diff_progress_label.config(
                text="正在准备输出目录...", foreground="blue"))

            # 获取输出目录
            output_dir = self._get_diff_output_directory()

            # 检查输出目录中是否已存在detection目录（避免重复执行）
            detection_dirs = [d for d in os.listdir(output_dir) if d.startswith('detection_') and os.path.isdir(os.path.join(output_dir, d))]
            if detection_dirs:
                self.logger.info("=" * 60)
                self.logger.info(f"检测到已有处理结果: {detection_dirs[0]}")
                self.logger.info(f"输出目录: {output_dir}")
                self.logger.info("跳过diff操作，直接显示已有结果")
                self.logger.info("=" * 60)

                # 更新进度：显示已有结果
                self.parent_frame.after(0, lambda: self.diff_progress_label.config(
                    text="已有处理结果，直接显示", foreground="green"))

                # 直接显示已有结果，不弹窗询问
                self.last_output_dir = output_dir
                self.parent_frame.after(0, lambda: self.open_output_dir_btn.config(state="normal"))

                # 尝试显示第一个检测目标的cutout图片
                cutout_displayed = self._display_first_detection_cutouts(output_dir)
                if cutout_displayed:
                    self.logger.info("已显示已有的cutout图片")
                else:
                    self.logger.info("未找到cutout图片")

                self.logger.info(f"输出目录: {output_dir} (点击'打开输出目录'按钮查看)")
                self.parent_frame.after(0, lambda: self.diff_button.config(state="normal", text="执行Diff"))
                self.parent_frame.after(0, lambda: self.diff_progress_label.config(text="", foreground="black"))
                return

            # 获取选择的降噪方式
            noise_methods = []
            if self.outlier_var.get():
                noise_methods.append('outlier')
            if self.hot_cold_var.get():
                noise_methods.append('hot_cold')
            if self.adaptive_median_var.get():
                noise_methods.append('adaptive_median')

            # 如果没有选择任何方式，不使用降噪（传入空列表）
            if not noise_methods:
                self.logger.info("未选择降噪方式，跳过降噪处理")

            # 获取选择的对齐方式
            alignment_method = self.alignment_var.get()
            self.logger.info(f"选择的对齐方式: {alignment_method}")

            # 获取是否去除亮线选项
            remove_bright_lines = self.remove_lines_var.get()
            self.logger.info(f"去除亮线: {'是' if remove_bright_lines else '否'}")

            # 获取拉伸方法选项
            stretch_method = self.stretch_method_var.get()
            self.logger.info(f"拉伸方法: {stretch_method}")

            # 获取百分位数参数
            percentile_low = 99.95  # 默认值
            if stretch_method == 'percentile':
                try:
                    percentile_low = float(self.percentile_var.get())
                    if percentile_low < 0 or percentile_low > 100:
                        raise ValueError("百分位数必须在0-100之间")
                    self.logger.info(f"百分位数: {percentile_low}%")
                except ValueError as e:
                    self.logger.warning(f"百分位数输入无效，使用默认值99.95%: {e}")
                    percentile_low = 99.95

            # 获取快速模式选项
            fast_mode = self.fast_mode_var.get()
            self.logger.info(f"快速模式: {'是' if fast_mode else '否'}")

            # 更新进度：开始执行Diff
            filename = os.path.basename(self.selected_file_path)
            self.parent_frame.after(0, lambda f=filename: self.diff_progress_label.config(
                text=f"正在执行Diff: {f}", foreground="blue"))

            # 执行diff操作
            result = self.diff_orb.process_diff(self.selected_file_path, template_file, output_dir,
                                              noise_methods=noise_methods, alignment_method=alignment_method,
                                              remove_bright_lines=remove_bright_lines,
                                              stretch_method=stretch_method,
                                              percentile_low=percentile_low,
                                              fast_mode=fast_mode)

            if result and result.get('success'):
                # 更新进度：处理完成
                new_spots = result.get('new_bright_spots', 0)
                self.parent_frame.after(0, lambda n=new_spots: self.diff_progress_label.config(
                    text=f"✓ Diff完成 - 检测到 {n} 个新亮点", foreground="green"))

                # 记录结果摘要到日志
                summary = self.diff_orb.get_diff_summary(result)
                self.logger.info("=" * 60)
                self.logger.info("Diff操作完成")
                self.logger.info("=" * 60)
                for line in summary.split('\n'):
                    if line.strip():
                        self.logger.info(line)
                self.logger.info("=" * 60)

                # 尝试显示第一个检测目标的cutout图片
                cutout_displayed = False
                output_dir = result.get('output_directory')
                if output_dir:
                    cutout_displayed = self._display_first_detection_cutouts(output_dir)

                # 根据是否显示了cutout图片决定后续操作
                if cutout_displayed:
                    self.logger.info("已显示cutout图片")
                else:
                    self.logger.info("未找到cutout图片，不显示其他文件")

                # 保存输出目录路径并启用按钮
                self.last_output_dir = output_dir
                self.parent_frame.after(0, lambda: self.open_output_dir_btn.config(state="normal"))
                self.logger.info(f"输出目录: {output_dir} (点击'打开输出目录'按钮查看)")
            else:
                self.logger.error("Diff操作失败")
                self.parent_frame.after(0, lambda: self.diff_progress_label.config(
                    text="✗ Diff操作失败", foreground="red"))
                self.parent_frame.after(0, lambda: messagebox.showerror("错误", "Diff操作失败"))

        except Exception as e:
            self.logger.error(f"执行diff操作时出错: {str(e)}")
            error_msg = str(e)
            self.parent_frame.after(0, lambda msg=error_msg: self.diff_progress_label.config(
                text=f"✗ 错误: {msg}", foreground="red"))
            self.parent_frame.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"执行diff操作时出错: {msg}"))
        finally:
            # 恢复按钮状态
            self.parent_frame.after(0, lambda: self.diff_button.config(state="normal", text="执行Diff"))

    def _get_diff_output_directory(self) -> str:
        """获取diff操作的输出目录"""
        from datetime import datetime
        import re

        # 获取配置的根目录
        base_output_dir = ""
        if self.get_diff_output_dir_callback:
            base_output_dir = self.get_diff_output_dir_callback()

        # 如果没有配置，使用下载文件所在目录
        if not base_output_dir or not os.path.exists(base_output_dir):
            if self.selected_file_path:
                base_output_dir = os.path.dirname(self.selected_file_path)
            else:
                base_output_dir = os.path.expanduser("~/diff_results")

        # 尝试从文件名、文件路径或URL选择中获取系统名、日期、天区信息
        system_name = "Unknown"
        date_str = datetime.now().strftime("%Y%m%d")
        sky_region = "Unknown"

        # 方法1: 从文件名解析（最优先，文件名包含最准确的信息）
        if self.selected_file_path:
            try:
                filename = os.path.basename(self.selected_file_path)
                # 文件名格式: GY3_K073-2_No Filter_60S_Bin2_UTC20250719_171814_-12.8C_.fit
                # 提取系统名 (GY开头+数字)
                system_match = re.search(r'(GY\d+)', filename, re.IGNORECASE)
                if system_match:
                    system_name = system_match.group(1).upper()

                # 提取天区 (K开头+数字)
                sky_match = re.search(r'(K\d{3})', filename, re.IGNORECASE)
                if sky_match:
                    sky_region = sky_match.group(1).upper()

                # 提取日期 (UTC后面的日期)
                date_match = re.search(r'UTC(\d{8})', filename)
                if date_match:
                    date_str = date_match.group(1)

                if system_name != "Unknown" or sky_region != "Unknown":
                    self.logger.info(f"从文件名解析: 系统={system_name}, 日期={date_str}, 天区={sky_region}")
            except Exception as e:
                self.logger.warning(f"从文件名解析信息失败: {e}")

        # 方法2: 从文件路径解析（如果方法1未获取完整信息）
        if self.selected_file_path and (system_name == "Unknown" or sky_region == "Unknown"):
            try:
                # 文件路径格式: .../系统名/日期/天区/文件名
                # 例如: E:/fix_data/GY5/20250922/K096/xxx.fit
                path_parts = self.selected_file_path.replace('\\', '/').split('/')

                # 从路径中查找符合模式的部分
                for i, part in enumerate(path_parts):
                    # 查找日期格式 (YYYYMMDD)
                    if re.match(r'^\d{8}$', part) and i > 0:
                        if system_name == "Unknown":
                            system_name = path_parts[i-1]  # 日期前一级是系统名
                        date_str = part
                        if i + 1 < len(path_parts):
                            # 查找天区格式 (K开头+数字)
                            next_part = path_parts[i+1]
                            if re.match(r'^K\d{3}', next_part):
                                sky_region = next_part
                        break

                self.logger.info(f"从文件路径解析: 系统={system_name}, 日期={date_str}, 天区={sky_region}")
            except Exception as e:
                self.logger.warning(f"从文件路径解析信息失败: {e}")

        # 方法3: 从URL选择回调获取信息（最后备选）
        if (system_name == "Unknown" or sky_region == "Unknown") and self.get_url_selections_callback:
            try:
                selections = self.get_url_selections_callback()
                if selections:
                    if system_name == "Unknown":
                        system_name = selections.get('telescope_name', 'Unknown')
                    if date_str == datetime.now().strftime("%Y%m%d"):
                        date_str = selections.get('date', date_str)
                    if sky_region == "Unknown":
                        sky_region = selections.get('k_number', 'Unknown')
                    self.logger.info(f"从URL选择补充: 系统={system_name}, 日期={date_str}, 天区={sky_region}")
            except Exception as e:
                self.logger.warning(f"从URL选择获取信息失败: {e}")

        # 从选中文件名生成子目录名（不带时间戳，避免重复执行）
        if self.selected_file_path:
            filename = os.path.basename(self.selected_file_path)
            name_without_ext = os.path.splitext(filename)[0]
            subdir_name = name_without_ext
        else:
            subdir_name = "diff_result"

        # 构建完整输出目录：根目录/系统名/日期/天区/文件名/
        output_dir = os.path.join(base_output_dir, system_name, date_str, sky_region, subdir_name)

        # 创建目录
        os.makedirs(output_dir, exist_ok=True)

        self.logger.info(f"diff输出目录: {output_dir}")
        self.logger.info(f"目录结构: {system_name}/{date_str}/{sky_region}/{subdir_name}")
        return output_dir

    def _auto_load_diff_results(self, file_path):
        """自动检查并加载diff结果"""
        try:
            # 获取该文件对应的输出目录
            output_dir = self._get_diff_output_directory()

            # 检查输出目录是否存在
            if not os.path.exists(output_dir):
                self.logger.info(f"未找到diff输出目录，清除显示")
                self._clear_diff_display()
                return

            # 检查输出目录中是否存在detection目录
            try:
                detection_dirs = [d for d in os.listdir(output_dir)
                                if d.startswith('detection_') and os.path.isdir(os.path.join(output_dir, d))]
            except Exception as e:
                self.logger.info(f"读取输出目录失败，清除显示: {str(e)}")
                self._clear_diff_display()
                return

            if not detection_dirs:
                self.logger.info(f"未找到detection目录，清除显示")
                self._clear_diff_display()
                return

            # 找到了diff结果
            self.logger.info("=" * 60)
            self.logger.info(f"发现已有diff结果: {detection_dirs[0]}")
            self.logger.info(f"输出目录: {output_dir}")
            self.logger.info("=" * 60)

            # 保存输出目录路径并启用按钮
            self.last_output_dir = output_dir
            self.open_output_dir_btn.config(state="normal")

            # 尝试显示第一个检测目标的cutout图片
            cutout_displayed = self._display_first_detection_cutouts(output_dir)
            if cutout_displayed:
                self.logger.info("已自动加载cutout图片")
                self.diff_progress_label.config(text="已加载diff结果", foreground="green")
            else:
                self.logger.info("未找到cutout图片")
                self.diff_progress_label.config(text="已有diff结果（无cutout）", foreground="blue")

            self.logger.info(f"输出目录: {output_dir} (点击'打开输出目录'按钮查看)")

        except Exception as e:
            self.logger.warning(f"自动加载diff结果失败: {str(e)}")
            self._clear_diff_display()
            # 不显示错误对话框，只记录日志

    def _clear_diff_display(self):
        """清除diff结果显示"""
        # 停止动画
        if hasattr(self, '_blink_animation_id') and self._blink_animation_id:
            self.parent_frame.after_cancel(self._blink_animation_id)
            self._blink_animation_id = None

        # 断开点击事件
        if hasattr(self, '_click_connection_id') and self._click_connection_id:
            self.canvas.mpl_disconnect(self._click_connection_id)
            self._click_connection_id = None

        # 清空主画布
        if hasattr(self, 'figure') and self.figure:
            self.figure.clear()
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.draw()

        # 重置cutout相关变量
        if hasattr(self, '_all_cutout_sets'):
            self._all_cutout_sets = []
        if hasattr(self, '_current_cutout_index'):
            self._current_cutout_index = 0
        if hasattr(self, '_total_cutouts'):
            self._total_cutouts = 0

        # 清空坐标显示框
        if hasattr(self, 'coord_deg_entry'):
            self.coord_deg_entry.delete(0, tk.END)
        if hasattr(self, 'coord_hms_entry'):
            self.coord_hms_entry.delete(0, tk.END)
        if hasattr(self, 'coord_compact_entry'):
            self.coord_compact_entry.delete(0, tk.END)

        # 更新cutout计数标签
        if hasattr(self, 'cutout_count_label'):
            self.cutout_count_label.config(text="0/0")

        # 禁用导航按钮
        if hasattr(self, 'prev_cutout_button'):
            self.prev_cutout_button.config(state="disabled")
        if hasattr(self, 'next_cutout_button'):
            self.next_cutout_button.config(state="disabled")
        if hasattr(self, 'check_dss_button'):
            self.check_dss_button.config(state="disabled")

        # 清除输出目录
        self.last_output_dir = None

        # 禁用打开输出目录按钮
        if hasattr(self, 'open_output_dir_btn'):
            self.open_output_dir_btn.config(state="disabled")

        # 清除进度标签
        if hasattr(self, 'diff_progress_label'):
            self.diff_progress_label.config(text="", foreground="black")

        self.logger.info("已清除diff结果显示")

    def get_header_info(self) -> Optional[str]:
        """获取FITS头信息"""
        if self.current_header is None:
            return None
        
        header_text = "FITS Header Information:\n"
        header_text += "=" * 50 + "\n"
        
        for key, value in self.current_header.items():
            if key and value is not None:
                header_text += f"{key:8} = {value}\n"
        
        return header_text

    def _execute_astap(self):
        """执行ASTAP处理"""
        if not self.selected_file_path:
            messagebox.showwarning("警告", "请先选择一个FITS文件")
            return

        if not self.astap_processor:
            messagebox.showerror("错误", "ASTAP处理器不可用")
            return

        try:
            # 禁用按钮
            self.astap_button.config(state="disabled", text="处理中...")
            self.parent_frame.update()  # 更新界面显示

            filename = os.path.basename(self.selected_file_path)
            self.logger.info(f"开始ASTAP处理: {filename}")

            # 执行ASTAP处理
            success = self.astap_processor.process_fits_file(self.selected_file_path)

            if success:
                # 在状态栏显示成功信息，不弹出对话框
                self.file_info_label.config(text=f"ASTAP处理完成: {filename}")
                self.logger.info(f"ASTAP处理成功: {filename}")
            else:
                messagebox.showerror("ASTAP处理失败",
                                   f"文件 {filename} 的ASTAP处理失败！\n\n"
                                   f"可能的原因:\n"
                                   f"1. 无法从文件名提取天区编号\n"
                                   f"2. 配置文件中没有对应天区的坐标\n"
                                   f"3. ASTAP程序执行失败\n\n"
                                   f"请检查日志获取详细信息。")
                self.logger.error(f"ASTAP处理失败: {filename}")

        except Exception as e:
            self.logger.error(f"ASTAP处理异常: {str(e)}")
            messagebox.showerror("错误", f"ASTAP处理时发生异常:\n{str(e)}")

        finally:
            # 恢复按钮状态
            if self.astap_processor:
                self.astap_button.config(state="normal", text="执行ASTAP")

    def _check_directory_wcs(self):
        """检查目录中FITS文件的WCS信息"""
        if not self.wcs_checker:
            messagebox.showerror("错误", "WCS检查器不可用")
            return

        if not self.selected_file_path:
            messagebox.showwarning("警告", "请先选择一个FITS文件")
            return

        try:
            # 获取选中文件所在的目录
            directory_path = os.path.dirname(self.selected_file_path)

            # 显示进度对话框
            progress_window = tk.Toplevel(self.parent_frame)
            progress_window.title("WCS检查进度")
            progress_window.geometry("400x150")
            progress_window.transient(self.parent_frame)
            progress_window.grab_set()

            # 居中显示
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
            y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
            progress_window.geometry(f"+{x}+{y}")

            progress_label = ttk.Label(progress_window, text="正在检查目录中的FITS文件...")
            progress_label.pack(pady=20)

            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=tk.X)
            progress_bar.start()

            # 强制更新界面
            progress_window.update()

            # 执行WCS检查
            self.logger.info(f"开始检查目录WCS信息: {directory_path}")
            with_wcs, total, with_wcs_files, without_wcs_files = self.wcs_checker.get_wcs_summary(directory_path)

            # 关闭进度对话框
            progress_bar.stop()
            progress_window.destroy()

            # 更新目录树中的文件颜色
            self._update_tree_wcs_colors(directory_path, with_wcs_files, without_wcs_files)

            # 在状态栏显示简单的结果信息，不弹出对话框
            self.file_info_label.config(text=f"WCS检查完成: {with_wcs}/{total} 个文件包含WCS信息")
            self.logger.info(f"WCS检查完成: {with_wcs}/{total} 个文件包含WCS信息")

        except Exception as e:
            # 确保关闭进度对话框
            try:
                progress_bar.stop()
                progress_window.destroy()
            except:
                pass

            self.logger.error(f"WCS检查失败: {str(e)}")
            messagebox.showerror("错误", f"WCS检查失败:\n{str(e)}")

    def _update_tree_wcs_colors(self, directory_path, with_wcs_files, without_wcs_files):
        """更新目录树中文件的颜色标识"""
        try:
            # 配置标签样式
            self.directory_tree.tag_configure("wcs_green", foreground="green")
            self.directory_tree.tag_configure("wcs_orange", foreground="orange")
            self.directory_tree.tag_configure("diff_blue", foreground="blue")

            # 遍历目录树，找到对应的文件节点并更新颜色
            def update_node_colors(parent_item):
                for child in self.directory_tree.get_children(parent_item):
                    values = self.directory_tree.item(child, "values")
                    tags = self.directory_tree.item(child, "tags")

                    if values and "fits_file" in tags:
                        file_path = values[0]
                        filename = os.path.basename(file_path)

                        # 检查文件是否在当前检查的目录中
                        if os.path.dirname(file_path) == directory_path:
                            if filename in with_wcs_files:
                                # 有WCS信息，显示为绿色
                                current_tags = list(tags)
                                current_tags.append("wcs_green")
                                self.directory_tree.item(child, tags=current_tags)
                            elif filename in without_wcs_files:
                                # 无WCS信息，显示为橙色
                                current_tags = list(tags)
                                current_tags.append("wcs_orange")
                                self.directory_tree.item(child, tags=current_tags)

                    # 递归处理子节点
                    update_node_colors(child)

            # 从根节点开始更新
            for root_item in self.directory_tree.get_children():
                update_node_colors(root_item)

            self.logger.info(f"已更新目录树颜色标识: {len(with_wcs_files)}个绿色, {len(without_wcs_files)}个橙色")

        except Exception as e:
            self.logger.error(f"更新目录树颜色时出错: {e}")

    def _display_first_detection_cutouts(self, output_dir):
        """
        显示第一个检测目标的cutout图片

        Args:
            output_dir: 输出目录路径

        Returns:
            bool: 是否成功显示了cutout图片
        """
        try:
            # 查找detection目录
            detection_dirs = list(Path(output_dir).glob("detection_*"))
            if not detection_dirs:
                self.logger.info("未找到detection目录")
                return False

            # 使用最新的detection目录
            detection_dir = sorted(detection_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            self.logger.info(f"找到detection目录: {detection_dir.name}")

            # 查找cutouts文件夹
            cutouts_dir = detection_dir / "cutouts"
            if not cutouts_dir.exists():
                self.logger.info("未找到cutouts文件夹")
                return False

            # 查找所有目标的图片（按文件名排序）
            reference_files = sorted(cutouts_dir.glob("*_1_reference.png"))
            aligned_files = sorted(cutouts_dir.glob("*_2_aligned.png"))
            detection_files = sorted(cutouts_dir.glob("*_3_detection.png"))

            if not (reference_files and aligned_files and detection_files):
                self.logger.info("未找到完整的cutout图片")
                return False

            # 保存所有图片列表和当前索引
            self._all_cutout_sets = []
            for ref, aligned, det in zip(reference_files, aligned_files, detection_files):
                self._all_cutout_sets.append({
                    'reference': str(ref),
                    'aligned': str(aligned),
                    'detection': str(det)
                })

            self._current_cutout_index = 0
            self._total_cutouts = len(self._all_cutout_sets)

            self.logger.info(f"找到 {self._total_cutouts} 组检测结果")

            # 显示第一组图片
            self._display_cutout_by_index(0)

            return True  # 成功显示

        except Exception as e:
            self.logger.error(f"显示cutout图片时出错: {e}")
            return False

    def _display_cutout_by_index(self, index):
        """
        显示指定索引的cutout图片

        Args:
            index: 图片组索引
        """
        if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
            return

        if index < 0 or index >= len(self._all_cutout_sets):
            return

        self._current_cutout_index = index
        cutout_set = self._all_cutout_sets[index]

        reference_img = cutout_set['reference']
        aligned_img = cutout_set['aligned']
        detection_img = cutout_set['detection']

        self.logger.info(f"显示第 {index + 1}/{self._total_cutouts} 组检测结果:")
        self.logger.info(f"  Reference: {os.path.basename(reference_img)}")
        self.logger.info(f"  Aligned: {os.path.basename(aligned_img)}")
        self.logger.info(f"  Detection: {os.path.basename(detection_img)}")

        # 更新计数标签
        self.cutout_count_label.config(text=f"{index + 1}/{self._total_cutouts}")

        # 启用导航按钮
        if self._total_cutouts > 1:
            self.prev_cutout_button.config(state="normal")
            self.next_cutout_button.config(state="normal")

        # 启用检查DSS按钮（只要有cutout就可以启用）
        if hasattr(self, 'check_dss_button'):
            self.check_dss_button.config(state="normal")

        # 提取文件信息（使用左侧选中的文件名）
        selected_filename = ""
        if self.selected_file_path:
            selected_filename = os.path.basename(self.selected_file_path)

        file_info = self._extract_file_info(reference_img, aligned_img, detection_img, selected_filename)

        # 更新坐标显示框
        self._update_coordinate_display(file_info)

        # 在主界面显示图片
        self._show_cutouts_in_main_display(reference_img, aligned_img, detection_img, file_info)

    def _show_next_cutout(self):
        """显示下一组cutout图片"""
        if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
            messagebox.showinfo("提示", "没有可显示的检测结果")
            return

        next_index = (self._current_cutout_index + 1) % self._total_cutouts
        self._display_cutout_by_index(next_index)

    def _update_coordinate_display(self, file_info):
        """
        更新坐标显示框

        Args:
            file_info: 文件信息字典
        """
        # 清空所有文本框
        self.coord_deg_entry.delete(0, tk.END)
        self.coord_hms_entry.delete(0, tk.END)
        self.coord_compact_entry.delete(0, tk.END)

        if not file_info:
            self.logger.warning("file_info为空")
            return

        self.logger.info(f"更新坐标显示，file_info内容: {file_info}")

        # 度数格式
        if file_info.get('ra') and file_info.get('dec'):
            deg_text = f"RA: {file_info['ra']}°  Dec: {file_info['dec']}°"
            self.coord_deg_entry.insert(0, deg_text)
            self.logger.info(f"度数格式: {deg_text}")
        else:
            self.logger.warning(f"度数格式缺失: ra={file_info.get('ra')}, dec={file_info.get('dec')}")

        # HMS:DMS格式（时分秒分开）
        if file_info.get('ra_hms') and file_info.get('dec_dms'):
            hms_text = f"{file_info['ra_hms']}  {file_info['dec_dms']}"
            self.coord_hms_entry.insert(0, hms_text)
            self.logger.info(f"HMS:DMS格式: {hms_text}")
        else:
            self.logger.warning(f"HMS:DMS格式缺失: ra_hms={file_info.get('ra_hms')}, dec_dms={file_info.get('dec_dms')}")

            # 如果有度数但没有HMS/DMS，尝试在这里计算
            if file_info.get('ra') and file_info.get('dec'):
                try:
                    from astropy.coordinates import Angle
                    import astropy.units as u

                    ra_deg = float(file_info['ra'])
                    dec_deg = float(file_info['dec'])

                    ra_angle = Angle(ra_deg, unit=u.degree)
                    dec_angle = Angle(dec_deg, unit=u.degree)

                    ra_hms = ra_angle.to_string(unit=u.hourangle, sep=':', precision=2)
                    dec_dms = dec_angle.to_string(unit=u.degree, sep=':', precision=2)

                    hms_text = f"{ra_hms}  {dec_dms}"
                    self.coord_hms_entry.insert(0, hms_text)
                    self.logger.info(f"补充计算HMS:DMS格式: {hms_text}")

                    # 同时计算合并格式
                    ra_h, ra_m, ra_s = ra_angle.hms
                    dec_sign_val, dec_d, dec_m, dec_s = dec_angle.signed_dms

                    ra_compact = f"{int(ra_h):02d}{int(ra_m):02d}{ra_s:05.2f}"
                    dec_sign = '+' if dec_sign_val >= 0 else '-'
                    dec_compact = f"{dec_sign}{abs(int(dec_d)):02d}{int(dec_m):02d}{abs(dec_s):05.2f}"

                    compact_text = f"{ra_compact}  {dec_compact}"
                    self.coord_compact_entry.insert(0, compact_text)
                    self.logger.info(f"补充计算合并格式: {compact_text}")

                    return  # 已经补充计算完成，直接返回

                except Exception as e:
                    self.logger.error(f"补充计算HMS/DMS格式失败: {e}")

        # 合并小数格式
        if file_info.get('ra_compact') and file_info.get('dec_compact'):
            compact_text = f"{file_info['ra_compact']}  {file_info['dec_compact']}"
            self.coord_compact_entry.insert(0, compact_text)
            self.logger.info(f"合并格式: {compact_text}")
        else:
            self.logger.warning(f"合并格式缺失: ra_compact={file_info.get('ra_compact')}, dec_compact={file_info.get('dec_compact')}")

    def _show_previous_cutout(self):
        """显示上一组cutout图片"""
        if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
            messagebox.showinfo("提示", "没有可显示的检测结果")
            return

        prev_index = (self._current_cutout_index - 1) % self._total_cutouts
        self._display_cutout_by_index(prev_index)

    def _on_tree_left_key(self, event):
        """处理目录树的左键事件 - 对应"上一组"按钮"""
        # 获取当前选中的节点
        selection = self.directory_tree.selection()
        if not selection:
            return  # 没有选中节点，使用默认行为

        item = selection[0]
        # 检查是否有子节点
        children = self.directory_tree.get_children(item)
        if children:
            # 有子节点，说明是目录节点，使用默认行为（折叠）
            return

        # 是最终节点（FITS文件），执行"上一组"操作
        if hasattr(self, 'prev_cutout_button') and str(self.prev_cutout_button['state']) == 'normal':
            self._show_previous_cutout()
            return "break"  # 阻止默认行为

    def _on_tree_right_key(self, event):
        """处理目录树的右键事件 - 对应"下一组"按钮"""
        # 获取当前选中的节点
        selection = self.directory_tree.selection()
        if not selection:
            return  # 没有选中节点，使用默认行为

        item = selection[0]
        # 检查是否有子节点
        children = self.directory_tree.get_children(item)
        if children:
            # 有子节点，说明是目录节点
            # 检查节点是否已经展开
            is_open = self.directory_tree.item(item, 'open')
            if is_open:
                # 已经展开，跳转到第一个子项目
                first_child = children[0]
                self.directory_tree.selection_set(first_child)
                self.directory_tree.focus(first_child)
                self.directory_tree.see(first_child)
                return "break"  # 阻止默认行为
            else:
                # 未展开，使用默认行为（展开）
                return

        # 是最终节点（FITS文件），执行"下一组"操作
        if hasattr(self, 'next_cutout_button') and str(self.next_cutout_button['state']) == 'normal':
            self._show_next_cutout()
            return "break"  # 阻止默认行为

    def _extract_file_info(self, reference_img, aligned_img, detection_img, selected_filename=""):
        """
        从文件路径和FITS文件中提取信息

        Args:
            reference_img: 参考图像路径
            aligned_img: 对齐图像路径
            detection_img: 检测图像路径
            selected_filename: 左侧选中的文件名

        Returns:
            dict: 包含文件信息的字典
        """
        from astropy.io import fits
        import re

        info = {
            'filename': '',
            'system_name': '',
            'region': '',
            'ra': '',
            'dec': ''
        }

        try:
            # 打印路径用于调试
            self.logger.info(f"提取文件信息，路径: {detection_img}")
            self.logger.info(f"选中的文件名: {selected_filename}")

            # 使用左侧选中的文件名
            if selected_filename:
                info['filename'] = selected_filename
                self.logger.info(f"使用选中的文件名: {selected_filename}")
            else:
                # 如果没有选中文件，从detection文件名提取blob编号
                detection_basename = os.path.basename(detection_img)
                self.logger.info(f"Detection文件名: {detection_basename}")

                # 提取blob编号 - 尝试多种格式
                blob_match = re.search(r'blob[_\s]*(\d+)', detection_basename, re.IGNORECASE)
                if blob_match:
                    blob_num = blob_match.group(1)
                    info['filename'] = f"目标 #{blob_num}"
                    self.logger.info(f"找到Blob编号: {blob_num}")
                else:
                    # 如果没找到blob编号，使用文件名
                    info['filename'] = os.path.splitext(detection_basename)[0]
                    self.logger.info(f"未找到Blob编号，使用文件名: {info['filename']}")

            # 保存blob编号用于后续查找RA/DEC
            detection_basename = os.path.basename(detection_img)
            blob_match = re.search(r'blob[_\s]*(\d+)', detection_basename, re.IGNORECASE)
            blob_num = blob_match.group(1) if blob_match else None

            # 尝试从路径中提取系统名和天区
            # 路径格式: .../diff_output/系统名/日期/天区/文件名/detection_xxx/cutouts/...
            path_parts = Path(detection_img).parts
            self.logger.info(f"路径部分: {path_parts}")

            # 查找detection目录的位置
            detection_index = -1
            for i, part in enumerate(path_parts):
                if part.startswith('detection_'):
                    detection_index = i
                    self.logger.info(f"找到detection目录在索引 {i}: {part}")
                    break

            if detection_index >= 0:
                # detection_xxx 的上一级是文件名目录
                # 再上一级是天区
                # 再上一级是日期
                # 再上一级是系统名
                if detection_index >= 1:
                    # 文件名目录（detection的父目录）
                    file_dir = path_parts[detection_index - 1]
                    self.logger.info(f"文件目录: {file_dir}")

                if detection_index >= 2:
                    info['region'] = path_parts[detection_index - 2]  # 天区
                    self.logger.info(f"天区: {info['region']}")

                if detection_index >= 4:
                    info['system_name'] = path_parts[detection_index - 4]  # 系统名
                    self.logger.info(f"系统名: {info['system_name']}")

            # 从像素坐标和WCS信息计算RA/DEC
            detection_dir = Path(detection_img).parent.parent
            self.logger.info(f"Detection目录: {detection_dir}")

            # 1. 首先尝试从cutout文件名中提取像素坐标
            pixel_x = None
            pixel_y = None

            # cutout文件名格式: 001_X1234_Y5678_... 或 001_RA123.456_DEC78.901_...
            detection_basename = os.path.basename(detection_img)
            xy_match = re.search(r'X(\d+)_Y(\d+)', detection_basename)
            if xy_match:
                pixel_x = float(xy_match.group(1))
                pixel_y = float(xy_match.group(2))
                self.logger.info(f"从cutout文件名提取像素坐标: X={pixel_x}, Y={pixel_y}")

            # 2. 如果文件名中没有X_Y坐标，尝试从detection结果文件中获取
            if pixel_x is None or pixel_y is None:
                result_files = []
                result_files.extend(list(detection_dir.glob("detection_result_*.txt")))
                result_files.extend(list(detection_dir.glob("*result*.txt")))

                parent_dir = detection_dir.parent
                result_files.extend(list(parent_dir.glob("detection_result_*.txt")))
                result_files.extend(list(parent_dir.glob("*result*.txt")))

                self.logger.info(f"找到结果文件: {len(result_files)} 个")

                if result_files:
                    result_file = result_files[0]
                    self.logger.info(f"读取结果文件: {result_file}")

                    try:
                        with open(result_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            self.logger.info(f"结果文件内容前500字符:\n{content[:500]}")

                            # 查找对应blob的像素坐标
                            if blob_num:
                                # 尝试多种格式提取像素坐标
                                # 格式示例: Blob #0: 位置=(123.45, 678.90)
                                patterns = [
                                    rf'Blob\s*#?\s*{blob_num}\s*:.*?位置[=:\s]*\(?\s*([\d.]+)\s*,\s*([\d.]+)\s*\)?',
                                    rf'目标\s*#?\s*{blob_num}\s*:.*?位置[=:\s]*\(?\s*([\d.]+)\s*,\s*([\d.]+)\s*\)?',
                                    rf'#{blob_num}.*?位置[=:\s]*\(?\s*([\d.]+)\s*,\s*([\d.]+)\s*\)?',
                                    rf'blob[_\s]*{blob_num}.*?[Pp]osition[=:\s]*\(?\s*([\d.]+)\s*,\s*([\d.]+)\s*\)?',
                                    rf'Blob\s*#?\s*{blob_num}\s*:.*?\(?\s*([\d.]+)\s*,\s*([\d.]+)\s*\)?',
                                ]

                                for i, pattern in enumerate(patterns):
                                    coord_match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                                    if coord_match:
                                        pixel_x = float(coord_match.group(1))
                                        pixel_y = float(coord_match.group(2))
                                        self.logger.info(f"从结果文件找到像素坐标(模式{i}): x={pixel_x}, y={pixel_y}")
                                        break

                            # 如果没找到像素坐标，尝试直接查找RA/DEC（备用方案）
                            if pixel_x is None or pixel_y is None:
                                if blob_num:
                                    patterns = [
                                        rf'Blob\s*#?\s*{blob_num}\s*:.*?RA[=:\s]+([\d.]+).*?Dec[=:\s]+([-\d.]+)',
                                        rf'目标\s*#?\s*{blob_num}\s*:.*?RA[=:\s]+([\d.]+).*?Dec[=:\s]+([-\d.]+)',
                                    ]

                                    for pattern in patterns:
                                        coord_match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                                        if coord_match:
                                            ra_deg = float(coord_match.group(1))
                                            dec_deg = float(coord_match.group(2))
                                            info['ra'] = f"{ra_deg:.6f}"
                                            info['dec'] = f"{dec_deg:.6f}"

                                            # 计算HMS/DMS格式
                                            from astropy.coordinates import Angle
                                            import astropy.units as u

                                            ra_angle = Angle(ra_deg, unit=u.degree)
                                            dec_angle = Angle(dec_deg, unit=u.degree)

                                            ra_hms = ra_angle.to_string(unit=u.hourangle, sep=':', precision=2)
                                            dec_dms = dec_angle.to_string(unit=u.degree, sep=':', precision=2)

                                            ra_h, ra_m, ra_s = ra_angle.hms
                                            dec_sign_val, dec_d, dec_m, dec_s = dec_angle.signed_dms

                                            ra_compact = f"{int(ra_h):02d}{int(ra_m):02d}{ra_s:05.2f}"
                                            dec_sign = '+' if dec_sign_val >= 0 else '-'
                                            dec_compact = f"{dec_sign}{abs(int(dec_d)):02d}{int(dec_m):02d}{abs(dec_s):05.2f}"

                                            info['ra_hms'] = ra_hms
                                            info['dec_dms'] = dec_dms
                                            info['ra_compact'] = ra_compact
                                            info['dec_compact'] = dec_compact

                                            self.logger.info(f"从结果文件直接找到RA/DEC: RA={info['ra']}, Dec={info['dec']}")
                                            break

                    except Exception as e:
                        self.logger.error(f"读取结果文件出错: {e}")

            # 3. 如果找到了像素坐标，从FITS文件的WCS信息计算RA/DEC
            if (pixel_x is not None and pixel_y is not None) and (not info['ra'] or not info['dec']):
                self.logger.info(f"尝试使用像素坐标 ({pixel_x}, {pixel_y}) 和WCS信息计算RA/DEC")

                # 查找多个位置的FITS文件
                fits_files = []

                # 在detection目录查找
                fits_files.extend(list(detection_dir.glob("*.fits")))
                fits_files.extend(list(detection_dir.glob("*.fit")))

                # 在父目录查找
                parent_dir = detection_dir.parent
                fits_files.extend(list(parent_dir.glob("*.fits")))
                fits_files.extend(list(parent_dir.glob("*.fit")))

                # 在父目录的父目录查找（可能是原始下载目录）
                if parent_dir.parent.exists():
                    fits_files.extend(list(parent_dir.parent.glob("*.fits")))
                    fits_files.extend(list(parent_dir.parent.glob("*.fit")))

                self.logger.info(f"找到FITS文件: {len(fits_files)} 个")

                if fits_files:
                    for fits_file in fits_files:
                        try:
                            self.logger.info(f"尝试读取FITS文件: {fits_file}")
                            with fits.open(fits_file) as hdul:
                                header = hdul[0].header

                                # 尝试使用WCS转换像素坐标到天球坐标
                                try:
                                    from astropy.wcs import WCS
                                    wcs = WCS(header)

                                    # 将像素坐标转换为天球坐标（FITS使用1-based索引）
                                    sky_coords = wcs.pixel_to_world(pixel_x, pixel_y)

                                    # 保存度数格式
                                    ra_deg = sky_coords.ra.degree
                                    dec_deg = sky_coords.dec.degree
                                    info['ra'] = f"{ra_deg:.6f}"
                                    info['dec'] = f"{dec_deg:.6f}"

                                    # 计算HMS/DMS格式
                                    from astropy.coordinates import Angle
                                    import astropy.units as u

                                    ra_angle = Angle(ra_deg, unit=u.degree)
                                    dec_angle = Angle(dec_deg, unit=u.degree)

                                    # HMS格式 (RA用小时)
                                    ra_hms = ra_angle.to_string(unit=u.hourangle, sep=':', precision=2)
                                    # DMS格式 (DEC用度)
                                    dec_dms = dec_angle.to_string(unit=u.degree, sep=':', precision=2)

                                    # 合并小数格式 (HHMMSS.SS, DDMMSS.SS)
                                    ra_h, ra_m, ra_s = ra_angle.hms
                                    dec_sign_val, dec_d, dec_m, dec_s = dec_angle.signed_dms

                                    ra_compact = f"{int(ra_h):02d}{int(ra_m):02d}{ra_s:05.2f}"
                                    dec_sign = '+' if dec_sign_val >= 0 else '-'
                                    dec_compact = f"{dec_sign}{abs(int(dec_d)):02d}{int(dec_m):02d}{abs(dec_s):05.2f}"

                                    info['ra_hms'] = ra_hms
                                    info['dec_dms'] = dec_dms
                                    info['ra_compact'] = ra_compact
                                    info['dec_compact'] = dec_compact

                                    self.logger.info(f"使用WCS计算得到坐标: RA={info['ra']}, Dec={info['dec']}")
                                    self.logger.info(f"  HMS格式: {ra_hms}, DMS格式: {dec_dms}")
                                    self.logger.info(f"  合并格式: {ra_compact}, {dec_compact}")
                                    break

                                except Exception as wcs_error:
                                    self.logger.warning(f"WCS转换失败: {wcs_error}")

                                    # 如果WCS转换失败，尝试使用简单的线性转换
                                    # 检查是否有基本的WCS关键字
                                    if all(key in header for key in ['CRVAL1', 'CRVAL2', 'CRPIX1', 'CRPIX2', 'CD1_1', 'CD2_2']):
                                        try:
                                            crval1 = header['CRVAL1']  # 参考点RA
                                            crval2 = header['CRVAL2']  # 参考点DEC
                                            crpix1 = header['CRPIX1']  # 参考像素X
                                            crpix2 = header['CRPIX2']  # 参考像素Y
                                            cd1_1 = header['CD1_1']    # 像素到度的转换矩阵
                                            cd2_2 = header['CD2_2']

                                            # 简单线性转换
                                            delta_x = pixel_x - crpix1
                                            delta_y = pixel_y - crpix2

                                            ra = crval1 + delta_x * cd1_1
                                            dec = crval2 + delta_y * cd2_2

                                            info['ra'] = f"{ra:.6f}"
                                            info['dec'] = f"{dec:.6f}"

                                            # 计算HMS/DMS格式
                                            from astropy.coordinates import Angle
                                            import astropy.units as u

                                            ra_angle = Angle(ra, unit=u.degree)
                                            dec_angle = Angle(dec, unit=u.degree)

                                            ra_hms = ra_angle.to_string(unit=u.hourangle, sep=':', precision=2)
                                            dec_dms = dec_angle.to_string(unit=u.degree, sep=':', precision=2)

                                            ra_h, ra_m, ra_s = ra_angle.hms
                                            dec_sign_val, dec_d, dec_m, dec_s = dec_angle.signed_dms

                                            ra_compact = f"{int(ra_h):02d}{int(ra_m):02d}{ra_s:05.2f}"
                                            dec_sign = '+' if dec_sign_val >= 0 else '-'
                                            dec_compact = f"{dec_sign}{abs(int(dec_d)):02d}{int(dec_m):02d}{abs(dec_s):05.2f}"

                                            info['ra_hms'] = ra_hms
                                            info['dec_dms'] = dec_dms
                                            info['ra_compact'] = ra_compact
                                            info['dec_compact'] = dec_compact

                                            self.logger.info(f"使用简单线性转换计算得到坐标: RA={info['ra']}, Dec={info['dec']}")
                                            break

                                        except Exception as linear_error:
                                            self.logger.warning(f"简单线性转换失败: {linear_error}")

                        except Exception as e:
                            self.logger.error(f"读取FITS文件失败 {fits_file}: {e}")

            # 4. 如果还是没有找到RA/DEC，尝试从FITS header直接读取（使用图像中心坐标）
            if not info['ra'] or not info['dec']:
                self.logger.info("尝试从FITS header直接读取RA/DEC")

                # 查找FITS文件
                fits_files = []
                fits_files.extend(list(detection_dir.glob("*.fits")))
                fits_files.extend(list(detection_dir.glob("*.fit")))

                parent_dir = detection_dir.parent
                fits_files.extend(list(parent_dir.glob("*.fits")))
                fits_files.extend(list(parent_dir.glob("*.fit")))

                if parent_dir.parent.exists():
                    fits_files.extend(list(parent_dir.parent.glob("*.fits")))
                    fits_files.extend(list(parent_dir.parent.glob("*.fit")))

                if fits_files:
                    for fits_file in fits_files:
                        try:
                            with fits.open(fits_file) as hdul:
                                header = hdul[0].header

                                # 尝试多种RA/DEC关键字
                                ra_keys = ['CRVAL1', 'RA', 'OBJCTRA', 'TELRA']
                                dec_keys = ['CRVAL2', 'DEC', 'OBJCTDEC', 'TELDEC']

                                ra_val = None
                                dec_val = None

                                for key in ra_keys:
                                    if key in header:
                                        ra_val = header[key]
                                        break

                                for key in dec_keys:
                                    if key in header:
                                        dec_val = header[key]
                                        break

                                if ra_val is not None and dec_val is not None:
                                    # 如果是字符串格式，需要转换
                                    if isinstance(ra_val, str):
                                        try:
                                            from astropy.coordinates import Angle
                                            import astropy.units as u
                                            ra_angle = Angle(ra_val, unit=u.hourangle)
                                            ra_val = ra_angle.degree
                                        except:
                                            pass

                                    if isinstance(dec_val, str):
                                        try:
                                            from astropy.coordinates import Angle
                                            import astropy.units as u
                                            dec_angle = Angle(dec_val, unit=u.degree)
                                            dec_val = dec_angle.degree
                                        except:
                                            pass

                                    info['ra'] = f"{float(ra_val):.6f}"
                                    info['dec'] = f"{float(dec_val):.6f}"

                                    # 计算HMS/DMS格式
                                    try:
                                        from astropy.coordinates import Angle
                                        import astropy.units as u

                                        ra_angle = Angle(float(ra_val), unit=u.degree)
                                        dec_angle = Angle(float(dec_val), unit=u.degree)

                                        ra_hms = ra_angle.to_string(unit=u.hourangle, sep=':', precision=2)
                                        dec_dms = dec_angle.to_string(unit=u.degree, sep=':', precision=2)

                                        ra_h, ra_m, ra_s = ra_angle.hms
                                        dec_sign_val, dec_d, dec_m, dec_s = dec_angle.signed_dms

                                        ra_compact = f"{int(ra_h):02d}{int(ra_m):02d}{ra_s:05.2f}"
                                        dec_sign = '+' if dec_sign_val >= 0 else '-'
                                        dec_compact = f"{dec_sign}{abs(int(dec_d)):02d}{int(dec_m):02d}{abs(dec_s):05.2f}"

                                        info['ra_hms'] = ra_hms
                                        info['dec_dms'] = dec_dms
                                        info['ra_compact'] = ra_compact
                                        info['dec_compact'] = dec_compact
                                    except Exception as format_error:
                                        self.logger.warning(f"格式转换失败: {format_error}")

                                    self.logger.info(f"从FITS header找到坐标: RA={info['ra']}, Dec={info['dec']}")
                                    break

                        except Exception as e:
                            self.logger.error(f"读取FITS文件失败 {fits_file}: {e}")

            self.logger.info(f"最终提取的信息: {info}")

        except Exception as e:
            self.logger.error(f"提取文件信息失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        return info

    def _show_cutouts_in_main_display(self, reference_img, aligned_img, detection_img, file_info=None):
        """
        在主界面显示三张cutout图片

        Args:
            reference_img: 参考图像路径
            aligned_img: 对齐图像路径
            detection_img: 检测图像路径
            file_info: 文件信息字典（可选）
        """
        from PIL import Image

        try:
            # 停止之前的动画（如果存在）
            if hasattr(self, '_blink_animation_id') and self._blink_animation_id:
                self.parent_frame.after_cancel(self._blink_animation_id)
                self._blink_animation_id = None

            # 断开之前的点击事件（如果存在）
            if hasattr(self, '_click_connection_id') and self._click_connection_id:
                self.canvas.mpl_disconnect(self._click_connection_id)
                self._click_connection_id = None

            # 清空当前图像
            self.figure.clear()

            # 创建主标题，显示文件信息
            if file_info:
                title_lines = []

                # 第一行：检测结果编号
                if hasattr(self, '_current_cutout_index') and hasattr(self, '_total_cutouts'):
                    title_lines.append(f"检测结果 {self._current_cutout_index + 1} / {self._total_cutouts}")

                # 第二行：系统名、天区、文件名
                info_parts = []
                if file_info.get('system_name'):
                    info_parts.append(f"系统: {file_info['system_name']}")
                if file_info.get('region'):
                    info_parts.append(f"天区: {file_info['region']}")
                if file_info.get('filename'):
                    info_parts.append(file_info['filename'])

                if info_parts:
                    title_lines.append(" | ".join(info_parts))

                # 第三行：RA/DEC（始终显示，即使没有值）
                ra_text = file_info.get('ra') if file_info.get('ra') else "N/A"
                dec_text = file_info.get('dec') if file_info.get('dec') else "N/A"
                title_lines.append(f"RA: {ra_text}°  Dec: {dec_text}°")

                # 组合标题
                title_text = "\n".join(title_lines)
                self.figure.suptitle(title_text, fontsize=10, fontweight='bold')
            else:
                # 如果没有文件信息，只显示基本标题
                if hasattr(self, '_current_cutout_index') and hasattr(self, '_total_cutouts'):
                    title_text = f"检测结果 {self._current_cutout_index + 1} / {self._total_cutouts}"
                    self.figure.suptitle(title_text, fontsize=12, fontweight='bold')

            # 创建1行3列的子图
            axes = self.figure.subplots(1, 3)

            # 加载reference和aligned图像数据
            ref_img = Image.open(reference_img)
            ref_array = np.array(ref_img)

            aligned_img_obj = Image.open(aligned_img)
            aligned_array = np.array(aligned_img_obj)

            detection_img_obj = Image.open(detection_img)
            detection_array = np.array(detection_img_obj)

            # 保存图像数据供动画使用
            self._blink_images = [ref_array, aligned_array]
            self._blink_index = 0

            # 显示第一张图片（reference）
            self._blink_ax = axes[0]
            self._blink_im = self._blink_ax.imshow(
                ref_array,
                cmap='gray' if len(ref_array.shape) == 2 else None
            )
            self._blink_ax.set_title("Reference ⇄ Aligned (闪烁)", fontsize=10, fontweight='bold')
            self._blink_ax.axis('off')

            # 显示aligned图像（可点击切换）
            self._click_ax = axes[1]
            self._click_images = [aligned_array, ref_array]
            self._click_image_names = ["Aligned", "Reference"]
            self._click_index = 0
            self._click_im = self._click_ax.imshow(
                aligned_array,
                cmap='gray' if len(aligned_array.shape) == 2 else None
            )
            total_images = len(self._click_images)
            self._click_ax.set_title(f"Aligned (1/{total_images}) - 点击切换", fontsize=10, fontweight='bold')
            self._click_ax.axis('off')

            # 显示detection图像
            axes[2].imshow(detection_array, cmap='gray' if len(detection_array.shape) == 2 else None)
            axes[2].set_title("Detection (检测结果)", fontsize=10, fontweight='bold')
            axes[2].axis('off')

            # 调整子图间距
            self.figure.tight_layout()

            # 刷新画布
            self.canvas.draw()

            # 绑定点击事件
            self._setup_click_toggle()

            # 启动闪烁动画
            self._start_blink_animation()

        except Exception as e:
            self.logger.error(f"显示cutout图片时出错: {e}")

    def _start_blink_animation(self):
        """启动闪烁动画"""
        def update_blink():
            try:
                # 切换图像索引
                self._blink_index = 1 - self._blink_index

                # 更新图像数据
                self._blink_im.set_data(self._blink_images[self._blink_index])

                # 更新标题显示当前图像
                if self._blink_index == 0:
                    self._blink_ax.set_title("Reference (模板图像)", fontsize=10, fontweight='bold')
                else:
                    self._blink_ax.set_title("Aligned (对齐图像)", fontsize=10, fontweight='bold')

                # 刷新画布
                self.canvas.draw_idle()

                # 继续下一次更新
                self._blink_animation_id = self.parent_frame.after(500, update_blink)

            except Exception as e:
                self.logger.error(f"闪烁动画更新失败: {e}")
                self._blink_animation_id = None

        # 启动第一次更新
        self._blink_animation_id = self.parent_frame.after(500, update_blink)

    def _setup_click_toggle(self):
        """设置点击切换功能"""
        def on_click(event):
            try:
                # 检查点击是否在aligned图像的子图区域内
                if event.inaxes == self._click_ax:
                    # 循环切换图像索引
                    self._click_index = (self._click_index + 1) % len(self._click_images)

                    # 更新图像数据
                    self._click_im.set_data(self._click_images[self._click_index])

                    # 更新标题显示当前图像
                    image_name = self._click_image_names[self._click_index] if hasattr(self, '_click_image_names') else f"Image {self._click_index}"
                    total_images = len(self._click_images)
                    self._click_ax.set_title(f"{image_name} ({self._click_index + 1}/{total_images}) - 点击切换",
                                           fontsize=10, fontweight='bold')

                    # 刷新画布
                    self.canvas.draw_idle()

            except Exception as e:
                self.logger.error(f"点击切换失败: {e}")

        # 绑定点击事件到canvas，并保存连接ID
        self._click_connection_id = self.canvas.mpl_connect('button_press_event', on_click)

    def _check_dss(self):
        """检查DSS图像 - 根据当前显示目标的RA/DEC和FITS文件WCS角度信息下载DSS图像"""
        try:
            # 检查是否有当前显示的cutout
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.warning("请先执行差分检测并显示检测结果")
                return

            if not hasattr(self, '_current_cutout_index'):
                self.logger.warning("没有当前显示的检测结果")
                return

            # 获取当前cutout的信息
            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            reference_img = current_cutout['reference']
            aligned_img = current_cutout['aligned']
            detection_img = current_cutout['detection']

            # 提取文件信息（包含RA/DEC）
            selected_filename = ""
            if self.selected_file_path:
                selected_filename = os.path.basename(self.selected_file_path)

            file_info = self._extract_file_info(reference_img, aligned_img, detection_img, selected_filename)

            # 检查是否有RA/DEC信息
            if not file_info.get('ra') or not file_info.get('dec'):
                self.logger.error("无法获取目标的RA/DEC坐标信息")
                return

            ra = float(file_info['ra'])
            dec = float(file_info['dec'])

            self.logger.info(f"准备下载DSS图像: RA={ra}, Dec={dec}")

            # 获取FITS文件的旋转角度
            rotation_angle = self._get_fits_rotation_angle(detection_img)

            self.logger.info(f"FITS文件旋转角度: {rotation_angle}°")

            # 构建输出文件名
            # 使用当前检测结果的目录
            detection_dir = Path(detection_img).parent
            dss_filename = f"dss_ra{ra:.4f}_dec{dec:.4f}_rot{rotation_angle:.1f}.jpg"
            dss_output_path = detection_dir / dss_filename

            # 显示下载进度对话框
            progress_window = tk.Toplevel(self.parent_frame)
            progress_window.title("下载DSS图像")
            progress_window.geometry("400x120")
            progress_window.transient(self.parent_frame)
            progress_window.grab_set()

            ttk.Label(progress_window, text=f"正在下载DSS图像...", font=("Arial", 10)).pack(pady=10)
            ttk.Label(progress_window, text=f"RA: {ra:.4f}°  Dec: {dec:.4f}°", font=("Arial", 9)).pack(pady=5)
            ttk.Label(progress_window, text=f"旋转角度: {rotation_angle:.1f}°", font=("Arial", 9)).pack(pady=5)

            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=tk.X)
            progress_bar.start(10)

            progress_window.update()

            # 下载DSS图像
            success = download_dss_rot(
                ra=ra,
                dec=dec,
                rotation=rotation_angle,
                out_file=str(dss_output_path),
                use_proxy=False
            )

            # 关闭进度对话框
            progress_bar.stop()
            progress_window.destroy()

            if success:
                self.logger.info(f"DSS图像下载成功: {dss_output_path}")

                # 将DSS图像添加到点击切换列表
                if hasattr(self, '_click_images') and self._click_images:
                    # 加载DSS图像
                    from PIL import Image
                    dss_img = Image.open(dss_output_path)
                    dss_array = np.array(dss_img)

                    # 添加到切换列表
                    self._click_images.append(dss_array)
                    self._click_image_names.append("DSS Image")

                    total_images = len(self._click_images)
                    self.logger.info(f"DSS图像已添加到切换列表，当前共有 {total_images} 张图像")
                    self.logger.info(f"文件保存在: {dss_output_path}")

                    # 自动切换到DSS图像
                    self._click_index = total_images - 1  # 最后一张（DSS图像）
                    self._click_im.set_data(self._click_images[self._click_index])

                    # 更新标题
                    image_name = self._click_image_names[self._click_index]
                    self._click_ax.set_title(f"{image_name} ({self._click_index + 1}/{total_images}) - 点击切换",
                                           fontsize=10, fontweight='bold')

                    # 刷新画布
                    self.canvas.draw_idle()

                    self.logger.info(f"已自动切换到DSS图像显示")
                else:
                    self.logger.info(f"DSS图像下载成功，文件保存在: {dss_output_path}")
            else:
                self.logger.error("DSS图像下载失败，请检查网络连接")

        except Exception as e:
            self.logger.error(f"检查DSS失败: {str(e)}", exc_info=True)

    def _get_fits_rotation_angle(self, fits_path):
        """
        从FITS文件的WCS信息中提取旋转角度

        Args:
            fits_path: FITS文件路径（可以是cutout图像路径）

        Returns:
            float: 旋转角度（度），如果无法获取则返回0
        """
        try:
            # 查找对应的原始FITS文件
            detection_dir = Path(fits_path).parent.parent
            self.logger.info(f"cutout文件路径: {fits_path}")
            self.logger.info(f"detection目录: {detection_dir}")

            # 尝试多个可能的FITS文件位置
            fits_files = []

            # 1. detection目录的上级目录（下载目录）- 优先查找原始文件
            parent_dir = detection_dir.parent
            self.logger.info(f"查找FITS文件的目录: {parent_dir}")

            # 查找所有FITS文件
            all_parent_fits = list(parent_dir.glob("*.fits")) + list(parent_dir.glob("*.fit"))
            self.logger.info(f"在 {parent_dir} 找到 {len(all_parent_fits)} 个FITS文件")

            # 优先级1: 查找 *_noise_cleaned_aligned.fits 文件（处理后但未stretched）
            noise_cleaned_aligned = [f for f in all_parent_fits
                                    if 'noise_cleaned_aligned' in f.name.lower()
                                    and 'stretched' not in f.name.lower()]

            # 优先级2: 查找原始FITS文件（不含任何处理标记）
            original_fits = [f for f in all_parent_fits
                           if not any(marker in f.name.lower()
                                    for marker in ['noise_cleaned', 'aligned', 'stretched', 'diff', 'detection'])]

            if noise_cleaned_aligned:
                fits_files.extend(noise_cleaned_aligned)
                self.logger.info(f"找到 {len(noise_cleaned_aligned)} 个 noise_cleaned_aligned FITS文件:")
                for f in noise_cleaned_aligned:
                    self.logger.info(f"  - {f.name}")
            elif original_fits:
                fits_files.extend(original_fits)
                self.logger.info(f"找到 {len(original_fits)} 个原始FITS文件:")
                for f in original_fits:
                    self.logger.info(f"  - {f.name}")
            else:
                # 如果都没有，使用所有FITS文件
                fits_files.extend(all_parent_fits)
                self.logger.info(f"未找到优先文件，使用所有FITS文件: {len(all_parent_fits)} 个")
                for f in all_parent_fits:
                    self.logger.info(f"  - {f.name}")

            # 2. detection目录本身（作为备选）
            if not fits_files:
                self.logger.info(f"在父目录未找到，尝试detection目录: {detection_dir}")
                fits_files.extend(list(detection_dir.glob("*.fits")))
                fits_files.extend(list(detection_dir.glob("*.fit")))
                self.logger.info(f"在detection目录找到 {len(fits_files)} 个FITS文件")

            if not fits_files:
                self.logger.warning(f"未找到FITS文件，使用默认旋转角度0")
                return 0.0

            # 使用第一个找到的FITS文件
            fits_file = fits_files[0]
            self.logger.info(f"选择FITS文件: {fits_file}")
            self.logger.info(f"读取FITS文件WCS信息: {fits_file.name}")

            with fits.open(fits_file) as hdul:
                header = hdul[0].header

                rotation = None

                # 方法1: 优先尝试从CROTA2关键字读取（最直接的方法）
                if 'CROTA2' in header:
                    rotation = float(header['CROTA2'])
                    self.logger.info(f"从CROTA2读取旋转角度: {rotation:.2f}°")
                elif 'CROTA1' in header:
                    rotation = float(header['CROTA1'])
                    self.logger.info(f"从CROTA1读取旋转角度: {rotation:.2f}°")

                # 方法2: 如果没有CROTA，尝试从CD矩阵计算
                if rotation is None and 'CD1_1' in header and 'CD1_2' in header:
                    cd1_1 = float(header['CD1_1'])
                    cd1_2 = float(header['CD1_2'])
                    cd2_1 = float(header.get('CD2_1', 0))
                    cd2_2 = float(header.get('CD2_2', 0))

                    self.logger.info(f"CD矩阵: [[{cd1_1:.6e}, {cd1_2:.6e}], [{cd2_1:.6e}, {cd2_2:.6e}]]")

                    # 检查是否有翻转
                    flip_x = cd1_1 < 0
                    flip_y = cd2_2 < 0

                    if flip_x:
                        self.logger.warning("CD1_1 < 0: X轴被翻转")
                    if flip_y:
                        self.logger.warning("CD2_2 < 0: Y轴被翻转")

                    # 计算旋转角度时，使用绝对值来消除翻转的影响
                    # 翻转不是旋转，应该分开处理
                    cd1_1_abs = abs(cd1_1)
                    cd2_2_abs = abs(cd2_2)

                    rotation = np.arctan2(cd1_2, cd1_1_abs) * 180 / np.pi
                    self.logger.info(f"从CD矩阵计算得到旋转角度（已消除翻转影响）: {rotation:.2f}°")

                    # 如果有翻转，记录但不影响旋转角度
                    if flip_x or flip_y:
                        self.logger.info(f"注意：图像有翻转（X={flip_x}, Y={flip_y}），但旋转角度已正确提取")

                # 方法3: 如果CD矩阵也没有，尝试使用WCS的PC矩阵
                if rotation is None:
                    try:
                        from astropy.wcs import WCS
                        wcs = WCS(header)

                        # 获取PC矩阵（或CD矩阵）
                        pc = wcs.wcs.get_pc()

                        self.logger.info(f"PC矩阵: [[{pc[0,0]:.6f}, {pc[0,1]:.6f}], [{pc[1,0]:.6f}, {pc[1,1]:.6f}]]")

                        # 检查翻转
                        flip_x = pc[0, 0] < 0
                        flip_y = pc[1, 1] < 0

                        if flip_x:
                            self.logger.warning("PC[0,0] < 0: X轴被翻转")
                        if flip_y:
                            self.logger.warning("PC[1,1] < 0: Y轴被翻转")

                        # 使用绝对值消除翻转影响
                        pc00_abs = abs(pc[0, 0])
                        rotation = np.arctan2(pc[0, 1], pc00_abs) * 180 / np.pi
                        self.logger.info(f"从WCS PC矩阵计算得到旋转角度（已消除翻转影响）: {rotation:.2f}°")

                        if flip_x or flip_y:
                            self.logger.info(f"注意：图像有翻转（X={flip_x}, Y={flip_y}），但旋转角度已正确提取")

                    except Exception as wcs_error:
                        self.logger.warning(f"WCS方法失败: {wcs_error}")

                # 如果所有方法都失败，使用默认值0
                if rotation is None:
                    self.logger.warning("无法从header获取旋转角度，使用默认值0")
                    return 0.0

                # 归一化角度到 [-180, 180) 范围（天文学常用范围）
                while rotation > 180:
                    rotation -= 360
                while rotation <= -180:
                    rotation += 360

                self.logger.info(f"最终使用的旋转角度: {rotation:.2f}°")

                return rotation

        except Exception as e:
            self.logger.error(f"获取旋转角度失败: {str(e)}")
            return 0.0


