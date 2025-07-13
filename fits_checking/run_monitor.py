#!/usr/bin/env python3
"""
FITS监控系统启动脚本
支持多种运行模式和配置选项
"""

import os
import sys
import argparse
import time
import threading
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fits_monitor import FITSFileMonitor
from config_loader import get_config


def print_banner():
    """打印程序横幅"""
    print("=" * 70)
    print("    FITS文件监控和质量评估系统 v2.0")
    print("    增强版 - 支持实时图表显示和数据记录")
    print("=" * 70)


def print_features():
    """打印功能列表"""
    print("主要功能:")
    print("  ✓ 实时监控FITS文件")
    print("  ✓ 自动质量分析（FWHM、椭圆度、源数量等）")
    print("  ✓ CSV数据记录")
    print("  ✓ 详细日志记录")
    print("  ✓ 可配置的质量阈值")
    print("")
    print("独立功能模块:")
    print("  ✓ 图表查看器: python plot_viewer.py")
    print("  ✓ 测试运行器: python test_runner.py")
    print("-" * 70)


def run_monitor(config):
    """运行监控器"""
    monitor_settings = config.get_monitor_settings()

    monitor_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
    scan_interval = monitor_settings.get('scan_interval', 5)
    enable_recording = monitor_settings.get('enable_recording', True)

    print(f"监控目录: {monitor_dir}")
    print(f"扫描间隔: {scan_interval} 秒")
    print(f"数据记录: {'启用' if enable_recording else '禁用'}")
    print(f"图表查看: 使用 'python plot_viewer.py' 查看图表")
    print(f"测试功能: 使用 'python test_runner.py' 运行测试")
    print("-" * 70)

    # 检查目录
    if not os.path.exists(monitor_dir):
        print(f"警告: 监控目录不存在: {monitor_dir}")
        print("创建测试目录...")
        os.makedirs(monitor_dir, exist_ok=True)

    # 创建并启动监控器
    monitor = FITSFileMonitor(
        monitor_dir,
        enable_recording=enable_recording
    )

    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("按 Ctrl+C 停止监控...")
    print("-" * 70)

    try:
        monitor.start_monitoring(scan_interval=scan_interval)
    except KeyboardInterrupt:
        print("\n监控已停止")





def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS文件监控和质量评估系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python run_monitor.py                    # 运行监控器
  python run_monitor.py --no-record        # 禁用数据记录
  python run_monitor.py --interval 10      # 设置扫描间隔为10秒
  python plot_viewer.py                    # 查看静态图表
  python plot_viewer.py --realtime         # 查看实时图表
  python test_runner.py                    # 运行测试功能
        """
    )

    parser.add_argument('--no-record', action='store_true',
                       help='禁用数据记录')
    parser.add_argument('--interval', type=int, default=None,
                       help='设置扫描间隔（秒）')
    parser.add_argument('--config', type=str, default='config.json',
                       help='指定配置文件路径')

    args = parser.parse_args()

    # 打印横幅和功能
    print_banner()
    print_features()

    # 加载配置
    config = get_config()

    # 应用命令行参数覆盖配置
    if args.interval is not None:
        config.set('monitor_settings', 'scan_interval', args.interval)
    if args.no_record:
        config.set('monitor_settings', 'enable_recording', False)

    # 运行监控器
    print("运行模式: 监控模式")
    print("-" * 70)
    run_monitor(config)

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("程序已退出")


if __name__ == "__main__":
    main()
