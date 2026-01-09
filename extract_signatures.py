import os
import argparse
import cv2
import numpy as np


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def extract_signatures(
    image_path: str,
    out_dir: str,
    min_area: int = 2500,
    pad: int = 20,
    remove_lines: bool = True,
    debug: bool = False,
) -> int:
    ensure_dir(out_dir)

    # Load image
    img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    # Convert to RGB for better color handling
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Enhanced preprocessing: better denoising while preserving edges
    gray_blur = cv2.bilateralFilter(gray, 9, 75, 75)  # Better edge preservation than Gaussian
    
    # Use adaptive threshold with optimized parameters for signature detection
    # Smaller block size and lower C value to capture more ink details
    thresh_adaptive = cv2.adaptiveThreshold(
        gray_blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,   # Smaller block size for better detail on signatures
        5,    # Lower C value to capture lighter ink strokes
    )
    
    # Also try Otsu's threshold for uniform areas
    _, thresh_otsu = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Combine both methods - adaptive is primary, Otsu fills gaps
    thr = cv2.bitwise_or(thresh_adaptive, thresh_otsu)
    
    # Clean up small noise while preserving signature strokes
    kernel_noise = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel_noise, iterations=1)

    # Optional: remove horizontal/vertical lines (forms, underlines)
    if remove_lines:
        h = thr.shape[0]
        w = thr.shape[1]

        # Horizontal lines
        horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // 40), 1))
        detect_h = cv2.morphologyEx(thr, cv2.MORPH_OPEN, horiz_kernel, iterations=1)

        # Vertical lines
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, h // 40)))
        detect_v = cv2.morphologyEx(thr, cv2.MORPH_OPEN, vert_kernel, iterations=1)

        lines = cv2.bitwise_or(detect_h, detect_v)
        thr = cv2.bitwise_and(thr, cv2.bitwise_not(lines))

    # Connect signature strokes a bit (helps prevent splitting)
    # Use slightly larger kernel to better connect signature parts
    connect_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
    thr_connected = cv2.dilate(thr, connect_kernel, iterations=2)  # More iterations to connect better

    # Find connected components (each candidate signature)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thr_connected, connectivity=8)

    # stats: [label, x, y, w, h, area] for each component; label 0 is background
    candidates = []
    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]
        if area < min_area:
            continue

        # Heuristics: signatures are usually wide-ish and not tiny blocks
        # More strict criteria to avoid combining multiple signatures
        aspect = w / float(h + 1e-6)
        
        # Filter out very tall narrow components (likely vertical lines or noise)
        if h > w * 3 and w < 100:
            continue
            
        # Filter out very wide short components (likely horizontal lines)
        if w > h * 5 and h < 30:
            continue
        
        # Keep signatures that are reasonably proportioned
        if aspect < 0.5 and w < 100:  # Too narrow and small
            continue

        candidates.append((label, x, y, w, h, area))

    # If nothing found, fallback to contours on thr (more permissive)
    if not candidates:
        contours, _ = cv2.findContours(thr_connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < min_area:
                continue
            candidates.append((-1, x, y, w, h, area))

    # Sort largest first (often main signatures)
    candidates.sort(key=lambda t: t[-1], reverse=True)

    if debug:
        dbg = img_bgr.copy()
        for _, x, y, w, h, _ in candidates:
            cv2.rectangle(dbg, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imwrite(os.path.join(out_dir, "_debug_boxes.png"), dbg)
        cv2.imwrite(os.path.join(out_dir, "_debug_mask.png"), thr_connected)

    saved = 0
    H, W = gray.shape[:2]

    for i, (_, x, y, w, h, _) in enumerate(candidates, start=1):
        # Pad crop with very generous padding to prevent cut-offs
        # Use much larger padding for vertical direction to catch full signatures including flourishes
        pad_x = pad * 1.5  # Horizontal padding
        pad_y = pad * 3  # Much more vertical padding for tall letters and flourishes
        x0 = max(0, int(x - pad_x))
        y0 = max(0, int(y - pad_y))
        x1 = min(W, int(x + w + pad_x))
        y1 = min(H, int(y + h + pad_y))

        # Extract color crop (preserve original colors)
        crop_rgb = img_rgb[y0:y1, x0:x1]
        crop_gray = gray[y0:y1, x0:x1]
        
        # Create a better mask using multiple methods for best quality
        crop_gray_local = crop_gray.copy()
        
        # CRITICAL: Remove horizontal lines from the crop FIRST before creating mask
        # This prevents lines from appearing in the final signature
        h_crop, w_crop = crop_gray_local.shape
        if h_crop > 20 and w_crop > 20:  # Only if crop is large enough
            # Detect horizontal lines more aggressively
            # Use a wider kernel to catch lines that span most of the width
            horiz_kernel_crop = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, int(w_crop * 0.7)), 1))
            
            # Detect lines using morphological operations (more iterations for better detection)
            detect_h_crop = cv2.morphologyEx(crop_gray_local, cv2.MORPH_OPEN, horiz_kernel_crop, iterations=3)
            
            # Create a binary mask of detected lines
            # Lines are usually uniform in brightness, so use variance to detect them
            line_threshold = np.mean(crop_gray_local) + 5  # Lower threshold to catch more lines
            _, lines_mask = cv2.threshold(detect_h_crop, line_threshold, 255, cv2.THRESH_BINARY)
            
            # Dilate the line mask more to ensure we catch the full width of lines
            line_dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
            lines_mask = cv2.dilate(lines_mask, line_dilate_kernel, iterations=2)
            
            # Get background color (use a more robust method)
            # Sample from corners and edges where lines are less likely
            corner_samples = np.concatenate([
                crop_gray_local[:h_crop//10, :].flatten(),
                crop_gray_local[-h_crop//10:, :].flatten(),
                crop_gray_local[:, :w_crop//10].flatten(),
                crop_gray_local[:, -w_crop//10:].flatten()
            ])
            if len(corner_samples) > 0:
                bg_color = int(np.median(corner_samples))
            else:
                bg_color = 255  # Default to white
            
            # Replace lines with background color in grayscale
            crop_gray_local[lines_mask > 128] = bg_color
            
            # Replace lines with background color in RGB (make it white/light)
            crop_rgb_clean = crop_rgb.copy()
            bg_rgb = [bg_color, bg_color, bg_color]
            crop_rgb_clean[lines_mask > 128] = bg_rgb
            crop_rgb = crop_rgb_clean
        
        # Method 1: Local adaptive threshold (good for uniform backgrounds)
        crop_mask_adaptive = cv2.adaptiveThreshold(
            crop_gray_local,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            9,   # Small block for fine detail
            3,   # Low C to capture all ink
        )
        
        # Method 2: Color-based extraction (better for colored ink like blue)
        # Convert to LAB color space for better color separation
        crop_lab = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2LAB)
        l_channel = crop_lab[:, :, 0]  # Lightness channel
        
        # Threshold on lightness - ink is darker than background
        _, crop_mask_lightness = cv2.threshold(
            l_channel, 
            0, 
            255, 
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        
        # Method 3: Color distance from white/light background
        # Calculate distance from white (255, 255, 255)
        white = np.array([255, 255, 255], dtype=np.float32)
        crop_float = crop_rgb.astype(np.float32)
        color_dist = np.sqrt(np.sum((crop_float - white) ** 2, axis=2))
        # Normalize and threshold
        if np.max(color_dist) > 0:
            color_dist_norm = (color_dist / np.max(color_dist) * 255).astype(np.uint8)
        else:
            color_dist_norm = np.zeros_like(color_dist, dtype=np.uint8)
        _, crop_mask_color = cv2.threshold(
            color_dist_norm,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        # Combine all methods - use union to catch all ink
        crop_mask_combined = cv2.bitwise_or(crop_mask_adaptive, crop_mask_lightness)
        crop_mask_combined = cv2.bitwise_or(crop_mask_combined, crop_mask_color)
        
        # CRITICAL: Remove any remaining horizontal lines from the mask
        # This is a second pass to catch any lines that made it through
        if h_crop > 20 and w_crop > 20:
            # More aggressive line detection in the mask
            horiz_kernel_mask = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, int(w_crop * 0.5)), 1))
            lines_in_mask = cv2.morphologyEx(crop_mask_combined, cv2.MORPH_OPEN, horiz_kernel_mask, iterations=2)
            
            # Dilate to ensure full line removal
            line_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
            lines_in_mask = cv2.dilate(lines_in_mask, line_dilate, iterations=1)
            
            # Remove detected lines from mask
            crop_mask_combined = cv2.bitwise_and(crop_mask_combined, cv2.bitwise_not(lines_in_mask))
        
        # Refine the mask: remove small noise and dots, smooth edges
        # First, remove very small isolated components (dots/noise)
        num_labels_mask, labels_mask, stats_mask, _ = cv2.connectedComponentsWithStats(crop_mask_combined, connectivity=8)
        
        # Calculate adaptive minimum area based on crop size
        # Be more aggressive in removing small dots
        crop_area = h_crop * w_crop
        min_component_area = max(50, int(crop_area * 0.002))  # At least 0.2% of crop area, minimum 50 pixels
        
        crop_mask_clean = np.zeros_like(crop_mask_combined)
        
        for label in range(1, num_labels_mask):
            area = stats_mask[label, cv2.CC_STAT_AREA]
            x_comp, y_comp, w_comp, h_comp = stats_mask[label, cv2.CC_STAT_LEFT], stats_mask[label, cv2.CC_STAT_TOP], stats_mask[label, cv2.CC_STAT_WIDTH], stats_mask[label, cv2.CC_STAT_HEIGHT]
            
            # Keep component if:
            # 1. It's large enough, OR
            # 2. It's part of a signature (tall enough or wide enough relative to crop)
            # Be more strict - signature parts should be substantial
            is_signature_part = (h_comp > h_crop * 0.15) or (w_comp > w_crop * 0.2)  # Signature parts are relatively large
            if area >= min_component_area or is_signature_part:
                crop_mask_clean[labels_mask == label] = 255
        
        # Then smooth edges with morphology
        kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        crop_mask_clean = cv2.morphologyEx(crop_mask_clean, cv2.MORPH_CLOSE, kernel_clean, iterations=1)
        crop_mask_clean = cv2.morphologyEx(crop_mask_clean, cv2.MORPH_OPEN, kernel_clean, iterations=1)
        
        # Create RGBA image preserving original signature colors
        rgba = np.zeros((crop_rgb.shape[0], crop_rgb.shape[1], 4), dtype=np.uint8)
        
        # Use the clean mask as alpha channel
        alpha = crop_mask_clean
        
        # For pixels with ink (alpha > 0), use original RGB colors
        # This preserves black, blue, or any other ink color from the original
        ink_pixels = alpha > 0
        
        # Copy RGB values where there's ink, preserving original colors
        rgba[..., 0] = np.where(ink_pixels, crop_rgb[..., 0], 0)  # R
        rgba[..., 1] = np.where(ink_pixels, crop_rgb[..., 1], 0)  # G
        rgba[..., 2] = np.where(ink_pixels, crop_rgb[..., 2], 0)  # B
        rgba[..., 3] = alpha  # Alpha channel (transparent background)
        
        # FINAL CLEANUP: Remove any remaining horizontal lines and small dots from the final image
        if h_crop > 20 and w_crop > 20:
            # Detect horizontal lines in the alpha channel
            alpha_gray = alpha.astype(np.uint8)
            horiz_final = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, int(w_crop * 0.6)), 1))
            lines_final = cv2.morphologyEx(alpha_gray, cv2.MORPH_OPEN, horiz_final, iterations=2)
            
            # Only remove if it's clearly a line (high confidence)
            _, lines_final_binary = cv2.threshold(lines_final, 200, 255, cv2.THRESH_BINARY)
            
            # Remove small isolated dots/noise (connected components that are too small)
            num_labels_final, labels_final, stats_final, _ = cv2.connectedComponentsWithStats(alpha_gray, connectivity=8)
            
            # Adaptive minimum area based on crop size
            crop_area_final = h_crop * w_crop
            min_signature_area = max(80, int(crop_area_final * 0.0015))  # At least 0.15% of crop area, minimum 80 pixels
            
            # Create a clean alpha mask
            alpha_clean = np.zeros_like(alpha_gray)
            for label in range(1, num_labels_final):
                area = stats_final[label, cv2.CC_STAT_AREA]
                x_comp, y_comp, w_comp, h_comp = stats_final[label, cv2.CC_STAT_LEFT], stats_final[label, cv2.CC_STAT_TOP], stats_final[label, cv2.CC_STAT_WIDTH], stats_final[label, cv2.CC_STAT_HEIGHT]
                
                component_mask = (labels_final == label)
                
                # Check if this component overlaps with detected lines
                line_overlap = np.sum(lines_final_binary[component_mask])
                line_overlap_ratio = line_overlap / area if area > 0 else 0
                
                # Keep component if:
                # 1. It's large enough AND not mostly a line, OR
                # 2. It's part of a signature (tall/wide enough) AND not mostly a line
                is_signature_part = (h_comp > h_crop * 0.12) or (w_comp > w_crop * 0.2)
                if (area >= min_signature_area or is_signature_part) and line_overlap_ratio < 0.5:
                    alpha_clean[component_mask] = alpha_gray[component_mask]
            
            # Update alpha and RGB channels
            alpha = alpha_clean
            rgba[..., 3] = alpha
            
            # Remove RGB data where alpha is now 0
            rgba[alpha == 0, 0] = 0
            rgba[alpha == 0, 1] = 0
            rgba[alpha == 0, 2] = 0
        
        # Preserve original appearance - no aggressive enhancement
        # The original colors are already preserved in the rgba image above
        # Only ensure alpha channel is correct for transparency

        out_path = os.path.join(out_dir, f"signature_{i:02d}.png")
        # OpenCV imwrite expects BGR, but we have RGB, so convert
        rgba_bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        cv2.imwrite(out_path, rgba_bgr)
        saved += 1

    return saved


def main():
    p = argparse.ArgumentParser(description="Extract signatures from a scanned document image.")
    p.add_argument("image", help="Path to scanned image (PNG/JPG).")
    p.add_argument("--out", default="signatures_out", help="Output folder.")
    p.add_argument("--min-area", type=int, default=2500, help="Minimum blob area to keep.")
    p.add_argument("--pad", type=int, default=20, help="Padding around each signature crop.")
    p.add_argument("--keep-lines", action="store_true", help="Do not attempt to remove lines.")
    p.add_argument("--debug", action="store_true", help="Write debug images with boxes/masks.")
    args = p.parse_args()

    count = extract_signatures(
        image_path=args.image,
        out_dir=args.out,
        min_area=args.min_area,
        pad=args.pad,
        remove_lines=not args.keep_lines,
        debug=args.debug,
    )

    print(f"Saved {count} signature(s) to: {args.out}")


if __name__ == "__main__":
    main()
