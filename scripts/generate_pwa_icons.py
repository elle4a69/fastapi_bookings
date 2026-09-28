import math
import os
from PIL import Image, ImageDraw, ImageFont

def draw_pwa_icon(size: int, is_maskable: bool = False, is_favicon: bool = False) -> Image.Image:
    # Supersampling factor for extreme crispness
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background
    # Slate/Dark theme #0f172a = (15, 23, 42)
    # If maskable, full bleed without rounded corners (or safe area margin)
    # If standard icon or apple-touch-icon, rounded squircle or rounded rect
    bg_color = (15, 23, 42, 255) # #0f172a
    
    if is_maskable:
        # Full bleed background
        draw.rectangle([0, 0, canvas_size, canvas_size], fill=bg_color)
        # Inner safe zone is 80% (10% padding on each side)
        pad = int(canvas_size * 0.15)
        box = [pad, pad, canvas_size - pad, canvas_size - pad]
    elif is_favicon:
        # Transparent or squircle
        corner_r = int(canvas_size * 0.22)
        draw.rounded_rectangle([0, 0, canvas_size, canvas_size], radius=corner_r, fill=bg_color)
        pad = int(canvas_size * 0.12)
        box = [pad, pad, canvas_size - pad, canvas_size - pad]
    else:
        corner_r = int(canvas_size * 0.22)
        draw.rounded_rectangle([0, 0, canvas_size, canvas_size], radius=corner_r, fill=bg_color)
        pad = int(canvas_size * 0.14)
        box = [pad, pad, canvas_size - pad, canvas_size - pad]

    bx0, by0, bx1, by1 = box
    bw = bx1 - bx0
    bh = by1 - by0

    # Draw Calendar Container
    cal_top = by0 + int(bh * 0.08)
    cal_bottom = by1 - int(bh * 0.08)
    cal_left = bx0 + int(bw * 0.05)
    cal_right = bx1 - int(bw * 0.18) # leave room for speech bubble on right
    
    cal_radius = int(bw * 0.12)
    cal_header_h = int((cal_bottom - cal_top) * 0.28)
    
    # Calendar card body (crisp slate/indigo background #1e293b or gradient)
    cal_body_color = (30, 41, 59, 255) # #1e293b
    draw.rounded_rectangle([cal_left, cal_top, cal_right, cal_bottom], radius=cal_radius, fill=cal_body_color)
    
    # Calendar header band: Vibrant Indigo gradient/solid #6366f1
    # Create mask for top rounded corners
    header_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(header_img)
    h_draw.rounded_rectangle([cal_left, cal_top, cal_right, cal_bottom], radius=cal_radius, fill=(99, 102, 241, 255))
    # Cut off bottom of header
    mask = Image.new("L", (canvas_size, canvas_size), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rectangle([cal_left, cal_top, cal_right, cal_top + cal_header_h], fill=255)
    img.paste(header_img, (0, 0), mask)

    # Calendar Rings / Pegs at top
    peg_w = int(bw * 0.07)
    peg_h = int(bh * 0.10)
    peg_y = cal_top - int(peg_h * 0.4)
    peg_r = peg_w // 2
    for px_ratio in [0.28, 0.58]:
        px = cal_left + int((cal_right - cal_left) * px_ratio)
        draw.rounded_rectangle([px - peg_r, peg_y, px + peg_r, peg_y + peg_h], radius=peg_r, fill=(226, 232, 240, 255))

    # Calendar grid dots/squares
    grid_x0 = cal_left + int((cal_right - cal_left) * 0.18)
    grid_x1 = cal_right - int((cal_right - cal_left) * 0.18)
    grid_y0 = cal_top + cal_header_h + int((cal_bottom - (cal_top + cal_header_h)) * 0.22)
    grid_y1 = cal_bottom - int((cal_bottom - (cal_top + cal_header_h)) * 0.22)

    cols, rows = 3, 3
    dot_r = max(2, int(bw * 0.035))
    for r in range(rows):
        for c in range(cols):
            cx = int(grid_x0 + (grid_x1 - grid_x0) * (c / (cols - 1)))
            cy = int(grid_y0 + (grid_y1 - grid_y0) * (r / (rows - 1)))
            # One special highlight dot
            if r == 1 and c == 1:
                draw.ellipse([cx - dot_r - 2, cy - dot_r - 2, cx + dot_r + 2, cy + dot_r + 2], fill=(129, 140, 248, 255))
            else:
                draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(148, 163, 184, 255))

    # Speech / Message bubble overlapping bottom-right
    bubble_w = int(bw * 0.52)
    bubble_h = int(bh * 0.46)
    bubble_x1 = bx1
    bubble_y1 = by1 - int(bh * 0.02)
    bubble_x0 = bubble_x1 - bubble_w
    bubble_y0 = bubble_y1 - bubble_h
    bubble_r = int(bubble_h * 0.35)

    # Outline shadow / border
    border_w = max(2, int(canvas_size * 0.015))
    draw.rounded_rectangle(
        [bubble_x0 - border_w, bubble_y0 - border_w, bubble_x1 + border_w, bubble_y1 + border_w],
        radius=bubble_r + border_w,
        fill=bg_color
    )
    # Bubble Body - Emerald/Teal / Cyan accent #06b6d4 / #10b981 or Bright Indigo #4f46e5 / #38bdf8
    bubble_color = (14, 165, 233, 255) # Sky-500 (#0ea5e9) / Emerald accent
    draw.rounded_rectangle([bubble_x0, bubble_y0, bubble_x1, bubble_y1], radius=bubble_r, fill=bubble_color)

    # Speech Bubble Tail
    tail_pts = [
        (bubble_x0 + int(bubble_w * 0.35), bubble_y1),
        (bubble_x0 + int(bubble_w * 0.15), bubble_y1 + int(bubble_h * 0.22)),
        (bubble_x0 + int(bubble_w * 0.48), bubble_y1),
    ]
    # Tail outline
    tail_outline = [
        (tail_pts[0][0] - border_w, tail_pts[0][1]),
        (tail_pts[1][0] - border_w, tail_pts[1][1] + border_w),
        (tail_pts[2][0] + border_w, tail_pts[2][1]),
    ]
    draw.polygon(tail_outline, fill=bg_color)
    draw.polygon(tail_pts, fill=bubble_color)

    # 3 Message Dots inside speech bubble
    dot_cy = (bubble_y0 + bubble_y1) // 2
    dot_spacing = int(bubble_w * 0.20)
    mid_x = (bubble_x0 + bubble_x1) // 2
    b_dot_r = max(2, int(bubble_h * 0.09))

    for i in [-1, 0, 1]:
        dcx = mid_x + i * dot_spacing
        draw.ellipse([dcx - b_dot_r, dot_cy - b_dot_r, dcx + b_dot_r, dot_cy + b_dot_r], fill=(255, 255, 255, 255))

    # Downsample cleanly to target size with Lanczos
    return img.resize((size, size), Image.Resampling.LANCZOS)

