#!/usr/bin/env python3
"""
仅测试图表显示功能
解决matplotlib在PyCharm中的显示问题
"""

import os
import sys
import time
import numpy as np
from datetime import datetime
from collections import deque

# 设置matplotlib后端
import matplotlib
matplotlib.use('TkAgg')  # 强制使用TkAgg后端，确保独立窗口显示
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class TestPlotter:
    """测试图表显示器"""
    
    def __init__(self, max_points=20):
        self.max_points = max_points
        self.timestamps = deque(maxlen=max_points)
        self.fwhm_values = deque(maxlen=max_points)
        self.ellipticity_values = deque(maxlen=max_points)
        self.n_sources_values = deque(maxlen=max_points)
        self.background_rms_values = deque(maxlen=max_points)
        
        # 设置matplotlib为交互模式
        plt.ion()
        
        # 创建图形和子图
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
        self.fig.suptitle('FITS图像质量实时监控测试', fontsize=14, fontweight='bold')
        
        # 初始化子图
        self.ax_fwhm = self.axes[0, 0]
        self.ax_ellipticity = self.axes[0, 1]
        self.ax_sources = self.axes[1, 0]
        self.ax_background = self.axes[1, 1]
        
        # 设置子图标题和标签
        self.ax_fwhm.set_title('FWHM (像素)')
        self.ax_fwhm.set_ylabel('FWHM')
        self.ax_fwhm.grid(True, alpha=0.3)
        
        self.ax_ellipticity.set_title('椭圆度')
        self.ax_ellipticity.set_ylabel('椭圆度')
        self.ax_ellipticity.grid(True, alpha=0.3)
        
        self.ax_sources.set_title('检测到的源数量')
        self.ax_sources.set_ylabel('源数量')
        self.ax_sources.grid(True, alpha=0.3)
        
        self.ax_background.set_title('背景RMS')
        self.ax_background.set_ylabel('RMS')
        self.ax_background.grid(True, alpha=0.3)
        
        # 初始化线条
        self.line_fwhm, = self.ax_fwhm.plot([], [], 'b-o', markersize=4)
        self.line_ellipticity, = self.ax_ellipticity.plot([], [], 'r-o', markersize=4)
        self.line_sources, = self.ax_sources.plot([], [], 'g-o', markersize=4)
        self.line_background, = self.ax_background.plot([], [], 'm-o', markersize=4)
        
        plt.tight_layout()
        
        # 显示窗口
        self.fig.show()
        
        print("图表窗口已创建，请检查是否在独立窗口中显示")
    
    def add_test_data(self, i):
        """添加测试数据"""
        timestamp = datetime.now()
        
        # 生成模拟数据
        fwhm = 2.0 + 0.5 * np.sin(i * 0.3) + np.random.normal(0, 0.1)
        ellipticity = 0.15 + 0.05 * np.cos(i * 0.2) + np.random.normal(0, 0.02)
        n_sources = int(45 + 10 * np.sin(i * 0.1) + np.random.normal(0, 3))
        background_rms = 100 + 20 * np.sin(i * 0.4) + np.random.normal(0, 5)
        
        # 添加数据
        self.timestamps.append(timestamp)
        self.fwhm_values.append(fwhm)
        self.ellipticity_values.append(ellipticity)
        self.n_sources_values.append(max(0, n_sources))
        self.background_rms_values.append(max(0, background_rms))
        
        # 更新图表
        self.update_plots()
        
        print(f"数据点 {i+1}: FWHM={fwhm:.2f}, 椭圆度={ellipticity:.3f}, 源数量={n_sources}, 背景RMS={background_rms:.1f}")
    
    def update_plots(self):
        """更新所有图表"""
        if len(self.timestamps) < 2:
            return
        
        # 转换时间戳为相对时间（秒）
        time_points = [(t - self.timestamps[0]).total_seconds() for t in self.timestamps]
        
        # 更新FWHM图表
        self.line_fwhm.set_data(time_points, self.fwhm_values)
        self.ax_fwhm.relim()
        self.ax_fwhm.autoscale_view()
        
        # 更新椭圆度图表
        self.line_ellipticity.set_data(time_points, self.ellipticity_values)
        self.ax_ellipticity.relim()
        self.ax_ellipticity.autoscale_view()
        
        # 更新源数量图表
        self.line_sources.set_data(time_points, self.n_sources_values)
        self.ax_sources.relim()
        self.ax_sources.autoscale_view()
        
        # 更新背景RMS图表
        self.line_background.set_data(time_points, self.background_rms_values)
        self.ax_background.relim()
        self.ax_background.autoscale_view()
        
        # 刷新图表
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
    
    def close(self):
        """关闭图表窗口"""
        plt.close(self.fig)


def main():
    """主函数"""
    print("=" * 60)
    print("FITS监控系统 - 图表显示测试")
    print("=" * 60)
    print("这个测试将:")
    print("1. 创建一个独立的图表窗口（不在PyCharm内嵌显示）")
    print("2. 生成模拟的FITS质量数据")
    print("3. 实时更新四个子图")
    print("4. 每2秒添加一个新数据点")
    print("-" * 60)
    
    try:
        # 创建测试图表
        plotter = TestPlotter()
        
        print("开始生成测试数据...")
        print("按 Ctrl+C 停止测试")
        print("-" * 60)
        
        # 生成测试数据
        for i in range(50):  # 生成50个数据点
            plotter.add_test_data(i)
            time.sleep(2)  # 每2秒更新一次
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试过程中出错: {e}")
    finally:
        try:
            plotter.close()
            print("图表窗口已关闭")
        except:
            pass
    
    print("测试完成")


if __name__ == "__main__":
    main()
