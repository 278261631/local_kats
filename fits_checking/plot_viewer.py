#!/usr/bin/env python3
"""
FITS质量数据图表查看器
从CSV日志文件中读取数据并显示图表
独立运行，不依赖主监控程序
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import argparse

# 设置matplotlib后端
import matplotlib
matplotlib.use('TkAgg')  # 强制使用TkAgg后端，确保独立窗口显示
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class FITSDataPlotter:
    """FITS质量数据图表显示器"""
    
    def __init__(self, csv_file='fits_quality_log.csv'):
        self.csv_file = csv_file
        self.data = None
        self.fig = None
        self.axes = None
        self.last_modified = 0
        
    def load_data(self):
        """从CSV文件加载数据"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"错误: CSV文件不存在: {self.csv_file}")
                return False
            
            # 检查文件是否有更新
            current_modified = os.path.getmtime(self.csv_file)
            if current_modified == self.last_modified and self.data is not None:
                return True  # 数据没有更新
            
            # 读取CSV文件
            self.data = pd.read_csv(self.csv_file)
            self.last_modified = current_modified
            
            if self.data.empty:
                print("警告: CSV文件为空")
                return False
            
            # 转换时间戳
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            
            # 处理数值列，将空字符串转换为NaN
            numeric_columns = ['n_sources', 'fwhm', 'ellipticity', 'lm5sig', 'background_mean', 'background_rms']
            for col in numeric_columns:
                if col in self.data.columns:
                    self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
            
            print(f"成功加载 {len(self.data)} 条记录")
            return True
            
        except Exception as e:
            print(f"加载数据时出错: {e}")
            return False
    
    def create_static_plot(self):
        """创建静态图表"""
        if not self.load_data():
            return
        
        # 创建图形和子图
        self.fig, self.axes = plt.subplots(2, 2, figsize=(14, 10))
        self.fig.suptitle('FITS图像质量数据分析', fontsize=16, fontweight='bold')
        
        # 获取时间轴
        timestamps = self.data['timestamp']
        
        # 子图1: FWHM
        ax1 = self.axes[0, 0]
        fwhm_data = self.data['fwhm'].dropna()
        fwhm_times = timestamps[self.data['fwhm'].notna()]
        
        if not fwhm_data.empty:
            ax1.plot(fwhm_times, fwhm_data, 'b-o', markersize=4, linewidth=1.5)
            ax1.set_title('FWHM (半高全宽)', fontsize=12, fontweight='bold')
            ax1.set_ylabel('FWHM (像素)')
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 添加质量阈值线
            ax1.axhline(y=2.0, color='g', linestyle='--', alpha=0.7, label='优秀 (<2.0)')
            ax1.axhline(y=3.0, color='orange', linestyle='--', alpha=0.7, label='良好 (<3.0)')
            ax1.axhline(y=5.0, color='r', linestyle='--', alpha=0.7, label='一般 (<5.0)')
            ax1.legend(fontsize=8)
        
        # 子图2: 椭圆度
        ax2 = self.axes[0, 1]
        ellipticity_data = self.data['ellipticity'].dropna()
        ellipticity_times = timestamps[self.data['ellipticity'].notna()]
        
        if not ellipticity_data.empty:
            ax2.plot(ellipticity_times, ellipticity_data, 'r-o', markersize=4, linewidth=1.5)
            ax2.set_title('椭圆度', fontsize=12, fontweight='bold')
            ax2.set_ylabel('椭圆度')
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 添加质量阈值线
            ax2.axhline(y=0.1, color='g', linestyle='--', alpha=0.7, label='优秀 (<0.1)')
            ax2.axhline(y=0.2, color='orange', linestyle='--', alpha=0.7, label='良好 (<0.2)')
            ax2.axhline(y=0.3, color='r', linestyle='--', alpha=0.7, label='一般 (<0.3)')
            ax2.legend(fontsize=8)
        
        # 子图3: 源数量
        ax3 = self.axes[1, 0]
        sources_data = self.data['n_sources'].dropna()
        sources_times = timestamps[self.data['n_sources'].notna()]
        
        if not sources_data.empty:
            ax3.plot(sources_times, sources_data, 'g-o', markersize=4, linewidth=1.5)
            ax3.set_title('检测到的源数量', fontsize=12, fontweight='bold')
            ax3.set_ylabel('源数量')
            ax3.grid(True, alpha=0.3)
            ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 添加质量阈值线
            ax3.axhline(y=50, color='g', linestyle='--', alpha=0.7, label='充足 (>50)')
            ax3.axhline(y=10, color='orange', linestyle='--', alpha=0.7, label='一般 (>10)')
            ax3.legend(fontsize=8)
        
        # 子图4: 背景RMS
        ax4 = self.axes[1, 1]
        rms_data = self.data['background_rms'].dropna()
        rms_times = timestamps[self.data['background_rms'].notna()]
        
        if not rms_data.empty:
            ax4.plot(rms_times, rms_data, 'm-o', markersize=4, linewidth=1.5)
            ax4.set_title('背景RMS', fontsize=12, fontweight='bold')
            ax4.set_ylabel('RMS')
            ax4.grid(True, alpha=0.3)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # 调整时间轴显示
        for ax in self.axes.flat:
            ax.tick_params(axis='x', rotation=45)
            if ax.get_lines():  # 只有当有数据时才调整
                ax.relim()
                ax.autoscale_view()
        
        plt.tight_layout()
        plt.show()
    
    def create_realtime_plot(self, update_interval=5000):
        """创建实时更新图表"""
        if not self.load_data():
            return

        # 创建图形和子图
        self.fig, self.axes = plt.subplots(2, 2, figsize=(14, 10))
        self.fig.suptitle('FITS图像质量数据分析 (实时更新)', fontsize=16, fontweight='bold')

        def update_plot(frame):
            """更新图表数据"""
            if self.load_data():  # 重新加载数据
                # 清除所有子图
                for ax in self.axes.flat:
                    ax.clear()

                # 重新绘制图表
                self._plot_realtime_data()

        # 初始绘制
        self._plot_realtime_data()

        # 创建动画
        ani = FuncAnimation(self.fig, update_plot, interval=update_interval, cache_frame_data=False)

        plt.show()
        return ani

    def _plot_realtime_data(self):
        """绘制实时数据到子图"""
        timestamps = self.data['timestamp']

        # 子图1: FWHM
        ax1 = self.axes[0, 0]
        fwhm_data = self.data['fwhm'].dropna()
        fwhm_times = timestamps[self.data['fwhm'].notna()]

        if not fwhm_data.empty:
            ax1.plot(fwhm_times, fwhm_data, 'b-o', markersize=3, linewidth=1)
            ax1.set_title('FWHM (半高全宽)')
            ax1.set_ylabel('FWHM (像素)')
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 子图2: 椭圆度
        ax2 = self.axes[0, 1]
        ellipticity_data = self.data['ellipticity'].dropna()
        ellipticity_times = timestamps[self.data['ellipticity'].notna()]

        if not ellipticity_data.empty:
            ax2.plot(ellipticity_times, ellipticity_data, 'r-o', markersize=3, linewidth=1)
            ax2.set_title('椭圆度')
            ax2.set_ylabel('椭圆度')
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 子图3: 源数量
        ax3 = self.axes[1, 0]
        sources_data = self.data['n_sources'].dropna()
        sources_times = timestamps[self.data['n_sources'].notna()]

        if not sources_data.empty:
            ax3.plot(sources_times, sources_data, 'g-o', markersize=3, linewidth=1)
            ax3.set_title('检测到的源数量')
            ax3.set_ylabel('源数量')
            ax3.grid(True, alpha=0.3)
            ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 子图4: 背景RMS
        ax4 = self.axes[1, 1]
        rms_data = self.data['background_rms'].dropna()
        rms_times = timestamps[self.data['background_rms'].notna()]

        if not rms_data.empty:
            ax4.plot(rms_times, rms_data, 'm-o', markersize=3, linewidth=1)
            ax4.set_title('背景RMS')
            ax4.set_ylabel('RMS')
            ax4.grid(True, alpha=0.3)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 调整时间轴显示
        for ax in self.axes.flat:
            ax.tick_params(axis='x', rotation=45)
            if ax.get_lines():
                ax.relim()
                ax.autoscale_view()

        plt.tight_layout()
    
    def print_statistics(self):
        """打印数据统计信息"""
        if not self.load_data():
            return
        
        print("\n" + "="*60)
        print("FITS质量数据统计信息")
        print("="*60)
        
        print(f"数据记录总数: {len(self.data)}")
        print(f"时间范围: {self.data['timestamp'].min()} 到 {self.data['timestamp'].max()}")
        
        # FWHM统计
        fwhm_data = self.data['fwhm'].dropna()
        if not fwhm_data.empty:
            print(f"\nFWHM统计:")
            print(f"  平均值: {fwhm_data.mean():.2f} 像素")
            print(f"  中位数: {fwhm_data.median():.2f} 像素")
            print(f"  标准差: {fwhm_data.std():.2f} 像素")
            print(f"  范围: {fwhm_data.min():.2f} - {fwhm_data.max():.2f} 像素")
        
        # 椭圆度统计
        ellipticity_data = self.data['ellipticity'].dropna()
        if not ellipticity_data.empty:
            print(f"\n椭圆度统计:")
            print(f"  平均值: {ellipticity_data.mean():.3f}")
            print(f"  中位数: {ellipticity_data.median():.3f}")
            print(f"  标准差: {ellipticity_data.std():.3f}")
            print(f"  范围: {ellipticity_data.min():.3f} - {ellipticity_data.max():.3f}")
        
        # 源数量统计
        sources_data = self.data['n_sources'].dropna()
        if not sources_data.empty:
            print(f"\n源数量统计:")
            print(f"  平均值: {sources_data.mean():.1f}")
            print(f"  中位数: {sources_data.median():.1f}")
            print(f"  标准差: {sources_data.std():.1f}")
            print(f"  范围: {int(sources_data.min())} - {int(sources_data.max())}")
        
        print("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS质量数据图表查看器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python plot_viewer.py                           # 显示静态图表
  python plot_viewer.py --realtime               # 实时更新图表
  python plot_viewer.py --stats                  # 显示统计信息
  python plot_viewer.py --file custom_log.csv    # 指定CSV文件
        """
    )
    
    parser.add_argument('--file', '-f', default='fits_quality_log.csv',
                       help='指定CSV数据文件路径 (默认: fits_quality_log.csv)')
    parser.add_argument('--realtime', '-r', action='store_true',
                       help='启用实时更新模式')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='显示数据统计信息')
    parser.add_argument('--interval', '-i', type=int, default=5,
                       help='实时更新间隔（秒，默认5秒）')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FITS质量数据图表查看器")
    print("=" * 60)
    print(f"数据文件: {args.file}")
    
    # 创建图表显示器
    plotter = FITSDataPlotter(args.file)
    
    # 显示统计信息
    if args.stats:
        plotter.print_statistics()
    
    # 显示图表
    if args.realtime:
        print(f"实时更新模式 (间隔: {args.interval}秒)")
        print("按 Ctrl+C 停止...")
        print("-" * 60)
        try:
            ani = plotter.create_realtime_plot(args.interval * 1000)
        except KeyboardInterrupt:
            print("\n实时更新已停止")
    else:
        print("静态图表模式")
        print("-" * 60)
        plotter.create_static_plot()


if __name__ == "__main__":
    main()
