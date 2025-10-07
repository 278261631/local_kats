import cv2
import numpy as np
import argparse
from pathlib import Path


def remove_lines_morphology(image, kernel_size=(1, 15), iterations=1):
    """
    使用形态学操作去除亮线
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel, iterations=iterations)
    
    result = cv2.subtract(gray, tophat)
    
    if len(image.shape) == 3:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    
    return result


def remove_lines_inpainting(image, threshold=200, kernel_size=3):
    """
    使用图像修复技术去除亮线
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
    
    return result, mask


def remove_lines_median_filter(image, ksize=5):
    """
    使用中值滤波去除亮线
    """
    result = cv2.medianBlur(image, ksize)
    return result


def remove_lines_bilateral(image, d=9, sigma_color=75, sigma_space=75):
    """
    使用双边滤波去除亮线同时保持边缘
    """
    result = cv2.bilateralFilter(image, d, sigma_color, sigma_space)
    return result


def remove_lines_adaptive(image, threshold_value=200, kernel_vertical=(1, 20), kernel_horizontal=(20, 1)):
    """
    自适应去除垂直和水平亮线
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    _, binary = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
    
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_vertical)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v, iterations=2)
    
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_horizontal)
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h, iterations=2)
    
    lines_mask = cv2.bitwise_or(vertical_lines, horizontal_lines)
    
    result = image.copy()
    if len(image.shape) == 3:
        result = cv2.inpaint(result, lines_mask, 3, cv2.INPAINT_TELEA)
    else:
        result_color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        result_color = cv2.inpaint(result_color, lines_mask, 3, cv2.INPAINT_TELEA)
        result = cv2.cvtColor(result_color, cv2.COLOR_BGR2GRAY)
    
    return result, lines_mask


def remove_lines_frequency(image):
    """
    使用频域滤波去除周期性亮线
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    dft = cv2.dft(np.float32(gray), flags=cv2.DFT_COMPLEX_OUTPUT)
    dft_shift = np.fft.fftshift(dft)

    rows, cols = gray.shape
    crow, ccol = rows // 2, cols // 2

    mask = np.ones((rows, cols, 2), np.uint8)
    r = 30
    center = [crow, ccol]
    x, y = np.ogrid[:rows, :cols]
    mask_area = (x - center[0]) ** 2 + (y - center[1]) ** 2 <= r*r
    mask[mask_area] = 1

    fshift = dft_shift * mask

    f_ishift = np.fft.ifftshift(fshift)
    img_back = cv2.idft(f_ishift)
    img_back = cv2.magnitude(img_back[:, :, 0], img_back[:, :, 1])

    img_back = cv2.normalize(img_back, None, 0, 255, cv2.NORM_MINMAX)
    result = np.uint8(img_back)

    if len(image.shape) == 3:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    return result


def remove_lines_inverse_inpainting(image, threshold=200, min_area=50, kernel_size=3):
    """
    反向修复：检测亮线并修复，保留检测目标
    通过面积过滤区分亮线（细长）和目标（较大块状）
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 检测所有亮区域
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # 查找所有连通区域
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    # 创建掩码：只标记亮线（小面积或细长区域）
    mask = np.zeros(gray.shape, dtype=np.uint8)

    for i in range(1, num_labels):  # 跳过背景（标签0）
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]

        # 判断是否为亮线：面积小或者长宽比极端（细长）
        aspect_ratio = max(width, height) / (min(width, height) + 1)

        # 如果面积小于阈值，或者是细长形状，认为是亮线
        if area < min_area or aspect_ratio > 10:
            mask[labels == i] = 255

    # 膨胀掩码以确保完全覆盖亮线
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    # 使用掩码修复图像
    result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

    return result, mask


def remove_lines_line_detection(image, threshold=200, line_length=30, line_gap=10):
    """
    使用霍夫直线检测来识别亮线
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 检测亮区域
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # 边缘检测
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)

    # 霍夫直线检测
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                            minLineLength=line_length, maxLineGap=line_gap)

    # 创建掩码
    mask = np.zeros(gray.shape, dtype=np.uint8)

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # 在掩码上画线，加粗一些
            cv2.line(mask, (x1, y1), (x2, y2), 255, 5)

    # 使用掩码修复图像
    result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

    return result, mask


