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
        self.root.geometry("1200x800")

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
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建扫描和下载标签页
        self.scan_frame = ttk.Frame(notebook)
        notebook.add(self.scan_frame, text="扫描和下载")
        
        # 创建图像查看标签页
        self.viewer_frame = ttk.Frame(notebook)
        notebook.add(self.viewer_frame, text="图像查看")
        
        # 创建日志标签页
        self.log_frame = ttk.Frame(notebook)
        notebook.add(self.log_frame, text="日志")
        
        # 初始化各个标签页
        self._create_scan_widgets()
        self._create_viewer_widgets()
        self._create_log_widgets()
        
    def _create_scan_widgets(self):
        """创建扫描和下载界面"""
        # URL构建器区域
        self.url_builder = URLBuilderFrame(self.scan_frame, self.config_manager, self._on_url_change, self._start_scan)

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
        
        # 下载参数
        params_frame = ttk.Frame(download_frame)
        params_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(params_frame, text="并发数:").pack(side=tk.LEFT)
        self.max_workers_var = tk.IntVar(value=1)
        ttk.Spinbox(params_frame, from_=1, to=3, textvariable=self.max_workers_var, width=5).pack(side=tk.LEFT, padx=(5, 15))

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

        # 创建FITS查看器，传递回调函数
        self.fits_viewer = FitsImageViewer(
            self.viewer_frame,
            get_download_dir_callback=self._get_download_dir,
            get_template_dir_callback=self._get_template_dir,
            get_diff_output_dir_callback=self._get_diff_output_dir,
            get_url_selections_callback=self._get_url_selections
        )
        
    def _create_log_widgets(self):
        """创建日志界面"""
        # 日志显示区域
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=30, width=100)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 日志控制按钮
        log_control_frame = ttk.Frame(self.log_frame)
        log_control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(log_control_frame, text="清除日志", command=self._clear_log).pack(side=tk.LEFT)
        ttk.Button(log_control_frame, text="保存日志", command=self._save_log).pack(side=tk.LEFT, padx=(10, 0))

    def _load_config(self):
        """加载配置"""
        try:
            # 加载下载设置
            download_settings = self.config_manager.get_download_settings()
            self.max_workers_var.set(download_settings.get("max_workers", 1))
            self.retry_times_var.set(download_settings.get("retry_times", 3))
            self.timeout_var.set(download_settings.get("timeout", 30))

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
            self._log(f"diff结果将保存到: {directory}/YYYYMMDD/文件名相关目录/")
            
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

    def _append_log(self, message):
        """在日志文本框中添加消息"""
        self.log_text.insert(tk.END, message)
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

    def _get_url_selections(self):
        """获取URL选择参数的回调函数"""
        return self.url_builder.get_current_selections()

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
