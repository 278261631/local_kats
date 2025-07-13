#!/usr/bin/env python3
"""
配置文件加载器
用于加载和管理系统配置
"""

import json
import os
import logging
from pathlib import Path


class ConfigLoader:
    """配置文件加载器"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.logger.info(f"配置文件加载成功: {self.config_file}")
            else:
                self.logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                self.config = self.get_default_config()
                self.save_config()  # 保存默认配置
                
        except Exception as e:
            self.logger.error(f"加载配置文件时出错: {str(e)}")
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """获取默认配置"""
        return {
            "monitor_settings": {
                "monitor_directory": "E:/fix_data/debug_fits_output",
                "scan_interval": 5,
                "file_timeout": 30,
                "enable_plotting": True,
                "enable_recording": True
            },
            "test_settings": {
                "source_directory": "E:/fix_data/debug_fits_input",
                "copy_delay": 2.5,
                "show_progress": True
            },
            "plotting_settings": {
                "max_points": 50,
                "figure_size": [12, 8],
                "update_interval": 1000,
                "font_family": "SimHei"
            },
            "recording_settings": {
                "csv_filename": "fits_quality_log.csv",
                "log_filename": "fits_monitor.log",
                "backup_logs": True
            },
            "quality_thresholds": {
                "fwhm": {
                    "excellent": 2.0,
                    "good": 3.0,
                    "fair": 5.0
                },
                "ellipticity": {
                    "excellent": 0.1,
                    "good": 0.2,
                    "fair": 0.3
                },
                "n_sources": {
                    "excellent": 50,
                    "good": 10
                }
            }
        }
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"配置文件保存成功: {self.config_file}")
        except Exception as e:
            self.logger.error(f"保存配置文件时出错: {str(e)}")
    
    def get(self, section, key=None, default=None):
        """获取配置值"""
        try:
            if key is None:
                return self.config.get(section, default)
            else:
                return self.config.get(section, {}).get(key, default)
        except Exception as e:
            self.logger.error(f"获取配置值时出错: {str(e)}")
            return default
    
    def set(self, section, key, value):
        """设置配置值"""
        try:
            if section not in self.config:
                self.config[section] = {}
            self.config[section][key] = value
            self.logger.info(f"配置已更新: {section}.{key} = {value}")
        except Exception as e:
            self.logger.error(f"设置配置值时出错: {str(e)}")
    
    def get_monitor_settings(self):
        """获取监控设置"""
        return self.get('monitor_settings', default={})
    
    def get_test_settings(self):
        """获取测试设置"""
        return self.get('test_settings', default={})
    
    def get_plotting_settings(self):
        """获取图表设置"""
        return self.get('plotting_settings', default={})
    
    def get_recording_settings(self):
        """获取记录设置"""
        return self.get('recording_settings', default={})
    
    def get_quality_thresholds(self):
        """获取质量阈值"""
        return self.get('quality_thresholds', default={})


# 全局配置实例
config = ConfigLoader()


def get_config():
    """获取全局配置实例"""
    return config


if __name__ == "__main__":
    # 测试配置加载器
    config_loader = ConfigLoader()
    
    print("监控设置:")
    print(json.dumps(config_loader.get_monitor_settings(), indent=2, ensure_ascii=False))
    
    print("\n测试设置:")
    print(json.dumps(config_loader.get_test_settings(), indent=2, ensure_ascii=False))
    
    print("\n图表设置:")
    print(json.dumps(config_loader.get_plotting_settings(), indent=2, ensure_ascii=False))
    
    print("\n质量阈值:")
    print(json.dumps(config_loader.get_quality_thresholds(), indent=2, ensure_ascii=False))