def process_image(input_path, output_dir, method='all'):
    """
    处理图片并保存结果
    """
    image = cv2.imread(input_path)
    if image is None:
        print(f"无法读取图片: {input_path}")
        return
    
    input_file = Path(input_path)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    base_name = input_file.stem
    
    print(f"正在处理图片: {input_path}")
    print(f"图片尺寸: {image.shape}")
    
    if method == 'all' or method == 'morphology':
        print("方法1: 形态学操作...")
        result1 = remove_lines_morphology(image, kernel_size=(1, 15))
        output_file = output_path / f"{base_name}_morphology.png"
        cv2.imwrite(str(output_file), result1)
        print(f"  保存到: {output_file}")
    
    if method == 'all' or method == 'inpainting':
        print("方法2: 图像修复...")
        result2, mask2 = remove_lines_inpainting(image, threshold=200)
        output_file = output_path / f"{base_name}_inpainting.png"
        cv2.imwrite(str(output_file), result2)
        mask_file = output_path / f"{base_name}_mask.png"
        cv2.imwrite(str(mask_file), mask2)
        print(f"  保存到: {output_file}")
        print(f"  掩码保存到: {mask_file}")
    
    if method == 'all' or method == 'median':
        print("方法3: 中值滤波...")
        result3 = remove_lines_median_filter(image, ksize=5)
        output_file = output_path / f"{base_name}_median.png"
        cv2.imwrite(str(output_file), result3)
        print(f"  保存到: {output_file}")
    
    if method == 'all' or method == 'bilateral':
        print("方法4: 双边滤波...")
        result4 = remove_lines_bilateral(image)
        output_file = output_path / f"{base_name}_bilateral.png"
        cv2.imwrite(str(output_file), result4)
        print(f"  保存到: {output_file}")
    
    if method == 'all' or method == 'adaptive':
        print("方法5: 自适应去线...")
        result5, mask5 = remove_lines_adaptive(image, threshold_value=200)
        output_file = output_path / f"{base_name}_adaptive.png"
        cv2.imwrite(str(output_file), result5)
        mask_file = output_path / f"{base_name}_adaptive_mask.png"
        cv2.imwrite(str(mask_file), mask5)
        print(f"  保存到: {output_file}")
        print(f"  掩码保存到: {mask_file}")
    
    if method == 'all' or method == 'frequency':
        print("方法6: 频域滤波...")
        result6 = remove_lines_frequency(image)
        output_file = output_path / f"{base_name}_frequency.png"
        cv2.imwrite(str(output_file), result6)
        print(f"  保存到: {output_file}")

    if method == 'all' or method == 'inverse':
        print("方法7: 反向修复（保留目标，去除亮线）...")
        result7, mask7 = remove_lines_inverse_inpainting(image, threshold=200, min_area=50)
        output_file = output_path / f"{base_name}_inverse.png"
        cv2.imwrite(str(output_file), result7)
        mask_file = output_path / f"{base_name}_inverse_mask.png"
        cv2.imwrite(str(mask_file), mask7)
        print(f"  保存到: {output_file}")
        print(f"  掩码保存到: {mask_file}")

    if method == 'all' or method == 'linedetect':
        print("方法8: 直线检测...")
        result8, mask8 = remove_lines_line_detection(image, threshold=200)
        output_file = output_path / f"{base_name}_linedetect.png"
        cv2.imwrite(str(output_file), result8)
        mask_file = output_path / f"{base_name}_linedetect_mask.png"
        cv2.imwrite(str(mask_file), mask8)
        print(f"  保存到: {output_file}")
        print(f"  掩码保存到: {mask_file}")

    print("\n处理完成!")


def main():
    parser = argparse.ArgumentParser(description='去除图片中的亮线')
    parser.add_argument('--input', '-i', type=str, default='line_test.png',
                        help='输入图片路径')
    parser.add_argument('--output', '-o', type=str, default='output',
                        help='输出目录')
    parser.add_argument('--method', '-m', type=str, default='all',
                        choices=['all', 'morphology', 'inpainting', 'median',
                                'bilateral', 'adaptive', 'frequency', 'inverse', 'linedetect'],
                        help='去除亮线的方法')
    
    args = parser.parse_args()
    
    process_image(args.input, args.output, args.method)


if __name__ == '__main__':
    main()

