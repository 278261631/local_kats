#!/usr/bin/env python3
"""
FITS文件背景抽取工具

该脚本用于处理E:\fix_data\star-detect目录下的所有FITS文件：
1. 提取每个FITS文件的背景
2. 将背景保存为JPG图像
3. 生成减去背景后的FITS文件

依赖库：
- astropy: FITS文件处理
- photutils: 背景估计
- matplotlib: 图像保存
- numpy: 数值计算
- PIL: 图像处理

作者: AI Assistant
日期: 2025-07-17
"""

import os
import sys
import glob
import logging
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from PIL import Image

# 导入配置
try:
    from config import *
except ImportError:
    # 如果没有配置文件，使用默认值
    INPUT_DIRECTORY = r"E:\fix_data\star-detect"
    OUTPUT_DIRECTORY = None
    BACKGROUND_BOX_SIZE = 50
    SIGMA_CLIP_SIGMA = 3.0
    SIGMA_CLIP_MAXITERS = 5
    JPG_DPI = 150
    JPG_FIGURE_SIZE = (10, 10)
    DISPLAY_PERCENTILES = [1, 99]
    OUTPUT_DTYPE = 'float32'
    FITS_EXTENSIONS = ['.fits', '.fit', '.fts']
    INCLUDE_UPPERCASE_EXTENSIONS = True
    LOG_LEVEL = 'INFO'
    LOG_FILENAME = 'background_extraction.log'
    CONSOLE_OUTPUT = True
    BACKGROUND_FILTER_SIZE = 3
    ADD_HISTORY_TO_HEADER = True
    OVERWRITE_EXISTING = True

try:
    from photutils.background import Background2D, MedianBackground
    from photutils.background import SExtractorBackground
    PHOTUTILS_AVAILABLE = True
except ImportError:
    PHOTUTILS_AVAILABLE = False
    print("警告: photutils未安装，将使用简单的统计方法估计背景")

# 配置日志
handlers = []
if LOG_FILENAME:
    handlers.append(logging.FileHandler(LOG_FILENAME))
if CONSOLE_OUTPUT:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

