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
    
    def __init__(self):
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

        # 创建界面
        self._create_widgets()

        # 加载配置
        self._load_config()
        
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

        # 创建日志标签页
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="日志")

        # 初始化各个标签页
        self._create_scan_widgets()
        self._create_batch_status_widgets()
        self._create_viewer_widgets()
        self._create_advanced_settings_widgets()
        self._create_log_widgets()
        
    def _create_scan_widgets(self):
        """创建扫描和下载界面"""
        # URL构建器区域
        self.url_builder = URLBuilderFrame(self.scan_frame, self.config_manager, self._on_url_change, self._start_scan, self._batch_process, self._open_batch_output_directory, self._full_day_batch_process, self._full_day_all_systems_batch_process)

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
        file_frame = ttk.LabelFrame(self.viewer_frame, text="文件选择", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(file_frame, text="从下载目录选择", command=self._select_from_download_dir).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="选择其他FITS文件", command=self._select_fits_file).pack(side=tk.LEFT, padx=(10, 0))

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
            file_selection_frame=file_frame  # 传递文件选择框架
        )

        # 设置diff_orb的GUI回调
        if self.fits_viewer.diff_orb:
            self.fits_viewer.diff_orb.gui_callback = self.get_error_logger_callback()

    def _create_advanced_settings_widgets(self):
        """创建高级设置界面"""
        # 创建主容器
        main_container = ttk.Frame(self.advanced_settings_frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

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

        # 第五行：GPS和MPC设置
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
            elif diff_output_dir:
                # 如果没有设置detected目录，但有diff输出目录，自动设置为diff输出目录下的detected子目录
                detected_dir = os.path.join(diff_output_dir, "detected")
                self.detected_dir_var.set(detected_dir)

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

        # 禁用按钮
        self.url_builder.set_batch_button_state("disabled")
        self.url_builder.set_scan_button_state("disabled")
        self.download_button.config(state="disabled")

        # 在新线程中执行批量处理
        thread = threading.Thread(target=self._batch_process_thread, args=(selected_files,))
        thread.daemon = True
        thread.start()

    def _batch_process_thread(self, selected_files):
        """批量处理线程"""
        try:
            # 获取线程数配置
            thread_count = self.url_builder.get_thread_count()

            self._log("=" * 60)
            self._log("开始批量处理")
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

            # 步骤1: 下载文件（启用ASTAP处理）
            self._log("\n步骤1: 下载文件（启用ASTAP处理）")
            self._log("-" * 60)
            self.root.after(0, lambda: self.status_label.config(text="正在下载并处理ASTAP..."))

            # 创建下载器（强制启用ASTAP）
            self.downloader = FitsDownloader(
                max_workers=self.max_workers_var.get(),
                retry_times=self.retry_times_var.get(),
                timeout=self.timeout_var.get(),
                enable_astap=True,  # 批量处理时强制启用ASTAP
                astap_config_path="config/url_config.json"
            )

            # 检查ASTAP处理器是否成功初始化
            if self.downloader.astap_processor:
                self._log("✓ ASTAP处理器已启用")
            else:
                self._log("✗ 警告: ASTAP处理器未启用，WCS对齐可能失败")
                self._log("  请检查ASTAP是否正确安装和配置")

            # 准备URL列表
            urls = [url for filename, url in selected_files]

            # 执行下载
            self._log(f"开始下载 {len(urls)} 个文件...")
            self.root.after(0, lambda: self.batch_progress_label.config(
                text=f"正在下载 {len(urls)} 个文件..."))

            # 更新所有文件状态为下载中
            for filename, url in selected_files:
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_DOWNLOADING))

            self._download_with_progress(urls, actual_download_dir)
            self._log("下载完成")

            # 步骤1.5: 检查WCS信息并准备文件列表
            self._log("\n步骤1.5: 检查WCS信息")
            self._log("-" * 60)
            self.root.after(0, lambda: self.batch_progress_label.config(text="检查WCS信息..."))

            # 获取下载的文件列表
            downloaded_files = []
            for filename, url in selected_files:
                file_path = os.path.join(actual_download_dir, filename)
                if os.path.exists(file_path):
                    downloaded_files.append(file_path)
                    # 更新状态为下载成功
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_SUCCESS))
                else:
                    self._log(f"警告: 文件未找到 {filename}")
                    # 更新状态为下载失败
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_FAILED, "文件未找到"))

            self._log(f"找到 {len(downloaded_files)} 个已下载的文件")

            # 检查每个文件的WCS信息
            files_with_wcs = []
            files_without_wcs = []

            for file_path in downloaded_files:
                filename = os.path.basename(file_path)

                # 更新状态为检查WCS
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_WCS_CHECKING))

                try:
                    # 检查是否有WCS信息
                    from astropy.io import fits as astropy_fits
                    with astropy_fits.open(file_path) as hdul:
                        header = hdul[0].header
                        has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                    if has_wcs:
                        files_with_wcs.append(file_path)
                        self._log(f"  {filename}: ✓ 已有WCS信息")
                        # 更新状态为有WCS
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_WCS_FOUND))
                    else:
                        files_without_wcs.append(file_path)
                        self._log(f"  {filename}: ✗ 缺少WCS信息")
                        # 更新状态为缺少WCS
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_WCS_MISSING))
                except Exception as e:
                    files_without_wcs.append(file_path)
                    self._log(f"  {filename}: 检查WCS时出错: {str(e)}")
                    # 更新状态为缺少WCS（错误）
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_WCS_MISSING, f"错误: {str(e)}"))

            self._log(f"WCS检查完成: {len(files_with_wcs)} 个有WCS, {len(files_without_wcs)} 个无WCS")

            # 对没有WCS信息的文件执行ASTAP处理
            if files_without_wcs:
                self._log(f"\n对 {len(files_without_wcs)} 个没有WCS信息的文件执行ASTAP处理...")

                if self.fits_viewer.astap_processor:
                    self.root.after(0, lambda: self.batch_progress_label.config(
                        text=f"正在为 {len(files_without_wcs)} 个文件添加WCS信息..."))

                    # 使用线程池并行处理ASTAP（与diff操作使用相同的线程数）
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    import threading

                    # 创建线程锁用于更新计数器
                    astap_counter_lock = threading.Lock()
                    astap_completed_count = 0
                    astap_success_count = 0
                    astap_fail_count = 0

                    # 创建线程池，使用与diff操作相同的线程数
                    with ThreadPoolExecutor(max_workers=thread_count) as executor:
                        # 提交所有ASTAP任务
                        future_to_file = {}
                        for file_path in files_without_wcs:
                            filename = os.path.basename(file_path)
                            
                            # 更新状态为ASTAP处理中
                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_ASTAP_PROCESSING))

                            future = executor.submit(
                                self._process_single_astap,
                                file_path
                            )
                            future_to_file[future] = file_path

                        # 处理完成的ASTAP任务
                        for future in as_completed(future_to_file):
                            file_path = future_to_file[future]
                            filename = os.path.basename(file_path)

                            with astap_counter_lock:
                                astap_completed_count += 1
                                current_completed = astap_completed_count

                            # 更新进度显示
                            progress_text = f"ASTAP处理中 ({current_completed}/{len(files_without_wcs)}): 并行处理中..."
                            self.root.after(0, lambda t=progress_text: self.batch_progress_label.config(text=t))

                            try:
                                result = future.result()
                                
                                # 记录日志
                                self._log(f"\n[{current_completed}/{len(files_without_wcs)}] {filename}")

                                # 检查result是否为字典（正确处理ASTAP结果）
                                if isinstance(result, dict) and 'success' in result:
                                    if result['success']:
                                        # ASTAP处理成功，重新检查WCS
                                        from astropy.io import fits as astropy_fits
                                        with astropy_fits.open(file_path) as hdul:
                                            header = hdul[0].header
                                            has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                                        if has_wcs:
                                            files_with_wcs.append(file_path)
                                            astap_success_count += 1
                                            self._log(f"  ✓ ASTAP处理成功，已添加WCS信息")
                                            # 更新状态为ASTAP成功
                                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                                f, BatchStatusWidget.STATUS_ASTAP_SUCCESS))
                                        else:
                                            astap_fail_count += 1
                                            self._log(f"  ✗ ASTAP处理完成但未添加WCS信息")
                                            # 更新状态为ASTAP失败
                                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                                f, BatchStatusWidget.STATUS_ASTAP_FAILED, "未添加WCS"))
                                    else:
                                        astap_fail_count += 1
                                        error_msg = result.get('message', '未知错误') if isinstance(result, dict) else str(result)
                                        self._log(f"  ✗ ASTAP处理失败: {error_msg}")
                                        # 更新状态为ASTAP失败
                                        self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                            f, BatchStatusWidget.STATUS_ASTAP_FAILED, msg))
                                else:
                                    # 处理意外返回类型
                                    astap_fail_count += 1
                                    error_msg = f"意外的返回类型: {type(result)}"
                                    self._log(f"  ✗ ASTAP处理失败: {error_msg}")
                                    # 更新状态为ASTAP失败
                                    self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                        f, BatchStatusWidget.STATUS_ASTAP_FAILED, msg))

                                # 更新统计信息
                                stats_text = f"ASTAP已完成: {current_completed}/{len(files_without_wcs)} | 成功: {astap_success_count} | 失败: {astap_fail_count}"
                                self.root.after(0, lambda t=stats_text: self.batch_stats_label.config(text=t))

                            except Exception as e:
                                astap_fail_count += 1
                                self._log(f"  ✗ ASTAP处理异常: {str(e)}")
                                self.root.after(0, lambda f=filename, err=str(e): self.batch_status_widget.update_status(
                                    f, BatchStatusWidget.STATUS_ASTAP_FAILED, err))

                    self._log(f"ASTAP处理完成，现在共有 {len(files_with_wcs)} 个文件包含WCS信息")
                    self._log(f"ASTAP处理统计: 成功 {astap_success_count} 个，失败 {astap_fail_count} 个")
                else:
                    self._log("警告: ASTAP处理器不可用，无法添加WCS信息")

            if not files_with_wcs:
                self._log("没有包含WCS信息的文件，批量处理结束")
                return

            # 步骤2: 执行Diff操作（只处理有WCS信息的文件）
            self._log("\n步骤2: 执行Diff操作")
            self._log("-" * 60)
            self.root.after(0, lambda: self.batch_progress_label.config(
                text=f"准备执行Diff操作 ({len(files_with_wcs)} 个文件)..."))

            # 对每个有WCS信息的文件执行diff
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

            # 完成
            self._log("\n" + "=" * 60)
            self._log("批量处理完成")
            self._log(f"成功: {success_count} 个")
            self._log(f"失败: {fail_count} 个")
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

            self.root.after(0, lambda: self.status_label.config(text=f"批量处理完成 (成功:{success_count} 失败:{fail_count})"))

            # 启用打开输出目录按钮
            if self.last_batch_output_root and os.path.exists(self.last_batch_output_root):
                self.root.after(0, lambda: self.url_builder.set_open_batch_output_button_state("normal"))

        except Exception as e:
            error_msg = f"批量处理失败: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
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

            # 按天区分组处理
            from collections import defaultdict
            files_by_region = defaultdict(list)
            for filename, url, k_number in all_files_to_process:
                files_by_region[k_number].append((filename, url))

            # 对每个天区执行批量处理
            for region_idx, (k_number, region_files) in enumerate(files_by_region.items(), 1):
                self._log(f"\n处理天区 [{region_idx}/{len(files_by_region)}]: {k_number}")
                self._log(f"文件数量: {len(region_files)}")

                # 调用现有的批量处理线程函数
                # 注意：这里直接调用内部处理逻辑，而不是启动新线程
                self._batch_process_region(region_files, tel_name, date, k_number)

            self._log("\n" + "=" * 60)
            self._log("全天下载diff处理完成！")
            self._log("=" * 60)

            # 显示完成消息
            self.root.after(0, lambda: messagebox.showinfo("完成", "全天下载diff处理完成！"))

        except Exception as e:
            error_msg = f"全天批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))

    def _batch_process_region(self, selected_files, tel_name, date, k_number):
        """
        处理单个天区的批量下载和diff操作
        这个方法复用现有的批量处理逻辑

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

            # 步骤1: 下载文件（启用ASTAP处理）
            self._log("\n步骤1: 下载文件（启用ASTAP处理）")
            self._log("-" * 60)
            self.root.after(0, lambda: self.status_label.config(text=f"正在下载 {k_number} 的文件..."))

            # 创建下载器（强制启用ASTAP）
            self.downloader = FitsDownloader(
                max_workers=self.max_workers_var.get(),
                retry_times=self.retry_times_var.get(),
                timeout=self.timeout_var.get(),
                enable_astap=True,
                astap_config_path="config/url_config.json"
            )

            # 准备URL列表
            urls = [url for filename, url in selected_files]

            # 执行下载
            self._log(f"开始下载 {len(urls)} 个文件...")

            # 更新所有文件状态为下载中
            for filename, url in selected_files:
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_DOWNLOADING))

            self._download_with_progress(urls, actual_download_dir)
            self._log("下载完成")

            # 步骤1.5: 检查WCS信息并准备文件列表
            self._log("\n步骤1.5: 检查WCS信息")
            self._log("-" * 60)

            # 获取下载的文件列表
            downloaded_files = []
            for filename, url in selected_files:
                file_path = os.path.join(actual_download_dir, filename)
                if os.path.exists(file_path):
                    downloaded_files.append(file_path)
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_SUCCESS))
                else:
                    self._log(f"警告: 文件未找到 {filename}")
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_DOWNLOAD_FAILED, "文件未找到"))

            self._log(f"找到 {len(downloaded_files)} 个已下载的文件")

            # 检查每个文件的WCS信息
            files_with_wcs = []
            files_without_wcs = []

            for file_path in downloaded_files:
                filename = os.path.basename(file_path)
                self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                    f, BatchStatusWidget.STATUS_WCS_CHECKING))

                try:
                    from astropy.io import fits as astropy_fits
                    with astropy_fits.open(file_path) as hdul:
                        header = hdul[0].header
                        has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                    if has_wcs:
                        files_with_wcs.append(file_path)
                        self._log(f"  {filename}: ✓ 已有WCS信息")
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_WCS_FOUND))
                    else:
                        files_without_wcs.append(file_path)
                        self._log(f"  {filename}: ✗ 缺少WCS信息")
                        self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                            f, BatchStatusWidget.STATUS_WCS_MISSING))
                except Exception as e:
                    files_without_wcs.append(file_path)
                    self._log(f"  {filename}: 检查WCS时出错: {str(e)}")
                    self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                        f, BatchStatusWidget.STATUS_WCS_MISSING, f"错误: {str(e)}"))

            self._log(f"WCS检查完成: {len(files_with_wcs)} 个有WCS, {len(files_without_wcs)} 个无WCS")

            # 对没有WCS信息的文件执行ASTAP处理
            if files_without_wcs:
                self._log(f"\n对 {len(files_without_wcs)} 个没有WCS信息的文件执行ASTAP处理...")

                if self.fits_viewer.astap_processor:
                    self.root.after(0, lambda: self.batch_progress_label.config(
                        text=f"正在为 {len(files_without_wcs)} 个文件添加WCS信息..."))

                    # 使用线程池并行处理ASTAP（与diff操作使用相同的线程数）
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    import threading

                    # 创建线程锁用于更新计数器
                    astap_counter_lock = threading.Lock()
                    astap_completed_count = 0
                    astap_success_count = 0
                    astap_fail_count = 0

                    # 创建线程池，使用与diff操作相同的线程数
                    with ThreadPoolExecutor(max_workers=thread_count) as executor:
                        # 提交所有ASTAP任务
                        future_to_file = {}
                        for file_path in files_without_wcs:
                            filename = os.path.basename(file_path)

                            # 更新状态为ASTAP处理中
                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                f, BatchStatusWidget.STATUS_ASTAP_PROCESSING))

                            future = executor.submit(
                                self._process_single_astap,
                                file_path
                            )
                            future_to_file[future] = file_path

                        # 处理完成的ASTAP任务
                        for future in as_completed(future_to_file):
                            file_path = future_to_file[future]
                            filename = os.path.basename(file_path)

                            with astap_counter_lock:
                                astap_completed_count += 1
                                current_completed = astap_completed_count

                            # 更新进度显示
                            progress_text = f"ASTAP处理中 ({current_completed}/{len(files_without_wcs)}): 并行处理中..."
                            self.root.after(0, lambda t=progress_text: self.batch_progress_label.config(text=t))

                            try:
                                result = future.result()

                                # 记录日志
                                self._log(f"\n[{current_completed}/{len(files_without_wcs)}] {filename}")

                                # 检查result是否为字典（正确处理ASTAP结果）
                                if isinstance(result, dict) and 'success' in result:
                                    if result['success']:
                                        # ASTAP处理成功，重新检查WCS
                                        from astropy.io import fits as astropy_fits
                                        with astropy_fits.open(file_path) as hdul:
                                            header = hdul[0].header
                                            has_wcs = 'CRVAL1' in header and 'CRVAL2' in header

                                        if has_wcs:
                                            files_with_wcs.append(file_path)
                                            astap_success_count += 1
                                            self._log(f"  ✓ ASTAP处理成功，已添加WCS信息")
                                            # 更新状态为ASTAP成功
                                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                                f, BatchStatusWidget.STATUS_ASTAP_SUCCESS))
                                        else:
                                            astap_fail_count += 1
                                            self._log(f"  ✗ ASTAP处理完成但未添加WCS信息")
                                            # 更新状态为ASTAP失败
                                            self.root.after(0, lambda f=filename: self.batch_status_widget.update_status(
                                                f, BatchStatusWidget.STATUS_ASTAP_FAILED, "未添加WCS"))
                                    else:
                                        astap_fail_count += 1
                                        error_msg = result.get('message', '未知错误') if isinstance(result, dict) else str(result)
                                        self._log(f"  ✗ ASTAP处理失败: {error_msg}")
                                        # 更新状态为ASTAP失败
                                        self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                            f, BatchStatusWidget.STATUS_ASTAP_FAILED, msg))
                                else:
                                    # 处理意外返回类型
                                    astap_fail_count += 1
                                    error_msg = f"意外的返回类型: {type(result)}"
                                    self._log(f"  ✗ ASTAP处理失败: {error_msg}")
                                    # 更新状态为ASTAP失败
                                    self.root.after(0, lambda f=filename, msg=error_msg: self.batch_status_widget.update_status(
                                        f, BatchStatusWidget.STATUS_ASTAP_FAILED, msg))

                                # 更新统计信息
                                stats_text = f"ASTAP已完成: {current_completed}/{len(files_without_wcs)} | 成功: {astap_success_count} | 失败: {astap_fail_count}"
                                self.root.after(0, lambda t=stats_text: self.batch_stats_label.config(text=t))

                            except Exception as e:
                                astap_fail_count += 1
                                self._log(f"  ✗ ASTAP处理异常: {str(e)}")
                                self.root.after(0, lambda f=filename, err=str(e): self.batch_status_widget.update_status(
                                    f, BatchStatusWidget.STATUS_ASTAP_FAILED, err))

                    self._log(f"\nASTAP处理完成: 成功 {astap_success_count} 个, 失败 {astap_fail_count} 个")
                    self._log(f"现在共有 {len(files_with_wcs)} 个文件包含WCS信息")
                else:
                    self._log("警告: ASTAP处理器不可用，无法添加WCS信息")

            if not files_with_wcs:
                self._log("没有包含WCS信息的文件，跳过该天区")
                return

            # 继续执行diff操作（调用现有的diff处理逻辑）
            self._execute_diff_for_files(files_with_wcs, thread_count)

        except Exception as e:
            self._log(f"处理天区 {k_number} 时出错: {str(e)}")
            import traceback
            self._log(traceback.format_exc())

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

                    # 按天区分组处理
                    from collections import defaultdict
                    files_by_region = defaultdict(list)
                    for filename, url, tel_name_item, k_number in system_files_to_process:
                        files_by_region[k_number].append((filename, url))

                    # 对每个天区执行批量处理
                    for region_idx, (k_number, region_files) in enumerate(files_by_region.items(), 1):
                        self._log(f"\n  处理天区 [{region_idx}/{len(files_by_region)}]: {k_number}")
                        self._log(f"  文件数量: {len(region_files)}")

                        # 调用现有的批量处理逻辑
                        self._batch_process_region(region_files, tel_name, date, k_number)

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
            self.root.after(0, lambda: messagebox.showinfo("完成", f"全天全系统下载diff处理完成！\n总共处理了 {total_files_processed} 个文件"))

        except Exception as e:
            error_msg = f"全天全系统批量处理失败: {str(e)}"
            self._log(error_msg)
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.url_builder.set_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_full_day_all_systems_batch_button_state("normal"))
            self.root.after(0, lambda: self.url_builder.set_scan_button_state("normal"))
            self.root.after(0, lambda: self.download_button.config(state="normal"))
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

            # 保存下载目录、模板目录和diff输出目录
            download_dir = self.download_dir_var.get().strip()
            template_dir = self.template_dir_var.get().strip()
            diff_output_dir = self.diff_output_dir_var.get().strip()
            if download_dir or template_dir or diff_output_dir:
                update_data = {}
                if download_dir:
                    update_data['download_directory'] = download_dir
                if template_dir:
                    update_data['template_directory'] = template_dir
                if diff_output_dir:
                    update_data['diff_output_directory'] = diff_output_dir
                self.config_manager.update_last_selected(**update_data)

            self._log("配置已保存")

        except Exception as e:
            self._log(f"保存配置失败: {str(e)}")
        finally:
            self.root.destroy()


def main():
    """主函数"""
    app = FitsWebDownloaderGUI()
    app.run()


if __name__ == "__main__":
    main()