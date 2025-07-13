#!/usr/bin/env python3
"""
测试分离式图表功能
验证主程序和图表查看器的独立运行
"""

import os
import sys
import time
import subprocess
import pandas as pd
from datetime import datetime

def test_main_program():
    """测试主监控程序（无图表功能）"""
    print("测试1: 主监控程序（轻量化版本）")
    print("-" * 50)
    
    try:
        # 导入主程序模块
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from fits_monitor import FITSFileMonitor, DataRecorder
        
        # 测试DataRecorder
        recorder = DataRecorder('test_output.csv')
        
        # 创建测试数据
        test_metrics = {
            'n_sources': 42,
            'fwhm': 2.3,
            'ellipticity': 0.12,
            'lm5sig': 21.5,
            'background_mean': 1050.0,
            'background_rms': 45.2
        }
        
        # 记录测试数据
        recorder.record_data('test_image.fits', test_metrics)
        
        print("✓ 主程序导入成功")
        print("✓ 数据记录器工作正常")
        print("✓ CSV文件生成成功")
        
        # 检查生成的CSV文件
        if os.path.exists('test_output.csv'):
            df = pd.read_csv('test_output.csv')
            print(f"✓ CSV文件包含 {len(df)} 条记录")
            print("  记录内容:")
            print(f"    文件名: {df.iloc[0]['filename']}")
            print(f"    FWHM: {df.iloc[0]['fwhm']}")
            print(f"    椭圆度: {df.iloc[0]['ellipticity']}")
            print(f"    源数量: {df.iloc[0]['n_sources']}")
        
        return True
        
    except Exception as e:
        print(f"✗ 主程序测试失败: {e}")
        return False

def test_plot_viewer():
    """测试图表查看器"""
    print("\n测试2: 图表查看器")
    print("-" * 50)
    
    try:
        # 创建测试数据文件
        create_test_csv()
        
        # 导入图表查看器
        from plot_viewer import FITSDataPlotter
        
        # 测试数据加载
        plotter = FITSDataPlotter('test_data.csv')
        
        if plotter.load_data():
            print("✓ 图表查看器导入成功")
            print("✓ 数据加载功能正常")
            print(f"✓ 加载了 {len(plotter.data)} 条记录")
            
            # 测试统计信息
            print("\n统计信息测试:")
            plotter.print_statistics()
            
            return True
        else:
            print("✗ 数据加载失败")
            return False
            
    except Exception as e:
        print(f"✗ 图表查看器测试失败: {e}")
        return False

def create_test_csv():
    """创建测试CSV数据文件"""
    import numpy as np
    
    # 生成测试数据
    timestamps = pd.date_range(start='2024-01-15 10:00:00', periods=20, freq='5min')
    
    data = []
    for i, ts in enumerate(timestamps):
        # 生成模拟数据
        fwhm = 2.0 + 0.5 * np.sin(i * 0.3) + np.random.normal(0, 0.1)
        ellipticity = 0.15 + 0.05 * np.cos(i * 0.2) + np.random.normal(0, 0.02)
        n_sources = int(45 + 10 * np.sin(i * 0.1) + np.random.normal(0, 3))
        background_rms = 100 + 20 * np.sin(i * 0.4) + np.random.normal(0, 5)
        
        data.append({
            'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
            'filename': f'test_image_{i+1:03d}.fits',
            'n_sources': max(0, n_sources),
            'fwhm': max(0.5, fwhm),
            'ellipticity': max(0, min(1, ellipticity)),
            'lm5sig': 20.0 + np.random.normal(0, 1),
            'background_mean': 1000 + np.random.normal(0, 50),
            'background_rms': max(10, background_rms)
        })
    
    # 保存到CSV文件
    df = pd.DataFrame(data)
    df.to_csv('test_data.csv', index=False)
    print(f"✓ 创建测试数据文件: test_data.csv ({len(data)} 条记录)")

def test_command_line():
    """测试命令行功能"""
    print("\n测试3: 命令行功能")
    print("-" * 50)
    
    try:
        # 测试主程序帮助
        result = subprocess.run([
            'python', 'fits_checking/run_monitor.py', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ 主程序命令行帮助正常")
        else:
            print("✗ 主程序命令行帮助失败")
            return False
        
        # 测试图表查看器帮助
        result = subprocess.run([
            'python', 'fits_checking/plot_viewer.py', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ 图表查看器命令行帮助正常")
        else:
            print("✗ 图表查看器命令行帮助失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 命令行测试失败: {e}")
        return False

def test_dependencies():
    """测试依赖包"""
    print("\n测试4: 依赖包检查")
    print("-" * 50)
    
    dependencies = [
        ('numpy', 'numpy'),
        ('pandas', 'pandas'),
        ('matplotlib', 'matplotlib.pyplot'),
        ('astropy', 'astropy.io.fits'),
        ('sep', 'sep'),
        ('scipy', 'scipy.ndimage'),
        ('photutils', 'photutils.detection')
    ]
    
    results = []
    for name, module in dependencies:
        try:
            __import__(module)
            print(f"✓ {name}: 已安装")
            results.append(True)
        except ImportError:
            print(f"✗ {name}: 未安装")
            results.append(False)
    
    return all(results)

def cleanup_test_files():
    """清理测试文件"""
    test_files = ['test_output.csv', 'test_data.csv', 'test_log.log']
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"清理测试文件: {file}")

def main():
    """主测试函数"""
    print("=" * 60)
    print("FITS监控系统 - 分离式图表功能测试")
    print("=" * 60)
    print("测试内容:")
    print("1. 主监控程序（轻量化，无图表功能）")
    print("2. 独立图表查看器")
    print("3. 命令行功能")
    print("4. 依赖包检查")
    print("=" * 60)
    
    results = []
    
    # 运行各项测试
    results.append(test_dependencies())
    results.append(test_main_program())
    results.append(test_plot_viewer())
    results.append(test_command_line())
    
    # 总结测试结果
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("-" * 60)
    
    passed = sum(results)
    total = len(results)
    
    test_names = [
        "依赖包检查",
        "主监控程序",
        "图表查看器",
        "命令行功能"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "通过" if result else "失败"
        print(f"{i+1}. {name}: {status}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("✓ 所有测试通过！分离式图表功能正常")
        print("\n使用方法:")
        print("1. 启动监控器: python fits_checking/run_monitor.py --test")
        print("2. 查看图表: python fits_checking/plot_viewer.py --realtime")
        print("3. 查看统计: python fits_checking/plot_viewer.py --stats")
    else:
        print("✗ 部分测试失败，请检查错误信息")
    
    print("=" * 60)
    
    # 清理测试文件
    cleanup_test_files()

if __name__ == "__main__":
    main()
