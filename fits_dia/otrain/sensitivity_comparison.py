#!/usr/bin/env python3
"""
O'TRAIN检测灵敏度对比测试
"""

import os
import sys
from process_difference_with_otrain import OTrainProcessor

def compare_sensitivity_settings():
    """
    对比不同灵敏度设置的检测结果
    """
    print("="*60)
    print("O'TRAIN检测灵敏度对比测试")
    print("="*60)
    
    # 测试文件路径
    test_fits_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(test_fits_file):
        print(f"❌ 测试文件不存在: {test_fits_file}")
        return False
    
    # 不同灵敏度设置
    sensitivity_configs = [
        {
            "name": "保守检测",
            "threshold": 4.0,
            "min_area": 10,
            "description": "高阈值，大区域 - 减少虚假检测"
        },
        {
            "name": "标准检测",
            "threshold": 3.0,
            "min_area": 5,
            "description": "传统设置 - 平衡检测"
        },
        {
            "name": "高灵敏度检测 (新默认)",
            "threshold": 2.5,
            "min_area": 3,
            "description": "降低阈值和区域 - 检测更多候选"
        },
        {
            "name": "极高灵敏度检测",
            "threshold": 2.0,
            "min_area": 2,
            "description": "最低阈值 - 最大检测率"
        }
    ]
    
    results = []
    
    print(f"📁 测试文件: {test_fits_file}")
    print(f"🔬 测试 {len(sensitivity_configs)} 种灵敏度设置...\n")
    
    for i, config in enumerate(sensitivity_configs, 1):
        print(f"{i}. {config['name']}")
        print(f"   {config['description']}")
        print(f"   阈值: {config['threshold']}σ, 最小区域: {config['min_area']}像素")
        
        try:
            # 创建处理器
            processor = OTrainProcessor(output_dir=f"sensitivity_test_{i}")
            processor.detection_threshold = config['threshold']
            processor.min_area = config['min_area']
            
            # 只进行检测和分类，不保存完整结果
            image_data, header, success = processor.load_fits_image(test_fits_file)
            if not success:
                print("   ❌ 文件加载失败")
                continue
            
            # 检测候选天体
            candidates = processor.detect_candidates(image_data)
            
            if candidates:
                # 提取cutout
                cutouts = processor.extract_cutouts(image_data, candidates)
                
                if cutouts:
                    # 分类
                    classification_results = processor.simulate_otrain_classification(cutouts)
                    real_count = sum(1 for r in classification_results if r['classification'] == 'real')
                    
                    result = {
                        'config': config,
                        'candidates': len(candidates),
                        'real_transients': real_count,
                        'false_positives': len(candidates) - real_count,
                        'real_rate': real_count / len(candidates) * 100 if len(candidates) > 0 else 0
                    }
                    results.append(result)
                    
                    print(f"   ✅ 候选天体: {len(candidates)}")
                    print(f"   ✅ 真实瞬变: {real_count}")
                    print(f"   ✅ 真实率: {real_count/len(candidates)*100:.1f}%")
                else:
                    print("   ❌ Cutout提取失败")
            else:
                print("   ⚠️  未检测到任何候选天体")
                result = {
                    'config': config,
                    'candidates': 0,
                    'real_transients': 0,
                    'false_positives': 0,
                    'real_rate': 0
                }
                results.append(result)
        
        except Exception as e:
            print(f"   ❌ 处理出错: {str(e)}")
        
        print()
    
    # 显示对比结果
    if results:
        print("="*60)
        print("检测结果对比")
        print("="*60)
        
        print(f"{'设置':<20} {'候选数':<8} {'真实数':<8} {'虚假数':<8} {'真实率':<8}")
        print("-" * 60)
        
        for result in results:
            name = result['config']['name']
            candidates = result['candidates']
            real = result['real_transients']
            false = result['false_positives']
            rate = result['real_rate']
            
            print(f"{name:<20} {candidates:<8} {real:<8} {false:<8} {rate:<8.1f}%")
        
        print()
        print("📊 分析结果:")
        
        # 找到检测最多候选天体的设置
        max_candidates = max(results, key=lambda x: x['candidates'])
        print(f"   🔍 最多候选检测: {max_candidates['config']['name']} ({max_candidates['candidates']}个)")
        
        # 找到真实瞬变天体最多的设置
        max_real = max(results, key=lambda x: x['real_transients'])
        print(f"   ⭐ 最多真实检测: {max_real['config']['name']} ({max_real['real_transients']}个)")
        
        # 找到真实率最高的设置
        max_rate = max(results, key=lambda x: x['real_rate'])
        print(f"   🎯 最高真实率: {max_rate['config']['name']} ({max_rate['real_rate']:.1f}%)")
        
        print()
        print("💡 建议:")
        print("   - 高灵敏度设置能检测到更多候选天体")
        print("   - 但可能增加虚假检测的数量")
        print("   - 新的默认设置(2.5σ, 3像素)提供了良好的平衡")
        print("   - 可根据具体需求调整参数")
        
        return True
    
    return False

def show_parameter_guide():
    """
    显示参数调整指南
    """
    print("\n" + "="*60)
    print("参数调整指南")
    print("="*60)
    
    print("🔧 检测阈值 (--threshold):")
    print("   • 4.0σ: 保守检测，减少虚假检测")
    print("   • 3.0σ: 标准检测，传统设置")
    print("   • 2.5σ: 高灵敏度，新默认设置 ⭐")
    print("   • 2.0σ: 极高灵敏度，最大检测率")
    print("   • 更低值 = 更敏感，但可能增加噪声")
    print()
    
    print("📏 最小区域面积 (--min-area):")
    print("   • 10像素: 只检测较大的天体")
    print("   • 5像素: 标准大小限制")
    print("   • 3像素: 检测小天体，新默认设置 ⭐")
    print("   • 2像素: 检测极小天体")
    print("   • 更小值 = 检测更小目标，但可能增加噪声")
    print()
    
    print("⚖️ 平衡建议:")
    print("   • 科学研究: 使用高灵敏度设置 (2.5σ, 3像素)")
    print("   • 实时监测: 使用标准设置 (3.0σ, 5像素)")
    print("   • 高精度需求: 使用保守设置 (4.0σ, 10像素)")
    print("   • 探索性分析: 使用极高灵敏度 (2.0σ, 2像素)")

def main():
    """主函数"""
    print("🌟 O'TRAIN检测灵敏度对比工具")
    print()
    
    # 运行对比测试
    success = compare_sensitivity_settings()
    
    if success:
        # 显示参数指南
        show_parameter_guide()
        
        print("\n" + "="*60)
        print("🎉 灵敏度对比测试完成!")
        print()
        print("📚 使用说明:")
        print("   python process_difference_with_otrain.py file.fits --threshold 2.5 --min-area 3")
        print("   python process_difference_with_otrain.py file.fits  # 使用新的高灵敏度默认设置")
        print()
    else:
        print("❌ 对比测试失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()
