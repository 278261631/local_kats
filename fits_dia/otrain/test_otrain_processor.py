#!/usr/bin/env python3
"""
测试O'TRAIN处理器
"""

import os
import sys
import numpy as np
from astropy.io import fits
import tempfile
import shutil

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from process_difference_with_otrain import OTrainProcessor

def create_test_fits_file():
    """
    创建一个测试用的FITS文件
    """
    # 创建模拟的差异图像数据
    image_size = 200
    image_data = np.random.normal(0, 0.1, (image_size, image_size))
    
    # 添加一些模拟的瞬变天体
    # 瞬变天体1: 强信号
    image_data[50:55, 50:55] += 2.0
    
    # 瞬变天体2: 中等信号
    image_data[100:103, 100:103] += 1.0
    
    # 瞬变天体3: 弱信号
    image_data[150, 150] += 0.8
    
    # 添加一些噪声点
    for _ in range(5):
        x, y = np.random.randint(0, image_size, 2)
        image_data[y, x] += np.random.uniform(0.3, 0.6)
    
    # 创建临时FITS文件
    temp_file = tempfile.NamedTemporaryFile(suffix='.fits', delete=False)
    
    # 创建FITS头
    header = fits.Header()
    header['OBJECT'] = 'TEST_DIFFERENCE'
    header['INSTRUME'] = 'TEST'
    header['DATE-OBS'] = '2025-01-23'
    
    # 保存FITS文件
    hdu = fits.PrimaryHDU(data=image_data, header=header)
    hdu.writeto(temp_file.name, overwrite=True)
    
    return temp_file.name

def test_otrain_processor():
    """
    测试O'TRAIN处理器
    """
    print("="*60)
    print("测试O'TRAIN处理器")
    print("="*60)
    
    # 创建测试FITS文件
    print("1. 创建测试FITS文件...")
    test_fits_file = create_test_fits_file()
    print(f"   测试文件: {test_fits_file}")
    
    # 创建临时输出目录
    temp_output_dir = tempfile.mkdtemp(prefix='otrain_test_')
    print(f"   输出目录: {temp_output_dir}")
    
    try:
        # 创建处理器
        print("\n2. 初始化O'TRAIN处理器...")
        processor = OTrainProcessor(output_dir=temp_output_dir)
        
        # 测试加载FITS文件
        print("\n3. 测试FITS文件加载...")
        image_data, header, success = processor.load_fits_image(test_fits_file)
        if success:
            print(f"   ✓ FITS文件加载成功")
            print(f"   图像大小: {image_data.shape}")
            print(f"   数据范围: [{np.min(image_data):.3f}, {np.max(image_data):.3f}]")
        else:
            print("   ✗ FITS文件加载失败")
            return False
        
        # 测试候选检测
        print("\n4. 测试候选天体检测...")
        candidates = processor.detect_candidates(image_data)
        print(f"   检测到 {len(candidates)} 个候选天体")
        for i, (x, y, flux, size) in enumerate(candidates):
            print(f"   候选{i+1}: 位置=({x:.1f}, {y:.1f}), 流量={flux:.2f}, 大小={size}")
        
        # 测试cutout提取
        print("\n5. 测试cutout提取...")
        cutouts = processor.extract_cutouts(image_data, candidates)
        print(f"   提取了 {len(cutouts)} 个cutout")
        for cutout_data in cutouts:
            print(f"   Cutout {cutout_data['id']}: 大小={cutout_data['image'].shape}")
        
        # 测试分类
        print("\n6. 测试CNN分类...")
        results = processor.simulate_otrain_classification(cutouts)
        print(f"   分类了 {len(results)} 个候选天体")
        real_count = sum(1 for r in results if r['classification'] == 'real')
        print(f"   真实瞬变天体: {real_count}/{len(results)}")
        
        # 测试完整处理流程
        print("\n7. 测试完整处理流程...")
        summary = processor.process_fits_file(test_fits_file)
        
        if summary:
            print("   ✓ 完整处理成功")
            print(f"   候选天体: {summary['candidates']}")
            print(f"   真实瞬变天体: {summary['real_transients']}")
            
            # 检查输出文件
            output_files = os.listdir(temp_output_dir)
            print(f"   生成文件: {len(output_files)} 个")
            for file in output_files:
                print(f"     - {file}")
            
            return True
        else:
            print("   ✗ 完整处理失败")
            return False
    
    except Exception as e:
        print(f"   ✗ 测试过程中出错: {str(e)}")
        return False
    
    finally:
        # 清理临时文件
        print(f"\n8. 清理临时文件...")
        try:
            os.unlink(test_fits_file)
            shutil.rmtree(temp_output_dir)
            print("   ✓ 临时文件清理完成")
        except Exception as e:
            print(f"   ⚠ 清理临时文件时出错: {str(e)}")

def test_with_real_file():
    """
    使用真实的测试文件进行测试
    """
    print("\n" + "="*60)
    print("使用真实文件测试")
    print("="*60)
    
    # 测试文件路径
    test_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(test_file):
        print(f"测试文件不存在: {test_file}")
        return False
    
    try:
        # 创建处理器
        processor = OTrainProcessor(output_dir="test_results")
        
        # 处理文件
        print(f"处理文件: {test_file}")
        summary = processor.process_fits_file(test_file)
        
        if summary:
            print("✓ 真实文件处理成功")
            print(f"候选天体: {summary['candidates']}")
            print(f"真实瞬变天体: {summary['real_transients']}")
            return True
        else:
            print("✗ 真实文件处理失败")
            return False
    
    except Exception as e:
        print(f"✗ 处理真实文件时出错: {str(e)}")
        return False

def main():
    """
    主测试函数
    """
    print("O'TRAIN处理器测试")
    print("="*60)
    
    # 测试1: 使用模拟数据
    success1 = test_otrain_processor()
    
    # 测试2: 使用真实数据
    success2 = test_with_real_file()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"模拟数据测试: {'✓ 通过' if success1 else '✗ 失败'}")
    print(f"真实数据测试: {'✓ 通过' if success2 else '✗ 失败'}")
    
    if success1 and success2:
        print("\n🎉 所有测试通过!")
        return True
    else:
        print("\n❌ 部分测试失败!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
