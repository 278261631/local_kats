#!/usr/bin/env python3
"""
FITS图像校准示例脚本
演示如何使用FITSCalibrator校准指定的科学图像

Author: Augment Agent
Date: 2025-08-04
"""

import sys
import logging
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from fits_calibration import FITSCalibrator
from calibration_config import get_calibration_config, validate_calibration_files, create_output_directory

def main(skip_bias=False, skip_dark=False, skip_flat=False):
    """主函数：校准指定的科学图像"""

    print("FITS图像校准示例")

    # 显示校准模式
    skipped_steps = []
    if skip_bias:
        skipped_steps.append("bias减除")
    if skip_dark:
        skipped_steps.append("dark减除")
    if skip_flat:
        skipped_steps.append("平场校正")

    if skipped_steps:
        print(f"模式: 自定义校准 (跳过: {', '.join(skipped_steps)})")
    else:
        print("模式: 完整校准")
    print("=" * 50)
    
    # 1. 验证校准文件
    print("1. 验证校准文件...")
    validation_results = validate_calibration_files('gy5')
    
    all_files_exist = True
    for frame_type, info in validation_results.items():
        status = "✓" if info['exists'] else "✗"
        size_mb = info['size'] / (1024 * 1024) if info['size'] > 0 else 0
        print(f"   {status} {frame_type.upper()}: {Path(info['path']).name if info['path'] else 'None'}")
        if info['exists']:
            print(f"      文件大小: {size_mb:.1f} MB")
        else:
            print(f"      文件不存在: {info['path']}")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ 部分校准文件不存在，请检查文件路径！")
        return False
    
    print("✓ 所有校准文件验证通过")
    
    # 2. 创建输出目录
    print("\n2. 创建输出目录...")
    output_dir = create_output_directory("calibrated_output")
    print(f"   输出目录: {output_dir.absolute()}")
    
    # 3. 初始化校准器
    print("\n3. 初始化校准器...")
    calibrator = FITSCalibrator(
        output_dir=output_dir,
        log_level=logging.INFO,
        skip_bias=skip_bias,
        skip_dark=skip_dark,
        skip_flat=skip_flat
    )
    
    # 4. 加载校准帧
    print("\n4. 加载校准帧...")
    config = get_calibration_config('gy5')

    try:
        # 根据跳过参数决定是否加载相应的校准帧
        bias_path = None if skip_bias else config['bias']
        dark_path = None if skip_dark else config['dark']
        flat_path = None if skip_flat else config['flat']

        calibrator.load_calibration_frames(
            bias_path=bias_path,
            dark_path=dark_path,
            flat_path=flat_path
        )
        calibrator.dark_exposure_time = config['dark_exposure_time']

        # 显示跳过的校准步骤
        skipped_steps = []
        if skip_bias:
            skipped_steps.append("bias减除")
        if skip_dark:
            skipped_steps.append("dark减除")
        if skip_flat:
            skipped_steps.append("平场校正")

        if skipped_steps:
            print(f"⚠️  跳过校准步骤: {', '.join(skipped_steps)}")
        print("✓ 校准帧加载完成")
        
    except Exception as e:
        print(f"❌ 校准帧加载失败: {e}")
        return False
    
    # 5. 校准科学图像
    print("\n5. 校准科学图像...")
    science_path = r"E:\fix_data\test\GY5\20250628\K053\GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit"
    
    # 检查科学图像是否存在
    if not Path(science_path).exists():
        print(f"❌ 科学图像不存在: {science_path}")
        return False
    
    print(f"   科学图像: {Path(science_path).name}")
    
    try:
        # 执行校准
        output_path = calibrator.calibrate_image(science_path)
        print(f"✓ 校准完成!")
        print(f"   输出文件: {output_path}")
        
        # 显示输出文件信息
        output_file = Path(output_path)
        if output_file.exists():
            size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"   文件大小: {size_mb:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 校准失败: {e}")
        return False

def batch_calibrate_example():
    """批量校准示例"""
    print("\n" + "=" * 50)
    print("批量校准示例")
    print("=" * 50)
    
    # 这里可以添加批量校准的示例代码
    # 例如扫描目录中的所有FITS文件并逐一校准
    
    test_dir = Path(r"E:\fix_data\test\GY5\20250628\K053")
    if not test_dir.exists():
        print(f"测试目录不存在: {test_dir}")
        return
    
    # 查找所有FITS文件
    fits_files = []
    for ext in ['.fits', '.fit']:
        fits_files.extend(test_dir.glob(f"*{ext}"))
    
    print(f"找到 {len(fits_files)} 个FITS文件:")
    for i, fits_file in enumerate(fits_files[:5], 1):  # 只显示前5个
        print(f"   {i}. {fits_file.name}")
    
    if len(fits_files) > 5:
        print(f"   ... 还有 {len(fits_files) - 5} 个文件")
    
    print("\n注意: 批量校准功能可以根据需要实现")

if __name__ == "__main__":
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='FITS图像校准示例')
    parser.add_argument('--skip-bias', action='store_true', help='跳过bias减除')
    parser.add_argument('--skip-dark', action='store_true', help='跳过dark减除')
    parser.add_argument('--skip-flat', action='store_true', help='跳过平场校正')
    args = parser.parse_args()

    try:
        # 执行单个文件校准示例
        success = main(skip_bias=args.skip_bias, skip_dark=args.skip_dark, skip_flat=args.skip_flat)

        if success:
            # 显示批量校准示例
            batch_calibrate_example()

            print("\n" + "=" * 50)
            print("校准完成! 🎉")
            print("=" * 50)
        else:
            print("\n校准失败，请检查错误信息。")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n未预期的错误: {e}")
        sys.exit(1)
