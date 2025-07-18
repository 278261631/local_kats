#!/usr/bin/env python3
"""
FITS图像查看器
用于显示和分析FITS文件
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import logging
from typing import Optional, Tuple


class FitsImageViewer:
    """FITS图像查看器"""
    
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.current_fits_data = None
        self.current_header = None
        self.current_file_path = None
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 创建界面
        self._create_widgets()
        
    def _create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 文件信息标签
        self.file_info_label = ttk.Label(toolbar_frame, text="未加载文件")
        self.file_info_label.pack(side=tk.LEFT)
        
        # 图像统计信息标签
        self.stats_label = ttk.Label(toolbar_frame, text="")
        self.stats_label.pack(side=tk.RIGHT)
        
        # 创建图像显示区域
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 创建控制面板
        control_frame = ttk.Frame(main_frame)
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
    
    def clear_display(self):
        """清除显示"""
        self.current_fits_data = None
        self.current_header = None
        self.current_file_path = None
        
        self.figure.clear()
        self.canvas.draw()
        
        self.file_info_label.config(text="未加载文件")
        self.stats_label.config(text="")
    
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
