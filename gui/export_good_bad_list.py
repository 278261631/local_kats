"""
Export GOOD/BAD target list with detailed information.

This module provides functionality to export GOOD/BAD labeled targets
to text files with coordinates and file information.
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime
from astropy.io import fits
from astropy.wcs import WCS


def extract_time_from_filename(filename: str) -> str:
    """
    Extract UTC time from filename.

    Filename format: GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_191828_-14.9C_.fits

    Returns:
        Time string like '20250628_191828' or empty string if not found.
    """
    pattern = r'UTC(\d{8}_\d{6})'
    match = re.search(pattern, filename)
    return match.group(1) if match else ""


def get_fits_center_coords(fits_path: str, logger: logging.Logger = None) -> tuple:
    """
    Get center coordinates (RA, DEC) from FITS header.

    Returns:
        tuple: (ra_deg, dec_deg) or (None, None) if not found.
    """
    try:
        with fits.open(fits_path) as hdul:
            header = hdul[0].header

            ra_keys = ['CRVAL1', 'RA', 'OBJCTRA', 'TELRA']
            dec_keys = ['CRVAL2', 'DEC', 'OBJCTDEC', 'TELDEC']

            ra_val = None
            dec_val = None

            for key in ra_keys:
                if key in header:
                    ra_val = header[key]
                    break

            for key in dec_keys:
                if key in header:
                    dec_val = header[key]
                    break

            if ra_val is not None and dec_val is not None:
                if isinstance(ra_val, str):
                    from astropy.coordinates import Angle
                    import astropy.units as u
                    ra_val = Angle(ra_val, unit=u.hourangle).degree

                if isinstance(dec_val, str):
                    from astropy.coordinates import Angle
                    import astropy.units as u
                    dec_val = Angle(dec_val, unit=u.degree).degree

                return float(ra_val), float(dec_val)
    except Exception as e:
        if logger:
            logger.warning(f"Failed to get FITS center coords: {e}")

    return None, None


def extract_pixel_coords_from_cutout(detection_img: str) -> tuple:
    """
    Extract pixel coordinates from cutout filename.

    Filename format: 001_X1234_Y5678_...

    Returns:
        tuple: (pixel_x, pixel_y) or (None, None) if not found.
    """
    basename = os.path.basename(detection_img)
    xy_match = re.search(r'X(\d+)_Y(\d+)', basename)
    if xy_match:
        return float(xy_match.group(1)), float(xy_match.group(2))
    return None, None


def pixel_to_radec(pixel_x: float, pixel_y: float, fits_path: str,
                   logger: logging.Logger = None) -> tuple:
    """
    Convert pixel coordinates to RA/DEC using WCS.

    Returns:
        tuple: (ra_deg, dec_deg) or (None, None) if conversion fails.
    """
    try:
        with fits.open(fits_path) as hdul:
            header = hdul[0].header
            wcs = WCS(header)
            sky_coords = wcs.pixel_to_world(pixel_x, pixel_y)
            return sky_coords.ra.degree, sky_coords.dec.degree
    except Exception as e:
        if logger:
            logger.warning(f"WCS conversion failed: {e}")
    return None, None


def find_aligned_fits(cutout_set: dict, logger: logging.Logger = None) -> str:
    """
    Find the aligned FITS file path from cutout set.

    Returns:
        Path to aligned FITS file or None if not found.
    """
    aligned_img = cutout_set.get('aligned')
    if not aligned_img:
        return None

    cutout_dir = Path(aligned_img).parent
    detection_dir = cutout_dir.parent

    # Look for aligned FITS in detection directory
    for pattern in ['*_aligned.fits', '*_aligned.fit', '*aligned*.fits']:
        fits_files = list(detection_dir.glob(pattern))
        if fits_files:
            return str(fits_files[0])

    # Try parent directories
    for parent in [detection_dir.parent, detection_dir.parent.parent]:
        for pattern in ['*_aligned.fits', '*_aligned.fit', '*noise_cleaned_aligned*.fits']:
            fits_files = list(parent.glob(pattern))
            if fits_files:
                return str(fits_files[0])

    return None


def extract_date_region_from_path(file_path: str) -> tuple:
    """
    Extract date and region from file path.

    Path format: .../output/GY2/20260126/K026/...

    Returns:
        tuple: (date_str, region_str) like ('20260126', 'K026')
    """
    parts = Path(file_path).parts
    date_str = ""
    region_str = ""

    for i, part in enumerate(parts):
        # Match date format YYYYMMDD
        if re.match(r'^\d{8}$', part):
            date_str = part
            if i + 1 < len(parts):
                region_str = parts[i + 1]
            break

    return date_str, region_str



class GoodBadListExporter:
    """
    Exporter for GOOD/BAD target list with detailed information.
    """

    def __init__(self, viewer, logger: logging.Logger = None):
        """
        Initialize exporter.

        Args:
            viewer: FITSViewer instance
            logger: Logger instance
        """
        self.viewer = viewer
        self.logger = logger or logging.getLogger(__name__)

    def export(self):
        """
        Export GOOD/BAD target list to text files.

        Export format:
        - Output directory: {output_root}/good_bad_list/{date}{region}/
        - File names: good-{time}.txt, bad-{time}.txt
        - Content: index, file_dir, aligned_filename, fits_center, time, pixel_xy, ra_dec
        """
        from tkinter import messagebox

        try:
            # 1. Get directory tree selection
            selection = self.viewer.directory_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a directory or file first")
                return

            root_node = selection[0]
            root_tags = self.viewer.directory_tree.item(root_node, "tags")
            root_values = self.viewer.directory_tree.item(root_node, "values")

            if not root_values and "fits_file" not in root_tags:
                messagebox.showwarning("Warning", "Please select a directory with FITS files")
                return

            # 2. Collect all FITS file nodes
            file_nodes = []
            self._collect_file_nodes(root_node, file_nodes)

            if not file_nodes:
                messagebox.showinfo("Info", "No FITS files found in selected directory")
                return

            # 3. Process files and collect GOOD/BAD targets
            good_records = []
            bad_records = []
            date_region_set = set()

            self.logger.info("=" * 60)
            self.logger.info(f"Starting GOOD/BAD list export: {len(file_nodes)} files")

            for file_node in file_nodes:
                self._process_file_node(file_node, good_records, bad_records, date_region_set)

            if not good_records and not bad_records:
                messagebox.showinfo("Info", "No GOOD/BAD labeled targets found")
                return

            # 4. Determine output directory
            output_dir = self._get_output_directory(date_region_set)
            if not output_dir:
                messagebox.showerror("Error", "Cannot determine output directory")
                return

            os.makedirs(output_dir, exist_ok=True)

            # 5. Write output files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            good_count = self._write_records(output_dir, "good", timestamp, good_records)
            bad_count = self._write_records(output_dir, "bad", timestamp, bad_records)

            # 6. Show result
            msg = (
                f"Export completed!\n\n"
                f"GOOD records: {good_count}\n"
                f"BAD records: {bad_count}\n\n"
                f"Output directory:\n{output_dir}"
            )
            messagebox.showinfo("Export GOOD/BAD List", msg)
            self.logger.info(f"Export completed: GOOD={good_count}, BAD={bad_count}")

        except Exception as e:
            err = f"Export failed: {str(e)}"
            self.logger.error(err, exc_info=True)
            messagebox.showerror("Error", err)


    def _collect_file_nodes(self, node, file_nodes: list):
        """Recursively collect FITS file nodes."""
        tags = self.viewer.directory_tree.item(node, "tags")

        if "fits_file" in tags:
            file_nodes.append(node)
        else:
            for child in self.viewer.directory_tree.get_children(node):
                self._collect_file_nodes(child, file_nodes)

    def _process_file_node(self, file_node, good_records: list, bad_records: list,
                           date_region_set: set):
        """Process a single file node and extract GOOD/BAD targets."""
        try:
            values = self.viewer.directory_tree.item(file_node, "values")
            if not values:
                return

            file_path = values[0]
            if not os.path.isfile(file_path):
                return

            region_dir = os.path.dirname(file_path)

            # Load diff results for this file
            if not self.viewer._load_diff_results_for_file(file_path, region_dir):
                return

            if not hasattr(self.viewer, "_all_cutout_sets") or not self.viewer._all_cutout_sets:
                return

            # Extract date and region
            date_str, region_str = extract_date_region_from_path(file_path)
            if date_str and region_str:
                date_region_set.add((date_str, region_str))

            # Get FITS center coordinates
            fits_center_ra, fits_center_dec = get_fits_center_coords(file_path, self.logger)

            for cutout_set in self.viewer._all_cutout_sets:
                label = (cutout_set or {}).get("manual_label")
                if not label:
                    continue

                label_lower = str(label).lower()
                if label_lower not in ("good", "bad"):
                    continue

                record = self._build_record(
                    file_path, cutout_set, fits_center_ra, fits_center_dec
                )

                if record:
                    if label_lower == "good":
                        good_records.append(record)
                    else:
                        bad_records.append(record)

        except Exception as e:
            self.logger.error(f"Error processing file node: {e}", exc_info=True)

    def _build_record(self, file_path: str, cutout_set: dict,
                      fits_center_ra, fits_center_dec) -> dict:
        """Build a record dict for export."""
        try:
            aligned_img = cutout_set.get('aligned')
            detection_img = cutout_set.get('detection')

            if not aligned_img or not detection_img:
                return None

            # Find aligned FITS file (e.g. *_noise_cleaned_aligned.fits)
            aligned_fits = find_aligned_fits(cutout_set, self.logger)

            # File directory and aligned filename from aligned FITS
            if aligned_fits:
                file_dir = os.path.dirname(aligned_fits)
                aligned_filename = os.path.basename(aligned_fits)
            else:
                file_dir = os.path.dirname(file_path)
                aligned_filename = ""

            # Extract time from aligned filename or original file path
            time_str = extract_time_from_filename(aligned_filename)
            if not time_str:
                time_str = extract_time_from_filename(os.path.basename(file_path))

            # Get pixel coordinates
            pixel_x, pixel_y = extract_pixel_coords_from_cutout(detection_img)

            # Get RA/DEC for target
            ra_deg, dec_deg = None, None
            if pixel_x is not None and pixel_y is not None and aligned_fits:
                ra_deg, dec_deg = pixel_to_radec(pixel_x, pixel_y, aligned_fits, self.logger)

            return {
                'file_dir': file_dir,
                'aligned_filename': aligned_filename,
                'fits_center_ra': fits_center_ra,
                'fits_center_dec': fits_center_dec,
                'time_str': time_str,
                'pixel_x': pixel_x,
                'pixel_y': pixel_y,
                'ra_deg': ra_deg,
                'dec_deg': dec_deg,
            }
        except Exception as e:
            self.logger.warning(f"Failed to build record: {e}")
            return None

    def _get_output_directory(self, date_region_set: set) -> str:
        """Determine output directory based on date and region."""
        try:
            # Get diff output directory from config
            if hasattr(self.viewer, 'config_manager') and self.viewer.config_manager:
                last_selected = self.viewer.config_manager.get_last_selected() or {}
                diff_output_dir = last_selected.get("diff_output_directory", "").strip()

                if not diff_output_dir:
                    # Try to get from current file path
                    if hasattr(self.viewer, 'selected_file_path') and self.viewer.selected_file_path:
                        parts = Path(self.viewer.selected_file_path).parts
                        for i, part in enumerate(parts):
                            if 'diff' in part.lower() or 'output' in part.lower():
                                diff_output_dir = str(Path(*parts[:i+1]))
                                break

                if diff_output_dir:
                    # Build subdirectory name from date and region
                    if date_region_set:
                        date_str, region_str = next(iter(date_region_set))
                        subdir = f"{date_str}{region_str}"
                    else:
                        subdir = datetime.now().strftime("%Y%m%d")

                    return os.path.join(diff_output_dir, "good_bad_list", subdir)

            return None
        except Exception as e:
            self.logger.error(f"Failed to get output directory: {e}")
            return None

    def _write_records(self, output_dir: str, label: str, timestamp: str,
                       records: list) -> int:
        """Write records to file."""
        if not records:
            return 0

        filename = f"{label}-{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Write header
                f.write("# GOOD/BAD Target List Export\n")
                f.write(f"# Label: {label.upper()}\n")
                f.write(f"# Export Time: {timestamp}\n")
                f.write(f"# Total Records: {len(records)}\n")
                f.write("#" + "=" * 79 + "\n")
                f.write("# Format: index file_dir aligned_filename ")
                f.write("fits_center_ra fits_center_dec time pixel_x pixel_y ra dec\n")
                f.write("#" + "=" * 79 + "\n\n")

                for idx, rec in enumerate(records, 1):
                    line = self._format_record(idx, rec)
                    f.write(line + "\n")

            self.logger.info(f"Written {len(records)} records to {filepath}")
            return len(records)

        except Exception as e:
            self.logger.error(f"Failed to write records: {e}")
            return 0

    def _format_record(self, idx: int, rec: dict) -> str:
        """Format a single record as a line."""
        def fmt_coord(val):
            return f"{val:.6f}" if val is not None else "N/A"

        def fmt_pixel(val):
            return f"{int(val)}" if val is not None else "N/A"

        parts = [
            f"{idx:04d}",
            rec.get('file_dir', 'N/A'),
            rec.get('aligned_filename', 'N/A'),
            fmt_coord(rec.get('fits_center_ra')),
            fmt_coord(rec.get('fits_center_dec')),
            rec.get('time_str', 'N/A'),
            fmt_pixel(rec.get('pixel_x')),
            fmt_pixel(rec.get('pixel_y')),
            fmt_coord(rec.get('ra_deg')),
            fmt_coord(rec.get('dec_deg')),
        ]

        return " ".join(parts)
