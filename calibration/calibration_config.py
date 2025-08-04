#!/usr/bin/env python3
"""
FITS图像校准配置文件
定义校准文件路径和参数

Author: Augment Agent
Date: 2025-08-04
"""

import os
from pathlib import Path

# 校准文件路径配置
CALIBRATION_PATHS = {
    'gy5': {
        'base_dir': r'E:\fix_data\calibration\gy5',
        'bias': r'E:\fix_data\calibration\gy5\master_bias_bin2.fits',
        'dark': r'E:\fix_data\calibration\gy5\master_dark_bin2_30s.fits',
        'flat': r'E:\fix_data\calibration\gy5\master_flat_C_bin2.fits',
        'dark_exposure_time': 30.0  # 暗电流帧曝光时间(秒)
    }
}

# 默认输出目录
DEFAULT_OUTPUT_DIR = Path("calibrated_output")

# 校准参数
CALIBRATION_PARAMS = {
    'output_dtype': 'float32',  # 输出数据类型
    'sigma_clip_sigma': 3.0,    # sigma裁剪参数
    'sigma_clip_maxiters': 5,   # sigma裁剪最大迭代次数
    'flat_normalization_method': 'median',  # flat帧归一化方法: 'median' 或 'mean'
    'min_flat_value': 0.1,      # flat帧最小值阈值，避免除零
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'save_to_file': True,
    'log_filename': 'calibration.log'
}

# 支持的FITS文件扩展名
SUPPORTED_EXTENSIONS = ['.fits', '.fit', '.fts']

# 曝光时间关键字（按优先级排序）
EXPOSURE_TIME_KEYWORDS = ['EXPTIME', 'EXPOSURE', 'ITIME', 'TELAPSE', 'TTIME']

# 默认曝光时间（当无法从头部获取时使用）
DEFAULT_EXPOSURE_TIME = 60.0

def get_calibration_config(instrument='gy5'):
    """
    获取指定仪器的校准配置
    
    Args:
        instrument (str): 仪器名称
        
    Returns:
        dict: 校准配置字典
    """
    if instrument not in CALIBRATION_PATHS:
        raise ValueError(f"不支持的仪器: {instrument}. 支持的仪器: {list(CALIBRATION_PATHS.keys())}")
    
    return CALIBRATION_PATHS[instrument]

def validate_calibration_files(instrument='gy5'):
    """
    验证校准文件是否存在
    
    Args:
        instrument (str): 仪器名称
        
    Returns:
        dict: 验证结果
    """
    config = get_calibration_config(instrument)
    results = {}
    
    for frame_type in ['bias', 'dark', 'flat']:
        file_path = config.get(frame_type)
        if file_path:
            results[frame_type] = {
                'path': file_path,
                'exists': Path(file_path).exists(),
                'size': Path(file_path).stat().st_size if Path(file_path).exists() else 0
            }
        else:
            results[frame_type] = {
                'path': None,
                'exists': False,
                'size': 0
            }
    
    return results

def create_output_directory(output_dir=None):
    """
    创建输出目录
    
    Args:
        output_dir (str): 输出目录路径
        
    Returns:
        Path: 输出目录路径对象
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    return output_path

def get_log_config():
    """获取日志配置"""
    return LOG_CONFIG.copy()

def get_calibration_params():
    """获取校准参数"""
    return CALIBRATION_PARAMS.copy()

# 示例配置验证
if __name__ == "__main__":
    print("校准配置验证:")
    print("=" * 50)
    
    # 验证GY5校准文件
    results = validate_calibration_files('gy5')
    
    for frame_type, info in results.items():
        status = "✓" if info['exists'] else "✗"
        size_mb = info['size'] / (1024 * 1024) if info['size'] > 0 else 0
        print(f"{status} {frame_type.upper()}: {info['path']}")
        if info['exists']:
            print(f"    文件大小: {size_mb:.1f} MB")
        else:
            print(f"    文件不存在!")
    
    print("\n校准参数:")
    params = get_calibration_params()
    for key, value in params.items():
        print(f"  {key}: {value}")
