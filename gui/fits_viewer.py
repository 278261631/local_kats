#!/usr/bin/env python3
"""
FITS图像查看器
用于显示和分析FITS文件
"""

import os
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


class FitsImageViewer:
    """FITS图像查看器"""

    def __init__(self, parent_frame, get_download_dir_callback: Optional[Callable] = None,
                 get_template_dir_callback: Optional[Callable] = None,
                 get_diff_output_dir_callback: Optional[Callable] = None,
                 get_url_selections_callback: Optional[Callable] = None):
        self.parent_frame = parent_frame
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

        # 初始化diff_orb集成
        self.diff_orb = DiffOrbIntegration()

        # 创建界面
        self._create_widgets()

        # 延迟执行首次刷新（确保界面完全创建后）
        self.parent_frame.after(100, self._first_time_refresh)
        
    def _create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 5))

        # 文件信息标签
        self.file_info_label = ttk.Label(toolbar_frame, text="未选择文件")
        self.file_info_label.pack(side=tk.LEFT)

        # 显示图像按钮
        self.display_button = ttk.Button(toolbar_frame, text="显示图像",
                                       command=self._display_selected_image, state="disabled")
        self.display_button.pack(side=tk.LEFT, padx=(10, 0))

        # 降噪方式选择框架
        noise_frame = ttk.Frame(toolbar_frame)
        noise_frame.pack(side=tk.LEFT, padx=(5, 0))

        # 降噪方式标签
        ttk.Label(noise_frame, text="降噪方式:").pack(side=tk.LEFT)

        # 降噪方式复选框
        self.outlier_var = tk.BooleanVar(value=True)  # 默认选中outlier
        self.hot_cold_var = tk.BooleanVar(value=False)  # 默认不选中hot_cold

        self.outlier_checkbox = ttk.Checkbutton(noise_frame, text="Outlier",
                                              variable=self.outlier_var)
        self.outlier_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        self.hot_cold_checkbox = ttk.Checkbutton(noise_frame, text="Hot/Cold",
                                               variable=self.hot_cold_var)
        self.hot_cold_checkbox.pack(side=tk.LEFT, padx=(5, 0))

        # 对齐方式选择框架
        alignment_frame = ttk.Frame(toolbar_frame)
        alignment_frame.pack(side=tk.LEFT, padx=(5, 0))

        # 对齐方式标签
        ttk.Label(alignment_frame, text="对齐方式:").pack(side=tk.LEFT)

        # 对齐方式单选框
        self.alignment_var = tk.StringVar(value="rigid")  # 默认选择rigid

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
        self.diff_button = ttk.Button(toolbar_frame, text="执行Diff",
                                    command=self._execute_diff, state="disabled")
        self.diff_button.pack(side=tk.LEFT, padx=(5, 0))

        # 打开目录按钮
        self.open_dir_button = ttk.Button(toolbar_frame, text="打开下载目录",
                                        command=self._open_download_directory)
        self.open_dir_button.pack(side=tk.LEFT, padx=(5, 0))

        # 图像统计信息标签
        self.stats_label = ttk.Label(toolbar_frame, text="")
        self.stats_label.pack(side=tk.RIGHT)

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

        # 不在这里初始化目录树，等待首次刷新

    def _create_image_display(self, parent):
        """创建右侧图像显示区域"""
        # 右侧框架
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 创建图像显示区域
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 创建控制面板
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 显示模式选择
        ttk.Label(control_frame, text="显示模式:").pack(side=tk.LEFT, padx=(0, 5))
        self.display_mode = tk.StringVar(value="linear")
        mode_combo = ttk.Combobox(control_frame, textvariable=self.display_mode, 
                                 values=["linear", "log", "sqrt", "asinh"], 
                                 state="readonly", width=10)
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        mode_combo.bind('<<ComboboxSelected>>', self._on_display_mode_change)
        
        # 颜色映射选择
        ttk.Label(control_frame, text="颜色映射:").pack(side=tk.LEFT, padx=(0, 5))
        self.colormap = tk.StringVar(value="gray")
        cmap_combo = ttk.Combobox(control_frame, textvariable=self.colormap,
                                 values=["gray", "viridis", "plasma", "inferno", "hot", "cool"],
                                 state="readonly", width=10)
        cmap_combo.pack(side=tk.LEFT, padx=(0, 10))
        cmap_combo.bind('<<ComboboxSelected>>', self._on_colormap_change)
        
        # 刷新按钮
        refresh_btn = ttk.Button(control_frame, text="刷新显示", command=self._refresh_display)
        refresh_btn.pack(side=tk.LEFT, padx=(10, 0))

        # 保存按钮
        save_btn = ttk.Button(control_frame, text="保存图像", command=self._save_image)
        save_btn.pack(side=tk.LEFT, padx=(5, 0))

    def _first_time_refresh(self):
        """首次打开时自动刷新目录树"""
        if not self.first_refresh_done:
            self.first_refresh_done = True
            self.logger.info("首次打开图像查看器，自动刷新目录树")
            self._refresh_directory_tree()

    def _refresh_directory_tree(self):
        """刷新目录树"""
        try:
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

            # 更新状态标签
            status_text = f"已选择: {filename}"
            if is_download_file:
                status_text += " (下载文件)"
                if can_diff:
                    status_text += " [可执行Diff]"
            else:
                status_text += " (模板文件)"

            self.file_info_label.config(text=status_text)
            self.logger.info(f"已选择FITS文件: {filename}")
        else:
            # 选中的不是FITS文件
            self.selected_file_path = None
            self.display_button.config(state="disabled")
            self.diff_button.config(state="disabled")
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
        """执行diff操作"""
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

        try:
            # 禁用按钮
            self.diff_button.config(state="disabled", text="处理中...")
            self.parent_frame.update()  # 更新界面显示

            # 查找对应的模板文件
            template_file = self.diff_orb.find_template_file(self.selected_file_path, template_dir)

            if not template_file:
                messagebox.showwarning("警告", "未找到匹配的模板文件")
                self.diff_button.config(state="normal", text="执行Diff")
                return

            # 获取输出目录
            output_dir = self._get_diff_output_directory()

            # 获取选择的降噪方式
            noise_methods = []
            if self.outlier_var.get():
                noise_methods.append('outlier')
            if self.hot_cold_var.get():
                noise_methods.append('hot_cold')

            # 如果没有选择任何方式，默认使用outlier
            if not noise_methods:
                noise_methods = ['outlier']
                self.logger.warning("未选择降噪方式，使用默认的outlier方法")

            # 获取选择的对齐方式
            alignment_method = self.alignment_var.get()
            self.logger.info(f"选择的对齐方式: {alignment_method}")

            # 执行diff操作
            result = self.diff_orb.process_diff(self.selected_file_path, template_file, output_dir,
                                              noise_methods=noise_methods, alignment_method=alignment_method)

            if result and result.get('success'):
                # 显示结果摘要
                summary = self.diff_orb.get_diff_summary(result)
                messagebox.showinfo("Diff操作完成", summary)

                # 自动查看差异图像（不询问）
                # 尝试加载差异图像
                output_files = result.get('output_files', {})
                self.logger.info(f"可用的输出文件: {list(output_files.keys())}")

                # 按优先级尝试加载文件
                files_to_try = [
                    ('difference_fits', '差异FITS文件'),
                    ('marked_fits', '标记FITS文件'),
                    ('aligned_fits', '对齐FITS文件'),
                    ('reference_fits', '参考FITS文件')
                ]

                # 如果没有difference_fits，尝试显示差异图像的PNG版本
                if 'difference_fits' not in output_files:
                    # 查找差异相关的PNG文件
                    output_dir = result.get('output_directory')
                    if output_dir and os.path.exists(output_dir):
                        diff_pngs = list(Path(output_dir).glob("*difference*.png"))
                        if diff_pngs:
                            # 显示差异PNG文件的信息
                            png_file = str(diff_pngs[0])
                            messagebox.showinfo("差异图像",
                                f"生成了差异图像文件:\n{os.path.basename(png_file)}\n\n"
                                f"注意：diff_orb生成的是PNG格式的差异图像，\n"
                                f"将显示对齐后的FITS文件供参考。")
                            self.logger.info(f"找到差异PNG文件: {os.path.basename(png_file)}")

                            # 尝试打开PNG文件所在目录
                            try:
                                self._open_directory_in_explorer(output_dir)
                            except:
                                pass

                loaded = False
                for file_key, file_desc in files_to_try:
                    file_path = output_files.get(file_key)
                    if file_path and os.path.exists(file_path):
                        self.logger.info(f"加载{file_desc}: {os.path.basename(file_path)}")
                        if self.load_fits_file(file_path):
                            loaded = True
                            break
                        else:
                            self.logger.warning(f"加载{file_desc}失败")

                if not loaded:
                    # 如果都没有成功加载，尝试直接扫描输出目录
                    output_dir = result.get('output_directory')
                    if output_dir and os.path.exists(output_dir):
                        fits_files = list(Path(output_dir).glob("*.fits"))
                        if fits_files:
                            # 加载第一个找到的FITS文件
                            first_fits = str(fits_files[0])
                            self.logger.info(f"尝试加载目录中的FITS文件: {os.path.basename(first_fits)}")
                            if self.load_fits_file(first_fits):
                                loaded = True

                    if not loaded:
                        messagebox.showwarning("警告", "没有找到可以显示的结果文件")

                # 自动打开输出目录（不询问）
                try:
                    self._open_directory_in_explorer(output_dir)
                    self.logger.info(f"已自动打开结果目录: {output_dir}")
                except Exception as e:
                    self.logger.warning(f"打开结果目录失败: {str(e)}")
            else:
                messagebox.showerror("错误", "Diff操作失败")

        except Exception as e:
            self.logger.error(f"执行diff操作时出错: {str(e)}")
            messagebox.showerror("错误", f"执行diff操作时出错: {str(e)}")
        finally:
            # 恢复按钮状态
            self.diff_button.config(state="normal", text="执行Diff")

    def _get_diff_output_directory(self) -> str:
        """获取diff操作的输出目录"""
        from datetime import datetime

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

        # 生成当前日期相关的目录
        current_date = datetime.now().strftime("%Y%m%d")

        # 从选中文件名生成子目录名
        if self.selected_file_path:
            filename = os.path.basename(self.selected_file_path)
            name_without_ext = os.path.splitext(filename)[0]
            # 生成时间戳确保唯一性
            timestamp = datetime.now().strftime("%H%M%S")
            subdir_name = f"{name_without_ext}_{timestamp}"
        else:
            timestamp = datetime.now().strftime("%H%M%S")
            subdir_name = f"diff_result_{timestamp}"

        # 构建完整输出目录：根目录/YYYYMMDD/文件名_时间戳/
        output_dir = os.path.join(base_output_dir, current_date, subdir_name)

        # 创建目录
        os.makedirs(output_dir, exist_ok=True)

        self.logger.info(f"diff输出目录: {output_dir}")
        return output_dir
    
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
