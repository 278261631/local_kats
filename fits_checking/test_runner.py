#!/usr/bin/env python3
"""
FITS监控系统测试运行器
独立的测试功能，包含文件复制器和监控器的协调运行
"""

import os
import sys
import time
import threading
import argparse
import shutil
import glob
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fits_monitor import FITSFileMonitor
from config_loader import get_config


def clear_fits_files(directory):
    """
    清除目录中的所有FITS文件

    Args:
        directory (str): 要清理的目录路径
    """
    if not os.path.exists(directory):
        return

    fits_pattern = os.path.join(directory, "**", "*.fits")
    existing_fits = glob.glob(fits_pattern, recursive=True)

    if existing_fits:
        print(f"清理目标目录中的 {len(existing_fits)} 个现有FITS文件...")
        for fits_file in existing_fits:
            try:
                os.remove(fits_file)
                print(f"  已删除: {os.path.basename(fits_file)}")
            except Exception as e:
                print(f"  删除失败 {os.path.basename(fits_file)}: {str(e)}")
        print("目录清理完成")
    else:
        print("目标目录中没有现有的FITS文件")


def copy_test_files(source_dir, target_dir, interval=2.5, max_files=None, clear_target=True):
    """
    慢速复制FITS文件到目标目录，用于测试监控功能

    Args:
        source_dir (str): 源目录路径
        target_dir (str): 目标目录路径
        interval (float): 复制间隔（秒）
        max_files (int): 最大复制文件数，None表示无限制
        clear_target (bool): 是否在复制前清除目标目录中的FITS文件
    """
    print(f"开始复制FITS文件...")
    print(f"源目录: {source_dir}")
    print(f"目标目录: {target_dir}")
    print(f"复制间隔: {interval} 秒")
    print(f"清理目标目录: {'是' if clear_target else '否'}")
    print("-" * 50)

    # 确保目标目录存在
    os.makedirs(target_dir, exist_ok=True)

    # 清除目标目录中现有的FITS文件
    if clear_target:
        clear_fits_files(target_dir)

    # 查找源目录中的FITS文件
    fits_pattern = os.path.join(source_dir, "**", "*.fits")
    fits_files = glob.glob(fits_pattern, recursive=True)

    if not fits_files:
        print(f"警告: 在源目录中未找到FITS文件: {source_dir}")
        return

    print(f"找到 {len(fits_files)} 个FITS文件")

    # 限制文件数量
    if max_files and len(fits_files) > max_files:
        fits_files = fits_files[:max_files]
        print(f"限制复制文件数量为: {max_files}")

    copied_count = 0

    try:
        for i, source_file in enumerate(fits_files, 1):
            # 生成目标文件名
            base_name = os.path.basename(source_file)
            name, ext = os.path.splitext(base_name)
            target_file = os.path.join(target_dir, f"test_{i:03d}_{name}{ext}")

            print(f"复制文件 {i}/{len(fits_files)}: {base_name} -> {os.path.basename(target_file)}")

            # 复制文件
            shutil.copy2(source_file, target_file)
            copied_count += 1

            # 等待指定间隔
            if i < len(fits_files):  # 最后一个文件后不需要等待
                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n复制被中断，已复制 {copied_count} 个文件")
    except Exception as e:
        print(f"复制过程中出错: {str(e)}")

    print(f"复制完成，共复制 {copied_count} 个文件")


class TestRunner:
    """测试运行器类"""

    def __init__(self, config, clear_target=True):
        self.config = config
        self.monitor_thread = None
        self.copier_thread = None
        self.monitor = None
        self.running = False
        self.source_dir = None
        self.monitor_dir = None
        self.copy_delay = None
        self.clear_target = clear_target
    
    def run_monitor_thread(self):
        """监控器线程函数"""
        try:
            monitor_settings = self.config.get_monitor_settings()

            scan_interval = monitor_settings.get('scan_interval', 5)
            enable_recording = monitor_settings.get('enable_recording', True)

            print(f"[监控器] 启动监控: {self.monitor_dir}")
            print(f"[监控器] 扫描间隔: {scan_interval} 秒")

            # 创建监控器
            self.monitor = FITSFileMonitor(
                self.monitor_dir,
                enable_recording=enable_recording,
                config=self.config.config
            )

            # 开始监控
            self.monitor.start_monitoring(scan_interval=scan_interval)
            
        except Exception as e:
            print(f"[监控器] 错误: {e}")
    
    def run_copier_thread(self):
        """文件复制器线程函数"""
        try:
            print("[复制器] 等待3秒让监控器先启动...")
            time.sleep(3)

            print("[复制器] 开始复制FITS文件...")
            copy_test_files(self.source_dir, self.monitor_dir, self.copy_delay, clear_target=self.clear_target)
            print("[复制器] 文件复制完成")

        except Exception as e:
            print(f"[复制器] 错误: {e}")
    
    def start_test(self):
        """启动测试"""
        print("=" * 60)
        print("FITS监控系统 - 独立测试运行器")
        print("=" * 60)
        
        monitor_settings = self.config.get_monitor_settings()
        test_settings = self.config.get_test_settings()

        self.monitor_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
        self.source_dir = test_settings.get('source_directory', 'test_fits_input')
        self.copy_delay = test_settings.get('copy_delay', 2.5)
        
        print(f"监控目录: {self.monitor_dir}")
        print(f"源目录: {self.source_dir}")
        print(f"复制延迟: {self.copy_delay} 秒")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        # 检查源目录
        if not os.path.exists(self.source_dir):
            print(f"错误: 源目录不存在: {self.source_dir}")
            print("请确保源目录存在并包含FITS文件")
            return False

        # 创建目标目录
        os.makedirs(self.monitor_dir, exist_ok=True)

        # 清理目标目录中现有的FITS文件（如果启用）
        if self.clear_target:
            print("清理测试环境...")
            clear_fits_files(self.monitor_dir)
        else:
            print("跳过目录清理（使用 --no-clear 选项）")
        
        # 启动监控器线程
        self.monitor_thread = threading.Thread(
            target=self.run_monitor_thread,
            daemon=True
        )
        self.monitor_thread.start()
        
        # 启动文件复制器线程
        self.copier_thread = threading.Thread(
            target=self.run_copier_thread,
            daemon=True
        )
        self.copier_thread.start()
        
        print("两个线程已启动:")
        print("  - 监控器线程: 监控新的FITS文件并分析")
        print("  - 复制器线程: 慢速复制FITS文件到监控目录")
        print("\n提示:")
        print("  - 使用 'python plot_viewer.py --realtime' 查看实时图表")
        print("  - 使用 'python plot_viewer.py --stats' 查看统计信息")
        print("  - 按 Ctrl+C 停止测试")
        print("-" * 60)
        
        self.running = True
        return True
    
    def wait_for_completion(self):
        """等待测试完成"""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号，正在关闭测试...")
            self.running = False
        
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("测试已停止")


