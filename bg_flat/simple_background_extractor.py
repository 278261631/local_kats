#!/usr/bin/env python3
"""
简化版FITS文件背景抽取工具

这是一个简化版本，只使用基本的Python库和astropy。
适用于没有安装photutils的环境。

依赖库：
- astropy: FITS文件处理
- matplotlib: 图像保存
- numpy: 数值计算

作者: AI Assistant
日期: 2025-07-17
"""

import os
import sys
import glob
import logging
from pathlib import Path
from typing import Tuple

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import matplotlib.pyplot as plt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_background_extraction.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SimpleBackgroundExtractor:
    """简化版FITS文件背景抽取器"""
    
    def __init__(self, input_dir: str, output_dir: str = None):
        """
        初始化背景抽取器
        
        Args:
            input_dir: 输入FITS文件目录
            output_dir: 输出目录，默认为输入目录下的simple_background_output
        """
        self.input_dir = Path(input_dir)
        if not self.input_dir.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        
        if output_dir is None:
            self.output_dir = self.input_dir / "simple_background_output"
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
        patterns = ['*.fits', '*.fit', '*.fts']
        fits_files = []
        
        for pattern in patterns:
            fits_files.extend(self.input_dir.glob(pattern))
            fits_files.extend(self.input_dir.glob(pattern.upper()))
        
        logger.info(f"找到 {len(fits_files)} 个FITS文件")
        return sorted(fits_files)
    
    def estimate_background_grid(self, data: np.ndarray, grid_size: int = 64) -> Tuple[float, np.ndarray]:
        """
        使用网格方法估计背景
        
        Args:
            data: 图像数据
            grid_size: 网格大小
            
        Returns:
            background_level: 平均背景水平
            background_map: 背景图
        """
        h, w = data.shape
        
        # 计算网格数量
        n_y = max(1, h // grid_size)
        n_x = max(1, w // grid_size)
        
        # 创建背景网格
        bg_grid = np.zeros((n_y, n_x))
        
        for i in range(n_y):
            for j in range(n_x):
                # 计算网格边界
                y1 = i * grid_size
                y2 = min((i + 1) * grid_size, h)
                x1 = j * grid_size
                x2 = min((j + 1) * grid_size, w)
                
                # 提取网格数据
                grid_data = data[y1:y2, x1:x2]
                
                # 使用sigma-clipped中位数估计背景
                try:
                    _, median, _ = sigma_clipped_stats(grid_data, sigma=3.0, maxiters=3)
                    bg_grid[i, j] = median
                except:
                    bg_grid[i, j] = np.median(grid_data)
        
        # 将网格插值到原始图像大小
        from scipy.ndimage import zoom
        try:
            zoom_y = h / n_y
            zoom_x = w / n_x
            background_map = zoom(bg_grid, (zoom_y, zoom_x), order=1)
        except ImportError:
            # 如果没有scipy，使用简单的重复方法
            background_map = np.repeat(np.repeat(bg_grid, grid_size, axis=0), grid_size, axis=1)
            background_map = background_map[:h, :w]
        
        background_level = np.median(background_map)
        
        logger.info(f"网格背景估计 - 网格大小: {grid_size}, 平均背景: {background_level:.2f}")
        return background_level, background_map
    
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
        mean, median, std = sigma_clipped_stats(data, sigma=3.0, maxiters=5)
        
        # 使用中位数作为背景水平
        background_level = median
        background_map = np.full_like(data, background_level)
        
        logger.info(f"简单背景估计 - 均值: {mean:.2f}, 中位数: {median:.2f}, 标准差: {std:.2f}")
        return background_level, background_map
    
    def save_background_jpg(self, background_data: np.ndarray, output_path: Path):
        """
        将背景数据保存为JPG图像
        
        Args:
            background_data: 背景数据
            output_path: 输出路径
        """
        plt.figure(figsize=(10, 10))
        
        # 使用百分位数确定显示范围
        vmin, vmax = np.percentile(background_data, [1, 99])
        
        plt.imshow(background_data, cmap='gray', origin='lower', 
                  vmin=vmin, vmax=vmax)
        plt.colorbar(label='Background Level')
        plt.title('Extracted Background')
        plt.xlabel('X (pixels)')
        plt.ylabel('Y (pixels)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"背景图像已保存: {output_path}")
    
    def process_fits_file(self, fits_path: Path, use_grid: bool = True) -> bool:
        """
        处理单个FITS文件
        
        Args:
            fits_path: FITS文件路径
            use_grid: 是否使用网格方法
            
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
            if use_grid and min(data.shape) > 128:
                background_level, background_map = self.estimate_background_grid(data)
            else:
                background_level, background_map = self.estimate_background_simple(data)
            
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
            new_hdu = fits.PrimaryHDU(data=background_subtracted.astype(np.float32), header=header)
            
            # 添加处理信息到头文件
            new_hdu.header['HISTORY'] = f'Background subtracted using simple_background_extractor.py'
            new_hdu.header['BGMETHOD'] = ('GRID' if use_grid else 'SIMPLE', 'Background estimation method')
            new_hdu.header['BGLEVEL'] = (background_level, 'Average background level')
            
            new_hdu.writeto(bg_sub_fits_path, overwrite=True)
            
            logger.info(f"处理完成: {fits_path.name}")
            logger.info(f"  - 背景图像: {bg_jpg_path}")
            logger.info(f"  - 背景减除FITS: {bg_sub_fits_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"处理文件失败 {fits_path.name}: {e}")
            return False
    
    def process_all_files(self, use_grid: bool = True):
        """处理所有FITS文件"""
        fits_files = self.find_fits_files()
        
        if not fits_files:
            logger.warning("未找到FITS文件")
            return
        
        success_count = 0
        total_count = len(fits_files)
        
        logger.info(f"开始处理 {total_count} 个文件...")
        
        for fits_file in fits_files:
            if self.process_fits_file(fits_file, use_grid):
                success_count += 1
        
        logger.info(f"处理完成: {success_count}/{total_count} 个文件成功")

def main():
    """主函数"""
    input_directory = r"E:\fix_data\star-detect"
    
    try:
        extractor = SimpleBackgroundExtractor(input_directory)
        extractor.process_all_files(use_grid=True)
        
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
