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
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_monitor import copy_test_files
from fits_monitor import FITSFileMonitor
from config_loader import get_config


class TestRunner:
    """测试运行器类"""
    
    def __init__(self, config):
        self.config = config
        self.monitor_thread = None
        self.copier_thread = None
        self.monitor = None
        self.running = False
    
    def run_monitor_thread(self):
        """监控器线程函数"""
        try:
            monitor_settings = self.config.get_monitor_settings()
            
            monitor_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
            scan_interval = monitor_settings.get('scan_interval', 5)
            enable_recording = monitor_settings.get('enable_recording', True)
            
            print(f"[监控器] 启动监控: {monitor_dir}")
            print(f"[监控器] 扫描间隔: {scan_interval} 秒")
            
            # 创建监控器
            self.monitor = FITSFileMonitor(
                monitor_dir,
                enable_recording=enable_recording
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
            copy_test_files()
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
        
        monitor_dir = monitor_settings.get('monitor_directory', 'test_fits_data')
        source_dir = test_settings.get('source_directory', 'test_fits_input')
        copy_delay = test_settings.get('copy_delay', 2.5)
        
        print(f"监控目录: {monitor_dir}")
        print(f"源目录: {source_dir}")
        print(f"复制延迟: {copy_delay} 秒")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        # 检查源目录
        if not os.path.exists(source_dir):
            print(f"错误: 源目录不存在: {source_dir}")
            print("请确保源目录存在并包含FITS文件")
            return False
        
        # 创建目标目录
        os.makedirs(monitor_dir, exist_ok=True)
        
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


def run_simple_test():
    """运行简单测试（仅文件复制）"""
    print("=" * 60)
    print("FITS文件复制测试")
    print("=" * 60)
    print("仅运行文件复制器，不启动监控器")
    print("-" * 60)
    
    try:
        copy_test_files()
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
            enable_recording=enable_recording
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
  python test_runner.py                    # 完整测试（监控器+文件复制器）
  python test_runner.py --copy-only        # 仅运行文件复制测试
  python test_runner.py --monitor-only     # 仅运行监控器测试
  python test_runner.py --interval 3       # 自定义扫描间隔
        """
    )
    
    parser.add_argument('--copy-only', action='store_true',
                       help='仅运行文件复制测试')
    parser.add_argument('--monitor-only', action='store_true',
                       help='仅运行监控器测试')
    parser.add_argument('--interval', type=int, default=None,
                       help='设置监控扫描间隔（秒）')
    parser.add_argument('--config', type=str, default='config.json',
                       help='指定配置文件路径')
    
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    
    # 应用命令行参数覆盖配置
    if args.interval is not None:
        config.set('monitor_settings', 'scan_interval', args.interval)
    
    # 根据参数选择运行模式
    if args.copy_only:
        run_simple_test()
    elif args.monitor_only:
        run_monitor_only()
    else:
        # 完整测试模式
        test_runner = TestRunner(config)
        if test_runner.start_test():
            test_runner.wait_for_completion()


if __name__ == "__main__":
    main()
