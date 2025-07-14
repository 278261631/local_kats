#!/usr/bin/env python3
"""
FITS图像特征点可视化工具
专门用于可视化和分析特征点匹配结果
"""

import os
import sys
import argparse
import numpy as np
import cv2
import matplotlib.pyplot as plt
from fits_alignment_comparison import FITSAlignmentComparison

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class FeatureVisualizer:
    """特征点可视化器"""
    
    def __init__(self, orb_params=None):
        """
        初始化可视化器
        
        Args:
            orb_params (dict): ORB参数配置
        """
        self.orb_params = orb_params or {
            'nfeatures': 1000,
            'scaleFactor': 1.2,
            'nlevels': 8,
            'edgeThreshold': 31,
            'firstLevel': 0,
            'WTA_K': 2,
            'patchSize': 31,
            'fastThreshold': 20
        }
        
        # 尝试设置scoreType
        try:
            self.orb_params['scoreType'] = cv2.ORB_SCORE_HARRIS
        except AttributeError:
            pass
    
    def load_and_preprocess_images(self, fits_path1, fits_path2, use_central_region=True, region_size=200):
        """
        加载和预处理FITS图像
        
        Args:
            fits_path1 (str): 第一个FITS文件路径
            fits_path2 (str): 第二个FITS文件路径
            use_central_region (bool): 是否使用中央区域
            region_size (int): 中央区域大小
            
        Returns:
            tuple: (img1, img2, success)
        """
        try:
            # 创建临时的比较系统来加载图像
            comparator = FITSAlignmentComparison(
                use_central_region=use_central_region,
                central_region_size=region_size
            )
            
            # 加载图像
            img1_data, _, success1 = comparator.load_fits_image(fits_path1)
            img2_data, _, success2 = comparator.load_fits_image(fits_path2)
            
            if not success1 or not success2:
                return None, None, False
            
            # 预处理
            img1 = comparator.preprocess_image(img1_data)
            img2 = comparator.preprocess_image(img2_data)
            
            return img1, img2, True
            
        except Exception as e:
            print(f"加载图像时出错: {str(e)}")
            return None, None, False
    
    def detect_and_analyze_features(self, img1, img2):
        """
        检测和分析特征点
        
        Args:
            img1 (np.ndarray): 第一张图像
            img2 (np.ndarray): 第二张图像
            
        Returns:
            tuple: (kp1, des1, kp2, des2, matches)
        """
        try:
            # 创建ORB检测器
            orb = cv2.ORB_create(**self.orb_params)
            
            # 检测关键点和描述符
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)
            
            print(f"检测到特征点: 图像1={len(kp1)}, 图像2={len(kp2)}")
            
            if des1 is None or des2 is None:
                print("警告: 未检测到足够的特征点")
                return kp1, des1, kp2, des2, []
            
            # 特征匹配
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            
            print(f"找到 {len(matches)} 个匹配点")
            
            return kp1, des1, kp2, des2, matches
            
        except Exception as e:
            print(f"特征检测时出错: {str(e)}")
            return None, None, None, None, []
    
    def create_comprehensive_visualization(self, img1, img2, kp1, kp2, matches, output_dir):
        """
        创建综合的特征点可视化
        
        Args:
            img1, img2: 输入图像
            kp1, kp2: 关键点
            matches: 匹配结果
            output_dir: 输出目录
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 1. 特征点匹配可视化
            self.visualize_matches(img1, img2, kp1, kp2, matches, 
                                 os.path.join(output_dir, "feature_matches.png"))
            
            # 2. 分别显示特征点
            self.visualize_keypoints_separate(img1, img2, kp1, kp2, 
                                            os.path.join(output_dir, "keypoints_separate.png"))
            
            # 3. 匹配质量分析
            self.analyze_and_visualize_match_quality(matches, kp1, kp2, 
                                                   os.path.join(output_dir, "match_analysis.png"))
            
            # 4. 特征点密度热图
            self.visualize_keypoint_density(img1, img2, kp1, kp2, 
                                          os.path.join(output_dir, "keypoint_density.png"))
            
            print(f"所有可视化结果已保存到: {output_dir}")
            
        except Exception as e:
            print(f"创建可视化时出错: {str(e)}")
    
    def visualize_matches(self, img1, img2, kp1, kp2, matches, save_path):
        """可视化特征点匹配"""
        if not matches:
            print("没有匹配点可以可视化")
            return
        
        # 显示最佳匹配
        num_matches = min(30, len(matches))
        img_matches = cv2.drawMatches(
            img1, kp1, img2, kp2, matches[:num_matches],
            None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
        )
        
        plt.figure(figsize=(20, 10))
        plt.imshow(img_matches, cmap='gray')
        plt.title(f'特征点匹配可视化 (显示前{num_matches}个最佳匹配，总共{len(matches)}个)', fontsize=16)
        plt.axis('off')
        
        # 添加统计信息
        info_text = (f"图像1特征点: {len(kp1)}\n"
                    f"图像2特征点: {len(kp2)}\n"
                    f"匹配点对: {len(matches)}\n"
                    f"匹配率: {len(matches)/min(len(kp1), len(kp2))*100:.1f}%")
        
        plt.text(20, 50, info_text, fontsize=14, color='yellow',
                bbox=dict(boxstyle="round,pad=0.5", facecolor="black", alpha=0.8))
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()  # 关闭图形以避免显示
        print(f"特征匹配可视化已保存: {save_path}")
    
    def visualize_keypoints_separate(self, img1, img2, kp1, kp2, save_path):
        """分别可视化特征点"""
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        
        # 图像1特征点
        img1_kp = cv2.drawKeypoints(img1, kp1, None, color=(0, 255, 0),
                                   flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        axes[0].imshow(img1_kp)
        axes[0].set_title(f'参考图像特征点 ({len(kp1)}个)', fontsize=14)
        axes[0].axis('off')
        
        # 图像2特征点
        img2_kp = cv2.drawKeypoints(img2, kp2, None, color=(0, 255, 0),
                                   flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        axes[1].imshow(img2_kp)
        axes[1].set_title(f'待对齐图像特征点 ({len(kp2)}个)', fontsize=14)
        axes[1].axis('off')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()  # 关闭图形以避免显示
        print(f"特征点分布可视化已保存: {save_path}")
    
    def analyze_and_visualize_match_quality(self, matches, kp1, kp2, save_path):
        """分析和可视化匹配质量"""
        if not matches:
            return
        
        distances = [m.distance for m in matches]
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 距离分布直方图
        axes[0, 0].hist(distances, bins=20, alpha=0.7, color='blue')
        axes[0, 0].set_title('匹配距离分布')
        axes[0, 0].set_xlabel('距离')
        axes[0, 0].set_ylabel('频次')
        axes[0, 0].axvline(np.mean(distances), color='red', linestyle='--', label=f'平均值: {np.mean(distances):.2f}')
        axes[0, 0].legend()
        
        # 匹配点空间分布
        pts1 = np.array([kp1[m.queryIdx].pt for m in matches])
        pts2 = np.array([kp2[m.trainIdx].pt for m in matches])
        
        axes[0, 1].scatter(pts1[:, 0], pts1[:, 1], alpha=0.6, s=30, c='red', label='图像1')
        axes[0, 1].set_title('图像1匹配点分布')
        axes[0, 1].set_xlabel('X坐标')
        axes[0, 1].set_ylabel('Y坐标')
        axes[0, 1].legend()
        
        axes[1, 0].scatter(pts2[:, 0], pts2[:, 1], alpha=0.6, s=30, c='blue', label='图像2')
        axes[1, 0].set_title('图像2匹配点分布')
        axes[1, 0].set_xlabel('X坐标')
        axes[1, 0].set_ylabel('Y坐标')
        axes[1, 0].legend()
        
        # 统计信息
        stats_text = (f"匹配统计:\n"
                     f"总匹配数: {len(matches)}\n"
                     f"平均距离: {np.mean(distances):.2f}\n"
                     f"最小距离: {np.min(distances):.2f}\n"
                     f"最大距离: {np.max(distances):.2f}\n"
                     f"距离标准差: {np.std(distances):.2f}\n\n"
                     f"空间分布:\n"
                     f"图像1范围: X={np.max(pts1[:, 0])-np.min(pts1[:, 0]):.1f}, "
                     f"Y={np.max(pts1[:, 1])-np.min(pts1[:, 1]):.1f}\n"
                     f"图像2范围: X={np.max(pts2[:, 0])-np.min(pts2[:, 0]):.1f}, "
                     f"Y={np.max(pts2[:, 1])-np.min(pts2[:, 1]):.1f}")
        
        axes[1, 1].text(0.05, 0.95, stats_text, transform=axes[1, 1].transAxes,
                        fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
        axes[1, 1].set_title('匹配质量统计')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()  # 关闭图形以避免显示
        print(f"匹配质量分析已保存: {save_path}")
    
    def visualize_keypoint_density(self, img1, img2, kp1, kp2, save_path):
        """可视化特征点密度热图"""
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        
        # 创建密度热图
        h1, w1 = img1.shape
        h2, w2 = img2.shape
        
        # 图像1密度
        pts1 = np.array([kp.pt for kp in kp1])
        if len(pts1) > 0:
            axes[0].hexbin(pts1[:, 0], pts1[:, 1], gridsize=20, cmap='hot', alpha=0.7)
        axes[0].imshow(img1, cmap='gray', alpha=0.5)
        axes[0].set_title(f'图像1特征点密度分布 ({len(kp1)}个特征点)')
        axes[0].set_xlim(0, w1)
        axes[0].set_ylim(h1, 0)
        
        # 图像2密度
        pts2 = np.array([kp.pt for kp in kp2])
        if len(pts2) > 0:
            axes[1].hexbin(pts2[:, 0], pts2[:, 1], gridsize=20, cmap='hot', alpha=0.7)
        axes[1].imshow(img2, cmap='gray', alpha=0.5)
        axes[1].set_title(f'图像2特征点密度分布 ({len(kp2)}个特征点)')
        axes[1].set_xlim(0, w2)
        axes[1].set_ylim(h2, 0)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()  # 关闭图形以避免显示
        print(f"特征点密度可视化已保存: {save_path}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='FITS图像特征点可视化工具')
    parser.add_argument('fits1', help='参考FITS文件路径')
    parser.add_argument('fits2', help='待比较FITS文件路径')
    parser.add_argument('--output', '-o', default='feature_visualization', help='输出目录')
    parser.add_argument('--no-central-region', action='store_true', help='不使用中央区域优化')
    parser.add_argument('--region-size', type=int, default=200, help='中央区域大小')
    parser.add_argument('--orb-features', type=int, default=1000, help='ORB特征点数量')
    
    args = parser.parse_args()
    
    # 检查文件
    if not os.path.exists(args.fits1):
        print(f"错误: 文件不存在 - {args.fits1}")
        return
    
    if not os.path.exists(args.fits2):
        print(f"错误: 文件不存在 - {args.fits2}")
        return
    
    print("=" * 60)
    print("FITS图像特征点可视化工具")
    print("=" * 60)
    print(f"参考图像: {os.path.basename(args.fits1)}")
    print(f"比较图像: {os.path.basename(args.fits2)}")
    print(f"输出目录: {args.output}")
    print(f"中央区域: {'禁用' if args.no_central_region else f'{args.region_size}x{args.region_size}像素'}")
    print("=" * 60)
    
    # 创建可视化器
    orb_params = {
        'nfeatures': args.orb_features,
        'scaleFactor': 1.2,
        'nlevels': 8,
        'edgeThreshold': 31,
        'firstLevel': 0,
        'WTA_K': 2,
        'patchSize': 31,
        'fastThreshold': 20
    }
    
    visualizer = FeatureVisualizer(orb_params)
    
    # 加载图像
    print("加载和预处理图像...")
    img1, img2, success = visualizer.load_and_preprocess_images(
        args.fits1, args.fits2, 
        not args.no_central_region, args.region_size
    )
    
    if not success:
        print("图像加载失败！")
        return
    
    # 检测特征点
    print("检测特征点和匹配...")
    kp1, des1, kp2, des2, matches = visualizer.detect_and_analyze_features(img1, img2)
    
    if kp1 is None or kp2 is None:
        print("特征点检测失败！")
        return
    
    # 创建可视化
    print("创建可视化...")
    visualizer.create_comprehensive_visualization(img1, img2, kp1, kp2, matches, args.output)
    
    print("\n特征点可视化完成！")

if __name__ == "__main__":
    main()
