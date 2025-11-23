#!/usr/bin/env python3
"""
FITS文件网页下载器GUI
用于扫描网页、下载FITS文件并显示图像
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import logging
from datetime import datetime
from pathlib import Path

import time
import json
from concurrent.futures import ThreadPoolExecutor
import shutil



# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_scanner import WebFitsScanner, DirectoryScanner
from fits_viewer import FitsImageViewer
from data_collect.data_02_download import FitsDownloader
from config_manager import ConfigManager
from url_builder import URLBuilderFrame
from batch_status_widget import BatchStatusWidget

# 尝试导入ASTAP处理器
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from astap_processor import ASTAPProcessor
except ImportError:
    ASTAPProcessor = None


class FitsWebDownloaderGUI:
    """FITS文件网页下载器主界面"""

    def __init__(self, auto_date=None, auto_telescope=None, auto_region=None):
        """
        初始化GUI

        Args:
            auto_date: 自动设置的日期（格式：YYYYMMDD）
            auto_telescope: 自动设置的望远镜系统名
            auto_region: 自动设置的天区名
        """
        self.root = tk.Tk()
        self.root.title("FITS文件网页下载器")
        self.root.geometry("1200x900")

        # 设置日志
        self._setup_logging()

        # 初始化配置管理器
        self.config_manager = ConfigManager()

        # 初始化组件
        self.scanner = WebFitsScanner()
        self.directory_scanner = DirectoryScanner()
        self.downloader = None

        # 数据存储
        self.fits_files_list = []  # [(filename, url, size)]
        self.download_directory = ""
        self.region_buttons = []  # 存储天区按钮引用
        self.region_button_states = {}  # 存储天区按钮的选中状态

        # 批量处理控制状态
        self.batch_paused = False  # 暂停标志
        self.batch_stopped = False  # 停止标志
        self.batch_pause_event = threading.Event()  # 暂停事件
        self.batch_pause_event.set()  # 初始为非暂停状态

        # 自动链：批量→查询→导出 控制开关
        self._auto_chain_followups = False
        # 自动链附加步骤：是否在自动链末尾上传到OSS（默认不启用）
        self.auto_chain_oss_upload_var = tk.BooleanVar(value=False)
        # 自动链：是否使用本地离线查询（初始化为配置中的值）
        try:
            _local_settings = self.config_manager.get_local_catalog_settings()
            _auto_local_default = bool(_local_settings.get("auto_chain_use_local_query", False))
        except Exception:
            _auto_local_default = False
        self.auto_chain_use_local_query_var = tk.BooleanVar(value=_auto_local_default)

        # 手动查询按钮：是否使用本地离线查询（初始化为配置中的值）
        try:
            _local_settings = self.config_manager.get_local_catalog_settings()
            _btn_local_default = bool(_local_settings.get("buttons_use_local_query", False))
        except Exception:
            _btn_local_default = False
        self.buttons_use_local_query_var = tk.BooleanVar(value=_btn_local_default)
        # 小行星查询方式（初始化为配置中的值）
        try:
            _local_settings = self.config_manager.get_local_catalog_settings()
            _method_default = str(_local_settings.get("asteroid_query_method", "auto"))
        except Exception:
            _method_default = "auto"
        self.asteroid_query_method_var = tk.StringVar(value=_method_default)
        # pympc 是否使用观测站代码（初始化为配置中的值，默认 False）
        try:
            _local_settings = self.config_manager.get_local_catalog_settings()
            _pympc_use_obs_default = bool(_local_settings.get("pympc_use_observatory", False))
        except Exception:
            _pympc_use_obs_default = False
        self.pympc_use_observatory_var = tk.BooleanVar(value=_pympc_use_obs_default)





        # 保存自动执行参数
        self.auto_date = auto_date
        self.auto_telescope = auto_telescope
        self.auto_region = auto_region

        # 创建界面
        self._create_widgets()

        # 加载配置
        self._load_config()

        # 如果有自动执行参数，设置UI并执行相应操作
        if self.auto_date:
            self.root.after(1000, self._apply_auto_settings)

    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建笔记本控件（标签页）
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 创建扫描和下载标签页
        self.scan_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.scan_frame, text="扫描和下载")

        # 创建批量处理状态标签页
        self.batch_status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.batch_status_frame, text="批量处理状态")

        # 创建图像查看标签页
        self.viewer_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.viewer_frame, text="图像查看")

        # 创建高级设置标签页
        self.advanced_settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_settings_frame, text="高级设置")

        # 创建天区收集（GY1）标签页
        self.region_collect_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.region_collect_frame, text="天区收集")

        # 创建日志标签页
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="日志")

        # 初始化各个标签页
        self._create_scan_widgets()
        self._create_batch_status_widgets()
        self._create_viewer_widgets()
        self._create_advanced_settings_widgets()
        self._create_region_collect_widgets()
        self._create_log_widgets()

    def _create_scan_widgets(self):
        """创建扫描和下载界面"""
        # URL构建器区域
        self.url_builder = URLBuilderFrame(self.scan_frame, self.config_manager, self._on_url_change, self._start_scan, self._batch_process, self._open_batch_output_directory, self._full_day_batch_process, self._full_day_all_systems_batch_process, self._pause_batch_process, self._stop_batch_process)

        # 保存批量处理的输出根目录
        self.last_batch_output_root = None

        # 扫描状态标签
        scan_status_frame = ttk.Frame(self.scan_frame)
        scan_status_frame.pack(fill=tk.X, pady=(0, 10))

        self.scan_status_label = ttk.Label(scan_status_frame, text="就绪")
        self.scan_status_label.pack(side=tk.LEFT)

        # 文件列表区域
        list_frame = ttk.LabelFrame(self.scan_frame, text="FITS文件列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建Treeview显示文件列表
        columns = ("filename", "size", "url")
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        # 设置列标题
        self.file_tree.heading("#0", text="选择")
        self.file_tree.heading("filename", text="文件名")
        self.file_tree.heading("size", text="大小")
        self.file_tree.heading("url", text="URL")

        # 设置列宽
        self.file_tree.column("#0", width=60)
        self.file_tree.column("filename", width=300)
        self.file_tree.column("size", width=100)
        self.file_tree.column("url", width=400)

        # 添加滚动条
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=tree_scroll.set)

        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定点击事件
        self.file_tree.bind('<Button-1>', self._on_tree_click)

        # 选择控制按钮
        select_frame = ttk.Frame(list_frame)
        select_frame.pack(fill=tk.X, pady=(5, 0))

        # 第一行：基本选择按钮
        basic_select_frame = ttk.Frame(select_frame)
        basic_select_frame.pack(fill=tk.X, pady=(0, 2))

        ttk.Button(basic_select_frame, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(basic_select_frame, text="全不选", command=self._deselect_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(basic_select_frame, text="反选", command=self._invert_selection).pack(side=tk.LEFT, padx=(0, 10))

        # 天区索引选择按钮 - 3x3网格布局
        region_select_frame = ttk.Frame(select_frame)
        region_select_frame.pack(fill=tk.X)

        # 创建3行3列的天区按钮（默认禁用）
        self.region_buttons = []
        for row in range(3):
            row_frame = ttk.Frame(region_select_frame)
            row_frame.pack(fill=tk.X, pady=(2, 0))

            for col in range(3):
                region_index = row * 3 + col + 1  # 1-9
                region_name = f"天区-{region_index}"
                btn = ttk.Button(row_frame, text=region_name, width=12, state="disabled",
                               command=lambda idx=region_index: self._select_by_region(idx))
                btn.pack(side=tk.LEFT, padx=(0, 2))
                self.region_buttons.append(btn)

        # 下载控制区域
        download_frame = ttk.LabelFrame(self.scan_frame, text="下载设置", padding=10)
        download_frame.pack(fill=tk.X)

        # 下载目录选择
        dir_frame = ttk.Frame(download_frame)
        dir_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(dir_frame, text="下载根目录:").pack(side=tk.LEFT)
        self.download_dir_var = tk.StringVar()
        self.download_dir_entry = ttk.Entry(dir_frame, textvariable=self.download_dir_var, width=50)
        self.download_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        ttk.Button(dir_frame, text="选择根目录", command=self._select_download_dir).pack(side=tk.RIGHT)

        # 模板文件目录选择
        template_frame = ttk.Frame(download_frame)
        template_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Label(template_frame, text="模板文件目录:").pack(side=tk.LEFT)
        self.template_dir_var = tk.StringVar()
        self.template_dir_entry = ttk.Entry(template_frame, textvariable=self.template_dir_var, width=50)
        self.template_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        ttk.Button(template_frame, text="选择模板目录", command=self._select_template_dir).pack(side=tk.RIGHT)

        # diff输出目录选择
        diff_output_frame = ttk.Frame(download_frame)
        diff_output_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Label(diff_output_frame, text="Diff输出根目录:").pack(side=tk.LEFT)
        self.diff_output_dir_var = tk.StringVar()
        self.diff_output_dir_entry = ttk.Entry(diff_output_frame, textvariable=self.diff_output_dir_var, width=50)
        self.diff_output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        ttk.Button(diff_output_frame, text="选择输出目录", command=self._select_diff_output_dir).pack(side=tk.RIGHT)

        # detected保存目录选择
        detected_frame = ttk.Frame(download_frame)
        detected_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Label(detected_frame, text="Detected保存目录:").pack(side=tk.LEFT)
        self.detected_dir_var = tk.StringVar()
        self.detected_dir_entry = ttk.Entry(detected_frame, textvariable=self.detected_dir_var, width=50)
        self.detected_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        ttk.Button(detected_frame, text="选择保存目录", command=self._select_detected_dir).pack(side=tk.RIGHT)

        # 未查询导出目录选择（也用于OSS上传）
        unqueried_export_frame = ttk.Frame(download_frame)
        unqueried_export_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Label(unqueried_export_frame, text="未查询导出目录:").pack(side=tk.LEFT)
        self.unqueried_export_dir_var = tk.StringVar()
        self.unqueried_export_dir_entry = ttk.Entry(unqueried_export_frame, textvariable=self.unqueried_export_dir_var, width=50)
        self.unqueried_export_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        ttk.Button(unqueried_export_frame, text="选择导出目录", command=self._select_unqueried_export_dir).pack(side=tk.RIGHT)

        # 下载参数
        params_frame = ttk.Frame(download_frame)
        params_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(params_frame, text="并发数:").pack(side=tk.LEFT)
        self.max_workers_var = tk.IntVar(value=1)
        self.max_workers_spinbox = ttk.Spinbox(params_frame, from_=1, to=1, textvariable=self.max_workers_var, width=5, state="disabled")
        self.max_workers_spinbox.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(params_frame, text="(已锁定)", foreground="gray").pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(params_frame, text="重试次数:").pack(side=tk.LEFT)
        self.retry_times_var = tk.IntVar(value=3)
        ttk.Spinbox(params_frame, from_=1, to=10, textvariable=self.retry_times_var, width=5).pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(params_frame, text="超时(秒):").pack(side=tk.LEFT)
        self.timeout_var = tk.IntVar(value=30)
        ttk.Spinbox(params_frame, from_=10, to=120, textvariable=self.timeout_var, width=5).pack(side=tk.LEFT, padx=(5, 15))

        # ASTAP处理选项
        self.enable_astap_var = tk.BooleanVar(value=False)
        astap_checkbox = ttk.Checkbutton(params_frame, text="启用ASTAP处理", variable=self.enable_astap_var)
        astap_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        # 如果ASTAP处理器不可用，禁用选项
        if not ASTAPProcessor:
            astap_checkbox.config(state="disabled")
            ttk.Label(params_frame, text="(ASTAP处理器不可用)", foreground="gray").pack(side=tk.LEFT, padx=(5, 0))

        # 下载按钮和进度条
        control_frame = ttk.Frame(download_frame)
        control_frame.pack(fill=tk.X)

        self.download_button = ttk.Button(control_frame, text="开始下载", command=self._start_download)
        self.download_button.pack(side=tk.LEFT)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, length=300)
        self.progress_bar.pack(side=tk.LEFT, padx=(10, 10), fill=tk.X, expand=True)

        self.status_label = ttk.Label(control_frame, text="就绪")
        self.status_label.pack(side=tk.RIGHT)

    def _create_viewer_widgets(self):
        """创建图像查看界面"""
        # 文件选择区域
        file_frame = ttk.LabelFrame(self.viewer_frame, text="文件选择", padding=6)
        file_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Button(file_frame, text="从下载目录选择", command=self._select_from_download_dir).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="选择其他FITS文件", command=self._select_fits_file).pack(side=tk.LEFT, padx=(8, 0))

        # 创建FITS查看器，传递配置管理器和回调函数
        # 将file_frame传递给FitsImageViewer，以便在其中添加按钮
        self.fits_viewer = FitsImageViewer(
            self.viewer_frame,
            config_manager=self.config_manager,
            get_download_dir_callback=self._get_download_dir,
            get_template_dir_callback=self._get_template_dir,
            get_diff_output_dir_callback=self._get_diff_output_dir,
            get_url_selections_callback=self._get_url_selections,
            log_callback=self.get_error_logger_callback(),  # 传递日志回调函数
            file_selection_frame=file_frame,  # 传递文件选择框架
            get_unqueried_export_dir_callback=self._get_unqueried_export_dir  # 传递未查询导出目录回调函数（也用于OSS上传）
        )

        # 设置diff_orb的GUI回调
        if self.fits_viewer.diff_orb:
            self.fits_viewer.diff_orb.gui_callback = self.get_error_logger_callback()

    def _create_advanced_settings_widgets(self):
        """创建高级设置界面"""
        # 创建主容器（带滚动条）
        outer_frame = ttk.Frame(self.advanced_settings_frame)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Canvas + Scrollbar 组成可滚动区域
        canvas = tk.Canvas(outer_frame, borderwidth=0, highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=v_scrollbar.set)

        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 在 Canvas 中创建真正的内容容器
        inner_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        # 根据内容自动调整滚动区域
        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner_frame.bind("<Configure>", _on_inner_configure)

        # 将内部容器作为 main_container 使用
        main_container = inner_frame

        # 标题
        title_label = ttk.Label(main_container, text="高级设置", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # 说明文本
        info_text = ("这里包含了FITS图像处理的高级参数设置。\n"
                    "这些设置会影响图像对齐、降噪、检测等处理过程。\n"
                    "修改后会自动保存到配置文件中。")
        info_label = ttk.Label(main_container, text=info_text, foreground="gray")
        info_label.pack(pady=(0, 20))

        # 创建设置区域
        settings_container = ttk.Frame(main_container)
        settings_container.pack(fill=tk.BOTH, expand=True)
        # AI训练导出根目录变量
        if not hasattr(self, 'ai_export_root_var'):
            self.ai_export_root_var = tk.StringVar()



        # 第一行：降噪方式和去除亮线
        row1_frame = ttk.LabelFrame(settings_container, text="降噪设置", padding=10)
        row1_frame.pack(fill=tk.X, pady=(0, 10))

        # 降噪方式
        noise_label = ttk.Label(row1_frame, text="降噪方式:")
        noise_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        # 获取fits_viewer的降噪变量（如果已创建）
        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            outlier_check = ttk.Checkbutton(row1_frame, text="Outlier",
                                          variable=self.fits_viewer.outlier_var)
            outlier_check.grid(row=0, column=1, sticky=tk.W, padx=5)

            hot_cold_check = ttk.Checkbutton(row1_frame, text="Hot/Cold",
                                           variable=self.fits_viewer.hot_cold_var)
            hot_cold_check.grid(row=0, column=2, sticky=tk.W, padx=5)

            adaptive_median_check = ttk.Checkbutton(row1_frame, text="Adaptive Median",
                                                  variable=self.fits_viewer.adaptive_median_var)
            adaptive_median_check.grid(row=0, column=3, sticky=tk.W, padx=5)

            # 去除亮线
            remove_lines_check = ttk.Checkbutton(row1_frame, text="去除亮线",
                                               variable=self.fits_viewer.remove_lines_var)
            remove_lines_check.grid(row=0, column=4, sticky=tk.W, padx=(20, 5))

        # 第二行：对齐方式
        row2_frame = ttk.LabelFrame(settings_container, text="对齐设置", padding=10)
        row2_frame.pack(fill=tk.X, pady=(0, 10))

        alignment_label = ttk.Label(row2_frame, text="对齐方式:")
        alignment_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            alignment_methods = [
                ("Rigid", "rigid"),
                ("WCS", "wcs"),
                ("Astropy", "astropy_reproject"),
                ("SWarp", "swarp")
            ]

            for i, (text, value) in enumerate(alignment_methods):
                rb = ttk.Radiobutton(row2_frame, text=text,
                                   variable=self.fits_viewer.alignment_var, value=value)
                rb.grid(row=0, column=i+1, sticky=tk.W, padx=5)

        # 第三行：检测参数
        # 显示/查询设置
        display_row = ttk.LabelFrame(settings_container, text="显示/查询设置", padding=10)
        display_row.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            # 拉伸方法
            ttk.Label(display_row, text="拉伸方法:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            rb_peak = ttk.Radiobutton(display_row, text="峰值", variable=self.fits_viewer.stretch_method_var, value="peak")
            rb_peak.grid(row=0, column=1, sticky=tk.W, padx=(5, 5))
            rb_pct = ttk.Radiobutton(display_row, text="百分位数", variable=self.fits_viewer.stretch_method_var, value="percentile")
            rb_pct.grid(row=0, column=2, sticky=tk.W, padx=(5, 15))
            ttk.Label(display_row, text="百分位:").grid(row=0, column=3, sticky=tk.W, padx=(0, 5))
            pct_entry = ttk.Entry(display_row, textvariable=self.fits_viewer.percentile_var, width=6)
            pct_entry.grid(row=0, column=4, sticky=tk.W, padx=(0, 2))
            ttk.Label(display_row, text="%").grid(row=0, column=5, sticky=tk.W, padx=(0, 10))

            # 搜索半径
            ttk.Label(display_row, text="搜索半径(°):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
            sr_entry = ttk.Entry(display_row, textvariable=self.fits_viewer.search_radius_var, width=8)
            sr_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 5), pady=(10, 0))
            ttk.Button(display_row, text="保存查询设置", command=self.fits_viewer._save_query_settings).grid(row=1, column=2, sticky=tk.W, padx=(5, 0), pady=(10, 0))

            # 批量查询间隔（秒）
            ttk.Label(display_row, text="批量查询间隔(s):").grid(row=1, column=3, sticky=tk.W, padx=(20, 5), pady=(10, 0))
            interval_entry = ttk.Entry(display_row, textvariable=self.fits_viewer.batch_query_interval_var, width=8)
            interval_entry.grid(row=1, column=4, sticky=tk.W, padx=(0, 5), pady=(10, 0))

        row3_frame = ttk.LabelFrame(settings_container, text="检测参数", padding=10)
        row3_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            # 锯齿比率
            jaggedness_label = ttk.Label(row3_frame, text="锯齿比率:")
            jaggedness_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

            jaggedness_entry = ttk.Entry(row3_frame, textvariable=self.fits_viewer.jaggedness_ratio_var, width=8)
            jaggedness_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

            # 检测方法
            detection_label = ttk.Label(row3_frame, text="检测方法:")
            detection_label.grid(row=0, column=2, sticky=tk.W, padx=(20, 5))

            detection_contour_radio = ttk.Radiobutton(row3_frame, text="轮廓",
                                                    variable=self.fits_viewer.detection_method_var, value="contour")
            detection_contour_radio.grid(row=0, column=3, sticky=tk.W, padx=5)

            detection_blob_radio = ttk.Radiobutton(row3_frame, text="SimpleBlobDetector",
                                                 variable=self.fits_viewer.detection_method_var, value="simple_blob")
            detection_blob_radio.grid(row=0, column=4, sticky=tk.W, padx=5)

        # 第四行：阈值和排序
        row4_frame = ttk.LabelFrame(settings_container, text="筛选和排序", padding=10)
        row4_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            # 综合得分阈值
            score_label = ttk.Label(row4_frame, text="综合得分 >")
            score_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

            score_entry = ttk.Entry(row4_frame, textvariable=self.fits_viewer.score_threshold_var, width=8)
            score_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

            # Aligned SNR阈值
            snr_label = ttk.Label(row4_frame, text="Aligned SNR >")
            snr_label.grid(row=0, column=2, sticky=tk.W, padx=(20, 5))

            snr_entry = ttk.Entry(row4_frame, textvariable=self.fits_viewer.aligned_snr_threshold_var, width=8)
            snr_entry.grid(row=0, column=3, sticky=tk.W, padx=5)

            # 排序方式
            sort_label = ttk.Label(row4_frame, text="排序:")
            sort_label.grid(row=0, column=4, sticky=tk.W, padx=(20, 5))

            sort_combo = ttk.Combobox(row4_frame, textvariable=self.fits_viewer.sort_by_var,
                                     values=["quality_score", "aligned_snr", "snr"],
                                     state="readonly", width=15)
            sort_combo.grid(row=0, column=5, sticky=tk.W, padx=5)

            # 直线检测过滤开关
            line_detection_check = ttk.Checkbutton(row4_frame, text="批量导出时过滤过中心直线",
                                                  variable=self.fits_viewer.enable_line_detection_filter_var)
            line_detection_check.grid(row=0, column=6, sticky=tk.W, padx=(20, 5))

        # 第五行：GPS和MPC设置
        # 第六行：直线检测设置（灵敏度与中心距离）
        row6_frame = ttk.LabelFrame(settings_container, text="直线检测设置", padding=10)
        row6_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            ttk.Label(row6_frame, text="灵敏度(1-100):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            e_sens = ttk.Entry(row6_frame, textvariable=self.fits_viewer.line_sensitivity_var, width=8)
            e_sens.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

            ttk.Label(row6_frame, text="过中心距离(px):").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
            e_center = ttk.Entry(row6_frame, textvariable=self.fits_viewer.line_center_distance_var, width=8)
            e_center.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))

        # 第七行：对齐性能设置（速度/稳健性权衡）
        row7_frame = ttk.LabelFrame(settings_container, text="对齐性能设置", padding=10)
        row7_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            # 第一排
            ttk.Label(row7_frame, text="星点上限:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            e_starmax = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_star_max_points_var, width=8)
            e_starmax.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

            ttk.Label(row7_frame, text="最小间距(px):").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
            e_starmind = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_star_min_distance_var, width=8)
            e_starmind.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))

            ttk.Label(row7_frame, text="亮星点池(三角):").grid(row=0, column=4, sticky=tk.W, padx=(10, 5))
            e_tripoints = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_tri_points_var, width=8)
            e_tripoints.grid(row=0, column=5, sticky=tk.W, padx=(0, 10))

            # 第二排
            ttk.Label(row7_frame, text="内点阈值(px):").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(8, 0))
            e_trithr = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_tri_inlier_thr_var, width=8)
            e_trithr.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=(8, 0))

            ttk.Label(row7_frame, text="形状量化:").grid(row=1, column=2, sticky=tk.W, padx=(10, 5), pady=(8, 0))
            e_tribin = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_tri_bin_scale_var, width=8)
            e_tribin.grid(row=1, column=3, sticky=tk.W, padx=(0, 10), pady=(8, 0))

            ttk.Label(row7_frame, text="可视化Top-K:").grid(row=1, column=4, sticky=tk.W, padx=(10, 5), pady=(8, 0))
            e_tritopk = ttk.Entry(row7_frame, textvariable=self.fits_viewer.align_tri_topk_var, width=8)
            e_tritopk.grid(row=1, column=5, sticky=tk.W, padx=(0, 10), pady=(8, 0))

        row5_frame = ttk.LabelFrame(settings_container, text="观测站设置", padding=10)
        row5_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            # GPS纬度
            lat_label = ttk.Label(row5_frame, text="GPS纬度:")
            lat_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

            lat_entry = ttk.Entry(row5_frame, textvariable=self.fits_viewer.gps_lat_var, width=10)
            lat_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

            lat_unit = ttk.Label(row5_frame, text="°N")
            lat_unit.grid(row=0, column=2, sticky=tk.W, padx=(0, 10))

            # GPS经度
            lon_label = ttk.Label(row5_frame, text="经度:")
            lon_label.grid(row=0, column=3, sticky=tk.W, padx=(10, 5))

            lon_entry = ttk.Entry(row5_frame, textvariable=self.fits_viewer.gps_lon_var, width=10)
            lon_entry.grid(row=0, column=4, sticky=tk.W, padx=5)

            lon_unit = ttk.Label(row5_frame, text="°E")
            lon_unit.grid(row=0, column=5, sticky=tk.W, padx=(0, 10))

            # 时区显示
            tz_label = ttk.Label(row5_frame, text="时区:")
            tz_label.grid(row=0, column=6, sticky=tk.W, padx=(10, 5))

            # 创建时区显示标签的引用
            self.advanced_timezone_label = ttk.Label(row5_frame, text="UTC+6", foreground="blue")
            self.advanced_timezone_label.grid(row=0, column=7, sticky=tk.W, padx=5)

            # 保存GPS按钮
            save_gps_btn = ttk.Button(row5_frame, text="保存GPS",
                                     command=self.fits_viewer._save_gps_settings)
            save_gps_btn.grid(row=0, column=8, sticky=tk.W, padx=(10, 5))

            # MPC代码
            mpc_label = ttk.Label(row5_frame, text="MPC代码:")
            mpc_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))

            mpc_entry = ttk.Entry(row5_frame, textvariable=self.fits_viewer.mpc_code_var, width=10)
            mpc_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(10, 0))

            # 保存MPC按钮
            save_mpc_btn = ttk.Button(row5_frame, text="保存MPC",
                                     command=self.fits_viewer._save_mpc_settings)
            save_mpc_btn.grid(row=1, column=2, sticky=tk.W, padx=(10, 5), pady=(10, 0), columnspan=2)
        # 第六行：自动链设置
        auto_chain_frame = ttk.LabelFrame(settings_container, text="自动链设置", padding=10)
        auto_chain_frame.pack(fill=tk.X, pady=(0, 10))

        # 自动链结束后是否执行OSS上传（默认不启用）
        auto_oss_check = ttk.Checkbutton(
            auto_chain_frame,
            text="自动链结束后执行OSS上传",
            variable=self.auto_chain_oss_upload_var,
            command=self._on_toggle_auto_chain_oss_upload
        )
        auto_oss_check.grid(row=0, column=0, sticky=tk.W)

        # 手动查询按钮：是否使用本地离线查询
        btn_local_chk = ttk.Checkbutton(
            auto_chain_frame,
            text="手动查询按钮使用本地查询(离线)",
            variable=self.buttons_use_local_query_var,
            command=self._on_toggle_buttons_use_local_query
        )
        btn_local_chk.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))

        # 自动链：是否使用本地离线查询
        auto_local_chk = ttk.Checkbutton(
            auto_chain_frame,
            text="自动链使用本地查询(离线)",
            variable=self.auto_chain_use_local_query_var,
            command=self._on_toggle_auto_chain_use_local_query
        )
        auto_local_chk.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # 小行星查询方式设置
        asteroid_method_frame = ttk.LabelFrame(settings_container, text="小行星查询方式", padding=10)
        asteroid_method_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(asteroid_method_frame, text="选择小行星查询后端:").grid(row=0, column=0, sticky=tk.W)

        ttk.Radiobutton(
            asteroid_method_frame,
            text="自动(推荐)",
            value="auto",
            variable=self.asteroid_query_method_var,
            command=self._on_change_asteroid_query_method,
        ).grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Radiobutton(
            asteroid_method_frame,
            text="Skybot(在线)",
            value="skybot",
            variable=self.asteroid_query_method_var,
            command=self._on_change_asteroid_query_method,
        ).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))

        ttk.Radiobutton(
            asteroid_method_frame,
            text="本地MPCORB(离线)",
            value="local",
            variable=self.asteroid_query_method_var,
            command=self._on_change_asteroid_query_method,
        ).grid(row=2, column=0, sticky=tk.W, pady=(5, 0))

        ttk.Radiobutton(
            asteroid_method_frame,
            text="pympc(轨道库)",
            value="pympc",
            variable=self.asteroid_query_method_var,
            command=self._on_change_asteroid_query_method,
        ).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))

        # pympc 观测站代码使用开关（仅在选择 pympc 时生效）
        ttk.Checkbutton(
            asteroid_method_frame,
            text="pympc 使用观测站代码(N87)",
            variable=self.pympc_use_observatory_var,
            command=self._on_toggle_pympc_use_observatory,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))


        # 本地查询资源设置
        local_catalog_frame = ttk.LabelFrame(settings_container, text="本地查询资源", padding=10)
        local_catalog_frame.pack(fill=tk.X, pady=(0, 10))

        # 更新/选择 本地小行星库
        ttk.Button(local_catalog_frame, text="选择/更新本地小行星库", command=self._update_local_asteroid_catalog).grid(row=0, column=0, sticky=tk.W)
        self.local_asteroid_status_label = ttk.Label(local_catalog_frame, text="小行星库: 未设置")
        self.local_asteroid_status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        # 更新/选择 本地变星库
        ttk.Button(local_catalog_frame, text="选择/更新本地变星库", command=self._update_local_vsx_catalog).grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.local_vsx_status_label = ttk.Label(local_catalog_frame, text="变星库: 未设置")
        self.local_vsx_status_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        # 小行星H上限设置
        try:
            local_settings = self.config_manager.get_local_catalog_settings()
            current_h = str(local_settings.get("mpc_h_limit", 20))
        except Exception:
            current_h = "20"
        self.mpc_h_limit_var = tk.StringVar(value=current_h)
        ttk.Label(local_catalog_frame, text="小行星H上限:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        h_entry = ttk.Entry(local_catalog_frame, textvariable=self.mpc_h_limit_var, width=8)
        h_entry.grid(row=2, column=1, sticky=tk.W, padx=(5, 5), pady=(5, 0))
        ttk.Button(local_catalog_frame, text="保存H上限", command=self._save_mpc_h_limit).grid(row=2, column=2, sticky=tk.W, pady=(5, 0))
        self.mpc_h_status_label = ttk.Label(local_catalog_frame, text=f"当前H上限: {current_h}")
        self.mpc_h_status_label.grid(row=2, column=3, sticky=tk.W, padx=(10, 0), pady=(5, 0))

        # AI训练数据导出设置
        ai_export_frame = ttk.LabelFrame(settings_container, text="AI训练数据导出", padding=10)
        ai_export_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ai_export_frame, text="AI训练导出根目录:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ai_export_entry = ttk.Entry(ai_export_frame, textvariable=self.ai_export_root_var, width=50)
        ai_export_entry.grid(row=0, column=1, sticky=tk.W, padx=(5, 5))

        ttk.Button(ai_export_frame, text="选择目录", command=self._select_ai_training_export_root).grid(
            row=0, column=2, sticky=tk.W, padx=(5, 0)
        )

        ttk.Label(
            ai_export_frame,
            text="说明：用于导出当前选择目录下所有标记为 GOOD/BAD 的检测cutout，用于AI训练。",
            foreground="gray"
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # AI GOOD/BAD 自动标记设置
        ai_mark_frame = ttk.LabelFrame(settings_container, text="AI自动标记(GOOD/BAD)", padding=10)
        ai_mark_frame.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, 'fits_viewer') and self.fits_viewer:
            ttk.Label(ai_mark_frame, text="置信度阈值:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            ai_thr_entry = ttk.Entry(ai_mark_frame, textvariable=self.fits_viewer.ai_confidence_threshold_var, width=8)
            ai_thr_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
            ttk.Label(
                ai_mark_frame,
                text="取值范围 0~1，默认 0.7。仅当AI预测置信度 ≥ 该值时才自动标记为 GOOD/BAD。",
                foreground="gray",
            ).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))



        # 星历文件选择
        ttk.Button(local_catalog_frame, text="选择星历文件(.bsp)", command=self._update_ephemeris_file).grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        self.ephemeris_status_label = ttk.Label(local_catalog_frame, text="星历: 未设置")
        self.ephemeris_status_label.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))

        # pympc 轨道目录更新
        ttk.Button(local_catalog_frame, text="更新pympc轨道目录", command=self._update_pympc_catalogue).grid(
            row=4, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.pympc_status_label = ttk.Label(local_catalog_frame, text="pympc目录: 未下载")
        self.pympc_status_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))



        # 初始化状态显示
        try:
            self._refresh_local_catalog_status_labels()
        except Exception:
            pass

        # 底部说明
        bottom_info = ttk.Label(main_container,
                               text="提示：所有设置修改会自动保存，并在下次启动时生效。",
                               foreground="blue", font=("Arial", 9))
        bottom_info.pack(side=tk.BOTTOM, pady=(20, 0))

    def _create_log_widgets(self):
        """创建日志界面"""
        # 日志显示区域
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=30, width=100)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 配置日志文本标签样式（用于彩色显示）
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("DEBUG", foreground="gray")

        # 日志控制按钮
        log_control_frame = ttk.Frame(self.log_frame)
        log_control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(log_control_frame, text="清除日志", command=self._clear_log).pack(side=tk.LEFT)
        ttk.Button(log_control_frame, text="保存日志", command=self._save_log).pack(side=tk.LEFT, padx=(10, 0))

    def _create_region_collect_widgets(self):
        """创建“天区收集（仅GY1）”界面：按日期范围收集GY1天区列表
        规则：默认优先从本地缓存加载；本地没有才去扫描远端。
        """
        from calendar_widget import CalendarDialog

        container = ttk.Frame(self.region_collect_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 日期选择区域
        date_frame = ttk.LabelFrame(container, text="日期范围（YYYYMMDD）")
        date_frame.pack(fill=tk.X, padx=5, pady=5)

        today = datetime.today().strftime("%Y%m%d")
        self.region_collect_start_var = tk.StringVar(value=today)
        self.region_collect_end_var = tk.StringVar(value=today)

        ttk.Label(date_frame, text="起始日期:").grid(row=0, column=0, sticky=tk.W, padx=(10, 5), pady=8)
        start_entry = ttk.Entry(date_frame, textvariable=self.region_collect_start_var, width=12)
        start_entry.grid(row=0, column=1, sticky=tk.W)
        ttk.Button(date_frame, text="选择", command=lambda: self._open_calendar(self.region_collect_start_var, "选择起始日期")).grid(row=0, column=2, padx=(6, 12))

        ttk.Label(date_frame, text="终止日期:").grid(row=0, column=3, sticky=tk.W, padx=(10, 5))
        end_entry = ttk.Entry(date_frame, textvariable=self.region_collect_end_var, width=12)
        end_entry.grid(row=0, column=4, sticky=tk.W)
        ttk.Button(date_frame, text="选择", command=lambda: self._open_calendar(self.region_collect_end_var, "选择终止日期")).grid(row=0, column=5, padx=(6, 12))

        # 天区索引收集按钮
        action_frame = ttk.Frame(container)
        action_frame.pack(fill=tk.X, padx=5, pady=(5, 10))
        ttk.Button(action_frame, text="收集GY1天区信息", command=self._collect_regions_for_range).pack(side=tk.LEFT)
        self.region_collect_status = ttk.Label(action_frame, text="就绪")
        self.region_collect_status.pack(side=tk.LEFT, padx=(12, 0))

        # 说明
        tip = "说明：仅针对 GY1。优先从本地缓存加载，当某天无缓存时才扫描远端。缓存文件：gui/gy1_region_index.json"
        ttk.Label(container, text=tip, foreground="blue").pack(fill=tk.X, padx=5)

        # 问题模板自动更新区域
        update_frame = ttk.LabelFrame(container, text="问题模板自动更新（fits_check_report.txt）")
        update_frame.pack(fill=tk.X, padx=5, pady=(10, 5))

        # 前N个问题模板
        ttk.Label(update_frame, text="处理前N个问题模板:").grid(row=0, column=0, sticky=tk.W, padx=(10, 5), pady=5)
        self.problem_top_n_var = tk.IntVar(value=1)
        top_n_spin = ttk.Spinbox(update_frame, from_=1, to=999, textvariable=self.problem_top_n_var, width=5)
        top_n_spin.grid(row=0, column=1, sticky=tk.W)
        self.problem_use_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(update_frame, text="全部", variable=self.problem_use_all_var).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))

        # 每个天区最近日期数
        ttk.Label(update_frame, text="每个天区最近日期数:").grid(row=1, column=0, sticky=tk.W, padx=(10, 5), pady=5)
        self.problem_recent_days_var = tk.IntVar(value=3)
        recent_spin = ttk.Spinbox(update_frame, from_=1, to=30, textvariable=self.problem_recent_days_var, width=5)
        recent_spin.grid(row=1, column=1, sticky=tk.W)

        # 生成模板最少参与图像数
        ttk.Label(update_frame, text="生成模板最少参与图像数:").grid(row=2, column=0, sticky=tk.W, padx=(10, 5), pady=5)
        self.problem_min_images_var = tk.IntVar(value=30)
        min_images_spin = ttk.Spinbox(update_frame, from_=1, to=999, textvariable=self.problem_min_images_var, width=5)
        min_images_spin.grid(row=2, column=1, sticky=tk.W)
        # 重投影线程数
        ttk.Label(update_frame, text="重投影线程数:").grid(row=2, column=2, sticky=tk.W, padx=(10, 5), pady=5)
        self.problem_reproject_threads_var = tk.IntVar(value=10)
        threads_spin = ttk.Spinbox(update_frame, from_=1, to=64, textvariable=self.problem_reproject_threads_var, width=5)
        threads_spin.grid(row=2, column=3, sticky=tk.W)
        # 预处理线程数
        ttk.Label(update_frame, text="预处理线程数:").grid(row=2, column=4, sticky=tk.W, padx=(10, 5), pady=5)
        self.problem_preprocess_threads_var = tk.IntVar(value=20)
        preprocess_threads_spin = ttk.Spinbox(update_frame, from_=1, to=64, textvariable=self.problem_preprocess_threads_var, width=5)
        preprocess_threads_spin.grid(row=2, column=5, sticky=tk.W)


        # 下载/生成按钮和状态
        ttk.Button(update_frame, text="下载问题模板对应观测文件", command=self._update_problem_templates).grid(row=3, column=0, sticky=tk.W, padx=(10, 5), pady=(8, 5))
        ttk.Button(update_frame, text="预处理图像", command=self._preprocess_problem_images).grid(row=3, column=1, sticky=tk.W, padx=(5, 5), pady=(8, 5))
        ttk.Button(update_frame, text="生成新模板", command=self._make_problem_templates).grid(row=3, column=2, sticky=tk.W, padx=(5, 5), pady=(8, 5))
        ttk.Button(update_frame, text="逐个更新模板(老逻辑)", command=self._update_templates_one_by_one).grid(row=3, column=3, sticky=tk.W, padx=(5, 5), pady=(8, 5))
        self.template_update_status = ttk.Label(update_frame, text="就绪")
        self.template_update_status.grid(row=3, column=4, columnspan=2, sticky=tk.W, padx=(5, 5))

        # 说明文本单独放在第4行，避免被遮挡
        ttk.Label(
            update_frame,
            text="说明：从 gui/templates_update/fits_check_report.txt 读取问题模板，按 gy1_region_index.json 查找最近日期并下载相应观测文件。",
            foreground="gray"
        ).grid(row=4, column=0, columnspan=6, sticky=tk.W, padx=(10, 5), pady=(5, 8))

    def _open_calendar(self, var: tk.StringVar, title: str):
        try:
            from calendar_widget import CalendarDialog
        except Exception:
            messagebox.showwarning("提示", "未发现日历组件，需手动输入日期。")
            return
        current = var.get() or datetime.today().strftime("%Y%m%d")
        dlg = CalendarDialog(self.root, title, current)
        selected = dlg.show()
        if selected:
            var.set(selected)

    def _collect_regions_for_range(self):
        start = (self.region_collect_start_var.get() or "").strip()
        end = (self.region_collect_end_var.get() or "").strip()
        if not (self.config_manager.validate_date(start) and self.config_manager.validate_date(end)):
            messagebox.showerror("错误", "请输入有效的起止日期（YYYYMMDD）")
            return
        if start > end:
            messagebox.showerror("错误", "起始日期不能大于终止日期")
            return

        def work():
            try:
                self.region_collect_status_after("处理中...", "blue")
                total = 0
                from_cache = 0
                scanned = 0
                dt = datetime.strptime(start, "%Y%m%d")
                end_dt = datetime.strptime(end, "%Y%m%d")
                # 预先加载GY1索引（日期 -> [天区列表]）
                index = self._load_gy1_index()
                while dt <= end_dt:
                    date_str = dt.strftime("%Y%m%d")
                    total += 1
                    regions = index.get(date_str)
                    if isinstance(regions, list) and regions:
                        # 本地已有缓存
                        from_cache += 1
                        self._log(f"[GY1][{date_str}] 本地已有缓存，跳过扫描。")
                    else:
                        # 需要扫描
                        try:
                            base_url = self.url_builder._build_base_url("GY1", date_str)
                            regions = self.url_builder.region_scanner.scan_available_regions(base_url)
                            normalized = sorted({str(r).upper() for r in regions if r})
                            index[date_str] = normalized
                            scanned += 1
                            self._log(f"[GY1][{date_str}] 扫描完成，{len(normalized)} 个天区 -> 已缓存。")
                            # 为保护服务器，每次实际扫描后增加 0.5 秒延迟
                            time.sleep(0.5)
                        except Exception as e:
                            self._log(f"[GY1][{date_str}] 扫描失败: {e}")
                    # 更新进度
                    self.region_collect_status_after(
                        f"进度: {from_cache + scanned}/{total} 天；缓存: {from_cache} 天；扫描: {scanned} 天", "green"
                    )
                    dt = dt.replace(day=dt.day) + (
                        datetime.strptime("19700102", "%Y%m%d") - datetime.strptime("19700101", "%Y%m%d")
                    )
                # 所有日期处理完后统一写回索引文件
                self._save_gy1_index(index)
                self.region_collect_status_after(
                    f"完成：合计{total}天，其中缓存{from_cache}天，扫描{scanned}天。", "green"
                )
            except Exception as e:
                self.region_collect_status_after(f"失败：{e}", "red")

        threading.Thread(target=work, daemon=True).start()

    def _update_templates_one_by_one(self):
        """使用逐个模板的老逻辑：对每个问题模板单独执行 下载->预处理->生成 模板（后台线程）"""
        thread = threading.Thread(target=self._update_templates_one_by_one_worker, daemon=True)
        thread.start()

    def _update_templates_one_by_one_worker(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            report_path = os.path.join(base_dir, "templates_update", "fits_check_report.txt")
            self._template_update_status_after("解析 fits_check_report.txt...", "blue")
            system_name, problems = self._parse_fits_check_report(report_path)
            if not system_name:
                self._template_update_status_after("无法从报告中识别系统名称", "red")
                return
            if not problems:
                self._template_update_status_after("报告中未找到问题模板文件", "orange")
                return

            # 选择前N个问题模板
            use_all = bool(self.problem_use_all_var.get())
            try:
                top_n = int(self.problem_top_n_var.get())
            except Exception:
                top_n = 1
            if top_n < 1:
                top_n = 1
            selected = problems if use_all else problems[:top_n]

            try:
                recent_days = int(self.problem_recent_days_var.get())
            except Exception:
                recent_days = 3
            if recent_days < 1:
                recent_days = 1

            index = self._load_gy1_index()
            if not index:
                self._template_update_status_after("GY1索引为空，请先执行“天区收集”。", "red")
                return

            system_upper = system_name.upper()
            tel = system_upper.lower()

            # 准备下载器
            if not self.downloader:
                self.downloader = FitsDownloader(
                    max_workers=1,
                    retry_times=self.retry_times_var.get(),
                    timeout=self.timeout_var.get(),
                    enable_astap=False,
                    astap_config_path="config/url_config.json",
                )

            url_template = self.config_manager.get_url_template()

            # 导入生成模板和预处理所需的依赖
            try:
                import numpy as np
                from astropy.io import fits
                from astropy.wcs import WCS
                from reproject.mosaicking import find_optimal_celestial_wcs, reproject_and_coadd
                import reproject
                from fits_checking.fits_monitor import FITSQualityAnalyzer
            except Exception as e:
                self._template_update_status_after(f"逐个更新失败：缺少依赖库: {e}", "red")
                return

            # ASTAP 处理器
            if not ASTAPProcessor:
                self._template_update_status_after("ASTAP处理器不可用，无法执行逐个更新。", "red")
                return
            astap_config_path = os.path.join(base_dir, "..", "config", "url_config.json")
            astap_processor = ASTAPProcessor(astap_config_path)

            # 质量分析器和阈值（沿用批量预处理逻辑）
            quality_analyzer = FITSQualityAnalyzer()
            lm_thres = 15.0
            ell_thres = 0.2
            fwhm_thres = 10.0

            bad_dir = os.path.join(base_dir, "templates_update", "bad_img")
            os.makedirs(bad_dir, exist_ok=True)

            # 生成模板时的最少参与图像数设置
            try:
                min_images = int(self.problem_min_images_var.get())
            except Exception:
                min_images = 30
            if min_images < 1:
                min_images = 1

            # 重投影线程数设置
            try:
                parallel_threads = int(self.problem_reproject_threads_var.get())
            except Exception:
                parallel_threads = 10
            if parallel_threads < 1:
                parallel_threads = 1

            total_templates = len(selected)
            made = 0

            from datetime import datetime as _dt

            def _format_bytes(num):
                if num is None:
                    return "未知"
                try:
                    num = float(num)
                except Exception:
                    return str(num)
                for unit in ["B", "KB", "MB", "GB"]:
                    if num < 1024.0:
                        return f"{num:.1f}{unit}"
                    num /= 1024.0
                return f"{num:.1f}TB"

            def _compute_lm5sig(fits_path: Path):
                """根据 .check.fits 和曝光时间计算5σ限制星等，并写入LM5SIG"""
                try:
                    stem = fits_path.stem
                    check_path = fits_path.with_name(f"{stem}.check.fits")
                    if not check_path.exists():
                        return None
                    with fits.open(check_path) as chdul:
                        data = chdul[0].data
                    if data is None:
                        return None
                    data = np.asarray(data, dtype=np.float64)
                    med = float(np.median(data))
                    if med <= 0:
                        return None
                    with fits.open(str(fits_path), mode="update") as hdul2:
                        hdr = hdul2[0].header
                        exptime = hdr.get("EXPOSURE", hdr.get("EXPTIME", 1.0))
                        try:
                            exptime = float(exptime)
                        except Exception:
                            exptime = 1.0
                        if exptime <= 0:
                            exptime = 1.0
                        zp = None
                        for key in ("ZP", "PHOTZP", "MAGZP", "ZP_MAG"):
                            if key in hdr:
                                zp = hdr.get(key)
                                break
                        if zp is None:
                            zp = 25.0
                        try:
                            zp = float(zp)
                        except Exception:
                            zp = 25.0
                        lmag = zp - 2.5 * np.log10(med * 5.0 * np.pi * 4.0**2 / exptime)
                        lmag = float(round(lmag, 3))
                        hdr["LM5SIG"] = (lmag, "5-sigma limiting magnitude")
                        hdul2.flush()
                    return lmag
                except Exception as e:
                    self._log(f"[逐个更新] 计算LM5SIG失败 {fits_path}: {e}")
                    return None

            # 对每个问题模板逐个执行：下载 -> 预处理 -> 生成
            for idx, problem in enumerate(selected, 1):
                k_number = problem.get("k_number")
                suffix = problem.get("suffix")
                k_full = problem.get("k_full")
                if not (k_number and suffix and k_full):
                    continue

                try:
                    k_region = int(str(k_number).lstrip("Kk"))
                    k_index = int(suffix)
                except Exception:
                    self._log(f"[逐个更新] 无法解析天区编号: {k_number}-{suffix}")
                    continue

                field_name = f"K{k_region:03d}-{k_index}"

                # 每个模板单独的 update 子目录
                update_root = os.path.join(base_dir, "templates_update", "update", tel, k_full)
                output_root = os.path.join(base_dir, "templates_update", "output", tel)
                os.makedirs(update_root, exist_ok=True)
                os.makedirs(output_root, exist_ok=True)

                # 如果输出模板已存在，则跳过
                temp_name = f"{field_name}.fits"
                existing_temp_path = Path(output_root) / temp_name
                if existing_temp_path.exists():
                    self._log(f"[逐个更新] 已存在输出模板 {system_upper} {k_full} -> {existing_temp_path}，跳过。")
                    continue

                # 1) 下载：仅下载当前模板需要的观测文件到其专属目录
                try:
                    dates = self._find_recent_dates_for_region(index, k_number, recent_days)
                except Exception:
                    dates = []
                if not dates:
                    self._log(f"[逐个更新] 天区 {k_number} 在 GY1 索引中没有找到任何日期，跳过。")
                    continue

                total_downloaded = 0

                for date in dates:
                    format_params = {"tel_name": system_upper, "date": date, "k_number": k_number}
                    if "{year_of_date}" in url_template:
                        try:
                            year_of_date = date[:4] if len(date) >= 4 else _dt.now().strftime("%Y")
                        except Exception:
                            year_of_date = _dt.now().strftime("%Y")
                        format_params["year_of_date"] = year_of_date

                    region_url = url_template.format(**format_params)
                    self._log(f"[逐个更新-下载] 扫描 {system_upper} {date} {k_full} - {region_url}")
                    try:
                        fits_files = self.directory_scanner.scan_directory_listing(region_url)
                        if not fits_files:
                            fits_files = self.scanner.scan_fits_files(region_url)
                    except Exception as e:
                        self._log(f"[逐个更新-下载] 扫描失败 {region_url}: {e}")
                        continue

                    if not fits_files:
                        self._log(f"[逐个更新-下载] {system_upper} {date} {k_full} 未找到任何FITS文件")
                        continue

                    pattern = k_full.lower()
                    candidates = [(fn, url, size) for fn, url, size in fits_files if pattern in fn.lower()]
                    if not candidates:
                        self._log(f"[逐个更新-下载] {system_upper} {date} 未找到包含 {k_full} 的文件（共 {len(fits_files)} 个）")
                        continue

                    for j, (filename, file_url, size) in enumerate(candidates, 1):
                        try:
                            self._log(
                                f"[逐个更新-下载] ({idx}/{total_templates}) #{j}/{len(candidates)} 下载 {system_upper} {date} {k_full} -> {filename}"
                            )

                            start_time = time.time()
                            last_update = [start_time]

                            def progress_callback(downloaded_bytes, total_bytes, fn):
                                now = time.time()
                                if now - last_update[0] < 0.3 and (total_bytes is None or downloaded_bytes < (total_bytes or 0)):
                                    return
                                last_update[0] = now
                                elapsed = max(now - start_time, 1e-3)
                                speed = downloaded_bytes / elapsed
                                speed_str = _format_bytes(speed)
                                downloaded_str = _format_bytes(downloaded_bytes)
                                total_str = _format_bytes(total_bytes) if total_bytes is not None else "未知"
                                text = f"逐个更新下载中: {fn} {downloaded_str}/{total_str} @ {speed_str}/s"
                                self._template_update_status_after(text, "blue")

                            result = self.downloader.download_single_file(file_url, update_root, progress_callback)

                            if isinstance(result, str) and result.startswith("跳过已存在文件"):
                                status_text = (
                                    f"逐个更新: 已存在，跳过 - {system_upper} {date} {k_full} -> {result}"
                                )
                                self._template_update_status_after(status_text, "orange")
                            else:
                                total_downloaded += 1
                                status_text = (
                                    f"逐个更新: 已下载 {total_downloaded} 个文件 - {system_upper} {date} {k_full} -> {result}"
                                )
                                self._template_update_status_after(status_text, "green")
                        except Exception as e:
                            self._log(f"[逐个更新-下载] 下载失败 {file_url}: {e}")
                            status_text = f"逐个更新下载失败: {system_upper} {date} {k_full} - {e}"
                            self._template_update_status_after(status_text, "red")

                # 收集当前模板 update 目录中的FITS文件
                update_root_path = Path(update_root)
                fits_paths = []
                for ext in (".fits", ".fit", ".fts"):
                    fits_paths.extend(update_root_path.glob(f"*{ext}"))
                    fits_paths.extend(update_root_path.glob(f"*{ext.upper()}"))
                fits_paths = sorted(set(fits_paths))
                if not fits_paths:
                    self._template_update_status_after(
                        f"逐个更新: {system_upper} {k_full} 的 update 目录中没有任何FITS文件，跳过。",
                        "orange",
                    )
                    continue

                # 2) 预处理：对该模板的所有文件执行 ASTAP + 质量筛选
                self._template_update_status_after(
                    f"逐个更新: ({idx}/{total_templates}) {system_upper} {k_full} - 开始预处理 {len(fits_paths)} 个FITS文件...",
                    "blue",
                )

                good_hdus = []
                used_files = []

                for p in fits_paths:
                    file_path = str(p)
                    basename = p.name
                    reasons = []
                    is_bad = False

                    # ASTAP 解算
                    try:
                        astap_ok = astap_processor.process_fits_file(file_path)
                        if not astap_ok:
                            reasons.append("ASTAP失败")
                            is_bad = True
                    except Exception as e:
                        self._log(f"[逐个更新-预处理] ASTAP处理异常 {file_path}: {e}")
                        reasons.append("ASTAP异常")
                        is_bad = True

                    # 质量评估
                    fwhm = np.nan
                    ellip = np.nan
                    lm_val = None
                    try:
                        with fits.open(file_path) as hdul:
                            data = hdul[0].data
                        if data is not None:
                            image = data.astype(np.float64)
                            metrics = quality_analyzer.calculate_quality_metrics(image)
                            if metrics:
                                fwhm = float(metrics.get("fwhm", np.nan))
                                ellip = float(metrics.get("ellipticity", np.nan))
                                lm_val = metrics.get("lm5sig")
                    except Exception as e:
                        self._log(f"[逐个更新-预处理] 质量分析失败 {file_path}: {e}")

                    lm_from_check = _compute_lm5sig(p)
                    if lm_from_check is not None:
                        lm_val = lm_from_check

                    if lm_val is None or not (isinstance(lm_val, (int, float)) and np.isfinite(lm_val)):
                        reasons.append("LM未知")
                        is_bad = True
                    elif lm_val < lm_thres:
                        reasons.append(f"LM5SIG={lm_val:.2f}<{lm_thres}")
                        is_bad = True

                    if not (isinstance(fwhm, (int, float)) and np.isfinite(fwhm)) or fwhm > fwhm_thres:
                        reasons.append(f"FWHM={fwhm}")
                        is_bad = True
                    if not (isinstance(ellip, (int, float)) and np.isfinite(ellip)) or ellip > ell_thres:
                        reasons.append(f"ELL={ellip}")
                        is_bad = True

                    if is_bad:
                        try:
                            dest = os.path.join(bad_dir, basename)
                            shutil.move(file_path, dest)
                            self._log(f"[逐个更新-预处理] 移动到 bad_img: {basename} ({'; '.join(reasons)})")
                        except Exception as e:
                            self._log(f"[逐个更新-预处理] 移动坏图像失败 {file_path}: {e}")
                    else:
                        # 作为候选参与模板合成
                        try:
                            hdu = fits.open(file_path)[0]
                            try:
                                w = WCS(hdu.header)
                                if not w.has_celestial:
                                    self._log(f"[逐个更新-预处理] 文件缺少天球WCS，跳过: {file_path}")
                                else:
                                    good_hdus.append(hdu)
                                    used_files.append(file_path)
                            except Exception as w_err:
                                self._log(f"[逐个更新-预处理] 文件WCS检查失败，跳过: {file_path}: {w_err}")
                        except Exception as e:
                            self._log(f"[逐个更新-预处理] 打开文件失败 {file_path}: {e}")

                if not good_hdus:
                    self._template_update_status_after(
                        f"逐个更新: {system_upper} {k_full} 预处理后没有可用的图像，跳过生成模板。",
                        "orange",
                    )
                    continue

                if len(good_hdus) < min_images:
                    self._template_update_status_after(
                        f"逐个更新: {system_upper} {k_full} 可用图像数 {len(good_hdus)} 小于最少参与图像数 {min_images}，跳过生成。",
                        "orange",
                    )
                    continue

                # 3) 生成模板：对 good_hdus 做重投影和合成
                self._template_update_status_after(
                    f"逐个更新: ({idx}/{total_templates}) {system_upper} {k_full} - 使用 {len(good_hdus)} 个文件合成模板...",
                    "blue",
                )

                try:
                    start_time = time.time()

                    wcs, shape_out = find_optimal_celestial_wcs(good_hdus)

                    hdu_list2 = []
                    for fpath in used_files:
                        try:
                            hdu_list2.append(fits.open(fpath)[0])
                        except Exception as e:
                            self._log(f"[逐个更新-生成] 重投影时打开文件失败 {fpath}: {e}")

                    if not hdu_list2:
                        self._template_update_status_after(
                            f"逐个更新: {system_upper} {k_full} 重投影时没有可用的HDU，跳过。",
                            "orange",
                        )
                        continue

                    comb, footprint = reproject_and_coadd(
                        hdu_list2,
                        wcs,
                        shape_out=shape_out,
                        reproject_function=reproject.reproject_interp,
                        combine_function="mean",
                        match_background=True,
                        parallel=parallel_threads,
                    )

                    data = np.where(footprint == len(hdu_list2), comb, np.nan).astype("float32")

                    no_trim_name = f"{field_name}_no_trim.fits"
                    temp_name = f"{field_name}.fits"

                    write_temp_dir = Path(output_root)
                    write_temp_dir.mkdir(parents=True, exist_ok=True)
                    no_trim_path = write_temp_dir / no_trim_name
                    temp_path = write_temp_dir / temp_name

                    fits.writeto(no_trim_path, data, wcs.to_header(), overwrite=True)

                    mask = np.isfinite(data)
                    if not mask.any():
                        self._log(f"[逐个更新-生成] {system_upper} {k_full} 合成结果全部为NaN，跳过裁剪。")
                        continue

                    ys, xs = np.where(mask)
                    y_min, y_max = int(ys.min()), int(ys.max())
                    x_min, x_max = int(xs.min()), int(xs.max())

                    trimmed_data = data[y_min: y_max + 1, x_min: x_max + 1].astype("float32")

                    header = wcs.to_header()
                    try:
                        if "CRPIX1" in header:
                            header["CRPIX1"] -= x_min
                        if "CRPIX2" in header:
                            header["CRPIX2"] -= y_min
                    except Exception:
                        pass

                    fits.writeto(temp_path, trimmed_data, header, overwrite=True)

                    elapsed = time.time() - start_time
                    self._log(f"[逐个更新-生成] 完成 {system_upper} {k_full} -> {temp_path}，用时 {elapsed:.1f} 秒")

                    made += 1
                    self._template_update_status_after(
                        f"逐个更新: ({idx}/{total_templates}) {system_upper} {k_full} -> {temp_path.name} ({elapsed:.1f}s)",
                        "green",
                    )
                except Exception as e:
                    files_str = ", ".join(str(p) for p in fits_paths)
                    self._log(f"[逐个更新-生成] {system_upper} {k_full} 处理失败: {e} | 文件列表: {files_str}")

            if made:
                self._template_update_status_after(
                    f"逐个更新完成：成功生成 {made}/{total_templates} 个模板，输出目录: templates_update/output/{tel}",
                    "green",
                )
            else:
                self._template_update_status_after("逐个更新完成：没有成功生成任何新模板。", "orange")
        except Exception as e:
            self._template_update_status_after(f"逐个更新出错: {e}", "red")


    def _update_problem_templates(self):
        """根据 fits_check_report.txt 下载问题模板对应的最新观测文件（后台线程）"""
        thread = threading.Thread(target=self._update_problem_templates_worker, daemon=True)
        thread.start()

    def _update_problem_templates_worker(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            report_path = os.path.join(base_dir, "templates_update", "fits_check_report.txt")
            self._template_update_status_after("解析 fits_check_report.txt...", "blue")
            system_name, problems = self._parse_fits_check_report(report_path)
            if not system_name:
                self._template_update_status_after("无法从报告中识别系统名称", "red")
                return
            if not problems:
                self._template_update_status_after("报告中未找到问题模板文件", "orange")
                return

            # 选择前N个问题模板
            use_all = bool(self.problem_use_all_var.get())
            try:
                top_n = int(self.problem_top_n_var.get())
            except Exception:
                top_n = 1
            if top_n < 1:
                top_n = 1
            selected = problems if use_all else problems[:top_n]

            try:
                recent_days = int(self.problem_recent_days_var.get())
            except Exception:
                recent_days = 3
            if recent_days < 1:
                recent_days = 1

            index = self._load_gy1_index()
            if not index:
                self._template_update_status_after("GY1索引为空，请先执行“天区收集”。", "red")
                return

            system_upper = system_name.upper()
            update_root = os.path.join(base_dir, "templates_update", "update", system_upper.lower())
            os.makedirs(update_root, exist_ok=True)

            if not self.downloader:
                self.downloader = FitsDownloader(
                    max_workers=1,
                    retry_times=self.retry_times_var.get(),
                    timeout=self.timeout_var.get(),
                    enable_astap=False,
                    astap_config_path="config/url_config.json"
                )

            # 准备下载任务列表：[(problem_item, date_str), ...]
            tasks = []
            for item in selected:
                region = item["k_number"]
                dates = self._find_recent_dates_for_region(index, region, recent_days)
                if not dates:
                    self._log(f"[模板更新] 天区 {region} 在 GY1 索引中没有找到任何日期，跳过。")
                    continue
                for date in dates:
                    tasks.append((item, date))

            if not tasks:
                self._template_update_status_after("没有需要下载的文件（所有天区在索引中都不存在）", "orange")
                return

            url_template = self.config_manager.get_url_template()
            total_tasks = len(tasks)
            completed = 0

            from datetime import datetime as _dt
            def _format_bytes(num):
                if num is None:
                    return "未知"
                try:
                    num = float(num)
                except Exception:
                    return str(num)
                for unit in ["B", "KB", "MB", "GB"]:
                    if num < 1024.0:
                        return f"{num:.1f}{unit}"
                    num /= 1024.0
                return f"{num:.1f}TB"



            for idx, (problem, date) in enumerate(tasks, 1):
                region = problem["k_number"]
                k_full = problem["k_full"]

                # 构建该天区的URL
                format_params = {"tel_name": system_upper, "date": date, "k_number": region}
                if "{year_of_date}" in url_template:
                    try:
                        year_of_date = date[:4] if len(date) >= 4 else _dt.now().strftime("%Y")
                    except Exception:
                        year_of_date = _dt.now().strftime("%Y")
                    format_params["year_of_date"] = year_of_date

                region_url = url_template.format(**format_params)
                self._log(f"[模板更新] 扫描 {system_upper} {date} {k_full} - {region_url}")
                try:
                    fits_files = self.directory_scanner.scan_directory_listing(region_url)
                    if not fits_files:
                        fits_files = self.scanner.scan_fits_files(region_url)
                except Exception as e:
                    self._log(f"[模板更新] 扫描失败 {region_url}: {e}")
                    continue

                if not fits_files:
                    self._log(f"[模板更新] {system_upper} {date} {k_full} 未找到任何FITS文件")
                    continue

                pattern = k_full.lower()
                candidates = [(fn, url) for fn, url, size in fits_files if pattern in fn.lower()]
                if not candidates:
                    self._log(f"[模板更新] {system_upper} {date} 未找到包含 {k_full} 的文件（共 {len(fits_files)} 个）")
                    continue

                for j, (filename, file_url) in enumerate(candidates, 1):
                    try:
                        self._log(
                            f"[模板更新] ({idx}/{total_tasks}) #{j}/{len(candidates)} 下载 {system_upper} {date} {k_full} -> {filename}"
                        )

                        start_time = time.time()
                        last_update = [start_time]

                        def progress_callback(downloaded_bytes, total_bytes, fn):
                            now = time.time()
                            # 限速更新，避免过于频繁
                            if now - last_update[0] < 0.3 and (total_bytes is None or downloaded_bytes < (total_bytes or 0)):
                                return
                            last_update[0] = now
                            elapsed = max(now - start_time, 1e-3)
                            speed = downloaded_bytes / elapsed
                            speed_str = _format_bytes(speed)
                            downloaded_str = _format_bytes(downloaded_bytes)
                            total_str = _format_bytes(total_bytes) if total_bytes is not None else "未知"
                            text = (
                                f"模板更新下载中: {fn} {downloaded_str}/{total_str} @ {speed_str}/s"
                            )
                            self._template_update_status_after(text, "blue")

                        result = self.downloader.download_single_file(file_url, update_root, progress_callback)

                        # 已存在且完整的文件由下载器返回“跳过已存在文件”
                        if isinstance(result, str) and result.startswith("跳过已存在文件"):
                            status_text = (
                                f"模板更新: 已存在，跳过 - {system_upper} {date} {k_full} -> {result}"
                            )
                            self._template_update_status_after(status_text, "orange")
                        else:
                            completed += 1
                            status_text = (
                                f"模板更新: 已下载 {completed} 个文件 - {system_upper} {date} {k_full} -> {result}"
                            )
                            self._template_update_status_after(status_text, "green")
                    except Exception as e:
                        self._log(f"[模板更新] 下载失败 {file_url}: {e}")
                        status_text = f"模板更新失败: {system_upper} {date} {k_full} - {e}"
                        self._template_update_status_after(status_text, "red")

            if completed:
                self._template_update_status_after(f"模板更新完成：成功 {completed}/{total_tasks} 个下载任务。", "green")
            else:
                self._template_update_status_after("模板更新完成：没有成功下载任何文件。", "orange")
        except Exception as e:
            self._template_update_status_after(f"模板更新出错: {e}", "red")


    def _preprocess_problem_images(self):
        """预处理已下载的观测图像（ASTAP多线程 + 质量筛选）"""
        thread = threading.Thread(target=self._preprocess_problem_images_worker, daemon=True)
        thread.start()

    def _preprocess_problem_images_worker(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            report_path = os.path.join(base_dir, "templates_update", "fits_check_report.txt")
            self._template_update_status_after("解析 fits_check_report.txt...", "blue")
            system_name, problems = self._parse_fits_check_report(report_path)
            if not system_name:
                self._template_update_status_after("无法从报告中识别系统名称", "red")
                return

            system_upper = system_name.upper()
            tel = system_upper.lower()
            update_root = os.path.join(base_dir, "templates_update", "update", tel)
            update_root_path = Path(update_root)
            if not update_root_path.exists():
                self._template_update_status_after("下载目录不存在，请先点击“下载问题模板对应观测文件”。", "red")
                return

            # 收集待处理FITS文件
            fits_files = []
            for ext in [".fits", ".fit", ".fts"]:
                fits_files.extend(update_root_path.glob(f"*{ext}"))
                fits_files.extend(update_root_path.glob(f"*{ext.upper()}"))
            fits_files = sorted(set(fits_files))
            if not fits_files:
                self._template_update_status_after("预处理失败：下载目录中未找到任何FITS文件。", "orange")
                return

            # 导入依赖
            try:
                import numpy as np
                from astropy.io import fits
                from fits_checking.fits_monitor import FITSQualityAnalyzer
            except Exception as e:
                self._template_update_status_after(f"预处理失败：缺少依赖库（numpy/astropy/fits_checking）: {e}", "red")
                return

            # ASTAP 处理器
            if not ASTAPProcessor:
                self._template_update_status_after("ASTAP处理器不可用，无法执行预处理。", "red")
                return
            config_path = os.path.join(base_dir, "..", "config", "url_config.json")
            astap_processor = ASTAPProcessor(config_path)

            # 质量分析器
            quality_analyzer = FITSQualityAnalyzer()

            # 阈值
            lm_thres = 15.0
            ell_thres = 0.2
            fwhm_thres = 10.0

            bad_dir = os.path.join(base_dir, "templates_update", "bad_img")
            os.makedirs(bad_dir, exist_ok=True)

            import shutil
            import math
            import threading as _threading

            total = len(fits_files)
            counters = {"processed": 0, "bad": 0}
            lock = _threading.Lock()

            def _compute_lm5sig(fits_path: Path):
                """根据 .check.fits 和曝光时间计算5σ限制星等，并写入LM5SIG"""
                stem = fits_path.stem
                check_path = fits_path.with_name(f"{stem}.check.fits")
                if not check_path.exists():
                    return None
                try:
                    with fits.open(check_path) as chdul:
                        data = chdul[0].data
                    if data is None:
                        return None
                    data = np.asarray(data, dtype=np.float64)
                    med = float(np.median(data))
                    if med <= 0:
                        return None
                    with fits.open(str(fits_path), mode="update") as hdul2:
                        hdr = hdul2[0].header
                        exptime = hdr.get("EXPOSURE", hdr.get("EXPTIME", 1.0))
                        try:
                            exptime = float(exptime)
                        except Exception:
                            exptime = 1.0
                        if exptime <= 0:
                            exptime = 1.0
                        zp = None
                        for key in ("ZP", "PHOTZP", "MAGZP", "ZP_MAG"):
                            if key in hdr:
                                zp = hdr.get(key)
                                break
                        if zp is None:
                            zp = 25.0
                        try:
                            zp = float(zp)
                        except Exception:
                            zp = 25.0
                        lmag = zp - 2.5 * np.log10(med * 5.0 * np.pi * 4.0**2 / exptime)
                        lmag = float(round(lmag, 3))
                        hdr["LM5SIG"] = (lmag, "5-sigma limiting magnitude")
                        hdul2.flush()
                    return lmag
                except Exception as e:
                    self._log(f"[预处理] 计算LM5SIG失败 {fits_path}: {e}")
                    return None

            def _process_single(path: Path):
                file_path = str(path)
                basename = path.name
                reasons = []
                is_bad = False

                # 1) ASTAP 解算（内部自动跳过已有WCS的文件）
                try:
                    astap_ok = astap_processor.process_fits_file(file_path)
                    if not astap_ok:
                        reasons.append("ASTAP失败")
                        is_bad = True
                except Exception as e:
                    self._log(f"[预处理] ASTAP处理异常 {file_path}: {e}")
                    reasons.append("ASTAP异常")
                    is_bad = True

                # 2) 质量评估（FWHM、椭圆度）
                fwhm = np.nan
                ellip = np.nan
                lm_val = None
                try:
                    with fits.open(file_path) as hdul:
                        data = hdul[0].data
                    if data is not None:
                        image = data.astype(np.float64)
                        metrics = quality_analyzer.calculate_quality_metrics(image)
                        if metrics:
                            fwhm = float(metrics.get("fwhm", np.nan))
                            ellip = float(metrics.get("ellipticity", np.nan))
                            lm_val = metrics.get("lm5sig")
                except Exception as e:
                    self._log(f"[预处理] 质量分析失败 {file_path}: {e}")

                # 3) 从 .check.fits 计算限制星等（如有），优先使用
                lm_from_check = _compute_lm5sig(path)
                if lm_from_check is not None:
                    lm_val = lm_from_check

                # 4) 根据阈值判断
                if lm_val is None or not (isinstance(lm_val, (int, float)) and math.isfinite(lm_val)):
                    reasons.append("LM未知")
                    is_bad = True
                elif lm_val < lm_thres:
                    reasons.append(f"LM5SIG={lm_val:.2f}<{lm_thres}")
                    is_bad = True

                if not (isinstance(fwhm, (int, float)) and math.isfinite(fwhm)) or fwhm > fwhm_thres:
                    reasons.append(f"FWHM={fwhm}")
                    is_bad = True
                if not (isinstance(ellip, (int, float)) and math.isfinite(ellip)) or ellip > ell_thres:
                    reasons.append(f"ELL={ellip}")
                    is_bad = True

                # 5) 移动到 bad_img
                if is_bad:
                    try:
                        dest = os.path.join(bad_dir, basename)
                        shutil.move(file_path, dest)
                        self._log(f"[预处理] 移动到 bad_img: {basename} ({'; '.join(reasons)})")
                    except Exception as e:
                        self._log(f"[预处理] 移动坏图像失败 {file_path}: {e}")

                # 6) 更新进度
                with lock:
                    counters["processed"] += 1
                    if is_bad:
                        counters["bad"] += 1
                    processed = counters["processed"]
                    bad = counters["bad"]

                status = "BAD" if is_bad else "OK"
                color = "orange" if is_bad else "green"
                text = f"预处理: ({processed}/{total}) {basename} -> {status}，坏图像 {bad} 张"
                self._template_update_status_after(text, color)

            try:
                max_workers = int(self.problem_preprocess_threads_var.get())
            except Exception:
                max_workers = 20
            if max_workers < 1:
                max_workers = 1
            self._template_update_status_after(
                f"开始预处理 {total} 个FITS文件（ASTAP多线程 + 质量筛选）...", "blue"
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(_process_single, fits_files)

            bad = counters["bad"]
            self._template_update_status_after(
                f"预处理完成：共处理 {total} 个文件，坏图像 {bad} 个（已移动到 templates_update/bad_img）",
                "green",
            )
        except Exception as e:
            self._template_update_status_after(f"预处理出错: {e}", "red")


    def _make_problem_templates(self):
        """根据已下载的观测文件生成新模板（后台线程）"""
        thread = threading.Thread(target=self._make_problem_templates_worker, daemon=True)
        thread.start()

    def _make_problem_templates_worker(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            report_path = os.path.join(base_dir, "templates_update", "fits_check_report.txt")
            self._template_update_status_after("解析 fits_check_report.txt...", "blue")
            system_name, problems = self._parse_fits_check_report(report_path)
            if not system_name:
                self._template_update_status_after("无法从报告中识别系统名称", "red")
                return
            if not problems:
                self._template_update_status_after("报告中未找到问题模板文件", "orange")
                return

            # 选择前N个问题模板
            use_all = bool(self.problem_use_all_var.get())
            try:
                top_n = int(self.problem_top_n_var.get())
            except Exception:
                top_n = 1
            if top_n < 1:
                top_n = 1
            selected = problems if use_all else problems[:top_n]

            system_upper = system_name.upper()
            tel = system_upper.lower()
            update_root = os.path.join(base_dir, "templates_update", "update", tel)
            output_root = os.path.join(base_dir, "templates_update", "output", tel)
            os.makedirs(output_root, exist_ok=True)

            update_root_path = Path(update_root)
            if not update_root_path.exists():
                self._template_update_status_after("下载目录不存在，请先点击“下载问题模板对应观测文件”。", "red")
                return

            # 先对下载目录中的文件执行ASTAP解算
            if not ASTAPProcessor:
                self._template_update_status_after("ASTAP处理器不可用，无法生成新模板。", "red")
                return

            self._template_update_status_after("正在对下载文件执行ASTAP解算...", "blue")
            try:
                config_path = os.path.join(base_dir, "..", "config", "url_config.json")
                astap_processor = ASTAPProcessor(config_path)

                # ASTAP解算进度回调：在状态栏显示已处理文件数
                def _astap_progress(current, total, file_path, success):
                    basename = os.path.basename(file_path)
                    status = "成功" if success else "失败"
                    color = "blue" if success else "orange"
                    self._template_update_status_after(
                        f"ASTAP解算: ({current}/{total}) {status} - {basename}",
                        color,
                    )

                astap_processor.process_directory(update_root, progress_callback=_astap_progress)
            except Exception as e:
                self._log(f"[模板生成] ASTAP解算过程中出错: {e}")

            # 导入生成模板所需的库
            try:
                import numpy as np
                from astropy.io import fits
                from astropy.wcs import WCS
                from reproject.mosaicking import find_optimal_celestial_wcs, reproject_and_coadd
                import reproject
            except Exception as e:
                self._template_update_status_after(f"模板生成失败：缺少依赖库（numpy/astropy/reproject）: {e}", "red")
                return

            total_templates = len(selected)
            made = 0

            # 生成模板时的最少参与图像数设置
            try:
                min_images = int(self.problem_min_images_var.get())
            except Exception:
                min_images = 30
            if min_images < 1:
                min_images = 1

            # 重投影线程数设置
            try:
                parallel_threads = int(self.problem_reproject_threads_var.get())
            except Exception:
                parallel_threads = 10
            if parallel_threads < 1:
                parallel_threads = 1

            for idx, item in enumerate(selected, 1):
                k_number = item.get("k_number")
                suffix = item.get("suffix")
                k_full = item.get("k_full")
                if not (k_number and suffix and k_full):
                    continue

                try:
                    k_region = int(str(k_number).lstrip("Kk"))
                    k_index = int(suffix)
                except Exception:
                    self._log(f"[模板生成] 无法解析天区编号: {k_number}-{suffix}")
                    continue

                # 如果输出目录中该模板已存在，则直接跳过
                field_name = f"K{k_region:03d}-{k_index}"
                temp_name = f"{field_name}.fits"
                existing_temp_path = Path(output_root) / temp_name
                if existing_temp_path.exists():
                    self._log(f"[模板生成] 已存在输出模板 {system_upper} {k_full} -> {existing_temp_path}，跳过。")
                    continue

                pattern = k_full.lower()
                fits_files = []
                for ext in ("*.fits", "*.fit", "*.fts"):
                    for p in update_root_path.glob(ext):
                        if pattern in p.name.lower():
                            fits_files.append(str(p))

                if not fits_files:
                    self._log(f"[模板生成] {system_upper} {k_full} 在下载目录中未找到任何FITS文件，跳过。")
                    continue

                self._template_update_status_after(
                    f"模板生成: ({idx}/{total_templates}) {system_upper} {k_full} - 使用 {len(fits_files)} 个文件合成...",
                    "blue",
                )

                try:
                    start_time = time.time()
                    # 收集具有天球WCS的HDU，出问题的文件逐个跳过
                    hdu_list = []
                    used_files = []
                    for fpath in fits_files:
                        try:
                            hdu = fits.open(fpath)[0]
                            try:
                                w = WCS(hdu.header)
                                if not w.has_celestial:
                                    self._log(f"[模板生成] 文件缺少天球WCS，跳过: {fpath}")
                                    continue
                            except Exception as w_err:
                                self._log(f"[模板生成] 文件WCS检查失败，跳过: {fpath}: {w_err}")
                                continue

                            hdu_list.append(hdu)
                            used_files.append(fpath)
                        except Exception as e:
                            self._log(f"[模板生成] 打开文件失败 {fpath}: {e}")

                    if not hdu_list:
                        self._log(f"[模板生成] {system_upper} {k_full} 所有文件均缺少有效天球WCS或无法打开，跳过。")
                        continue

                    # 如果可用图像数小于阈值，则不生成该模板
                    if len(hdu_list) < min_images:
                        self._log(
                            f"[模板生成] {system_upper} {k_full} 可用图像数 {len(hdu_list)} 小于最少参与图像数 {min_images}，跳过生成。"
                        )
                        continue

                    wcs, shape_out = find_optimal_celestial_wcs(hdu_list)

                    # 为避免内存泄漏，重新打开一次用于真正重投影
                    hdu_list2 = []
                    for fpath in used_files:
                        try:
                            hdu_list2.append(fits.open(fpath)[0])
                        except Exception as e:
                            self._log(f"[模板生成] 重投影时打开文件失败 {fpath}: {e}")

                    if not hdu_list2:
                        self._log(f"[模板生成] {system_upper} {k_full} 重投影时没有可用的HDU，跳过。")
                        continue

                    comb, footprint = reproject_and_coadd(
                        hdu_list2,
                        wcs,
                        shape_out=shape_out,
                        reproject_function=reproject.reproject_interp,
                        combine_function="mean",
                        match_background=True,
                        parallel=parallel_threads,
                    )

                    # 只保留所有图像都覆盖的位置，其它位置设为NaN，并转为 float32 以兼容旧程序
                    data = np.where(footprint == len(hdu_list2), comb, np.nan).astype("float32")

                    field_name = f"K{k_region:03d}-{k_index}"
                    no_trim_name = f"{field_name}_no_trim.fits"
                    temp_name = f"{field_name}.fits"

                    write_temp_dir = Path(output_root)
                    write_temp_dir.mkdir(parents=True, exist_ok=True)
                    no_trim_path = write_temp_dir / no_trim_name
                    temp_path = write_temp_dir / temp_name

                    # 写入未裁剪模板
                    fits.writeto(no_trim_path, data, wcs.to_header(), overwrite=True)

                    # 简单实现 trim_zeros：裁掉外围都是NaN的区域，并修正CRPIX
                    mask = np.isfinite(data)
                    if not mask.any():
                        self._log(f"[模板生成] {system_upper} {k_full} 合成结果全部为NaN，跳过裁剪。")
                        continue

                    ys, xs = np.where(mask)
                    y_min, y_max = int(ys.min()), int(ys.max())
                    x_min, x_max = int(xs.min()), int(xs.max())
                    # 裁剪后也保持 float32
                    trimmed_data = data[y_min: y_max + 1, x_min: x_max + 1].astype("float32")

                    header = wcs.to_header()
                    try:
                        if "CRPIX1" in header:
                            header["CRPIX1"] -= x_min
                        if "CRPIX2" in header:
                            header["CRPIX2"] -= y_min
                    except Exception:
                        pass

                    fits.writeto(temp_path, trimmed_data, header, overwrite=True)

                    elapsed = time.time() - start_time
                    self._log(f"[模板生成] 完成 {system_upper} {k_full} -> {temp_path}，用时 {elapsed:.1f} 秒")

                    made += 1
                    self._template_update_status_after(
                        f"模板生成: ({idx}/{total_templates}) {system_upper} {k_full} -> {temp_path.name} ({elapsed:.1f}s)",
                        "green",
                    )
                except Exception as e:
                    # 记录更详细的信息，指出涉及到的观测文件，然后跳过该模板
                    files_str = ", ".join(str(p) for p in fits_files)
                    self._log(f"[模板生成] {system_upper} {k_full} 处理失败: {e} | 文件列表: {files_str}")

            if made:
                self._template_update_status_after(
                    f"模板生成完成：成功生成 {made}/{total_templates} 个模板，输出目录: templates_update/output/{tel}",
                    "green",
                )
            else:
                self._template_update_status_after("模板生成完成：没有成功生成任何新模板。", "orange")
        except Exception as e:
            self._template_update_status_after(f"模板生成出错: {e}", "red")



    def _parse_fits_check_report(self, report_path: str):
        """解析 gui/templates_update/fits_check_report.txt，返回 (system_name, problems)"""
        system_name = None
        problems = []
        try:
            import re
            with open(report_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("检查目录:"):
                        m = re.search(r"(GY\d+)", line, re.IGNORECASE)
                        if m:
                            system_name = m.group(1).upper()
                        continue
                    # 形如：1. F:\template\gy2\K001-5.fits (1个问题, 1个错误)
                    m = re.match(r"\d+\.\s+(.+?\.fits)\b", line, re.IGNORECASE)
                    if not m:
                        continue
                    file_path = m.group(1)
                    base = os.path.basename(file_path)
                    m_k = re.search(r"(K\d{3})-(\d+)", base, re.IGNORECASE)
                    if not m_k:
                        continue
                    k_number = m_k.group(1).upper()
                    suffix = m_k.group(2)
                    k_full = f"{k_number}-{suffix}"
                    problems.append({
                        "path": file_path,
                        "k_number": k_number,
                        "suffix": suffix,
                        "k_full": k_full,
                    })
                    if not system_name:
                        m_sys = re.search(r"(GY\d+)", file_path, re.IGNORECASE)
                        if m_sys:
                            system_name = m_sys.group(1).upper()
        except Exception as e:
            self._log(f"解析fits_check_report失败: {e}")
        return system_name, problems

    def _find_recent_dates_for_region(self, index: dict, region: str, max_count: int):
        """在GY1索引中为指定天区寻找最近的若干日期（按日期字符串倒序）"""
        region_upper = str(region).upper()
        try:
            sorted_dates = sorted(index.keys(), reverse=True)
        except Exception:
            sorted_dates = list(index.keys())
            sorted_dates.sort(reverse=True)
        result = []
        for date in sorted_dates:
            regions = index.get(date) or []
            try:
                if region_upper in [str(r).upper() for r in regions]:
                    result.append(date)
                    if len(result) >= max_count:
                        break
            except Exception:
                continue
        return result

    def _template_update_status_after(self, text: str, color: str = "black"):
        """在线程中安全更新模板更新状态标签"""
        try:
            self.root.after(0, lambda: self.template_update_status.config(text=text, foreground=color))
        except Exception:
            pass

    def region_collect_status_after(self, text: str, color: str):
        try:
            self.root.after(0, lambda: self.region_collect_status.config(text=text, foreground=color))
        except Exception:
            pass

    # GY1 索引文件：多行紧凑JSON（日期 -> [天区列表]），存放于 gui/gy1_region_index.json
    # 要求：大括号单独一行，每个日期一行，按日期排序
    def _gy1_index_file(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "gy1_region_index.json")

    def _load_gy1_index(self) -> dict:
        try:
            path = self._gy1_index_file()
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            self._log(f"读取GY1索引文件失败，将使用空索引: {e}")
        return {}

    def _save_gy1_index(self, index: dict):
        """将GY1索引写入文件，格式例如：
        {
          "YYYYMMDD":["K001","K002"],
          "YYYYMMDE":[...]
        }
        大括号单独一行，日期行按key排序。
        """
        try:
            path = self._gy1_index_file()
            with open(path, "w", encoding="utf-8") as f:
                f.write("{\n")
                keys = sorted(index.keys())
                for i, k in enumerate(keys):
                    v = index[k]
                    line = "  " + json.dumps(str(k), ensure_ascii=False) + ":" + \
                        json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                    if i < len(keys) - 1:
                        line += ","
                    f.write(line + "\n")
                f.write("}")
        except Exception as e:
            self._log(f"写入GY1索引文件失败: {e}")



    def _on_toggle_auto_chain_oss_upload(self):
        """高级设置：切换自动链末尾OSS上传开关（立即保存到配置）"""
        try:
            enabled = bool(self.auto_chain_oss_upload_var.get())
            self.config_manager.update_automation_settings(enable_auto_chain_oss_upload=enabled)
            self._log(f"[设置] 自动链OSS上传: {'开启' if enabled else '关闭'}")
        except Exception as e:
            self._log(f"保存自动链OSS上传设置失败: {e}")


    def _on_toggle_auto_chain_use_local_query(self):
        """高级设置：切换自动链是否使用本地查询（立即保存到配置）"""
        try:
            enabled = bool(self.auto_chain_use_local_query_var.get())
            self.config_manager.update_local_catalog_settings(auto_chain_use_local_query=enabled)
            self._log(f"[设置] 自动链本地查询: {'开启' if enabled else '关闭'}")
        except Exception as e:
            self._log(f"保存自动链本地查询设置失败: {e}")
        # 同步H上限与星历状态
        try:
            settings_local = self.config_manager.get_local_catalog_settings()
        except Exception:
            settings_local = {}
        try:
            h_val = self.mpc_h_limit_var.get() if hasattr(self, 'mpc_h_limit_var') else str(settings_local.get('mpc_h_limit', 20))
            if hasattr(self, 'mpc_h_status_label'):
                self.mpc_h_status_label.config(text=f"当前H上限: {h_val}")
        except Exception:
            pass
        ephem_path = settings_local.get("ephemeris_file_path", "") or ""
        if hasattr(self, 'ephemeris_status_label'):
            ephem_name = Path(ephem_path).name if ephem_path else "未设置"
            self.ephemeris_status_label.config(text=f"星历: {ephem_name}")

    def _on_toggle_buttons_use_local_query(self):
        """高级设置：切换手动查询按钮是否使用本地查询（立即保存到配置）"""
        try:
            enabled = bool(self.buttons_use_local_query_var.get())
            self.config_manager.update_local_catalog_settings(buttons_use_local_query=enabled)
            self._log(f"[设置] 手动按钮本地查询: {'开启' if enabled else '关闭'}")
        except Exception as e:
            self._log(f"保存手动按钮本地查询设置失败: {e}")


    def _on_toggle_pympc_use_observatory(self):
        """高级设置：切换使用pympc时是否使用观测站代码（立即保存到配置）"""
        try:
            enabled = bool(self.pympc_use_observatory_var.get())
            self.config_manager.update_local_catalog_settings(pympc_use_observatory=enabled)
            self._log(f"[设置] pympc 使用观测站代码: {'开启' if enabled else '关闭'}")
        except Exception as e:
            self._log(f"保存 pympc 观测站代码设置失败: {e}")

    def _on_change_asteroid_query_method(self):
        """高级设置：切换小行星查询方式（立即保存到配置）"""
        try:
            method = str(self.asteroid_query_method_var.get() or "auto")
            self.config_manager.update_local_catalog_settings(asteroid_query_method=method)
            self._log(f"[设置] 小行星查询方式: {method}")
        except Exception as e:
            self._log(f"保存小行星查询方式失败: {e}")



    def _refresh_local_catalog_status_labels(self):
        """刷新本地库状态标签"""
        try:
            settings = self.config_manager.get_local_catalog_settings()
        except Exception:
            settings = {}
        ast_path = settings.get("asteroid_catalog_path", "") or ""
        vsx_path = settings.get("vsx_catalog_path", "") or ""
        ast_ts = settings.get("last_asteroid_update", "") or ""
        vsx_ts = settings.get("last_vsx_update", "") or ""
        pympc_path = settings.get("pympc_catalog_path", "") or ""
        pympc_ts = settings.get("last_pympc_update", "") or ""

        if hasattr(self, 'local_asteroid_status_label'):
            name = Path(ast_path).name if ast_path else "未设置"
            ts = ast_ts or "未知"
            self.local_asteroid_status_label.config(text=f"小行星库: {name} | 更新时间: {ts}")
        if hasattr(self, 'local_vsx_status_label'):
            name = Path(vsx_path).name if vsx_path else "未设置"
            ts = vsx_ts or "未知"
            self.local_vsx_status_label.config(text=f"变星库: {name} | 更新时间: {ts}")
        if hasattr(self, 'pympc_status_label'):
            name = Path(pympc_path).name if pympc_path else "默认目录"
            ts = pympc_ts or "未知"
            self.pympc_status_label.config(text=f"pympc目录: {name} | 更新时间: {ts}")

        ephem_path = settings.get("ephemeris_file_path", "") or ""
        if hasattr(self, 'ephemeris_status_label'):
            ephem_name = Path(ephem_path).name if ephem_path else "未设置"
            self.ephemeris_status_label.config(text=f"星历: {ephem_name}")
        if hasattr(self, 'mpc_h_status_label'):
            try:
                h_val = str(settings.get("mpc_h_limit", "")) or (self.mpc_h_limit_var.get() if hasattr(self, 'mpc_h_limit_var') else "20")
            except Exception:
                h_val = "20"
            self.mpc_h_status_label.config(text=f"当前H上限: {h_val}")

    def _update_local_asteroid_catalog(self):
        """选择/更新本地小行星库文件（本地CSV/TSV/自定义分隔文本）"""
        try:
            # 默认使用run_gui.py同级(gui)目录下的mpc_variables子目录
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            default_mpc_dir = os.path.join(gui_dir, 'mpc_variables')
            os.makedirs(default_mpc_dir, exist_ok=True)
            initialdir = self.download_dir_var.get() or default_mpc_dir
            file_path = filedialog.askopenfilename(
                title="选择本地小行星库文件",
                initialdir=initialdir,
                filetypes=[
                    ("MPCORB files", "*.dat *.DAT *.gz *.GZ"),
                    ("Catalog files", "*.csv *.tsv *.txt *.fits *.fit *.fts"),
                    ("All files", "*.*")
                ]
            )
            if not file_path:
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config_manager.update_local_catalog_settings(
                asteroid_catalog_path=file_path,
                last_asteroid_update=ts
            )
            self._refresh_local_catalog_status_labels()
            self._log(f"[设置] 已更新本地小行星库: {file_path}")
        except Exception as e:
            self._log(f"更新本地小行星库失败: {e}")


    def _update_pympc_catalogue(self):
        """使用 pympc.update_catalogue() 下载/更新 Minor Planet Center 轨道目录"""
        try:
            try:
                import pympc  # type: ignore
            except ImportError:
                messagebox.showerror("缺少依赖", "未安装 pympc 库，请先使用 pip install pympc 安装。")
                self._log("更新pympc轨道目录失败: 未安装 pympc")
                return

            self._log("开始更新 pympc Minor Planet Center 轨道目录...")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            xephem_cat = pympc.update_catalogue()
            cat_path = str(xephem_cat) if xephem_cat else ""
            self.config_manager.update_local_catalog_settings(
                pympc_catalog_path=cat_path,
                last_pympc_update=ts,
            )
            self._refresh_local_catalog_status_labels()
            self._log(f"[设置] 已更新pympc轨道目录: {cat_path or '未返回路径'}")
        except Exception as e:
            self._log(f"更新pympc轨道目录失败: {e}")

    def _save_mpc_h_limit(self):
        """保存MPC H上限到配置"""
        try:
            val_str = self.mpc_h_limit_var.get().strip()
            h_val = float(val_str)
            self.config_manager.update_local_catalog_settings(mpc_h_limit=h_val)
            if hasattr(self, 'mpc_h_status_label'):
                self.mpc_h_status_label.config(text=f"当前H上限: {val_str}")
            self._log(f"[设置] 已保存小行星H上限: {val_str}")
        except Exception as e:
            self._log(f"保存H上限失败: {e}")

    def _update_ephemeris_file(self):
        """选择/更新本地星历文件(.bsp)"""
        try:
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            default_dir = os.path.join(gui_dir, 'ephemeris')
            os.makedirs(default_dir, exist_ok=True)
            file_path = filedialog.askopenfilename(
                title="选择星历文件(.bsp)",
                initialdir=default_dir,
                filetypes=[("JPL Ephemeris", "*.bsp"), ("All files", "*.*")]
            )
            if not file_path:
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config_manager.update_local_catalog_settings(
                ephemeris_file_path=file_path,
                last_ephemeris_update=ts
            )
            self._refresh_local_catalog_status_labels()
            self._log(f"[设置] 已更新星历文件: {file_path}")
        except Exception as e:
            self._log(f"更新星历文件失败: {e}")

                # 出现异常时保持默认 False

    def _update_local_vsx_catalog(self):
        """选择/更新本地变星库文件（本地CSV/TSV/自定义分隔文本）"""
        try:
            # 默认使用run_gui.py同级(gui)目录下的mpc_variables子目录
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            default_vsx_dir = os.path.join(gui_dir, 'mpc_variables')
            os.makedirs(default_vsx_dir, exist_ok=True)
            initialdir = self.download_dir_var.get() or default_vsx_dir
            file_path = filedialog.askopenfilename(
                title="选择本地变星库文件",
                initialdir=initialdir,
                filetypes=[
                    ("Catalog files", "*.csv *.tsv *.txt *.fits *.fit *.fts"),
                    ("All files", "*.*")
                ]
            )
            if not file_path:
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config_manager.update_local_catalog_settings(
                vsx_catalog_path=file_path,
                last_vsx_update=ts
            )
            self._refresh_local_catalog_status_labels()
            self._log(f"[设置] 已更新本地变星库: {file_path}")
        except Exception as e:
            self._log(f"更新本地变星库失败: {e}")

    def _create_batch_status_widgets(self):

        """创建批量处理状态界面"""
        # 标题和说明
        title_frame = ttk.Frame(self.batch_status_frame)
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = ttk.Label(title_frame, text="批量处理状态", font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT)

        info_label = ttk.Label(title_frame, text="实时显示批量处理过程中每个文件的状态", foreground="gray")
        info_label.pack(side=tk.LEFT, padx=(20, 0))

        # 进度信息框架
        progress_frame = ttk.LabelFrame(self.batch_status_frame, text="处理进度", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 当前状态标签
        self.batch_progress_label = ttk.Label(progress_frame, text="等待开始批量处理...", font=("Arial", 10))
        self.batch_progress_label.pack(anchor=tk.W)

        # 统计信息标签
        self.batch_stats_label = ttk.Label(progress_frame, text="", foreground="blue")
        self.batch_stats_label.pack(anchor=tk.W, pady=(5, 0))

        # 批量处理状态显示组件
        status_frame = ttk.LabelFrame(self.batch_status_frame, text="文件状态列表", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.batch_status_widget = BatchStatusWidget(status_frame)
        self.batch_status_widget.create_widget()

        # 控制按钮
        control_frame = ttk.Frame(self.batch_status_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(control_frame, text="清空状态", command=self._clear_batch_status).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="显示统计", command=self._show_batch_statistics).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(control_frame, text="导出报告", command=self._export_batch_report).pack(side=tk.LEFT, padx=(10, 0))

    def _load_config(self):
        """加载配置"""
        try:
            # 加载下载设置
            download_settings = self.config_manager.get_download_settings()
            # 并发数锁定为1，不从配置加载
            self.max_workers_var.set(1)
            self.retry_times_var.set(download_settings.get("retry_times", 3))
            self.timeout_var.set(download_settings.get("timeout", 30))

            # 加载批量处理设置
            batch_settings = self.config_manager.get_batch_process_settings()
            # 这些设置将在url_builder中使用
            self._log(f"批量处理设置已加载: 线程数={batch_settings.get('thread_count', 4)}")

            # 加载下载目录和模板目录
            last_selected = self.config_manager.get_last_selected()
            download_dir = last_selected.get("download_directory", "")
            if download_dir:
                self.download_dir_var.set(download_dir)

            template_dir = last_selected.get("template_directory", "")
            if template_dir:
                self.template_dir_var.set(template_dir)

            diff_output_dir = last_selected.get("diff_output_directory", "")
            if diff_output_dir:
                self.diff_output_dir_var.set(diff_output_dir)

            detected_dir = last_selected.get("detected_directory", "")
            if detected_dir:
                self.detected_dir_var.set(detected_dir)

            unqueried_export_dir = last_selected.get("unqueried_export_directory", "")
            if unqueried_export_dir:
                self.unqueried_export_dir_var.set(unqueried_export_dir)
            elif diff_output_dir:
                # 如果没有设置detected目录，但有diff输出目录，自动设置为diff输出目录下的detected子目录
                detected_dir = os.path.join(diff_output_dir, "detected")
                self.detected_dir_var.set(detected_dir)

            # 加载AI训练数据导出根目录
            ai_export_root = last_selected.get("ai_training_export_root", "")
            if ai_export_root and hasattr(self, "ai_export_root_var"):
                self.ai_export_root_var.set(ai_export_root)

            # 加载自动链设置
            try:
                auto_settings = self.config_manager.get_automation_settings()
                self.auto_chain_oss_upload_var.set(bool(auto_settings.get("enable_auto_chain_oss_upload", False)))
            except Exception as _:
                # 出现异常时保持默认 False
                self.auto_chain_oss_upload_var.set(False)

            self._log("配置加载完成")

        except Exception as e:
            self._log(f"加载配置失败: {str(e)}")

    def _on_url_change(self, url):
        """URL变化事件处理"""
        self._log(f"URL已更新: {url}")
        # 可以在这里添加其他URL变化时的处理逻辑

    def _start_scan(self):
        """开始扫描"""
        # 获取当前构建的URL
        url = self.url_builder.get_current_url()

        # 验证URL
        if not url or url.startswith("请选择") or url.startswith("日期格式"):
            messagebox.showwarning("警告", "请先构建有效的URL")
            return

        # 验证选择
        valid, error_msg = self.url_builder.validate_current_selections()
        if not valid:
            messagebox.showerror("验证失败", error_msg)
            return

        # 禁用扫描按钮
        self.url_builder.set_scan_button_state("disabled")
        self.scan_status_label.config(text="正在扫描...")

        # 清空文件列表
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # 重置天区按钮状态
        self._reset_region_buttons()

        # 在新线程中执行扫描
        thread = threading.Thread(target=self._scan_thread, args=(url,))
        thread.daemon = True
        thread.start()

    def _scan_thread(self, url):
        """扫描线程"""
        try:
            self._log(f"开始扫描URL: {url}")

            # 尝试目录扫描器
            try:
                fits_files = self.directory_scanner.scan_directory_listing(url)
            except Exception as e:
                self._log(f"目录扫描失败，尝试通用扫描器: {str(e)}")
                fits_files = self.scanner.scan_fits_files(url)

            self.fits_files_list = fits_files

            # 更新界面
            self.root.after(0, self._update_file_list)
            self._log(f"扫描完成，找到 {len(fits_files)} 个FITS文件")

            # 如果找到文件，启用批量处理按钮
            if len(fits_files) > 0:
                self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))

        except Exception as e:
            error_msg = f"扫描失败: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用扫描按钮
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.scan_status_label.config(text="就绪"))

    def _update_file_list(self):
        """更新文件列表显示"""
        for filename, url, size in self.fits_files_list:
            size_str = self.scanner.format_file_size(size)
            item = self.file_tree.insert("", "end", text="☐", values=(filename, size_str, url))

        # 更新天区按钮
        self._update_region_buttons()

    def _update_region_buttons(self):
        """根据扫描结果更新天区按钮"""
        # 提取文件名中的K编号
        k_numbers = set()
        for filename, url, size in self.fits_files_list:
            # 从文件名中提取K编号，例如：K025-1, K036-2 等
            import re
            match = re.search(r'K(\d{3})-(\d)', filename)
            if match:
                k_base = match.group(1)  # 例如：025
                region_idx = int(match.group(2))  # 例如：1
                k_numbers.add((region_idx, f"K{k_base}-{region_idx}"))

        # 更新按钮状态和文字
        for i, btn in enumerate(self.region_buttons):
            region_index = i + 1  # 1-9
            # 查找对应的K编号
            k_text = None
            for idx, k_name in k_numbers:
                if idx == region_index:
                    k_text = k_name
                    break

            if k_text:
                # 更新按钮文字和状态
                btn.config(text=k_text, state="normal")
                # 初始化按钮选中状态
                if k_text not in self.region_button_states:
                    self.region_button_states[k_text] = False
                # 更新按钮外观
                self._update_button_appearance(btn, k_text)
            else:
                btn.config(text=f"天区-{region_index}", state="disabled")
                # 清除禁用按钮的状态
                old_text = btn.cget("text")
                if old_text in self.region_button_states:
                    del self.region_button_states[old_text]

    def _reset_region_buttons(self):
        """重置天区按钮状态"""
        # 清空选中状态
        self.region_button_states.clear()

        for i, btn in enumerate(self.region_buttons):
            region_index = i + 1
            btn.config(text=f"天区-{region_index}", state="disabled")

    def _update_button_appearance(self, btn, k_text):
        """更新按钮外观以显示选中状态"""
        is_selected = self.region_button_states.get(k_text, False)
        if is_selected:
            # 选中状态：添加复选标记
            btn.config(text=f"☑ {k_text}")
        else:
            # 未选中状态：显示空复选框
            btn.config(text=f"☐ {k_text}")

    def _on_tree_click(self, event):
        """处理树形控件点击事件"""
        region = self.file_tree.identify_region(event.x, event.y)
        if region == "tree":
            item = self.file_tree.identify_row(event.y)
            if item:
                # 切换选择状态
                current_text = self.file_tree.item(item, "text")
                new_text = "☑" if current_text == "☐" else "☐"
                self.file_tree.item(item, text=new_text)

    def _select_all(self):
        """全选"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, text="☑")

    def _deselect_all(self):
        """全不选"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, text="☐")

    def _invert_selection(self):
        """反选"""
        for item in self.file_tree.get_children():
            current_text = self.file_tree.item(item, "text")
            new_text = "☑" if current_text == "☐" else "☐"
            self.file_tree.item(item, text=new_text)

    def _select_by_region(self, region_index):
        """按天区索引选择文件（复选框样式）"""
        # 获取对应按钮
        btn = self.region_buttons[region_index - 1]

        # 如果按钮被禁用，不执行选择
        if btn.cget("state") == "disabled":
            return

        # 从按钮文字中提取K编号（去掉复选框符号）
        btn_text = btn.cget("text")
        if btn_text.startswith("☑ "):
            k_text = btn_text[2:]  # 去掉"☑ "
        elif btn_text.startswith("☐ "):
            k_text = btn_text[2:]  # 去掉"☐ "
        else:
            k_text = btn_text  # 兼容没有复选框符号的情况

        # 切换按钮选中状态
        current_state = self.region_button_states.get(k_text, False)
        new_state = not current_state
        self.region_button_states[k_text] = new_state

        # 更新按钮外观
        self._update_button_appearance(btn, k_text)

        # 根据新状态选择或取消选择对应文件
        selected_count = 0
        deselected_count = 0
        selected_files = []  # 存储选中的文件信息

        for item in self.file_tree.get_children():
            values = self.file_tree.item(item, "values")
            filename = values[0]  # 文件名在第一列

            if k_text in filename:
                if new_state:
                    # 选中状态：选择文件
                    self.file_tree.item(item, text="☑")
                    selected_count += 1
                    selected_files.append(filename)
                else:
                    # 未选中状态：取消选择文件
                    self.file_tree.item(item, text="☐")
                    deselected_count += 1

        # 记录日志
        if new_state:
            self._log(f"已选择包含 '{k_text}' 的文件，共 {selected_count} 个")
            # 输出cp命令
            self._output_cp_commands(selected_files, k_text)
        else:
            self._log(f"已取消选择包含 '{k_text}' 的文件，共 {deselected_count} 个")

    def _output_cp_commands(self, selected_files, k_text):
        """输出选中文件的cp命令"""
        if not selected_files:
            return

        # 获取当前选择的参数
        selections = self.url_builder.get_current_selections()
        telescope_name = selections.get('telescope_name', 'Unknown')  # 例如：GY1
        date_str = selections.get('date', 'Unknown')  # 例如：20250922

        # 从k_text中提取天区前缀，例如从"K025-1"提取"K025"
        import re
        match = re.search(r'(K\d{3})', k_text)
        sky_region_prefix = match.group(1) if match else k_text

        # 转换系统名称为小写
        system_name = telescope_name.lower()

        self._log("=" * 50)
        self._log(f"选中天区 {k_text} 的文件cp命令:")

        # 构建服务调试路径（只需要构建一次）
        serv_debug_path = f'/data/{system_name}/20251332/{sky_region_prefix}/'

        # 输出创建目录命令
        mkdir_command = f'mkdir -p {serv_debug_path}'
        self._log_plain(mkdir_command)

        for filename in selected_files:
            # URL解码文件名，去除%20等编码字符
            import urllib.parse
            decoded_filename = urllib.parse.unquote(filename)

            # 构建原始文件路径
            original_file_path = f'/data/{system_name}/{date_str}/{sky_region_prefix}/{decoded_filename}'

            # 生成cp命令
            cp_command = f'cp "{original_file_path}" {serv_debug_path}'

            # 使用不带时间前缀的日志输出cp命令
            self._log_plain(cp_command)

        self._log("=" * 50)

        # 另一种调试
        for filename in selected_files:
            # URL解码文件名，去除%20等编码字符
            import urllib.parse
            decoded_filename = urllib.parse.unquote(filename)
            decoded_filename_no_ext = decoded_filename.replace(".fit", "").replace("_No Filter_", "_C_")

            # 构建原始文件路径
            original_file_path = f'/data/{system_name}/20251332/{sky_region_prefix}/{decoded_filename}'
            fix_cat_path = f'/data/{system_name}/20251332/{sky_region_prefix}/redux/{decoded_filename_no_ext}_pp.diff1.fixedsrc.cat'
            mo_cat_path = f'/data/{system_name}/20251332/{sky_region_prefix}/redux/{decoded_filename_no_ext}_pp.diff1.mo.cat'

            # 生成autoredux命令
            redux_command = f'python autoredux_pool_server.py  "{original_file_path}" "{system_name}"'
            self._log_plain(redux_command)
            self._log_plain(" ")
            self._log_plain("cd redux")
            self._log_plain(" ")

            find_fix_command = f'timeout 1800 python find_fixedsrc.py "{fix_cat_path}" '
            self._log_plain(find_fix_command)
            self._log_plain(" ")
            find_mo_command = f'timeout 1800 python find_mo.py "{mo_cat_path}" '
            self._log_plain(find_mo_command)
            self._log_plain(" ")
        mpc80file_debug = f'/data/{system_name}/20251332/{sky_region_prefix}/redux/{k_text}_mpc.80'
        astcheck_command = f'timeout 1800 python astid.py "{mpc80file_debug}"'
        self._log_plain(astcheck_command)
        self._log_plain(" ")
        self._log("=" * 50)

        for filename in selected_files:
            # URL解码文件名，去除%20等编码字符
            import urllib.parse
            decoded_filename = urllib.parse.unquote(filename)
            decoded_filename_no_ext = decoded_filename.replace(".fit", "").replace("_No Filter_", "_C_")

            # 构建原始文件路径
            original_file_path = f'/data/{system_name}/{date_str}/{sky_region_prefix}/{decoded_filename}'
            fix_cat_path = f'/data/{system_name}/{date_str}/{sky_region_prefix}/redux/{decoded_filename_no_ext}_pp.diff1.fixedsrc.cat'
            mo_cat_path = f'/data/{system_name}/{date_str}/{sky_region_prefix}/redux/{decoded_filename_no_ext}_pp.diff1.mo.cat'

            # 生成autoredux命令
            redux_command = f'python autoredux_pool_server.py  "{original_file_path}" "{system_name}"'
            self._log_plain(redux_command)
            self._log_plain(" ")
            self._log_plain("cd redux")
            self._log_plain(" ")

            find_fix_command = f'timeout 1800 python find_fixedsrc.py "{fix_cat_path}" '
            self._log_plain(find_fix_command)
            self._log_plain(" ")
            find_mo_command = f'timeout 1800 python find_mo.py "{mo_cat_path}" '
            self._log_plain(find_mo_command)
            self._log_plain(" ")
        mpc80file = f'/data/{system_name}/{date_str}/{sky_region_prefix}/redux/{k_text}_mpc.80'
        astcheck_command = f'timeout 1800 python astid.py "{mpc80file}"'
        self._log_plain(astcheck_command)
        self._log_plain(" ")
        self._log("=" * 50)

    def _select_download_dir(self):
        """选择下载根目录"""
        # 获取当前目录作为初始目录
        current_dir = self.download_dir_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择下载根目录", initialdir=initial_dir)
        if directory:
            self.download_dir_var.set(directory)
            # 保存到配置
            self.config_manager.update_last_selected(download_directory=directory)
            self._log(f"下载根目录已设置: {directory}")
            self._log(f"文件将保存到: {directory}/望远镜名/日期/天区/")

    def _select_template_dir(self):
        """选择模板文件目录"""
        # 获取当前目录作为初始目录
        current_dir = self.template_dir_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择模板文件目录", initialdir=initial_dir)
        if directory:
            self.template_dir_var.set(directory)
            # 保存到配置
            self.config_manager.update_last_selected(template_directory=directory)
            self._log(f"模板文件目录已设置: {directory}")
            # 刷新FITS查看器的目录树
            if hasattr(self, 'fits_viewer'):
                self.fits_viewer._refresh_directory_tree()

    def _select_diff_output_dir(self):
        """选择diff输出根目录"""
        # 获取当前目录作为初始目录
        current_dir = self.diff_output_dir_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择diff输出根目录", initialdir=initial_dir)
        if directory:
            self.diff_output_dir_var.set(directory)
            # 保存到配置
            self.config_manager.update_last_selected(diff_output_directory=directory)
            self._log(f"diff输出根目录已设置: {directory}")
            self._log(f"diff结果将保存到: {directory}/系统名/日期/天区/文件名/")

            # 自动设置detected目录为diff输出根目录下的detected子目录
            detected_dir = os.path.join(directory, "detected")
            self.detected_dir_var.set(detected_dir)
            self.config_manager.update_last_selected(detected_directory=detected_dir)
            self._log(f"detected保存目录已自动设置: {detected_dir}")

    def _select_detected_dir(self):
        """选择detected保存目录"""
        # 获取当前目录作为初始目录
        current_dir = self.detected_dir_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择detected保存目录", initialdir=initial_dir)
        if directory:
            self.detected_dir_var.set(directory)
            # 保存到配置
            self.config_manager.update_last_selected(detected_directory=directory)
            self._log(f"detected保存目录已设置: {directory}")
            self._log(f"检测结果将保存到: {directory}/YYYYMMDD/saved_HHMMSS_NNN/")

    def _select_unqueried_export_dir(self):
        """选择未查询导出目录（也用于OSS上传）"""
        # 获取当前目录作为初始目录
        current_dir = self.unqueried_export_dir_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择未查询导出目录", initialdir=initial_dir)
        if directory:
            self.unqueried_export_dir_var.set(directory)
            # 保存到配置
            self.config_manager.update_last_selected(unqueried_export_directory=directory)
            self._log(f"未查询导出目录已设置: {directory}")
            self._log(f"未查询检测结果将导出到: {directory}/系统名/日期/天区/文件名/detection_xxx/")
            self._log(f"此目录也将用于OSS上传")

    def _select_ai_training_export_root(self):
        """选择AI训练数据导出根目录"""
        # 获取当前目录作为初始目录
        current_dir = self.ai_export_root_var.get()
        initial_dir = current_dir if current_dir and os.path.exists(current_dir) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title="选择AI训练导出根目录", initialdir=initial_dir)
        if directory:
            self.ai_export_root_var.set(directory)
            if self.config_manager:
                # 保存到配置的 last_selected 中
                self.config_manager.update_last_selected(ai_training_export_root=directory)
            self._log(f"AI训练导出根目录已设置: {directory}")
            self._log("导出AI训练数据时，GOOD/BAD 图像将分别保存到该目录下的子目录中。")



    def _get_selected_files(self):
        """获取选中的文件"""
        selected_files = []
        for item in self.file_tree.get_children():
            if self.file_tree.item(item, "text") == "☑":
                values = self.file_tree.item(item, "values")
                filename, size_str, url = values
                selected_files.append((filename, url))
        return selected_files

    def _start_download(self):
        """开始下载"""
        selected_files = self._get_selected_files()
        if not selected_files:
            messagebox.showwarning("警告", "请选择要下载的文件")
            return

        base_download_dir = self.download_dir_var.get().strip()
        if not base_download_dir:
            messagebox.showwarning("警告", "请选择下载根目录")
            return

        # 获取当前选择的参数来构建子目录
        selections = self.url_builder.get_current_selections()
        tel_name = selections.get('telescope_name', 'Unknown')
        date = selections.get('date', 'Unknown')
        k_number = selections.get('k_number', 'Unknown')

        # 构建实际下载目录：根目录/tel_name/YYYYMMDD/K0??
        actual_download_dir = os.path.join(base_download_dir, tel_name, date, k_number)

        # 创建下载目录
        os.makedirs(actual_download_dir, exist_ok=True)

        self._log(f"下载根目录: {base_download_dir}")
        self._log(f"实际下载目录: {actual_download_dir}")
        self._log(f"目录结构: {tel_name}/{date}/{k_number}")

        # 禁用下载按钮
        self.download_button.config(state="disabled")
        self.status_label.config(text="正在下载...")

        # 保存下载设置到配置
        self.config_manager.update_download_settings(
            max_workers=self.max_workers_var.get(),
            retry_times=self.retry_times_var.get(),
            timeout=self.timeout_var.get()
        )

        # 重置进度条
        self.progress_var.set(0)
        self.progress_bar.config(maximum=len(selected_files))

        # 在新线程中执行下载
        thread = threading.Thread(target=self._download_thread, args=(selected_files, actual_download_dir))
        thread.daemon = True
        thread.start()

    def _download_thread(self, selected_files, download_dir):
        """下载线程"""
        try:
            # 创建下载器
            self.downloader = FitsDownloader(
                max_workers=self.max_workers_var.get(),
                retry_times=self.retry_times_var.get(),
                timeout=self.timeout_var.get(),
                enable_astap=self.enable_astap_var.get(),
                astap_config_path="config/url_config.json"
            )

            # 准备URL列表
            urls = [url for filename, url in selected_files]

            self._log(f"开始下载 {len(urls)} 个文件到目录: {download_dir}")

            # 执行下载（这里需要修改原始下载器以支持进度回调）
            self._download_with_progress(urls, download_dir)

            self._log("下载完成！")
            # 不显示弹出提示框，只在日志中记录

        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用下载按钮
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            self.root.after(0, lambda: self.status_label.config(text="下载完成"))

    def _download_with_progress(self, urls, download_dir):
        """带进度显示的下载"""
        completed = 0
        total_files = len(urls)

        for i, url in enumerate(urls):
            try:
                # 创建进度回调函数
                def progress_callback(downloaded_bytes, total_bytes, filename):
                    # 计算当前文件的进度
                    if total_bytes:
                        file_progress = (downloaded_bytes / total_bytes) * 100
                        # 计算总体进度：已完成文件 + 当前文件进度
                        overall_progress = (i + downloaded_bytes / total_bytes) / total_files * 100
                    else:
                        file_progress = 0
                        overall_progress = i / total_files * 100

                    # 更新界面（在主线程中执行）
                    self.root.after(0, lambda: self._update_download_progress(
                        overall_progress, i + 1, total_files, filename, file_progress, downloaded_bytes, total_bytes
                    ))

                result = self.downloader.download_single_file(url, download_dir, progress_callback)
                completed += 1

                # 文件下载完成后的最终更新
                final_progress = (i + 1) / total_files * 100
                self.root.after(0, lambda p=final_progress: self.progress_var.set(p))
                self.root.after(0, lambda c=completed, t=total_files:
                               self.status_label.config(text=f"已完成: {c}/{t}"))

                self._log(f"[{i+1}/{total_files}] {result}")

            except Exception as e:
                self._log(f"下载失败 {url}: {str(e)}")

    def _update_download_progress(self, overall_progress, current_file, total_files, filename, file_progress, downloaded_bytes, total_bytes):
        """更新下载进度显示"""
        # 更新进度条
        self.progress_var.set(overall_progress)

        # 格式化文件大小
        def format_bytes(bytes_val):
            if bytes_val is None:
                return "未知"
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f}{unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f}TB"

        # 更新状态标签
        if total_bytes:
            status_text = f"[{current_file}/{total_files}] {filename} - {file_progress:.1f}% ({format_bytes(downloaded_bytes)}/{format_bytes(total_bytes)})"
        else:
            status_text = f"[{current_file}/{total_files}] {filename} - {format_bytes(downloaded_bytes)}"

        self.status_label.config(text=status_text)

    def _select_fits_file(self):
        """选择FITS文件进行查看"""
        file_path = filedialog.askopenfilename(
            title="选择FITS文件",
            filetypes=[
                ("FITS files", "*.fits *.fit *.fts"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.fits_viewer.load_fits_file(file_path)

    def _select_from_download_dir(self):
        """从下载目录选择FITS文件"""
        base_download_dir = self.download_dir_var.get().strip()
        if not base_download_dir or not os.path.exists(base_download_dir):
            # 如果没有设置下载目录，提示用户设置
            if messagebox.askyesno("设置下载根目录", "还没有设置下载根目录，是否现在设置？"):
                self._select_download_dir()
                base_download_dir = self.download_dir_var.get().strip()
                if not base_download_dir:
                    return
            else:
                return

        # 获取当前选择的参数来构建搜索路径
        selections = self.url_builder.get_current_selections()
        tel_name = selections.get('telescope_name', '')
        date = selections.get('date', '')
        k_number = selections.get('k_number', '')

        # 构建可能的搜索路径
        search_paths = []

        # 1. 优先搜索当前选择对应的目录
        if tel_name and date and k_number:
            current_path = os.path.join(base_download_dir, tel_name, date, k_number)
            if os.path.exists(current_path):
                search_paths.append(("当前选择", current_path))

        # 2. 搜索同一望远镜的其他日期/天区
        if tel_name:
            tel_path = os.path.join(base_download_dir, tel_name)
            if os.path.exists(tel_path):
                for date_dir in os.listdir(tel_path):
                    date_path = os.path.join(tel_path, date_dir)
                    if os.path.isdir(date_path):
                        for k_dir in os.listdir(date_path):
                            k_path = os.path.join(date_path, k_dir)
                            if os.path.isdir(k_path):
                                search_paths.append((f"{tel_name}/{date_dir}/{k_dir}", k_path))

        # 3. 搜索所有望远镜目录
        if os.path.exists(base_download_dir):
            for tel_dir in os.listdir(base_download_dir):
                tel_path = os.path.join(base_download_dir, tel_dir)
                if os.path.isdir(tel_path) and tel_dir != tel_name:  # 避免重复
                    for date_dir in os.listdir(tel_path):
                        date_path = os.path.join(tel_path, date_dir)
                        if os.path.isdir(date_path):
                            for k_dir in os.listdir(date_path):
                                k_path = os.path.join(date_path, k_dir)
                                if os.path.isdir(k_path):
                                    search_paths.append((f"{tel_dir}/{date_dir}/{k_dir}", k_path))

        # 查找FITS文件
        all_fits_files = []
        for path_desc, search_path in search_paths:
            for ext in ['*.fits', '*.fit', '*.fts']:
                fits_files = list(Path(search_path).glob(ext))
                for fits_file in fits_files:
                    all_fits_files.append((path_desc, fits_file))

        if not all_fits_files:
            # 如果没有找到FITS文件，询问是否从其他位置选择
            if messagebox.askyesno("没有找到文件",
                                 f"在下载根目录 {base_download_dir} 中没有找到FITS文件，\n是否从其他位置选择？"):
                self._select_fits_file()
            return

        # 按修改时间排序，最新的在前面
        all_fits_files.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)

        # 创建文件选择对话框
        file_info = [(f"{path_desc}: {fits_file.name}", str(fits_file)) for path_desc, fits_file in all_fits_files]
        selected = self._show_fits_file_selection_dialog(file_info, "选择FITS文件 (按修改时间排序)")

        if selected:
            if self.fits_viewer.load_fits_file(selected):
                self._log(f"已加载FITS文件: {os.path.basename(selected)}")
                self._log(f"文件路径: {selected}")
            else:
                self._log(f"加载FITS文件失败: {selected}")

    def _show_file_selection_dialog(self, file_names, title="选择FITS文件"):
        """显示文件选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # 文件列表
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for name in file_names:
            listbox.insert(tk.END, name)

        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        selected_file = [None]

        def on_ok():
            selection = listbox.curselection()
            if selection:
                selected_file[0] = file_names[selection[0]]
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.RIGHT)

        # 双击选择
        listbox.bind('<Double-Button-1>', lambda e: on_ok())

        dialog.wait_window()
        return selected_file[0]

    def _show_fits_file_selection_dialog(self, file_info_list, title="选择FITS文件"):
        """显示FITS文件选择对话框，支持显示路径信息"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # 文件列表框架
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建Treeview显示文件信息
        columns = ("file", "path")
        tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        # 设置列标题
        tree.heading("#0", text="")
        tree.heading("file", text="文件信息")
        tree.heading("path", text="完整路径")

        # 设置列宽
        tree.column("#0", width=30)
        tree.column("file", width=350)
        tree.column("path", width=300)

        # 添加滚动条
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 填充文件信息
        for i, (file_desc, file_path) in enumerate(file_info_list):
            tree.insert("", "end", text=str(i+1), values=(file_desc, file_path))

        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        selected_file = [None]

        def on_ok():
            selection = tree.selection()
            if selection:
                item = selection[0]
                values = tree.item(item, "values")
                selected_file[0] = values[1]  # 返回完整路径
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        def on_double_click(event):
            on_ok()

        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.RIGHT)

        # 绑定双击事件
        tree.bind('<Double-Button-1>', on_double_click)

        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        dialog.wait_window()
        return selected_file[0]

    def _log(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # 在主线程中更新日志显示
        self.root.after(0, lambda: self._append_log(log_message))

        # 同时输出到控制台
        print(log_message.strip())

    def _log_plain(self, message):
        """添加不带时间前缀的日志消息"""
        log_message = f"{message}\n"

        # 在主线程中更新日志显示
        self.root.after(0, lambda: self._append_log(log_message))

        # 同时输出到控制台
        print(message)

    def _append_log(self, message, level="INFO"):
        """
        在日志文本框中添加消息

        Args:
            message (str): 日志消息
            level (str): 日志级别 (ERROR, WARNING, INFO, DEBUG)
        """
        # 添加时间戳
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"

        # 插入消息并应用颜色标签
        start_index = self.log_text.index(tk.END)
        self.log_text.insert(tk.END, full_message)

        # 应用颜色标签到整行
        end_index = self.log_text.index(tk.END)
        self.log_text.tag_add(level, start_index, end_index)

        # 滚动到底部
        self.log_text.see(tk.END)

    def _clear_log(self):
        """清除日志"""
        self.log_text.delete(1.0, tk.END)

    def _save_log(self):
        """保存日志"""
        file_path = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("成功", f"日志已保存到:\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败:\n{str(e)}")

    def _clear_batch_status(self):
        """清空批量处理状态"""
        self.batch_status_widget.clear()
        self.batch_progress_label.config(text="等待开始批量处理...")
        self.batch_stats_label.config(text="")
        self._log("批量处理状态已清空")

    def _show_batch_statistics(self):
        """显示批量处理统计信息"""
        stats = self.batch_status_widget.get_statistics()

        stats_text = f"""批量处理统计信息

