#!/usr/bin/env python3
"""
FITS监控系统快速设置脚本
自动创建配置文件和检查环境
"""

import os
import shutil
import json
from pathlib import Path


def setup_config():
    """设置配置文件"""
    config_file = 'config.json'
    template_file = 'config.json.template'
    
    print("🔧 配置文件设置")
    print("-" * 50)
    
    if os.path.exists(config_file):
        print(f"✓ 配置文件已存在: {config_file}")
        return True
    
    if not os.path.exists(template_file):
        print(f"✗ 模板文件不存在: {template_file}")
        return False
    
    # 复制模板文件
    shutil.copy(template_file, config_file)
    print(f"✓ 已从模板创建配置文件: {config_file}")
    
    # 读取配置并提示用户修改
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("\n📝 请根据您的环境修改以下路径:")
        print(f"  监控目录: {config['monitor_settings']['monitor_directory']}")
        print(f"  源目录: {config['test_settings']['source_directory']}")
        print(f"\n编辑文件: {config_file}")
        
    except Exception as e:
        print(f"✗ 读取配置文件失败: {e}")
        return False
    
    return True


def check_directories():
    """检查目录是否存在"""
    print("\n📁 目录检查")
    print("-" * 50)
    
    config_file = 'config.json'
    if not os.path.exists(config_file):
        print("○ 配置文件不存在，跳过目录检查")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检查监控目录
        monitor_dir = config['monitor_settings']['monitor_directory']
        if os.path.exists(monitor_dir):
            print(f"✓ 监控目录存在: {monitor_dir}")
        else:
            print(f"✗ 监控目录不存在: {monitor_dir}")
            create = input("  是否创建该目录? (y/N): ").lower().strip()
            if create == 'y':
                os.makedirs(monitor_dir, exist_ok=True)
                print(f"✓ 已创建监控目录: {monitor_dir}")
        
        # 检查源目录
        source_dir = config['test_settings']['source_directory']
        if os.path.exists(source_dir):
            print(f"✓ 源目录存在: {source_dir}")
        else:
            print(f"✗ 源目录不存在: {source_dir}")
            print("  请手动创建该目录并放入FITS文件用于测试")
    
    except Exception as e:
        print(f"✗ 检查目录时出错: {e}")


def check_dependencies():
    """检查依赖包"""
    print("\n📦 依赖包检查")
    print("-" * 50)
    
    required_packages = [
        'numpy',
        'pandas', 
        'matplotlib',
        'astropy',
        'sep',
        'scipy',
        'photutils'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}: 已安装")
        except ImportError:
            print(f"✗ {package}: 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n缺少 {len(missing_packages)} 个依赖包:")
        print("安装命令:")
        print(f"  pip install {' '.join(missing_packages)}")
        print("或者:")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("\n✓ 所有依赖包都已安装")
        return True


def run_quick_test():
    """运行快速测试"""
    print("\n🧪 快速测试")
    print("-" * 50)
    
    try:
        # 测试配置加载
        from config_loader import ConfigLoader
        config_loader = ConfigLoader()
        print("✓ 配置加载器测试通过")
        
        # 测试监控器导入
        from fits_monitor import FITSFileMonitor
        print("✓ 监控器模块导入成功")
        
        # 测试图表查看器导入
        from plot_viewer import FITSDataPlotter
        print("✓ 图表查看器模块导入成功")
        
        # 测试测试运行器导入
        from test_runner import TestRunner
        print("✓ 测试运行器模块导入成功")
        
        print("\n✓ 所有模块测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 模块测试失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("FITS监控系统 - 快速设置")
    print("=" * 60)
    
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    success_count = 0
    total_steps = 4
    
    # 1. 设置配置文件
    if setup_config():
        success_count += 1
    
    # 2. 检查目录
    check_directories()
    success_count += 1
    
    # 3. 检查依赖
    if check_dependencies():
        success_count += 1
    
    # 4. 运行测试
    if run_quick_test():
        success_count += 1
    
    # 总结
    print("\n" + "=" * 60)
    print("设置完成")
    print("=" * 60)
    print(f"完成步骤: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("✓ 所有设置完成！")
        print("\n🚀 现在可以使用:")
        print("  python start.py status      # 检查状态")
        print("  python start.py test        # 运行测试")
        print("  python start.py monitor     # 启动监控")
        print("  python start.py plot        # 查看图表")
    else:
        print("⚠ 部分设置未完成，请检查上述错误信息")
        print("\n📖 查看详细说明:")
        print("  CONFIG_SETUP.md - 配置文件设置指南")
        print("  FINAL_COMPLETE_GUIDE.md - 完整使用指南")


if __name__ == "__main__":
    main()
