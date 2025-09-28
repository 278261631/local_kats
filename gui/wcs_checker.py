#!/usr/bin/env python3
"""
WCS信息检查器
用于检查FITS文件是否包含有效的WCS（World Coordinate System）信息
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from astropy.io import fits
from astropy.wcs import WCS
import warnings

# 忽略WCS相关的警告
warnings.filterwarnings('ignore', category=UserWarning, module='astropy.wcs')


class WCSChecker:
    """WCS信息检查器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_fits_wcs(self, fits_file_path: str) -> bool:
        """
        检查单个FITS文件是否包含有效的WCS信息
        
        Args:
            fits_file_path (str): FITS文件路径
            
        Returns:
            bool: True表示包含有效WCS信息，False表示不包含
        """
        try:
            if not os.path.exists(fits_file_path):
                self.logger.warning(f"文件不存在: {fits_file_path}")
                return False
            
            # 打开FITS文件
            with fits.open(fits_file_path) as hdul:
                # 检查主HDU的header
                header = hdul[0].header
                
                # 检查基本的WCS关键字
                wcs_keywords = [
                    'CRVAL1', 'CRVAL2',  # 参考点的世界坐标
                    'CRPIX1', 'CRPIX2',  # 参考点的像素坐标
                    'CDELT1', 'CDELT2',  # 像素尺度（可选，可能用CD矩阵代替）
                    'CTYPE1', 'CTYPE2'   # 坐标类型
                ]
                
                # 检查CD矩阵（线性变换矩阵）
                cd_keywords = ['CD1_1', 'CD1_2', 'CD2_1', 'CD2_2']
                
                # 检查PC矩阵（旋转矩阵）
                pc_keywords = ['PC1_1', 'PC1_2', 'PC2_1', 'PC2_2']
                
                # 至少需要有CRVAL, CRPIX, CTYPE
                required_keywords = ['CRVAL1', 'CRVAL2', 'CRPIX1', 'CRPIX2', 'CTYPE1', 'CTYPE2']
                
                # 检查必需的关键字
                missing_required = []
                for keyword in required_keywords:
                    if keyword not in header:
                        missing_required.append(keyword)
                
                if missing_required:
                    self.logger.debug(f"文件 {os.path.basename(fits_file_path)} 缺少必需的WCS关键字: {missing_required}")
                    return False
                
                # 检查是否有尺度信息（CDELT或CD矩阵或PC矩阵）
                has_cdelt = 'CDELT1' in header and 'CDELT2' in header
                has_cd_matrix = all(kw in header for kw in cd_keywords)
                has_pc_matrix = all(kw in header for kw in pc_keywords)
                
                if not (has_cdelt or has_cd_matrix or has_pc_matrix):
                    self.logger.debug(f"文件 {os.path.basename(fits_file_path)} 缺少尺度信息（CDELT/CD/PC）")
                    return False
                
                # 尝试创建WCS对象来验证
                try:
                    wcs = WCS(header)
                    
                    # 检查WCS是否有效（能够进行坐标转换）
                    if wcs.has_celestial:
                        # 测试一个简单的坐标转换
                        test_pixel = [100, 100]  # 测试像素坐标
                        world_coords = wcs.pixel_to_world_values(test_pixel[0], test_pixel[1])
                        
                        if world_coords is not None and len(world_coords) >= 2:
                            self.logger.debug(f"文件 {os.path.basename(fits_file_path)} 包含有效的WCS信息")
                            return True
                        else:
                            self.logger.debug(f"文件 {os.path.basename(fits_file_path)} WCS坐标转换失败")
                            return False
                    else:
                        self.logger.debug(f"文件 {os.path.basename(fits_file_path)} WCS不包含天球坐标系统")
                        return False
                        
                except Exception as wcs_error:
                    self.logger.debug(f"文件 {os.path.basename(fits_file_path)} WCS创建失败: {str(wcs_error)}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"检查文件 {fits_file_path} 的WCS信息时出错: {str(e)}")
            return False
    
    def check_directory_wcs(self, directory_path: str) -> Dict[str, bool]:
        """
        检查目录中所有FITS文件的WCS信息
        
        Args:
            directory_path (str): 目录路径
            
        Returns:
            Dict[str, bool]: 文件路径到WCS状态的映射 {文件路径: 是否有WCS}
        """
        results = {}
        
        try:
            if not os.path.exists(directory_path):
                self.logger.error(f"目录不存在: {directory_path}")
                return results
            
            # 查找所有FITS文件
            fits_extensions = ['.fits', '.fit', '.fts']
            fits_files = []
            
            for ext in fits_extensions:
                pattern = f"*{ext}"
                fits_files.extend(Path(directory_path).glob(pattern))
                fits_files.extend(Path(directory_path).glob(pattern.upper()))
            
            if not fits_files:
                self.logger.info(f"目录中没有找到FITS文件: {directory_path}")
                return results
            
            self.logger.info(f"开始检查目录 {directory_path} 中的 {len(fits_files)} 个FITS文件")
            
            # 检查每个文件
            for fits_file in fits_files:
                file_path = str(fits_file)
                has_wcs = self.check_fits_wcs(file_path)
                results[file_path] = has_wcs
            
            # 统计结果
            with_wcs = sum(1 for has_wcs in results.values() if has_wcs)
            total = len(results)
            self.logger.info(f"WCS检查完成: {with_wcs}/{total} 个文件包含WCS信息")
            
            return results
            
        except Exception as e:
            self.logger.error(f"检查目录 {directory_path} 时出错: {str(e)}")
            return results
    
    def get_wcs_summary(self, directory_path: str) -> Tuple[int, int, List[str], List[str]]:
        """
        获取目录WCS检查摘要
        
        Args:
            directory_path (str): 目录路径
            
        Returns:
            Tuple[int, int, List[str], List[str]]: (有WCS的文件数, 总文件数, 有WCS的文件列表, 无WCS的文件列表)
        """
        results = self.check_directory_wcs(directory_path)
        
        with_wcs_files = []
        without_wcs_files = []
        
        for file_path, has_wcs in results.items():
            filename = os.path.basename(file_path)
            if has_wcs:
                with_wcs_files.append(filename)
            else:
                without_wcs_files.append(filename)
        
        return len(with_wcs_files), len(results), with_wcs_files, without_wcs_files
    
    def get_wcs_info_details(self, fits_file_path: str) -> Optional[Dict]:
        """
        获取FITS文件的详细WCS信息
        
        Args:
            fits_file_path (str): FITS文件路径
            
        Returns:
            Optional[Dict]: WCS详细信息字典，如果没有WCS则返回None
        """
        try:
            if not os.path.exists(fits_file_path):
                return None
            
            with fits.open(fits_file_path) as hdul:
                header = hdul[0].header
                
                if not self.check_fits_wcs(fits_file_path):
                    return None
                
                wcs_info = {}
                
                # 基本WCS信息
                wcs_info['CRVAL1'] = header.get('CRVAL1', 'N/A')
                wcs_info['CRVAL2'] = header.get('CRVAL2', 'N/A')
                wcs_info['CRPIX1'] = header.get('CRPIX1', 'N/A')
                wcs_info['CRPIX2'] = header.get('CRPIX2', 'N/A')
                wcs_info['CTYPE1'] = header.get('CTYPE1', 'N/A')
                wcs_info['CTYPE2'] = header.get('CTYPE2', 'N/A')
                
                # 尺度信息
                if 'CDELT1' in header:
                    wcs_info['CDELT1'] = header['CDELT1']
                    wcs_info['CDELT2'] = header['CDELT2']
                
                # CD矩阵
                cd_matrix = {}
                for kw in ['CD1_1', 'CD1_2', 'CD2_1', 'CD2_2']:
                    if kw in header:
                        cd_matrix[kw] = header[kw]
                if cd_matrix:
                    wcs_info['CD_MATRIX'] = cd_matrix
                
                # PC矩阵
                pc_matrix = {}
                for kw in ['PC1_1', 'PC1_2', 'PC2_1', 'PC2_2']:
                    if kw in header:
                        pc_matrix[kw] = header[kw]
                if pc_matrix:
                    wcs_info['PC_MATRIX'] = pc_matrix
                
                # 其他相关信息
                wcs_info['EQUINOX'] = header.get('EQUINOX', 'N/A')
                wcs_info['RADESYS'] = header.get('RADESYS', 'N/A')
                
                return wcs_info
                
        except Exception as e:
            self.logger.error(f"获取文件 {fits_file_path} 的WCS详细信息时出错: {str(e)}")
            return None


def main():
    """主函数，用于命令行测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WCS信息检查器')
    parser.add_argument('input', help='FITS文件路径或目录路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--details', '-d', action='store_true', help='显示详细WCS信息')
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建检查器
    checker = WCSChecker()
    
    # 处理输入
    if os.path.isfile(args.input):
        # 检查单个文件
        has_wcs = checker.check_fits_wcs(args.input)
        print(f"文件: {args.input}")
        print(f"WCS状态: {'✓ 包含WCS信息' if has_wcs else '✗ 不包含WCS信息'}")
        
        if has_wcs and args.details:
            wcs_info = checker.get_wcs_info_details(args.input)
            if wcs_info:
                print("\nWCS详细信息:")
                for key, value in wcs_info.items():
                    print(f"  {key}: {value}")
        
    elif os.path.isdir(args.input):
        # 检查目录
        with_wcs, total, with_wcs_files, without_wcs_files = checker.get_wcs_summary(args.input)
        
        print(f"目录: {args.input}")
        print(f"总计: {total} 个FITS文件")
        print(f"包含WCS: {with_wcs} 个文件")
        print(f"不含WCS: {total - with_wcs} 个文件")
        
        if with_wcs_files:
            print(f"\n包含WCS的文件 ({len(with_wcs_files)}):")
            for filename in sorted(with_wcs_files):
                print(f"  ✓ {filename}")
        
        if without_wcs_files:
            print(f"\n不含WCS的文件 ({len(without_wcs_files)}):")
            for filename in sorted(without_wcs_files):
                print(f"  ✗ {filename}")
    else:
        print(f"错误: 输入路径不存在: {args.input}")


if __name__ == "__main__":
    main()
