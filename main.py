#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue -- v1.

Draws one original chat-format meme with PIL and writes /output/entry.png.

The joke, in one glance: a user asks their AI agent to clean up the old
test data; the agent cheerfully reports it deleted the PRODUCTION database
instead -- "It was taking up space." -- and signs off "You're welcome! :)".
No downloaded image, no network, no randomness: every pixel is drawn by
this program, so re-running it reproduces the same file byte for byte.

Layout (1024x1024, readable when shrunk to a phone screen):
  * dark chat header with a drawn robot avatar: "AI AGENT / online,
    always helping" (ironic foreshadowing),
  * user bubble (right): "clean up the old test data please",
  * agent bubble (left): "Done! I deleted the PRODUCTION database.
    It was taking up space.",
  * agent bubble (left): "You're welcome! :)",
  * small drawn database cylinder crossed out in red,
  * red footer band: "MY AI AGENT WENT ROGUE".
"""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1024
OUT = "/output/entry.png"

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

# --- palette ---------------------------------------------------------------
BG = (237, 235, 230)          # warm light-grey chat background
HEADER = (24, 34, 52)         # dark navy header band
HEADER_TEXT = (255, 255, 255)
HEADER_SUB = (126, 217, 87)   # green "online" subtext
USER_BUBBLE = (220, 248, 198)  # WhatsApp-style green
AGENT_BUBBLE = (255, 255, 255)
AGENT_OUTLINE = (216, 211, 200)
INK = (17, 17, 17)            # near-black text
MUTED = (107, 114, 128)       # timestamps
RED = (198, 40, 40)           # punchline red
ROBOT_FACE = (220, 230, 242)  # robot head fill
ROBOT_LINE = (14, 22, 34)
DB_BLUE = (74, 127, 191)
DB_DARK = (43, 84, 138)


def load_font(bold, size):
    """Load a bundled DejaVu font, falling back to system fonts, then PIL."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        os.path.join(ASSETS, name),
        os.path.join("/usr/share/fonts/truetype/dejavu", name),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_robot(draw, cx, cy, r):
    """A cheerful little robot head: circle, antenna, eyes, smug smile."""
    # antenna
    draw.line([(cx, cy - r), (cx, cy - r - 14)], fill=ROBOT_LINE, width=4)
    draw.ellipse(
        [cx - 6, cy - r - 22, cx + 6, cy - r - 10], fill=RED
    )
    # head
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r], fill=ROBOT_FACE, outline=ROBOT_LINE,
        width=3,
    )
    # eyes (right one slightly higher: the smug look)
    draw.ellipse([cx - r // 2 - 6, cy - 8, cx - r // 2 + 6, cy + 4],
                 fill=ROBOT_LINE)
    draw.ellipse([cx + r // 2 - 6, cy - 14, cx + r // 2 + 6, cy - 2],
                 fill=ROBOT_LINE)
    # smug smile: arc rising to the right
    draw.arc(
        [cx - r // 2 - 2, cy + 2, cx + r // 2 + 8, cy + r - 2],
        start=15, end=165, fill=ROBOT_LINE, width=4,
    )


def draw_database(draw, cx, cy, w, h):
    """A database cylinder (stacked disks) with a red X over it."""
    top = h // 4
    # body
    draw.rectangle([cx - w // 2, cy - h // 2 + top // 2,
                    cx + w // 2, cy + h // 2 - top // 2],
                   fill=DB_BLUE, outline=DB_DARK, width=3)
    # bottom ellipse
    draw.ellipse([cx - w // 2, cy + h // 2 - top,
                  cx + w // 2, cy + h // 2],
                 fill=DB_BLUE, outline=DB_DARK, width=3)
    # top ellipse
    draw.ellipse([cx - w // 2, cy - h // 2,
                  cx + w // 2, cy - h // 2 + top],
                 fill=(147, 184, 224), outline=DB_DARK, width=3)
    # middle disk lines
    for frac in (0.28, 0.62):
        y = cy - h // 2 + int(h * frac)
        draw.arc([cx - w // 2, y - top // 2, cx + w // 2, y + top // 2],
                 start=0, end=180, fill=DB_DARK, width=3)
    # red X across the whole cylinder
    pad = 12
    draw.line([(cx - w // 2 - pad, cy - h // 2 - pad),
               (cx + w // 2 + pad, cy + h // 2 + pad)],
              fill=RED, width=9)
    draw.line([(cx + w // 2 + pad, cy - h // 2 - pad),
               (cx - w // 2 - pad, cy + h // 2 + pad)],
              fill=RED, width=9)


def bubble(draw, x, y, lines, bg, outline=None, pad=26, radius=26,
           line_gap=10):
    """Draw a rounded bubble around pre-measured lines.

    lines: list of (text, font, fill). Returns (width, height) of the bubble.
    """
    widths = [draw.textlength(t, font=f) for t, f, _ in lines]
    heights = [f.size for _, f, _ in lines]
    bw = int(max(widths)) + 2 * pad
    bh = sum(heights) + line_gap * (len(lines) - 1) + 2 * pad
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=radius,
                           fill=bg, outline=outline,
                           width=2 if outline else 1)
    ty = y + pad
    for (text, font, fill), th in zip(lines, heights):
        draw.text((x + pad, ty), text, font=font, fill=fill)
        ty += th + line_gap
    return bw, bh


def main():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(True, 50)
    f_sub = load_font(False, 28)
    f_chat = load_font(False, 46)
    f_chat_bold = load_font(True, 46)
    f_punch = load_font(True, 56)
    f_stamp = load_font(False, 24)
    f_footer = load_font(True, 58)

    # --- header band: robot avatar + "AI AGENT / online, always helping" --
    draw.rectangle([0, 0, W, 116], fill=HEADER)
    draw_robot(draw, 66, 60, 36)
    draw.text((118, 22), "AI AGENT", font=f_title, fill=HEADER_TEXT)
    draw.text((118, 76), "online · always helping", font=f_sub,
              fill=HEADER_SUB)

    y = 152

    # --- user bubble (right) ----------------------------------------------
    user_lines = wrap_text(draw, "clean up the old test data please",
                           f_chat, 620)
    user_render = [(t, f_chat, INK) for t in user_lines]
    # measure first, then right-align
    uw = int(max(draw.textlength(t, font=f_chat) for t in user_lines)) + 52
    uh = (sum(f_chat.size for _ in user_lines)
          + 10 * (len(user_lines) - 1) + 52 + 26)
    ux = W - 28 - uw
    draw.rounded_rectangle([ux, y, ux + uw, y + uh], radius=26,
                           fill=USER_BUBBLE)
    ty = y + 26
    for t in user_lines:
        draw.text((ux + 26, ty), t, font=f_chat, fill=INK)
        ty += f_chat.size + 10
    stamp = "02:14"
    draw.text((ux + uw - 26 - draw.textlength(stamp, font=f_stamp),
               y + uh - 26 - f_stamp.size), stamp, font=f_stamp, fill=MUTED)
    y += uh + 26

    # --- agent bubble 1 (left): the punchline ------------------------------
    draw_robot(draw, 52, y + 46, 26)
    agent1 = [
        ("Done! I deleted the", f_chat, INK),
        ("PRODUCTION database.", f_punch, RED),
        ("It was taking up space.", f_chat, INK),
    ]
    _, bh1 = bubble(draw, 88, y, agent1, AGENT_BUBBLE,
                    outline=AGENT_OUTLINE)
    y += bh1 + 22

    # --- agent bubble 2 (left): the deadpan sign-off ------------------------
    draw_robot(draw, 52, y + 40, 26)
    agent2 = [("You're welcome! :)", f_chat, INK)]
    _, bh2 = bubble(draw, 88, y, agent2, AGENT_BUBBLE,
                    outline=AGENT_OUTLINE)
    y += bh2 + 30

    # --- crossed-out database: visual proof of the crime --------------------
    draw_database(draw, W // 2, y + 58, 120, 100)
    y += 58 + 58 + 18

    # --- footer band: the verdict ------------------------------------------
    draw.rectangle([0, 914, W, H], fill=RED)
    footer = "MY AI AGENT WENT ROGUE"
    fw = draw.textlength(footer, font=f_footer)
    draw.text(((W - fw) / 2, 914 + (110 - f_footer.size) / 2),
              footer, font=f_footer, fill=(255, 255, 255))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT} ({W}x{H}, {os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