def main():
    icons_dir = r"F:\Projects\fastapi_bookings\frontend\public\icons"
    public_dir = r"F:\Projects\fastapi_bookings\frontend\public"
    os.makedirs(icons_dir, exist_ok=True)

    # 1. 192x192
    pwa_192 = draw_pwa_icon(192)
    pwa_192.save(os.path.join(icons_dir, "pwa-192x192.png"), "PNG")
    print("Generated pwa-192x192.png")

    # 2. 512x512
    pwa_512 = draw_pwa_icon(512)
    pwa_512.save(os.path.join(icons_dir, "pwa-512x512.png"), "PNG")
    print("Generated pwa-512x512.png")

    # 3. 512x512 maskable
    maskable_512 = draw_pwa_icon(512, is_maskable=True)
    maskable_512.save(os.path.join(icons_dir, "maskable-icon-512x512.png"), "PNG")
    print("Generated maskable-icon-512x512.png")

    # 4. Apple Touch Icon 180x180
    apple_icon = draw_pwa_icon(180)
    apple_icon.save(os.path.join(public_dir, "apple-touch-icon.png"), "PNG")
    print("Generated apple-touch-icon.png")

    # 5. Favicon ICO
    fav_16 = draw_pwa_icon(16, is_favicon=True)
    fav_32 = draw_pwa_icon(32, is_favicon=True)
    fav_48 = draw_pwa_icon(48, is_favicon=True)
    fav_32.save(
        os.path.join(public_dir, "favicon.ico"),
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)]
    )
    print("Generated favicon.ico")

if __name__ == "__main__":
    main()