总文件数: {stats['total']}

下载统计:
  - 下载成功: {stats['download_success']}
  - 下载失败: {stats['download_failed']}
  - 跳过下载: {stats['download_skipped']}

WCS统计:
  - 有WCS: {stats['wcs_found']}
  - 缺WCS: {stats['wcs_missing']}

ASTAP统计:
  - ASTAP成功: {stats['astap_success']}
  - ASTAP失败: {stats['astap_failed']}

Diff统计:
  - Diff成功: {stats['diff_success']}
  - Diff失败: {stats['diff_failed']}
  - 跳过Diff: {stats['diff_skipped']}
"""

        messagebox.showinfo("批量处理统计", stats_text)
        self._log("显示批量处理统计信息")

    def _export_batch_report(self):
        """导出批量处理报告"""
        stats = self.batch_status_widget.get_statistics()

        if stats['total'] == 0:
            messagebox.showwarning("警告", "没有可导出的批量处理数据")
            return

        file_path = filedialog.asksaveasfilename(
            title="导出批量处理报告",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("批量处理报告\n")
                    f.write("=" * 60 + "\n\n")

                    f.write(f"总文件数: {stats['total']}\n\n")

                    f.write("下载统计:\n")
                    f.write(f"  - 下载成功: {stats['download_success']}\n")
                    f.write(f"  - 下载失败: {stats['download_failed']}\n")
                    f.write(f"  - 跳过下载: {stats['download_skipped']}\n\n")

                    f.write("WCS统计:\n")
                    f.write(f"  - 有WCS: {stats['wcs_found']}\n")
                    f.write(f"  - 缺WCS: {stats['wcs_missing']}\n\n")

                    f.write("ASTAP统计:\n")
                    f.write(f"  - ASTAP成功: {stats['astap_success']}\n")
                    f.write(f"  - ASTAP失败: {stats['astap_failed']}\n\n")

                    f.write("Diff统计:\n")
                    f.write(f"  - Diff成功: {stats['diff_success']}\n")
                    f.write(f"  - Diff失败: {stats['diff_failed']}\n")
                    f.write(f"  - 跳过Diff: {stats['diff_skipped']}\n\n")

                    f.write("=" * 60 + "\n")
                    f.write("文件详细状态:\n")
                    f.write("=" * 60 + "\n\n")

                    # 获取所有文件状态
                    for filename in self.batch_status_widget.file_labels.keys():
                        status_info = self.batch_status_widget.get_status(filename)
                        if status_info:
                            status_text = status_info.get('text', '')
                            extra_info = status_info.get('extra_info', '')
                            f.write(f"{filename}\n")
                            f.write(f"  状态: {status_text}")
                            if extra_info:
                                f.write(f" - {extra_info}")
                            f.write("\n\n")

                messagebox.showinfo("成功", f"批量处理报告已导出到:\n{file_path}")
                self._log(f"批量处理报告已导出: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出报告失败:\n{str(e)}")
                self._log(f"导出报告失败: {str(e)}", "ERROR")

    def get_error_logger_callback(self):
        """
        获取错误日志记录器的GUI回调函数

        Returns:
            Callable: 回调函数，接受(message, level)参数
        """
        def callback(message, level="INFO"):
            """
            错误日志回调函数

            Args:
                message (str): 日志消息
                level (str): 日志级别 (ERROR, WARNING, INFO, DEBUG)
            """
            # 在主线程中更新日志显示
            self.root.after(0, lambda: self._append_log(message, level))

        return callback

    def run(self):
        """运行GUI应用程序"""
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _get_download_dir(self):
        """获取下载根目录的回调函数"""
        return self.download_dir_var.get().strip()

    def _get_template_dir(self):
        """获取模板文件目录的回调函数"""
        return self.template_dir_var.get().strip()

    def _get_diff_output_dir(self):
        """获取diff输出根目录的回调函数"""
        return self.diff_output_dir_var.get().strip()

    def _get_unqueried_export_dir(self):
        """获取未查询导出目录的回调函数（也用于OSS上传）"""
        return self.unqueried_export_dir_var.get().strip()

    def _open_batch_output_directory(self):
        """打开批量处理的输出根目录"""
        if not self.last_batch_output_root or not os.path.exists(self.last_batch_output_root):
            messagebox.showwarning("警告", "没有可用的批量输出目录")
            return

        try:
            import subprocess
            import platform

            if platform.system() == 'Windows':
                os.startfile(self.last_batch_output_root)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', self.last_batch_output_root])
            else:  # Linux
                subprocess.run(['xdg-open', self.last_batch_output_root])

            self._log(f"已打开批量输出目录: {self.last_batch_output_root}")
        except Exception as e:
            self._log(f"打开批量输出目录失败: {str(e)}")
            messagebox.showerror("错误", f"打开目录失败: {str(e)}")

    def _get_thread_safe_diff_output_directory(self, file_path: str) -> str:
        """
        线程安全地获取diff操作的输出目录

        Args:
            file_path: FITS文件路径

        Returns:
            str: 输出目录路径
        """
        from datetime import datetime
        import re

        # 获取配置的根目录
        base_output_dir = ""
        if self.fits_viewer.get_diff_output_dir_callback:
            base_output_dir = self.fits_viewer.get_diff_output_dir_callback()

        # 如果没有配置，使用下载文件所在目录
        if not base_output_dir or not os.path.exists(base_output_dir):
            base_output_dir = os.path.dirname(file_path)

        # 尝试从文件名、文件路径解析系统名、日期、天区信息
        system_name = "Unknown"
        date_str = datetime.now().strftime("%Y%m%d")
        sky_region = "Unknown"

        # 从文件名解析
        try:
            filename = os.path.basename(file_path)
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
        except Exception as e:
            self._log(f"从文件名解析信息失败: {e}")

        # 从文件路径解析（如果文件名未获取完整信息）
        if system_name == "Unknown" or sky_region == "Unknown":
            try:
                # 文件路径格式: .../系统名/日期/天区/文件名
                path_parts = file_path.replace('\\', '/').split('/')

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
            except Exception as e:
                self._log(f"从文件路径解析信息失败: {e}")

        # 从选中文件名生成子目录名（不带时间戳，避免重复执行）
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]
        subdir_name = name_without_ext

        # 构建完整输出目录：根目录/系统名/日期/天区/文件名/
        output_dir = os.path.join(base_output_dir, system_name, date_str, sky_region, subdir_name)

        # 创建目录
        os.makedirs(output_dir, exist_ok=True)

        return output_dir

    def _process_single_diff(self, download_file, template_dir, noise_methods, alignment_method,
                            remove_bright_lines, stretch_method, percentile_low, fast_mode, sort_by='aligned_snr'):
        """
        处理单个文件的diff操作（线程安全）

        Returns:
            dict: 包含处理结果的字典 {'success': bool, 'filename': str, 'message': str, 'new_spots': int}
        """
        filename = os.path.basename(download_file)
        result_dict = {
            'success': False,
            'filename': filename,
            'message': '',
            'new_spots': 0
        }

        try:
            # 查找模板文件
            template_file = self.fits_viewer.diff_orb.find_template_file(download_file, template_dir)

            if not template_file:
                result_dict['message'] = "未找到模板"
                return result_dict

            # 线程安全：直接生成输出目录，不依赖共享的selected_file_path
            output_dir = self._get_thread_safe_diff_output_directory(download_file)

            # 检查是否已存在结果
            if os.path.exists(output_dir):
                detection_dirs = [d for d in os.listdir(output_dir)
                                if d.startswith('detection_') and os.path.isdir(os.path.join(output_dir, d))]
                if detection_dirs:
                    result_dict['success'] = True
                    result_dict['message'] = "已有结果"
                    result_dict['skipped'] = True
                    return result_dict

            # 执行diff操作
            diff_result = self.fits_viewer.diff_orb.process_diff(
                download_file,
                template_file,
                output_dir,
                noise_methods=noise_methods,
                alignment_method=alignment_method,
                remove_bright_lines=remove_bright_lines,
                stretch_method=stretch_method,
                percentile_low=percentile_low,
                fast_mode=fast_mode,
                sort_by=sort_by
            )

            if diff_result and diff_result.get('success'):
                result_dict['success'] = True
                result_dict['new_spots'] = diff_result.get('new_bright_spots', 0)
                result_dict['message'] = f"{result_dict['new_spots']}个亮点"
            else:
                result_dict['message'] = "处理失败"

        except Exception as e:
            result_dict['message'] = str(e)

        return result_dict

    def _process_single_astap(self, file_path):
        """
        处理单个文件的ASTAP操作（线程安全）

        Returns:
            dict: 包含处理结果的字典 {'success': bool, 'filename': str, 'message': str}
        """
        filename = os.path.basename(file_path)
        result_dict = {
            'success': False,
            'filename': filename,
            'message': ''
        }

        try:
            # 检查ASTAP处理器是否可用
            if not self.fits_viewer or not self.fits_viewer.astap_processor:
                result_dict['message'] = "ASTAP处理器不可用"
                return result_dict

            # 检查文件是否存在
            if not os.path.exists(file_path):
                result_dict['message'] = "文件不存在"
                return result_dict

            # 执行ASTAP处理
            astap_success = self.fits_viewer.astap_processor.process_fits_file(file_path)

            if astap_success:
                result_dict['success'] = True
                result_dict['message'] = "ASTAP处理成功"
            else:
                result_dict['message'] = "ASTAP处理失败"

        except Exception as e:
            result_dict['message'] = str(e)

        return result_dict

    def _pause_batch_process(self):
        """暂停/继续批量处理"""
        if self.batch_paused:
            # 当前是暂停状态，点击后继续
            self.batch_paused = False
            self.batch_pause_event.set()  # 释放暂停
            self.url_builder.set_pause_batch_button_text("⏸ 暂停")
            self._log("批量处理已继续")
            self.status_label.config(text="批量处理继续中...")
        else:
            # 当前是运行状态，点击后暂停
            self.batch_paused = True
            self.batch_pause_event.clear()  # 设置暂停
            self.url_builder.set_pause_batch_button_text("▶ 继续")
            self._log("批量处理已暂停")
            self.status_label.config(text="批量处理已暂停")

    def _stop_batch_process(self):
        """停止批量处理"""
        if messagebox.askyesno("确认", "确定要停止批量处理吗？\n已处理的文件不会回滚。"):
            self.batch_stopped = True
            self.batch_paused = False
            self.batch_pause_event.set()  # 如果正在暂停，先释放以便线程能检测到停止标志
            self._log("正在停止批量处理...")
            self.status_label.config(text="正在停止批量处理...")

    def _batch_process(self):
        """批量下载并执行diff操作"""
        selected_files = self._get_selected_files()
        if not selected_files:
            messagebox.showwarning("警告", "请选择要处理的文件")
            return

        # 检查必要的目录配置
        base_download_dir = self.download_dir_var.get().strip()
        template_dir = self.template_dir_var.get().strip()
        diff_output_dir = self.diff_output_dir_var.get().strip()

        if not base_download_dir:
            messagebox.showwarning("警告", "请配置下载根目录")
            return

        if not template_dir:
            messagebox.showwarning("警告", "请配置模板文件目录")
            return

        if not diff_output_dir:
            messagebox.showwarning("警告", "请配置Diff输出根目录")
            return

        # 重置批量处理控制状态
        self.batch_paused = False
        self.batch_stopped = False
        self.batch_pause_event.set()

        # 禁用按钮
        self.url_builder.set_batch_button_state("disabled")
        self.url_builder.set_scan_button_state("disabled")
        self.download_button.config(state="disabled")

        # 启用暂停和停止按钮
        self.url_builder.set_pause_batch_button_state("normal")
        self.url_builder.set_pause_batch_button_text("⏸ 暂停")
        self.url_builder.set_stop_batch_button_state("normal")

        # 在新线程中执行批量处理
        thread = threading.Thread(target=self._batch_process_thread, args=(selected_files,))
        thread.daemon = True
        thread.start()

    def _batch_process_thread(self, selected_files):
        """批量处理线程（使用流水线模式）"""
        try:
            # 获取线程数配置
            thread_count = self.url_builder.get_thread_count()

            self._log("=" * 60)
            self._log("开始批量处理（流水线模式）")
            self._log(f"线程数: {thread_count}")
            self._log("=" * 60)

            # 切换到批量处理状态标签页
            self.root.after(0, lambda: self.notebook.select(1))  # 索引1是批量处理状态标签页

            # 清空并初始化批量状态组件
            self.root.after(0, lambda: self.batch_status_widget.clear())
            self.root.after(0, lambda: self.batch_progress_label.config(
                text=f"正在准备批量处理 {len(selected_files)} 个文件..."))
            self.root.after(0, lambda: self.batch_stats_label.config(text=""))

            # 添加所有文件到状态列表
            for filename, url in selected_files:
                self.root.after(0, lambda f=filename: self.batch_status_widget.add_file(f))

            # 获取当前选择的参数来构建子目录
            selections = self.url_builder.get_current_selections()
            tel_name = selections.get('telescope_name', 'Unknown')
            date = selections.get('date', 'Unknown')
            k_number = selections.get('k_number', 'Unknown')

            # 构建下载目录
            base_download_dir = self.download_dir_var.get().strip()
            actual_download_dir = os.path.join(base_download_dir, tel_name, date, k_number)
            os.makedirs(actual_download_dir, exist_ok=True)

            self._log(f"下载目录: {actual_download_dir}")
            self._log(f"模板目录: {self.template_dir_var.get().strip()}")

            # 保存批量输出根目录（系统名/日期/天区级别的目录）
            from datetime import datetime
            base_output_dir = self.diff_output_dir_var.get().strip()
            current_date = datetime.now().strftime("%Y%m%d")
            # 使用与download目录相同的结构：系统名/日期/天区
            self.last_batch_output_root = os.path.join(base_output_dir, tel_name, date, k_number)

            self._log(f"输出根目录: {self.last_batch_output_root}")
            self._log(f"目录结构: {tel_name}/{date}/{k_number}")

            # 使用流水线模式处理
            self._log("\n使用流水线模式: 下载 → ASTAP → Diff")
            self._log("-" * 60)
            self._pipeline_process_files(selected_files, actual_download_dir, thread_count)

            # 完成
            self._log("\n" + "=" * 60)
            self._log("批量处理完成（流水线模式）")
            self._log("=" * 60)

            # 更新批量处理状态标签页的进度信息
            self.root.after(0, lambda: self.batch_progress_label.config(
                text=f"✓ 批量处理完成！"))

            # 获取并显示最终统计
            stats = self.batch_status_widget.get_statistics()
            final_stats_text = (
                f"总计: {stats['total']} | "
                f"Diff成功: {stats['diff_success']} | "
                f"Diff失败: {stats['diff_failed']} | "
                f"跳过: {stats['diff_skipped']}"
            )
            self.root.after(0, lambda t=final_stats_text: self.batch_stats_label.config(text=t))

            self.root.after(0, lambda: self.status_label.config(text=f"批量处理完成"))

            # 启用打开输出目录按钮
            if self.last_batch_output_root and os.path.exists(self.last_batch_output_root):
                self.root.after(0, lambda: self.url_builder.set_open_batch_output_button_state("normal"))

        except Exception as e:
            error_msg = f"批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: (None if getattr(self, "_auto_silent_mode", False) else messagebox.showerror("错误", error_msg)))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            # 
            try:
                self._auto_silent_mode = False
            except Exception:
                pass

            # 
            # 
            # 
            # 
            # 
            # [Auto] [Chain] [Batch] []
            if getattr(self, "_auto_chain_followups", False):
                # [Note] :     GUI 
                self.root.after(500, self._auto_batch_query)

            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            # 禁用暂停和停止按钮
            self.root.after(0, lambda: self.url_builder.set_pause_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_stop_batch_button_state("disabled"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))

    def _get_url_selections(self):
        """获取URL选择参数的回调函数"""
        return self.url_builder.get_current_selections()

    def _full_day_batch_process(self):
        """全天下载diff - 对所选日期的所有天区的所有文件执行批量下载diff操作"""
        # 获取当前选择
        selections = self.url_builder.get_current_selections()
        tel_name = selections.get('telescope_name', '').strip()
        date = selections.get('date', '').strip()

        # 验证必要参数
        if not tel_name:
            messagebox.showwarning("警告", "请选择望远镜")
            return

        if not date:
            messagebox.showwarning("警告", "请选择日期")
            return

        # 检查必要的目录配置
        base_download_dir = self.download_dir_var.get().strip()
        template_dir = self.template_dir_var.get().strip()
        diff_output_dir = self.diff_output_dir_var.get().strip()

        if not base_download_dir:
            messagebox.showwarning("警告", "请配置下载根目录")
            return

        if not template_dir:
            messagebox.showwarning("警告", "请配置模板文件目录")
            return

        if not diff_output_dir:
            messagebox.showwarning("警告", "请配置Diff输出根目录")
            return

        # 获取可用的天区列表
        available_regions = self.url_builder.get_available_regions()
        if not available_regions:
            # 如果没有天区列表，尝试扫描
            messagebox.showinfo("提示", "正在扫描可用天区，请稍候...")
            # 触发天区扫描
            self.url_builder._auto_scan_regions()
            # 等待扫描完成后再次获取
            self.root.after(2000, lambda: self._continue_full_day_batch_process(tel_name, date))
            return

        # 确认操作
        msg = f"将对以下配置执行全天下载diff操作:\n\n"
        msg += f"望远镜: {tel_name}\n"
        msg += f"日期: {date}\n"
        msg += f"天区数量: {len(available_regions)}\n"
        msg += f"天区列表: {', '.join(available_regions)}\n\n"
        msg += f"这将扫描并处理所有天区的所有FITS文件，可能需要较长时间。\n\n"
        msg += f"是否继续？"

        if not messagebox.askyesno("确认", msg):
            return

        # 重置批量处理控制状态
        self.batch_paused = False
        self.batch_stopped = False
        self.batch_pause_event.set()

        # 启用暂停和停止按钮
        self.url_builder.set_pause_batch_button_state("normal")
        self.url_builder.set_pause_batch_button_text("⏸ 暂停")
        self.url_builder.set_stop_batch_button_state("normal")

        # 在新线程中执行
        thread = threading.Thread(target=self._full_day_batch_process_thread, args=(tel_name, date, available_regions))
        thread.daemon = True
        thread.start()

    def _continue_full_day_batch_process(self, tel_name, date):
        """继续执行全天下载diff（在扫描天区后）"""
        available_regions = self.url_builder.get_available_regions()
        if not available_regions:
            messagebox.showwarning("警告", "未找到可用的天区")
            return

        # 确认操作
        msg = f"将对以下配置执行全天下载diff操作:\n\n"
        msg += f"望远镜: {tel_name}\n"
        msg += f"日期: {date}\n"
        msg += f"天区数量: {len(available_regions)}\n"
        msg += f"天区列表: {', '.join(available_regions)}\n\n"
        msg += f"这将扫描并处理所有天区的所有FITS文件，可能需要较长时间。\n\n"
        msg += f"是否继续？"

        if not messagebox.askyesno("确认", msg):
            return

        # 在新线程中执行
        thread = threading.Thread(target=self._full_day_batch_process_thread, args=(tel_name, date, available_regions))
        thread.daemon = True
        thread.start()

    def _full_day_batch_process_thread(self, tel_name, date, available_regions):
        """全天批量处理线程"""
        try:
            # 禁用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("disabled"))
            self.root.after(0, lambda: self.download_button.config(state="disabled"))

            self._log("=" * 60)
            self._log("开始全天下载diff处理")
            self._log(f"望远镜: {tel_name}")
            self._log(f"日期: {date}")
            self._log(f"天区数量: {len(available_regions)}")
            self._log("=" * 60)

            # 切换到批量处理状态标签页
            self.root.after(0, lambda: self.notebook.select(1))

            # 收集所有天区的所有文件
            all_files_to_process = []
            total_regions = len(available_regions)

            for region_idx, k_number in enumerate(available_regions, 1):
                # 检查停止标志
                if self.batch_stopped:
                    self._log("\n全天批量处理已被停止")
                    break

                # 检查暂停标志
                if self.batch_paused:
                    self._log(f"\n全天批量处理已暂停（当前进度: 天区 {region_idx-1}/{total_regions}）")
                    self.root.after(0, lambda r=region_idx-1, t=total_regions: self.status_label.config(
                        text=f"全天批量处理已暂停 (天区 {r}/{t})"))

                # 等待暂停解除
                self.batch_pause_event.wait()

                # 暂停解除后再次检查停止标志
                if self.batch_stopped:
                    self._log("\n全天批量处理已被停止")
                    break

                self._log(f"\n[{region_idx}/{total_regions}] 正在扫描天区: {k_number}")
                self.root.after(0, lambda r=region_idx, t=total_regions, k=k_number:
                               self.status_label.config(text=f"正在扫描天区 [{r}/{t}]: {k}"))

                # 构建该天区的URL
                url_template = self.config_manager.get_url_template()
                format_params = {
                    'tel_name': tel_name,
                    'date': date,
                    'k_number': k_number
                }

                # 如果模板需要年份，添加年份参数
                if '{year_of_date}' in url_template:
                    try:
                        year_of_date = date[:4] if len(date) >= 4 else datetime.now().strftime('%Y')
                        format_params['year_of_date'] = year_of_date
                    except Exception:
                        format_params['year_of_date'] = datetime.now().strftime('%Y')

                region_url = url_template.format(**format_params)

                # 扫描该天区的FITS文件
                try:
                    fits_files = self.directory_scanner.scan_directory_listing(region_url)
                    if not fits_files:
                        # 如果目录扫描失败，尝试通用扫描器
                        fits_files = self.scanner.scan_fits_files(region_url)

                    self._log(f"  找到 {len(fits_files)} 个文件")

                    # 将文件添加到处理列表，同时记录天区信息
                    for filename, url, size in fits_files:
                        all_files_to_process.append((filename, url, k_number))

                except Exception as e:
                    self._log(f"  扫描失败: {str(e)}")
                    continue

            if not all_files_to_process:
                self._log("\n未找到任何FITS文件")
                self.root.after(0, lambda: messagebox.showwarning("警告", "未找到任何FITS文件"))
                return

            self._log(f"\n总共找到 {len(all_files_to_process)} 个文件")
            self._log("=" * 60)

            # 准备批量处理
            # 清空并初始化批量状态组件
            self.root.after(0, lambda: self.batch_status_widget.clear())
            self.root.after(0, lambda: self.batch_progress_label.config(
                text=f"正在准备批量处理 {len(all_files_to_process)} 个文件..."))

            # 添加所有文件到状态列表
            for filename, url, k_number in all_files_to_process:
                self.root.after(0, lambda f=filename: self.batch_status_widget.add_file(f))

            # 直接跨天区流水线处理：不按天区分批
            self._log("\n使用跨天区流水线：下载 → ASTAP → Diff（不按天区分批）")
            self.root.after(0, lambda: self.status_label.config(text=f"正在流水线处理所有天区的文件..."))

            # 准备带目录的文件列表（为每个文件指定独立下载目录）
            base_download_dir = self.download_dir_var.get().strip()
            selected_files_with_dirs = []
            for filename, url, k_number in all_files_to_process:
                per_dir = os.path.join(base_download_dir, tel_name, date, k_number)
                selected_files_with_dirs.append((filename, url, per_dir))

            # 设置输出根目录到 系统/日期
            base_output_dir = self.diff_output_dir_var.get().strip()
            self.last_batch_output_root = os.path.join(base_output_dir, tel_name, date)
            os.makedirs(self.last_batch_output_root, exist_ok=True)

            # 执行流水线
            thread_count = self.url_builder.get_thread_count()
            self._pipeline_process_files(selected_files_with_dirs, base_download_dir, thread_count)

            self._log("\n" + "=" * 60)
            self._log("全天下载diff处理完成！")
            self._log("=" * 60)

            # 显示完成消息
            self.root.after(0, lambda: (None if getattr(self, "_auto_silent_mode", False) else messagebox.showinfo("完成", "全天下载diff处理完成！")))

        except Exception as e:
            error_msg = f"全天批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: (None if getattr(self, "_auto_silent_mode", False) else messagebox.showerror("错误", error_msg)))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            # 禁用暂停和停止按钮
            self.root.after(0, lambda: self.url_builder.set_pause_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_stop_batch_button_state("disabled"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))
            # 恢复静默模式标志（若启用过）
            try:
                self._auto_silent_mode = False
            except Exception:
                pass


    def _batch_process_region(self, selected_files, tel_name, date, k_number):
        """
        处理单个天区的批量下载和diff操作（流水线模式）
        下载完一个文件 → 立即ASTAP → 立即Diff

        Args:
            selected_files: [(filename, url), ...] 文件列表
            tel_name: 望远镜名称
            date: 日期
            k_number: 天区编号
        """
        try:
            # 获取线程数配置
            thread_count = self.url_builder.get_thread_count()

            # 构建下载目录
            base_download_dir = self.download_dir_var.get().strip()
            actual_download_dir = os.path.join(base_download_dir, tel_name, date, k_number)
            os.makedirs(actual_download_dir, exist_ok=True)

            self._log(f"下载目录: {actual_download_dir}")

            # 保存批量输出根目录
            base_output_dir = self.diff_output_dir_var.get().strip()
            self.last_batch_output_root = os.path.join(base_output_dir, tel_name, date, k_number)

            # 使用流水线模式处理
            self._log("\n使用流水线模式: 下载 → ASTAP → Diff")
            self._log("-" * 60)
            self.root.after(0, lambda: self.status_label.config(text=f"正在流水线处理 {k_number} 的文件..."))

            # 调用流水线处理方法
            self._pipeline_process_files(selected_files, actual_download_dir, thread_count)

        except Exception as e:
            self._log(f"处理天区 {k_number} 时出错: {str(e)}")
            import traceback
            self._log(traceback.format_exc())

    def _pipeline_process_files(self, selected_files, download_dir, thread_count):
        """
        流水线处理文件：下载 → ASTAP → Diff
        每下载完一个文件，立即进行ASTAP处理，ASTAP完成后立即进行Diff处理

        Args:
            selected_files: [(filename, url), ...] 文件列表
            download_dir: 下载目录
            thread_count: 线程数
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        import queue

        # 创建队列用于流水线处理
        astap_queue = queue.Queue()  # 下载完成的文件队列
        diff_queue = queue.Queue()   # ASTAP完成的文件队列

        # 统计信息
        stats_lock = threading.Lock()
        stats = {
            'download_completed': 0,
            'download_failed': 0,
            'astap_completed': 0,
            'astap_success': 0,
            'astap_failed': 0,
            'diff_completed': 0,
            'diff_success': 0,
            'diff_failed': 0,
            'total_files': len(selected_files),
            'current_speed_mb_s': 0.0,
        }

        # 停止标志
        stop_event = threading.Event()

        # 获取diff配置参数
        template_dir = self.template_dir_var.get().strip()
        noise_methods = []
        if self.fits_viewer.outlier_var.get():
            noise_methods.append('outlier')
        if self.fits_viewer.hot_cold_var.get():
            noise_methods.append('hot_cold')
        if self.fits_viewer.adaptive_median_var.get():
            noise_methods.append('adaptive_median')
        alignment_method = self.fits_viewer.alignment_var.get()
        remove_bright_lines = self.fits_viewer.remove_lines_var.get()
        stretch_method = self.fits_viewer.stretch_method_var.get()
        fast_mode = self.fits_viewer.fast_mode_var.get()
        percentile_low = 99.95
        if stretch_method == 'percentile':
            try:
                percentile_low = float(self.fits_viewer.percentile_entry.get())
            except:
                percentile_low = 99.95
        sort_by = self.fits_viewer.sort_by_var.get()

        # 启动ASTAP工作线程池
        def astap_worker():
            """ASTAP处理工作线程"""
            while not stop_event.is_set() and not self.batch_stopped:
                try:
                    file_path = astap_queue.get(timeout=1)
                    if file_path is None:  # 结束信号
                        astap_queue.task_done()
                        break

                    # 检查停止标志
                    if self.batch_stopped:
                        astap_queue.task_done()
                        break

                    # 等待暂停解除
                    self.batch_pause_event.wait()

                    # 暂停解除后再次检查停止标志
                    if self.batch_stopped:
                        astap_queue.task_done()
                        break

                    try:
                        filename = os.path.basename(file_path)
                        self._log(f"[ASTAP] 开始处理: {filename}")
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_ASTAP_PROCESSING))

                        # 执行ASTAP处理
                        result = self._process_single_astap(file_path)

                        with stats_lock:
                            stats['astap_completed'] += 1

                        if result and result.get('success'):
                            # 检查WCS
                            from astropy.io import fits as astropy_fits
                            with astropy_fits.open(file_path) as hdul:
                                header = hdul[0].header
                                has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                            if has_wcs:
                                with stats_lock:
                                    stats['astap_success'] += 1
                                self._log(f"[ASTAP] ✓ 成功: {filename}")
                                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                    f, BatchStatusWidget.STATUS_ASTAP_SUCCESS))
                                # 放入diff队列
                                diff_queue.put(file_path)
                            else:
                                with stats_lock:
                                    stats['astap_failed'] += 1
                                self._log(f"[ASTAP] ✗ 失败(无WCS): {filename}")
                                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                    f, BatchStatusWidget.STATUS_ASTAP_FAILED, "未添加WCS"))
                        else:
                            with stats_lock:
                                stats['astap_failed'] += 1
                            error_msg = result.get('message', '未知错误') if result else '处理失败'
                            self._log(f"[ASTAP] ✗ 失败: {filename} - {error_msg}")
                            self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_ASTAP_FAILED, msg))

                        # 更新统计
                        self._update_pipeline_stats(stats)

                    finally:
                        # 标记任务完成
                        astap_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    self._log(f"[ASTAP] 异常: {str(e)}")
                    try:
                        astap_queue.task_done()
                    except:
                        pass

        # 启动Diff工作线程池
        def diff_worker():
            """Diff处理工作线程"""
            while not stop_event.is_set() and not self.batch_stopped:
                try:
                    file_path = diff_queue.get(timeout=1)
                    if file_path is None:  # 结束信号
                        diff_queue.task_done()
                        break

                    # 检查停止标志
                    if self.batch_stopped:
                        diff_queue.task_done()
                        break

                    # 等待暂停解除
                    self.batch_pause_event.wait()

                    # 暂停解除后再次检查停止标志
                    if self.batch_stopped:
                        diff_queue.task_done()
                        break

                    try:
                        filename = os.path.basename(file_path)
                        self._log(f"[Diff] 开始处理: {filename}")
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_DIFF_PROCESSING))

                        # 执行Diff处理
                        result = self._process_single_diff(
                            file_path, template_dir, noise_methods, alignment_method,
                            remove_bright_lines, stretch_method, percentile_low, fast_mode, sort_by
                        )

                        with stats_lock:
                            stats['diff_completed'] += 1

                        if result and result.get('success'):
                            with stats_lock:
                                stats['diff_success'] += 1
                            new_spots = result.get('new_spots', 0)
                            self._log(f"[Diff] ✓ 成功: {filename} - {new_spots}个亮点")
                            self.root.after(0, lambda f=filename, n=new_spots: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_DIFF_SUCCESS, f"{n}个亮点"))
                        else:
                            with stats_lock:
                                stats['diff_failed'] += 1
                            error_msg = result.get('message', '未知错误') if result else '处理失败'
                            self._log(f"[Diff] ✗ 失败: {filename} - {error_msg}")
                            self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_DIFF_FAILED, msg))

                        # 更新统计
                        self._update_pipeline_stats(stats)

                    finally:
                        # 标记任务完成
                        diff_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    self._log(f"[Diff] 异常: {str(e)}")
                    try:
                        diff_queue.task_done()
                    except:
                        pass

        # 启动ASTAP和Diff工作线程
        astap_threads = []
        diff_threads = []

        for i in range(thread_count):
            t = threading.Thread(target=astap_worker, daemon=True)
            t.start()
            astap_threads.append(t)

        for i in range(thread_count):
            t = threading.Thread(target=diff_worker, daemon=True)
            t.start()
            diff_threads.append(t)

        self._log(f"启动了 {thread_count} 个ASTAP工作线程和 {thread_count} 个Diff工作线程")

        # 下载文件并放入ASTAP队列（单线程下载）
        self._log("\n开始下载文件...")
        for idx, item in enumerate(selected_files, 1):
            # 兼容两种输入格式：
            # 1) (filename, url)
            # 2) (filename, url, per_download_dir)
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                filename, url = item[0], item[1]
                per_download_dir = item[2] if len(item) >= 3 and item[2] else download_dir
            else:
                # 输入异常，跳过
                continue

            # 检查停止标志
            if self.batch_stopped:
                self._log("\n批量处理已被停止")
                stop_event.set()
                break

            # 检查暂停标志
            if self.batch_paused:
                self._log(f"\n批量处理已暂停（当前进度: {idx-1}/{len(selected_files)}）")
                self.root.after(0, lambda i=idx-1, t=len(selected_files): self.status_label.config(
                    text=f"批量处理已暂停 ({i}/{t})"))

            # 等待暂停解除
            self.batch_pause_event.wait()

            # 暂停解除后再次检查停止标志
            if self.batch_stopped:
                self._log("\n批量处理已被停止")
                stop_event.set()
                break

            self._log(f"[下载] [{idx}/{len(selected_files)}] {filename}")
            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                f, BatchStatusWidget.STATUS_DOWNLOADING))
            # 标记下载开始时间并在“批量处理状态/处理进度”显示当前下载中文件
            start_time = time.time()
            self.root.after(0, lambda i=idx, t=len(selected_files), f=filename:
                            self.batch_progress_label.config(text=f"下载中 ({i}/{t}): {f}"))

            # 初始化下载进度状态（用于滚动显示速度）
            progress_state = {'last_time': start_time, 'last_bytes': 0, 'last_ui': start_time}

            def progress_callback(downloaded_bytes, total_bytes, fn=filename, i=idx, t=len(selected_files)):
                now = time.time()
                delta_t = max(now - progress_state['last_time'], 1e-3)
                delta_bytes = max(downloaded_bytes - progress_state['last_bytes'], 0)
                inst_speed_mb_s = (delta_bytes / (1024.0 * 1024.0)) / delta_t
                downloaded_mb = downloaded_bytes / (1024.0 * 1024.0)
                total_mb = (total_bytes / (1024.0 * 1024.0)) if total_bytes else None
                # 节流更新频率，避免UI过于频繁刷新
                if now - progress_state['last_ui'] >= 0.2:
                    if total_mb is not None:
                        text = f"下载中 ({i}/{t}): {fn} | {downloaded_mb:.2f}/{total_mb:.2f} MB | 速度: {inst_speed_mb_s:.2f} MB/s"
                    else:
                        text = f"下载中 ({i}/{t}): {fn} | {downloaded_mb:.2f}/未知 MB | 速度: {inst_speed_mb_s:.2f} MB/s"
                    self.root.after(0, lambda txt=text: self.batch_progress_label.config(text=txt))
                    with stats_lock:
                        stats['current_speed_mb_s'] = inst_speed_mb_s
                    progress_state['last_ui'] = now
                progress_state['last_time'] = now
                progress_state['last_bytes'] = downloaded_bytes

            # 为每个文件选择独立目录（若提供）
            os.makedirs(per_download_dir, exist_ok=True)
            file_path = os.path.join(per_download_dir, filename)

            # 检查文件是否已存在
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                self._log(f"[下载] ⊙ 文件已存在，跳过下载: {filename}")
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_DOWNLOAD_SUCCESS))

                # 检查是否已有WCS
                try:
                    from astropy.io import fits as astropy_fits
                    with astropy_fits.open(file_path) as hdul:
                        header = hdul[0].header
                        has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                    if has_wcs:
                        self._log(f"[下载] ✓ 文件已有WCS，直接进入Diff队列: {filename}")
                        diff_queue.put(file_path)
                    else:
                        self._log(f"[下载] → 文件无WCS，进入ASTAP队列: {filename}")
                        astap_queue.put(file_path)
                except:
                    astap_queue.put(file_path)
                # 已存在则更新处理进度提示（无速度）
                self.root.after(0, lambda i=idx, t=len(selected_files), f=filename:
                                self.batch_progress_label.config(text=f"跳过下载(已存在) ({i}/{t}): {f}"))

                with stats_lock:
                    stats['current_speed_mb_s'] = 0.0
                    stats['download_completed'] += 1
                continue

            # 下载文件
            try:
                # 使用现有的下载器
                if not self.downloader:
                    self.downloader = FitsDownloader(
                        max_workers=1,
                        retry_times=self.retry_times_var.get(),
                        timeout=self.timeout_var.get(),
                        enable_astap=False,  # 不在下载器中处理ASTAP
                        astap_config_path="config/url_config.json"
                    )

                # 注意：需使用每个文件对应的独立下载目录 per_download_dir，避免与队列中的 file_path 不一致
                result = self.downloader.download_single_file(url, per_download_dir, progress_callback)

                if "成功" in result:
                    with stats_lock:
                        stats['download_completed'] += 1
                    self._log(f"[下载] ✓ 成功: {filename}")
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_SUCCESS))
                    # 计算并显示当前下载速度（MB/s）
                    try:
                        elapsed = max(time.time() - start_time, 1e-3)
                        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        speed_mb_s = (size_bytes / (1024.0 * 1024.0)) / elapsed
                    except Exception:
                        speed_mb_s = 0.0
                    self.root.after(0, lambda i=idx, t=len(selected_files), f=filename, s=speed_mb_s:

                                    self.batch_progress_label.config(text=f"下载完成 ({i}/{t}): {f} | 速度: {s:.2f} MB/s"))


                    with stats_lock:
                        stats['current_speed_mb_s'] = speed_mb_s

                    # 检查是否已有WCS
                    try:
                        from astropy.io import fits as astropy_fits
                        with astropy_fits.open(file_path) as hdul:
                            header = hdul[0].header
                            has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                        if has_wcs:
                            self._log(f"[下载] ✓ 文件已有WCS，直接进入Diff队列: {filename}")
                            diff_queue.put(file_path)
                        else:
                            self._log(f"[下载] → 文件无WCS，进入ASTAP队列: {filename}")
                            astap_queue.put(file_path)
                    except:
                        astap_queue.put(file_path)
                else:
                    with stats_lock:
                        stats['download_failed'] += 1
                        stats['current_speed_mb_s'] = 0.0
                    self._log(f"[下载] ✗ 失败: {filename}")
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_FAILED, "下载失败"))
                    self.root.after(0, lambda i=idx, t=len(selected_files), f=filename:
                                    self.batch_progress_label.config(text=f"下载失败 ({i}/{t}): {f}"))





            except Exception as e:
                with stats_lock:
                    stats['download_failed'] += 1
                    stats['current_speed_mb_s'] = 0.0
                self._log(f"[下载] ✗ 异常: {filename} - {str(e)}")
                self.root.after(0, lambda f=filename, err=str(e): self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_DOWNLOAD_FAILED, err))

                self.root.after(0, lambda i=idx, t=len(selected_files), f=filename, err=str(e):
                                self.batch_progress_label.config(text=f"下载异常 ({i}/{t}): {f} | {err}"))


            # 更新统计
            self._update_pipeline_stats(stats)

        self._log("\n所有文件下载完成，等待ASTAP和Diff处理完成...")

        # 等待ASTAP队列处理完成
        astap_queue.join()
        # 发送结束信号给ASTAP线程
        for _ in range(thread_count):
            astap_queue.put(None)

        # 等待Diff队列处理完成
        diff_queue.join()
        # 发送结束信号给Diff线程
        for _ in range(thread_count):
            diff_queue.put(None)

        # 等待所有线程结束
        stop_event.set()
        for t in astap_threads:
            t.join(timeout=5)
        for t in diff_threads:
            t.join(timeout=5)

        # 打印最终统计
        self._log("\n" + "=" * 60)
        self._log("流水线处理完成！")
        self._log(f"下载: 成功 {stats['download_completed']}, 失败 {stats['download_failed']}")
        self._log(f"ASTAP: 成功 {stats['astap_success']}, 失败 {stats['astap_failed']}")
        self._log(f"Diff: 成功 {stats['diff_success']}, 失败 {stats['diff_failed']}")
        self._log("=" * 60)

    def _update_pipeline_stats(self, stats):
        """更新流水线统计信息显示"""
        speed = stats.get('current_speed_mb_s', 0.0)
        stats_text = (f"下载: {stats['download_completed']}/{stats['total_files']} | "
                      f"速度: {speed:.2f} MB/s | "
                      f"ASTAP: {stats['astap_success']}/{stats['astap_completed']} | "
                      f"Diff: {stats['diff_success']}/{stats['diff_completed']}")
        self.root.after(0, lambda t=stats_text: self.batch_stats_label.config(text=t))

    def _execute_diff_for_files(self, files_with_wcs, thread_count):
        """
        对文件列表执行diff操作

        Args:
            files_with_wcs: 包含WCS信息的文件路径列表
            thread_count: 线程数
        """
        # 步骤2: 执行Diff操作
        self._log("\n步骤2: 执行Diff操作")
        self._log("-" * 60)
        self.root.after(0, lambda: self.status_label.config(text="正在执行Diff操作..."))

        success_count = 0
        fail_count = 0

        template_dir = self.template_dir_var.get().strip()

        # 从fits_viewer的控件获取配置参数（控件已从配置文件加载）
        noise_methods = []
        if self.fits_viewer.outlier_var.get():
            noise_methods.append('outlier')
        if self.fits_viewer.hot_cold_var.get():
            noise_methods.append('hot_cold')
        if self.fits_viewer.adaptive_median_var.get():
            noise_methods.append('adaptive_median')

        alignment_method = self.fits_viewer.alignment_var.get()
        remove_bright_lines = self.fits_viewer.remove_lines_var.get()
        stretch_method = self.fits_viewer.stretch_method_var.get()
        fast_mode = self.fits_viewer.fast_mode_var.get()

        # 获取百分位数参数
        percentile_low = 99.95
        if stretch_method == 'percentile':
            try:
                percentile_low = float(self.fits_viewer.percentile_var.get())
            except:
                percentile_low = 99.95

        # 获取排序方式参数
        sort_by = self.fits_viewer.sort_by_var.get()

        self._log(f"使用配置: 降噪={noise_methods}, 对齐={alignment_method}, 去亮线={remove_bright_lines}, 拉伸={stretch_method}, 快速模式={fast_mode}, 排序方式={sort_by}")
        self._log(f"使用 {thread_count} 个线程并行处理")

        # 使用线程池并行处理
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        # 创建线程锁用于更新计数器
        counter_lock = threading.Lock()
        completed_count = 0

        # 创建线程池
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            # 提交所有任务
            future_to_file = {}
            for download_file in files_with_wcs:
                filename = os.path.basename(download_file)
                # 更新状态为Diff处理中
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_DIFF_PROCESSING))

                future = executor.submit(
                    self._process_single_diff,
                    download_file, template_dir, noise_methods, alignment_method,
                    remove_bright_lines, stretch_method, percentile_low, fast_mode, sort_by
                )
                future_to_file[future] = download_file

            # 处理完成的任务
            for future in as_completed(future_to_file):
                download_file = future_to_file[future]
                filename = os.path.basename(download_file)

                with counter_lock:
                    completed_count += 1
                    current_completed = completed_count

                # 更新进度显示
                progress_text = f"Diff处理中 ({current_completed}/{len(files_with_wcs)}): 并行处理中..."
                self.root.after(0, lambda t=progress_text: self.batch_progress_label.config(text=t))

                try:
                    result_dict = future.result()

                    # 记录日志
                    self._log(f"\n[{current_completed}/{len(files_with_wcs)}] {filename}")

                    if result_dict['success']:
                        if result_dict.get('skipped'):
                            # 跳过的文件
                            success_count += 1
                            self._log(f"  ⊙ 已存在处理结果，跳过")
                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_DIFF_SKIPPED, "已有结果"))
                        else:
                            # 成功处理
                            success_count += 1
                            new_spots = result_dict['new_spots']
                            self._log(f"  ✓ 成功 - 检测到 {new_spots} 个新亮点")
                            self.root.after(0, lambda f=filename, n=new_spots: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_DIFF_SUCCESS, f"{n}个亮点"))
                    else:
                        # 失败
                        fail_count += 1
                        self._log(f"  ✗ {result_dict['message']}")
                        self.root.after(0, lambda f=filename, msg=result_dict['message']: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_DIFF_FAILED, msg))

                    # 更新统计信息
                    stats_text = f"已完成: {current_completed}/{len(files_with_wcs)} | 成功: {success_count} | 失败: {fail_count}"
                    self.root.after(0, lambda t=stats_text: self.batch_stats_label.config(text=t))

                except Exception as e:
                    fail_count += 1
                    self._log(f"  ✗ 处理异常: {str(e)}")
                    self.root.after(0, lambda f=filename, err=str(e): self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DIFF_FAILED, err))

        self._log(f"\nDiff处理完成: 成功 {success_count} 个, 失败 {fail_count} 个")

    def _full_day_all_systems_batch_process(self):
        """全天全系统下载diff - 对所选日期的所有系统的所有天区的所有文件执行批量下载diff操作"""
        # 获取当前选择的日期
        selections = self.url_builder.get_current_selections()
        date = selections.get('date', '').strip()

        # 验证必要参数
        if not date:
            messagebox.showwarning("警告", "请选择日期")
            return

        # 检查必要的目录配置
        base_download_dir = self.download_dir_var.get().strip()
        template_dir = self.template_dir_var.get().strip()
        diff_output_dir = self.diff_output_dir_var.get().strip()

        if not base_download_dir:
            messagebox.showwarning("警告", "请配置下载根目录")
            return

        if not template_dir:
            messagebox.showwarning("警告", "请配置模板文件目录")
            return

        if not diff_output_dir:
            messagebox.showwarning("警告", "请配置Diff输出根目录")
            return

        # 获取所有望远镜系统
        all_telescopes = self.config_manager.get_telescope_names()
        if not all_telescopes:
            messagebox.showwarning("警告", "未找到可用的望远镜系统")
            return

        # 确认操作
        msg = f"将对以下配置执行全天全系统下载diff操作:\n\n"
        msg += f"日期: {date}\n"
        msg += f"系统数量: {len(all_telescopes)}\n"
        msg += f"系统列表: {', '.join(all_telescopes)}\n\n"
        msg += f"这将扫描并处理所有系统的所有天区的所有FITS文件，\n"
        msg += f"可能需要非常长的时间。\n\n"
        msg += f"是否继续？"

        if not messagebox.askyesno("确认", msg):
            return

        # 重置批量处理控制状态
        self.batch_paused = False
        self.batch_stopped = False
        self.batch_pause_event.set()

        # 启用暂停和停止按钮
        self.url_builder.set_pause_batch_button_state("normal")
        self.url_builder.set_pause_batch_button_text("⏸ 暂停")
        self.url_builder.set_stop_batch_button_state("normal")

        # 在新线程中执行
        thread = threading.Thread(target=self._full_day_all_systems_batch_process_thread, args=(date, all_telescopes))
        thread.daemon = True
        thread.start()

    def _full_day_all_systems_batch_process_thread(self, date, all_telescopes):
        """全天全系统批量处理线程"""
        try:
            # 禁用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_full_day_all_systems_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("disabled"))
            self.root.after(0, lambda: self.download_button.config(state="disabled"))

            self._log("=" * 60)
            self._log("开始全天全系统下载diff处理")
            self._log(f"日期: {date}")
            self._log(f"系统数量: {len(all_telescopes)}")
            self._log(f"系统列表: {', '.join(all_telescopes)}")
            self._log("=" * 60)

            # 切换到批量处理状态标签页
            self.root.after(0, lambda: self.notebook.select(1))

            # 清空批量状态组件
            self.root.after(0, lambda: self.batch_status_widget.clear())

            # 遍历所有系统
            total_systems = len(all_telescopes)
            total_files_processed = 0

            for system_idx, tel_name in enumerate(all_telescopes, 1):
                # 检查停止标志
                if self.batch_stopped:
                    self._log("\n全天全系统批量处理已被停止")
                    break

                # 检查暂停标志
                if self.batch_paused:
                    self._log(f"\n全天全系统批量处理已暂停（当前进度: 系统 {system_idx-1}/{total_systems}）")
                    self.root.after(0, lambda s=system_idx-1, t=total_systems: self.status_label.config(
                        text=f"全天全系统批量处理已暂停 (系统 {s}/{t})"))

                # 等待暂停解除
                self.batch_pause_event.wait()

                # 暂停解除后再次检查停止标志
                if self.batch_stopped:
                    self._log("\n全天全系统批量处理已被停止")
                    break

                self._log(f"\n{'=' * 60}")
                self._log(f"[{system_idx}/{total_systems}] 处理系统: {tel_name}")
                self._log(f"{'=' * 60}")
                self.root.after(0, lambda s=system_idx, t=total_systems, n=tel_name:
                               self.status_label.config(text=f"正在处理系统 [{s}/{t}]: {n}"))

                # 构建该系统的基础URL并扫描天区
                url_template = self.config_manager.get_url_template()
                format_params = {
                    'tel_name': tel_name,
                    'date': date,
                    'k_number': ''
                }

                # 如果模板需要年份，添加年份参数
                if '{year_of_date}' in url_template:
                    try:
                        year_of_date = date[:4] if len(date) >= 4 else datetime.now().strftime('%Y')
                        format_params['year_of_date'] = year_of_date
                    except Exception:
                        format_params['year_of_date'] = datetime.now().strftime('%Y')

                base_url = url_template.format(**format_params).rstrip('/')

                # 扫描该系统的可用天区
                self._log(f"扫描天区: {base_url}")
                try:
                    from url_builder import RegionScanner
                    region_scanner = RegionScanner()
                    available_regions = region_scanner.scan_available_regions(base_url)

                    if not available_regions:
                        self._log(f"  未找到可用天区，跳过系统 {tel_name}")
                        continue

                    self._log(f"  找到 {len(available_regions)} 个天区: {', '.join(available_regions)}")

                    # 收集该系统所有天区的所有文件
                    system_files_to_process = []

                    for region_idx, k_number in enumerate(available_regions, 1):
                        # 检查停止标志
                        if self.batch_stopped:
                            self._log("\n全天全系统批量处理已被停止")
                            break

                        # 检查暂停标志并等待
                        self.batch_pause_event.wait()

                        # 暂停解除后再次检查停止标志
                        if self.batch_stopped:
                            break

                        self._log(f"\n  [{region_idx}/{len(available_regions)}] 扫描天区: {k_number}")
                        self.root.after(0, lambda s=system_idx, t=total_systems, n=tel_name, r=region_idx, rt=len(available_regions), k=k_number:
                                       self.status_label.config(text=f"系统 [{s}/{t}] {n} - 天区 [{r}/{rt}]: {k}"))

                        # 构建该天区的URL
                        format_params['k_number'] = k_number
                        region_url = url_template.format(**format_params)

                        # 扫描该天区的FITS文件
                        try:
                            fits_files = self.directory_scanner.scan_directory_listing(region_url)
                            if not fits_files:
                                fits_files = self.scanner.scan_fits_files(region_url)

                            self._log(f"    找到 {len(fits_files)} 个文件")

                            # 将文件添加到处理列表
                            for filename, url, size in fits_files:
                                system_files_to_process.append((filename, url, tel_name, k_number))

                        except Exception as e:
                            self._log(f"    扫描失败: {str(e)}")
                            continue

                    if not system_files_to_process:
                        self._log(f"\n系统 {tel_name} 未找到任何FITS文件")
                        continue

                    self._log(f"\n系统 {tel_name} 总共找到 {len(system_files_to_process)} 个文件")

                    # 添加所有文件到状态列表
                    for filename, url, tel_name_item, k_number in system_files_to_process:
                        self.root.after(0, lambda f=filename: self.batch_status_widget.add_file(f))

                    # 直接跨天区流水线处理（单系统，不按天区分批）
                    self._log(f"\n  使用跨天区流水线：系统 {tel_name}（不按天区分批）")
                    base_download_dir = self.download_dir_var.get().strip()
                    selected_files_with_dirs = []
                    for filename, url, tel_name_item, k_number in system_files_to_process:
                        per_dir = os.path.join(base_download_dir, tel_name, date, k_number)
                        selected_files_with_dirs.append((filename, url, per_dir))

                    # 设置输出根目录到 系统/日期
                    base_output_dir = self.diff_output_dir_var.get().strip()
                    self.last_batch_output_root = os.path.join(base_output_dir, tel_name, date)
                    os.makedirs(self.last_batch_output_root, exist_ok=True)

                    thread_count = self.url_builder.get_thread_count()
                    self._pipeline_process_files(selected_files_with_dirs, base_download_dir, thread_count)

                    total_files_processed += len(system_files_to_process)

                except Exception as e:
                    self._log(f"处理系统 {tel_name} 时出错: {str(e)}")
                    import traceback
                    self._log(traceback.format_exc())
                    continue

            self._log("\n" + "=" * 60)
            self._log("全天全系统下载diff处理完成！")
            self._log(f"总共处理了 {total_files_processed} 个文件")
            self._log("=" * 60)

            # 显示完成消息
            self.root.after(0, lambda: (None if getattr(self, "_auto_silent_mode", False) else messagebox.showinfo("完成", f"全天全系统下载diff处理完成！\n总共处理了 {total_files_processed} 个文件")))

        except Exception as e:
            error_msg = f"全天全系统批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: (None if getattr(self, "_auto_silent_mode", False) else messagebox.showerror("错误", error_msg)))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_all_systems_batch_button_state("normal"))
            # 恢复静默标志（若启用过）
            try:
                self._auto_silent_mode = False
            except Exception:
                pass

            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            # 禁用暂停和停止按钮
            self.root.after(0, lambda: self.url_builder.set_pause_batch_button_state("disabled"))
            self.root.after(0, lambda: self.url_builder.set_stop_batch_button_state("disabled"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))

    def _on_closing(self):
        """应用程序关闭事件"""
        try:
            # 保存当前配置
            self.config_manager.update_download_settings(
                max_workers=self.max_workers_var.get(),
                retry_times=self.retry_times_var.get(),
                timeout=self.timeout_var.get()
            )

            # 保存下载目录、模板目录、diff输出目录和未查询导出目录
            download_dir = self.download_dir_var.get().strip()
            template_dir = self.template_dir_var.get().strip()
            diff_output_dir = self.diff_output_dir_var.get().strip()
            detected_dir = self.detected_dir_var.get().strip()
            unqueried_export_dir = self.unqueried_export_dir_var.get().strip()
            if download_dir or template_dir or diff_output_dir or detected_dir or unqueried_export_dir:
                update_data = {}
                if download_dir:
                    update_data['download_directory'] = download_dir
                if template_dir:
                    update_data['template_directory'] = template_dir
                if diff_output_dir:
                    update_data['diff_output_directory'] = diff_output_dir
                if detected_dir:
                    update_data['detected_directory'] = detected_dir
                if unqueried_export_dir:
                    update_data['unqueried_export_directory'] = unqueried_export_dir
                self.config_manager.update_last_selected(**update_data)

            self._log("配置已保存")

        except Exception as e:
            self._log(f"保存配置失败: {str(e)}")
        finally:
            self.root.destroy()

    def _apply_auto_settings(self):
        """应用自动设置并执行相应操作"""
        try:
            self._log("=" * 60)
            self._log("自动执行模式")
            self._log(f"日期: {self.auto_date}")
            self._log(f"望远镜: {self.auto_telescope}")
            self._log(f"天区: {self.auto_region}")
            self._log("=" * 60)

            # 验证日期格式
            if not self.config_manager.validate_date(self.auto_date):
                error_msg = f"日期格式无效: {self.auto_date}，需要YYYYMMDD格式"
                self._log(error_msg)
                messagebox.showerror("参数错误", error_msg)
                return

            # 设置日期
            self.url_builder.date_var.set(self.auto_date)
            self._log(f"已设置日期: {self.auto_date}")

            # 根据参数组合决定执行的操作
            if self.auto_region:
                # 有日期、望远镜系统名和天区名 - 执行"扫描fits文件" + "全选" + "批量下载并diff"
                if not self.auto_telescope:
                    error_msg = "指定了天区但未指定望远镜系统名"
                    self._log(error_msg)
                    messagebox.showerror("参数错误", error_msg)
                    return

                self._log("执行模式: 扫描fits文件 + 全选 + 批量下载并diff")

                # 设置望远镜
                self.url_builder.telescope_var.set(self.auto_telescope)
                self._log(f"已设置望远镜: {self.auto_telescope}")

                # 设置天区
                self.url_builder.k_number_var.set(self.auto_region)
                self._log(f"已设置天区: {self.auto_region}")

                # 延迟执行，确保UI完全初始化
                self.root.after(2000, self._auto_scan_and_batch)

            elif self.auto_telescope:
                # 有日期和望远镜系统名 - 执行"全天下载diff"操作
                self._log("执行模式: 全天下载diff")

                # 设置望远镜
                self.url_builder.telescope_var.set(self.auto_telescope)
                self._log(f"已设置望远镜: {self.auto_telescope}")

                # 延迟执行，确保UI完全初始化
                self.root.after(2000, self._auto_full_day_batch)

            else:
                # 只有日期 - 执行"全天全系统diff"操作
                self._log("执行模式: 全天全系统diff")

                # 延迟执行，确保UI完全初始化
                self.root.after(2000, self._auto_full_day_all_systems_batch)

        except Exception as e:
            error_msg = f"应用自动设置失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            messagebox.showerror("错误", error_msg)

    def _auto_scan_and_batch(self):
        """自动执行：扫描fits文件 + 全选 + 批量下载并diff"""
        try:
            self._log("开始自动扫描FITS文件...")

            # 执行扫描
            self._start_scan()

            # 等待扫描完成后全选并批量处理
            self.root.after(3000, self._auto_select_all_and_batch)

        except Exception as e:
            error_msg = f"自动扫描失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            if not getattr(self, "_auto_silent_mode", False):
                messagebox.showerror("错误", error_msg)

    def _auto_select_all_and_batch(self):
        """自动执行：全选并批量处理"""
        try:
            # 检查是否有文件
            if not self.fits_files_list:
                self._log("未找到FITS文件，无法执行批量处理")
                if not getattr(self, "_auto_silent_mode", False):
                    messagebox.showwarning("警告", "未找到FITS文件")
                return

            self._log(f"找到 {len(self.fits_files_list)} 个FITS文件")

            # 全选
            self._log("执行全选...")
            self._select_all()

            # 延迟一下再执行批量处理
            self.root.after(1000, self._auto_execute_batch)

        except Exception as e:
            error_msg = f"自动全选失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            if not getattr(self, "_auto_silent_mode", False):
                messagebox.showerror("错误", error_msg)

    def _auto_execute_batch(self):
        """自动执行：批量下载并diff（全程静默，无弹窗打断）"""
        try:
            self._log("开始批量下载并diff...")

            # 标记后续需要自动执行 批量查询 和 批量导出未查询
            self._auto_chain_followups = True

            # 开启静默模式，避免任何弹窗阻塞（包含后续查询/导出/上传链）
            setattr(self, "_auto_silent_mode", True)
            try:
                # 需要静默viewer里的导出/OSS上传弹窗
                self.fits_viewer._auto_silent_mode = True
            except Exception:
                pass

            # 静默执行批量处理（屏蔽确认/提示类弹窗）
            self._run_without_messageboxes(self._batch_process)

        except Exception as e:
            error_msg = f"自动批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            messagebox.showerror("错误", error_msg)

    def _auto_full_day_batch(self):
        """自动执行：全天下载diff"""
        try:
            self._log("开始全天下载diff...")

            # 静默执行全天下载diff（屏蔽确认对话框）
            self._run_without_messageboxes(self._full_day_batch_process)

        except Exception as e:
            error_msg = f"自动全天下载diff失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            # 自动模式下也不弹框
            if not getattr(self, "_auto_silent_mode", False):
                messagebox.showerror("错误", error_msg)

    # ========================= 自动链：批量 → 批量查询 → 批量导出未查询 =========================
    def _normalize_path(self, p: str) -> str:
        import os
        return os.path.normcase(os.path.normpath(p)) if p else ""

    def _find_viewer_tree_node_by_path(self, target_path: str):
        """在 FitsImageViewer 的目录树中按绝对路径查找节点，返回 item id 或 None"""
        tree = getattr(self.fits_viewer, "directory_tree", None)
        if tree is None or not target_path:
            return None
        norm_target = self._normalize_path(target_path)

        def dfs(parent_id):
            for item in tree.get_children(parent_id):
                vals = tree.item(item, "values")
                node_path = self._normalize_path(vals[0]) if vals else ""
                if node_path == norm_target:
                    return item
                found = dfs(item)
                if found:
                    return found
            return None

        return dfs("")

    def _run_without_messageboxes(self, func, *args, **kwargs):
        """在一次调用期间临时屏蔽 messagebox 弹窗，自动同意确认并跳过“打开目录”。"""
        from tkinter import messagebox as mb
        saved = {}
        for name in ("showinfo", "showwarning", "showerror", "askyesno", "askquestion"):
            if hasattr(mb, name):
                saved[name] = getattr(mb, name)

        def _log_msg(kind, title, message=None):
            msg = f"[自动静默][{kind}] {title}"
            if message:
                msg += f": {message}"
            self._log(msg)

        def _silent_showinfo(title, message=None, *args, **kwargs):
            _log_msg("info", title, message)
            return None

        def _silent_showwarning(title, message=None, *args, **kwargs):
            _log_msg("warning", title, message)
            return None

        def _silent_showerror(title, message=None, *args, **kwargs):
            _log_msg("error", title, message)
            return None

        def _silent_ask_bool(title, message=None, *args, **kwargs):
            text = f"{title} {message}" if message is not None else str(title)
            # 若包含“打开目录”，返回否；其他确认一律同意
            deny = ("打开目录" in text) or ("open" in text.lower() and "dir" in text.lower())
            _log_msg("ask", title, message)
            return False if deny else True

        def _silent_ask_yn(title, message=None, *args, **kwargs):
            text = f"{title} {message}" if message is not None else str(title)
            # askquestion 需要返回 'yes'/'no'
            deny = ("打开目录" in text) or ("open" in text.lower() and "dir" in text.lower())
            _log_msg("ask", title, message)
            return 'no' if deny else 'yes'

        try:
            if "showinfo" in saved:
                mb.showinfo = _silent_showinfo
            if "showwarning" in saved:
                mb.showwarning = _silent_showwarning
            if "showerror" in saved:
                mb.showerror = _silent_showerror
            if "askyesno" in saved:
                mb.askyesno = _silent_ask_bool
            if "askquestion" in saved:
                mb.askquestion = _silent_ask_yn
            return func(*args, **kwargs)
        finally:
            for name, fn in saved.items():
                setattr(mb, name, fn)

    def _auto_batch_query(self):
        """自动：在图像查看器中定位到当前天区目录并执行“批量查询(小行星/变星)”"""
        import os
        try:
            self._log("[自动] 开始批量查询(小行星/变星)...")
            # 切换到“FITS查看”页签
            self.notebook.select(self.viewer_frame)

            # 刷新目录树
            self.fits_viewer._refresh_directory_tree()

            # 依据当前选择构建天区下载目录路径：根/telescope/date/k_number
            selections = self.url_builder.get_current_selections()
            tel_name = selections.get('telescope_name', 'Unknown')
            date = selections.get('date', 'Unknown')
            k_number = selections.get('k_number', 'Unknown')
            base_download_dir = self.download_dir_var.get().strip()
            region_dir = os.path.join(base_download_dir, tel_name, date, k_number)

            # 在目录树中定位并选中该天区节点
            node = self._find_viewer_tree_node_by_path(region_dir)
            if node:
                tree = self.fits_viewer.directory_tree
                tree.selection_set(node)
                tree.focus(node)
                tree.see(node)
                self._log(f"[自动] 已选择天区目录: {region_dir}")
            else:
                self._log(f"[自动] 未找到天区目录节点: {region_dir}，将仍尝试执行批量查询")

            # 静默执行批量查询，屏蔽可能的弹窗
            use_local = False
            try:
                settings = self.config_manager.get_local_catalog_settings()
                use_local = bool(settings.get("auto_chain_use_local_query", False))
            except Exception:
                use_local = False
            if use_local and hasattr(self.fits_viewer, "_batch_query_local_asteroids_and_variables"):
                self._run_without_messageboxes(self.fits_viewer._batch_query_local_asteroids_and_variables)
            else:
                self._run_without_messageboxes(self.fits_viewer._batch_query_asteroids_and_variables)

            # 查询完成后，继续执行“批量导出未查询”
            self.root.after(500, self._auto_batch_export_unqueried)
        except Exception as e:
            self._log(f"[自动] 批量查询失败: {e}")
            import traceback
            self._log(traceback.format_exc())

    def _auto_batch_export_unqueried(self):
        """自动：执行“批量导出未查询”并静默处理所有弹窗"""
        try:
            self._log("[自动] 开始批量导出未查询...")
            # 确保停留在查看器页签并刷新目录树
            self.notebook.select(self.viewer_frame)
            self.fits_viewer._refresh_directory_tree()

            # 静默执行导出（将自动确认导出，且不会弹出“打开目录”提示）
            self._run_without_messageboxes(self.fits_viewer._batch_export_unqueried)

            self._log("[自动] 批量导出未查询完成")
        except Exception as e:
            self._log(f"[自动] 批量导出未查询失败: {e}")
            import traceback
            self._log(traceback.format_exc())
        finally:
            # 根据设置，决定是否继续执行OSS上传
            try:
                enabled = bool(self.auto_chain_oss_upload_var.get())
            except Exception:
                enabled = False
            if enabled:
                self._log("[自动] 已启用自动链OSS上传，500ms后开始上传...")
                self.root.after(500, self._auto_upload_to_oss)
            else:
                # 关闭自动链并恢复静默标志
                self._auto_chain_followups = False
                try:
                    self._auto_silent_mode = False
                except Exception:
                    pass
                try:
                    self.fits_viewer._auto_silent_mode = False
                except Exception:
                    pass


    def _auto_upload_to_oss(self):
        """自动：执行OSS上传并静默处理所有弹窗"""
        try:
            self._log("[自动] 开始上传到OSS...")
            # 确保停留在查看器页签并刷新目录树（上传实现依赖导出目录配置）
            self.notebook.select(self.viewer_frame)
            self.fits_viewer._refresh_directory_tree()
            # 静默执行OSS上传：自动确认上传，屏蔽完成/错误弹窗
            # 注意：_upload_to_oss 会在后台线程中执行实际上传，此处不等待完成
            self._run_without_messageboxes(self.fits_viewer._upload_to_oss)
            self._log("[自动] 已启动OSS上传（后台进行），详细进度见 oss_sync/oss_upload.log")
        except Exception as e:
            self._log(f"[自动] 启动OSS上传失败: {e}")
            import traceback
            self._log(traceback.format_exc())
        finally:
            # 关闭自动链，并恢复下载器的静默标志（viewer会在上传线程结束时恢复）
            self._auto_chain_followups = False
            try:
                self._auto_silent_mode = False
            except Exception:
                pass

    def _auto_full_day_all_systems_batch(self):
        """自动执行：全天全系统diff"""
        try:
            self._log("开始全天全系统diff...")

            # 开启静默模式，避免任何弹窗阻塞
            setattr(self, "_auto_silent_mode", True)
            # 全天全系统流程不涉及viewer链条，这里无需设置 viewer 的静默标志
            # 静默执行全天全系统diff（屏蔽确认对话框）
            self._run_without_messageboxes(self._full_day_all_systems_batch_process)

        except Exception as e:
            error_msg = f"自动全天全系统diff失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            if not getattr(self, "_auto_silent_mode", False):
                messagebox.showerror("错误", error_msg)


def main():
    """主函数"""
    app = FitsWebDownloaderGUI()
    app.run()


if __name__ == "__main__":
    main()