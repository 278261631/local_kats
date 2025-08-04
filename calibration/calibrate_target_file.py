#!/usr/bin/env python3
"""
校准指定的目标FITS文件
专门用于校准: GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit

Author: Augment Agent
Date: 2025-08-04
"""

import sys
import logging
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from fits_calibration import FITSCalibrator
from calibration_config import get_calibration_config, validate_calibration_files

def main(skip_bias=False, skip_dark=False, skip_flat=False):
    """校准指定的目标文件"""

    print("🌟 FITS图像校准工具")
    print("=" * 50)
    print("目标文件: GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit")
    print("校准文件: E:\\fix_data\\calibration\\gy5\\")

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
        print("模式: 完整校准 (bias + dark + flat)")
    print("=" * 50)
    
    # 定义文件路径
    target_file = r"E:\fix_data\test\GY5\20250628\K053\GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit"
    output_dir = Path("calibrated_output")
    
    try:
        # 1. 检查目标文件是否存在
        print("1. 检查目标文件...")
        if not Path(target_file).exists():
            print(f"❌ 目标文件不存在: {target_file}")
            return False
        
        file_size = Path(target_file).stat().st_size / (1024 * 1024)
        print(f"✓ 目标文件存在 ({file_size:.1f} MB)")
        
        # 2. 验证校准文件
        print("\n2. 验证校准文件...")
        validation_results = validate_calibration_files('gy5')
        
        all_files_exist = True
        for frame_type, info in validation_results.items():
            status = "✓" if info['exists'] else "❌"
            size_mb = info['size'] / (1024 * 1024) if info['size'] > 0 else 0
            print(f"   {status} {frame_type.upper()}: {Path(info['path']).name}")
            if info['exists']:
                print(f"      文件大小: {size_mb:.1f} MB")
            else:
                print(f"      文件不存在!")
                all_files_exist = False
        
        if not all_files_exist:
            print("\n❌ 部分校准文件不存在，无法继续!")
            return False
        
        print("✓ 所有校准文件验证通过")
        
        # 3. 创建输出目录
        print(f"\n3. 创建输出目录...")
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 输出目录: {output_dir.absolute()}")
        
        # 4. 初始化校准器
        print("\n4. 初始化校准器...")
        calibrator = FITSCalibrator(
            output_dir=output_dir,
            log_level=logging.INFO,
            skip_bias=skip_bias,
            skip_dark=skip_dark,
            skip_flat=skip_flat
        )
        
        # 5. 加载校准帧
        print("\n5. 加载校准帧...")
        config = get_calibration_config('gy5')

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
        
        # 6. 执行校准
        print("\n6. 执行校准...")
        print("   这可能需要几分钟时间，请耐心等待...")
        
        output_path = calibrator.calibrate_image(target_file)
        
        # 7. 验证输出
        print("\n7. 验证输出...")
        output_file = Path(output_path)
        if output_file.exists():
            output_size = output_file.stat().st_size / (1024 * 1024)
            print(f"✓ 校准完成!")
            print(f"   输出文件: {output_file.name}")
            print(f"   文件大小: {output_size:.1f} MB")
            print(f"   完整路径: {output_file.absolute()}")
            
            # 显示校准信息
            print(f"\n📊 校准信息:")
            if skip_bias:
                print(f"   - Bias减除: ⚠️  跳过 (用户设置)")
            else:
                print(f"   - Bias减除: ✓ (消除读出噪声)")

            if skip_dark:
                print(f"   - Dark减除: ⚠️  跳过 (用户设置)")
            else:
                print(f"   - Dark减除: ✓ (消除热噪声，缩放因子: 2.0)")

            if skip_flat:
                print(f"   - Flat校正: ⚠️  跳过 (用户设置)")
            else:
                print(f"   - Flat校正: ✓ (校正像素响应不均匀性)")
            
            return True
        else:
            print("❌ 校准失败，输出文件未生成")
            return False
            
    except Exception as e:
        print(f"\n❌ 校准过程中发生错误: {e}")
        return False

def show_usage_info():
    """显示使用说明"""
    print("\n" + "=" * 50)
    print("📖 使用说明")
    print("=" * 50)
    print("1. 确保校准文件存在于 E:\\fix_data\\calibration\\gy5\\")
    print("2. 确保目标文件存在于指定路径")
    print("3. 运行此脚本进行校准")
    print("4. 校准后的文件将保存在 calibrated_output\\ 目录中")
    print("\n校准流程:")
    print("  原始图像 → Bias减除 → Dark减除 → Flat校正 → 校准图像")
    print("\n校准文件说明:")
    print("  - master_bias_bin2.fits: 偏置帧，消除读出噪声")
    print("  - master_dark_bin2_30s.fits: 暗电流帧，消除热噪声")
    print("  - master_flat_C_bin2.fits: 平场帧，校正像素响应")

if __name__ == "__main__":
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='校准指定的FITS文件')
    parser.add_argument('--skip-bias', action='store_true', help='跳过bias减除')
    parser.add_argument('--skip-dark', action='store_true', help='跳过dark减除')
    parser.add_argument('--skip-flat', action='store_true', help='跳过平场校正')
    args = parser.parse_args()

    try:
        success = main(skip_bias=args.skip_bias, skip_dark=args.skip_dark, skip_flat=args.skip_flat)

        if success:
            print("\n🎉 校准成功完成!")
            show_usage_info()
        else:
            print("\n💥 校准失败!")
            print("请检查错误信息并确保所有文件路径正确。")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 未预期的错误: {e}")
        sys.exit(1)
