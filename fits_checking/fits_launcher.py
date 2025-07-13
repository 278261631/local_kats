#!/usr/bin/env python3
"""
FITS监控系统统一启动器
提供所有功能模块的统一入口
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime


def print_banner():
    """打印程序横幅"""
    print("=" * 70)
    print("    FITS文件监控和质量评估系统 v3.0")
    print("    模块化版本 - 功能完全分离")
    print("=" * 70)


def print_modules():
    """打印模块列表"""
    print("可用模块:")
    print("  1. 监控器 (run_monitor.py)    - 核心文件监控和质量分析")
    print("  2. 图表查看器 (plot_viewer.py) - 数据可视化和统计分析")
    print("  3. 测试运行器 (test_runner.py) - 测试功能和文件复制")
    print("  4. 配置管理器 (config_loader.py) - 系统配置管理")
    print("-" * 70)


def launch_monitor(args):
    """启动监控器"""
    print("启动监控器...")

    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = ['python', os.path.join(script_dir, 'run_monitor.py')]

    if args.no_record:
        cmd.append('--no-record')
    if args.interval:
        cmd.extend(['--interval', str(args.interval)])
    if args.config:
        cmd.extend(['--config', args.config])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n监控器已停止")
    except Exception as e:
        print(f"启动监控器失败: {e}")


def launch_plot_viewer(args):
    """启动图表查看器"""
    print("启动图表查看器...")

    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = ['python', os.path.join(script_dir, 'plot_viewer.py')]

    if args.file:
        cmd.extend(['--file', args.file])
    if args.realtime:
        cmd.append('--realtime')
    if args.stats:
        cmd.append('--stats')
    if args.interval:
        cmd.extend(['--interval', str(args.interval)])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n图表查看器已停止")
    except Exception as e:
        print(f"启动图表查看器失败: {e}")


def launch_test_runner(args):
    """启动测试运行器"""
    print("启动测试运行器...")

    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = ['python', os.path.join(script_dir, 'test_runner.py')]

    if args.copy_only:
        cmd.append('--copy-only')
    if args.monitor_only:
        cmd.append('--monitor-only')
    if args.interval:
        cmd.extend(['--interval', str(args.interval)])
    if args.config:
        cmd.extend(['--config', args.config])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n测试运行器已停止")
    except Exception as e:
        print(f"启动测试运行器失败: {e}")


def show_status():
    """显示系统状态"""
    print("系统状态检查:")
    print("-" * 70)

    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 检查文件存在性
    files_to_check = [
        'run_monitor.py',
        'plot_viewer.py',
        'test_runner.py',
        'fits_monitor.py',
        'config_loader.py'
    ]

    for filename in files_to_check:
        file_path = os.path.join(script_dir, filename)
        if os.path.exists(file_path):
            print(f"✓ {filename}: 存在")
        else:
            print(f"✗ {filename}: 缺失")

    # 检查配置文件
    config_file = os.path.join(script_dir, 'config.json')
    if os.path.exists(config_file):
        print(f"✓ config.json: 存在")
    else:
        print(f"○ config.json: 不存在（将自动创建）")

    # 检查数据文件
    data_file = os.path.join(script_dir, 'fits_quality_log.csv')
    if os.path.exists(data_file):
        print(f"✓ fits_quality_log.csv: 存在")
    else:
        print(f"○ fits_quality_log.csv: 不存在（运行监控器后创建）")

    print("-" * 70)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS监控系统统一启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python fits_launcher.py monitor                    # 启动监控器
  python fits_launcher.py plot                       # 启动图表查看器
  python fits_launcher.py plot --realtime            # 启动实时图表
  python fits_launcher.py test                       # 启动完整测试
  python fits_launcher.py test --copy-only           # 仅文件复制测试
  python fits_launcher.py status                     # 显示系统状态
        """
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 监控器命令
    monitor_parser = subparsers.add_parser('monitor', help='启动监控器')
    monitor_parser.add_argument('--no-record', action='store_true', help='禁用数据记录')
    monitor_parser.add_argument('--interval', type=int, help='扫描间隔（秒）')
    monitor_parser.add_argument('--config', help='配置文件路径')
    
    # 图表查看器命令
    plot_parser = subparsers.add_parser('plot', help='启动图表查看器')
    plot_parser.add_argument('--file', help='CSV数据文件路径')
    plot_parser.add_argument('--realtime', action='store_true', help='实时更新模式')
    plot_parser.add_argument('--stats', action='store_true', help='显示统计信息')
    plot_parser.add_argument('--interval', type=int, help='更新间隔（秒）')
    
    # 测试运行器命令
    test_parser = subparsers.add_parser('test', help='启动测试运行器')
    test_parser.add_argument('--copy-only', action='store_true', help='仅文件复制测试')
    test_parser.add_argument('--monitor-only', action='store_true', help='仅监控器测试')
    test_parser.add_argument('--interval', type=int, help='扫描间隔（秒）')
    test_parser.add_argument('--config', help='配置文件路径')
    
    # 状态命令
    subparsers.add_parser('status', help='显示系统状态')
    
    args = parser.parse_args()
    
    # 打印横幅
    print_banner()
    print_modules()
    
    # 根据命令执行相应功能
    if args.command == 'monitor':
        launch_monitor(args)
    elif args.command == 'plot':
        launch_plot_viewer(args)
    elif args.command == 'test':
        launch_test_runner(args)
    elif args.command == 'status':
        show_status()
    else:
        print("请指定一个命令。使用 --help 查看帮助信息。")
        print("\n快速开始:")
        print("  python fits_launcher.py monitor     # 启动监控器")
        print("  python fits_launcher.py plot        # 查看图表")
        print("  python fits_launcher.py test        # 运行测试")
        print("  python fits_launcher.py status      # 检查状态")


if __name__ == "__main__":
    main()
