#!/usr/bin/env python3
"""
配置文件管理器
用于保存和加载GUI应用程序的配置信息
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
import logging


class ConfigManager:
    """配置文件管理器"""
    
    def __init__(self, config_file="gui_config.json"):
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        
        # 默认配置
        self.default_config = {
            "telescope_names": ["GY1", "GY2", "GY3", "GY4", "GY5", "GY6"],
            "k_numbers": [f"K{i:03d}" for i in range(1, 100)],  # K001 - K099
            "last_selected": {
                "telescope_name": "GY5",
                "date": datetime.now().strftime("%Y%m%d"),
                "k_number": "K096",
                "download_directory": "",
                "template_directory": "",
                "diff_output_directory": ""
            },
            "download_settings": {
                "max_workers": 1,
                "max_workers_limit": 3,
                "retry_times": 3,
                "timeout": 30
            },
            "display_settings": {
                "default_display_mode": "linear",
                "default_colormap": "gray",
                "auto_select_from_download_dir": True
            },
            "url_template": "https://download.china-vo.org/psp/KATS/{tel_name}-DATA/{date}/{k_number}/"
        }
        
        # 加载配置
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 合并默认配置和加载的配置
                config = self.default_config.copy()
                self._deep_update(config, loaded_config)
                
                self.logger.info(f"配置文件加载成功: {self.config_file}")
                return config
            else:
                self.logger.info("配置文件不存在，使用默认配置")
                return self.default_config.copy()
                
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            return self.default_config.copy()
    
    def save_config(self) -> bool:
        """
        保存配置文件
        
        Returns:
            bool: 是否保存成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置文件保存成功: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """深度更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def get_telescope_names(self) -> List[str]:
        """获取望远镜名称列表"""
        return self.config["telescope_names"]
    
    def get_k_numbers(self) -> List[str]:
        """获取K序号列表"""
        return self.config["k_numbers"]
    
    def get_last_selected(self) -> Dict[str, str]:
        """获取上次选择的值"""
        return self.config["last_selected"]
    
    def update_last_selected(self, **kwargs):
        """更新上次选择的值"""
        for key, value in kwargs.items():
            if key in self.config["last_selected"]:
                self.config["last_selected"][key] = value
        self.save_config()
    
    def get_download_settings(self) -> Dict[str, int]:
        """获取下载设置"""
        return self.config["download_settings"]
    
    def update_download_settings(self, **kwargs):
        """更新下载设置"""
        for key, value in kwargs.items():
            if key in self.config["download_settings"]:
                self.config["download_settings"][key] = value
        self.save_config()
    
    def get_display_settings(self) -> Dict[str, Any]:
        """获取显示设置"""
        return self.config["display_settings"]
    
    def update_display_settings(self, **kwargs):
        """更新显示设置"""
        for key, value in kwargs.items():
            if key in self.config["display_settings"]:
                self.config["display_settings"][key] = value
        self.save_config()
    
    def get_url_template(self) -> str:
        """获取URL模板"""
        return self.config["url_template"]
    
    def build_url(self, tel_name: str = None, date: str = None, k_number: str = None) -> str:
        """
        构建URL
        
        Args:
            tel_name (str): 望远镜名称，如果为None则使用上次选择的值
            date (str): 日期，如果为None则使用上次选择的值
            k_number (str): K序号，如果为None则使用上次选择的值
            
        Returns:
            str: 构建的URL
        """
        last_selected = self.get_last_selected()
        
        tel_name = tel_name or last_selected["telescope_name"]
        date = date or last_selected["date"]
        k_number = k_number or last_selected["k_number"]
        
        url_template = self.get_url_template()
        return url_template.format(
            tel_name=tel_name,
            date=date,
            k_number=k_number
        )
    
    def validate_date(self, date_str: str) -> bool:
        """
        验证日期格式
        
        Args:
            date_str (str): 日期字符串 (YYYYMMDD)
            
        Returns:
            bool: 是否有效
        """
        try:
            datetime.strptime(date_str, '%Y%m%d')
            return True
        except ValueError:
            return False
    
    def validate_k_number(self, k_number: str) -> bool:
        """
        验证K序号格式
        
        Args:
            k_number (str): K序号字符串
            
        Returns:
            bool: 是否有效
        """
        return k_number in self.get_k_numbers()
    
    def validate_telescope_name(self, tel_name: str) -> bool:
        """
        验证望远镜名称
        
        Args:
            tel_name (str): 望远镜名称
            
        Returns:
            bool: 是否有效
        """
        return tel_name in self.get_telescope_names()
    
    def get_recent_dates(self, days: int = 7) -> List[str]:
        """
        获取最近几天的日期列表
        
        Args:
            days (int): 天数
            
        Returns:
            List[str]: 日期列表 (YYYYMMDD格式)
        """
        from datetime import timedelta
        
        dates = []
        base_date = datetime.now()
        
        for i in range(days):
            date = base_date - timedelta(days=i)
            dates.append(date.strftime('%Y%m%d'))
        
        return dates
    
    def export_config(self, export_file: str) -> bool:
        """
        导出配置到指定文件
        
        Args:
            export_file (str): 导出文件路径
            
        Returns:
            bool: 是否导出成功
        """
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置导出成功: {export_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出配置失败: {str(e)}")
            return False
    
    def import_config(self, import_file: str) -> bool:
        """
        从指定文件导入配置
        
        Args:
            import_file (str): 导入文件路径
            
        Returns:
            bool: 是否导入成功
        """
        try:
            if not os.path.exists(import_file):
                raise FileNotFoundError(f"配置文件不存在: {import_file}")
            
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # 验证配置格式
            if not isinstance(imported_config, dict):
                raise ValueError("配置文件格式无效")
            
            # 合并配置
            self._deep_update(self.config, imported_config)
            self.save_config()
            
            self.logger.info(f"配置导入成功: {import_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"导入配置失败: {str(e)}")
            return False
