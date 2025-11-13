import cv2
import numpy as np
from pathlib import Path
import argparse
from typing import List, Tuple


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """计算点到线段的最短距离（像素）。"""
    # 线段向量和点向量
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1

    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq == 0:
        # 退化为点
        return float(np.hypot(px - x1, py - y1))

    # 投影参数 t ∈ [0,1]
    t = (wx * vx + wy * vy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    # 线段上最近点
    cx, cy = x1 + t * vx, y1 + t * vy
    return float(np.hypot(px - cx, py - cy))


def detect_lines_near_center(image: np.ndarray,
                             radius_px: int = 3,
                             canny1: int = 50,
                             canny2: int = 150,
                             hough_thresh: int = 60,
                             min_len: int = 30,
                             max_gap: int = 5,
                             roi_margin: int = 0) -> Tuple[List[Tuple[int, int, int, int]], List[Tuple[int, int, int, int]], Tuple[int, int]]:
    """
    使用 Canny + HoughLinesP 检测线段，仅在中心附近 ROI 内进行，返回：
    - near_lines: 与图像中心距离 <= radius_px 的线段列表
    - all_lines: 该图像检测到的全部线段列表（已换算回整图坐标）
    - center: 图像中心 (cx, cy)
    """
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2

    # 灰度 + 轻微平滑
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # ROI 策略：roi_margin < 0 时使用全图；否则仅在中心附近 ROI 内检测
    if roi_margin < 0:
        x0, y0, x1, y1 = 0, 0, w, h
    else:
        half = max(radius_px + roi_margin, 8)
        x0, x1 = max(0, cx - half), min(w, cx + half)
        y0, y1 = max(0, cy - half), min(h, cy + half)
    roi = gray[y0:y1, x0:x1]

    all_lines: List[Tuple[int, int, int, int]] = []
    near_lines: List[Tuple[int, int, int, int]] = []

    if roi.size > 0:
        edges = cv2.Canny(roi, canny1, canny2, apertureSize=3)
        roi_h, roi_w = roi.shape[:2]
        # 缩小 ROI 时自动降低最小线段长度阈值（为 ROI 边长的 0.6 倍）
        adj_min_len = min(min_len, int(0.6 * max(roi_w, roi_h)))
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180.0,
            threshold=hough_thresh,
            minLineLength=int(adj_min_len),
            maxLineGap=max_gap,
        )
    else:
        lines = None

    if lines is not None:
        for ln in lines:
            rx1, ry1, rx2, ry2 = map(int, ln[0])
            x1g, y1g, x2g, yg2 = x0 + rx1, y0 + ry1, x0 + rx2, y0 + ry2
            all_lines.append((x1g, y1g, x2g, yg2))
            d = point_to_segment_distance(cx, cy, x1g, y1g, x2g, yg2)
            if d <= radius_px:
                near_lines.append((x1g, y1g, x2g, yg2))

    return near_lines, all_lines, (cx, cy)



def compute_line_saliency_map(gray: np.ndarray,
                               all_lines: List[Tuple[int, int, int, int]],
                               center: Tuple[int, int]) -> dict:
    """计算每条线段的显著性分数并返回映射 {(x1,y1,x2,y2) -> score}。
    设计：
    - 长度归一化: 线长 / (0.5*max(w,h))，截断到[0,1]
    - 边缘强度: Sobel梯度幅值在该线段上的平均，除以整图的P95后截断到[0,1]
    - 显著性: 0.6*边缘强度 + 0.4*长度
    """
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    gray_f = gray.astype(np.float32)
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    p95 = float(np.percentile(grad, 95)) if grad.size > 0 else 1.0
    p95 = max(p95, 1e-6)
    L_ref = 0.5 * float(max(w, h))
    L_ref = max(L_ref, 1.0)

    scores = {}
    for x1, y1, x2, y2 in all_lines:
        # 线段长度
        length = float(np.hypot(x2 - x1, y2 - y1))
        L_norm = min(1.0, length / L_ref)
        # 采样线上的梯度强度
        n_samples = max(10, int(length))
        xs = np.linspace(x1, x2, num=n_samples, dtype=np.float32)
        ys = np.linspace(y1, y2, num=n_samples, dtype=np.float32)
        xi = np.clip(xs.astype(np.int32), 0, w - 1)
        yi = np.clip(ys.astype(np.int32), 0, h - 1)
        vals = grad[yi, xi] if grad.size > 0 else np.array([0.0], dtype=np.float32)
        G_norm = float(np.clip(np.mean(vals) / p95, 0.0, 1.0)) if vals.size > 0 else 0.0
        saliency = 0.6 * G_norm + 0.4 * L_norm
        scores[(int(x1), int(y1), int(x2), int(y2))] = float(saliency)
    return scores


