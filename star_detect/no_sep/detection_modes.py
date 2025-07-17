"""
星点检测模式配置文件
提供不同的检测参数组合，适应不同的使用需求
"""

from star_detector import StarDetector

def get_detector_config(mode="balanced"):
    """
    获取不同模式的检测器配置
    
    Parameters:
    -----------
    mode : str
        检测模式：
        - "minimal": 最少模式，只检测最明显的星点
        - "selective": 精选模式，检测较明显的星点
        - "balanced": 平衡模式，适中数量的星点
        - "sensitive": 敏感模式，检测较多星点
        - "maximum": 最大模式，检测所有可能的星点
        
    Returns:
    --------
    dict
        检测器参数配置
    """
    
    configs = {
        "minimal": {
            "min_area": 25,
            "max_area": 400,
            "threshold_factor": 4.0,
            "min_circularity": 0.6,
            "min_solidity": 0.8,
            "adaptive_threshold": False,
            "dark_star_mode": False,
            "description": "只检测最明显、最圆的亮星（通常<10个）"
        },
        
        "selective": {
            "min_area": 15,
            "max_area": 500,
            "threshold_factor": 3.5,
            "min_circularity": 0.5,
            "min_solidity": 0.7,
            "adaptive_threshold": False,
            "dark_star_mode": False,
            "description": "检测较明显的星点（通常10-50个）"
        },
        
        "balanced": {
            "min_area": 8,
            "max_area": 600,
            "threshold_factor": 3.0,
            "min_circularity": 0.4,
            "min_solidity": 0.6,
            "adaptive_threshold": False,
            "dark_star_mode": False,
            "description": "平衡的星点检测（通常50-200个）"
        },
        
        "sensitive": {
            "min_area": 5,
            "max_area": 800,
            "threshold_factor": 2.5,
            "min_circularity": 0.35,
            "min_solidity": 0.55,
            "adaptive_threshold": True,
            "dark_star_mode": False,
            "description": "敏感检测，包含较暗星点（通常200-1000个）"
        },
        
        "maximum": {
            "min_area": 3,
            "max_area": 1000,
            "threshold_factor": 2.0,
            "min_circularity": 0.3,
            "min_solidity": 0.5,
            "adaptive_threshold": True,
            "dark_star_mode": True,
            "description": "最大检测模式，包含所有可能的星点（通常>1000个）"
        }
    }
    
    if mode not in configs:
        raise ValueError(f"未知的检测模式: {mode}. 可用模式: {list(configs.keys())}")
    
    return configs[mode]

def create_detector(mode="balanced"):
    """
    创建指定模式的星点检测器
    
    Parameters:
    -----------
    mode : str
        检测模式
        
    Returns:
    --------
    StarDetector
        配置好的星点检测器
    """
    config = get_detector_config(mode)
    
    # 移除描述信息，只保留参数
    detector_params = {k: v for k, v in config.items() if k != "description"}
    
    return StarDetector(**detector_params)

def print_all_modes():
    """打印所有可用的检测模式"""
    print("可用的星点检测模式:")
    print("=" * 50)
    
    modes = ["minimal", "selective", "balanced", "sensitive", "maximum"]
    
    for mode in modes:
        config = get_detector_config(mode)
        print(f"\n🔹 {mode.upper()} 模式:")
        print(f"   {config['description']}")
        print(f"   参数: 面积{config['min_area']}-{config['max_area']}, "
              f"阈值{config['threshold_factor']}, "
              f"圆度≥{config['min_circularity']}")

if __name__ == "__main__":
    print_all_modes()
