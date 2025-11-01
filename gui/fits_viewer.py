#!/usr/bin/env python3
"""
FITS图像查看器
用于显示和分析FITS文件
"""

import os
import sys
import re
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
from datetime import datetime, timedelta
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
                 get_url_selections_callback: Optional[Callable] = None,
                 log_callback: Optional[Callable] = None,
                 file_selection_frame: Optional[tk.Frame] = None):
        self.parent_frame = parent_frame
        self.file_selection_frame = file_selection_frame  # 文件选择框架，用于添加按钮
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
        self.log_callback = log_callback  # 日志回调函数，用于输出到日志标签页

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

        # 初始化查询结果存储（已废弃，改用cutout字典存储）
        # 保留这些变量以兼容旧代码
        self._skybot_query_results = None
        self._vsx_query_results = None
        self._skybot_queried = False
        self._vsx_queried = False

        # 创建界面
        self._create_widgets()

        # 从配置文件加载批量处理参数到控件
        self._load_batch_settings()

        # 绑定控件变化事件，自动保存到配置文件
        self._bind_batch_settings_events()

        # 从配置文件加载DSS翻转设置
        self._load_dss_flip_settings()

        # 绑定DSS翻转设置变化事件
        self._bind_dss_flip_settings_events()

        # 从配置文件加载GPS设置
        self._load_gps_settings()

        # 绑定GPS设置变化事件
        self._bind_gps_settings_events()

        # 从配置文件加载MPC代码设置
        self._load_mpc_settings()

        # 从配置文件加载查询设置
        self._load_query_settings()

        # 从配置文件加载检测过滤设置
        self._load_detection_filter_settings()

        # 绑定检测过滤设置变化事件
        self._bind_detection_filter_settings_events()

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

        # 如果有文件选择框架，将文件信息标签、显示图像、打开下载目录、检查WCS按钮添加到其中
        if self.file_selection_frame:
            # 文件信息标签
            self.file_info_label = ttk.Label(self.file_selection_frame, text="未选择文件")
            self.file_info_label.pack(side=tk.LEFT, padx=(20, 0))

            # 显示图像按钮
            self.display_button = ttk.Button(self.file_selection_frame, text="显示图像",
                                           command=self._display_selected_image, state="disabled")
            self.display_button.pack(side=tk.LEFT, padx=(10, 0))

            # 打开目录按钮
            self.open_dir_button = ttk.Button(self.file_selection_frame, text="打开下载目录",
                                            command=self._open_download_directory)
            self.open_dir_button.pack(side=tk.LEFT, padx=(10, 0))

            # WCS检查按钮
            self.wcs_check_button = ttk.Button(self.file_selection_frame, text="检查WCS",
                                             command=self._check_directory_wcs, state="disabled")
            self.wcs_check_button.pack(side=tk.LEFT, padx=(10, 0))

            # 如果WCS检查器不可用，禁用按钮
            if not self.wcs_checker:
                self.wcs_check_button.config(state="disabled", text="WCS检查不可用")
        else:
            # 如果没有文件选择框架，创建一个独立的第一行工具栏来放置这些按钮
            toolbar_frame0 = ttk.Frame(toolbar_container)
            toolbar_frame0.pack(fill=tk.X, pady=(0, 2))

            # 文件信息标签
            self.file_info_label = ttk.Label(toolbar_frame0, text="未选择文件")
            self.file_info_label.pack(side=tk.LEFT)

            # 显示图像按钮
            self.display_button = ttk.Button(toolbar_frame0, text="显示图像",
                                           command=self._display_selected_image, state="disabled")
            self.display_button.pack(side=tk.LEFT, padx=(10, 0))

            # 打开目录按钮
            self.open_dir_button = ttk.Button(toolbar_frame0, text="打开下载目录",
                                            command=self._open_download_directory)
            self.open_dir_button.pack(side=tk.LEFT, padx=(10, 0))

            # WCS检查按钮
            self.wcs_check_button = ttk.Button(toolbar_frame0, text="检查WCS",
                                             command=self._check_directory_wcs, state="disabled")
            self.wcs_check_button.pack(side=tk.LEFT, padx=(10, 0))

            # 如果WCS检查器不可用，禁用按钮
            if not self.wcs_checker:
                self.wcs_check_button.config(state="disabled", text="WCS检查不可用")

        # 初始化高级设置变量（这些变量会在高级设置标签页中使用）
        self.outlier_var = tk.BooleanVar(value=False)  # 默认不选中outlier
        self.hot_cold_var = tk.BooleanVar(value=False)  # 默认不选中hot_cold
        self.adaptive_median_var = tk.BooleanVar(value=True)  # 默认选中adaptive_median
        self.remove_lines_var = tk.BooleanVar(value=True)  # 默认选中去除亮线
        self.alignment_var = tk.StringVar(value="wcs")  # 默认选择wcs
        self.jaggedness_ratio_var = tk.StringVar(value="2.0")
        self.detection_method_var = tk.StringVar(value="contour")
        self.score_threshold_var = tk.StringVar(value="3.0")
        self.aligned_snr_threshold_var = tk.StringVar(value="1.1")
        self.sort_by_var = tk.StringVar(value="aligned_snr")

        # 初始化GPS和MPC变量（这些变量会在高级设置标签页中使用）
        self.gps_lat_var = tk.StringVar(value="43.4")
        self.gps_lon_var = tk.StringVar(value="87.1")
        self.mpc_code_var = tk.StringVar(value="N87")

        # 第一行工具栏（图像统计信息）
        toolbar_frame1 = ttk.Frame(toolbar_container)
        toolbar_frame1.pack(fill=tk.X, pady=(0, 2))

        # 图像统计信息标签
        self.stats_label = ttk.Label(toolbar_frame1, text="")
        self.stats_label.pack(side=tk.LEFT)

        # 第二行工具栏（diff操作按钮）
        toolbar_frame2 = ttk.Frame(toolbar_container)
        toolbar_frame2.pack(fill=tk.X, pady=(2, 0))

        # diff操作按钮
        self.diff_button = ttk.Button(toolbar_frame2, text="执行Diff",
                                    command=self._execute_diff, state="disabled")
        self.diff_button.pack(side=tk.LEFT, padx=(0, 0))

        # WCS稀疏采样优化选项（放在执行Diff按钮后面）
        self.wcs_sparse_var = tk.BooleanVar(value=False)  # 默认不启用稀疏采样
        self.wcs_sparse_checkbox = ttk.Checkbutton(toolbar_frame2, text="WCS稀疏采样",
                                                   variable=self.wcs_sparse_var)
        self.wcs_sparse_checkbox.pack(side=tk.LEFT, padx=(10, 0))

        # 生成GIF选项（放在WCS稀疏采样后面）
        self.generate_gif_var = tk.BooleanVar(value=False)  # 默认不生成GIF
        self.generate_gif_checkbox = ttk.Checkbutton(toolbar_frame2, text="生成GIF图像",
                                                     variable=self.generate_gif_var)
        self.generate_gif_checkbox.pack(side=tk.LEFT, padx=(10, 0))

        # ASTAP处理按钮
        self.astap_button = ttk.Button(toolbar_frame2, text="执行ASTAP",
                                     command=self._execute_astap, state="disabled")
        self.astap_button.pack(side=tk.LEFT, padx=(10, 0))

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
        self.check_dss_button.pack(side=tk.LEFT, padx=(0, 5))

        # DSS翻转选项（使用Checkbutton）
        self.flip_dss_vertical_var = tk.BooleanVar(value=True)  # 默认选中
        self.flip_dss_vertical_check = ttk.Checkbutton(toolbar_frame3, text="上下翻转DSS",
                                                       variable=self.flip_dss_vertical_var,
                                                       command=self._on_flip_dss_config_changed)
        self.flip_dss_vertical_check.pack(side=tk.LEFT, padx=(0, 5))

        self.flip_dss_horizontal_var = tk.BooleanVar(value=False)  # 默认不选中
        self.flip_dss_horizontal_check = ttk.Checkbutton(toolbar_frame3, text="左右翻转DSS",
                                                         variable=self.flip_dss_horizontal_var,
                                                         command=self._on_flip_dss_config_changed)
        self.flip_dss_horizontal_check.pack(side=tk.LEFT, padx=(0, 0))

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

        # 时间显示区域（第五行工具栏）
        toolbar_frame5 = ttk.Frame(toolbar_container)
        toolbar_frame5.pack(fill=tk.X, pady=2)

        # UTC时间
        ttk.Label(toolbar_frame5, text="UTC:").pack(side=tk.LEFT, padx=(5, 2))
        self.time_utc_entry = ttk.Entry(toolbar_frame5, width=20)
        self.time_utc_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 北京时间
        ttk.Label(toolbar_frame5, text="北京时间:").pack(side=tk.LEFT, padx=(5, 2))
        self.time_beijing_entry = ttk.Entry(toolbar_frame5, width=20)
        self.time_beijing_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 本地时区时间（根据GPS计算）
        ttk.Label(toolbar_frame5, text="本地时间:").pack(side=tk.LEFT, padx=(5, 2))
        self.time_local_entry = ttk.Entry(toolbar_frame5, width=20)
        self.time_local_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 时区显示标签（需要保留，用于显示计算的时区）
        ttk.Label(toolbar_frame5, text="时区:").pack(side=tk.LEFT, padx=(10, 2))
        self.timezone_label = ttk.Label(toolbar_frame5, text="UTC+6", foreground="blue")
        self.timezone_label.pack(side=tk.LEFT, padx=(0, 5))

        # 卫星查询按钮 (使用tk.Button以支持背景色)
        self.satellite_button = tk.Button(toolbar_frame5, text="查询卫星",
                                         command=self._query_satellite, state="disabled",
                                         bg="#FFA500", relief=tk.RAISED, padx=5, pady=2)  # 默认橙黄色(未查询)
        self.satellite_button.pack(side=tk.LEFT, padx=(10, 5))

        # 卫星查询结果显示
        ttk.Label(toolbar_frame5, text="卫星:").pack(side=tk.LEFT, padx=(5, 2))
        self.satellite_result_label = ttk.Label(toolbar_frame5, text="未查询", foreground="gray")
        self.satellite_result_label.pack(side=tk.LEFT, padx=(0, 5))

        # 查询设置和结果显示（第六行工具栏）
        toolbar_frame6 = ttk.Frame(toolbar_container)
        toolbar_frame6.pack(fill=tk.X, pady=2)

        # 搜索半径设置
        ttk.Label(toolbar_frame6, text="搜索半径(°):").pack(side=tk.LEFT, padx=(5, 2))
        self.search_radius_var = tk.StringVar(value="0.01")
        self.search_radius_entry = ttk.Entry(toolbar_frame6, textvariable=self.search_radius_var, width=6)
        self.search_radius_entry.pack(side=tk.LEFT, padx=(0, 5))

        # 保存搜索半径按钮
        self.save_search_radius_button = ttk.Button(toolbar_frame6, text="保存半径",
                                                   command=self._save_query_settings)
        self.save_search_radius_button.pack(side=tk.LEFT, padx=(0, 10))

        # 批量查询按钮
        self.batch_query_button = ttk.Button(toolbar_frame6, text="批量查询",
                                            command=self._batch_query_asteroids_and_variables,
                                            state="disabled")
        self.batch_query_button.pack(side=tk.LEFT, padx=(5, 5))

        # 批量删除查询结果按钮
        self.batch_delete_query_button = ttk.Button(toolbar_frame6, text="删除查询结果",
                                                    command=self._batch_delete_query_results,
                                                    state="disabled")
        self.batch_delete_query_button.pack(side=tk.LEFT, padx=(0, 5))

        # Skybot查询按钮 (使用tk.Button以支持背景色)
        self.skybot_button = tk.Button(toolbar_frame6, text="查询小行星(Skybot)",
                                       command=self._query_skybot, state="disabled",
                                       bg="#FFA500", relief=tk.RAISED, padx=5, pady=2)  # 默认橙黄色(未查询)
        self.skybot_button.pack(side=tk.LEFT, padx=(5, 5))

        # Skybot查询结果显示
        ttk.Label(toolbar_frame6, text="查询结果:").pack(side=tk.LEFT, padx=(5, 2))
        self.skybot_result_label = ttk.Label(toolbar_frame6, text="未查询", foreground="gray")
        self.skybot_result_label.pack(side=tk.LEFT, padx=(0, 5))

        # 变星星等限制
        ttk.Label(toolbar_frame6, text="变星星等≤:").pack(side=tk.LEFT, padx=(10, 2))
        self.vsx_mag_limit_var = tk.StringVar(value="20.0")
        self.vsx_mag_limit_entry = ttk.Entry(toolbar_frame6, textvariable=self.vsx_mag_limit_var, width=6)
        self.vsx_mag_limit_entry.pack(side=tk.LEFT, padx=(0, 5))

        # 变星查询按钮 (使用tk.Button以支持背景色)
        self.vsx_button = tk.Button(toolbar_frame6, text="查询变星(VSX)",
                                     command=self._query_vsx, state="disabled",
                                     bg="#FFA500", relief=tk.RAISED, padx=5, pady=2)  # 默认橙黄色(未查询)
        self.vsx_button.pack(side=tk.LEFT, padx=(5, 5))

        # 变星查询结果显示
        ttk.Label(toolbar_frame6, text="变星:").pack(side=tk.LEFT, padx=(5, 2))
        self.vsx_result_label = ttk.Label(toolbar_frame6, text="未查询", foreground="gray")
        self.vsx_result_label.pack(side=tk.LEFT, padx=(0, 5))

        # 保存检测结果按钮
        self.save_detection_button = ttk.Button(toolbar_frame6, text="保存检测结果",
                                               command=self._save_detection_result, state="disabled")
        self.save_detection_button.pack(side=tk.LEFT, padx=(10, 5))

        # 如果ASTAP处理器不可用，禁用按钮
        if not self.astap_processor:
            self.astap_button.config(state="disabled", text="ASTAP不可用")

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
        ttk.Button(refresh_frame, text="跳转未查询", command=self._jump_to_next_unqueried).pack(side=tk.LEFT, padx=(5, 0))

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

        # 中心距离过滤设置
        self.enable_center_distance_filter_var = tk.BooleanVar(value=False)
        self.enable_center_distance_filter_checkbox = ttk.Checkbutton(
            control_frame1,
            text="启用中心距离过滤",
            variable=self.enable_center_distance_filter_var,
            command=self._on_enable_center_distance_filter_change
        )
        self.enable_center_distance_filter_checkbox.pack(side=tk.LEFT, padx=(10, 5))

        ttk.Label(control_frame1, text="最大距离:").pack(side=tk.LEFT, padx=(5, 5))
        self.max_center_distance_var = tk.StringVar(value="2400")
        self.max_center_distance_entry = ttk.Entry(control_frame1, textvariable=self.max_center_distance_var, width=8)
        self.max_center_distance_entry.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(control_frame1, text="像素").pack(side=tk.LEFT, padx=(0, 5))

        # 当前检测目标的中心距离显示
        ttk.Label(control_frame1, text="当前距离:").pack(side=tk.LEFT, padx=(10, 5))
        self.current_center_distance_label = ttk.Label(control_frame1, text="--", foreground="blue", font=("Arial", 9, "bold"))
        self.current_center_distance_label.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(control_frame1, text="像素").pack(side=tk.LEFT, padx=(0, 5))

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
            # 映射配置文件中的值到GUI选项
            alignment_mapping = {
                'orb': 'rigid',
                'ecc': 'wcs',
                'astropy_reproject': 'astropy_reproject',
                'swarp': 'swarp'
            }
            self.alignment_var.set(alignment_mapping.get(alignment_method, 'rigid'))

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

            # 锯齿比率
            max_jaggedness_ratio = batch_settings.get('max_jaggedness_ratio', 2.0)
            self.jaggedness_ratio_var.set(str(max_jaggedness_ratio))

            # 检测方法
            detection_method = batch_settings.get('detection_method', 'contour')
            self.detection_method_var.set(detection_method)

            # 综合得分阈值
            score_threshold = batch_settings.get('score_threshold', 3.0)
            self.score_threshold_var.set(str(score_threshold))

            # Aligned SNR阈值
            aligned_snr_threshold = batch_settings.get('aligned_snr_threshold', 1.1)
            self.aligned_snr_threshold_var.set(str(aligned_snr_threshold))

            # 排序方式
            sort_by = batch_settings.get('sort_by', 'quality_score')
            self.sort_by_var.set(sort_by)

            # WCS稀疏采样优化
            wcs_use_sparse = batch_settings.get('wcs_use_sparse', False)
            self.wcs_sparse_var.set(wcs_use_sparse)

            # 生成GIF选项
            generate_gif = batch_settings.get('generate_gif', False)
            self.generate_gif_var.set(generate_gif)

            self.logger.info(f"批量处理参数已加载到控件: 降噪={noise_method}, 对齐={alignment_method}, 去亮线={remove_bright_lines}, 快速模式={fast_mode}, 拉伸={stretch_method}, 百分位={percentile_low}%, 锯齿比率={max_jaggedness_ratio}, 检测方法={detection_method}, 综合得分阈值={score_threshold}, Aligned SNR阈值={aligned_snr_threshold}, 排序方式={sort_by}, WCS稀疏采样={wcs_use_sparse}, 生成GIF={generate_gif}")

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

            # 绑定锯齿比率输入框
            self.jaggedness_ratio_var.trace('w', self._on_jaggedness_ratio_change)

            # 绑定检测方法单选框
            self.detection_method_var.trace('w', self._on_batch_settings_change)

            # 绑定综合得分阈值输入框
            self.score_threshold_var.trace('w', self._on_score_threshold_change)

            # 绑定Aligned SNR阈值输入框
            self.aligned_snr_threshold_var.trace('w', self._on_aligned_snr_threshold_change)

            # 绑定排序方式下拉框
            self.sort_by_var.trace('w', self._on_batch_settings_change)

            # 绑定WCS稀疏采样复选框
            self.wcs_sparse_var.trace('w', self._on_batch_settings_change)

            # 绑定生成GIF复选框
            self.generate_gif_var.trace('w', self._on_batch_settings_change)

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

            # 确定对齐方式 - 映射GUI选项到配置文件值
            alignment_mapping = {
                'rigid': 'orb',
                'wcs': 'ecc',
                'astropy_reproject': 'astropy_reproject',
                'swarp': 'swarp'
            }
            alignment_method = alignment_mapping.get(self.alignment_var.get(), 'orb')

            # 确定拉伸方法
            stretch_method = 'percentile'
            if self.stretch_method_var.get() == 'peak':
                stretch_method = 'minmax'
            elif self.stretch_method_var.get() == 'percentile':
                stretch_method = 'percentile'

            # 获取检测方法
            detection_method = self.detection_method_var.get()

            # 获取排序方式
            sort_by = self.sort_by_var.get()

            # 获取WCS稀疏采样设置
            wcs_use_sparse = self.wcs_sparse_var.get()

            # 获取生成GIF设置
            generate_gif = self.generate_gif_var.get()

            # 保存到配置文件
            self.config_manager.update_batch_process_settings(
                noise_method=noise_method,
                alignment_method=alignment_method,
                remove_bright_lines=self.remove_lines_var.get(),
                fast_mode=self.fast_mode_var.get(),
                stretch_method=stretch_method,
                detection_method=detection_method,
                sort_by=sort_by,
                wcs_use_sparse=wcs_use_sparse,
                generate_gif=generate_gif
            )

            self.logger.info(f"批量处理参数已保存: 降噪={noise_method}, 对齐={alignment_method}, 去亮线={self.remove_lines_var.get()}, 快速模式={self.fast_mode_var.get()}, 拉伸={stretch_method}, 检测方法={detection_method}, 排序方式={sort_by}, WCS稀疏采样={wcs_use_sparse}, 生成GIF={generate_gif}")

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

    def _on_jaggedness_ratio_change(self, *args):
        """锯齿比率参数变化时保存到配置文件（延迟保存）"""
        if not self.config_manager:
            return

        # 取消之前的延迟保存任务
        if hasattr(self, '_jaggedness_save_timer'):
            self.parent_frame.after_cancel(self._jaggedness_save_timer)

        # 设置新的延迟保存任务（1秒后保存）
        self._jaggedness_save_timer = self.parent_frame.after(1000, self._save_jaggedness_ratio)

    def _save_jaggedness_ratio(self):
        """保存锯齿比率参数到配置文件"""
        if not self.config_manager:
            return

        try:
            max_jaggedness_ratio = float(self.jaggedness_ratio_var.get())
            self.config_manager.update_batch_process_settings(max_jaggedness_ratio=max_jaggedness_ratio)
            self.logger.info(f"锯齿比率参数已保存: {max_jaggedness_ratio}")
        except ValueError:
            self.logger.warning(f"无效的锯齿比率值: {self.jaggedness_ratio_var.get()}")
        except Exception as e:
            self.logger.error(f"保存锯齿比率参数失败: {str(e)}")

    def _on_score_threshold_change(self, *args):
        """综合得分阈值参数变化时保存到配置文件（延迟保存）"""
        if not self.config_manager:
            return

        # 取消之前的延迟保存任务
        if hasattr(self, '_score_save_timer'):
            self.parent_frame.after_cancel(self._score_save_timer)

        # 设置新的延迟保存任务（1秒后保存）
        self._score_save_timer = self.parent_frame.after(1000, self._save_score_threshold)

    def _save_score_threshold(self):
        """保存综合得分阈值参数到配置文件"""
        if not self.config_manager:
            return

        try:
            score_threshold = float(self.score_threshold_var.get())
            self.config_manager.update_batch_process_settings(score_threshold=score_threshold)
            self.logger.info(f"综合得分阈值参数已保存: {score_threshold}")
        except ValueError:
            self.logger.warning(f"无效的综合得分阈值值: {self.score_threshold_var.get()}")
        except Exception as e:
            self.logger.error(f"保存综合得分阈值参数失败: {str(e)}")

    def _on_aligned_snr_threshold_change(self, *args):
        """Aligned SNR阈值参数变化时保存到配置文件（延迟保存）"""
        if not self.config_manager:
            return

        # 取消之前的延迟保存任务
        if hasattr(self, '_aligned_snr_save_timer'):
            self.parent_frame.after_cancel(self._aligned_snr_save_timer)

        # 设置新的延迟保存任务（1秒后保存）
        self._aligned_snr_save_timer = self.parent_frame.after(1000, self._save_aligned_snr_threshold)

    def _save_aligned_snr_threshold(self):
        """保存Aligned SNR阈值参数到配置文件"""
        if not self.config_manager:
            return

        try:
            aligned_snr_threshold = float(self.aligned_snr_threshold_var.get())
            self.config_manager.update_batch_process_settings(aligned_snr_threshold=aligned_snr_threshold)
            self.logger.info(f"Aligned SNR阈值参数已保存: {aligned_snr_threshold}")
        except ValueError:
            self.logger.warning(f"无效的Aligned SNR阈值值: {self.aligned_snr_threshold_var.get()}")
        except Exception as e:
            self.logger.error(f"保存Aligned SNR阈值参数失败: {str(e)}")

    def _load_dss_flip_settings(self):
        """从配置文件加载DSS翻转设置"""
        if not self.config_manager:
            return

        try:
            dss_settings = self.config_manager.get_dss_flip_settings()

            # 加载翻转设置，默认值：上下翻转=True，左右翻转=False
            flip_vertical = dss_settings.get('flip_vertical', True)
            flip_horizontal = dss_settings.get('flip_horizontal', False)

            self.flip_dss_vertical_var.set(flip_vertical)
            self.flip_dss_horizontal_var.set(flip_horizontal)

            self.logger.info(f"DSS翻转设置已加载: 上下翻转={flip_vertical}, 左右翻转={flip_horizontal}")

        except Exception as e:
            self.logger.error(f"加载DSS翻转设置失败: {str(e)}")
            # 使用默认值
            self.flip_dss_vertical_var.set(True)
            self.flip_dss_horizontal_var.set(False)

    def _bind_dss_flip_settings_events(self):
        """绑定DSS翻转设置的变化事件"""
        if not self.config_manager:
            return

        try:
            # 绑定翻转复选框
            self.flip_dss_vertical_var.trace('w', self._on_flip_dss_config_changed)
            self.flip_dss_horizontal_var.trace('w', self._on_flip_dss_config_changed)

            self.logger.info("DSS翻转设置事件已绑定")

        except Exception as e:
            self.logger.error(f"绑定DSS翻转设置事件失败: {str(e)}")

    def _on_flip_dss_config_changed(self, *args):
        """DSS翻转设置变化时保存到配置文件并应用翻转"""
        if not self.config_manager:
            return

        try:
            # 保存到配置文件
            self.config_manager.update_dss_flip_settings(
                flip_vertical=self.flip_dss_vertical_var.get(),
                flip_horizontal=self.flip_dss_horizontal_var.get()
            )

            self.logger.info(f"DSS翻转设置已保存: 上下翻转={self.flip_dss_vertical_var.get()}, 左右翻转={self.flip_dss_horizontal_var.get()}")

            # 如果已经有DSS图像，应用翻转
            self._apply_dss_flip()

        except Exception as e:
            self.logger.error(f"保存DSS翻转设置失败: {str(e)}")

    def _load_gps_settings(self):
        """从配置文件加载GPS设置"""
        if not self.config_manager:
            return

        try:
            gps_settings = self.config_manager.get_gps_settings()

            # 加载GPS坐标，默认值：43.4 N, 87.1 E
            latitude = gps_settings.get('latitude', 43.4)
            longitude = gps_settings.get('longitude', 87.1)

            self.gps_lat_var.set(str(latitude))
            self.gps_lon_var.set(str(longitude))

            # 更新时区显示
            self._update_timezone_display()

            self.logger.info(f"GPS设置已加载: 纬度={latitude}°N, 经度={longitude}°E")

        except Exception as e:
            self.logger.error(f"加载GPS设置失败: {str(e)}")
            # 使用默认值
            self.gps_lat_var.set("43.4")
            self.gps_lon_var.set("87.1")
            self._update_timezone_display()

    def _bind_gps_settings_events(self):
        """绑定GPS设置的变化事件"""
        try:
            # 绑定GPS输入框变化事件（实时更新时区显示）
            self.gps_lat_var.trace('w', self._on_gps_changed)
            self.gps_lon_var.trace('w', self._on_gps_changed)

            self.logger.info("GPS设置事件已绑定")

        except Exception as e:
            self.logger.error(f"绑定GPS设置事件失败: {str(e)}")

    def _on_gps_changed(self, *args):
        """GPS坐标变化时更新时区显示"""
        self._update_timezone_display()

    def _save_gps_settings(self):
        """保存GPS设置到配置文件"""
        if not self.config_manager:
            return

        try:
            latitude = float(self.gps_lat_var.get())
            longitude = float(self.gps_lon_var.get())

            # 保存到配置文件
            self.config_manager.update_gps_settings(
                latitude=latitude,
                longitude=longitude
            )

            self.logger.info(f"GPS设置已保存: 纬度={latitude}°N, 经度={longitude}°E")

            # 更新时区显示
            self._update_timezone_display()

            # 如果有时间信息，重新计算本地时间
            if hasattr(self, '_current_utc_time') and self._current_utc_time:
                self._update_time_display_with_utc(self._current_utc_time)

        except ValueError:
            self.logger.error(f"无效的GPS坐标: 纬度={self.gps_lat_var.get()}, 经度={self.gps_lon_var.get()}")
        except Exception as e:
            self.logger.error(f"保存GPS设置失败: {str(e)}")

    def _update_timezone_display(self):
        """根据GPS经度更新时区显示"""
        try:
            longitude = float(self.gps_lon_var.get())

            # 根据经度计算时区（每15度一个时区）
            timezone_offset = round(longitude / 15)

            # 限制在合理范围内 [-12, +14]
            timezone_offset = max(-12, min(14, timezone_offset))

            # 更新时区标签
            timezone_text = f"UTC+{timezone_offset}" if timezone_offset >= 0 else f"UTC{timezone_offset}"
            self.timezone_label.config(text=timezone_text)

            # 同时更新高级设置标签页中的时区显示（如果存在）
            if hasattr(self, 'parent_frame') and hasattr(self.parent_frame.master.master, 'advanced_timezone_label'):
                try:
                    self.parent_frame.master.master.advanced_timezone_label.config(text=timezone_text)
                except:
                    pass  # 如果高级设置标签页还未创建，忽略错误

            self.logger.info(f"时区已更新: 经度={longitude}°E → UTC{timezone_offset:+d}")

        except ValueError:
            self.timezone_label.config(text="UTC+?")
            self.logger.warning(f"无效的经度值: {self.gps_lon_var.get()}")
        except Exception as e:
            self.logger.error(f"更新时区显示失败: {str(e)}")

    def _load_mpc_settings(self):
        """从配置文件加载MPC代码设置"""
        if not self.config_manager:
            return

        try:
            mpc_settings = self.config_manager.get_mpc_settings()

            # 加载MPC代码，默认值：N87
            mpc_code = mpc_settings.get('mpc_code', 'N87')

            self.mpc_code_var.set(mpc_code)

            self.logger.info(f"MPC代码设置已加载: {mpc_code}")

        except Exception as e:
            self.logger.error(f"加载MPC代码设置失败: {str(e)}")
            # 使用默认值
            self.mpc_code_var.set("N87")

    def _save_mpc_settings(self):
        """保存MPC代码设置到配置文件"""
        if not self.config_manager:
            return

        try:
            mpc_code = self.mpc_code_var.get().strip().upper()

            if not mpc_code:
                self.logger.error("MPC代码不能为空")
                return

            # 保存到配置文件
            self.config_manager.update_mpc_settings(mpc_code=mpc_code)

            self.logger.info(f"MPC代码设置已保存: {mpc_code}")

        except Exception as e:
            self.logger.error(f"保存MPC代码设置失败: {str(e)}")

    def _load_query_settings(self):
        """从配置文件加载查询设置"""
        if not self.config_manager:
            return

        try:
            query_settings = self.config_manager.get_query_settings()

            # 加载搜索半径，默认值：0.01度
            search_radius = query_settings.get('search_radius', 0.01)

            self.search_radius_var.set(str(search_radius))

            self.logger.info(f"查询设置已加载: 搜索半径={search_radius}°")

        except Exception as e:
            self.logger.error(f"加载查询设置失败: {str(e)}")
            # 使用默认值
            self.search_radius_var.set("0.01")

    def _save_query_settings(self):
        """保存查询设置到配置文件"""
        if not self.config_manager:
            return

        try:
            search_radius = float(self.search_radius_var.get())

            if search_radius <= 0:
                self.logger.error("搜索半径必须大于0")
                return

            # 保存到配置文件
            self.config_manager.update_query_settings(search_radius=search_radius)

            self.logger.info(f"查询设置已保存: 搜索半径={search_radius}°")

        except ValueError:
            self.logger.error(f"无效的搜索半径: {self.search_radius_var.get()}")
        except Exception as e:
            self.logger.error(f"保存查询设置失败: {str(e)}")

    def _load_detection_filter_settings(self):
        """从配置文件加载检测过滤设置"""
        if not self.config_manager:
            return

        try:
            filter_settings = self.config_manager.get_detection_filter_settings()

            # 加载是否启用中心距离过滤，默认值：False
            enable_filter = filter_settings.get('enable_center_distance_filter', False)
            self.enable_center_distance_filter_var.set(enable_filter)

            # 加载最大中心距离，默认值：2400像素
            max_center_distance = filter_settings.get('max_center_distance', 2400)
            self.max_center_distance_var.set(str(max_center_distance))

            # 加载自动启用阈值，默认值：50
            auto_enable_threshold = filter_settings.get('auto_enable_threshold', 50)
            self._auto_enable_threshold = auto_enable_threshold

            self.logger.info(f"检测过滤设置已加载: 启用过滤={enable_filter}, 最大中心距离={max_center_distance}像素, 自动启用阈值={auto_enable_threshold}")

        except Exception as e:
            self.logger.error(f"加载检测过滤设置失败: {str(e)}")
            # 使用默认值
            self.enable_center_distance_filter_var.set(False)
            self.max_center_distance_var.set("2400")
            self._auto_enable_threshold = 50

    def _bind_detection_filter_settings_events(self):
        """绑定检测过滤设置的变化事件"""
        if not self.config_manager:
            return

        try:
            # 绑定最大中心距离输入框（使用延迟保存）
            self.max_center_distance_var.trace('w', self._on_max_center_distance_change)

            self.logger.info("检测过滤设置事件已绑定")

        except Exception as e:
            self.logger.error(f"绑定检测过滤设置事件失败: {str(e)}")

    def _on_max_center_distance_change(self, *args):
        """最大中心距离参数变化时保存到配置文件（延迟保存）"""
        if not self.config_manager:
            return

        # 取消之前的延迟保存任务
        if hasattr(self, '_max_center_distance_save_timer'):
            self.parent_frame.after_cancel(self._max_center_distance_save_timer)

        # 设置新的延迟保存任务（1秒后保存）
        self._max_center_distance_save_timer = self.parent_frame.after(1000, self._save_max_center_distance)

    def _save_max_center_distance(self):
        """保存最大中心距离参数到配置文件"""
        if not self.config_manager:
            return

        try:
            max_center_distance = float(self.max_center_distance_var.get())

            if max_center_distance < 0:
                self.logger.warning(f"最大中心距离不能为负数: {max_center_distance}")
                return

            self.config_manager.update_detection_filter_settings(max_center_distance=max_center_distance)
            self.logger.info(f"最大中心距离参数已保存: {max_center_distance}像素")
        except ValueError:
            self.logger.warning(f"无效的最大中心距离值: {self.max_center_distance_var.get()}")
        except Exception as e:
            self.logger.error(f"保存最大中心距离参数失败: {str(e)}")

    def _on_enable_center_distance_filter_change(self):
        """启用/禁用中心距离过滤开关变化时保存到配置文件"""
        if not self.config_manager:
            return

        try:
            enable_filter = self.enable_center_distance_filter_var.get()
            self.config_manager.update_detection_filter_settings(enable_center_distance_filter=enable_filter)
            self.logger.info(f"中心距离过滤开关已{'启用' if enable_filter else '禁用'}")
        except Exception as e:
            self.logger.error(f"保存中心距离过滤开关状态失败: {str(e)}")

    def _get_high_score_count_from_current_detection(self):
        """从当前detection目录的analysis.txt文件中读取高分检测目标数量"""
        try:
            # 从第一个cutout获取detection目录路径
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                return None

            first_cutout = self._all_cutout_sets[0]
            detection_img = first_cutout.get('detection')
            if not detection_img:
                return None

            # detection图片路径: .../detection_xxx/cutouts/xxx_3_detection.png
            # detection目录路径: .../detection_xxx
            cutout_dir = Path(detection_img).parent
            detection_dir = cutout_dir.parent

            # 查找 analysis.txt 文件（支持带参数的长文件名）
            analysis_files = [f for f in detection_dir.iterdir()
                            if '_analysis' in f.name and f.suffix == '.txt']

            if not analysis_files:
                self.logger.warning(f"未找到analysis.txt文件: {detection_dir}")
                return None

            analysis_path = analysis_files[0]

            # 解析analysis.txt文件
            with open(analysis_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 获取配置的阈值和排序方式
            score_threshold = 3.0  # 默认综合得分阈值
            aligned_snr_threshold = 1.1  # 默认Aligned SNR阈值
            sort_by = 'aligned_snr'  # 默认排序方式
            if self.config_manager:
                try:
                    batch_settings = self.config_manager.get_batch_process_settings()
                    score_threshold = batch_settings.get('score_threshold', 3.0)
                    aligned_snr_threshold = batch_settings.get('aligned_snr_threshold', 1.1)
                    sort_by = batch_settings.get('sort_by', 'aligned_snr')
                except Exception:
                    pass

            # 解析每一行检测结果
            high_score_count = 0
            lines = content.split('\n')
            in_data_section = False
            for line in lines:
                line_stripped = line.strip()

                # 检测到分隔线后，下一行开始是数据
                if line_stripped.startswith('-' * 10):
                    in_data_section = True
                    continue

                # 跳过表头
                if '综合得分' in line or '序号' in line:
                    continue

                # 只在数据区域解析
                if in_data_section and line_stripped:
                    # 尝试解析数据行
                    parts = line_stripped.split()
                    if len(parts) >= 14:  # 需要至少14列才能读取Aligned中心7x7SNR
                        try:
                            # 第一列是序号，第二列是综合得分，第14列是Aligned中心7x7SNR
                            seq = int(parts[0])  # 验证第一列是数字
                            score = float(parts[1])
                            aligned_snr_str = parts[13]  # 第14列（索引13）

                            # 解析Aligned SNR（可能是数字或"N/A"）
                            aligned_snr = None
                            if aligned_snr_str != 'N/A':
                                try:
                                    aligned_snr = float(aligned_snr_str)
                                except ValueError:
                                    aligned_snr = None

                            # 根据排序方式决定判断条件
                            is_high_score = False
                            if sort_by == 'aligned_snr':
                                # 使用 aligned_snr 排序时，只判断 aligned_snr > 阈值
                                if aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                    is_high_score = True
                            else:
                                # 使用其他排序方式时，判断综合得分 > score_threshold 且 Aligned SNR > aligned_snr_threshold
                                if score > score_threshold and aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                    is_high_score = True

                            if is_high_score:
                                high_score_count += 1
                        except (ValueError, IndexError):
                            continue

            self.logger.info(f"从analysis.txt读取到高分检测目标数量: {high_score_count}")
            return high_score_count

        except Exception as e:
            self.logger.warning(f"读取高分检测目标数量失败: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    def _check_auto_enable_center_distance_filter(self):
        """检查是否需要自动启用/禁用中心距离过滤（根据高分检测目标数量）"""
        if not hasattr(self, '_auto_enable_threshold'):
            self._auto_enable_threshold = 50  # 默认阈值

        if not hasattr(self, '_total_cutouts'):
            return

        # 从当前detection目录的analysis.txt文件中读取高分检测目标数量
        high_score_count = self._get_high_score_count_from_current_detection()

        if high_score_count is None:
            # 如果无法读取高分数量，使用总检测数量作为后备方案
            self.logger.warning("无法读取高分检测目标数量，使用总检测数量作为后备方案")
            high_score_count = self._total_cutouts

        # 如果高分检测目标数量超过阈值，自动启用过滤
        if high_score_count > self._auto_enable_threshold:
            # 只在当前未启用时才自动启用
            if not self.enable_center_distance_filter_var.get():
                self.enable_center_distance_filter_var.set(True)
                self.logger.info(f"高分检测目标数量 ({high_score_count}) 超过阈值 ({self._auto_enable_threshold})，自动启用中心距离过滤")
                # 保存到配置文件
                if self.config_manager:
                    self.config_manager.update_detection_filter_settings(enable_center_distance_filter=True)
        else:
            # 如果高分检测目标数量不超过阈值，自动禁用过滤
            if self.enable_center_distance_filter_var.get():
                self.enable_center_distance_filter_var.set(False)
                self.logger.info(f"高分检测目标数量 ({high_score_count}) 不超过阈值 ({self._auto_enable_threshold})，自动禁用中心距离过滤")
                # 保存到配置文件
                if self.config_manager:
                    self.config_manager.update_detection_filter_settings(enable_center_distance_filter=False)

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
            self.directory_tree.tag_configure("diff_purple", foreground="#8B00FF")  # 蓝紫色（检测列表为空）
            self.directory_tree.tag_configure("diff_gold_red", foreground="#FF4500")  # 金红色（有高分检测）

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

            # 添加文件节点并检查diff结果
            for filename, file_path, file_size in fits_files:
                size_str = self._format_file_size(file_size)
                file_text = f"📄 {filename} ({size_str})"

                # 检查是否有diff结果并确定颜色标记
                file_tags = ["fits_file"]
                detection_info = self._check_file_diff_result(file_path, directory)

                if detection_info:
                    if detection_info['high_score_count'] > 0:
                        file_tags.append("diff_gold_red")
                        file_text = f"📄 [{detection_info['high_score_count']}] {filename} ({size_str})"
                    elif detection_info['is_empty']:
                        file_tags.append("diff_purple")
                    else:
                        file_tags.append("diff_blue")

                self.directory_tree.insert(parent_node, "end", text=file_text,
                                         values=(file_path,), tags=tuple(file_tags))

        except Exception as e:
            self.logger.error(f"添加FITS文件失败: {str(e)}")

    def _check_file_diff_result(self, file_path, region_dir):
        """
        检查单个文件是否有diff结果

        Args:
            file_path: FITS文件路径
            region_dir: 天区目录路径

        Returns:
            dict or None: 包含检测信息的字典，如果没有diff结果则返回None
                {
                    'has_result': bool,
                    'is_empty': bool,
                    'high_score_count': int,
                    'detection_count': int
                }
        """
        try:
            filename = os.path.basename(file_path)

            # 获取配置的输出目录
            base_output_dir = None
            if self.get_diff_output_dir_callback:
                base_output_dir = self.get_diff_output_dir_callback()

            if not base_output_dir or not os.path.exists(base_output_dir):
                return None

            # 从region_dir提取相对路径部分
            download_dir = None
            if self.get_download_dir_callback:
                download_dir = self.get_download_dir_callback()

            if not download_dir:
                return None

            # 标准化路径
            normalized_region_dir = os.path.normpath(region_dir)
            normalized_download_dir = os.path.normpath(download_dir)

            # 获取相对路径
            try:
                relative_path = os.path.relpath(normalized_region_dir, normalized_download_dir)
            except ValueError:
                return None

            # 构建输出目录路径
            output_region_dir = os.path.join(base_output_dir, relative_path)
            file_basename = os.path.splitext(filename)[0]
            potential_output_dir = os.path.join(output_region_dir, file_basename)

            # 检查是否存在detection目录
            if not os.path.exists(potential_output_dir) or not os.path.isdir(potential_output_dir):
                return None

            # 查找detection_开头的目录
            detection_dir_path = None
            try:
                items = os.listdir(potential_output_dir)
                for item_name in items:
                    item_path = os.path.join(potential_output_dir, item_name)
                    if os.path.isdir(item_path) and item_name.startswith('detection_'):
                        detection_dir_path = item_path
                        break
            except Exception:
                return None

            if not detection_dir_path:
                return None

            # 分析 analysis.txt 文件
            detection_count = 0
            high_score_count = 0
            is_empty_detection = False

            try:
                # 查找 analysis.txt 文件（支持带参数的长文件名）
                analysis_files = [f for f in os.listdir(detection_dir_path)
                                if '_analysis' in f and f.endswith('.txt')]

                if analysis_files:
                    analysis_path = os.path.join(detection_dir_path, analysis_files[0])

                    with open(analysis_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                        # 查找检测数量行
                        count_match = re.search(r'检测到\s+(\d+)\s+个斑点', content)
                        if count_match:
                            detection_count = int(count_match.group(1))

                            if detection_count == 0:
                                is_empty_detection = True
                            else:
                                # 获取配置的阈值和排序方式
                                score_threshold = 3.0  # 默认综合得分阈值
                                aligned_snr_threshold = 1.1  # 默认Aligned SNR阈值
                                sort_by = 'aligned_snr'  # 默认排序方式
                                if self.config_manager:
                                    try:
                                        batch_settings = self.config_manager.get_batch_process_settings()
                                        score_threshold = batch_settings.get('score_threshold', 3.0)
                                        aligned_snr_threshold = batch_settings.get('aligned_snr_threshold', 1.1)
                                        sort_by = batch_settings.get('sort_by', 'aligned_snr')
                                    except Exception:
                                        pass

                                # 解析每一行检测结果
                                lines = content.split('\n')
                                in_data_section = False
                                for line in lines:
                                    line_stripped = line.strip()

                                    # 检测到分隔线后，下一行开始是数据
                                    if line_stripped.startswith('-' * 10):
                                        in_data_section = True
                                        continue

                                    # 跳过表头
                                    if '综合得分' in line or '序号' in line:
                                        continue

                                    # 只在数据区域解析
                                    if in_data_section and line_stripped:
                                        # 尝试解析数据行
                                        parts = line_stripped.split()
                                        if len(parts) >= 14:  # 需要至少14列才能读取Aligned中心7x7SNR
                                            try:
                                                # 第一列是序号，第二列是综合得分，第14列是Aligned中心7x7SNR
                                                seq = int(parts[0])  # 验证第一列是数字
                                                score = float(parts[1])
                                                aligned_snr_str = parts[13]  # 第14列（索引13）

                                                # 解析Aligned SNR（可能是数字或"N/A"）
                                                aligned_snr = None
                                                if aligned_snr_str != 'N/A':
                                                    try:
                                                        aligned_snr = float(aligned_snr_str)
                                                    except ValueError:
                                                        aligned_snr = None

                                                # 根据排序方式决定判断条件
                                                is_high_score = False
                                                if sort_by == 'aligned_snr':
                                                    # 使用 aligned_snr 排序时，只判断 aligned_snr > 阈值
                                                    if aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                                        is_high_score = True
                                                else:
                                                    # 使用其他排序方式时，判断综合得分 > score_threshold 且 Aligned SNR > aligned_snr_threshold
                                                    if score > score_threshold and aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                                        is_high_score = True

                                                if is_high_score:
                                                    high_score_count += 1
                                            except (ValueError, IndexError):
                                                continue
            except Exception as e:
                # 记录异常但不中断
                import traceback
                self.logger.debug(f"解析analysis.txt异常: {e}\n{traceback.format_exc()}")
                pass

            return {
                'has_result': True,
                'is_empty': is_empty_detection,
                'high_score_count': high_score_count,
                'detection_count': detection_count
            }

        except Exception:
            return None

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
            self.batch_query_button.config(state="disabled")
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

            # 启用批量查询按钮（单个文件也支持批量查询其所有检测目标）
            self.batch_query_button.config(state="normal")
            # 启用批量删除查询结果按钮
            self.batch_delete_query_button.config(state="normal")
        else:
            # 选中的不是FITS文件（可能是目录）
            self.selected_file_path = None
            self.display_button.config(state="disabled")
            self.diff_button.config(state="disabled")
            if self.astap_processor:
                self.astap_button.config(state="disabled")
            if self.wcs_checker:
                self.wcs_check_button.config(state="disabled")

            # 检查是否选中了目录，如果是则启用批量查询按钮
            if values and any(tag in tags for tag in ["region", "date", "telescope"]):
                self.batch_query_button.config(state="normal")
                self.batch_delete_query_button.config(state="normal")
                self.file_info_label.config(text="已选择目录 [可批量查询]")
            else:
                self.batch_query_button.config(state="disabled")
                self.batch_delete_query_button.config(state="disabled")
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
                    detection_dir_path = None
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
                                    detection_dir_path = item_path
                                    self.logger.info(f"  ✓ 找到diff结果: {filename} -> {item_name}")
                                    break
                        except Exception as list_error:
                            self.logger.error(f"  列出目录内容失败: {list_error}")
                    else:
                        self.logger.debug(f"  输出目录不存在")

                    # 如果有diff结果，分析检测结果并标记颜色
                    if has_diff_result and detection_dir_path:
                        # 分析 analysis.txt 文件
                        detection_count = 0
                        high_score_count = 0
                        is_empty_detection = False

                        try:
                            # 查找 analysis.txt 文件（支持带参数的长文件名）
                            analysis_files = [f for f in os.listdir(detection_dir_path) if '_analysis' in f and f.endswith('.txt')]

                            if analysis_files:
                                analysis_path = os.path.join(detection_dir_path, analysis_files[0])
                                self.logger.info(f"  分析文件: {analysis_path}")

                                with open(analysis_path, 'r', encoding='utf-8') as f:
                                    content = f.read()

                                    # 查找检测数量行，例如："检测到 5 个斑点"
                                    count_match = re.search(r'检测到\s+(\d+)\s+个斑点', content)
                                    if count_match:
                                        detection_count = int(count_match.group(1))
                                        self.logger.info(f"  检测数量: {detection_count}")

                                        if detection_count == 0:
                                            is_empty_detection = True
                                        else:
                                            # 获取配置的阈值和排序方式
                                            score_threshold = 3.0  # 默认综合得分阈值
                                            aligned_snr_threshold = 1.1  # 默认Aligned SNR阈值
                                            sort_by = 'aligned_snr'  # 默认排序方式
                                            if self.config_manager:
                                                try:
                                                    batch_settings = self.config_manager.get_batch_process_settings()
                                                    score_threshold = batch_settings.get('score_threshold', 3.0)
                                                    aligned_snr_threshold = batch_settings.get('aligned_snr_threshold', 1.1)
                                                    sort_by = batch_settings.get('sort_by', 'aligned_snr')
                                                except Exception:
                                                    pass

                                            # 解析每一行检测结果
                                            # 格式: 序号 综合得分 面积 圆度 ... Aligned中心7x7SNR
                                            lines = content.split('\n')
                                            in_data_section = False
                                            for line in lines:
                                                line_stripped = line.strip()

                                                # 检测到分隔线后，下一行开始是数据
                                                if line_stripped.startswith('-' * 10):
                                                    in_data_section = True
                                                    continue

                                                # 跳过表头
                                                if '综合得分' in line or '序号' in line:
                                                    continue

                                                # 只在数据区域解析
                                                if in_data_section and line_stripped:
                                                    # 尝试解析数据行
                                                    parts = line_stripped.split()
                                                    if len(parts) >= 14:  # 需要至少14列才能读取Aligned中心7x7SNR
                                                        try:
                                                            # 第一列是序号，第二列是综合得分，第14列是Aligned中心7x7SNR
                                                            seq = int(parts[0])  # 验证第一列是数字
                                                            score = float(parts[1])
                                                            aligned_snr_str = parts[13]  # 第14列（索引13）

                                                            # 解析Aligned SNR（可能是数字或"N/A"）
                                                            aligned_snr = None
                                                            if aligned_snr_str != 'N/A':
                                                                try:
                                                                    aligned_snr = float(aligned_snr_str)
                                                                except ValueError:
                                                                    aligned_snr = None

                                                            # 根据排序方式决定判断条件
                                                            is_high_score = False
                                                            if sort_by == 'aligned_snr':
                                                                # 使用 aligned_snr 排序时，只判断 aligned_snr > 阈值
                                                                if aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                                                    is_high_score = True
                                                            else:
                                                                # 使用其他排序方式时，判断综合得分 > score_threshold 且 Aligned SNR > aligned_snr_threshold
                                                                if score > score_threshold and aligned_snr is not None and aligned_snr > aligned_snr_threshold:
                                                                    is_high_score = True

                                                            if is_high_score:
                                                                high_score_count += 1
                                                                self.logger.debug(f"    找到高分: 序号{seq}, 得分{score}, Aligned SNR{aligned_snr}")
                                                        except (ValueError, IndexError):
                                                            continue

                                            # 获取配置的阈值和排序方式用于日志显示
                                            score_threshold_for_log = 3.0
                                            aligned_snr_threshold_for_log = 1.1
                                            sort_by_for_log = 'aligned_snr'
                                            if self.config_manager:
                                                try:
                                                    batch_settings = self.config_manager.get_batch_process_settings()
                                                    score_threshold_for_log = batch_settings.get('score_threshold', 3.0)
                                                    aligned_snr_threshold_for_log = batch_settings.get('aligned_snr_threshold', 1.1)
                                                    sort_by_for_log = batch_settings.get('sort_by', 'aligned_snr')
                                                except Exception:
                                                    pass

                                            # 根据排序方式显示不同的日志信息
                                            if sort_by_for_log == 'aligned_snr':
                                                self.logger.info(f"  高分检测数量 (Aligned SNR>{aligned_snr_threshold_for_log}): {high_score_count}")
                                            else:
                                                self.logger.info(f"  高分检测数量 (综合得分>{score_threshold_for_log} 且 Aligned SNR>{aligned_snr_threshold_for_log}): {high_score_count}")
                            else:
                                self.logger.warning(f"  未找到 analysis.txt 文件")

                        except Exception as analysis_error:
                            self.logger.error(f"  分析检测结果失败: {analysis_error}")

                        # 根据分析结果标记颜色
                        current_tags = list(child_tags)
                        # 移除其他颜色标记
                        current_tags = [t for t in current_tags if t not in ["wcs_green", "wcs_orange", "diff_blue", "diff_purple", "diff_gold_red"]]

                        # 获取当前显示的文本
                        current_text = self.directory_tree.item(child, "text")
                        # 移除可能存在的数量前缀
                        current_text = re.sub(r'^\[\d+\]\s*', '', current_text)

                        if high_score_count > 0:
                            # 有高分检测，标记为金红色，并在前面加上数量
                            current_tags.append("diff_gold_red")
                            new_text = f"[{high_score_count}] {current_text}"
                            self.directory_tree.item(child, text=new_text, tags=current_tags)
                            self.logger.info(f"  ✓ 已标记为金红色: {filename}，高分检测数: {high_score_count}")
                        elif is_empty_detection:
                            # 检测列表为空，标记为蓝紫色
                            current_tags.append("diff_purple")
                            self.directory_tree.item(child, tags=current_tags)
                            self.logger.info(f"  ✓ 已标记为蓝紫色: {filename}（检测列表为空）")
                        else:
                            # 有检测但无高分，标记为蓝色
                            current_tags.append("diff_blue")
                            self.directory_tree.item(child, tags=current_tags)
                            self.logger.info(f"  ✓ 已标记为蓝色: {filename}")

                        marked_count += 1

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

    def _jump_to_next_unqueried(self):
        """跳转到下一个未查询小行星、变星、卫星的high_score检测结果"""
        try:
            # 检查是否有检测结果
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                messagebox.showinfo("提示", "当前没有检测结果")
                return

            if not hasattr(self, '_current_cutout_index'):
                messagebox.showinfo("提示", "请先显示检测结果")
                return

            # 获取high_score_count
            high_score_count = self._get_high_score_count_from_current_detection()
            if high_score_count is None or high_score_count == 0:
                messagebox.showinfo("提示", "当前文件没有高分检测目标")
                return

            # 只在high_score范围内查找
            max_index = min(high_score_count, len(self._all_cutout_sets))

            # 从当前索引的下一个开始查找
            start_index = self._current_cutout_index
            found_index = None

            # 循环查找
            for i in range(max_index):
                # 计算要检查的索引（从下一个开始，循环）
                check_index = (start_index + i + 1) % max_index

                # 临时设置当前索引以便检查查询结果
                original_index = self._current_cutout_index
                self._current_cutout_index = check_index

                # 检查三种查询结果
                skybot_queried, skybot_result = self._check_existing_query_results('skybot')
                vsx_queried, vsx_result = self._check_existing_query_results('vsx')
                satellite_queried, satellite_result = self._check_existing_query_results('satellite')

                # 恢复原索引
                self._current_cutout_index = original_index

                # 判断是否符合条件：三个都未找到（已查询但未找到，或未查询）
                skybot_not_found = (not skybot_queried) or (skybot_queried and skybot_result == "已查询，未找到")
                vsx_not_found = (not vsx_queried) or (vsx_queried and vsx_result == "已查询，未找到")
                satellite_not_found = (not satellite_queried) or (satellite_queried and satellite_result == "已查询，未找到")

                if skybot_not_found and vsx_not_found and satellite_not_found:
                    found_index = check_index
                    break

            if found_index is not None:
                # 跳转到找到的检测结果
                self._display_cutout_by_index(found_index)
                self.logger.info(f"跳转到检测目标 #{found_index + 1}（未查询或未找到小行星/变星/卫星）")
            else:
                messagebox.showinfo("提示", f"在前{max_index}个高分检测目标中，未找到符合条件的检测结果\n（条件：未查询或未找到小行星、变星、卫星）")

        except Exception as e:
            error_msg = f"跳转失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("错误", error_msg)

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

            # 获取锯齿比率参数
            max_jaggedness_ratio = 2.0  # 默认值
            try:
                max_jaggedness_ratio = float(self.jaggedness_ratio_var.get())
                if max_jaggedness_ratio <= 0:
                    raise ValueError("锯齿比率必须大于0")
                self.logger.info(f"锯齿比率: {max_jaggedness_ratio}")
            except ValueError as e:
                self.logger.warning(f"锯齿比率输入无效，使用默认值2.0: {e}")
                max_jaggedness_ratio = 2.0

            # 获取检测方法
            detection_method = self.detection_method_var.get()
            self.logger.info(f"检测方法: {detection_method}")

            # 获取排序方式
            sort_by = self.sort_by_var.get()
            self.logger.info(f"排序方式: {sort_by}")

            # 获取WCS稀疏采样设置
            wcs_use_sparse = self.wcs_sparse_var.get()
            self.logger.info(f"WCS稀疏采样: {'启用' if wcs_use_sparse else '禁用'}")

            # 获取生成GIF设置
            generate_gif = self.generate_gif_var.get()
            self.logger.info(f"生成GIF: {'启用' if generate_gif else '禁用'}")

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
                                              fast_mode=fast_mode,
                                              max_jaggedness_ratio=max_jaggedness_ratio,
                                              detection_method=detection_method,
                                              sort_by=sort_by,
                                              wcs_use_sparse=wcs_use_sparse,
                                              generate_gif=generate_gif)

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

        # 重置当前中心距离标签
        if hasattr(self, 'current_center_distance_label'):
            self.current_center_distance_label.config(text="--")

        # 禁用导航按钮
        if hasattr(self, 'prev_cutout_button'):
            self.prev_cutout_button.config(state="disabled")
        if hasattr(self, 'next_cutout_button'):
            self.next_cutout_button.config(state="disabled")
        if hasattr(self, 'check_dss_button'):
            self.check_dss_button.config(state="disabled")
        if hasattr(self, 'skybot_button'):
            self.skybot_button.config(state="disabled", bg="#FFA500")  # 重置为橙黄色(未查询)
            self.skybot_result_label.config(text="未查询", foreground="gray")
            self._skybot_query_results = None  # 清空查询结果
            self._skybot_queried = False  # 清空查询标记
        if hasattr(self, 'vsx_button'):
            self.vsx_button.config(state="disabled", bg="#FFA500")  # 重置为橙黄色(未查询)
            self.vsx_result_label.config(text="未查询", foreground="gray")
            self._vsx_query_results = None  # 清空查询结果
            self._vsx_queried = False  # 清空查询标记
        if hasattr(self, 'satellite_button'):
            self.satellite_button.config(state="disabled", bg="#FFA500")  # 重置为橙黄色(未查询)
            self.satellite_result_label.config(text="未查询", foreground="gray")
            self._satellite_query_results = None  # 清空查询结果
            self._satellite_queried = False  # 清空查询标记
        if hasattr(self, 'save_detection_button'):
            self.save_detection_button.config(state="disabled")

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
            self.directory_tree.tag_configure("diff_purple", foreground="#8B00FF")  # 蓝紫色（检测列表为空）
            self.directory_tree.tag_configure("diff_gold_red", foreground="#FF4500")  # 金红色（有高分检测）

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
                    'detection': str(det),
                    'skybot_results': None,  # 小行星查询结果
                    'vsx_results': None,     # 变星查询结果
                    'skybot_queried': False, # 是否已查询小行星
                    'vsx_queried': False     # 是否已查询变星
                })

            self._current_cutout_index = 0
            self._total_cutouts = len(self._all_cutout_sets)

            self.logger.info(f"找到 {self._total_cutouts} 组检测结果")

            # 加载每个cutout的查询结果
            for idx, cutout_set in enumerate(self._all_cutout_sets):
                self._load_query_results_from_file(cutout_set, idx)

            # 检查是否需要自动启用中心距离过滤
            self._check_auto_enable_center_distance_filter()

            # 显示第一组图片
            self._display_cutout_by_index(0)

            return True  # 成功显示

        except Exception as e:
            self.logger.error(f"显示cutout图片时出错: {e}")
            return False

    def _load_query_results_from_file(self, cutout_set, cutout_index):
        """从query_results_XXX.txt文件加载查询结果到cutout字典"""
        try:
            detection_img = cutout_set.get('detection')
            if not detection_img or not os.path.exists(detection_img):
                return

            cutout_dir = os.path.dirname(detection_img)
            # 使用检测目标序号作为文件名的一部分
            query_results_file = os.path.join(cutout_dir, f"query_results_{cutout_index + 1:03d}.txt")

            if not os.path.exists(query_results_file):
                return

            # 读取文件内容
            with open(query_results_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查小行星查询状态
            import re
            skybot_match = re.search(r'小行星列表:\n((?:  - .*\n)+)', content)
            if skybot_match:
                result_lines = skybot_match.group(1).strip()
                if '(未查询)' not in result_lines:
                    cutout_set['skybot_queried'] = True
                    # 检查是否有实际结果
                    if '(已查询，未找到)' not in result_lines:
                        # 有实际结果,创建一个模拟的结果列表(用于按钮颜色显示)
                        # 计算结果数量
                        result_count = len([line for line in result_lines.split('\n') if line.strip().startswith('-')])
                        # 创建一个简单的列表来表示有结果(长度表示数量)
                        cutout_set['skybot_results'] = [None] * result_count
                    else:
                        # 已查询但未找到
                        cutout_set['skybot_results'] = []

            # 检查变星查询状态
            vsx_match = re.search(r'变星列表:\n((?:  - .*\n)+)', content)
            if vsx_match:
                result_lines = vsx_match.group(1).strip()
                if '(未查询)' not in result_lines:
                    cutout_set['vsx_queried'] = True
                    # 检查是否有实际结果
                    if '(已查询，未找到)' not in result_lines:
                        # 有实际结果,创建一个模拟的结果列表(用于按钮颜色显示)
                        # 计算结果数量
                        result_count = len([line for line in result_lines.split('\n') if line.strip().startswith('-')])
                        # 创建一个简单的列表来表示有结果(长度表示数量)
                        cutout_set['vsx_results'] = [None] * result_count
                    else:
                        # 已查询但未找到
                        cutout_set['vsx_results'] = []

        except Exception as e:
            self.logger.error(f"加载查询结果失败: {str(e)}")

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

        # 从文件加载查询结果状态（如果存在）
        self._load_query_results_from_file(cutout_set, index)

        reference_img = cutout_set['reference']
        aligned_img = cutout_set['aligned']
        detection_img = cutout_set['detection']

        self.logger.info(f"显示第 {index + 1}/{self._total_cutouts} 组检测结果:")
        self.logger.info(f"  Reference: {os.path.basename(reference_img)}")
        self.logger.info(f"  Aligned: {os.path.basename(aligned_img)}")
        self.logger.info(f"  Detection: {os.path.basename(detection_img)}")

        # 更新计数标签
        self.cutout_count_label.config(text=f"{index + 1}/{self._total_cutouts}")

        # 更新当前检测目标的中心距离显示
        if hasattr(self, 'current_center_distance_label'):
            current_distance = self._get_detection_center_distance(cutout_set)
            if current_distance > 0:
                self.current_center_distance_label.config(text=f"{current_distance:.1f}")
            else:
                self.current_center_distance_label.config(text="--")

        # 启用导航按钮
        if self._total_cutouts > 1:
            self.prev_cutout_button.config(state="normal")
            self.next_cutout_button.config(state="normal")

        # 启用检查DSS按钮（只要有cutout就可以启用）
        if hasattr(self, 'check_dss_button'):
            self.check_dss_button.config(state="normal")

        # 启用Skybot查询按钮（只要有cutout就可以启用）
        if hasattr(self, 'skybot_button'):
            self.skybot_button.config(state="normal")
            # 更新按钮颜色以反映查询状态
            self._update_query_button_color('skybot')

        # 启用变星查询按钮（只要有cutout就可以启用）
        if hasattr(self, 'vsx_button'):
            self.vsx_button.config(state="normal")
            # 更新按钮颜色以反映查询状态
            self._update_query_button_color('vsx')

        # 启用卫星查询按钮（只要有cutout就可以启用）
        if hasattr(self, 'satellite_button'):
            self.satellite_button.config(state="normal")
            # 更新按钮颜色以反映查询状态
            self._update_query_button_color('satellite')

        # 启用保存检测结果按钮（只要有cutout就可以启用）
        if hasattr(self, 'save_detection_button'):
            self.save_detection_button.config(state="normal")

        # 提取文件信息（使用左侧选中的文件名）
        selected_filename = ""
        if self.selected_file_path:
            selected_filename = os.path.basename(self.selected_file_path)

        file_info = self._extract_file_info(reference_img, aligned_img, detection_img, selected_filename)

        # 更新坐标显示框
        self._update_coordinate_display(file_info)

        # 在主界面显示图片
        self._show_cutouts_in_main_display(reference_img, aligned_img, detection_img, file_info)

    def _get_detection_center_distance(self, cutout_set):
        """
        计算检测结果距离图像中心的距离

        Args:
            cutout_set: cutout数据集

        Returns:
            float: 距离中心的像素距离，如果无法计算则返回0
        """
        try:
            detection_img = cutout_set.get('detection')
            if not detection_img:
                self.logger.info("_get_detection_center_distance: detection_img为空")
                return 0

            # 从文件名提取像素坐标
            detection_basename = os.path.basename(detection_img)
            self.logger.info(f"_get_detection_center_distance: 检测文件名={detection_basename}")

            xy_match = re.search(r'X(\d+)_Y(\d+)', detection_basename)

            if not xy_match:
                self.logger.info("_get_detection_center_distance: 未找到X/Y坐标，尝试RA/DEC格式")
                # 如果没有X/Y坐标，尝试从RA/DEC格式的文件名中获取坐标
                # 文件名格式: 001_RA285.123456_DEC43.567890_...
                ra_dec_match = re.search(r'RA([\d.]+)_DEC([\d.]+)', detection_basename)
                if ra_dec_match:
                    self.logger.info("_get_detection_center_distance: 找到RA/DEC坐标")
                    # 如果是RA/DEC格式，需要通过WCS转换为像素坐标
                    # 这里先尝试从aligned文件的header获取WCS信息
                    aligned_img = cutout_set.get('aligned')
                    if aligned_img:
                        cutout_dir = Path(aligned_img).parent
                        detection_dir = cutout_dir.parent
                        fits_dir = detection_dir.parent  # 原始FITS文件所在目录
                        self.logger.info(f"_get_detection_center_distance: fits_dir={fits_dir}")

                        # 查找aligned.fits文件
                        aligned_fits_files = list(fits_dir.glob('*_aligned.fits'))
                        self.logger.info(f"_get_detection_center_distance: 找到{len(aligned_fits_files)}个aligned.fits文件")
                        if aligned_fits_files:
                            self.logger.info(f"_get_detection_center_distance: 使用文件={aligned_fits_files[0]}")
                            with fits.open(aligned_fits_files[0]) as hdul:
                                header = hdul[0].header
                                image_data = hdul[0].data

                                if image_data is not None and header is not None:
                                    try:
                                        from astropy.wcs import WCS
                                        wcs = WCS(header)

                                        ra = float(ra_dec_match.group(1))
                                        dec = float(ra_dec_match.group(2))

                                        # 将RA/DEC转换为像素坐标
                                        pixel_coords = wcs.all_world2pix([[ra, dec]], 0)
                                        pixel_x = pixel_coords[0][0]
                                        pixel_y = pixel_coords[0][1]

                                        height, width = image_data.shape
                                        center_x = width / 2.0
                                        center_y = height / 2.0

                                        # 计算距离
                                        distance = np.sqrt((pixel_x - center_x)**2 + (pixel_y - center_y)**2)
                                        self.logger.info(f"_get_detection_center_distance: RA/DEC格式计算距离={distance:.1f}像素")
                                        return distance
                                    except Exception as wcs_error:
                                        self.logger.warning(f"_get_detection_center_distance: WCS转换失败: {wcs_error}")

                self.logger.info("_get_detection_center_distance: 未找到RA/DEC坐标或无法转换")
                return 0

            pixel_x = float(xy_match.group(1))
            pixel_y = float(xy_match.group(2))
            self.logger.info(f"_get_detection_center_distance: 提取到X/Y坐标: X={pixel_x}, Y={pixel_y}")

            # 获取图像尺寸（从detection文件的父目录中的原始FITS文件）
            # 尝试从aligned文件获取图像尺寸
            aligned_img = cutout_set.get('aligned')
            if aligned_img:
                # 从aligned cutout的父目录找到原始aligned FITS文件
                # cutout路径: .../detection_xxx/cutouts/xxx.png
                # detection_dir: .../detection_xxx
                # 原始FITS文件在detection_dir的父目录
                cutout_dir = Path(aligned_img).parent
                detection_dir = cutout_dir.parent
                fits_dir = detection_dir.parent  # 原始FITS文件所在目录
                self.logger.info(f"_get_detection_center_distance: fits_dir={fits_dir}")

                # 查找aligned.fits文件
                aligned_fits_files = list(fits_dir.glob('*_aligned.fits'))
                self.logger.info(f"_get_detection_center_distance: 找到{len(aligned_fits_files)}个aligned.fits文件")

                if aligned_fits_files:
                    self.logger.info(f"_get_detection_center_distance: 使用文件={aligned_fits_files[0]}")
                    with fits.open(aligned_fits_files[0]) as hdul:
                        image_data = hdul[0].data
                        if image_data is not None:
                            height, width = image_data.shape
                            center_x = width / 2.0
                            center_y = height / 2.0
                            self.logger.info(f"_get_detection_center_distance: 图像尺寸={width}x{height}, 中心=({center_x:.1f}, {center_y:.1f})")

                            # 计算距离
                            distance = np.sqrt((pixel_x - center_x)**2 + (pixel_y - center_y)**2)
                            self.logger.info(f"_get_detection_center_distance: X/Y格式计算距离={distance:.1f}像素")
                            return distance
                        else:
                            self.logger.warning("_get_detection_center_distance: image_data为None")
                else:
                    self.logger.warning("_get_detection_center_distance: 未找到aligned.fits文件")
            else:
                self.logger.warning("_get_detection_center_distance: aligned_img为空")

            # 如果无法获取图像尺寸，返回0
            self.logger.info("_get_detection_center_distance: 无法获取图像尺寸，返回0")
            return 0

        except Exception as e:
            self.logger.warning(f"计算检测结果中心距离失败: {str(e)}")
            import traceback
            self.logger.warning(traceback.format_exc())
            return 0

    def _show_next_cutout(self):
        """显示下一组cutout图片（如果启用过滤，则跳过距离中心过远的检测结果）"""
        if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
            messagebox.showinfo("提示", "没有可显示的检测结果")
            return

        # 检查是否启用中心距离过滤
        enable_filter = self.enable_center_distance_filter_var.get() if hasattr(self, 'enable_center_distance_filter_var') else False

        # 如果未启用过滤，直接显示下一个
        if not enable_filter:
            next_index = (self._current_cutout_index + 1) % self._total_cutouts
            self._display_cutout_by_index(next_index)
            return

        # 启用过滤时，获取最大中心距离阈值
        try:
            max_distance = float(self.max_center_distance_var.get())
        except (ValueError, AttributeError):
            max_distance = 2400  # 默认值

        # 从当前索引开始查找下一个符合条件的检测结果
        start_index = self._current_cutout_index
        attempts = 0

        while attempts < self._total_cutouts:
            next_index = (start_index + attempts + 1) % self._total_cutouts
            cutout_set = self._all_cutout_sets[next_index]

            # 计算距离中心的距离
            distance = self._get_detection_center_distance(cutout_set)

            # 如果距离为0（无法计算）或小于等于阈值，则显示
            if distance == 0 or distance <= max_distance:
                self._display_cutout_by_index(next_index)
                return
            else:
                self.logger.info(f"跳过检测结果 {next_index + 1}，距离中心 {distance:.1f} 像素 > {max_distance} 像素")

            attempts += 1

        # 如果所有检测结果都不符合条件，显示提示
        messagebox.showinfo("提示", f"没有找到距离中心小于 {max_distance} 像素的检测结果")
        self.logger.warning(f"所有检测结果都超过最大中心距离阈值 {max_distance} 像素")

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
        self.time_utc_entry.delete(0, tk.END)
        self.time_beijing_entry.delete(0, tk.END)
        self.time_local_entry.delete(0, tk.END)

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

        # 时间显示
        time_info = self._extract_time_from_filename(file_info.get('filename', ''))
        if time_info:
            # 保存UTC时间用于后续更新
            self._current_utc_time = time_info.get('utc_datetime')

            # UTC时间
            if time_info.get('utc'):
                self.time_utc_entry.insert(0, time_info['utc'])
                self.logger.info(f"UTC时间: {time_info['utc']}")

            # 北京时间
            if time_info.get('beijing'):
                self.time_beijing_entry.insert(0, time_info['beijing'])
                self.logger.info(f"北京时间: {time_info['beijing']}")

            # 本地时间（根据GPS计算）
            if time_info.get('local'):
                self.time_local_entry.insert(0, time_info['local'])
                self.logger.info(f"本地时间: {time_info['local']}")
        else:
            self._current_utc_time = None
            self.logger.warning("未能从文件名提取时间信息")

    def _extract_time_from_filename(self, filename):
        """
        从文件名提取UTC时间并转换为不同时区

        文件名格式示例: GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_191828_-14.9C_.fits

        Args:
            filename: 文件名

        Returns:
            dict: 包含utc, beijing, local时间字符串的字典，如果提取失败返回None
        """
        import re
        from datetime import datetime, timedelta

        try:
            # 匹配UTC时间格式: UTC20250628_191828
            pattern = r'UTC(\d{8})_(\d{6})'
            match = re.search(pattern, filename)

            if not match:
                self.logger.warning(f"文件名中未找到UTC时间格式: {filename}")
                return None

            date_str = match.group(1)  # 20250628
            time_str = match.group(2)  # 191828

            # 解析UTC时间
            utc_dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")

            # 格式化UTC时间
            utc_formatted = utc_dt.strftime("%Y-%m-%d %H:%M:%S")

            # 计算北京时间 (UTC+8)
            beijing_dt = utc_dt + timedelta(hours=8)
            beijing_formatted = beijing_dt.strftime("%Y-%m-%d %H:%M:%S")

            # 根据GPS经度计算本地时区
            try:
                longitude = float(self.gps_lon_var.get())
                timezone_offset = round(longitude / 15)
                timezone_offset = max(-12, min(14, timezone_offset))
            except:
                timezone_offset = 6  # 默认UTC+6

            # 计算本地时间
            local_dt = utc_dt + timedelta(hours=timezone_offset)
            local_formatted = local_dt.strftime("%Y-%m-%d %H:%M:%S")

            return {
                'utc': utc_formatted,
                'utc_datetime': utc_dt,  # 保存datetime对象用于后续更新
                'beijing': beijing_formatted,
                'local': local_formatted
            }

        except Exception as e:
            self.logger.error(f"提取时间信息失败: {e}")
            return None

    def _update_time_display_with_utc(self, utc_dt):
        """
        根据UTC时间更新所有时间显示

        Args:
            utc_dt: datetime对象，UTC时间
        """
        from datetime import timedelta

        try:
            # 清空时间框
            self.time_utc_entry.delete(0, tk.END)
            self.time_beijing_entry.delete(0, tk.END)
            self.time_local_entry.delete(0, tk.END)

            # UTC时间
            utc_formatted = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.time_utc_entry.insert(0, utc_formatted)

            # 北京时间 (UTC+8)
            beijing_dt = utc_dt + timedelta(hours=8)
            beijing_formatted = beijing_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.time_beijing_entry.insert(0, beijing_formatted)

            # 根据GPS经度计算本地时区
            try:
                longitude = float(self.gps_lon_var.get())
                timezone_offset = round(longitude / 15)
                timezone_offset = max(-12, min(14, timezone_offset))
            except:
                timezone_offset = 6  # 默认UTC+6

            # 本地时间
            local_dt = utc_dt + timedelta(hours=timezone_offset)
            local_formatted = local_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.time_local_entry.insert(0, local_formatted)

            self.logger.info(f"时间已更新: UTC={utc_formatted}, 北京={beijing_formatted}, 本地={local_formatted} (UTC{timezone_offset:+d})")

        except Exception as e:
            self.logger.error(f"更新时间显示失败: {e}")

    def _show_previous_cutout(self):
        """显示上一组cutout图片（如果启用过滤，则跳过距离中心过远的检测结果）"""
        if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
            messagebox.showinfo("提示", "没有可显示的检测结果")
            return

        # 检查是否启用中心距离过滤
        enable_filter = self.enable_center_distance_filter_var.get() if hasattr(self, 'enable_center_distance_filter_var') else False

        # 如果未启用过滤，直接显示上一个
        if not enable_filter:
            prev_index = (self._current_cutout_index - 1) % self._total_cutouts
            self._display_cutout_by_index(prev_index)
            return

        # 启用过滤时，获取最大中心距离阈值
        try:
            max_distance = float(self.max_center_distance_var.get())
        except (ValueError, AttributeError):
            max_distance = 2400  # 默认值

        # 从当前索引开始查找上一个符合条件的检测结果
        start_index = self._current_cutout_index
        attempts = 0

        while attempts < self._total_cutouts:
            prev_index = (start_index - attempts - 1) % self._total_cutouts
            cutout_set = self._all_cutout_sets[prev_index]

            # 计算距离中心的距离
            distance = self._get_detection_center_distance(cutout_set)

            # 如果距离为0（无法计算）或小于等于阈值，则显示
            if distance == 0 or distance <= max_distance:
                self._display_cutout_by_index(prev_index)
                return
            else:
                self.logger.info(f"跳过检测结果 {prev_index + 1}，距离中心 {distance:.1f} 像素 > {max_distance} 像素")

            attempts += 1

        # 如果所有检测结果都不符合条件，显示提示
        messagebox.showinfo("提示", f"没有找到距离中心小于 {max_distance} 像素的检测结果")
        self.logger.warning(f"所有检测结果都超过最大中心距离阈值 {max_distance} 像素")

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

        # 是最终节点（FITS文件）
        # 检查是否有检测结果且不是第一个检测结果
        has_cutouts = hasattr(self, '_current_cutout_index') and hasattr(self, '_total_cutouts')
        is_not_first = has_cutouts and self._current_cutout_index > 0

        # 只有在不是第一个检测结果时才执行"上一组"操作
        if is_not_first:
            if hasattr(self, 'prev_cutout_button') and str(self.prev_cutout_button['state']) == 'normal':
                self._show_previous_cutout()
                return "break"  # 阻止默认行为

        # 其他情况（第一个检测结果或没有检测结果），保留默认折叠功能
        # 不返回"break"，让默认行为执行

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

    def _draw_crosshair_on_axis(self, ax, image_shape, color='lime', linewidth=1, size=10, gap=5):
        """
        在matplotlib axis上绘制空心十字准星

        Args:
            ax: matplotlib axis对象
            image_shape: 图像形状 (height, width) 或 (height, width, channels)
            color: 十字准星颜色，默认lime（亮绿色）
            linewidth: 线条粗细，默认1
            size: 十字准星臂长，默认10像素
            gap: 中心空隙大小，默认5像素
        """
        # 获取图像中心坐标
        h, w = image_shape[0], image_shape[1]
        center_x, center_y = w / 2, h / 2

        # 绘制水平线（左右两段）
        ax.plot([center_x - gap - size, center_x - gap], [center_y, center_y],
                color=color, linewidth=linewidth, linestyle='-')
        ax.plot([center_x + gap, center_x + gap + size], [center_y, center_y],
                color=color, linewidth=linewidth, linestyle='-')

        # 绘制垂直线（上下两段）
        ax.plot([center_x, center_x], [center_y - gap - size, center_y - gap],
                color=color, linewidth=linewidth, linestyle='-')
        ax.plot([center_x, center_x], [center_y + gap, center_y + gap + size],
                color=color, linewidth=linewidth, linestyle='-')

    def _draw_four_pointed_star(self, ax, x, y, color='orange', linewidth=1, size=8, gap=2):
        """
        在matplotlib axis上绘制空心四芒星

        Args:
            ax: matplotlib axis对象
            x: 星标中心x坐标（像素）
            y: 星标中心y坐标（像素）
            color: 星标颜色，默认orange（橘黄色）
            linewidth: 线条粗细，默认1
            size: 星标臂长，默认8像素
            gap: 中心空隙大小，默认2像素
        """
        # 只绘制水平和垂直的十字线（4条线）
        # 绘制水平线（左右两段）
        ax.plot([x - gap - size, x - gap], [y, y],
                color=color, linewidth=linewidth, linestyle='-')
        ax.plot([x + gap, x + gap + size], [y, y],
                color=color, linewidth=linewidth, linestyle='-')

        # 绘制垂直线（上下两段）
        ax.plot([x, x], [y - gap - size, y - gap],
                color=color, linewidth=linewidth, linestyle='-')
        ax.plot([x, x], [y + gap, y + gap + size],
                color=color, linewidth=linewidth, linestyle='-')

    def _draw_variable_stars_on_axis(self, ax, aligned_img_path, image_shape, file_info=None):
        """
        在matplotlib axis上绘制变星标记

        Args:
            ax: matplotlib axis对象
            aligned_img_path: aligned图像路径（用于定位对应的FITS文件）
            image_shape: 图像形状 (height, width) 或 (height, width, channels)
            file_info: 文件信息字典（包含RA/DEC等信息）
        """
        try:
            self.logger.info("=== 开始绘制变星标记 ===")

            # 检查是否有当前cutout和变星查询结果
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.info("没有cutout sets，跳过变星标记")
                return
            if not hasattr(self, '_current_cutout_index'):
                self.logger.info("没有current_cutout_index，跳过变星标记")
                return

            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            vsx_queried = current_cutout.get('vsx_queried', False)
            vsx_results = current_cutout.get('vsx_results', None)

            self.logger.info(f"变星查询状态: queried={vsx_queried}, results={vsx_results}")

            # 如果没有查询或没有结果，直接返回
            if not vsx_queried or not vsx_results or len(vsx_results) == 0:
                self.logger.info("没有变星查询结果，跳过变星标记")
                return

            # 检查file_info是否包含RA/DEC
            if not file_info or not file_info.get('ra') or not file_info.get('dec'):
                self.logger.warning("file_info中没有RA/DEC信息，无法绘制变星标记")
                return

            # 从file_info获取cutout中心的RA/DEC坐标
            cutout_center_ra = float(file_info['ra'])
            cutout_center_dec = float(file_info['dec'])
            self.logger.info(f"Cutout中心坐标: RA={cutout_center_ra}°, DEC={cutout_center_dec}°")

            # 从aligned图像路径获取对应的FITS文件
            cutout_dir = os.path.dirname(aligned_img_path)
            detection_dir = os.path.dirname(cutout_dir)
            fits_dir = os.path.dirname(detection_dir)

            # 查找aligned.fits文件
            aligned_fits_files = list(Path(fits_dir).glob('*_aligned.fits'))
            if not aligned_fits_files:
                self.logger.warning("未找到aligned.fits文件，无法绘制变星标记")
                return

            aligned_fits_path = aligned_fits_files[0]
            self.logger.info(f"使用FITS文件获取WCS信息: {aligned_fits_path}")

            # 读取FITS文件的header获取WCS信息
            from astropy.io import fits
            from astropy.wcs import WCS
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            import re

            with fits.open(aligned_fits_path) as hdul:
                header = hdul[0].header
                wcs = WCS(header)

                # 将cutout中心的RA/DEC转换为原始FITS的像素坐标
                cutout_center_coord = SkyCoord(ra=cutout_center_ra*u.degree, dec=cutout_center_dec*u.degree)
                cutout_center_pixel = wcs.world_to_pixel(cutout_center_coord)
                self.logger.info(f"Cutout中心在原始FITS中的像素坐标: ({cutout_center_pixel[0]:.1f}, {cutout_center_pixel[1]:.1f})")

                # cutout图像的尺寸
                h, w = image_shape[0], image_shape[1]
                cutout_half_size = w / 2  # 假设cutout是正方形

                # 计算cutout在原始FITS中的边界
                cutout_x_min = cutout_center_pixel[0] - cutout_half_size
                cutout_y_min = cutout_center_pixel[1] - cutout_half_size
                self.logger.info(f"Cutout在原始FITS中的边界: ({cutout_x_min:.1f}, {cutout_y_min:.1f})")

                # 遍历变星结果，绘制标记
                # 从query_results文件中读取实际的变星坐标
                detection_img = current_cutout.get('detection')
                if not detection_img:
                    self.logger.warning("无法获取detection图像路径")
                    return

                cutout_img_dir = os.path.dirname(detection_img)
                query_results_file = os.path.join(cutout_img_dir, f"query_results_{self._current_cutout_index + 1:03d}.txt")

                self.logger.info(f"查找query_results文件: {query_results_file}")
                self.logger.info(f"文件是否存在: {os.path.exists(query_results_file)}")

                if os.path.exists(query_results_file):
                    with open(query_results_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    self.logger.info(f"query_results文件内容长度: {len(content)} 字符")

                    # 解析变星列表
                    vsx_match = re.search(r'变星列表:\n((?:  - .*\n)+)', content)
                    if vsx_match:
                        self.logger.info("找到变星列表匹配")
                        result_lines = vsx_match.group(1).strip()

                        # 解析每一行变星信息
                        for line in result_lines.split('\n'):
                            if line.strip().startswith('-') and '(未查询)' not in line and '(已查询，未找到)' not in line:
                                # 提取RA和DEC (兼容 "RA=xxx°" 和 "RA=xxx deg°" 两种格式)
                                ra_match = re.search(r'RA=([\d.]+)\s*(?:deg)?°', line)
                                dec_match = re.search(r'DEC=([-\d.]+)\s*(?:deg)?°', line)

                                if ra_match and dec_match:
                                    vsx_ra = float(ra_match.group(1))
                                    vsx_dec = float(dec_match.group(1))

                                    # 将变星的RA/DEC转换为原始FITS的像素坐标
                                    vsx_coord = SkyCoord(ra=vsx_ra*u.degree, dec=vsx_dec*u.degree)
                                    vsx_pixel = wcs.world_to_pixel(vsx_coord)

                                    # 转换为cutout图像的像素坐标
                                    vsx_x_in_cutout = vsx_pixel[0] - cutout_x_min
                                    vsx_y_in_cutout = vsx_pixel[1] - cutout_y_min

                                    # 检查变星是否在cutout范围内
                                    if 0 <= vsx_x_in_cutout < w and 0 <= vsx_y_in_cutout < h:
                                        self.logger.info(f"绘制变星标记: RA={vsx_ra}, DEC={vsx_dec}, "
                                                       f"cutout坐标=({vsx_x_in_cutout:.1f}, {vsx_y_in_cutout:.1f})")

                                        # 绘制橘黄色四芒星（小而细的十字标记）
                                        self._draw_four_pointed_star(ax, vsx_x_in_cutout, vsx_y_in_cutout,
                                                                    color='orange', linewidth=1, size=8, gap=2)
                                    else:
                                        self.logger.info(f"变星不在cutout范围内: RA={vsx_ra}, DEC={vsx_dec}")
                    else:
                        self.logger.warning("未找到变星列表匹配")
                else:
                    self.logger.warning("未找到query_results文件")

        except Exception as e:
            self.logger.error(f"绘制变星标记时出错: {e}", exc_info=True)

    def _draw_asteroids_on_axis(self, ax, aligned_img_path, image_shape, file_info=None):
        """
        在matplotlib axis上绘制小行星标记

        Args:
            ax: matplotlib axis对象
            aligned_img_path: aligned图像路径（用于定位对应的FITS文件）
            image_shape: 图像形状 (height, width) 或 (height, width, channels)
            file_info: 文件信息字典（包含RA/DEC等信息）
        """
        try:
            self.logger.info("=== 开始绘制小行星标记 ===")

            # 检查是否有当前cutout和小行星查询结果
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.info("没有cutout sets，跳过小行星标记")
                return
            if not hasattr(self, '_current_cutout_index'):
                self.logger.info("没有current_cutout_index，跳过小行星标记")
                return

            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            skybot_queried = current_cutout.get('skybot_queried', False)
            skybot_results = current_cutout.get('skybot_results', None)

            self.logger.info(f"小行星查询状态: queried={skybot_queried}, results={skybot_results}")

            # 如果没有查询或没有结果，直接返回
            if not skybot_queried or not skybot_results or len(skybot_results) == 0:
                self.logger.info("没有小行星查询结果，跳过小行星标记")
                return

            # 检查file_info是否包含RA/DEC
            if not file_info or not file_info.get('ra') or not file_info.get('dec'):
                self.logger.warning("file_info中没有RA/DEC信息，无法绘制小行星标记")
                return

            # 从file_info获取cutout中心的RA/DEC坐标
            cutout_center_ra = float(file_info['ra'])
            cutout_center_dec = float(file_info['dec'])
            self.logger.info(f"Cutout中心坐标: RA={cutout_center_ra}°, DEC={cutout_center_dec}°")

            # 从aligned图像路径获取对应的FITS文件
            cutout_dir = os.path.dirname(aligned_img_path)
            detection_dir = os.path.dirname(cutout_dir)
            fits_dir = os.path.dirname(detection_dir)

            # 查找aligned.fits文件
            aligned_fits_files = list(Path(fits_dir).glob('*_aligned.fits'))
            if not aligned_fits_files:
                self.logger.warning("未找到aligned.fits文件，无法绘制小行星标记")
                return

            aligned_fits_path = aligned_fits_files[0]
            self.logger.info(f"使用FITS文件获取WCS信息: {aligned_fits_path}")

            # 读取FITS文件的header获取WCS信息
            from astropy.io import fits
            from astropy.wcs import WCS
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            import re

            with fits.open(aligned_fits_path) as hdul:
                header = hdul[0].header
                wcs = WCS(header)

                # 将cutout中心的RA/DEC转换为原始FITS的像素坐标
                cutout_center_coord = SkyCoord(ra=cutout_center_ra*u.degree, dec=cutout_center_dec*u.degree)
                cutout_center_pixel = wcs.world_to_pixel(cutout_center_coord)
                self.logger.info(f"Cutout中心在原始FITS中的像素坐标: ({cutout_center_pixel[0]:.1f}, {cutout_center_pixel[1]:.1f})")

                # cutout图像的尺寸
                h, w = image_shape[0], image_shape[1]
                cutout_half_size = w / 2  # 假设cutout是正方形

                # 计算cutout在原始FITS中的边界
                cutout_x_min = cutout_center_pixel[0] - cutout_half_size
                cutout_y_min = cutout_center_pixel[1] - cutout_half_size
                self.logger.info(f"Cutout在原始FITS中的边界: ({cutout_x_min:.1f}, {cutout_y_min:.1f})")

                # 遍历小行星结果，绘制标记
                # 从query_results文件中读取实际的小行星坐标
                detection_img = current_cutout.get('detection')
                if not detection_img:
                    self.logger.warning("无法获取detection图像路径")
                    return

                cutout_img_dir = os.path.dirname(detection_img)
                query_results_file = os.path.join(cutout_img_dir, f"query_results_{self._current_cutout_index + 1:03d}.txt")

                self.logger.info(f"查找query_results文件: {query_results_file}")
                self.logger.info(f"文件是否存在: {os.path.exists(query_results_file)}")

                if os.path.exists(query_results_file):
                    with open(query_results_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    self.logger.info(f"query_results文件内容长度: {len(content)} 字符")

                    # 解析小行星列表
                    skybot_match = re.search(r'小行星列表:\n((?:  - .*\n)+)', content)
                    if skybot_match:
                        self.logger.info("找到小行星列表匹配")
                        result_lines = skybot_match.group(1).strip()

                        # 解析每一行小行星信息
                        for line in result_lines.split('\n'):
                            if line.strip().startswith('-') and '(未查询)' not in line and '(已查询，未找到)' not in line:
                                # 提取RA和DEC (注意小行星格式可能是 "RA=xxx deg°" 或 "RA=xxx°")
                                ra_match = re.search(r'RA=([\d.]+)\s*(?:deg)?°', line)
                                dec_match = re.search(r'DEC=([-\d.]+)\s*(?:deg)?°', line)

                                if ra_match and dec_match:
                                    asteroid_ra = float(ra_match.group(1))
                                    asteroid_dec = float(dec_match.group(1))

                                    # 将小行星的RA/DEC转换为原始FITS的像素坐标
                                    asteroid_coord = SkyCoord(ra=asteroid_ra*u.degree, dec=asteroid_dec*u.degree)
                                    asteroid_pixel = wcs.world_to_pixel(asteroid_coord)

                                    # 转换为cutout图像的像素坐标
                                    asteroid_x_in_cutout = asteroid_pixel[0] - cutout_x_min
                                    asteroid_y_in_cutout = asteroid_pixel[1] - cutout_y_min

                                    # 检查小行星是否在cutout范围内
                                    if 0 <= asteroid_x_in_cutout < w and 0 <= asteroid_y_in_cutout < h:
                                        self.logger.info(f"绘制小行星标记: RA={asteroid_ra}, DEC={asteroid_dec}, "
                                                       f"cutout坐标=({asteroid_x_in_cutout:.1f}, {asteroid_y_in_cutout:.1f})")

                                        # 绘制青色四芒星（小而细的十字标记）
                                        self._draw_four_pointed_star(ax, asteroid_x_in_cutout, asteroid_y_in_cutout,
                                                                    color='cyan', linewidth=1, size=8, gap=2)
                                    else:
                                        self.logger.info(f"小行星不在cutout范围内: RA={asteroid_ra}, DEC={asteroid_dec}")
                    else:
                        self.logger.warning("未找到小行星列表匹配")
                else:
                    self.logger.warning("未找到query_results文件")

        except Exception as e:
            self.logger.error(f"绘制小行星标记时出错: {e}", exc_info=True)

    def _draw_satellites_on_axis(self, ax, aligned_img_path, image_shape, file_info=None):
        """
        在matplotlib axis上绘制卫星标记

        Args:
            ax: matplotlib axis对象
            aligned_img_path: aligned图像路径（用于定位对应的FITS文件）
            image_shape: 图像形状 (height, width) 或 (height, width, channels)
            file_info: 文件信息字典（包含RA/DEC等信息）
        """
        try:
            self.logger.info("=== 开始绘制卫星标记 ===")

            # 检查是否有当前cutout和卫星查询结果
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.info("没有cutout sets，跳过卫星标记")
                return
            if not hasattr(self, '_current_cutout_index'):
                self.logger.info("没有current_cutout_index，跳过卫星标记")
                return

            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            satellite_queried = current_cutout.get('satellite_queried', False)
            satellite_results = current_cutout.get('satellite_results', None)

            self.logger.info(f"卫星查询状态: queried={satellite_queried}, results={satellite_results}")

            # 如果没有查询或没有结果，直接返回
            if not satellite_queried or not satellite_results or len(satellite_results) == 0:
                self.logger.info("没有卫星查询结果，跳过卫星标记")
                return

            # 检查file_info是否包含RA/DEC
            if not file_info or not file_info.get('ra') or not file_info.get('dec'):
                self.logger.warning("file_info中没有RA/DEC信息，无法绘制卫星标记")
                return

            # 从file_info获取cutout中心的RA/DEC坐标
            cutout_center_ra = float(file_info['ra'])
            cutout_center_dec = float(file_info['dec'])
            self.logger.info(f"Cutout中心坐标: RA={cutout_center_ra}°, DEC={cutout_center_dec}°")

            # 从aligned图像路径获取对应的FITS文件
            cutout_dir = os.path.dirname(aligned_img_path)
            detection_dir = os.path.dirname(cutout_dir)
            fits_dir = os.path.dirname(detection_dir)

            # 查找aligned.fits文件
            aligned_fits_files = list(Path(fits_dir).glob('*_aligned.fits'))
            if not aligned_fits_files:
                self.logger.warning("未找到aligned.fits文件，无法绘制卫星标记")
                return

            aligned_fits_path = aligned_fits_files[0]
            self.logger.info(f"使用FITS文件获取WCS信息: {aligned_fits_path}")

            # 读取FITS文件的header获取WCS信息
            from astropy.io import fits
            from astropy.wcs import WCS
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            import re

            with fits.open(aligned_fits_path) as hdul:
                header = hdul[0].header
                wcs = WCS(header)

                # 将cutout中心的RA/DEC转换为原始FITS的像素坐标
                cutout_center_coord = SkyCoord(ra=cutout_center_ra*u.degree, dec=cutout_center_dec*u.degree)
                cutout_center_pixel = wcs.world_to_pixel(cutout_center_coord)
                self.logger.info(f"Cutout中心在原始FITS中的像素坐标: ({cutout_center_pixel[0]:.1f}, {cutout_center_pixel[1]:.1f})")

                # cutout图像的尺寸
                h, w = image_shape[0], image_shape[1]
                cutout_half_size = w / 2  # 假设cutout是正方形

                # 计算cutout在原始FITS中的边界
                cutout_x_min = cutout_center_pixel[0] - cutout_half_size
                cutout_y_min = cutout_center_pixel[1] - cutout_half_size
                self.logger.info(f"Cutout在原始FITS中的边界: ({cutout_x_min:.1f}, {cutout_y_min:.1f})")

                # 遍历卫星结果，绘制标记
                # 从query_results文件中读取实际的卫星坐标
                detection_img = current_cutout.get('detection')
                if not detection_img:
                    self.logger.warning("无法获取detection图像路径")
                    return

                cutout_img_dir = os.path.dirname(detection_img)
                query_results_file = os.path.join(cutout_img_dir, f"query_results_{self._current_cutout_index + 1:03d}.txt")

                self.logger.info(f"查找query_results文件: {query_results_file}")
                self.logger.info(f"文件是否存在: {os.path.exists(query_results_file)}")

                if os.path.exists(query_results_file):
                    with open(query_results_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    self.logger.info(f"query_results文件内容长度: {len(content)} 字符")

                    # 解析卫星列表
                    satellite_match = re.search(r'卫星列表:\n((?:  - .*\n)+)', content)
                    if satellite_match:
                        self.logger.info("找到卫星列表匹配")
                        result_lines = satellite_match.group(1).strip()

                        # 解析每一行卫星信息
                        for line in result_lines.split('\n'):
                            if line.strip().startswith('-') and '(未查询)' not in line and '(已查询，未找到)' not in line:
                                # 提取RA和DEC
                                ra_match = re.search(r'RA=([\d.]+)\s*°', line)
                                dec_match = re.search(r'DEC=([-\d.]+)\s*°', line)

                                if ra_match and dec_match:
                                    satellite_ra = float(ra_match.group(1))
                                    satellite_dec = float(dec_match.group(1))

                                    # 将卫星的RA/DEC转换为原始FITS的像素坐标
                                    satellite_coord = SkyCoord(ra=satellite_ra*u.degree, dec=satellite_dec*u.degree)
                                    satellite_pixel = wcs.world_to_pixel(satellite_coord)

                                    # 转换为cutout图像的坐标
                                    satellite_x_in_cutout = satellite_pixel[0] - cutout_x_min
                                    satellite_y_in_cutout = satellite_pixel[1] - cutout_y_min

                                    # 检查卫星是否在cutout范围内
                                    if 0 <= satellite_x_in_cutout < w and 0 <= satellite_y_in_cutout < h:
                                        self.logger.info(f"绘制卫星标记: RA={satellite_ra}, DEC={satellite_dec}, "
                                                       f"cutout坐标=({satellite_x_in_cutout:.1f}, {satellite_y_in_cutout:.1f})")

                                        # 绘制紫色四芒星（小而细的十字标记）
                                        self._draw_four_pointed_star(ax, satellite_x_in_cutout, satellite_y_in_cutout,
                                                                    color='magenta', linewidth=1, size=8, gap=2)
                                    else:
                                        self.logger.info(f"卫星不在cutout范围内: RA={satellite_ra}, DEC={satellite_dec}")
                    else:
                        self.logger.warning("未找到卫星列表匹配")
                else:
                    self.logger.warning("未找到query_results文件")

        except Exception as e:
            self.logger.error(f"绘制卫星标记时出错: {e}", exc_info=True)

    def _refresh_current_cutout_display(self):
        """
        重新绘制当前显示的cutout（用于查询完成后更新标记）
        """
        try:
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.warning("没有cutout sets，无法刷新显示")
                return

            if not hasattr(self, '_current_cutout_index'):
                self.logger.warning("没有current_cutout_index，无法刷新显示")
                return

            # 获取当前cutout的信息
            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            reference_img = current_cutout['reference']
            aligned_img = current_cutout['aligned']
            detection_img = current_cutout['detection']

            # 提取文件信息
            selected_filename = ""
            if self.selected_file_path:
                selected_filename = os.path.basename(self.selected_file_path)

            file_info = self._extract_file_info(reference_img, aligned_img, detection_img, selected_filename)

            # 重新显示cutout
            self._show_cutouts_in_main_display(reference_img, aligned_img, detection_img, file_info)

            self.logger.info("已刷新cutout显示")

        except Exception as e:
            self.logger.error(f"刷新cutout显示失败: {e}", exc_info=True)

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
            self._blink_aligned_img_path = aligned_img  # 保存aligned图像路径供绘制变星使用
            self._blink_file_info = file_info  # 保存file_info供绘制变星使用

            # 显示第一张图片（reference）
            self._blink_ax = axes[0]
            self._blink_im = self._blink_ax.imshow(
                ref_array,
                cmap='gray' if len(ref_array.shape) == 2 else None
            )
            self._blink_ax.set_title("Reference ⇄ Aligned (闪烁)", fontsize=10, fontweight='bold')
            self._blink_ax.axis('off')
            # 添加十字准星
            self._draw_crosshair_on_axis(self._blink_ax, ref_array.shape)

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
            # 添加十字准星
            self._draw_crosshair_on_axis(self._click_ax, aligned_array.shape)

            # 在aligned图像上绘制变星标记（橘黄色）
            self._draw_variable_stars_on_axis(self._click_ax, aligned_img, aligned_array.shape, file_info)

            # 在aligned图像上绘制小行星标记（青色）
            self._draw_asteroids_on_axis(self._click_ax, aligned_img, aligned_array.shape, file_info)

            # 在aligned图像上绘制卫星标记（紫色）
            self._draw_satellites_on_axis(self._click_ax, aligned_img, aligned_array.shape, file_info)

            # 显示detection图像
            axes[2].imshow(detection_array, cmap='gray' if len(detection_array.shape) == 2 else None)
            axes[2].set_title("Detection (检测结果)", fontsize=10, fontweight='bold')
            axes[2].axis('off')
            # 添加十字准星
            self._draw_crosshair_on_axis(axes[2], detection_array.shape)

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

                # 清除之前的所有绘图元素（除了图像本身）
                # 使用clear()然后重新绘制图像
                self._blink_ax.clear()

                # 重新绘制图像
                self._blink_im = self._blink_ax.imshow(
                    self._blink_images[self._blink_index],
                    cmap='gray' if len(self._blink_images[self._blink_index].shape) == 2 else None
                )
                self._blink_ax.axis('off')

                # 更新标题显示当前图像
                if self._blink_index == 0:
                    self._blink_ax.set_title("Reference (模板图像)", fontsize=10, fontweight='bold')
                    # 绘制十字准星
                    self._draw_crosshair_on_axis(self._blink_ax, self._blink_images[0].shape)
                else:
                    self._blink_ax.set_title("Aligned (对齐图像)", fontsize=10, fontweight='bold')
                    # 绘制十字准星
                    self._draw_crosshair_on_axis(self._blink_ax, self._blink_images[1].shape)

                # 刷新画布
                self.canvas.draw_idle()

                # 继续下一次更新
                self._blink_animation_id = self.parent_frame.after(500, update_blink)

            except Exception as e:
                self.logger.error(f"闪烁动画更新失败: {e}", exc_info=True)
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

                    # 记录DSS图像的索引和原始数据
                    self._dss_image_index = len(self._click_images) - 1
                    self._dss_original_array = dss_array.copy()  # 保存原始数据用于翻转操作

                    total_images = len(self._click_images)
                    self.logger.info(f"DSS图像已添加到切换列表，当前共有 {total_images} 张图像")
                    self.logger.info(f"文件保存在: {dss_output_path}")

                    # 应用翻转设置
                    self._apply_dss_flip()

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

    def _apply_dss_flip(self):
        """根据配置应用DSS图像翻转"""
        try:
            # 检查是否有DSS图像
            if not hasattr(self, '_dss_image_index') or not hasattr(self, '_dss_original_array'):
                return

            # 获取DSS图像索引
            dss_index = self._dss_image_index

            # 从原始图像开始应用翻转
            flipped_dss = self._dss_original_array.copy()

            # 根据配置应用翻转
            if self.flip_dss_vertical_var.get():
                flipped_dss = np.flipud(flipped_dss)

            if self.flip_dss_horizontal_var.get():
                flipped_dss = np.fliplr(flipped_dss)

            # 更新图像数据
            self._click_images[dss_index] = flipped_dss

            # 如果当前显示的是DSS图像，更新显示
            if hasattr(self, '_click_index') and self._click_index == dss_index:
                self._click_im.set_data(flipped_dss)
                self.canvas.draw_idle()

            # 记录翻转状态
            flip_status = []
            if self.flip_dss_vertical_var.get():
                flip_status.append("上下翻转")
            if self.flip_dss_horizontal_var.get():
                flip_status.append("左右翻转")

            if flip_status:
                self.logger.info(f"DSS图像已应用翻转: {', '.join(flip_status)}")
            else:
                self.logger.info("DSS图像已恢复原始方向")

        except Exception as e:
            self.logger.error(f"应用DSS图像翻转失败: {str(e)}", exc_info=True)

    def _query_skybot(self):
        """使用Skybot查询小行星数据"""
        try:
            # 立即重置结果标签，确保用户能看到查询状态变化
            self.skybot_result_label.config(text="准备中...", foreground="gray")
            self.skybot_result_label.update_idletasks()  # 强制刷新界面

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
                self.skybot_result_label.config(text="坐标缺失", foreground="red")
                return

            ra = float(file_info['ra'])
            dec = float(file_info['dec'])

            # 检查是否有UTC时间
            if not hasattr(self, '_current_utc_time') or not self._current_utc_time:
                self.logger.error("无法获取UTC时间信息")
                self.skybot_result_label.config(text="时间缺失", foreground="red")
                return

            utc_time = self._current_utc_time

            # 获取GPS位置
            try:
                latitude = float(self.gps_lat_var.get())
                longitude = float(self.gps_lon_var.get())
            except ValueError:
                self.logger.error(f"无效的GPS坐标: 纬度={self.gps_lat_var.get()}, 经度={self.gps_lon_var.get()}")
                self.skybot_result_label.config(text="GPS无效", foreground="red")
                return

            # 获取MPC代码
            mpc_code = self.mpc_code_var.get().strip().upper()
            if not mpc_code:
                mpc_code = 'N87'  # 默认值

            # 获取搜索半径
            try:
                search_radius = float(self.search_radius_var.get())
            except ValueError:
                self.logger.warning(f"无效的搜索半径: {self.search_radius_var.get()}，使用默认值0.01")
                search_radius = 0.01

            query_info = f"准备查询Skybot: RA={ra}°, Dec={dec}°, UTC={utc_time}, MPC={mpc_code}, GPS=({latitude}°N, {longitude}°E), 半径={search_radius}°"
            self.logger.info(query_info)
            # 输出到日志标签页
            if self.log_callback:
                self.log_callback(query_info, "INFO")

            self.skybot_result_label.config(text="查询中...", foreground="orange")
            self.skybot_result_label.update_idletasks()  # 强制刷新界面

            # 执行Skybot查询
            results = self._perform_skybot_query(ra, dec, utc_time, mpc_code, latitude, longitude, search_radius)

            if results is not None:
                # 保存查询结果到当前cutout
                current_cutout = self._all_cutout_sets[self._current_cutout_index]
                current_cutout['skybot_queried'] = True
                current_cutout['skybot_results'] = results

                # 同时保存到成员变量（兼容旧代码）
                self._skybot_queried = True
                self._skybot_query_results = results

                count = len(results)
                if count > 0:

                    self.skybot_result_label.config(text=f"找到 {count} 个", foreground="green")
                    success_msg = f"Skybot查询成功，找到 {count} 个小行星"
                    self.logger.info(success_msg)
                    if self.log_callback:
                        self.log_callback(success_msg, "INFO")

                    # 输出详细结果到日志
                    separator = "=" * 80
                    header = "Skybot查询结果详情:"
                    self.logger.info(separator)
                    self.logger.info(header)
                    self.logger.info(separator)
                    if self.log_callback:
                        self.log_callback(separator, "INFO")
                        self.log_callback(header, "INFO")
                        self.log_callback(separator, "INFO")

                    # 获取列名
                    colnames = results.colnames
                    colnames_msg = f"可用列: {', '.join(colnames)}"
                    self.logger.info(colnames_msg)
                    if self.log_callback:
                        self.log_callback(colnames_msg, "INFO")

                    for i, row in enumerate(results, 1):
                        asteroid_header = f"\n第 {i} 个小行星:"
                        self.logger.info(asteroid_header)
                        if self.log_callback:
                            self.log_callback(asteroid_header, "INFO")

                        # 使用字典访问方式，并处理可能不存在的列
                        try:
                            # 常见的列名
                            if 'Name' in colnames:
                                msg = f"  名称: {row['Name']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Number' in colnames:
                                msg = f"  编号: {row['Number']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Type' in colnames:
                                msg = f"  类型: {row['Type']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'RA' in colnames:
                                msg = f"  RA: {row['RA']}°"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'DEC' in colnames:
                                msg = f"  DEC: {row['DEC']}°"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Dg' in colnames:
                                msg = f"  距离: {row['Dg']} AU"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Mv' in colnames:
                                msg = f"  星等: {row['Mv']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'posunc' in colnames:
                                msg = f"  位置不确定度: {row['posunc']} arcsec"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")

                            # 输出所有列（用于调试）
                            full_data_msg = f"  完整数据: {dict(zip(colnames, row))}"
                            self.logger.info(full_data_msg)
                            if self.log_callback:
                                self.log_callback(full_data_msg, "INFO")

                        except Exception as e:
                            error_msg = f"  解析第 {i} 个小行星数据失败: {e}"
                            self.logger.error(error_msg)
                            if self.log_callback:
                                self.log_callback(error_msg, "ERROR")

                    self.logger.info(separator)
                    if self.log_callback:
                        self.log_callback(separator, "INFO")

                    # 更新txt文件中的查询结果
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 紫红色(有结果)
                    self._update_query_button_color('skybot')

                    # 重新绘制图像以显示小行星标记
                    self._refresh_current_cutout_display()
                else:
                    # 查询结果为空（未找到）
                    # 注意：已经在上面保存了results（空列表）到cutout
                    self._skybot_query_results = None  # 兼容旧代码

                    self.skybot_result_label.config(text="未找到", foreground="blue")
                    not_found_msg = "Skybot查询完成，未找到小行星"
                    self.logger.info(not_found_msg)
                    if self.log_callback:
                        self.log_callback(not_found_msg, "INFO")

                    # 更新txt文件，标记为"已查询，未找到"
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 绿色(无结果)
                    self._update_query_button_color('skybot')

                    # 重新绘制图像（虽然没有结果，但确保界面一致性）
                    self._refresh_current_cutout_display()
            else:
                # 查询失败，不保存到cutout（保持未查询状态）
                self._skybot_query_results = None  # 兼容旧代码

                self.skybot_result_label.config(text="查询失败", foreground="red")
                error_msg = "Skybot查询失败"
                self.logger.error(error_msg)
                if self.log_callback:
                    self.log_callback(error_msg, "ERROR")

        except Exception as e:
            exception_msg = f"Skybot查询失败: {str(e)}"
            self.logger.error(exception_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exception_msg, "ERROR")
            self.skybot_result_label.config(text="查询出错", foreground="red")

    def _perform_skybot_query(self, ra, dec, utc_time, mpc_code, latitude, longitude, search_radius=0.01):
        """
        执行Skybot查询

        Args:
            ra: 赤经（度）
            dec: 赤纬（度）
            utc_time: UTC时间（datetime对象）
            mpc_code: MPC观测站代码
            latitude: 纬度（度，仅用于日志）
            longitude: 经度（度，仅用于日志）
            search_radius: 搜索半径（度，默认0.01）

        Returns:
            查询结果表，如果失败返回None
        """
        try:
            from astroquery.imcce import Skybot
            from astropy.time import Time
            from astropy.coordinates import SkyCoord
            import astropy.units as u

            # 转换时间格式
            obs_time = Time(utc_time)

            # 创建坐标对象
            coord = SkyCoord(ra=ra*u.degree, dec=dec*u.degree, frame='icrs')

            # 设置搜索半径
            search_radius_u = search_radius * u.degree

            param_header = f"Skybot查询参数:"
            param_coord = f"  坐标: RA={ra}°, Dec={dec}°"
            param_time = f"  时间: {obs_time.iso}"
            param_station = f"  观测站: MPC code {mpc_code}"
            param_gps = f"  (GPS参考: 经度={longitude}°, 纬度={latitude}°)"
            param_radius = f"  搜索半径: {search_radius}°"

            self.logger.info(param_header)
            self.logger.info(param_coord)
            self.logger.info(param_time)
            self.logger.info(param_station)
            self.logger.info(param_gps)
            self.logger.info(param_radius)

            if self.log_callback:
                self.log_callback(param_header, "INFO")
                self.log_callback(param_coord, "INFO")
                self.log_callback(param_time, "INFO")
                self.log_callback(param_station, "INFO")
                self.log_callback(param_gps, "INFO")
                self.log_callback(param_radius, "INFO")

            # 执行查询，使用MPC观测站代码
            try:
                results = Skybot.cone_search(coord, search_radius_u, obs_time, location=mpc_code)
                return results
            except RuntimeError as e:
                # RuntimeError通常表示"未找到小行星"，这是正常情况
                error_msg = str(e)
                if "No solar system object was found" in error_msg:
                    no_result_msg = "Skybot查询完成：在指定区域未找到小行星"
                    self.logger.info(no_result_msg)
                    if self.log_callback:
                        self.log_callback(no_result_msg, "INFO")
                    # 返回空表而不是None，表示查询成功但无结果
                    from astropy.table import Table
                    return Table()
                else:
                    # 其他RuntimeError仍然作为错误处理
                    error_msg_full = f"Skybot查询失败: {error_msg}"
                    self.logger.error(error_msg_full)
                    if self.log_callback:
                        self.log_callback(error_msg_full, "ERROR")
                    return None

        except ImportError as e:
            import_error_msg = "astroquery未安装或导入失败，请安装: pip install astroquery"
            detail_error_msg = f"详细错误: {e}"
            self.logger.error(import_error_msg)
            self.logger.error(detail_error_msg)
            if self.log_callback:
                self.log_callback(import_error_msg, "ERROR")
                self.log_callback(detail_error_msg, "ERROR")
            return None
        except Exception as e:
            exec_error_msg = f"Skybot查询执行失败: {str(e)}"
            self.logger.error(exec_error_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exec_error_msg, "ERROR")
            return None

    def _query_vsx(self):
        """使用VSX查询变星数据"""
        try:
            # 立即重置结果标签，确保用户能看到查询状态变化
            self.vsx_result_label.config(text="准备中...", foreground="gray")
            self.vsx_result_label.update_idletasks()  # 强制刷新界面

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
                self.vsx_result_label.config(text="坐标缺失", foreground="red")
                return

            ra = float(file_info['ra'])
            dec = float(file_info['dec'])

            # 获取星等限制
            try:
                mag_limit = float(self.vsx_mag_limit_var.get())
            except ValueError:
                self.logger.warning(f"无效的星等限制: {self.vsx_mag_limit_var.get()}，使用默认值20.0")
                mag_limit = 20.0

            # 获取搜索半径
            try:
                search_radius = float(self.search_radius_var.get())
            except ValueError:
                self.logger.warning(f"无效的搜索半径: {self.search_radius_var.get()}，使用默认值0.01")
                search_radius = 0.01

            query_info = f"准备查询VSX: RA={ra}°, Dec={dec}°, 星等限制≤{mag_limit}, 半径={search_radius}°"
            self.logger.info(query_info)
            # 输出到日志标签页
            if self.log_callback:
                self.log_callback(query_info, "INFO")

            self.vsx_result_label.config(text="查询中...", foreground="orange")
            self.vsx_result_label.update_idletasks()  # 强制刷新界面

            # 执行VSX查询
            results = self._perform_vsx_query(ra, dec, mag_limit, search_radius)

            if results is not None:
                # 保存查询结果到当前cutout
                current_cutout = self._all_cutout_sets[self._current_cutout_index]
                current_cutout['vsx_queried'] = True
                current_cutout['vsx_results'] = results

                # 同时保存到成员变量（兼容旧代码）
                self._vsx_queried = True
                self._vsx_query_results = results

                count = len(results)
                if count > 0:

                    self.vsx_result_label.config(text=f"找到 {count} 个", foreground="green")
                    success_msg = f"VSX查询成功，找到 {count} 个变星"
                    self.logger.info(success_msg)
                    if self.log_callback:
                        self.log_callback(success_msg, "INFO")

                    # 输出详细结果到日志
                    separator = "=" * 80
                    header = "VSX查询结果详情:"
                    self.logger.info(separator)
                    self.logger.info(header)
                    self.logger.info(separator)
                    if self.log_callback:
                        self.log_callback(separator, "INFO")
                        self.log_callback(header, "INFO")
                        self.log_callback(separator, "INFO")

                    # 获取列名
                    colnames = results.colnames
                    colnames_msg = f"可用列: {', '.join(colnames)}"
                    self.logger.info(colnames_msg)
                    if self.log_callback:
                        self.log_callback(colnames_msg, "INFO")

                    for i, row in enumerate(results, 1):
                        vstar_header = f"\n第 {i} 个变星:"
                        self.logger.info(vstar_header)
                        if self.log_callback:
                            self.log_callback(vstar_header, "INFO")

                        # 使用字典访问方式，并处理可能不存在的列
                        try:
                            # 常见的列名
                            if 'Name' in colnames:
                                msg = f"  名称: {row['Name']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Type' in colnames:
                                msg = f"  类型: {row['Type']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'RAJ2000' in colnames:
                                msg = f"  RA: {row['RAJ2000']}°"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'DEJ2000' in colnames:
                                msg = f"  DEC: {row['DEJ2000']}°"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'max' in colnames:
                                msg = f"  最大星等: {row['max']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'min' in colnames:
                                msg = f"  最小星等: {row['min']}"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")
                            if 'Period' in colnames:
                                msg = f"  周期: {row['Period']} 天"
                                self.logger.info(msg)
                                if self.log_callback:
                                    self.log_callback(msg, "INFO")

                            # 输出所有列（用于调试）
                            full_data_msg = f"  完整数据: {dict(zip(colnames, row))}"
                            self.logger.info(full_data_msg)
                            if self.log_callback:
                                self.log_callback(full_data_msg, "INFO")

                        except Exception as e:
                            error_msg = f"  解析第 {i} 个变星数据失败: {e}"
                            self.logger.error(error_msg)
                            if self.log_callback:
                                self.log_callback(error_msg, "ERROR")

                    self.logger.info(separator)
                    if self.log_callback:
                        self.log_callback(separator, "INFO")

                    # 更新txt文件中的查询结果
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 紫红色(有结果)
                    self._update_query_button_color('vsx')

                    # 重新绘制图像以显示变星标记
                    self._refresh_current_cutout_display()
                else:
                    # 查询结果为空（未找到）
                    # 注意：已经在上面保存了results（空列表）到cutout
                    self._vsx_query_results = None  # 兼容旧代码

                    self.vsx_result_label.config(text="未找到", foreground="blue")
                    not_found_msg = "VSX查询完成，未找到变星"
                    self.logger.info(not_found_msg)
                    if self.log_callback:
                        self.log_callback(not_found_msg, "INFO")

                    # 更新txt文件，标记为"已查询，未找到"
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 绿色(无结果)
                    self._update_query_button_color('vsx')

                    # 重新绘制图像（虽然没有结果，但确保界面一致性）
                    self._refresh_current_cutout_display()
            else:
                # 查询失败，不保存到cutout（保持未查询状态）
                self._vsx_query_results = None  # 兼容旧代码

                self.vsx_result_label.config(text="查询失败", foreground="red")
                error_msg = "VSX查询失败"
                self.logger.error(error_msg)
                if self.log_callback:
                    self.log_callback(error_msg, "ERROR")

        except Exception as e:
            exception_msg = f"VSX查询失败: {str(e)}"
            self.logger.error(exception_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exception_msg, "ERROR")
            self.vsx_result_label.config(text="查询出错", foreground="red")

    def _perform_vsx_query(self, ra, dec, mag_limit=16.0, search_radius=0.01):
        """
        执行VSX变星查询

        Args:
            ra: 赤经（度）
            dec: 赤纬（度）
            mag_limit: 星等限制（只返回最大星等≤此值的变星）
            search_radius: 搜索半径（度，默认0.01）

        Returns:
            查询结果表，如果失败返回None
        """
        try:
            from astroquery.vizier import Vizier
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            import numpy as np

            # 创建坐标对象
            coord = SkyCoord(ra=ra*u.degree, dec=dec*u.degree, frame='icrs')

            # 设置搜索半径
            search_radius_u = search_radius * u.degree

            param_header = f"VSX查询参数:"
            param_coord = f"  坐标: RA={ra}°, Dec={dec}°"
            param_radius = f"  搜索半径: {search_radius}°"
            param_mag = f"  星等限制: ≤{mag_limit}"

            self.logger.info(param_header)
            self.logger.info(param_coord)
            self.logger.info(param_radius)
            self.logger.info(param_mag)
            if self.log_callback:
                self.log_callback(param_header, "INFO")
                self.log_callback(param_coord, "INFO")
                self.log_callback(param_radius, "INFO")
                self.log_callback(param_mag, "INFO")

            # 执行查询，使用VizieR查询VSX目录
            # VSX目录在VizieR中的标识是 "B/vsx/vsx"
            v = Vizier(columns=['**'], row_limit=5)  # 获取所有列，不限制行数
            try:
                results = v.query_region(coord, radius=search_radius_u, catalog="B/vsx/vsx")

                if results and len(results) > 0:
                    # VizieR返回的是TableList，取第一个表
                    table = results[0]

                    # 应用星等过滤
                    # VSX中的星等列名可能是 'max' (最大星等，即最亮时)
                    if 'max' in table.colnames and len(table) > 0:
                        # 过滤掉最大星等(最亮时)大于限制的变星
                        # 注意：需要处理masked值和无效值
                        try:
                            # 创建有效的掩码
                            valid_mask = np.ones(len(table), dtype=bool)

                            for i, mag_val in enumerate(table['max']):
                                try:
                                    # 尝试转换为浮点数
                                    if hasattr(mag_val, 'mask') and mag_val.mask:
                                        # 如果是masked值，保留该行（不过滤）
                                        continue
                                    mag_float = float(mag_val)
                                    if mag_float > mag_limit:
                                        valid_mask[i] = False
                                except (ValueError, TypeError):
                                    # 如果无法转换，保留该行（不过滤）
                                    continue

                            table = table[valid_mask]
                            filter_msg = f"星等过滤后剩余 {len(table)} 个变星"
                            self.logger.info(filter_msg)
                            if self.log_callback:
                                self.log_callback(filter_msg, "INFO")
                        except Exception as e:
                            filter_error = f"星等过滤失败: {str(e)}，返回未过滤结果"
                            self.logger.warning(filter_error)
                            if self.log_callback:
                                self.log_callback(filter_error, "WARNING")

                    return table
                else:
                    # 返回空表而不是None，表示查询成功但无结果
                    from astropy.table import Table
                    return Table()

            except Exception as e:
                error_msg = f"VSX查询失败: {str(e)}"
                self.logger.error(error_msg)
                if self.log_callback:
                    self.log_callback(error_msg, "ERROR")
                return None

        except ImportError as e:
            import_error_msg = "astroquery未安装或导入失败，请安装: pip install astroquery"
            detail_error_msg = f"详细错误: {e}"
            self.logger.error(import_error_msg)
            self.logger.error(detail_error_msg)
            if self.log_callback:
                self.log_callback(import_error_msg, "ERROR")
                self.log_callback(detail_error_msg, "ERROR")
            return None
        except Exception as e:
            exec_error_msg = f"VSX查询执行失败: {str(e)}"
            self.logger.error(exec_error_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exec_error_msg, "ERROR")
            return None

    def _query_satellite(self):
        """使用Skyfield查询卫星数据"""
        try:
            # 立即重置结果标签，确保用户能看到查询状态变化
            self.satellite_result_label.config(text="准备中...", foreground="gray")
            self.satellite_result_label.update_idletasks()  # 强制刷新界面

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
                self.satellite_result_label.config(text="坐标缺失", foreground="red")
                return

            ra = float(file_info['ra'])
            dec = float(file_info['dec'])

            # 检查是否有UTC时间
            if not hasattr(self, '_current_utc_time') or not self._current_utc_time:
                self.logger.error("无法获取UTC时间信息")
                self.satellite_result_label.config(text="时间缺失", foreground="red")
                return

            utc_time = self._current_utc_time

            # 获取GPS位置
            try:
                latitude = float(self.gps_lat_var.get())
                longitude = float(self.gps_lon_var.get())
            except ValueError:
                self.logger.error(f"无效的GPS坐标: 纬度={self.gps_lat_var.get()}, 经度={self.gps_lon_var.get()}")
                self.satellite_result_label.config(text="GPS无效", foreground="red")
                return

            # 获取搜索半径
            try:
                search_radius = float(self.search_radius_var.get())
            except ValueError:
                self.logger.warning(f"无效的搜索半径: {self.search_radius_var.get()}，使用默认值0.01")
                search_radius = 0.01

            query_info = f"准备查询卫星: RA={ra}°, Dec={dec}°, UTC={utc_time}, GPS=({latitude}°N, {longitude}°E), 半径={search_radius}°"
            self.logger.info(query_info)
            # 输出到日志标签页
            if self.log_callback:
                self.log_callback(query_info, "INFO")

            self.satellite_result_label.config(text="查询中...", foreground="orange")
            self.satellite_result_label.update_idletasks()  # 强制刷新界面

            # 执行卫星查询
            results = self._perform_satellite_query(ra, dec, utc_time, latitude, longitude, search_radius)

            if results is not None:
                # 保存查询结果到当前cutout
                current_cutout = self._all_cutout_sets[self._current_cutout_index]
                current_cutout['satellite_queried'] = True
                current_cutout['satellite_results'] = results

                # 同时保存到成员变量（兼容旧代码）
                self._satellite_queried = True
                self._satellite_query_results = results

                if len(results) > 0:
                    # 查询成功且有结果
                    self.satellite_result_label.config(text=f"找到 {len(results)} 个", foreground="green")
                    success_msg = f"卫星查询完成，找到 {len(results)} 个卫星"
                    self.logger.info(success_msg)
                    if self.log_callback:
                        self.log_callback(success_msg, "INFO")

                    # 输出详细结果
                    for i, sat in enumerate(results, 1):
                        sat_detail = f"  卫星 {i}: {sat.get('name', 'Unknown')} - 距离={sat.get('separation', 0):.4f}°"
                        self.logger.info(sat_detail)
                        if self.log_callback:
                            self.log_callback(sat_detail, "INFO")

                    # 更新txt文件中的查询结果
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 紫红色(有结果)
                    self._update_query_button_color('satellite')

                    # 重新绘制图像以显示卫星标记
                    self._refresh_current_cutout_display()
                else:
                    # 查询结果为空（未找到）
                    self._satellite_query_results = None  # 兼容旧代码

                    self.satellite_result_label.config(text="未找到", foreground="blue")
                    not_found_msg = "卫星查询完成，未找到卫星"
                    self.logger.info(not_found_msg)
                    if self.log_callback:
                        self.log_callback(not_found_msg, "INFO")

                    # 更新txt文件，标记为"已查询，未找到"
                    self._update_detection_txt_with_query_results()

                    # 更新按钮颜色 - 绿色(无结果)
                    self._update_query_button_color('satellite')

                    # 重新绘制图像（虽然没有结果，但确保界面一致性）
                    self._refresh_current_cutout_display()
            else:
                # 查询失败，不保存到cutout（保持未查询状态）
                self._satellite_query_results = None  # 兼容旧代码

                self.satellite_result_label.config(text="查询失败", foreground="red")
                error_msg = "卫星查询失败"
                self.logger.error(error_msg)
                if self.log_callback:
                    self.log_callback(error_msg, "ERROR")

        except Exception as e:
            exception_msg = f"卫星查询失败: {str(e)}"
            self.logger.error(exception_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exception_msg, "ERROR")
            self.satellite_result_label.config(text="查询出错", foreground="red")

    def _perform_satellite_query(self, ra, dec, utc_time, latitude, longitude, search_radius=0.01):
        """
        执行卫星查询

        Args:
            ra: 赤经（度）
            dec: 赤纬（度）
            utc_time: UTC时间（datetime对象）
            latitude: 纬度（度）
            longitude: 经度（度）
            search_radius: 搜索半径（度，默认0.01）

        Returns:
            查询结果列表，如果失败返回None
        """
        try:
            from skyfield.api import load, wgs84, EarthSatellite
            from skyfield.toposlib import GeographicPosition
            import numpy as np

            param_header = f"卫星查询参数:"
            param_coord = f"  坐标: RA={ra}°, Dec={dec}°"
            param_time = f"  时间: {utc_time}"
            param_gps = f"  观测位置: 纬度={latitude}°N, 经度={longitude}°E"
            param_radius = f"  搜索半径: {search_radius}°"

            self.logger.info(param_header)
            self.logger.info(param_coord)
            self.logger.info(param_time)
            self.logger.info(param_gps)
            self.logger.info(param_radius)
            if self.log_callback:
                self.log_callback(param_header, "INFO")
                self.log_callback(param_coord, "INFO")
                self.log_callback(param_time, "INFO")
                self.log_callback(param_gps, "INFO")
                self.log_callback(param_radius, "INFO")

            # 加载时间尺度
            ts = load.timescale()
            t = ts.utc(utc_time.year, utc_time.month, utc_time.day,
                      utc_time.hour, utc_time.minute, utc_time.second)

            # 创建观测位置
            observer = wgs84.latlon(latitude, longitude)

            # 加载TLE数据（使用最新的活跃卫星数据）
            # 这里使用Celestrak的活跃卫星TLE数据
            try:
                satellites = load.tle_file('https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle')
                self.logger.info(f"成功加载 {len(satellites)} 个卫星的TLE数据")
                if self.log_callback:
                    self.log_callback(f"成功加载 {len(satellites)} 个卫星的TLE数据", "INFO")
            except Exception as e:
                error_msg = f"加载TLE数据失败: {str(e)}"
                self.logger.error(error_msg)
                if self.log_callback:
                    self.log_callback(error_msg, "ERROR")
                return None

            # 查找在搜索半径内的卫星
            results = []
            for satellite in satellites:
                try:
                    # 计算卫星在观测时间和位置的位置
                    geocentric = satellite.at(t)
                    topocentric = (geocentric - observer.at(t))
                    sat_ra, sat_dec, distance = topocentric.radec()

                    # 计算角距离
                    sat_ra_deg = sat_ra._degrees
                    sat_dec_deg = sat_dec.degrees

                    # 简单的角距离计算（球面三角）
                    delta_ra = np.radians(sat_ra_deg - ra)
                    delta_dec = np.radians(sat_dec_deg - dec)
                    ra_rad = np.radians(ra)
                    dec_rad = np.radians(dec)
                    sat_dec_rad = np.radians(sat_dec_deg)

                    separation = np.degrees(np.arccos(
                        np.sin(dec_rad) * np.sin(sat_dec_rad) +
                        np.cos(dec_rad) * np.cos(sat_dec_rad) * np.cos(delta_ra)
                    ))

                    # 如果在搜索半径内，添加到结果
                    if separation <= search_radius:
                        results.append({
                            'name': satellite.name,
                            'ra': sat_ra_deg,
                            'dec': sat_dec_deg,
                            'separation': separation,
                            'distance_km': distance.km
                        })
                except Exception as e:
                    # 跳过有问题的卫星
                    continue

            return results

        except ImportError as e:
            import_error_msg = "skyfield未安装或导入失败，请安装: pip install skyfield"
            detail_error_msg = f"详细错误: {e}"
            self.logger.error(import_error_msg)
            self.logger.error(detail_error_msg)
            if self.log_callback:
                self.log_callback(import_error_msg, "ERROR")
                self.log_callback(detail_error_msg, "ERROR")
            return None
        except Exception as e:
            exec_error_msg = f"卫星查询执行失败: {str(e)}"
            self.logger.error(exec_error_msg, exc_info=True)
            if self.log_callback:
                self.log_callback(exec_error_msg, "ERROR")
            return None

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

    def _save_detection_result(self):
        """保存当前显示的检测结果到output文件夹"""
        try:
            # 检查是否有当前显示的cutout
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                messagebox.showwarning("警告", "请先执行差分检测并显示检测结果")
                return

            if not hasattr(self, '_current_cutout_index'):
                messagebox.showwarning("警告", "没有当前显示的检测结果")
                return

            # 获取当前cutout的信息
            current_cutout = self._all_cutout_sets[self._current_cutout_index]
            reference_img = current_cutout['reference']
            aligned_img = current_cutout['aligned']
            detection_img = current_cutout['detection']

            # 获取输出目录（last_output_dir）
            if not self.last_output_dir or not os.path.exists(self.last_output_dir):
                messagebox.showwarning("警告", "无法找到输出目录")
                return

            # 从cutout文件名提取检测目标编号
            # 文件名格式: 001_RA285.123456_DEC43.567890_GY5_K096_1_reference.png
            # 或: 001_X1234_Y5678_GY5_K096_1_reference.png
            reference_basename = os.path.basename(reference_img)
            import re

            # 提取序号（前3位数字）
            match = re.match(r'(\d{3})_', reference_basename)
            if not match:
                messagebox.showerror("错误", f"无法解析检测结果文件名: {reference_basename}")
                self.logger.error(f"文件名格式不匹配: {reference_basename}")
                return

            detection_num = match.group(1)

            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 获取detected根目录
            detected_root = None

            # 优先从配置管理器获取detected目录
            if self.config_manager:
                last_selected = self.config_manager.get_last_selected()
                detected_dir = last_selected.get("detected_directory", "")
                if detected_dir and os.path.exists(os.path.dirname(detected_dir)):
                    # 配置的detected目录直接作为根目录
                    detected_root = Path(detected_dir)
                    self.logger.info(f"使用配置的detected目录: {detected_root}")

            # 如果配置中没有或目录不存在，尝试从diff_output目录推断
            if not detected_root:
                self.logger.info("配置中没有detected目录，从diff_output目录推断")
                # 路径结构: diff_output/系统名/日期/天区/文件名/detection_xxx
                # 需要找到diff_output目录
                current_path = Path(self.last_output_dir)
                diff_output_root = None

                # 向上查找，直到找到包含多个系统目录的根目录
                for parent in current_path.parents:
                    # 检查是否是diff_output根目录（通常名为diff_output或包含系统名子目录）
                    if parent.name == 'diff_output' or (parent.parent and parent.parent.name == 'diff_output'):
                        diff_output_root = parent if parent.name == 'diff_output' else parent.parent
                        break

                # 如果没找到，使用last_output_dir的上5级目录
                if not diff_output_root:
                    diff_output_root = current_path.parents[4] if len(list(current_path.parents)) > 4 else current_path.parent

                # 在diff_output根目录下创建detected目录
                detected_root = diff_output_root / "detected"
                self.logger.info(f"推断的detected目录: {detected_root}")

            # 创建带日期的子目录：detected/YYYYMMDD/
            date_str = datetime.now().strftime("%Y%m%d")
            detected_date_dir = detected_root / date_str

            # 创建保存目录：detected/YYYYMMDD/saved_HHMMSS_NNN/
            save_dir = detected_date_dir / f"saved_{timestamp[9:]}_{detection_num}"
            save_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"最终保存目录: {save_dir}")

            self.logger.info(f"开始保存检测结果 #{detection_num} 到: {save_dir}")

            # 1. 收集并保存参数信息
            params_file = save_dir / "detection_parameters.txt"
            self._save_detection_parameters(str(params_file), detection_num, timestamp)

            # 2. 复制cutout图片
            import shutil
            shutil.copy2(reference_img, str(save_dir / os.path.basename(reference_img)))
            shutil.copy2(aligned_img, str(save_dir / os.path.basename(aligned_img)))
            shutil.copy2(detection_img, str(save_dir / os.path.basename(detection_img)))
            self.logger.info("已复制cutout图片")

            # 3. 查找并复制noise_cleaned_aligned.fits文件
            parent_dir = Path(self.last_output_dir)
            noise_cleaned_files = list(parent_dir.glob("*noise_cleaned_aligned.fits"))
            for fits_file in noise_cleaned_files:
                shutil.copy2(str(fits_file), str(save_dir / fits_file.name))
            self.logger.info(f"已复制 {len(noise_cleaned_files)} 个noise_cleaned_aligned.fits文件")

            # 4. 查找并复制aligned_comparison文件
            aligned_comparison_files = list(parent_dir.glob("aligned_comparison_*"))
            for comp_file in aligned_comparison_files:
                if comp_file.is_file():
                    shutil.copy2(str(comp_file), str(save_dir / comp_file.name))
            self.logger.info(f"已复制 {len(aligned_comparison_files)} 个aligned_comparison文件")

            # 5. 复制整个cutouts目录
            cutouts_src = parent_dir / "cutouts"
            if cutouts_src.exists():
                cutouts_dst = save_dir / "cutouts"
                if cutouts_dst.exists():
                    shutil.rmtree(str(cutouts_dst))
                shutil.copytree(str(cutouts_src), str(cutouts_dst))
                self.logger.info("已复制cutouts目录")

            # 合并成一个弹窗：显示成功消息并询问是否打开
            result = messagebox.askquestion(
                "保存成功",
                f"检测结果 #{detection_num} 已保存到:\n{save_dir}\n\n是否打开保存目录？",
                icon='info'
            )

            self.logger.info(f"检测结果保存完成: {save_dir}")

            if result == 'yes':
                self._open_directory_in_explorer(str(save_dir))

        except Exception as e:
            error_msg = f"保存检测结果失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("错误", error_msg)

    def _update_query_button_color(self, query_type='skybot'):
        """
        更新查询按钮的颜色以反映查询状态（从当前cutout读取）

        Args:
            query_type: 'skybot', 'vsx' 或 'satellite'
        """
        try:
            # 检查是否有当前cutout
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                return

            if not hasattr(self, '_current_cutout_index'):
                return

            current_cutout = self._all_cutout_sets[self._current_cutout_index]

            if query_type == 'skybot':
                button = self.skybot_button
                label = self.skybot_result_label
                queried = current_cutout.get('skybot_queried', False)
                results = current_cutout.get('skybot_results', None)
            elif query_type == 'vsx':
                button = self.vsx_button
                label = self.vsx_result_label
                queried = current_cutout.get('vsx_queried', False)
                results = current_cutout.get('vsx_results', None)
            else:  # satellite
                button = self.satellite_button
                label = self.satellite_result_label
                queried = current_cutout.get('satellite_queried', False)
                results = current_cutout.get('satellite_results', None)

            if not queried:
                # 未查询 - 橙黄色
                button.config(bg="#FFA500")
                label.config(text="未查询", foreground="gray")
            elif results is None or len(results) == 0:
                # 已查询但无结果 - 绿色
                button.config(bg="#00C853")
                label.config(text="未找到", foreground="blue")
            else:
                # 有结果 - 紫红色
                button.config(bg="#C2185B")
                count = len(results)
                label.config(text=f"找到 {count} 个", foreground="green")

        except Exception as e:
            self.logger.error(f"更新查询按钮颜色失败: {str(e)}")

    def _check_existing_query_results(self, query_type='skybot'):
        """
        检查当前cutout目录的query_results.txt文件中是否已有查询结果

        Args:
            query_type: 'skybot', 'vsx' 或 'satellite'

        Returns:
            tuple: (has_result, result_text)
                has_result: True表示已查询过（无论是否找到），False表示未查询
                result_text: 查询结果文本描述
        """
        try:
            # 检查是否有当前cutout
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                return False, None

            if not hasattr(self, '_current_cutout_index'):
                return False, None

            current_cutout = self._all_cutout_sets[self._current_cutout_index]

            # 从cutout的detection文件路径获取cutout目录
            detection_img = current_cutout.get('detection')
            if not detection_img or not os.path.exists(detection_img):
                return False, None

            # cutout目录是detection图像的父目录
            cutout_dir = os.path.dirname(detection_img)
            # 使用检测目标序号作为文件名的一部分
            query_results_file = os.path.join(cutout_dir, f"query_results_{self._current_cutout_index + 1:03d}.txt")

            # 如果文件不存在，返回未查询
            if not os.path.exists(query_results_file):
                return False, None

            # 读取文件内容
            with open(query_results_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 根据查询类型检查对应的列表
            if query_type == 'skybot':
                # 查找小行星列表部分
                import re
                match = re.search(r'小行星列表:\n((?:  - .*\n)+)', content)
                if match:
                    result_lines = match.group(1).strip()
                    if '(未查询)' in result_lines:
                        return False, None  # 未查询
                    elif '(已查询，未找到)' in result_lines:
                        return True, "已查询，未找到"  # 已查询但未找到
                    else:
                        # 已查询且找到结果
                        count = len(result_lines.split('\n'))
                        return True, f"已查询，找到 {count} 个"
            elif query_type == 'vsx':
                # 查找变星列表部分
                import re
                match = re.search(r'变星列表:\n((?:  - .*\n)+)', content)
                if match:
                    result_lines = match.group(1).strip()
                    if '(未查询)' in result_lines:
                        return False, None  # 未查询
                    elif '(已查询，未找到)' in result_lines:
                        return True, "已查询，未找到"  # 已查询但未找到
                    else:
                        # 已查询且找到结果
                        count = len(result_lines.split('\n'))
                        return True, f"已查询，找到 {count} 个"
            else:  # satellite
                # 查找卫星列表部分
                import re
                match = re.search(r'卫星列表:\n((?:  - .*\n)+)', content)
                if match:
                    result_lines = match.group(1).strip()
                    if '(未查询)' in result_lines:
                        return False, None  # 未查询
                    elif '(已查询，未找到)' in result_lines:
                        return True, "已查询，未找到"  # 已查询但未找到
                    else:
                        # 已查询且找到结果
                        count = len(result_lines.split('\n'))
                        return True, f"已查询，找到 {count} 个"

            return False, None

        except Exception as e:
            self.logger.error(f"检查已有查询结果失败: {str(e)}")
            return False, None

    def _update_detection_txt_with_query_results(self):
        """将查询结果保存到当前cutout目录的query_results.txt文件中"""
        try:
            # 检查是否有当前cutout
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.warning("没有当前cutout，无法保存查询结果")
                return

            if not hasattr(self, '_current_cutout_index'):
                self.logger.warning("没有当前cutout索引，无法保存查询结果")
                return

            current_cutout = self._all_cutout_sets[self._current_cutout_index]

            # 从cutout的detection文件路径获取cutout目录
            detection_img = current_cutout.get('detection')
            if not detection_img or not os.path.exists(detection_img):
                self.logger.warning(f"检测图像文件不存在: {detection_img}")
                return

            # cutout目录是detection图像的父目录
            cutout_dir = os.path.dirname(detection_img)

            # 使用检测目标序号作为文件名的一部分，避免覆盖
            query_results_file = os.path.join(cutout_dir, f"query_results_{self._current_cutout_index + 1:03d}.txt")

            self.logger.info(f"保存查询结果到: {query_results_file}")

            # 从当前cutout读取查询结果
            skybot_queried = current_cutout.get('skybot_queried', False)
            skybot_results = current_cutout.get('skybot_results', None)
            vsx_queried = current_cutout.get('vsx_queried', False)
            vsx_results = current_cutout.get('vsx_results', None)
            satellite_queried = current_cutout.get('satellite_queried', False)
            satellite_results = current_cutout.get('satellite_results', None)

            # 准备小行星列表内容
            skybot_lines = []
            if skybot_queried:
                if skybot_results is not None and len(skybot_results) > 0:
                    colnames = skybot_results.colnames
                    for i, row in enumerate(skybot_results, 1):
                        asteroid_info = []
                        if 'Name' in colnames:
                            asteroid_info.append(f"名称={row['Name']}")
                        if 'Number' in colnames:
                            asteroid_info.append(f"编号={row['Number']}")
                        if 'Type' in colnames:
                            asteroid_info.append(f"类型={row['Type']}")
                        if 'RA' in colnames:
                            asteroid_info.append(f"RA={row['RA']:.6f}°")
                        if 'DEC' in colnames:
                            asteroid_info.append(f"DEC={row['DEC']:.6f}°")
                        if 'Mv' in colnames:
                            asteroid_info.append(f"星等={row['Mv']}")
                        if 'Dg' in colnames:
                            asteroid_info.append(f"距离={row['Dg']}AU")
                        skybot_lines.append(f"  - 小行星{i}: {', '.join(asteroid_info)}")
                else:
                    skybot_lines.append("  - (已查询，未找到)")
            else:
                skybot_lines.append("  - (未查询)")

            # 准备变星列表内容
            vsx_lines = []
            if vsx_queried:
                if vsx_results is not None and len(vsx_results) > 0:
                    colnames = vsx_results.colnames
                    for i, row in enumerate(vsx_results, 1):
                        vstar_info = []
                        if 'Name' in colnames:
                            vstar_info.append(f"名称={row['Name']}")
                        if 'Type' in colnames:
                            vstar_info.append(f"类型={row['Type']}")
                        if 'RAJ2000' in colnames:
                            vstar_info.append(f"RA={row['RAJ2000']:.6f}°")
                        if 'DEJ2000' in colnames:
                            vstar_info.append(f"DEC={row['DEJ2000']:.6f}°")
                        if 'max' in colnames:
                            vstar_info.append(f"最大星等={row['max']}")
                        if 'min' in colnames:
                            vstar_info.append(f"最小星等={row['min']}")
                        if 'Period' in colnames:
                            vstar_info.append(f"周期={row['Period']}天")
                        vsx_lines.append(f"  - 变星{i}: {', '.join(vstar_info)}")
                else:
                    vsx_lines.append("  - (已查询，未找到)")
            else:
                vsx_lines.append("  - (未查询)")

            # 写入查询结果文件
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(query_results_file, 'w', encoding='utf-8') as f:
                f.write(f"查询结果\n")
                f.write(f"=" * 80 + "\n")
                f.write(f"时间: {timestamp}\n")
                f.write(f"检测目标序号: {self._current_cutout_index + 1}\n\n")

                f.write(f"小行星列表:\n")
                for line in skybot_lines:
                    f.write(f"{line}\n")
                f.write("\n")

                f.write(f"变星列表:\n")
                for line in vsx_lines:
                    f.write(f"{line}\n")
                f.write("\n")

                # 准备卫星列表内容
                satellite_lines = []
                if satellite_queried:
                    if satellite_results is not None and len(satellite_results) > 0:
                        for i, sat in enumerate(satellite_results, 1):
                            sat_info = []
                            if 'name' in sat:
                                sat_info.append(f"名称={sat['name']}")
                            if 'ra' in sat:
                                sat_info.append(f"RA={sat['ra']:.6f}°")
                            if 'dec' in sat:
                                sat_info.append(f"DEC={sat['dec']:.6f}°")
                            if 'separation' in sat:
                                sat_info.append(f"角距离={sat['separation']:.4f}°")
                            if 'distance_km' in sat:
                                sat_info.append(f"距离={sat['distance_km']:.1f}km")
                            satellite_lines.append(f"  - 卫星{i}: {', '.join(sat_info)}")
                    else:
                        satellite_lines.append("  - (已查询，未找到)")
                else:
                    satellite_lines.append("  - (未查询)")

                f.write(f"卫星列表:\n")
                for line in satellite_lines:
                    f.write(f"{line}\n")
                f.write("\n")

            self.logger.info(f"查询结果已保存到: {query_results_file}")

        except Exception as e:
            self.logger.error(f"更新txt文件失败: {str(e)}", exc_info=True)

    def _save_detection_parameters(self, params_file, detection_num, timestamp):
        """保存检测参数到文本文件"""
        try:
            with open(params_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"检测结果参数信息 - 检测目标 #{detection_num}\n")
                f.write("=" * 60 + "\n\n")

                # 基本信息
                f.write(f"检测时间: {timestamp[:8]}-{timestamp[9:]}\n")
                f.write(f"检测编号: {detection_num}\n")
                f.write(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 文件信息
                if self.selected_file_path:
                    f.write(f"选中文件: {os.path.basename(self.selected_file_path)}\n")
                    f.write(f"文件路径: {self.selected_file_path}\n\n")

                # 坐标信息（从显示框读取）
                f.write("坐标信息:\n")
                f.write(f"  度格式: {self.coord_deg_entry.get()}\n")
                f.write(f"  时分秒: {self.coord_hms_entry.get()}\n")
                f.write(f"  紧凑格式: {self.coord_compact_entry.get()}\n\n")

                # 时间信息
                f.write("时间信息:\n")
                f.write(f"  UTC: {self.time_utc_entry.get()}\n")
                f.write(f"  北京时间: {self.time_beijing_entry.get()}\n")
                f.write(f"  本地时间: {self.time_local_entry.get()}\n\n")

                # GPS信息
                if self.config_manager:
                    gps_settings = self.config_manager.get_gps_settings()
                    f.write("GPS信息:\n")
                    f.write(f"  纬度: {gps_settings.get('latitude', 'N/A')}°\n")
                    f.write(f"  经度: {gps_settings.get('longitude', 'N/A')}°\n\n")

                # MPC信息
                if self.config_manager:
                    mpc_settings = self.config_manager.get_mpc_settings()
                    f.write("MPC信息:\n")
                    f.write(f"  观测站代码: {mpc_settings.get('mpc_code', 'N/A')}\n\n")

                # Diff处理参数
                if self.config_manager:
                    batch_settings = self.config_manager.get_batch_process_settings()
                    f.write("Diff处理参数:\n")
                    f.write(f"  降噪方法: {batch_settings.get('noise_method', 'N/A')}\n")
                    f.write(f"  对齐方法: {batch_settings.get('alignment_method', 'N/A')}\n")
                    f.write(f"  去除亮线: {batch_settings.get('remove_bright_lines', 'N/A')}\n")
                    f.write(f"  快速模式: {batch_settings.get('fast_mode', 'N/A')}\n")
                    f.write(f"  拉伸方法: {batch_settings.get('stretch_method', 'N/A')}\n")
                    f.write(f"  百分位参数: {batch_settings.get('percentile_low', 'N/A')}\n")
                    f.write(f"  最大锯齿比率: {batch_settings.get('max_jaggedness_ratio', 'N/A')}\n\n")

                # Skybot查询结果
                skybot_result = self.skybot_result_label.cget("text")
                f.write(f"Skybot查询结果: {skybot_result}\n")

                # VSX查询结果
                vsx_result = self.vsx_result_label.cget("text")
                f.write(f"VSX查询结果: {vsx_result}\n\n")

                f.write("=" * 60 + "\n")
                f.write("参数文件结束\n")
                f.write("=" * 60 + "\n")

            self.logger.info(f"参数文件已保存: {params_file}")

        except Exception as e:
            self.logger.error(f"保存参数文件失败: {str(e)}")

    def _batch_delete_query_results(self):
        """批量删除查询结果文件"""
        try:
            # 获取当前选中的节点
            selection = self.directory_tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请先选择一个目录或文件")
                return

            item = selection[0]
            values = self.directory_tree.item(item, "values")
            tags = self.directory_tree.item(item, "tags")

            if not values:
                messagebox.showwarning("警告", "请选择一个目录或文件")
                return

            # 判断是文件还是目录
            is_file = "fits_file" in tags

            if is_file:
                # 选中的是单个文件
                file_path = values[0]

                # 检查文件是否有diff结果
                if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                    messagebox.showinfo("提示", "该文件没有检测结果")
                    return

                # 确认删除
                result = messagebox.askyesno("确认删除",
                                            f"确定要删除该文件的所有查询结果吗？\n\n文件: {os.path.basename(file_path)}")
                if not result:
                    return

                # 删除当前文件的所有查询结果
                deleted_count = self._delete_query_results_for_current_file()
                messagebox.showinfo("完成", f"已删除 {deleted_count} 个查询结果文件")
                self.logger.info(f"已删除 {deleted_count} 个查询结果文件")

                # 刷新显示
                if hasattr(self, '_current_cutout_index'):
                    self._display_cutout_by_index(self._current_cutout_index)

            else:
                # 选中的是目录
                directory = values[0]

                # 确认删除
                result = messagebox.askyesno("确认删除",
                                            f"确定要删除该目录下所有文件的查询结果吗？\n\n目录: {directory}\n\n这将删除所有 query_results_*.txt 文件")
                if not result:
                    return

                # 获取对应的输出目录
                output_directory = self._get_output_directory_from_download_directory(directory)
                if not output_directory:
                    messagebox.showwarning("警告", "未找到对应的输出目录")
                    return

                self.logger.info(f"下载目录: {directory}")
                self.logger.info(f"输出目录: {output_directory}")

                # 删除输出目录下的所有查询结果文件
                deleted_count = self._delete_query_results_for_directory(output_directory)
                messagebox.showinfo("完成", f"已删除 {deleted_count} 个查询结果文件")
                self.logger.info(f"已删除 {deleted_count} 个查询结果文件")

        except Exception as e:
            error_msg = f"批量删除查询结果失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("错误", error_msg)

    def _delete_query_results_for_current_file(self):
        """删除当前文件的所有查询结果"""
        deleted_count = 0
        try:
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                return 0

            for idx, cutout_set in enumerate(self._all_cutout_sets):
                detection_img = cutout_set.get('detection')
                if not detection_img or not os.path.exists(detection_img):
                    continue

                cutout_dir = os.path.dirname(detection_img)
                query_results_file = os.path.join(cutout_dir, f"query_results_{idx + 1:03d}.txt")

                if os.path.exists(query_results_file):
                    try:
                        os.remove(query_results_file)
                        deleted_count += 1
                        self.logger.info(f"已删除: {query_results_file}")

                        # 重置查询状态
                        cutout_set['skybot_queried'] = False
                        cutout_set['vsx_queried'] = False
                        cutout_set['skybot_results'] = None
                        cutout_set['vsx_results'] = None
                    except Exception as e:
                        self.logger.error(f"删除文件失败 {query_results_file}: {str(e)}")

        except Exception as e:
            self.logger.error(f"删除当前文件查询结果失败: {str(e)}")

        return deleted_count

    def _get_output_directory_from_download_directory(self, download_directory):
        """根据下载目录获取对应的输出目录"""
        try:
            # 获取配置的输出目录
            base_output_dir = None
            if self.get_diff_output_dir_callback:
                base_output_dir = self.get_diff_output_dir_callback()

            if not base_output_dir or not os.path.exists(base_output_dir):
                self.logger.warning("输出目录不存在")
                return None

            # 获取下载目录
            download_dir = None
            if self.get_download_dir_callback:
                download_dir = self.get_download_dir_callback()

            if not download_dir:
                self.logger.warning("下载目录不存在")
                return None

            # 标准化路径
            normalized_download_directory = os.path.normpath(download_directory)
            normalized_download_dir = os.path.normpath(download_dir)

            # 获取相对路径
            try:
                relative_path = os.path.relpath(normalized_download_directory, normalized_download_dir)
            except ValueError:
                self.logger.warning(f"无法计算相对路径: {normalized_download_directory} 相对于 {normalized_download_dir}")
                return None

            # 构建输出目录路径
            output_directory = os.path.join(base_output_dir, relative_path)

            if not os.path.exists(output_directory):
                self.logger.warning(f"输出目录不存在: {output_directory}")
                return None

            return output_directory

        except Exception as e:
            self.logger.error(f"获取输出目录失败: {str(e)}")
            return None

    def _delete_query_results_for_directory(self, directory):
        """删除目录下所有文件的查询结果"""
        deleted_count = 0
        try:
            # 递归遍历目录
            for root, dirs, files in os.walk(directory):
                # 查找所有 query_results_*.txt 文件
                for filename in files:
                    if filename.startswith('query_results_') and filename.endswith('.txt'):
                        file_path = os.path.join(root, filename)
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            self.logger.info(f"已删除: {file_path}")
                        except Exception as e:
                            self.logger.error(f"删除文件失败 {file_path}: {str(e)}")

        except Exception as e:
            self.logger.error(f"删除目录查询结果失败: {str(e)}")

        return deleted_count

    def _batch_query_asteroids_and_variables(self):
        """批量查询小行星和变星"""
        try:
            # 获取当前选中的节点
            selection = self.directory_tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请先选择一个目录或文件")
                return

            item = selection[0]
            values = self.directory_tree.item(item, "values")
            tags = self.directory_tree.item(item, "tags")

            if not values:
                messagebox.showwarning("警告", "请选择一个目录或文件")
                return

            # 判断是文件还是目录
            is_file = "fits_file" in tags

            if is_file:
                # 选中的是单个文件
                file_path = values[0]

                # 检查文件是否有diff结果
                if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                    self.logger.warning("该文件没有检测结果，跳过批量查询")
                    return

                # 检查high_score_count
                high_score_count = self._get_high_score_count_from_current_detection()
                if high_score_count >= 8:
                    self.logger.info(f"该文件的high_score_count为{high_score_count}，不符合批量查询条件（需要<8）")
                    return

                # 执行单文件批量查询
                self._execute_single_file_batch_query()

            else:
                # 选中的是目录
                directory = values[0]

                # 收集目录下所有需要处理的文件
                files_to_process = self._collect_files_for_batch_query(directory)

                if not files_to_process:
                    self.logger.info("没有找到需要查询的文件")
                    return

                # 执行批量查询
                self._execute_batch_query(files_to_process)

        except Exception as e:
            error_msg = f"批量查询失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("错误", error_msg)

    def _execute_single_file_batch_query(self):
        """对当前文件的所有检测目标执行批量查询"""
        try:
            if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                self.logger.warning("没有检测结果")
                return

            # 获取high_score_count，只查询高分目标
            high_score_count = self._get_high_score_count_from_current_detection()
            if high_score_count is None or high_score_count == 0:
                self.logger.info("没有高分检测目标")
                return

            # 只处理前 high_score_count 个检测目标
            total = min(high_score_count, len(self._all_cutout_sets))
            success_count = 0
            skip_count = 0

            # 创建进度窗口
            progress_window = tk.Toplevel(self.parent_frame)
            progress_window.title("批量查询进度")
            progress_window.geometry("500x150")

            # 进度标签
            progress_label = ttk.Label(progress_window, text="准备开始...")
            progress_label.pack(pady=10)

            # 详细信息
            detail_label = ttk.Label(progress_window, text="", wraplength=450)
            detail_label.pack(pady=5)

            # 进度条
            progress_bar = ttk.Progressbar(progress_window, length=400, mode='determinate')
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = total

            # 统计标签
            stats_label = ttk.Label(progress_window, text="")
            stats_label.pack(pady=5)

            def update_progress(current, status):
                progress_bar['value'] = current
                progress_label.config(text=f"处理进度: {current}/{total}")
                detail_label.config(text=f"状态: {status}")
                stats_label.config(text=f"成功: {success_count} | 跳过: {skip_count}")
                progress_window.update()

            try:
                for cutout_idx in range(total):
                    self._current_cutout_index = cutout_idx

                    # 检查是否已经查询过
                    skybot_queried, skybot_result = self._check_existing_query_results('skybot')
                    vsx_queried, vsx_result = self._check_existing_query_results('vsx')

                    self.logger.info(f"目标 {cutout_idx + 1}: skybot_queried={skybot_queried}, skybot_result={skybot_result}")
                    self.logger.info(f"目标 {cutout_idx + 1}: vsx_queried={vsx_queried}, vsx_result={vsx_result}")

                    # 如果都已查询过，跳过
                    if skybot_queried and vsx_queried:
                        skip_count += 1
                        update_progress(cutout_idx + 1, f"目标 {cutout_idx + 1}: 已全部查询过")
                        continue

                    # 查询小行星
                    if not skybot_queried:
                        update_progress(cutout_idx + 0.3, f"目标 {cutout_idx + 1}: 查询小行星...")
                        self._query_skybot()

                        # 检查小行星查询结果
                        skybot_queried, skybot_result = self._check_existing_query_results('skybot')
                        self.logger.info(f"目标 {cutout_idx + 1}: 小行星查询后 skybot_queried={skybot_queried}, skybot_result={skybot_result}")

                    # 判断是否需要查询变星
                    # 只有当小行星找到结果时才跳过变星查询
                    should_query_vsx = True
                    # 检查是否真的找到了小行星（排除"未找到"的情况）
                    if skybot_queried and skybot_result and "找到" in skybot_result and "未找到" not in skybot_result:
                        # 小行星有结果，跳过变星查询
                        should_query_vsx = False
                        success_count += 1
                        update_progress(cutout_idx + 1, f"目标 {cutout_idx + 1}: 找到小行星，跳过变星查询")
                        self.logger.info(f"目标 {cutout_idx + 1}: 找到小行星，跳过变星查询")

                    self.logger.info(f"目标 {cutout_idx + 1}: should_query_vsx={should_query_vsx}, vsx_queried={vsx_queried}")

                    # 查询变星（只有在小行星无有效结果时才查询）
                    if should_query_vsx and not vsx_queried:
                        self.logger.info(f"目标 {cutout_idx + 1}: 开始查询变星...")
                        update_progress(cutout_idx + 0.7, f"目标 {cutout_idx + 1}: 查询变星...")
                        self._query_vsx()
                        success_count += 1
                        update_progress(cutout_idx + 1, f"目标 {cutout_idx + 1}: 完成")
                    elif not should_query_vsx:
                        # 已经跳过变星查询
                        self.logger.info(f"目标 {cutout_idx + 1}: 跳过变星查询（小行星已找到）")
                        pass
                    else:
                        # 变星已查询过
                        self.logger.info(f"目标 {cutout_idx + 1}: 变星已查询过")
                        success_count += 1
                        update_progress(cutout_idx + 1, f"目标 {cutout_idx + 1}: 完成")

                # 完成
                progress_label.config(text="批量查询完成！")
                detail_label.config(text=f"总计: {total} 个检测目标")
                self.logger.info(f"批量查询完成！成功: {success_count}, 跳过: {skip_count}")

            except Exception as e:
                self.logger.error(f"批量查询过程出错: {str(e)}")
            finally:
                progress_window.destroy()

        except Exception as e:
            error_msg = f"单文件批量查询失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

    def _collect_files_for_batch_query(self, directory):
        """收集目录下所有需要批量查询的文件"""
        files_to_process = []

        try:
            # 递归遍历目录
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.lower().endswith(('.fits', '.fit', '.fts')):
                        file_path = os.path.join(root, filename)

                        # 检查文件的diff结果
                        detection_info = self._check_file_diff_result(file_path, root)

                        if detection_info and detection_info.get('has_result'):
                            high_score_count = detection_info.get('high_score_count', 0)

                            # 只处理 high_score_count < 8 的文件
                            if high_score_count < 8:
                                files_to_process.append({
                                    'file_path': file_path,
                                    'region_dir': root,
                                    'high_score_count': high_score_count,
                                    'detection_info': detection_info
                                })
                                self.logger.info(f"添加到批量查询列表: {filename} (high_score={high_score_count})")

            self.logger.info(f"共收集到 {len(files_to_process)} 个文件需要批量查询")

        except Exception as e:
            self.logger.error(f"收集文件失败: {str(e)}")

        return files_to_process

    def _execute_batch_query(self, files_to_process):
        """执行批量查询"""
        total = len(files_to_process)
        success_count = 0
        skip_count = 0
        error_count = 0

        # 创建进度窗口
        progress_window = tk.Toplevel(self.parent_frame)
        progress_window.title("批量查询进度")
        progress_window.geometry("500x200")

        # 进度标签
        progress_label = ttk.Label(progress_window, text="准备开始...")
        progress_label.pack(pady=10)

        # 详细信息
        detail_label = ttk.Label(progress_window, text="", wraplength=450)
        detail_label.pack(pady=5)

        # 进度条
        progress_bar = ttk.Progressbar(progress_window, length=400, mode='determinate')
        progress_bar.pack(pady=10)
        progress_bar['maximum'] = total

        # 统计标签
        stats_label = ttk.Label(progress_window, text="")
        stats_label.pack(pady=5)

        def update_progress(current, filename, status):
            progress_bar['value'] = current
            progress_label.config(text=f"处理进度: {current}/{total}")
            detail_label.config(text=f"当前文件: {filename}\n状态: {status}")
            stats_label.config(text=f"成功: {success_count} | 跳过: {skip_count} | 错误: {error_count}")
            progress_window.update()

        try:
            for idx, file_info in enumerate(files_to_process, 1):
                file_path = file_info['file_path']
                filename = os.path.basename(file_path)

                try:
                    # 加载文件的diff结果
                    update_progress(idx - 0.5, filename, "加载检测结果...")

                    if not self._load_diff_results_for_file(file_path, file_info['region_dir']):
                        skip_count += 1
                        update_progress(idx, filename, "跳过（无法加载检测结果）")
                        continue

                    # 检查是否有检测结果
                    if not hasattr(self, '_all_cutout_sets') or not self._all_cutout_sets:
                        skip_count += 1
                        update_progress(idx, filename, "跳过（无检测结果）")
                        continue

                    # 获取high_score_count，只查询高分目标
                    high_score_count = self._get_high_score_count_from_current_detection()
                    if high_score_count is None or high_score_count == 0:
                        skip_count += 1
                        update_progress(idx, filename, "跳过（无高分目标）")
                        continue

                    # 只遍历前 high_score_count 个检测目标
                    total_to_query = min(high_score_count, len(self._all_cutout_sets))
                    queried_count = 0
                    for cutout_idx in range(total_to_query):
                        self._current_cutout_index = cutout_idx

                        # 检查是否已经查询过
                        skybot_queried, skybot_result = self._check_existing_query_results('skybot')
                        vsx_queried, vsx_result = self._check_existing_query_results('vsx')

                        # 如果都已查询过，跳过
                        if skybot_queried and vsx_queried:
                            continue

                        # 查询小行星
                        if not skybot_queried:
                            update_progress(idx - 0.3, filename, f"查询小行星 ({cutout_idx + 1}/{total_to_query})...")
                            self._query_skybot()
                            queried_count += 1

                            # 检查小行星查询结果
                            skybot_queried, skybot_result = self._check_existing_query_results('skybot')

                        # 判断是否需要查询变星
                        # 只有当小行星找到结果时才跳过变星查询
                        should_query_vsx = True
                        # 检查是否真的找到了小行星（排除"未找到"的情况）
                        if skybot_queried and skybot_result and "找到" in skybot_result and "未找到" not in skybot_result:
                            # 小行星有结果，跳过变星查询
                            should_query_vsx = False

                        # 查询变星（只有在小行星无有效结果时才查询）
                        if should_query_vsx and not vsx_queried:
                            update_progress(idx - 0.1, filename, f"查询变星 ({cutout_idx + 1}/{total_to_query})...")
                            self._query_vsx()
                            queried_count += 1

                    if queried_count > 0:
                        success_count += 1
                        update_progress(idx, filename, f"完成（查询了 {queried_count} 个目标）")
                    else:
                        skip_count += 1
                        update_progress(idx, filename, "跳过（已全部查询过）")

                except Exception as e:
                    error_count += 1
                    error_msg = f"处理失败: {str(e)}"
                    self.logger.error(f"处理文件 {filename} 失败: {str(e)}")
                    update_progress(idx, filename, error_msg)

            # 完成
            progress_label.config(text="批量查询完成！")
            detail_label.config(text=f"总计: {total} 个文件")
            self.logger.info(f"批量查询完成！成功: {success_count}, 跳过: {skip_count}, 错误: {error_count}")

        except Exception as e:
            self.logger.error(f"批量查询过程出错: {str(e)}")
        finally:
            progress_window.destroy()

    def _load_diff_results_for_file(self, file_path, region_dir):
        """为指定文件加载diff结果"""
        try:
            # 获取配置的输出目录
            base_output_dir = None
            if self.get_diff_output_dir_callback:
                base_output_dir = self.get_diff_output_dir_callback()

            if not base_output_dir or not os.path.exists(base_output_dir):
                return False

            # 从region_dir提取相对路径部分
            download_dir = None
            if self.get_download_dir_callback:
                download_dir = self.get_download_dir_callback()

            if not download_dir:
                return False

            # 标准化路径
            normalized_region_dir = os.path.normpath(region_dir)
            normalized_download_dir = os.path.normpath(download_dir)

            # 获取相对路径
            try:
                relative_path = os.path.relpath(normalized_region_dir, normalized_download_dir)
            except ValueError:
                return False

            # 构建输出目录路径
            filename = os.path.basename(file_path)
            output_region_dir = os.path.join(base_output_dir, relative_path)
            file_basename = os.path.splitext(filename)[0]
            potential_output_dir = os.path.join(output_region_dir, file_basename)

            # 检查是否存在detection目录
            if not os.path.exists(potential_output_dir) or not os.path.isdir(potential_output_dir):
                return False

            # 查找detection_开头的目录
            detection_dir_path = None
            try:
                items = os.listdir(potential_output_dir)
                for item_name in items:
                    item_path = os.path.join(potential_output_dir, item_name)
                    if os.path.isdir(item_path) and item_name.startswith('detection_'):
                        detection_dir_path = item_path
                        break
            except Exception:
                return False

            if not detection_dir_path:
                return False

            # 加载cutouts（使用与_display_first_detection_cutouts相同的逻辑）
            cutouts_dir = Path(detection_dir_path) / "cutouts"
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
                cutout_set = {
                    'reference': str(ref),
                    'aligned': str(aligned),
                    'detection': str(det),
                    'skybot_results': None,
                    'vsx_results': None,
                    'skybot_queried': False,
                    'vsx_queried': False
                }
                self._all_cutout_sets.append(cutout_set)

            self._current_cutout_index = 0
            self._total_cutouts = len(self._all_cutout_sets)

            # 加载每个cutout的查询结果
            for idx, cutout_set in enumerate(self._all_cutout_sets):
                self._load_query_results_from_file(cutout_set, idx)

            self.logger.info(f"成功加载 {self._total_cutouts} 个检测目标")
            return True

        except Exception as e:
            self.logger.error(f"加载文件diff结果失败: {str(e)}")
            return False


