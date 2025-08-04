#!/usr/bin/env python3
"""
批量FITS图像校准脚本
支持目录扫描和批量处理多个FITS文件

Author: Augment Agent
Date: 2025-08-04
"""

import sys
import os
import glob
import logging
from pathlib import Path
import argparse
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from fits_calibration import FITSCalibrator
from calibration_config import (
    get_calibration_config, 
    validate_calibration_files, 
    create_output_directory,
    SUPPORTED_EXTENSIONS
)

def find_fits_files(input_dir, recursive=False):
    """
    查找目录中的FITS文件
    
    Args:
        input_dir (str): 输入目录
        recursive (bool): 是否递归搜索子目录
        
    Returns:
        list: FITS文件路径列表
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise ValueError(f"输入目录不存在: {input_dir}")
    
    fits_files = []
    
    for ext in SUPPORTED_EXTENSIONS:
        if recursive:
            pattern = f"**/*{ext}"
            fits_files.extend(input_path.glob(pattern))
        else:
            pattern = f"*{ext}"
            fits_files.extend(input_path.glob(pattern))
    
    return sorted(fits_files)

def setup_batch_logging(output_dir, log_level=logging.INFO):
    """设置批量处理日志"""
    log_file = output_dir / f"batch_calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # 创建logger
    logger = logging.getLogger('BatchCalibrator')
    logger.setLevel(log_level)
    
    # 清除现有handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 文件handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def batch_calibrate(input_dir, output_dir=None, instrument='gy5',
                   recursive=False, skip_existing=True, max_files=None,
                   skip_bias=False, skip_dark=False, skip_flat=False):
    """
    批量校准FITS文件

    Args:
        input_dir (str): 输入目录
        output_dir (str): 输出目录
        instrument (str): 仪器名称
        recursive (bool): 是否递归搜索
        skip_existing (bool): 是否跳过已存在的文件
        max_files (int): 最大处理文件数
        skip_bias (bool): 是否跳过bias减除
        skip_dark (bool): 是否跳过dark减除
        skip_flat (bool): 是否跳过平场校正

    Returns:
        dict: 处理结果统计
    """
    
    # 创建输出目录
    if output_dir is None:
        output_dir = Path(input_dir) / "calibrated"
    output_path = create_output_directory(output_dir)
    
    # 设置日志
    logger = setup_batch_logging(output_path)
    
    logger.info("=" * 60)
    logger.info("开始批量FITS图像校准")
    logger.info("=" * 60)
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"输出目录: {output_path}")
    logger.info(f"仪器配置: {instrument}")
    logger.info(f"递归搜索: {recursive}")
    logger.info(f"跳过已存在: {skip_existing}")
    logger.info(f"跳过bias减除: {skip_bias}")
    logger.info(f"跳过dark减除: {skip_dark}")
    logger.info(f"跳过平场校正: {skip_flat}")
    
    # 验证校准文件
    logger.info("验证校准文件...")
    validation_results = validate_calibration_files(instrument)
    
    missing_files = []
    for frame_type, info in validation_results.items():
        if not info['exists']:
            missing_files.append(f"{frame_type}: {info['path']}")
    
    if missing_files:
        logger.error("以下校准文件不存在:")
        for missing in missing_files:
            logger.error(f"  - {missing}")
        raise FileNotFoundError("校准文件缺失")
    
    logger.info("✓ 所有校准文件验证通过")
    
    # 查找FITS文件
    logger.info("搜索FITS文件...")
    fits_files = find_fits_files(input_dir, recursive)
    
    if not fits_files:
        logger.warning(f"在目录 {input_dir} 中未找到FITS文件")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
    
    logger.info(f"找到 {len(fits_files)} 个FITS文件")
    
    # 限制处理文件数
    if max_files and len(fits_files) > max_files:
        fits_files = fits_files[:max_files]
        logger.info(f"限制处理前 {max_files} 个文件")
    
    # 初始化校准器
    logger.info("初始化校准器...")
    calibrator = FITSCalibrator(
        output_dir=output_path,
        log_level=logging.WARNING,
        skip_bias=skip_bias,
        skip_dark=skip_dark,
        skip_flat=skip_flat
    )

    # 加载校准帧
    config = get_calibration_config(instrument)

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
        logger.info(f"⚠️  跳过校准步骤: {', '.join(skipped_steps)}")
    
    logger.info("✓ 校准器初始化完成")
    
    # 批量处理
    results = {'total': len(fits_files), 'success': 0, 'failed': 0, 'skipped': 0}
    
    for i, fits_file in enumerate(fits_files, 1):
        logger.info(f"处理 {i}/{len(fits_files)}: {fits_file.name}")
        
        try:
            # 生成输出文件名
            output_name = f"{fits_file.stem}_calibrated.fits"
            output_file = output_path / output_name
            
            # 检查是否跳过已存在的文件
            if skip_existing and output_file.exists():
                logger.info(f"  跳过已存在的文件: {output_name}")
                results['skipped'] += 1
                continue
            
            # 执行校准
            calibrated_path = calibrator.calibrate_image(
                str(fits_file), 
                str(output_file)
            )
            
            # 检查输出文件
            if Path(calibrated_path).exists():
                file_size = Path(calibrated_path).stat().st_size / (1024 * 1024)
                logger.info(f"  ✓ 校准成功: {output_name} ({file_size:.1f} MB)")
                results['success'] += 1
            else:
                logger.error(f"  ✗ 输出文件未生成: {output_name}")
                results['failed'] += 1
                
        except Exception as e:
            logger.error(f"  ✗ 校准失败: {str(e)}")
            results['failed'] += 1
    
    # 输出统计结果
    logger.info("=" * 60)
    logger.info("批量校准完成")
    logger.info("=" * 60)
    logger.info(f"总文件数: {results['total']}")
    logger.info(f"成功: {results['success']}")
    logger.info(f"失败: {results['failed']}")
    logger.info(f"跳过: {results['skipped']}")
    logger.info(f"成功率: {results['success']/results['total']*100:.1f}%")
    
    return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='批量FITS图像校准工具')
    
    parser.add_argument('input_dir', help='输入目录路径')
    parser.add_argument('-o', '--output', help='输出目录路径')
    parser.add_argument('-i', '--instrument', default='gy5', help='仪器名称 (默认: gy5)')
    parser.add_argument('-r', '--recursive', action='store_true', help='递归搜索子目录')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已存在的文件')
    parser.add_argument('-n', '--max-files', type=int, help='最大处理文件数')
    parser.add_argument('--skip-bias', action='store_true', help='跳过bias减除')
    parser.add_argument('--skip-dark', action='store_true', help='跳过dark减除')
    parser.add_argument('--skip-flat', action='store_true', help='跳过平场校正')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    try:
        # 执行批量校准
        results = batch_calibrate(
            input_dir=args.input_dir,
            output_dir=args.output,
            instrument=args.instrument,
            recursive=args.recursive,
            skip_existing=not args.no_skip,
            max_files=args.max_files,
            skip_bias=args.skip_bias,
            skip_dark=args.skip_dark,
            skip_flat=args.skip_flat
        )
        
        # 根据结果设置退出码
        if results['failed'] > 0:
            print(f"\n警告: {results['failed']} 个文件校准失败")
            sys.exit(1)
        else:
            print(f"\n✓ 所有文件校准成功!")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
