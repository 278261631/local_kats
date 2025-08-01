#!/usr/bin/env python3
"""
FITS文件名解析器
用于从FITS文件名中提取望远镜名称、K序号等信息
"""

import re
import os
import logging
from typing import Optional, Dict, List
from pathlib import Path


class FITSFilenameParser:
    """FITS文件名解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 定义文件名模式
        self.patterns = [
            # 模式1: GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit
            r'(?P<tel_name>GY[1-6])_(?P<k_number>K\d{3})-?(?P<k_suffix>\d*)',
            
            # 模式2: download_GY5_20250718_K096_001.fits
            r'download_(?P<tel_name>GY[1-6])_(?P<date>\d{8})_(?P<k_number>K\d{3})_(?P<sequence>\d+)',
            
            # 模式3: template_calibration_001.fits (模板文件)
            r'template_(?P<type>\w+)_(?P<sequence>\d+)',
            
            # 模式4: GY5_20250718_K096_filename.fits (通用格式)
            r'(?P<tel_name>GY[1-6])_(?P<date>\d{8})_(?P<k_number>K\d{3})',
            
            # 模式5: 简单格式 GY5_K096_xxx.fits
            r'(?P<tel_name>GY[1-6])_(?P<k_number>K\d{3})',
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.patterns]
    
    def parse_filename(self, filename: str) -> Optional[Dict[str, str]]:
        """
        解析FITS文件名
        
        Args:
            filename (str): 文件名
            
        Returns:
            Optional[Dict[str, str]]: 解析结果字典，包含tel_name, k_number等信息
        """
        try:
            # 移除路径和扩展名
            base_name = os.path.splitext(os.path.basename(filename))[0]
            
            # 尝试每个模式
            for i, pattern in enumerate(self.compiled_patterns):
                match = pattern.search(base_name)
                if match:
                    result = match.groupdict()
                    result['pattern_index'] = i
                    result['original_filename'] = filename
                    result['base_name'] = base_name
                    
                    # 标准化结果
                    self._normalize_result(result)
                    
                    self.logger.debug(f"文件名解析成功: {filename} -> {result}")
                    return result
            
            self.logger.warning(f"无法解析文件名: {filename}")
            return None
            
        except Exception as e:
            self.logger.error(f"解析文件名时出错 {filename}: {str(e)}")
            return None
    
    def _normalize_result(self, result: Dict[str, str]):
        """标准化解析结果"""
        # 确保望远镜名称大写
        if 'tel_name' in result:
            result['tel_name'] = result['tel_name'].upper()
        
        # 确保K序号格式正确
        if 'k_number' in result:
            k_num = result['k_number'].upper()
            if not k_num.startswith('K'):
                k_num = 'K' + k_num
            result['k_number'] = k_num
        
        # 处理K序号后缀
        if 'k_suffix' in result and result['k_suffix']:
            result['k_full'] = f"{result['k_number']}-{result['k_suffix']}"
        else:
            result['k_full'] = result.get('k_number', '')
    
    def find_template_file(self, template_dir: str, tel_name: str, k_number: str) -> Optional[str]:
        """
        在模板目录中查找对应的模板文件
        
        Args:
            template_dir (str): 模板目录路径
            tel_name (str): 望远镜名称 (如 GY5)
            k_number (str): K序号 (如 K096)
            
        Returns:
            Optional[str]: 找到的模板文件路径，如果没找到返回None
        """
        if not os.path.exists(template_dir):
            self.logger.error(f"模板目录不存在: {template_dir}")
            return None
        
        try:
            # 搜索策略：按优先级查找匹配的模板文件
            search_patterns = [
                # 1. 精确匹配：望远镜名称和K序号都匹配
                f"*{tel_name}*{k_number}*.fits",
                f"*{tel_name}*{k_number}*.fit",
                f"*{tel_name}*{k_number}*.fts",
                
                # 2. 望远镜匹配：只匹配望远镜名称
                f"*{tel_name}*.fits",
                f"*{tel_name}*.fit", 
                f"*{tel_name}*.fts",
                
                # 3. K序号匹配：只匹配K序号
                f"*{k_number}*.fits",
                f"*{k_number}*.fit",
                f"*{k_number}*.fts",
                
                # 4. 通用模板：查找reference、template、calibration等
                "*reference*.fits",
                "*template*.fits",
                "*calibration*.fits",
                "*standard*.fits",
            ]
            
            for pattern in search_patterns:
                matches = list(Path(template_dir).rglob(pattern))
                if matches:
                    # 返回第一个匹配的文件
                    template_file = str(matches[0])
                    self.logger.info(f"找到模板文件: {template_file} (模式: {pattern})")
                    return template_file
            
            self.logger.warning(f"未找到匹配的模板文件: {tel_name}, {k_number}")
            return None
            
        except Exception as e:
            self.logger.error(f"查找模板文件时出错: {str(e)}")
            return None
    
    def get_file_info(self, filename: str) -> Dict[str, str]:
        """
        获取文件的详细信息
        
        Args:
            filename (str): 文件名
            
        Returns:
            Dict[str, str]: 文件信息字典
        """
        info = {
            'filename': os.path.basename(filename),
            'path': filename,
            'extension': os.path.splitext(filename)[1].lower(),
            'size': 0,
            'is_fits': False
        }
        
        # 检查是否是FITS文件
        fits_extensions = ['.fits', '.fit', '.fts']
        info['is_fits'] = info['extension'] in fits_extensions
        
        # 获取文件大小
        try:
            if os.path.exists(filename):
                info['size'] = os.path.getsize(filename)
        except:
            pass
        
        # 解析文件名
        parsed = self.parse_filename(filename)
        if parsed:
            info.update(parsed)
        
        return info
    
    def validate_file_pair(self, download_file: str, template_file: str) -> bool:
        """
        验证下载文件和模板文件是否匹配
        
        Args:
            download_file (str): 下载文件路径
            template_file (str): 模板文件路径
            
        Returns:
            bool: 是否匹配
        """
        try:
            download_info = self.parse_filename(download_file)
            template_info = self.parse_filename(template_file)
            
            if not download_info or not template_info:
                return False
            
            # 检查是否都是FITS文件
            if not (download_file.lower().endswith(('.fits', '.fit', '.fts')) and 
                   template_file.lower().endswith(('.fits', '.fit', '.fts'))):
                return False
            
            # 如果模板文件有望远镜信息，检查是否匹配
            if 'tel_name' in template_info and 'tel_name' in download_info:
                if template_info['tel_name'] != download_info['tel_name']:
                    self.logger.warning(f"望远镜名称不匹配: {download_info['tel_name']} vs {template_info['tel_name']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证文件对时出错: {str(e)}")
            return False
    
    def list_template_files(self, template_dir: str) -> List[Dict[str, str]]:
        """
        列出模板目录中的所有FITS文件及其信息
        
        Args:
            template_dir (str): 模板目录路径
            
        Returns:
            List[Dict[str, str]]: 模板文件信息列表
        """
        template_files = []
        
        if not os.path.exists(template_dir):
            return template_files
        
        try:
            # 查找所有FITS文件
            fits_extensions = ['*.fits', '*.fit', '*.fts']
            for ext in fits_extensions:
                for file_path in Path(template_dir).rglob(ext):
                    file_info = self.get_file_info(str(file_path))
                    template_files.append(file_info)
            
            # 按文件名排序
            template_files.sort(key=lambda x: x['filename'])
            
            self.logger.info(f"找到 {len(template_files)} 个模板文件")
            return template_files
            
        except Exception as e:
            self.logger.error(f"列出模板文件时出错: {str(e)}")
            return template_files


# 测试代码
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.DEBUG)
    
    parser = FITSFilenameParser()
    
    # 测试文件名
    test_filenames = [
        "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit",
        "download_GY5_20250718_K096_001.fits",
        "template_calibration_001.fits",
        "GY5_20250718_K096_test.fits",
        "GY2_K001_data.fits",
        "invalid_filename.fits"
    ]
    
    print("文件名解析测试:")
    print("=" * 60)
    
    for filename in test_filenames:
        result = parser.parse_filename(filename)
        print(f"文件名: {filename}")
        if result:
            print(f"  解析结果: {result}")
        else:
            print("  解析失败")
        print()
