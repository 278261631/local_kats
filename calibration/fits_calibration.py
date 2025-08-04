#!/usr/bin/env python3
"""
FITS图像校准工具
实现标准的天文图像校准流程：bias减除、dark减除、flat field校正

Author: Augment Agent
Date: 2025-08-04
"""

import os
import sys
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import warnings

# 忽略FITS文件的警告
warnings.filterwarnings('ignore', category=fits.verify.VerifyWarning)

class FITSCalibrator:
    """FITS图像校准器"""
    
    def __init__(self, calibration_dir=None, output_dir=None, log_level=logging.INFO,
                 skip_bias=False, skip_dark=False, skip_flat=False):
        """
        初始化校准器

        Args:
            calibration_dir (str): 校准文件目录路径
            output_dir (str): 输出目录路径
            log_level: 日志级别
            skip_bias (bool): 是否跳过bias减除
            skip_dark (bool): 是否跳过dark减除
            skip_flat (bool): 是否跳过平场校正
        """
        self.calibration_dir = Path(calibration_dir) if calibration_dir else None
        self.output_dir = Path(output_dir) if output_dir else Path("calibrated_output")

        # 设置日志
        self.setup_logging(log_level)

        # 校准帧
        self.master_bias = None
        self.master_dark = None
        self.master_flat = None

        # 校准参数
        self.dark_exposure_time = 30.0  # 暗电流帧曝光时间(秒)
        self.skip_bias = skip_bias  # 是否跳过bias减除
        self.skip_dark = skip_dark  # 是否跳过dark减除
        self.skip_flat = skip_flat  # 是否跳过平场校正
        
    def setup_logging(self, log_level):
        """设置日志系统"""
        self.logger = logging.getLogger('FITSCalibrator')
        self.logger.setLevel(log_level)
        
        if not self.logger.handlers:
            # 创建控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            
            # 创建格式器
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
    
    def load_calibration_frames(self, bias_path=None, dark_path=None, flat_path=None):
        """
        加载校准帧
        
        Args:
            bias_path (str): bias帧路径
            dark_path (str): dark帧路径  
            flat_path (str): flat帧路径
        """
        try:
            # 加载bias帧
            if bias_path and Path(bias_path).exists():
                self.logger.info(f"加载bias帧: {bias_path}")
                with fits.open(bias_path) as hdul:
                    self.master_bias = self._get_image_data(hdul)
                self.logger.info(f"Bias帧形状: {self.master_bias.shape}")
            
            # 加载dark帧
            if dark_path and Path(dark_path).exists():
                self.logger.info(f"加载dark帧: {dark_path}")
                with fits.open(dark_path) as hdul:
                    self.master_dark = self._get_image_data(hdul)
                self.logger.info(f"Dark帧形状: {self.master_dark.shape}")
            
            # 加载flat帧
            if flat_path and Path(flat_path).exists():
                self.logger.info(f"加载flat帧: {flat_path}")
                with fits.open(flat_path) as hdul:
                    self.master_flat = self._get_image_data(hdul)
                    # 归一化flat帧
                    flat_median = np.median(self.master_flat)
                    self.master_flat = self.master_flat / flat_median
                self.logger.info(f"Flat帧形状: {self.master_flat.shape}")
                
        except Exception as e:
            self.logger.error(f"加载校准帧失败: {str(e)}")
            raise
    
    def _get_image_data(self, hdul):
        """从FITS HDU列表中提取图像数据"""
        for i, hdu in enumerate(hdul):
            if hdu.data is not None and len(hdu.data.shape) == 2:
                self.logger.debug(f"使用HDU {i}, 数据形状: {hdu.data.shape}")
                return hdu.data.astype(np.float64)
        
        raise ValueError("未找到有效的2D图像数据")
    
    def _get_exposure_time(self, header):
        """从FITS头部获取曝光时间"""
        exposure_keywords = ['EXPTIME', 'EXPOSURE', 'ITIME', 'TELAPSE']
        
        for keyword in exposure_keywords:
            if keyword in header:
                return float(header[keyword])
        
        self.logger.warning("未找到曝光时间信息，使用默认值60秒")
        return 60.0
    
    def calibrate_image(self, science_path, output_path=None):
        """
        校准单个科学图像
        
        Args:
            science_path (str): 科学图像路径
            output_path (str): 输出路径，如果为None则自动生成
            
        Returns:
            str: 校准后图像的保存路径
        """
        try:
            science_path = Path(science_path)
            self.logger.info(f"开始校准图像: {science_path.name}")
            
            # 读取科学图像
            with fits.open(science_path) as hdul:
                science_data = self._get_image_data(hdul)
                header = hdul[0].header.copy()
            
            self.logger.info(f"科学图像形状: {science_data.shape}")
            
            # 获取曝光时间
            exposure_time = self._get_exposure_time(header)
            self.logger.info(f"曝光时间: {exposure_time}秒")
            
            # 执行校准
            calibrated_data = self._perform_calibration(science_data, exposure_time)
            
            # 生成输出路径
            if output_path is None:
                output_path = self._generate_output_path(science_path)
            
            # 保存校准后的图像
            self._save_calibrated_image(calibrated_data, header, output_path)
            
            self.logger.info(f"校准完成，保存至: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"图像校准失败: {str(e)}")
            raise
    
    def _perform_calibration(self, science_data, exposure_time):
        """执行实际的校准过程"""
        calibrated = science_data.copy()

        # 1. Bias减除
        if self.skip_bias:
            self.logger.info("跳过bias减除 (用户设置)")
        elif self.master_bias is not None:
            self.logger.info("执行bias减除")
            calibrated = calibrated - self.master_bias
        else:
            self.logger.warning("未加载bias帧，跳过bias减除")

        # 2. Dark减除（需要按曝光时间缩放）
        if self.skip_dark:
            self.logger.info("跳过dark减除 (用户设置)")
        elif self.master_dark is not None:
            self.logger.info("执行dark减除")
            # 计算dark缩放因子
            dark_scale = exposure_time / self.dark_exposure_time
            scaled_dark = self.master_dark * dark_scale
            calibrated = calibrated - scaled_dark
            self.logger.info(f"Dark缩放因子: {dark_scale:.3f}")
        else:
            self.logger.warning("未加载dark帧，跳过dark减除")

        # 3. Flat field校正
        if self.skip_flat:
            self.logger.info("跳过flat field校正 (用户设置)")
        elif self.master_flat is not None:
            self.logger.info("执行flat field校正")
            # 避免除零
            flat_safe = np.where(self.master_flat > 0.1, self.master_flat, 1.0)
            calibrated = calibrated / flat_safe
        else:
            self.logger.warning("未加载flat帧，跳过flat field校正")
        
        # 计算校准统计信息
        mean, median, std = sigma_clipped_stats(calibrated, sigma=3.0)
        self.logger.info(f"校准后统计: mean={mean:.2f}, median={median:.2f}, std={std:.2f}")
        
        return calibrated
    
    def _generate_output_path(self, science_path):
        """生成输出文件路径"""
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成输出文件名
        base_name = science_path.stem
        output_name = f"{base_name}_calibrated.fits"
        
        return self.output_dir / output_name
    
    def _save_calibrated_image(self, calibrated_data, header, output_path):
        """保存校准后的图像"""
        # 更新头部信息
        header['HISTORY'] = f'Calibrated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        header['HISTORY'] = 'Applied bias subtraction, dark subtraction, and flat field correction'
        
        if self.master_bias is not None and not self.skip_bias:
            header['HISTORY'] = 'Bias subtraction applied'
        elif self.skip_bias:
            header['HISTORY'] = 'Bias subtraction skipped by user setting'

        if self.master_dark is not None and not self.skip_dark:
            header['HISTORY'] = f'Dark subtraction applied (scaled by exposure time)'
        elif self.skip_dark:
            header['HISTORY'] = 'Dark subtraction skipped by user setting'

        if self.master_flat is not None and not self.skip_flat:
            header['HISTORY'] = 'Flat field correction applied'
        elif self.skip_flat:
            header['HISTORY'] = 'Flat field correction skipped by user setting'
        
        # 创建新的FITS文件
        hdu = fits.PrimaryHDU(data=calibrated_data.astype(np.float32), header=header)
        hdu.writeto(output_path, overwrite=True)
        
        self.logger.info(f"校准图像已保存: {output_path}")


def main():
    """主函数示例"""
    # 示例用法
    calibrator = FITSCalibrator()
    
    # 校准文件路径
    bias_path = r"E:\fix_data\calibration\gy5\master_bias_bin2.fits"
    dark_path = r"E:\fix_data\calibration\gy5\master_dark_bin2_30s.fits"
    flat_path = r"E:\fix_data\calibration\gy5\master_flat_C_bin2.fits"
    
    # 加载校准帧
    calibrator.load_calibration_frames(bias_path, dark_path, flat_path)
    
    # 科学图像路径
    science_path = r"E:\fix_data\test\GY5\20250628\K053\GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit"
    
    # 执行校准
    output_path = calibrator.calibrate_image(science_path)
    print(f"校准完成: {output_path}")


if __name__ == "__main__":
    main()