def run_simple_test(clear_target=True):
    """运行简单测试（仅文件复制）"""
    print("=" * 60)
    print("FITS文件复制测试")
    print("=" * 60)
    print("仅运行文件复制器，不启动监控器")
    print("-" * 60)

    # 使用默认配置
    config = get_config()
    test_settings = config.get_test_settings()
    monitor_settings = config.get_monitor_settings()

    source_dir = test_settings.get('source_directory', 'test_fits_input')
    target_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
    copy_delay = test_settings.get('copy_delay', 2.5)

    print(f"源目录: {source_dir}")
    print(f"目标目录: {target_dir}")
    print(f"复制延迟: {copy_delay} 秒")
    print("-" * 60)

    # 确保目标目录存在
    os.makedirs(target_dir, exist_ok=True)

    try:
        copy_test_files(source_dir, target_dir, copy_delay, clear_target=clear_target)
        print("文件复制测试完成")
    except Exception as e:
        print(f"文件复制测试失败: {e}")


def run_monitor_only():
    """仅运行监控器"""
    print("=" * 60)
    print("FITS监控器测试")
    print("=" * 60)
    print("仅运行监控器，等待现有FITS文件")
    print("-" * 60)
    
    try:
        config = get_config()
        monitor_settings = config.get_monitor_settings()
        
        monitor_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
        scan_interval = monitor_settings.get('scan_interval', 5)
        enable_recording = monitor_settings.get('enable_recording', True)
        
        print(f"监控目录: {monitor_dir}")
        print(f"扫描间隔: {scan_interval} 秒")
        print("按 Ctrl+C 停止监控")
        print("-" * 60)
        
        # 检查目录
        if not os.path.exists(monitor_dir):
            print(f"警告: 监控目录不存在: {monitor_dir}")
            print("创建测试目录...")
            os.makedirs(monitor_dir, exist_ok=True)
        
        # 创建并启动监控器
        monitor = FITSFileMonitor(
            monitor_dir,
            enable_recording=enable_recording,
            config=config.config
        )
        
        monitor.start_monitoring(scan_interval=scan_interval)
        
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"监控器运行出错: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS监控系统独立测试运行器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python test_runner.py                    # 默认：仅运行文件复制测试
  python test_runner.py --full-test        # 完整测试（监控器+文件复制器）
  python test_runner.py --monitor-only     # 仅运行监控器测试
  python test_runner.py --interval 3       # 自定义扫描间隔
  python test_runner.py --no-clear         # 不清理目标目录中现有FITS文件
        """
    )
    
    parser.add_argument('--full-test', action='store_true',
                       help='运行完整测试（监控器+文件复制器）')
    parser.add_argument('--monitor-only', action='store_true',
                       help='仅运行监控器测试')
    parser.add_argument('--interval', type=int, default=None,
                       help='设置监控扫描间隔（秒）')
    parser.add_argument('--no-clear', action='store_true',
                       help='不清理目标目录中现有的FITS文件')
    parser.add_argument('--config', type=str, default='config.json',
                       help='指定配置文件路径')
    
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    
    # 应用命令行参数覆盖配置
    if args.interval is not None:
        config.set('monitor_settings', 'scan_interval', args.interval)
    
    # 根据参数选择运行模式
    clear_target = not args.no_clear  # 默认清理，除非指定 --no-clear

    if args.full_test:
        # 完整测试模式（监控器+文件复制器）
        test_runner = TestRunner(config, clear_target=clear_target)
        if test_runner.start_test():
            test_runner.wait_for_completion()
    elif args.monitor_only:
        run_monitor_only()
    else:
        # 默认模式：仅运行文件复制测试
        run_simple_test(clear_target=clear_target)


if __name__ == "__main__":
    main()
