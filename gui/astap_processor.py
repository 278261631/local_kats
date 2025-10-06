#!/usr/bin/env python3
"""
ASTAP处理器
用于在FITS文件下载完成后，根据文件名中的天区编号匹配坐标并执行ASTAP命令
"""

import os
import sys
import json
import logging
import subprocess
import re
from pathlib import Path
from typing import Optional, Dict, Tuple

from filename_parser import FITSFilenameParser


class ASTAPProcessor:
    """ASTAP处理器类"""
    
    def __init__(self, config_path: str = "config/url_config.json"):
        """
        初始化ASTAP处理器
        
        Args:
            config_path (str): 配置文件路径
        """
        self.config_path = config_path
        self.config_data = None
        self.filename_parser = FITSFilenameParser()
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_path):
                self.logger.error(f"配置文件不存在: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            self.logger.info(f"配置文件加载成功: {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            self.config_data = None
    
    def extract_k_full_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取完整的天区编号
        
        Args:
            filename (str): 文件名
            
        Returns:
            Optional[str]: 天区完整编号，如 "K025-1"
        """
        try:
            # 使用文件名解析器
            parsed_info = self.filename_parser.parse_filename(filename)
            if parsed_info and 'k_full' in parsed_info:
                k_full = parsed_info['k_full']
                self.logger.info(f"从文件名 {filename} 提取到天区编号: {k_full}")
                return k_full
            
            # 如果解析器失败，使用正则表达式作为备用方案
            match = re.search(r'K(\d{3})-(\d)', filename)
            if match:
                k_full = f"K{match.group(1)}-{match.group(2)}"
                self.logger.info(f"通过正则表达式从文件名 {filename} 提取到天区编号: {k_full}")
                return k_full
            
            self.logger.warning(f"无法从文件名中提取天区编号: {filename}")
            return None
            
        except Exception as e:
            self.logger.error(f"提取天区编号时出错: {str(e)}")
            return None
    
    def get_coordinates_for_region(self, k_full: str) -> Optional[Tuple[float, float]]:
        """
        根据天区编号获取坐标
        
        Args:
            k_full (str): 天区完整编号，如 "K025-1"
            
        Returns:
            Optional[Tuple[float, float]]: (RA, DEC) 坐标，如果没找到返回None
        """
        try:
            if not self.config_data or 'regionData' not in self.config_data:
                self.logger.error("配置数据无效或缺少regionData")
                return None
            
            region_data = self.config_data['regionData']
            
            if k_full in region_data:
                coordinates = region_data[k_full]
                if isinstance(coordinates, list) and len(coordinates) >= 2:
                    ra, dec = float(coordinates[0]), float(coordinates[1])
                    self.logger.info(f"找到天区 {k_full} 的坐标: RA={ra}, DEC={dec}")
                    return ra, dec
                else:
                    self.logger.error(f"天区 {k_full} 的坐标格式无效: {coordinates}")
                    return None
            else:
                self.logger.warning(f"未找到天区 {k_full} 的坐标数据")
                return None
                
        except Exception as e:
            self.logger.error(f"获取坐标时出错: {str(e)}")
            return None
    
    def generate_astap_command(self, fits_file_path: str, ra: float, dec: float) -> Optional[str]:
        """
        生成ASTAP命令
        
        Args:
            fits_file_path (str): FITS文件路径
            ra (float): 赤经
            dec (float): 赤纬
            
        Returns:
            Optional[str]: ASTAP命令字符串
        """
        try:
            if not self.config_data or 'astap_cmd_template' not in self.config_data:
                self.logger.error("配置数据无效或缺少astap_cmd_template")
                return None
            
            template = self.config_data['astap_cmd_template']
            
            # 格式化命令
            # ASTAP使用SPD (South Polar Distance) = DEC + 90
            astap_spd = dec + 90
            command = template.format(
                astap_ra=ra,
                astap_spd=astap_spd,
                fits_file_path=fits_file_path
            )
            
            self.logger.info(f"生成ASTAP命令: {command}")
            return command
            
        except Exception as e:
            self.logger.error(f"生成ASTAP命令时出错: {str(e)}")
            return None
    
    def execute_astap_command(self, command: str) -> bool:
        """
        执行ASTAP命令
        
        Args:
            command (str): 要执行的命令
            
        Returns:
            bool: 执行是否成功
        """
        try:
            self.logger.info(f"开始执行ASTAP命令: {command}")
            
            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.logger.info("ASTAP命令执行成功")
                if result.stdout:
                    self.logger.debug(f"ASTAP输出: {result.stdout}")
                return True
            else:
                self.logger.error(f"ASTAP命令执行失败，返回码: {result.returncode}")
                if result.stderr:
                    self.logger.error(f"错误信息: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("ASTAP命令执行超时")
            return False
        except Exception as e:
            self.logger.error(f"执行ASTAP命令时出错: {str(e)}")
            return False
    
    def process_fits_file(self, fits_file_path: str) -> bool:
        """
        处理单个FITS文件：提取天区编号、获取坐标、生成并执行ASTAP命令
        
        Args:
            fits_file_path (str): FITS文件路径
            
        Returns:
            bool: 处理是否成功
        """
        try:
            self.logger.info(f"开始处理FITS文件: {fits_file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(fits_file_path):
                self.logger.error(f"FITS文件不存在: {fits_file_path}")
                return False
            
            # 1. 从文件名提取天区编号
            filename = os.path.basename(fits_file_path)
            k_full = self.extract_k_full_from_filename(filename)
            if not k_full:
                self.logger.error(f"无法从文件名提取天区编号")
                self.logger.error(f"  文件名: {filename}")
                self.logger.error(f"  期望格式: 包含K###-#格式的天区编号（如K054-1）")
                return False

            self.logger.info(f"提取到天区编号: {k_full}")

            # 2. 获取坐标
            coordinates = self.get_coordinates_for_region(k_full)
            if not coordinates:
                self.logger.error(f"无法获取天区 {k_full} 的坐标")
                self.logger.error(f"  配置文件: {self.config_path}")
                self.logger.error(f"  请检查配置文件中是否包含天区 {k_full} 的坐标信息")
                return False

            ra, dec = coordinates
            self.logger.info(f"获取到坐标: RA={ra}h, DEC={dec}°")

            # 3. 生成ASTAP命令
            command = self.generate_astap_command(fits_file_path, ra, dec)
            if not command:
                self.logger.error("生成ASTAP命令失败")
                self.logger.error(f"  ASTAP路径: {self.astap_path}")
                self.logger.error(f"  请检查ASTAP是否正确安装")
                return False

            self.logger.info(f"生成的ASTAP命令: {command}")

            # 4. 执行ASTAP命令
            success = self.execute_astap_command(command)

            if success:
                self.logger.info(f"FITS文件处理完成: {fits_file_path}")
            else:
                self.logger.error(f"FITS文件处理失败: {fits_file_path}")
                self.logger.error(f"  执行的命令: {command}")
                self.logger.error(f"  请检查上面的错误信息获取失败原因")

            return success
            
        except Exception as e:
            self.logger.error(f"处理FITS文件时出错: {str(e)}")
            return False
    
    def process_directory(self, directory_path: str) -> Dict[str, bool]:
        """
        处理目录中的所有FITS文件
        
        Args:
            directory_path (str): 目录路径
            
        Returns:
            Dict[str, bool]: 文件处理结果字典 {文件路径: 是否成功}
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
                self.logger.warning(f"目录中没有找到FITS文件: {directory_path}")
                return results
            
            self.logger.info(f"找到 {len(fits_files)} 个FITS文件")
            
            # 处理每个文件
            for fits_file in fits_files:
                file_path = str(fits_file)
                success = self.process_fits_file(file_path)
                results[file_path] = success
            
            # 统计结果
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            self.logger.info(f"目录处理完成: {successful}/{total} 个文件成功处理")
            
            return results
            
        except Exception as e:
            self.logger.error(f"处理目录时出错: {str(e)}")
            return results


def main():
    """主函数，用于命令行测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ASTAP处理器')
    parser.add_argument('input', help='FITS文件路径或目录路径')
    parser.add_argument('--config', default='../config/url_config.json', help='配置文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建处理器
    processor = ASTAPProcessor(args.config)
    
    # 处理输入
    if os.path.isfile(args.input):
        # 处理单个文件
        success = processor.process_fits_file(args.input)
        sys.exit(0 if success else 1)
    elif os.path.isdir(args.input):
        # 处理目录
        results = processor.process_directory(args.input)
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        print(f"处理完成: {successful}/{total} 个文件成功")
        sys.exit(0 if successful == total else 1)
    else:
        print(f"错误: 输入路径不存在: {args.input}")
        sys.exit(1)


if __name__ == "__main__":
    main()
