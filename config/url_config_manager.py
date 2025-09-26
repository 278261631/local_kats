#!/usr/bin/env python3
"""
URL配置管理器
"""

import json
import os
from typing import Dict, Any
from datetime import datetime


class URLConfigManager:
    """URL配置管理器"""

    def __init__(self, config_file: str = None):
        if config_file is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(current_dir, "url_config.json")

        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                raise FileNotFoundError(f"URL配置文件不存在: {self.config_file}")
        except Exception as e:
            raise RuntimeError(f"加载URL配置文件失败: {e}")
    
    def get_base_url(self, url_type: str = None) -> str:
        """获取基础URL"""
        if url_type is None:
            url_type = "primary"  # 默认使用primary
        return self.config["base_urls"][url_type]
    
    def get_url_template(self, template_type: str = None) -> str:
        """获取URL模板"""
        if template_type is None:
            template_type = "standard"  # 默认使用standard模板
        return self.config["url_templates"][template_type]
    
    def build_url(self, tel_name: str, date: str, k_number: str = None,
                  template_type: str = None, url_type: str = None, recent_data: bool = False) -> str:
        """构建完整的URL"""
        base_url = self.get_base_url(url_type)

        if recent_data:
            template = self.get_url_template("recent_data")
        else:
            template = self.get_url_template(template_type)

        format_params = {
            'base_url': base_url,
            'tel_name': tel_name,
            'date': date
        }

        if k_number:
            format_params['k_number'] = k_number

        if '{year_of_date}' in template:
            try:
                year_of_date = date[:4] if len(date) >= 4 else datetime.now().strftime('%Y')
                format_params['year_of_date'] = year_of_date
            except Exception:
                format_params['year_of_date'] = datetime.now().strftime('%Y')

        return template.format(**format_params)
    
    def get_setting(self, key: str) -> Any:
        """获取设置值"""
        # 提供默认设置值
        default_settings = {
            "timeout": 30,
            "retry_times": 3,
            "user_agent": "MyCustomUserAgent"
        }
        return default_settings.get(key, None)
    
    def get_path_setting(self, key: str) -> str:
        """获取路径设置"""
        return self.config["path_settings"][key]
    
    def get_available_base_urls(self) -> Dict[str, str]:
        """获取所有可用的基础URL"""
        return self.config["base_urls"]

    def get_available_templates(self) -> Dict[str, str]:
        """获取所有可用的URL模板"""
        return self.config["url_templates"]


# 创建全局实例
url_config_manager = URLConfigManager()
