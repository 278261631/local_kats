#!/usr/bin/env python3
"""
URL构建器组件
用于构建和管理KATS数据下载URL
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging
import requests
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import Callable, Optional, List
from config_manager import ConfigManager
from calendar_widget import CalendarDialog


class RegionScanner:
    """天区扫描器 - 从URL中获取可用的天区列表"""

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        # 禁用代理
        self.session.proxies = {
            'http': None,
            'https': None
        }

        # 禁用SSL验证以避免证书问题
        self.session.verify = False

        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 设置更宽松的SSL适配器
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        import ssl

        # 创建自定义的HTTPAdapter
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                # 设置更宽松的SSL选项
                try:
                    context.set_ciphers('DEFAULT@SECLEVEL=1')
                except:
                    pass  # 如果设置失败就忽略
                kwargs['ssl_context'] = context
                return super().init_poolmanager(*args, **kwargs)

        # 挂载适配器
        self.session.mount('https://', SSLAdapter())

        self.logger = logging.getLogger(__name__)

    def scan_available_regions(self, base_url: str) -> List[str]:
        """
        扫描指定URL下可用的天区列表

        Args:
            base_url (str): 基础URL，不包含天区信息

        Returns:
            List[str]: 可用的天区列表，如 ['K001', 'K002', ...]
        """
        try:
            self.logger.info(f"开始扫描天区: {base_url}")

            # 尝试使用requests，如果失败则使用urllib
            try:
                response = self.session.get(base_url, timeout=self.timeout)
                response.raise_for_status()
                content = response.text
            except Exception as e:
                self.logger.warning(f"requests失败，尝试urllib: {str(e)}")
                content = self._get_content_with_urllib(base_url)

            # 解析HTML内容
            soup = BeautifulSoup(content, 'html.parser')

            regions = []

            # 查找所有链接
            for link in soup.find_all('a', href=True):
                href = link['href']

                # 检查是否是天区目录（K开头的目录）
                if self._is_region_directory(href):
                    region_name = self._extract_region_name(href)
                    if region_name and region_name not in regions:
                        regions.append(region_name)
                        self.logger.debug(f"找到天区: {region_name}")

            # 排序天区列表
            regions.sort()

            self.logger.info(f"扫描完成，找到 {len(regions)} 个天区")
            return regions

        except requests.RequestException as e:
            self.logger.error(f"网络请求失败: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"扫描过程出错: {str(e)}")
            raise

    def _is_region_directory(self, href: str) -> bool:
        """检查链接是否是天区目录"""
        # 移除查询参数和片段
        clean_href = href.split('?')[0].split('#')[0]

        # 提取目录名
        dir_name = clean_href.strip('/').split('/')[-1]

        # 检查是否符合天区命名规则（K开头，后跟数字）
        pattern = r'^K\d{3}$'
        return bool(re.match(pattern, dir_name, re.IGNORECASE))

    def _extract_region_name(self, href: str) -> str:
        """从href中提取天区名称"""
        # 移除查询参数和片段
        clean_href = href.split('?')[0].split('#')[0]

        # 提取目录名
        dir_name = clean_href.strip('/').split('/')[-1]

        # 返回大写的天区名称
        return dir_name.upper()

    def _get_content_with_urllib(self, url: str) -> str:
        """使用urllib获取网页内容（作为requests的备用方案）"""
        import urllib.request
        import urllib.error
        import ssl

        # 创建SSL上下文
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # 创建无代理的opener
        proxy_handler = urllib.request.ProxyHandler({})
        https_handler = urllib.request.HTTPSHandler(context=context)
        opener = urllib.request.build_opener(proxy_handler, https_handler)

        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }

        req = urllib.request.Request(url, headers=headers)

        with opener.open(req, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='ignore')


class URLBuilderFrame:
    """URL构建器界面组件"""

    def __init__(self, parent_frame, config_manager: ConfigManager, on_url_change: Optional[Callable] = None, on_scan_fits: Optional[Callable] = None, on_batch_process: Optional[Callable] = None, on_open_batch_output: Optional[Callable] = None):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.on_url_change = on_url_change  # URL变化时的回调函数
        self.on_scan_fits = on_scan_fits  # 扫描FITS文件时的回调函数
        self.on_batch_process = on_batch_process  # 批量处理时的回调函数
        self.on_open_batch_output = on_open_batch_output  # 打开批量输出目录时的回调函数

        self.logger = logging.getLogger(__name__)

        # 创建天区扫描器
        self.region_scanner = RegionScanner()

        # 创建界面变量
        self.telescope_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.k_number_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.url_template_var = tk.StringVar()

        # 天区相关变量
        self.available_regions = []
        self.is_scanning_regions = False
        self.last_scanned_url = ""  # 记录上次扫描的URL，避免重复扫描

        # 创建界面
        self._create_widgets()

        # 加载上次的选择
        self._load_last_selections()

        # 绑定变化事件
        self._bind_events()

        # 初始构建URL
        self._update_url()

        # 初始化后触发一次自动扫描
        self.parent_frame.after(1000, self._auto_scan_regions)

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.LabelFrame(self.parent_frame, text="URL构建器", padding=10)
        main_frame.pack(fill=tk.X, pady=(0, 10))

        # 第一行：望远镜选择
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(row1, text="望远镜:").pack(side=tk.LEFT, padx=(0, 5))
        self.telescope_combo = ttk.Combobox(
            row1,
            textvariable=self.telescope_var,
            values=self.config_manager.get_telescope_names(),
            state="readonly",
            width=8
        )
        self.telescope_combo.pack(side=tk.LEFT, padx=(0, 15))

        # 日期选择
        ttk.Label(row1, text="日期:").pack(side=tk.LEFT, padx=(0, 5))

        # 日期显示和选择框架
        date_frame = ttk.Frame(row1)
        date_frame.pack(side=tk.LEFT, padx=(0, 15))

        # 日期显示标签
        self.date_display_label = ttk.Label(date_frame, textvariable=self.date_var,
                                          relief='sunken', width=12, anchor='center')
        self.date_display_label.pack(side=tk.LEFT)

        # 日历按钮
        self.calendar_button = ttk.Button(date_frame, text="📅", width=3,
                                        command=self._show_calendar)
        self.calendar_button.pack(side=tk.LEFT, padx=(2, 0))

        # 今天按钮
        ttk.Button(row1, text="今天", command=self._set_today, width=6).pack(side=tk.LEFT, padx=(0, 15))

        # K序号选择
        ttk.Label(row1, text="天区:").pack(side=tk.LEFT, padx=(0, 5))

        # 天区选择框架
        region_frame = ttk.Frame(row1)
        region_frame.pack(side=tk.LEFT, padx=(0, 5))

        self.k_number_combo = ttk.Combobox(
            region_frame,
            textvariable=self.k_number_var,
            values=self.config_manager.get_k_numbers(),
            state="readonly",
            width=8
        )
        self.k_number_combo.pack(side=tk.LEFT)

        # 扫描天区按钮
        self.scan_regions_button = ttk.Button(
            region_frame,
            text="🔍",
            width=3,
            command=self._manual_scan_regions,
            state="disabled"  # 初始状态禁用，需要先选择望远镜和日期
        )
        self.scan_regions_button.pack(side=tk.LEFT, padx=(2, 0))

        # 天区状态标签
        self.region_status_label = ttk.Label(row1, text="", foreground="gray")
        self.region_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # 扫描FITS文件按钮
        self.scan_fits_button = ttk.Button(row1, text="扫描FITS文件", command=self._on_scan_fits_clicked)
        self.scan_fits_button.pack(side=tk.LEFT, padx=(15, 0))

        # 批量处理按钮
        self.batch_process_button = ttk.Button(row1, text="批量下载并Diff", command=self._on_batch_process_clicked, state="disabled")
        self.batch_process_button.pack(side=tk.LEFT, padx=(5, 0))

        # 打开批量输出目录按钮
        self.open_batch_output_button = ttk.Button(row1, text="打开输出目录", command=self._on_open_batch_output_clicked, state="disabled")
        self.open_batch_output_button.pack(side=tk.LEFT, padx=(5, 0))

        # 第二行：URL模板选择
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(row2, text="URL格式:").pack(side=tk.LEFT, padx=(0, 5))

        # URL模板选择下拉框
        template_options = self.config_manager.get_url_template_options()
        self.template_combo = ttk.Combobox(
            row2,
            textvariable=self.url_template_var,
            values=list(template_options.values()),
            state="readonly",
            width=25
        )
        self.template_combo.pack(side=tk.LEFT, padx=(0, 15))

        # 第三行：URL显示和控制
        row3 = ttk.Frame(main_frame)
        row3.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(row3, text="URL:").pack(side=tk.LEFT, padx=(0, 5))

        # URL显示框
        self.url_entry = ttk.Entry(row3, textvariable=self.url_var, state="readonly")
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # 复制按钮
        ttk.Button(row3, text="复制", command=self._copy_url, width=6).pack(side=tk.LEFT, padx=(0, 5))

        # 构建按钮
        ttk.Button(row3, text="构建URL", command=self._update_url, width=8).pack(side=tk.RIGHT)



    def _load_last_selections(self):
        """加载上次的选择"""
        last_selected = self.config_manager.get_last_selected()

        self.telescope_var.set(last_selected.get("telescope_name", "GY5"))
        self.date_var.set(last_selected.get("date", datetime.now().strftime('%Y%m%d')))
        self.k_number_var.set(last_selected.get("k_number", "K096"))

        # 加载URL模板类型
        current_template_type = self.config_manager.get_url_template_type()
        template_options = self.config_manager.get_url_template_options()
        template_display_name = template_options.get(current_template_type, template_options["standard"])
        self.url_template_var.set(template_display_name)

    def _bind_events(self):
        """绑定事件"""
        self.telescope_var.trace('w', self._on_telescope_or_date_change)
        self.date_var.trace('w', self._on_telescope_or_date_change)
        self.k_number_var.trace('w', self._on_selection_change)
        self.url_template_var.trace('w', self._on_template_change)

    def _on_telescope_or_date_change(self, *args):
        """望远镜或日期变化事件处理"""
        # 检查是否可以启用天区扫描按钮
        self._update_scan_button_state()

        # 自动触发天区扫描
        self._auto_scan_regions()

        # 更新URL和保存选择
        self._update_url()
        self._save_selections()

    def _on_selection_change(self, *args):
        """选择变化事件处理"""
        self._update_url()
        self._save_selections()

    def _on_template_change(self, *args):
        """URL模板变化事件处理"""
        try:
            # 根据显示名称找到对应的模板类型
            template_options = self.config_manager.get_url_template_options()
            selected_display_name = self.url_template_var.get()

            # 找到对应的模板类型
            template_type = None
            for type_key, display_name in template_options.items():
                if display_name == selected_display_name:
                    template_type = type_key
                    break

            if template_type:
                # 更新配置中的模板类型
                self.config_manager.update_url_template_type(template_type)
                self.logger.info(f"URL模板类型已更改为: {template_type}")

                # 更新URL
                self._update_url()

        except Exception as e:
            self.logger.error(f"更改URL模板类型失败: {str(e)}")

    def _update_url(self):
        """更新URL"""
        try:
            # 验证输入
            tel_name = self.telescope_var.get()
            date = self.date_var.get()
            k_number = self.k_number_var.get()

            if not tel_name or not date or not k_number:
                self.url_var.set("请选择所有参数")
                return

            # 验证日期格式
            if not self.config_manager.validate_date(date):
                self.url_var.set("日期格式无效 (需要YYYYMMDD)")
                return

            # 构建URL
            url = self.config_manager.build_url(tel_name, date, k_number)
            self.url_var.set(url)

            # 调用回调函数
            if self.on_url_change:
                self.on_url_change(url)

            self.logger.info(f"URL已更新: {url}")

        except Exception as e:
            error_msg = f"构建URL失败: {str(e)}"
            self.url_var.set(error_msg)
            self.logger.error(error_msg)

    def _save_selections(self):
        """保存当前选择"""
        try:
            self.config_manager.update_last_selected(
                telescope_name=self.telescope_var.get(),
                date=self.date_var.get(),
                k_number=self.k_number_var.get()
            )
        except Exception as e:
            self.logger.error(f"保存选择失败: {str(e)}")

    def _set_today(self):
        """设置为今天的日期"""
        today = datetime.now().strftime('%Y%m%d')
        self.date_var.set(today)

    def _show_calendar(self):
        """显示日历选择对话框"""
        try:
            current_date = self.date_var.get()

            # 获取根窗口
            root = self.parent_frame
            while root.master:
                root = root.master

            dialog = CalendarDialog(root, "选择日期", current_date)
            selected_date = dialog.show()

            if selected_date:
                self.date_var.set(selected_date)
                self.logger.info(f"通过日历选择日期: {selected_date}")
                # 手动触发更新，确保URL更新
                self._update_url()

        except Exception as e:
            self.logger.error(f"显示日历对话框失败: {str(e)}")
            messagebox.showerror("错误", f"显示日历失败: {str(e)}")

    def _update_scan_button_state(self):
        """更新天区扫描按钮状态"""
        tel_name = self.telescope_var.get()
        date = self.date_var.get()

        # 只有当望远镜和日期都选择了才启用扫描按钮
        if tel_name and date and self.config_manager.validate_date(date) and not self.is_scanning_regions:
            self.scan_regions_button.config(state="normal")
        else:
            self.scan_regions_button.config(state="disabled")

    def _auto_scan_regions(self):
        """自动扫描天区（在日期或望远镜变化时触发）"""
        tel_name = self.telescope_var.get()
        date = self.date_var.get()

        # 只有当望远镜和日期都有效时才自动扫描
        if tel_name and date and self.config_manager.validate_date(date) and not self.is_scanning_regions:
            # 延迟一点时间执行，避免用户快速切换时频繁扫描
            self.parent_frame.after(500, self._scan_regions)

    def _manual_scan_regions(self):
        """手动扫描天区（点击按钮触发）"""
        self._manual_scan = True
        # 清除上次扫描的URL，强制重新扫描
        self.last_scanned_url = ""
        self._scan_regions()

    def _scan_regions(self):
        """扫描可用的天区"""
        if self.is_scanning_regions:
            return

        tel_name = self.telescope_var.get()
        date = self.date_var.get()

        if not tel_name or not date:
            # 自动扫描时不显示警告，只有手动点击时才显示
            if hasattr(self, '_manual_scan') and self._manual_scan:
                messagebox.showwarning("警告", "请先选择望远镜和日期")
            return

        if not self.config_manager.validate_date(date):
            # 自动扫描时不显示警告，只有手动点击时才显示
            if hasattr(self, '_manual_scan') and self._manual_scan:
                messagebox.showwarning("警告", "日期格式无效")
            return

        # 构建不包含天区的基础URL
        base_url = self._build_base_url(tel_name, date)

        # 检查是否与上次扫描的URL相同，避免重复扫描
        if base_url == self.last_scanned_url:
            return

        # 在后台线程中扫描天区
        import threading

        def scan_thread():
            try:
                self.is_scanning_regions = True
                self.parent_frame.after(0, lambda: self.region_status_label.config(text="扫描中...", foreground="blue"))
                self.parent_frame.after(0, lambda: self.scan_regions_button.config(state="disabled"))

                # 扫描天区
                regions = self.region_scanner.scan_available_regions(base_url)

                # 记录扫描的URL
                self.last_scanned_url = base_url

                # 更新界面
                self.parent_frame.after(0, lambda: self._update_region_list(regions))

            except Exception as e:
                error_msg = f"扫描天区失败: {str(e)}"
                self.logger.error(error_msg)
                # 只有手动扫描时才显示错误对话框
                if hasattr(self, '_manual_scan') and self._manual_scan:
                    self.parent_frame.after(0, lambda: messagebox.showerror("错误", error_msg))
                self.parent_frame.after(0, lambda: self.region_status_label.config(text="扫描失败", foreground="red"))
            finally:
                self.is_scanning_regions = False
                self.parent_frame.after(0, self._update_scan_button_state)
                # 重置手动扫描标志
                if hasattr(self, '_manual_scan'):
                    self._manual_scan = False

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()

    def _build_base_url(self, tel_name: str, date: str) -> str:
        """构建不包含天区的基础URL"""
        url_template = self.config_manager.get_url_template()

        # 准备格式化参数（不包含k_number）
        format_params = {
            'tel_name': tel_name,
            'date': date,
            'k_number': ''  # 临时占位符
        }

        # 如果模板需要年份，添加年份参数
        if '{year_of_date}' in url_template:
            try:
                year_of_date = date[:4] if len(date) >= 4 else datetime.now().strftime('%Y')
                format_params['year_of_date'] = year_of_date
            except Exception:
                format_params['year_of_date'] = datetime.now().strftime('%Y')

        # 构建URL并移除k_number部分
        full_url = url_template.format(**format_params)
        # 移除末尾的空字符串部分（k_number占位符）
        base_url = full_url.rstrip('/')

        return base_url

    def _update_region_list(self, regions: List[str]):
        """更新天区列表"""
        self.available_regions = regions

        if regions:
            # 更新下拉框选项
            self.k_number_combo['values'] = regions

            # 如果当前选择的天区不在新列表中，清空选择
            current_selection = self.k_number_var.get()
            if current_selection not in regions:
                self.k_number_var.set('')

            # 更新状态标签
            self.region_status_label.config(
                text=f"找到 {len(regions)} 个天区",
                foreground="green"
            )

            self.logger.info(f"更新天区列表: {regions}")
        else:
            self.region_status_label.config(text="未找到天区", foreground="orange")

    def _copy_url(self):
        """复制URL到剪贴板"""
        try:
            url = self.url_var.get()
            if url and not url.startswith("请选择") and not url.startswith("日期格式"):
                self.parent_frame.clipboard_clear()
                self.parent_frame.clipboard_append(url)
                messagebox.showinfo("成功", "URL已复制到剪贴板")
            else:
                messagebox.showwarning("警告", "没有有效的URL可复制")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {str(e)}")

    def get_current_url(self) -> str:
        """获取当前构建的URL"""
        return self.url_var.get()

    def get_current_selections(self) -> dict:
        """获取当前选择的参数"""
        return {
            "telescope_name": self.telescope_var.get(),
            "date": self.date_var.get(),
            "k_number": self.k_number_var.get()
        }

    def set_selections(self, telescope_name: str = None, date: str = None, k_number: str = None):
        """设置选择的参数"""
        if telescope_name:
            self.telescope_var.set(telescope_name)
        if date:
            self.date_var.set(date)
        if k_number:
            self.k_number_var.set(k_number)

    def validate_current_selections(self) -> tuple:
        """
        验证当前选择

        Returns:
            tuple: (是否有效, 错误信息)
        """
        tel_name = self.telescope_var.get()
        date = self.date_var.get()
        k_number = self.k_number_var.get()

        if not tel_name:
            return False, "请选择望远镜"

        if not self.config_manager.validate_telescope_name(tel_name):
            return False, f"无效的望远镜名称: {tel_name}"

        if not date:
            return False, "请输入日期"

        if not self.config_manager.validate_date(date):
            return False, "日期格式无效，请使用YYYYMMDD格式"

        if not k_number:
            return False, "请选择天区序号"

        if not self.config_manager.validate_k_number(k_number):
            return False, f"无效的天区序号: {k_number}"

        return True, ""


    def _on_scan_fits_clicked(self):
        """扫描FITS文件按钮点击事件"""
        if self.on_scan_fits:
            self.on_scan_fits()

    def _on_batch_process_clicked(self):
        """批量处理按钮点击事件"""
        if self.on_batch_process:
            self.on_batch_process()

    def _on_open_batch_output_clicked(self):
        """打开批量输出目录按钮点击事件"""
        if self.on_open_batch_output:
            self.on_open_batch_output()

    def set_scan_button_state(self, state: str):
        """设置扫描按钮状态"""
        if hasattr(self, 'scan_fits_button'):
            self.scan_fits_button.config(state=state)

    def set_scan_button_text(self, text: str):
        """设置扫描按钮文本"""
        if hasattr(self, 'scan_fits_button'):
            self.scan_fits_button.config(text=text)

    def set_batch_button_state(self, state: str):
        """设置批量处理按钮状态"""
        if hasattr(self, 'batch_process_button'):
            self.batch_process_button.config(state=state)

    def set_open_batch_output_button_state(self, state: str):
        """设置打开批量输出目录按钮状态"""
        if hasattr(self, 'open_batch_output_button'):
            self.open_batch_output_button.config(state=state)



class URLBuilderDialog:
    """URL构建器对话框"""

    def __init__(self, parent, config_manager: ConfigManager):
        self.parent = parent
        self.config_manager = config_manager
        self.result = None

        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("URL构建器")
        self.dialog.geometry("600x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 创建URL构建器
        self.url_builder = URLBuilderFrame(self.dialog, config_manager)

        # 创建按钮
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="确定", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _on_ok(self):
        """确定按钮事件"""
        valid, error_msg = self.url_builder.validate_current_selections()
        if valid:
            self.result = {
                "url": self.url_builder.get_current_url(),
                "selections": self.url_builder.get_current_selections()
            }
            self.dialog.destroy()
        else:
            messagebox.showerror("验证失败", error_msg)

    def _on_cancel(self):
        """取消按钮事件"""
        self.dialog.destroy()

    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
