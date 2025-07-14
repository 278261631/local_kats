#!/usr/bin/env python3
"""
ORB参数调优工具
帮助找到最适合您的FITS图像的ORB特征检测参数
"""

import os
import sys
import numpy as np
import cv2
import matplotlib.pyplot as plt
from fits_alignment_comparison import FITSAlignmentComparison

# 设置matplotlib不显示窗口
plt.ioff()

class ORBTuner:
    """ORB参数调优器"""
    
    def __init__(self, fits_path1, fits_path2):
        """
        初始化调优器
        
        Args:
            fits_path1 (str): 参考FITS文件路径
            fits_path2 (str): 待比较FITS文件路径
        """
        self.fits_path1 = fits_path1
        self.fits_path2 = fits_path2
        self.img1 = None
        self.img2 = None
        
    def load_images(self, use_central_region=True, region_size=200):
        """加载和预处理图像"""
        try:
            comparator = FITSAlignmentComparison(
                use_central_region=use_central_region,
                central_region_size=region_size
            )
            
            img1_data, _, success1 = comparator.load_fits_image(self.fits_path1)
            img2_data, _, success2 = comparator.load_fits_image(self.fits_path2)
            
            if not success1 or not success2:
                return False
            
            self.img1 = comparator.preprocess_image(img1_data)
            self.img2 = comparator.preprocess_image(img2_data)
            
            return True
            
        except Exception as e:
            print(f"加载图像时出错: {str(e)}")
            return False
    
    def test_orb_parameters(self, orb_params):
        """
        测试ORB参数组合
        
        Args:
            orb_params (dict): ORB参数
            
        Returns:
            dict: 测试结果
        """
        try:
            # 创建ORB检测器
            orb = cv2.ORB_create(**orb_params)
            
            # 检测关键点和描述符
            kp1, des1 = orb.detectAndCompute(self.img1, None)
            kp2, des2 = orb.detectAndCompute(self.img2, None)
            
            if des1 is None or des2 is None or len(kp1) == 0 or len(kp2) == 0:
                return {
                    'keypoints1': 0,
                    'keypoints2': 0,
                    'matches': 0,
                    'match_ratio': 0.0,
                    'avg_distance': float('inf'),
                    'success': False
                }
            
            # 特征匹配
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            
            # 计算匹配质量
            match_ratio = len(matches) / min(len(kp1), len(kp2)) if min(len(kp1), len(kp2)) > 0 else 0
            avg_distance = np.mean([m.distance for m in matches]) if matches else float('inf')
            
            return {
                'keypoints1': len(kp1),
                'keypoints2': len(kp2),
                'matches': len(matches),
                'match_ratio': match_ratio,
                'avg_distance': avg_distance,
                'success': True
            }
            
        except Exception as e:
            print(f"测试ORB参数时出错: {str(e)}")
            return {
                'keypoints1': 0,
                'keypoints2': 0,
                'matches': 0,
                'match_ratio': 0.0,
                'avg_distance': float('inf'),
                'success': False
            }
    
    def tune_parameters(self):
        """调优ORB参数"""
        print("开始ORB参数调优...")
        
        # 定义参数搜索空间
        parameter_sets = [
            # 基础参数组合
            {'name': '默认参数', 'nfeatures': 1000, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 20},
            {'name': '更多特征点', 'nfeatures': 2000, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 20},
            {'name': '更少特征点', 'nfeatures': 500, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 20},
            
            # 调整尺度因子
            {'name': '小尺度因子', 'nfeatures': 1000, 'scaleFactor': 1.1, 'nlevels': 8, 'fastThreshold': 20},
            {'name': '大尺度因子', 'nfeatures': 1000, 'scaleFactor': 1.5, 'nlevels': 8, 'fastThreshold': 20},
            
            # 调整金字塔层数
            {'name': '更多层数', 'nfeatures': 1000, 'scaleFactor': 1.2, 'nlevels': 12, 'fastThreshold': 20},
            {'name': '更少层数', 'nfeatures': 1000, 'scaleFactor': 1.2, 'nlevels': 4, 'fastThreshold': 20},
            
            # 调整FAST阈值
            {'name': '低FAST阈值', 'nfeatures': 1000, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 10},
            {'name': '高FAST阈值', 'nfeatures': 1000, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 30},
            
            # 天文图像优化组合
            {'name': '天文优化1', 'nfeatures': 1500, 'scaleFactor': 1.15, 'nlevels': 10, 'fastThreshold': 15},
            {'name': '天文优化2', 'nfeatures': 2000, 'scaleFactor': 1.1, 'nlevels': 12, 'fastThreshold': 10},
            {'name': '天文优化3', 'nfeatures': 3000, 'scaleFactor': 1.2, 'nlevels': 8, 'fastThreshold': 5},
        ]
        
        results = []
        
        for params in parameter_sets:
            name = params.pop('name')
            print(f"测试参数组合: {name}")
            
            # 添加固定参数
            full_params = {
                'edgeThreshold': 31,
                'firstLevel': 0,
                'WTA_K': 2,
                'patchSize': 31,
                **params
            }
            
            # 尝试添加scoreType
            try:
                full_params['scoreType'] = cv2.ORB_SCORE_HARRIS
            except AttributeError:
                pass
            
            result = self.test_orb_parameters(full_params)
            result['name'] = name
            result['params'] = params
            results.append(result)
            
            print(f"  特征点: {result['keypoints1']}/{result['keypoints2']}, "
                  f"匹配: {result['matches']}, "
                  f"匹配率: {result['match_ratio']:.3f}, "
                  f"平均距离: {result['avg_distance']:.2f}")
        
        return results
    
    def analyze_results(self, results):
        """分析调优结果"""
        print("\n" + "=" * 80)
        print("ORB参数调优结果分析")
        print("=" * 80)
        
        # 过滤成功的结果
        successful_results = [r for r in results if r['success']]
        
        if not successful_results:
            print("❌ 所有参数组合都失败了！")
            return None
        
        # 按不同指标排序
        by_matches = sorted(successful_results, key=lambda x: x['matches'], reverse=True)
        by_match_ratio = sorted(successful_results, key=lambda x: x['match_ratio'], reverse=True)
        by_distance = sorted(successful_results, key=lambda x: x['avg_distance'])
        
        print(f"{'参数组合':<15} {'特征点1':<8} {'特征点2':<8} {'匹配数':<8} {'匹配率':<8} {'平均距离':<10}")
        print("-" * 80)
        
        for result in successful_results:
            print(f"{result['name']:<15} {result['keypoints1']:<8} {result['keypoints2']:<8} "
                  f"{result['matches']:<8} {result['match_ratio']:<8.3f} {result['avg_distance']:<10.2f}")
        
        print("\n🏆 推荐参数组合:")
        print("-" * 40)
        
        # 最多匹配点
        best_matches = by_matches[0]
        print(f"最多匹配点: {best_matches['name']} ({best_matches['matches']}个匹配)")
        
        # 最高匹配率
        best_ratio = by_match_ratio[0]
        print(f"最高匹配率: {best_ratio['name']} ({best_ratio['match_ratio']:.3f})")
        
        # 最小距离
        best_distance = by_distance[0]
        print(f"最佳匹配质量: {best_distance['name']} (距离={best_distance['avg_distance']:.2f})")
        
        # 综合评分
        print("\n📊 综合评分 (匹配数 × 匹配率 / 距离):")
        scored_results = []
        for result in successful_results:
            if result['avg_distance'] > 0:
                score = (result['matches'] * result['match_ratio']) / result['avg_distance']
                scored_results.append((result, score))
        
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        for i, (result, score) in enumerate(scored_results[:5]):
            print(f"{i+1}. {result['name']}: 评分={score:.3f}")
        
        # 返回最佳参数
        if scored_results:
            best_overall = scored_results[0][0]
            print(f"\n✅ 推荐使用: {best_overall['name']}")
            print("参数配置:")
            for key, value in best_overall['params'].items():
                print(f"  {key}: {value}")
            
            return best_overall
        
        return None
    
    def save_comparison_chart(self, results, output_path):
        """保存参数对比图表"""
        try:
            successful_results = [r for r in results if r['success']]
            if not successful_results:
                return
            
            names = [r['name'] for r in successful_results]
            matches = [r['matches'] for r in successful_results]
            ratios = [r['match_ratio'] for r in successful_results]
            distances = [r['avg_distance'] for r in successful_results]
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 匹配数量
            axes[0, 0].bar(range(len(names)), matches, color='skyblue')
            axes[0, 0].set_title('匹配点数量')
            axes[0, 0].set_ylabel('匹配数')
            axes[0, 0].set_xticks(range(len(names)))
            axes[0, 0].set_xticklabels(names, rotation=45, ha='right')
            
            # 匹配率
            axes[0, 1].bar(range(len(names)), ratios, color='lightgreen')
            axes[0, 1].set_title('匹配率')
            axes[0, 1].set_ylabel('匹配率')
            axes[0, 1].set_xticks(range(len(names)))
            axes[0, 1].set_xticklabels(names, rotation=45, ha='right')
            
            # 平均距离
            axes[1, 0].bar(range(len(names)), distances, color='salmon')
            axes[1, 0].set_title('平均匹配距离')
            axes[1, 0].set_ylabel('距离')
            axes[1, 0].set_xticks(range(len(names)))
            axes[1, 0].set_xticklabels(names, rotation=45, ha='right')
            
            # 综合评分
            scores = []
            for result in successful_results:
                if result['avg_distance'] > 0:
                    score = (result['matches'] * result['match_ratio']) / result['avg_distance']
                    scores.append(score)
                else:
                    scores.append(0)
            
            axes[1, 1].bar(range(len(names)), scores, color='gold')
            axes[1, 1].set_title('综合评分')
            axes[1, 1].set_ylabel('评分')
            axes[1, 1].set_xticks(range(len(names)))
            axes[1, 1].set_xticklabels(names, rotation=45, ha='right')
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"参数对比图表已保存: {output_path}")
            
        except Exception as e:
            print(f"保存对比图表时出错: {str(e)}")

def main():
    """主函数"""
    fits_dir = r"E:\fix_data\align-compare"
    fits1 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit")
    fits2 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit")
    
    if not os.path.exists(fits1) or not os.path.exists(fits2):
        print("错误: FITS文件不存在")
        return
    
    print("=" * 60)
    print("ORB参数调优工具")
    print("=" * 60)
    print(f"参考图像: {os.path.basename(fits1)}")
    print(f"比较图像: {os.path.basename(fits2)}")
    print("=" * 60)
    
    # 创建调优器
    tuner = ORBTuner(fits1, fits2)
    
    # 加载图像
    if not tuner.load_images():
        print("图像加载失败！")
        return
    
    # 执行调优
    results = tuner.tune_parameters()
    
    # 分析结果
    best_params = tuner.analyze_results(results)
    
    # 保存对比图表
    tuner.save_comparison_chart(results, "orb_parameter_comparison.png")
    
    if best_params:
        print(f"\n💡 建议在运行对齐程序时使用以下参数:")
        print(f"python run_alignment_comparison.py --directory \"{fits_dir}\" --orb-features {best_params['params']['nfeatures']}")

if __name__ == "__main__":
    main()
