#!/usr/bin/env python3
"""
增强版FITS监控器测试脚本
测试实时图表显示和数据记录功能
"""

import os
import sys
import time
import threading
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fits_monitor import FITSFileMonitor
from test_monitor import copy_test_files


def run_monitor_in_thread(monitor_dir):
    """在单独线程中运行监控器"""
    try:
        print(f"启动监控器线程，监控目录: {monitor_dir}")
        
        # 创建监控器实例
        monitor = FITSFileMonitor(
            monitor_dir,
            enable_plotting=True,   # 启用实时图表
            enable_recording=True   # 启用数据记录
        )
        
        # 开始监控
        monitor.start_monitoring(scan_interval=3)  # 3秒扫描间隔
        
    except Exception as e:
        print(f"监控器线程出错: {str(e)}")


def run_file_copier_in_thread():
    """在单独线程中运行文件复制器"""
    try:
        print("启动文件复制器线程...")
        time.sleep(5)  # 等待5秒让监控器先启动
        
        # 开始复制文件（这会触发监控器检测新文件）
        copy_test_files()
        
    except Exception as e:
        print(f"文件复制器线程出错: {str(e)}")


def main():
    """主函数"""
    print("=" * 60)
    print("增强版FITS监控器测试")
    print("=" * 60)
    print("功能:")
    print("1. 实时图表显示 - 显示FWHM、椭圆度、源数量、背景RMS的变化趋势")
    print("2. 数据记录 - 将分析结果保存到CSV文件")
    print("3. 慢速测试 - 文件复制间隔2.5秒，便于观察实时效果")
    print("=" * 60)
    
    # 监控目录
    monitor_directory = r"E:\fix_data\debug_fits_output"
    
    # 检查源目录是否存在
    source_directory = r"E:\fix_data\debug_fits_input"
    if not os.path.exists(source_directory):
        print(f"错误: 源目录不存在: {source_directory}")
        print("请确保源目录存在并包含FITS文件")
        return
    
    # 创建目标目录
    os.makedirs(monitor_directory, exist_ok=True)
    
    print(f"监控目录: {monitor_directory}")
    print(f"源目录: {source_directory}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    try:
        # 创建并启动监控器线程
        monitor_thread = threading.Thread(
            target=run_monitor_in_thread, 
            args=(monitor_directory,),
            daemon=True
        )
        monitor_thread.start()
        
        # 创建并启动文件复制器线程
        copier_thread = threading.Thread(
            target=run_file_copier_in_thread,
            daemon=True
        )
        copier_thread.start()
        
        print("两个线程已启动:")
        print("- 监控器线程: 监控新的FITS文件并分析")
        print("- 复制器线程: 慢速复制FITS文件到监控目录")
        print("\n按 Ctrl+C 停止测试...")
        print("-" * 60)
        
        # 主线程等待
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭...")
        print("测试完成！")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n生成的文件:")
        print("- fits_monitor.log: 监控日志文件")
        print("- fits_quality_log.csv: 质量分析数据记录")
        
    except Exception as e:
        print(f"测试过程中出错: {str(e)}")


if __name__ == "__main__":
    main()