def annotate_image(image: np.ndarray,
                   near_lines: List[Tuple[int, int, int, int]],
                   center: Tuple[int, int],
                   radius_px: int,
                   all_lines: List[Tuple[int, int, int, int]] | None = None,
                   line_scores: dict | None = None) -> np.ndarray:
    """
    标注图像：
    - 所有检测到的线段（可选）用绿色绘制，并在有评分时标注 s=显著性
    - 与中心距离 <= radius_px 的线段用红色高亮
    - 画出中心点和半径圈
    """
    if image.ndim == 2:
        out = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        out = image.copy()

    # 先绘制所有线段为绿色，并可选标注显著性
    if all_lines:
        for x1, y1, x2, y2 in all_lines:
            cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 1, cv2.LINE_AA)
            if line_scores is not None:
                s = line_scores.get((int(x1), int(y1), int(x2), int(y2)))
                if s is not None:
                    mx, my = int((x1 + x2) * 0.5), int((y1 + y2) * 0.5)
                    label = f"s={s:.2f}"
                    cv2.putText(out, label, (mx + 3, my - 3), cv2.FONT_HERSHEY_SIMPLEX,
                                0.4, (0, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(out, label, (mx + 3, my - 3), cv2.FONT_HERSHEY_SIMPLEX,
                                0.4, (0, 255, 255), 1, cv2.LINE_AA)

    # 高亮靠近中心的线段（红色，线宽与绿色一致，不加粗）
    for x1, y1, x2, y2 in near_lines:
        cv2.line(out, (x1, y1), (x2, y2), (0, 0, 255), 1, cv2.LINE_AA)

    cx, cy = center
    # 中心与半径圈
    cv2.circle(out, (cx, cy), radius_px, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.drawMarker(out, (cx, cy), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=8, thickness=1)

    return out


def process_one_image(img_path: Path, out_dir: Path, radius_px: int,
                      canny1: int, canny2: int, hough_thresh: int, min_len: int, max_gap: int,
                      roi_margin: int = 0,
                      max_near_lines: int | None = None,
                      save_all_lines: bool = True,
                      label_saliency: bool = True,
                      saliency_thresh: float = 0.8) -> Tuple[int, int]:
    image = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        print(f"[跳过] 无法读取图片: {img_path}")
        return 0, 0

    near_lines, all_lines, center = detect_lines_near_center(
        image,
        radius_px=radius_px,
        canny1=canny1,
        canny2=canny2,
        hough_thresh=hough_thresh,
        min_len=min_len,
        max_gap=max_gap,
        roi_margin=roi_margin,
    )

    # 可选：仅保留距离中心最近的前 N 条
    if max_near_lines and max_near_lines > 0 and near_lines:
        cx, cy = center
        ranked = sorted(
            near_lines,
            key=lambda ln: point_to_segment_distance(cx, cy, ln[0], ln[1], ln[2], ln[3])
        )
        near_lines = ranked[:max_near_lines]

    # 显著性评分与阈值过滤：计算每条线段的显著性，并丢弃 s < saliency_thresh 的线
    gray_for_score = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    line_scores = compute_line_saliency_map(gray_for_score, all_lines, center) if len(all_lines) > 0 else {}

    if len(line_scores) > 0:
        # 过滤 all_lines 与 near_lines
        all_lines = [ln for ln in all_lines if line_scores.get((int(ln[0]), int(ln[1]), int(ln[2]), int(ln[3])), 0.0) >= float(saliency_thresh)]
        near_lines = [ln for ln in near_lines if line_scores.get((int(ln[0]), int(ln[1]), int(ln[2]), int(ln[3])), 0.0) >= float(saliency_thresh)]

    # 若不需要显示显著性标签，则不传入评分
    line_scores_for_draw = line_scores if label_saliency else None

    annotated = annotate_image(
        image,
        near_lines,
        center,
        radius_px,
        all_lines if save_all_lines else None,
        line_scores=line_scores_for_draw,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{img_path.stem}_center_lines.png"
    cv2.imwrite(str(out_file), annotated)

    print(f"- {img_path.name}: 检测线段 {len(all_lines)} 条，靠近中心(≤{radius_px}px) {len(near_lines)} 条 -> {out_file.name}")
    return len(all_lines), len(near_lines)


def main():
    parser = argparse.ArgumentParser(description="检测并标注距离图像中心3像素以内的线段")
    parser.add_argument("--input-dir", type=str, default=None,
                        help="输入图像目录（默认：脚本所在目录）")
    parser.add_argument("--output-dir", type=str, default="output_center_lines",
                        help="输出目录（默认：输入目录下的 output_center_lines 子目录）")
    parser.add_argument("--radius", type=int, default=3, help="中心半径像素阈值，默认3")
    parser.add_argument("--canny1", type=int, default=50, help="Canny 低阈值")
    parser.add_argument("--canny2", type=int, default=150, help="Canny 高阈值")
    parser.add_argument("--hough-thresh", type=int, default=60, help="HoughLinesP 累计阈值")
    parser.add_argument("--min-len", type=int, default=30, help="最小线段长度")
    parser.add_argument("--max-gap", type=int, default=5, help="线段内最大间隙")
    # 显示控制：默认绘制所有线段，并为每条线标注显著性
    parser.add_argument("--saliency-thresh", type=float, default=0.65,
                        help="显著性阈值，低于该值的线段将被忽略（范围0~1，默认0.65）")

    parser.add_argument("--no-all-lines", dest="no_all_lines", action="store_true", default=False,
                        help="不以绿色绘制所有线段（默认绘制）")
    parser.add_argument("--show-all-lines", dest="no_all_lines", action="store_false",
                        help="绘制所有检测到的线段为绿色（默认）")
    parser.add_argument("--label-saliency", dest="label_saliency", action="store_true", default=True,
                        help="为每条检测线段标注显著性分数（默认）")
    parser.add_argument("--no-label-saliency", dest="label_saliency", action="store_false",
                        help="不标注显著性分数")

    # ROI 默认关闭（-1 表示全图检测）；最多保留2条最近中心线段
    parser.add_argument("--roi-margin", type=int, default=-1, help="中心半径外扩像素；-1 表示全图检测（默认）")
    parser.add_argument("--max-near-lines", type=int, default=2, help="靠近中心线段的最大显示数量（默认2）")

    # 模式：未指定时默认使用 aggressive 参数
    parser.add_argument("--gentle", action="store_true", help="温和模式：降低灵敏度，减少误检")
    parser.add_argument("--aggressive", action="store_true", help="激进模式：提高灵敏度，尽量不漏检（默认）")
    parser.add_argument("--recursive", action="store_true", help="递归扫描子目录（默认关闭）")
    parser.add_argument("--only-aligned", action="store_true", help="仅处理文件名以 _aligned 结尾的图片（默认处理所有）")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    in_dir = Path(args.input_dir) if args.input_dir else script_dir
    # 输出目录：绝对路径则直接使用；相对路径则放在输入目录下
    if args.output_dir:
        out_dir_candidate = Path(args.output_dir)
        out_dir = out_dir_candidate if out_dir_candidate.is_absolute() else in_dir / out_dir_candidate
    else:
        out_dir = in_dir / "output_center_lines"

    # 参数模式选择：gentle/normal/aggressive
    if args.gentle and args.aggressive:
        print("[警告] 同时指定了 --gentle 和 --aggressive，优先使用 --gentle")
    if args.gentle:
        canny1, canny2, hough_thresh, min_len, max_gap = 70, 200, 100, 30, 4
        mode = "gentle"
    elif args.aggressive:
        canny1, canny2, hough_thresh, min_len, max_gap = 30, 90, 20, 8, 12
        mode = "aggressive"
    else:
        # 默认使用 aggressive 参数
        canny1, canny2, hough_thresh, min_len, max_gap = 30, 90, 20, 8, 12
        mode = "aggressive (default)"

    max_near = args.max_near_lines if args.max_near_lines and args.max_near_lines > 0 else None

    # 支持的测试图像后缀
    print(f"递归扫描: {'是' if args.recursive else '否'} | 仅_aligned: {'是' if args.only_aligned else '否'}")

    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    # 构建候选文件列表：支持递归和仅_aligned 过滤
    if args.recursive:
        candidates = (p for p in in_dir.rglob("*") if p.is_file())
    else:
        candidates = (p for p in in_dir.iterdir() if p.is_file())

    img_files = []
    for p in candidates:
        suf = p.suffix.lower()
        if suf not in exts:
            continue
        stem = p.stem
        if stem.endswith("_center_lines"):
            continue
        if args.only_aligned and not stem.endswith("_aligned"):
            continue
        img_files.append(p)

    img_files = sorted(img_files)

    if not img_files:
        print(f"未在目录中找到测试图像: {in_dir}")
        return

    print(f"输入目录: {in_dir}")
    print(f"输出目录: {out_dir}")
    print(f"中心半径阈值: {args.radius} px")
    print(f"模式: {mode} | ROI外扩: {args.roi_margin}px | 最大中心线数: {max_near or '不限'} | 显著性阈值: {args.saliency_thresh:.2f}")

    total_all, total_near = 0, 0
    for p in img_files:
        # 递归模式下：输出目录按文件所在目录决定；
        # - 若 --output-dir 为绝对路径，则在该目录下按相对 in_dir 的层级展开
        # - 若为相对路径或未提供，则在图片所在目录下创建对应子目录
        if args.recursive:
            out_dir_for_file: Path
            out_dir_opt = Path(args.output_dir) if args.output_dir else None
            if out_dir_opt and out_dir_opt.is_absolute():
                try:
                    rel = p.parent.relative_to(in_dir)
                except Exception:
                    rel = Path()
                out_dir_for_file = out_dir_opt / rel
            else:
                out_name = out_dir_opt if out_dir_opt else Path("output_center_lines")
                out_dir_for_file = p.parent / out_name
        else:
            out_dir_for_file = out_dir

        cnt_all, cnt_near = process_one_image(
            p,
            out_dir_for_file,
            args.radius,
            canny1,
            canny2,
            hough_thresh,
            min_len,
            max_gap,
            roi_margin=args.roi_margin,
            max_near_lines=max_near,
            save_all_lines=(not args.no_all_lines),
            label_saliency=args.label_saliency,
            saliency_thresh=args.saliency_thresh,
        )
        total_all += cnt_all
        total_near += cnt_near

    print("\n处理完成:")
    print(f"  图像数: {len(img_files)}")
    print(f"  总检测线段: {total_all}")
    print(f"  总靠近中心线段(≤{args.radius}px): {total_near}")


if __name__ == "__main__":
    main()

