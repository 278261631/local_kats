#!/usr/bin/env python3
"""
测试diff操作的文件输出
专门验证diff_orb生成的文件是否被正确识别和收集
"""

import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
import sys

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from diff_orb_integration import DiffOrbIntegration
from astropy.io import fits


def create_test_fits_pair():
    """创建一对测试FITS文件"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="diff_output_test_")
    
    # 创建观测文件（包含新亮点）
    obs_data = np.random.normal(1000, 100, (300, 300))
    # 添加新亮点
    obs_data[100:105, 100:105] += 2000
    obs_data[200:205, 150:155] += 1500
    
    obs_file = os.path.join(temp_dir, "observation.fits")
    hdu = fits.PrimaryHDU(obs_data)
    hdu.header['OBJECT'] = 'Test Observation'
    hdu.writeto(obs_file, overwrite=True)
    
    # 创建模板文件（基础背景）
    template_data = np.random.normal(1000, 100, (300, 300))
    
    template_file = os.path.join(temp_dir, "template.fits")
    hdu = fits.PrimaryHDU(template_data)
    hdu.header['OBJECT'] = 'Test Template'
    hdu.writeto(template_file, overwrite=True)
    
    return temp_dir, obs_file, template_file


def test_diff_output():
    """测试diff操作的文件输出"""
    print("=" * 60)
    print("测试diff操作文件输出")
    print("=" * 60)
    
    # 创建测试文件
    temp_dir, obs_file, template_file = create_test_fits_pair()
    
    try:
        print(f"测试目录: {temp_dir}")
        print(f"观测文件: {os.path.basename(obs_file)}")
        print(f"模板文件: {os.path.basename(template_file)}")
        
        # 创建diff集成对象
        diff_integration = DiffOrbIntegration()
        
        if not diff_integration.is_available():
            print("diff_orb模块不可用，跳过测试")
            return
        
        print("\n执行diff操作...")
        
        # 创建输出目录
        output_dir = os.path.join(temp_dir, "results")
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行diff操作
        result = diff_integration.process_diff(obs_file, template_file, output_dir)
        
        if result:
            print(f"\ndiff操作成功:")
            print(f"  对齐成功: {result.get('alignment_success', False)}")
            print(f"  新亮点数量: {result.get('new_bright_spots', 0)}")
            print(f"  输出目录: {result.get('output_directory', 'N/A')}")
            
            # 检查输出文件
            output_files = result.get('output_files', {})
            print(f"\n收集到的输出文件 ({len(output_files)} 个):")
            for file_type, file_path in output_files.items():
                print(f"  {file_type}: {os.path.basename(file_path)}")
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    print(f"    文件大小: {size} 字节")
                else:
                    print(f"    ❌ 文件不存在!")
            
            # 直接扫描输出目录
            print(f"\n直接扫描输出目录:")
            all_files = list(Path(output_dir).glob("*"))
            print(f"  总文件数: {len(all_files)}")
            
            for file_path in all_files:
                if file_path.is_file():
                    size = file_path.stat().st_size
                    print(f"  {file_path.name} ({size} 字节)")
            
            # 检查是否有difference相关文件
            diff_files = list(Path(output_dir).glob("*diff*"))
            diff_files.extend(list(Path(output_dir).glob("*difference*")))
            
            print(f"\n差异相关文件 ({len(diff_files)} 个):")
            for file_path in diff_files:
                print(f"  {file_path.name}")
            
            # 检查关键文件是否存在
            print(f"\n关键文件检查:")
            key_files = ['difference_fits', 'marked_fits', 'aligned_fits']
            for key in key_files:
                if key in output_files:
                    file_path = output_files[key]
                    exists = os.path.exists(file_path)
                    print(f"  {key}: {'✓' if exists else '❌'} {os.path.basename(file_path)}")
                else:
                    print(f"  {key}: ❌ 未找到")
            
            # 生成摘要
            summary = diff_integration.get_diff_summary(result)
            print(f"\n操作摘要:")
            print(summary)
            
        else:
            print("❌ diff操作失败")
            
            # 即使失败也检查输出目录
            print(f"\n检查输出目录 (操作失败后):")
            if os.path.exists(output_dir):
                all_files = list(Path(output_dir).glob("*"))
                print(f"  文件数: {len(all_files)}")
                for file_path in all_files:
                    if file_path.is_file():
                        print(f"  {file_path.name}")
            else:
                print("  输出目录不存在")
    
    finally:
        # 清理测试目录
        try:
            shutil.rmtree(temp_dir)
            print(f"\n已清理测试目录: {temp_dir}")
        except Exception as e:
            print(f"\n清理测试目录失败: {e}")


def test_file_collection():
    """测试文件收集逻辑"""
    print("\n" + "=" * 60)
    print("测试文件收集逻辑")
    print("=" * 60)
    
    # 创建临时目录和测试文件
    temp_dir = tempfile.mkdtemp(prefix="file_collection_test_")
    
    try:
        # 创建各种类型的测试文件
        test_files = [
            "test_difference.fits",
            "result_diff.fits", 
            "output_marked.fits",
            "aligned_image.fits",
            "reference_template.fits",
            "bright_spots_report.txt",
            "visualization.jpg",
            "some_other_file.fits",
            "random_data.txt"
        ]
        
        print(f"创建测试文件:")
        for filename in test_files:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(f"Test file: {filename}")
            print(f"  {filename}")
        
        # 测试文件收集
        diff_integration = DiffOrbIntegration()
        output_files = diff_integration._collect_output_files(temp_dir)
        
        print(f"\n文件收集结果:")
        print(f"  收集到 {len(output_files)} 个文件")
        for file_type, file_path in output_files.items():
            print(f"  {file_type}: {os.path.basename(file_path)}")
    
    finally:
        # 清理
        try:
            shutil.rmtree(temp_dir)
            print(f"\n已清理测试目录")
        except:
            pass


def main():
    """主测试函数"""
    print("diff操作文件输出测试")
    
    # 测试实际的diff操作
    test_diff_output()
    
    # 测试文件收集逻辑
    test_file_collection()


if __name__ == "__main__":
    main()