class BackgroundExtractor:
    """FITS文件背景抽取器"""
    
    def __init__(self, input_dir: str, output_dir: str = None):
        """
        初始化背景抽取器
        
        Args:
            input_dir: 输入FITS文件目录
            output_dir: 输出目录，默认为输入目录下的background_output
        """
        self.input_dir = Path(input_dir)
        if not self.input_dir.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        
        if output_dir is None:
            self.output_dir = self.input_dir / "background_output"
        else:
            self.output_dir = Path(output_dir)
        
        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "backgrounds").mkdir(exist_ok=True)
        (self.output_dir / "background_subtracted").mkdir(exist_ok=True)
        
        logger.info(f"输入目录: {self.input_dir}")
        logger.info(f"输出目录: {self.output_dir}")
    
    def find_fits_files(self) -> list:
        """查找所有FITS文件"""
        patterns = [f'*{ext}' for ext in FITS_EXTENSIONS]
        fits_files = []

        for pattern in patterns:
            fits_files.extend(self.input_dir.glob(pattern))
            if INCLUDE_UPPERCASE_EXTENSIONS:
                fits_files.extend(self.input_dir.glob(pattern.upper()))

        logger.info(f"找到 {len(fits_files)} 个FITS文件")
        return sorted(fits_files)
    
    def estimate_background_simple(self, data: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        使用简单统计方法估计背景
        
        Args:
            data: 图像数据
            
        Returns:
            background_level: 背景水平值
            background_map: 背景图（常数值）
        """
        # 使用sigma-clipped统计来估计背景
        mean, median, std = sigma_clipped_stats(data, sigma=SIGMA_CLIP_SIGMA, maxiters=SIGMA_CLIP_MAXITERS)
        
        # 使用中位数作为背景水平
        background_level = median
        background_map = np.full_like(data, background_level)
        
        logger.info(f"简单背景估计 - 均值: {mean:.2f}, 中位数: {median:.2f}, 标准差: {std:.2f}")
        return background_level, background_map
    
    def estimate_background_2d(self, data: np.ndarray, box_size: int = 50) -> Tuple[float, np.ndarray]:
        """
        使用2D背景估计方法
        
        Args:
            data: 图像数据
            box_size: 背景估计的网格大小
            
        Returns:
            background_level: 平均背景水平
            background_map: 2D背景图
        """
        if not PHOTUTILS_AVAILABLE:
            return self.estimate_background_simple(data)
        
        try:
            # 使用SExtractor风格的背景估计
            bkg_estimator = SExtractorBackground()
            bkg = Background2D(data, box_size, filter_size=BACKGROUND_FILTER_SIZE, bkg_estimator=bkg_estimator)
            
            background_level = np.median(bkg.background)
            background_map = bkg.background
            
            logger.info(f"2D背景估计 - 平均背景: {background_level:.2f}")
            return background_level, background_map
            
        except Exception as e:
            logger.warning(f"2D背景估计失败，使用简单方法: {e}")
            return self.estimate_background_simple(data)
    
    def save_background_jpg(self, background_data: np.ndarray, output_path: Path):
        """
        将背景数据保存为JPG图像
        
        Args:
            background_data: 背景数据
            output_path: 输出路径
        """
        plt.figure(figsize=JPG_FIGURE_SIZE)

        # 使用百分位数确定显示范围
        vmin, vmax = np.percentile(background_data, DISPLAY_PERCENTILES)
        
        plt.imshow(background_data, cmap='gray', origin='lower', 
                  vmin=vmin, vmax=vmax)
        plt.colorbar(label='Background Level')
        plt.title('Extracted Background')
        plt.xlabel('X (pixels)')
        plt.ylabel('Y (pixels)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=JPG_DPI, bbox_inches='tight')
        plt.close()
        
        logger.info(f"背景图像已保存: {output_path}")
    
    def process_fits_file(self, fits_path: Path) -> bool:
        """
        处理单个FITS文件
        
        Args:
            fits_path: FITS文件路径
            
        Returns:
            是否处理成功
        """
        try:
            logger.info(f"处理文件: {fits_path.name}")
            
            # 读取FITS文件
            with fits.open(fits_path) as hdul:
                # 通常科学数据在第一个或第二个HDU中
                data = None
                header = None
                
                for i, hdu in enumerate(hdul):
                    if hdu.data is not None and len(hdu.data.shape) == 2:
                        data = hdu.data.astype(np.float64)
                        header = hdu.header
                        logger.info(f"使用HDU {i}, 数据形状: {data.shape}")
                        break
                
                if data is None:
                    logger.error(f"未找到有效的2D图像数据: {fits_path.name}")
                    return False
            
            # 估计背景
            background_level, background_map = self.estimate_background_2d(data, BACKGROUND_BOX_SIZE)
            
            # 生成输出文件名
            base_name = fits_path.stem
            
            # 保存背景图像为JPG
            bg_jpg_path = self.output_dir / "backgrounds" / f"{base_name}_background.jpg"
            self.save_background_jpg(background_map, bg_jpg_path)
            
            # 生成背景减除后的数据
            background_subtracted = data - background_map
            
            # 保存背景减除后的FITS文件
            bg_sub_fits_path = self.output_dir / "background_subtracted" / f"{base_name}_bg_subtracted.fits"
            
            # 创建新的FITS文件
            output_dtype = getattr(np, OUTPUT_DTYPE)
            new_hdu = fits.PrimaryHDU(data=background_subtracted.astype(output_dtype), header=header)

            # 添加处理信息到头文件
            if ADD_HISTORY_TO_HEADER:
                new_hdu.header['HISTORY'] = f'Background subtracted using extract_background.py'
                new_hdu.header['BGMETHOD'] = ('2D' if PHOTUTILS_AVAILABLE else 'SIMPLE', 'Background estimation method')
                new_hdu.header['BGLEVEL'] = (background_level, 'Average background level')

            new_hdu.writeto(bg_sub_fits_path, overwrite=OVERWRITE_EXISTING)
            
            logger.info(f"处理完成: {fits_path.name}")
            logger.info(f"  - 背景图像: {bg_jpg_path}")
            logger.info(f"  - 背景减除FITS: {bg_sub_fits_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"处理文件失败 {fits_path.name}: {e}")
            return False
    
    def process_all_files(self):
        """处理所有FITS文件"""
        fits_files = self.find_fits_files()
        
        if not fits_files:
            logger.warning("未找到FITS文件")
            return
        
        success_count = 0
        total_count = len(fits_files)
        
        logger.info(f"开始处理 {total_count} 个文件...")
        
        for fits_file in fits_files:
            if self.process_fits_file(fits_file):
                success_count += 1
        
        logger.info(f"处理完成: {success_count}/{total_count} 个文件成功")

def main():
    """主函数"""
    try:
        extractor = BackgroundExtractor(INPUT_DIRECTORY, OUTPUT_DIRECTORY)
        extractor.process_all_files()

    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
