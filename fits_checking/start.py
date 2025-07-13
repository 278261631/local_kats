#!/usr/bin/env python3
"""
FITS监控系统简单启动器
避免路径问题的直接启动方式
"""

import os
import sys
import argparse

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def start_monitor(args):
    """启动监控器"""
    print("启动监控器...")
    try:
        from run_monitor import main as monitor_main
        
        # 模拟命令行参数
        original_argv = sys.argv.copy()
        sys.argv = ['run_monitor.py']
        
        if args.no_record:
            sys.argv.append('--no-record')
        if args.interval:
            sys.argv.extend(['--interval', str(args.interval)])
        if args.config:
            sys.argv.extend(['--config', args.config])
        
        monitor_main()
        
    except KeyboardInterrupt:
        print("\n监控器已停止")
    except Exception as e:
        print(f"启动监控器失败: {e}")
    finally:
        sys.argv = original_argv


def start_plot_viewer(args):
    """启动图表查看器"""
    print("启动图表查看器...")
    try:
        from plot_viewer import main as plot_main
        
        # 模拟命令行参数
        original_argv = sys.argv.copy()
        sys.argv = ['plot_viewer.py']
        
        if args.file:
            sys.argv.extend(['--file', args.file])
        if args.realtime:
            sys.argv.append('--realtime')
        if args.stats:
            sys.argv.append('--stats')
        if args.interval:
            sys.argv.extend(['--interval', str(args.interval)])
        
        plot_main()
        
    except KeyboardInterrupt:
        print("\n图表查看器已停止")
    except Exception as e:
        print(f"启动图表查看器失败: {e}")
    finally:
        sys.argv = original_argv


def start_test_runner(args):
    """启动测试运行器"""
    print("启动测试运行器...")
    try:
        from test_runner import main as test_main
        
        # 模拟命令行参数
        original_argv = sys.argv.copy()
        sys.argv = ['test_runner.py']
        
        if args.copy_only:
            sys.argv.append('--copy-only')
        if args.monitor_only:
            sys.argv.append('--monitor-only')
        if args.interval:
            sys.argv.extend(['--interval', str(args.interval)])
        if args.config:
            sys.argv.extend(['--config', args.config])
        
        test_main()
        
    except KeyboardInterrupt:
        print("\n测试运行器已停止")
    except Exception as e:
        print(f"启动测试运行器失败: {e}")
    finally:
        sys.argv = original_argv


def show_status():
    """显示系统状态"""
    print("系统状态检查:")
    print("-" * 50)
    
    # 检查文件存在性
    files_to_check = [
        'run_monitor.py',
        'plot_viewer.py', 
        'test_runner.py',
        'fits_monitor.py',
        'config_loader.py'
    ]
    
    for filename in files_to_check:
        file_path = os.path.join(current_dir, filename)
        if os.path.exists(file_path):
            print(f"✓ {filename}: 存在")
        else:
            print(f"✗ {filename}: 缺失")
    
    # 检查配置文件
    config_file = os.path.join(current_dir, 'config.json')
    if os.path.exists(config_file):
        print(f"✓ config.json: 存在")
    else:
        print(f"○ config.json: 不存在（将自动创建）")
    
    # 检查数据文件
    data_file = os.path.join(current_dir, 'fits_quality_log.csv')
    if os.path.exists(data_file):
        print(f"✓ fits_quality_log.csv: 存在")
    else:
        print(f"○ fits_quality_log.csv: 不存在（运行监控器后创建）")
    
    print("-" * 50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS监控系统简单启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python start.py monitor                    # 启动监控器
  python start.py plot                       # 启动图表查看器
  python start.py plot --realtime            # 启动实时图表
  python start.py test                       # 启动完整测试
  python start.py test --copy-only           # 仅文件复制测试
  python start.py status                     # 显示系统状态
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
    
    print("=" * 60)
    print("FITS监控系统 - 简单启动器")
    print("=" * 60)
    
    # 根据命令执行相应功能
    if args.command == 'monitor':
        start_monitor(args)
    elif args.command == 'plot':
        start_plot_viewer(args)
    elif args.command == 'test':
        start_test_runner(args)
    elif args.command == 'status':
        show_status()
    else:
        print("请指定一个命令。使用 --help 查看帮助信息。")
        print("\n快速开始:")
        print("  python start.py monitor     # 启动监控器")
        print("  python start.py plot        # 查看图表")
        print("  python start.py test        # 运行测试")
        print("  python start.py status      # 检查状态")


if __name__ == "__main__":
    main()
