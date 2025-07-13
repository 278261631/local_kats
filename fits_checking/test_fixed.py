#!/usr/bin/env python3
"""
测试修复后的FITS监控系统
"""

import os
import sys
import time
import logging

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_logging():
    """测试日志输出是否正常"""
    print("测试1: 日志输出")
    
    # 配置测试日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test_log.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('test')
    
    try:
        # 测试各种字符输出
        logger.info("[OK] FWHM: 优秀 (< 2.0 像素)")
        logger.info("[GOOD] 椭圆度: 良好 (0.1-0.2)")
        logger.info("[FAIR] 源数量: 一般 (10-50)")
        logger.info("[POOR] 背景RMS: 较差")
        logger.info("总体评估: 图像质量良好 [OK]")
        print("✓ 日志输出测试通过")
        return True
    except Exception as e:
        print(f"✗ 日志输出测试失败: {e}")
        return False

def test_matplotlib():
    """测试matplotlib图表显示"""
    print("\n测试2: matplotlib图表显示")
    
    try:
        import matplotlib
        matplotlib.use('TkAgg')  # 设置后端
        import matplotlib.pyplot as plt
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 创建简单测试图表
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot([1, 2, 3, 4], [1, 4, 2, 3], 'b-o')
        ax.set_title('测试图表 - 中文显示')
        ax.set_xlabel('时间')
        ax.set_ylabel('数值')
        ax.grid(True)
        
        plt.show(block=False)
        print("✓ matplotlib图表创建成功")
        print("  请检查是否有独立窗口显示")
        
        time.sleep(3)  # 显示3秒
        plt.close(fig)
        print("✓ 图表窗口已关闭")
        return True
        
    except Exception as e:
        print(f"✗ matplotlib测试失败: {e}")
        return False

def test_config_loader():
    """测试配置加载器"""
    print("\n测试3: 配置加载器")
    
    try:
        from config_loader import ConfigLoader
        
        config = ConfigLoader()
        monitor_settings = config.get_monitor_settings()
        
        print(f"✓ 配置加载成功")
        print(f"  监控目录: {monitor_settings.get('monitor_directory', 'N/A')}")
        print(f"  扫描间隔: {monitor_settings.get('scan_interval', 'N/A')} 秒")
        print(f"  图表显示: {monitor_settings.get('enable_plotting', 'N/A')}")
        print(f"  数据记录: {monitor_settings.get('enable_recording', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"✗ 配置加载器测试失败: {e}")
        return False

def test_quality_analyzer():
    """测试质量分析器（不使用真实FITS文件）"""
    print("\n测试4: 质量分析器基本功能")
    
    try:
        from fits_monitor import FITSQualityAnalyzer
        import numpy as np
        
        analyzer = FITSQualityAnalyzer()
        
        # 创建模拟数据
        test_metrics = {
            'n_sources': 35,
            'fwhm': 2.5,
            'ellipticity': 0.15,
            'lm5sig': 20.5,
            'background_mean': 1000.0,
            'background_rms': 50.0
        }
        
        # 测试质量评估
        print("模拟质量评估结果:")
        analyzer.print_quality_results(test_metrics)
        
        print("✓ 质量分析器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 质量分析器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("FITS监控系统修复验证测试")
    print("=" * 60)
    print("测试内容:")
    print("1. 日志输出（解决Unicode编码问题）")
    print("2. matplotlib图表显示（独立窗口）")
    print("3. 配置加载器")
    print("4. 质量分析器基本功能")
    print("-" * 60)
    
    results = []
    
    # 运行各项测试
    results.append(test_logging())
    results.append(test_matplotlib())
    results.append(test_config_loader())
    results.append(test_quality_analyzer())
    
    # 总结测试结果
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("-" * 60)
    
    passed = sum(results)
    total = len(results)
    
    test_names = [
        "日志输出",
        "matplotlib图表显示", 
        "配置加载器",
        "质量分析器"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "通过" if result else "失败"
        print(f"{i+1}. {name}: {status}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("✓ 所有测试通过！系统修复成功")
        print("\n可以安全使用以下命令启动系统:")
        print("  python fits_checking/run_monitor.py --test")
    else:
        print("✗ 部分测试失败，请检查错误信息")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
