#!/usr/bin/env python3
"""
URL构建器组件
用于构建和管理KATS数据下载URL
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging
from typing import Callable, Optional
from config_manager import ConfigManager
from calendar_widget import CalendarDialog


class URLBuilderFrame:
    """URL构建器界面组件"""
    
    def __init__(self, parent_frame, config_manager: ConfigManager, on_url_change: Optional[Callable] = None):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.on_url_change = on_url_change  # URL变化时的回调函数
        
        self.logger = logging.getLogger(__name__)
        
        # 创建界面变量
        self.telescope_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.k_number_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.url_template_var = tk.StringVar()
        
        # 创建界面
        self._create_widgets()
        
        # 加载上次的选择
        self._load_last_selections()
        
        # 绑定变化事件
        self._bind_events()
        
        # 初始构建URL
        self._update_url()
    
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
        self.k_number_combo = ttk.Combobox(
            row1,
            textvariable=self.k_number_var,
            values=self.config_manager.get_k_numbers(),
            state="readonly",
            width=8
        )
        self.k_number_combo.pack(side=tk.LEFT)
        
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
        self.telescope_var.trace('w', self._on_selection_change)
        self.date_var.trace('w', self._on_selection_change)
        self.k_number_var.trace('w', self._on_selection_change)
        self.url_template_var.trace('w', self._on_template_change)
    
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
