#!/usr/bin/env python3
"""
Ryan Oelkers DIA 演示脚本
展示如何使用DIA分析器处理FITS文件
"""

import os
import sys
from ryanoelkers_dia import RyanOelkersDIA
from create_test_data import create_test_fits_pair


def run_demo():
    """运行DIA演示"""
    print("=" * 60)
    print("Ryan Oelkers DIA 演示")
    print("=" * 60)
    
    # 1. 创建测试数据
    print("\n步骤1: 创建测试数据")
    print("-" * 30)
    
    test_dir = "demo_data"
    os.makedirs(test_dir, exist_ok=True)
    
    ref_file, sci_file = create_test_fits_pair(test_dir)
    
    # 2. 初始化DIA分析器
    print(f"\n步骤2: 初始化DIA分析器")
    print("-" * 30)
    
    dia = RyanOelkersDIA(
        detection_threshold=3.0,  # 使用较低的阈值以检测更多源
        psf_matching=True
    )
    
    print(f"检测阈值: {dia.detection_threshold} sigma")
    print(f"PSF匹配: {'启用' if dia.psf_matching else '禁用'}")
    
    # 3. 执行DIA处理
    print(f"\n步骤3: 执行DIA处理")
    print("-" * 30)
    
    result = dia.process_dia(ref_file, sci_file, test_dir)
    
    # 4. 显示结果
    print(f"\n步骤4: 处理结果")
    print("-" * 30)
    
    if result and result['success']:
        print(f"✓ DIA处理成功!")
        print(f"检测到瞬变源: {result['transients_detected']} 个")
        
        if result['transients']:
            print(f"\n检测到的瞬变源:")
            for i, transient in enumerate(result['transients']):
                print(f"  源 {i+1}: 位置=({transient['x']:.1f}, {transient['y']:.1f}), "
                      f"SNR={transient['snr']:.1f}, 流量={transient['flux']:.2e}")
        
        print(f"\n输出文件:")
        print(f"  差异图像: {os.path.basename(result['difference_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")
        
        # 5. 验证结果
        print(f"\n步骤5: 验证结果")
        print("-" * 30)
        
        expected_positions = [(75, 125), (175, 75), (225, 175), (125, 225)]
        detected_positive = [t for t in result['transients'] if t['flux'] > 0]
        
        print(f"预期瞬变源位置: {expected_positions}")
        print(f"检测到正流量源: {len(detected_positive)} 个")
        
        for i, transient in enumerate(detected_positive):
            print(f"  检测源 {i+1}: ({transient['x']:.1f}, {transient['y']:.1f})")
            
        return True
        
    else:
        print(f"✗ DIA处理失败")
        return False


def cleanup_demo():
    """清理演示文件"""
    import shutil
    
    demo_dir = "demo_data"
    if os.path.exists(demo_dir):
        try:
            shutil.rmtree(demo_dir)
            print(f"\n清理完成: 已删除 {demo_dir} 目录")
        except Exception as e:
            print(f"\n清理失败: {e}")


if __name__ == '__main__':
    try:
        success = run_demo()
        
        print(f"\n" + "=" * 60)
        if success:
            print("✓ 演示完成! Ryan Oelkers DIA 工作正常")
        else:
            print("✗ 演示失败")
        print("=" * 60)
        
        # 询问是否清理文件
        try:
            response = input("\n是否删除演示文件? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                cleanup_demo()
        except KeyboardInterrupt:
            print("\n\n演示结束")
            
    except Exception as e:
        print(f"\n演示过程中出错: {e}")
        sys.exit(1)
