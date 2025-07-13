#!/usr/bin/env python3
"""
分离式图表功能演示脚本
展示主监控程序和图表查看器的独立运行
"""

import os
import sys
import time
import subprocess
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_demo_data():
    """创建演示数据"""
    print("创建演示数据...")
    
    # 生成模拟的FITS质量数据
    start_time = datetime.now() - timedelta(hours=2)
    timestamps = pd.date_range(start=start_time, periods=30, freq='3min')
    
    data = []
    for i, ts in enumerate(timestamps):
        # 模拟不同质量的数据
        if i < 10:  # 前10个数据点 - 优秀质量
            fwhm = 1.8 + 0.2 * np.sin(i * 0.3) + np.random.normal(0, 0.1)
            ellipticity = 0.08 + 0.02 * np.cos(i * 0.2) + np.random.normal(0, 0.01)
            n_sources = int(55 + 5 * np.sin(i * 0.1) + np.random.normal(0, 2))
        elif i < 20:  # 中间10个数据点 - 一般质量
            fwhm = 2.5 + 0.3 * np.sin(i * 0.4) + np.random.normal(0, 0.15)
            ellipticity = 0.18 + 0.04 * np.cos(i * 0.3) + np.random.normal(0, 0.02)
            n_sources = int(35 + 8 * np.sin(i * 0.2) + np.random.normal(0, 3))
        else:  # 最后10个数据点 - 较差质量
            fwhm = 3.2 + 0.5 * np.sin(i * 0.5) + np.random.normal(0, 0.2)
            ellipticity = 0.25 + 0.05 * np.cos(i * 0.4) + np.random.normal(0, 0.03)
            n_sources = int(25 + 10 * np.sin(i * 0.3) + np.random.normal(0, 4))
        
        background_rms = 100 + 20 * np.sin(i * 0.6) + np.random.normal(0, 5)
        
        data.append({
            'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
            'filename': f'demo_image_{i+1:03d}.fits',
            'n_sources': max(5, n_sources),
            'fwhm': max(0.8, fwhm),
            'ellipticity': max(0.02, min(0.8, ellipticity)),
            'lm5sig': 20.0 + np.random.normal(0, 1),
            'background_mean': 1000 + np.random.normal(0, 50),
            'background_rms': max(20, background_rms)
        })
    
    # 保存到CSV文件
    df = pd.DataFrame(data)
    df.to_csv('fits_quality_log.csv', index=False)
    
    print(f"✓ 创建了 {len(data)} 条演示数据")
    print("  - 前10条: 优秀质量 (FWHM<2.0, 椭圆度<0.1)")
    print("  - 中10条: 一般质量 (FWHM~2.5, 椭圆度~0.18)")
    print("  - 后10条: 较差质量 (FWHM>3.0, 椭圆度>0.25)")
    print("✓ 数据已保存到: fits_quality_log.csv")

def demo_static_plot():
    """演示静态图表"""
    print("\n" + "="*60)
    print("演示1: 静态图表查看")
    print("="*60)
    print("显示所有历史数据的静态图表...")
    
    try:
        # 运行静态图表查看器
        result = subprocess.run([
            'python', 'fits_checking/plot_viewer.py'
        ], timeout=10, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ 静态图表已显示")
            print("  请检查是否有图表窗口弹出")
        else:
            print("✗ 静态图表显示失败")
            print(f"错误: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("✓ 图表窗口已打开（超时正常，说明窗口正在显示）")
    except Exception as e:
        print(f"✗ 运行图表查看器时出错: {e}")

def demo_stats():
    """演示统计信息"""
    print("\n" + "="*60)
    print("演示2: 数据统计信息")
    print("="*60)
    
    try:
        # 运行统计信息查看
        result = subprocess.run([
            'python', 'fits_checking/plot_viewer.py', '--stats'
        ], timeout=15, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ 统计信息:")
            print(result.stdout)
        else:
            print("✗ 统计信息获取失败")
            print(f"错误: {result.stderr}")
            
    except Exception as e:
        print(f"✗ 运行统计分析时出错: {e}")

def demo_monitor_info():
    """演示监控器信息"""
    print("\n" + "="*60)
    print("演示3: 主监控程序信息")
    print("="*60)
    print("主监控程序已轻量化，专注于文件监控和数据记录")
    print("特点:")
    print("  ✓ 无matplotlib依赖，启动更快")
    print("  ✓ 资源占用更少")
    print("  ✓ 适合服务器环境运行")
    print("  ✓ 专注核心监控功能")
    
    print("\n启动命令:")
    print("  python fits_checking/run_monitor.py          # 基本监控")
    print("  python fits_checking/run_monitor.py --test   # 测试模式")
    
    print("\n图表查看命令:")
    print("  python fits_checking/plot_viewer.py          # 静态图表")
    print("  python fits_checking/plot_viewer.py --realtime  # 实时图表")
    print("  python fits_checking/plot_viewer.py --stats     # 统计信息")

def demo_workflow():
    """演示完整工作流程"""
    print("\n" + "="*60)
    print("演示4: 典型工作流程")
    print("="*60)
    
    print("步骤1: 启动主监控程序（后台运行）")
    print("  命令: python fits_checking/run_monitor.py")
    print("  功能: 监控FITS文件，记录质量数据到CSV")
    
    print("\n步骤2: 按需查看图表（独立运行）")
    print("  命令: python fits_checking/plot_viewer.py")
    print("  功能: 从CSV读取数据，显示图表分析")
    
    print("\n步骤3: 实时监控（可选）")
    print("  命令: python fits_checking/plot_viewer.py --realtime")
    print("  功能: 每5秒自动刷新图表数据")
    
    print("\n优势:")
    print("  ✓ 主程序轻量，图表功能丰富")
    print("  ✓ 可以独立分析历史数据")
    print("  ✓ 支持多种查看模式")
    print("  ✓ 便于部署和维护")

def main():
    """主演示函数"""
    print("=" * 70)
    print("FITS监控系统 - 分离式图表功能演示")
    print("=" * 70)
    print("本演示将展示:")
    print("1. 静态图表查看")
    print("2. 数据统计信息")
    print("3. 主监控程序信息")
    print("4. 典型工作流程")
    print("=" * 70)
    
    # 创建演示数据
    create_demo_data()
    
    # 等待用户确认
    input("\n按回车键开始演示...")
    
    # 运行各项演示
    demo_static_plot()
    
    input("\n按回车键继续下一个演示...")
    demo_stats()
    
    input("\n按回车键继续下一个演示...")
    demo_monitor_info()
    
    input("\n按回车键继续下一个演示...")
    demo_workflow()
    
    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70)
    print("现在您可以:")
    print("1. 查看生成的演示数据: fits_quality_log.csv")
    print("2. 运行静态图表: python fits_checking/plot_viewer.py")
    print("3. 查看统计信息: python fits_checking/plot_viewer.py --stats")
    print("4. 启动监控程序: python fits_checking/run_monitor.py --test")
    print("5. 实时查看图表: python fits_checking/plot_viewer.py --realtime")
    
    # 清理选项
    cleanup = input("\n是否删除演示数据文件? (y/N): ").lower().strip()
    if cleanup == 'y':
        if os.path.exists('fits_quality_log.csv'):
            os.remove('fits_quality_log.csv')
            print("✓ 演示数据文件已删除")
    else:
        print("✓ 演示数据文件已保留")

if __name__ == "__main__":
    main()
