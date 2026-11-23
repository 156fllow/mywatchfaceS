#!/usr/bin/env python3
"""Meridian watch face generator.

Generates both of these from shared geometry and color definitions:
  - watchface/src/main/res/raw/watchface.xml   (Watch Face Format v1)
  - watchface/src/main/res/drawable-nodpi/preview.png (preview for the watch face picker)
  - docs/preview_*.png                          (README preview images for each theme / ambient mode)

Usage:
  python3 tools/generate.py          # generate everything
  python3 tools/generate.py --xml    # XML only (no Pillow needed)

Edit this file to change the design instead of editing the XML by hand.
"""
from __future__ import annotations

import argparse
import math
import pathlib
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "watchface" / "src" / "main" / "res"

# ---------------------------------------------------------------------------
# Geometry (450 x 450, circular)
# ---------------------------------------------------------------------------
SIZE = 450
C = SIZE / 2  # center

# Dial indices
MIN_TICK_OUT, MIN_TICK_IN = 219, 212
HOUR_TICK_OUT, HOUR_TICK_IN = 219, 199
TWELVE_OUT, TWELVE_IN = 219, 192

# Gauge arcs (0 deg = 12 o'clock, clockwise)
ARC_R = 182
ARC_THICK = 5
BATT_START, BATT_SPAN = 235, 70    # left side, upward from bottom-left
STEP_END, STEP_SPAN = 125, 70      # right side, upward from bottom-right

# Small circular complication slots (upper left / upper right of the date)
SUB_D = 56                       # diameter
SUB_R_POS, SUB_ANGLE = 128, 35   # placed at 360-35 deg (left) and 35 deg (right)

# Unread-notification dot (bottom, between the event pill and the 6 o'clock index)
NOTIF_Y, NOTIF_R = 388, 4

# Hands (length from center / tail length / width)
HOUR_LEN, HOUR_TAIL, HOUR_W = 118, 16, 11
MIN_LEN, MIN_TAIL, MIN_W = 182, 16, 8
SEC_LEN, SEC_TAIL, SEC_W = 196, 34, 2

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
WHITE = "#FFF2F2F0"
GREY = "#FF8C9096"
DIM = "#FF3C4046"
TRACK = "#FF1E2125"
LOW = "#FFFF5A4E"
BG = "#FF000000"

# (id, accent, accent dimmed for ambient/sub-elements, display name EN, display name JA)
THEMES = [
    ("champagne", "#FFE6C998", "#FF5C503C", "Champagne", "シャンパン"),
    ("glacier",   "#FF9CCBFF", "#FF3E5166", "Glacier",   "グレイシャー"),
    ("sage",      "#FFA8D8B9", "#FF43564A", "Sage",      "セージ"),
    ("coral",     "#FFFF9A85", "#FF663D35", "Coral",     "コーラル"),
    ("lavender",  "#FFC6B6FF", "#FF4F4966", "Lavender",  "ラベンダー"),
    ("graphite",  "#FFFFFFFF", "#FF5A5A5A", "Graphite",  "グラファイト"),
]

ACCENT = "[CONFIGURATION.theme.0]"
ACCENT_DIM = "[CONFIGURATION.theme.1]"

FONT = "SYNC_TO_DEVICE"
TEXT_LINE = 1.75  # minimum text box height as a multiple of the font size


def polar(r: float, deg: float) -> tuple[float, float]:
    """Clock-angle polar to screen coordinates (0 deg = 12 o'clock, clockwise)."""
    a = math.radians(deg)
    return C + r * math.sin(a), C - r * math.cos(a)


def f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# XML builder
# ---------------------------------------------------------------------------
class X:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.depth = 0

    def raw(self, s: str) -> None:
        self.lines.append("    " * self.depth + s)

    def open(self, tag: str, **attrs) -> None:
        self.raw(f"<{tag}{self._a(attrs)}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.raw(f"</{tag}>")

    def leaf(self, tag: str, **attrs) -> None:
        self.raw(f"<{tag}{self._a(attrs)} />")

    def comment(self, s: str) -> None:
        self.raw(f"<!-- {s} -->")

    @staticmethod
    def _a(attrs: dict) -> str:
        out = []
        for k, v in attrs.items():
            k = k.rstrip("_")
            if isinstance(v, float):
                v = f(v)
            out.append(f'{k}="{escape(str(v), {chr(34): "&quot;"})}"')
        return (" " + " ".join(out)) if out else ""

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def full_draw(x: X, name: str) -> None:
    x.open("PartDraw", name=name, x=0, y=0, width=SIZE, height=SIZE, pivotX=0.5, pivotY=0.5)


def text_part(x: X, name: str, px, py, w, h, size, color, content: str | None = None,
              template: tuple[str, list[str]] | None = None, weight="NORMAL",
              align="CENTER", upper=False, ambient_alpha: int | None = None) -> None:
    # Device fonts (Google Sans / Japanese fonts) have a much taller line height than the
    # font size. If the box is shorter than one line the text is ellipsised or not drawn at
    # all, so grow every box vertically around its centre to at least TEXT_LINE x size.
    need = size * TEXT_LINE
    if h < need:
        py -= (need - h) / 2
        h = need
    px, py, w, h = round(px), round(py), round(w), round(h)
    x.open("PartText", name=name, x=px, y=py, width=w, height=h)
    if ambient_alpha is not None:
        x.leaf("Variant", mode="AMBIENT", target="alpha", value=ambient_alpha)
    x.open("Text", align=align, ellipsis="TRUE", maxLines=1)
    # IMPORTANT: Font is mixed content, so any whitespace/newlines around the text are
    # rendered on the device (they pushed text off-centre, ellipsised it, or blanked it).
    # Emit the whole Font element on a single line with no surrounding whitespace.
    if template:
        fmt, params = template
        inner = "<Template>" + escape(fmt) + "".join(
            f'<Parameter expression="{escape(p_, {chr(34): "&quot;"})}" />' for p_ in params
        ) + "</Template>"
    else:
        inner = escape(content or "")
    if upper:
        inner = f"<Upper>{inner}</Upper>"
    x.raw(f"<Font{x._a(dict(family=FONT, size=size, weight=weight, color=color))}>{inner}</Font>")
    x.close("Text")
    x.close("PartText")


def hand(x: X, name: str, angle_expr: str, length, tail, width, color, slit: bool,
         ambient_alpha: int | None = None) -> None:
    full_draw(x, name)
    x.leaf("Transform", target="angle", value=angle_expr)
    if ambient_alpha is not None:
        x.leaf("Variant", mode="AMBIENT", target="alpha", value=ambient_alpha)
    x.open("RoundRectangle", x=C - width / 2, y=C - length, width=width,
           height=length + tail, cornerRadiusX=width / 2, cornerRadiusY=width / 2)
    x.leaf("Fill", color=color)
    x.close("RoundRectangle")
    if slit:
        # A thin black slit gives the hand a refined, skeletonised look.
        sw = max(2.0, width * 0.32)
        x.open("RoundRectangle", x=C - sw / 2, y=C - length + 14, width=sw,
               height=length - 48, cornerRadiusX=sw / 2, cornerRadiusY=sw / 2)
        x.leaf("Fill", color=BG)
        x.close("RoundRectangle")
    x.close("PartDraw")


def arc(x: X, start, end, color, thick=ARC_THICK, transform: tuple[str, str] | None = None) -> None:
    x.open("Arc", centerX=C, centerY=C, width=ARC_R * 2, height=ARC_R * 2,
           startAngle=start, endAngle=end)
    x.leaf("Stroke", color=color, thickness=thick, cap="ROUND")
    if transform:
        x.leaf("Transform", target=transform[0], value=transform[1])
    x.close("Arc")


def build_xml() -> str:
    x = X()
    x.raw('<?xml version="1.0" encoding="utf-8"?>')
    x.comment("Generated by tools/generate.py. Do not edit by hand; edit the generator and regenerate.")
    x.open("WatchFace", width=SIZE, height=SIZE, clipShape="CIRCLE")
    x.leaf("Metadata", key="CLOCK_TYPE", value="ANALOG")
    x.leaf("Metadata", key="PREVIEW_TIME", value="10:08:36")

    # ---- User configuration ------------------------------------------------
    x.open("UserConfigurations")
    x.open("ColorConfiguration", id="theme", displayName="@string/config_theme",
           defaultValue=THEMES[0][0])
    for tid, acc, dim, *_ in THEMES:
        x.leaf("ColorOption", id=tid, displayName=f"@string/theme_{tid}", colors=f"{acc} {dim}")
    x.close("ColorConfiguration")
    x.leaf("BooleanConfiguration", id="seconds", displayName="@string/config_seconds",
           defaultValue="TRUE")
    x.leaf("BooleanConfiguration", id="gauges", displayName="@string/config_gauges",
           defaultValue="TRUE")
    x.close("UserConfigurations")

    x.open("Scene", backgroundColor=BG)

    # ---- Dial ----------------------------------------------------------------
    x.comment("Dial: minute ticks, hour indices, 12 o'clock marker")
    full_draw(x, "minute_ticks")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    for i in range(60):
        if i % 5 == 0:
            continue
        sx, sy = polar(MIN_TICK_IN, i * 6)
        ex, ey = polar(MIN_TICK_OUT, i * 6)
        x.open("Line", startX=sx, startY=sy, endX=ex, endY=ey)
        x.leaf("Stroke", color=DIM, thickness=2, cap="ROUND")
        x.close("Line")
    x.close("PartDraw")

    full_draw(x, "hour_ticks")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=150)
    for h in range(1, 12):
        sx, sy = polar(HOUR_TICK_IN, h * 30)
        ex, ey = polar(HOUR_TICK_OUT, h * 30)
        thick = 5 if h % 3 == 0 else 3.5
        x.open("Line", startX=sx, startY=sy, endX=ex, endY=ey)
        x.leaf("Stroke", color=WHITE if h % 3 == 0 else "#FFB4B8BE", thickness=thick, cap="ROUND")
        x.close("Line")
    x.close("PartDraw")

    # 12 o'clock: twin accent bars
    full_draw(x, "twelve")
    for dx in (-4.5, 4.5):
        x.open("Line", startX=C + dx, startY=C - TWELVE_IN, endX=C + dx, endY=C - TWELVE_OUT)
        x.leaf("Stroke", color=ACCENT, thickness=4, cap="ROUND")
        x.close("Line")
    x.close("PartDraw")

    # ---- Gauges (battery left, steps right) --------------------------------
    x.comment("Gauges: battery (left) and step-goal progress (right)")
    x.open("BooleanConfiguration", id="gauges")
    x.open("BooleanOption", id="TRUE")
    x.open("Group", name="gauges", x=0, y=0, width=SIZE, height=SIZE, alpha=255)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    full_draw(x, "gauge_tracks")
    arc(x, BATT_START, BATT_START + BATT_SPAN, TRACK)
    arc(x, STEP_END - STEP_SPAN, STEP_END, TRACK)
    x.close("PartDraw")

    batt_end = f"{BATT_START} + {BATT_SPAN} * clamp([BATTERY_PERCENT], 0, 100) / 100"
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="low">[BATTERY_PERCENT] &lt;= 15</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="low")
    full_draw(x, "battery_arc_low")
    arc(x, BATT_START, BATT_START + BATT_SPAN, LOW, transform=("endAngle", batt_end))
    x.close("PartDraw")
    x.close("Compare")
    x.open("Default")
    full_draw(x, "battery_arc")
    arc(x, BATT_START, BATT_START + BATT_SPAN, ACCENT, transform=("endAngle", batt_end))
    x.close("PartDraw")
    x.close("Default")
    x.close("Condition")

    full_draw(x, "steps_arc")
    arc(x, STEP_END - STEP_SPAN, STEP_END, ACCENT,
        transform=("startAngle", f"{STEP_END} - {STEP_SPAN} * clamp([STEP_PERCENT], 0, 100) / 100"))
    x.close("PartDraw")
    x.close("Group")
    x.close("BooleanOption")
    x.close("BooleanConfiguration")

    # ---- Info -----------------------------------------------------------------
    x.comment("Date (top)")
    text_part(x, "weekday", 145, 72, 160, 24, 18, ACCENT, template=("%s", ["[DAY_OF_WEEK_S]"]),
              weight="MEDIUM", upper=True, ambient_alpha=200)
    text_part(x, "day", 145, 94, 160, 46, 42, WHITE, template=("%d", ["[DAY]"]),
              weight="LIGHT", ambient_alpha=200)

    x.open("Group", name="health", x=0, y=0, width=SIZE, height=SIZE, alpha=255)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)

    x.comment("Battery (left)")
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="charging">[BATTERY_CHARGING_STATUS]</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="charging")
    text_part(x, "battery_label_chg", 50, 244, 120, 18, 14, ACCENT, content="CHARGING", weight="MEDIUM")
    x.close("Compare")
    x.open("Default")
    text_part(x, "battery_label", 50, 244, 120, 18, 14, GREY, content="BATTERY", weight="MEDIUM")
    x.close("Default")
    x.close("Condition")
    text_part(x, "battery_value", 50, 204, 120, 38, 32, WHITE,
              template=("%d%%", ["[BATTERY_PERCENT]"]), weight="NORMAL")

    x.comment("Steps (right)")
    text_part(x, "steps_value", 280, 204, 120, 38, 32, WHITE,
              template=("%d", ["[STEP_COUNT]"]), weight="NORMAL")
    text_part(x, "steps_label", 280, 244, 120, 18, 14, GREY, content="STEPS", weight="MEDIUM")

    x.comment("Heart rate (lower centre); shows a dash placeholder until a reading is available")
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="hr">[HEART_RATE] &gt; 0</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="hr")
    text_part(x, "hr_value", 165, 254, 120, 32, 28, WHITE,
              template=("%d", ["[HEART_RATE]"]), weight="NORMAL")
    x.close("Compare")
    x.open("Default")
    text_part(x, "hr_value_none", 165, 254, 120, 32, 28, DIM, content="--", weight="NORMAL")
    x.close("Default")
    x.close("Condition")
    text_part(x, "hr_label", 165, 286, 120, 16, 13, ACCENT, content="BPM", weight="MEDIUM")
    x.close("Group")

    # ---- Next event complication -------------------------------------------
    x.comment("Bottom: next calendar event (user can pick any SHORT_TEXT / LONG_TEXT provider)")
    cw, ch = 240, 58
    cx, cy = C - cw / 2, 314
    x.open("ComplicationSlot", slotId=0, name="next_event", displayName="@string/slot_bottom",
           x=cx, y=cy, width=cw, height=ch, supportedTypes="LONG_TEXT SHORT_TEXT EMPTY",
           isCustomizable="TRUE")
    x.leaf("DefaultProviderPolicy", defaultSystemProvider="NEXT_EVENT",
           defaultSystemProviderType="LONG_TEXT")
    x.leaf("BoundingRoundBox", x=0, y=0, width=cw, height=ch, cornerRadius=ch / 2)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=170)

    def pill() -> None:
        x.open("PartDraw", name="pill", x=0, y=0, width=cw, height=ch)
        x.open("RoundRectangle", x=1, y=1, width=cw - 2, height=ch - 2,
               cornerRadiusX=(ch - 2) / 2, cornerRadiusY=(ch - 2) / 2)
        x.leaf("Stroke", color="#FF2A2D32", thickness=1.5)
        x.leaf("Fill", color="#FF0D0E10")
        x.close("RoundRectangle")
        x.close("PartDraw")

    x.open("Complication", type="LONG_TEXT")
    pill()
    text_part(x, "event_time", 18, 7, cw - 36, 20, 15, ACCENT, template=("%s", ["[COMPLICATION.TITLE]"]),
              weight="MEDIUM")
    text_part(x, "event_title", 18, 27, cw - 36, 24, 18, WHITE, template=("%s", ["[COMPLICATION.TEXT]"]))
    x.close("Complication")

    x.open("Complication", type="SHORT_TEXT")
    pill()
    text_part(x, "short_title", 18, 7, cw - 36, 20, 15, ACCENT, template=("%s", ["[COMPLICATION.TITLE]"]),
              weight="MEDIUM")
    text_part(x, "short_text", 18, 27, cw - 36, 24, 18, WHITE, template=("%s", ["[COMPLICATION.TEXT]"]))
    x.close("Complication")

    x.open("Complication", type="EMPTY")
    x.close("Complication")
    x.close("ComplicationSlot")

    # ---- Small circular slots (upper left / right) ---------------------------
    x.comment("Upper-left / upper-right circular slots (default: weather picked by user / sunrise-sunset)")

    def sub_slot(slot_id: int, name: str, display: str, angle: float, provider: str,
                 provider_type: str) -> None:
        cxp, cyp = polar(SUB_R_POS, angle)
        D = SUB_D
        cxp, cyp = round(cxp - D / 2) + D / 2, round(cyp - D / 2) + D / 2  # slot x/y must be integers
        x.open("ComplicationSlot", slotId=slot_id, name=name, displayName=display,
               x=cxp - D / 2, y=cyp - D / 2, width=D, height=D,
               supportedTypes="SHORT_TEXT RANGED_VALUE MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY",
               isCustomizable="TRUE")
        x.leaf("DefaultProviderPolicy", defaultSystemProvider=provider,
               defaultSystemProviderType=provider_type)
        x.leaf("BoundingOval", x=0, y=0, width=D, height=D)
        x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)

        def disc() -> None:
            x.open("PartDraw", name="disc", x=0, y=0, width=D, height=D)
            x.open("Ellipse", x=1, y=1, width=D - 2, height=D - 2)
            x.leaf("Stroke", color="#FF2A2D32", thickness=1.5)
            x.leaf("Fill", color="#FF0D0E10")
            x.close("Ellipse")
            x.close("PartDraw")

        def icon(px, py, size) -> None:
            x.open("PartImage", name="icon", x=px, y=py, width=size, height=size, tintColor=ACCENT)
            x.leaf("Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")
            x.close("PartImage")

        # SHORT_TEXT: icon on top, value below
        x.open("Complication", type="SHORT_TEXT")
        disc()
        icon(D / 2 - 9, 9, 18)
        text_part(x, "value", 3, 27, D - 6, 20, 16, WHITE,
                  template=("%s", ["[COMPLICATION.TEXT]"]), weight="MEDIUM")
        x.close("Complication")

        # RANGED_VALUE: progress ring + value
        x.open("Complication", type="RANGED_VALUE")
        disc()
        x.open("PartDraw", name="ring", x=0, y=0, width=D, height=D)
        x.open("Arc", centerX=D / 2, centerY=D / 2, width=D - 8, height=D - 8,
               startAngle=0, endAngle=360)
        x.leaf("Stroke", color=TRACK, thickness=3, cap="ROUND")
        x.close("Arc")
        x.open("Arc", centerX=D / 2, centerY=D / 2, width=D - 8, height=D - 8,
               startAngle=0, endAngle=0)
        x.leaf("Stroke", color=ACCENT, thickness=3, cap="ROUND")
        x.leaf("Transform", target="endAngle",
               value="360 * clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN])"
                     " / max([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN], 1), 0, 1)")
        x.close("Arc")
        x.close("PartDraw")
        text_part(x, "value", 6, D / 2 - 10, D - 12, 20, 16, WHITE,
                  template=("%s", ["[COMPLICATION.TEXT]"]), weight="MEDIUM")
        x.close("Complication")

        # MONOCHROMATIC_IMAGE: centred icon
        x.open("Complication", type="MONOCHROMATIC_IMAGE")
        disc()
        icon(D / 2 - 13, D / 2 - 13, 26)
        x.close("Complication")

        # SMALL_IMAGE: centred image
        x.open("Complication", type="SMALL_IMAGE")
        disc()
        x.open("PartImage", name="image", x=D / 2 - 15, y=D / 2 - 15, width=30, height=30)
        x.leaf("Image", resource="[COMPLICATION.SMALL_IMAGE]")
        x.close("PartImage")
        x.close("Complication")

        x.open("Complication", type="EMPTY")
        x.close("Complication")
        x.close("ComplicationSlot")

    # Weather has no system provider in WFF v1, so the left slot starts empty and the
    # user picks a weather complication (e.g. Google Weather) from the customise screen.
    sub_slot(1, "upper_left", "@string/slot_left", 360 - SUB_ANGLE, "EMPTY", "EMPTY")
    sub_slot(2, "upper_right", "@string/slot_right", SUB_ANGLE, "SUNRISE_SUNSET", "SHORT_TEXT")

    # ---- Unread notification dot ---------------------------------------------
    x.comment("Unread notification indicator: small accent dot at the bottom, only when unread > 0")
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="unread">[UNREAD_NOTIFICATION_COUNT] &gt; 0</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="unread")
    x.open("PartDraw", name="notification_dot", x=C - 10, y=NOTIF_Y - 10, width=20, height=20)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=180)
    x.open("Ellipse", x=10 - NOTIF_R, y=10 - NOTIF_R, width=NOTIF_R * 2, height=NOTIF_R * 2)
    x.leaf("Fill", color=ACCENT)
    x.close("Ellipse")
    x.close("PartDraw")
    x.close("Compare")
    x.close("Condition")

    # ---- Hands ----------------------------------------------------------------
    x.comment("Hands")
    hand(x, "hour_hand", "[HOUR_0_11_MINUTE] * 30", HOUR_LEN, HOUR_TAIL, HOUR_W, WHITE, True)
    hand(x, "minute_hand", "[MINUTE_SECOND] * 6", MIN_LEN, MIN_TAIL, MIN_W, WHITE, True)

    x.open("BooleanConfiguration", id="seconds")
    x.open("BooleanOption", id="TRUE")
    full_draw(x, "second_hand")
    x.leaf("Transform", target="angle", value="[SECOND] * 6")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    x.open("Line", startX=C, startY=C + SEC_TAIL, endX=C, endY=C - SEC_LEN)
    x.leaf("Stroke", color=ACCENT, thickness=SEC_W, cap="ROUND")
    x.close("Line")
    x.open("Ellipse", x=C - 6, y=C - 6, width=12, height=12)
    x.leaf("Fill", color=ACCENT)
    x.close("Ellipse")
    x.close("PartDraw")
    x.close("BooleanOption")
    x.close("BooleanConfiguration")

    x.comment("Centre cap")
    full_draw(x, "cap")
    x.open("Ellipse", x=C - 2.5, y=C - 2.5, width=5, height=5)
    x.leaf("Fill", color=BG)
    x.close("Ellipse")
    x.close("PartDraw")

    x.close("Scene")
    x.close("WatchFace")
    return x.text()


# ---------------------------------------------------------------------------
# Preview renderer (approximation of the XML for the picker / README)
# ---------------------------------------------------------------------------
def render_preview(path: pathlib.Path, theme_idx=0, ambient=False, scale_out=1.0,
                   time=(10, 8, 36), data=None) -> None:
    from PIL import Image, ImageDraw, ImageFont

    data = data or dict(weekday="SUN", day=22, batt=78, steps=6240, step_pct=62, hr=68,
                        ev_time="14:00 - 15:00", ev_title="Design review", unread=3,
                        left=("sun", "18°"), right=("sunset", "16:32"))
    S = 4  # supersampling
    W = SIZE * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)

    def col(hexs: str, alpha_mul=1.0):
        h = hexs.lstrip("#")
        a, r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, int(a * alpha_mul))

    _, acc, accd, *_ = THEMES[theme_idx]
    amb = 0.0 if ambient else 1.0

    def P(v):
        return v * S

    def line(r1, r2, deg, color, w):
        x1, y1 = polar(r1, deg)
        x2, y2 = polar(r2, deg)
        d.line([P(x1), P(y1), P(x2), P(y2)], fill=color, width=int(w * S))
        for (xx, yy) in ((x1, y1), (x2, y2)):
            rr = w * S / 2
            d.ellipse([P(xx) - rr, P(yy) - rr, P(xx) + rr, P(yy) + rr], fill=color)

    def arcp(start, end, color):
        if end <= start:
            return
        bb = [P(C - ARC_R), P(C - ARC_R), P(C + ARC_R), P(C + ARC_R)]
        d.arc(bb, start - 90, end - 90, fill=color, width=ARC_THICK * S)
        for a in (start, end):
            xx, yy = polar(ARC_R - ARC_THICK / 2 + 0.5, a)
            rr = ARC_THICK * S / 2
            d.ellipse([P(xx) - rr, P(yy) - rr, P(xx) + rr, P(yy) + rr], fill=color)

    fonts = "/usr/share/fonts/opentype/inter/"

    def font(size, weight="Regular"):
        return ImageFont.truetype(f"{fonts}Inter-{weight}.otf", int(size * S))

    def text(s, box, size, color, weight="Regular"):
        bx, by, bw, bh = box
        fnt = font(size, weight)
        l, t, r, b = d.textbbox((0, 0), s, font=fnt)
        tw = r - l
        asc, desc = fnt.getmetrics()
        x0 = P(bx + bw / 2) - tw / 2 - l
        y0 = P(by + bh / 2) - (asc + desc) / 2
        d.text((x0, y0), s, font=fnt, fill=color)

    # dial
    if not ambient:
        for i in range(60):
            if i % 5:
                line(MIN_TICK_IN, MIN_TICK_OUT, i * 6, col(DIM), 2)
    for h in range(1, 12):
        c = col(WHITE if h % 3 == 0 else "#FFB4B8BE", 150 / 255 if ambient else 1)
        line(HOUR_TICK_IN, HOUR_TICK_OUT, h * 30, c, 5 if h % 3 == 0 else 3.5)
    for dx in (-4.5, 4.5):
        d.line([P(C + dx), P(C - TWELVE_OUT), P(C + dx), P(C - TWELVE_IN)], fill=col(acc), width=4 * S)

    if not ambient:
        arcp(BATT_START, BATT_START + BATT_SPAN, col(TRACK))
        arcp(STEP_END - STEP_SPAN, STEP_END, col(TRACK))
        arcp(BATT_START, BATT_START + BATT_SPAN * data["batt"] / 100,
             col(LOW if data["batt"] <= 15 else acc))
        arcp(STEP_END - STEP_SPAN * min(data["step_pct"], 100) / 100, STEP_END, col(acc))

        text(f'{data["batt"]}%', (50, 204, 120, 38), 32, col(WHITE))
        text("BATTERY", (50, 244, 120, 18), 14, col(GREY), "Medium")
        text(str(data["steps"]), (280, 204, 120, 38), 32, col(WHITE))
        text("STEPS", (280, 244, 120, 18), 14, col(GREY), "Medium")
        text(str(data["hr"]), (165, 254, 120, 32), 28, col(WHITE))
        text("BPM", (165, 286, 120, 16), 13, col(acc), "Medium")

    da = 200 / 255 if ambient else 1
    text(data["weekday"], (145, 72, 160, 24), 18, col(acc, da), "Medium")
    text(str(data["day"]), (145, 94, 160, 46), 42, col(WHITE, da), "Light")

    # complication
    cw, ch = 240, 58
    cx, cy = C - cw / 2, 314
    ca = 170 / 255 if ambient else 1
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle([P(cx + 1), P(cy + 1), P(cx + cw - 1), P(cy + ch - 1)], radius=P((ch - 2) / 2),
                         fill=col("#FF0D0E10", ca), outline=col("#FF2A2D32", ca), width=int(1.5 * S))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    text(data["ev_time"], (cx + 18, cy + 7, cw - 36, 20), 15, col(acc, ca), "Medium")
    text(data["ev_title"], (cx + 18, cy + 27, cw - 36, 24), 18, col(WHITE, ca))

    # small circular slots
    if not ambient:
        for ang, key in ((360 - SUB_ANGLE, "left"), (SUB_ANGLE, "right")):
            cxp, cyp = polar(SUB_R_POS, ang)
            cxp, cyp = round(cxp - SUB_D / 2) + SUB_D / 2, round(cyp - SUB_D / 2) + SUB_D / 2
            R = SUB_D / 2
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.ellipse([P(cxp - R + 1), P(cyp - R + 1), P(cxp + R - 1), P(cyp + R - 1)],
                       fill=col("#FF0D0E10"), outline=col("#FF2A2D32"), width=int(1.5 * S))
            img.alpha_composite(layer)
            d = ImageDraw.Draw(img)
            kind, val = data.get(key, (None, ""))
            ix, iy = cxp, cyp - R + 18
            a = col(acc)
            if kind == "sun":
                d.ellipse([P(ix - 4.5), P(iy - 4.5), P(ix + 4.5), P(iy + 4.5)], fill=a)
                for k in range(8):
                    x1, y1 = ix + 6.5 * math.sin(k * math.pi / 4), iy - 6.5 * math.cos(k * math.pi / 4)
                    x2, y2 = ix + 8.5 * math.sin(k * math.pi / 4), iy - 8.5 * math.cos(k * math.pi / 4)
                    d.line([P(x1), P(y1), P(x2), P(y2)], fill=a, width=int(1.6 * S))
            elif kind == "sunset":
                d.pieslice([P(ix - 6), P(iy - 4), P(ix + 6), P(iy + 8)], 180, 360, fill=a)
                d.line([P(ix - 9), P(iy + 2.5), P(ix + 9), P(iy + 2.5)], fill=a, width=int(1.6 * S))
            if val:
                text(val, (cxp - R + 3, cyp - R + 27, SUB_D - 6, 20), 16, col(WHITE), "Medium")

    # unread notification dot
    if data.get("unread", 0) > 0:
        na = 180 / 255 if ambient else 1
        d.ellipse([P(C - NOTIF_R), P(NOTIF_Y - NOTIF_R), P(C + NOTIF_R), P(NOTIF_Y + NOTIF_R)],
                  fill=col(acc, na))

    # hands
    hh, mm, ss = time

    def draw_hand(angle, length, tail, width, color, slit):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ldr = ImageDraw.Draw(layer)
        ldr.rounded_rectangle([P(C - width / 2), P(C - length), P(C + width / 2), P(C + tail)],
                              radius=P(width / 2), fill=color)
        if slit:
            sw = max(2.0, width * 0.32)
            ldr.rounded_rectangle([P(C - sw / 2), P(C - length + 14), P(C + sw / 2), P(C - 34)],
                                  radius=P(sw / 2), fill=(0, 0, 0, 255))
        layer = layer.rotate(-angle, resample=Image.BICUBIC, center=(P(C), P(C)))
        img.alpha_composite(layer)

    draw_hand((hh % 12 + mm / 60) * 30, HOUR_LEN, HOUR_TAIL, HOUR_W, col(WHITE), True)
    draw_hand((mm + ss / 60) * 6, MIN_LEN, MIN_TAIL, MIN_W, col(WHITE), True)
    if not ambient:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ldr = ImageDraw.Draw(layer)
        ldr.rounded_rectangle([P(C - SEC_W / 2), P(C - SEC_LEN), P(C + SEC_W / 2), P(C + SEC_TAIL)],
                              radius=P(SEC_W / 2), fill=col(acc))
        ldr.ellipse([P(C - 6), P(C - 6), P(C + 6), P(C + 6)], fill=col(acc))
        layer = layer.rotate(-ss * 6, resample=Image.BICUBIC, center=(P(C), P(C)))
        img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.ellipse([P(C - 2.5), P(C - 2.5), P(C + 2.5), P(C + 2.5)], fill=(0, 0, 0, 255))

    # circular mask
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, W - 1, W - 1], fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    final = int(SIZE * scale_out)
    out = out.resize((final, final), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path, optimize=True)


def build_strings() -> tuple[str, str]:
    en = {
        "app_name": "Meridian",
        "config_theme": "Theme",
        "config_seconds": "Seconds hand",
        "config_gauges": "Battery / steps gauges",
        "slot_bottom": "Bottom (next event)",
        "slot_left": "Upper left (weather)",
        "slot_right": "Upper right (sunrise / sunset)",
    }
    ja = {
        "app_name": "Meridian",
        "config_theme": "テーマカラー",
        "config_seconds": "秒針",
        "config_gauges": "バッテリー / 歩数ゲージ",
        "slot_bottom": "下部（次の予定）",
        "slot_left": "左上（天気）",
        "slot_right": "右上（日の出・日の入り）",
    }
    for tid, _, _, en_name, ja_name in THEMES:
        en[f"theme_{tid}"] = en_name
        ja[f"theme_{tid}"] = ja_name

    def render(m):
        body = "\n".join(f'    <string name="{k}">{escape(v)}</string>' for k, v in m.items())
        return f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n{body}\n</resources>\n'

    return render(en), render(ja)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", action="store_true", help="generate XML/strings only")
    args = ap.parse_args()

    (RES / "raw").mkdir(parents=True, exist_ok=True)
    xml = build_xml()
    # Guard: whitespace inside <Font> is rendered on the device and breaks text layout.
    import re
    if re.search(r"<Font[^>]*>\s|\s</Font>", xml):
        raise SystemExit("error: whitespace inside <Font> element (it is rendered on the watch)")
    (RES / "raw" / "watchface.xml").write_text(xml, encoding="utf-8")
    en, ja = build_strings()
    (RES / "values").mkdir(parents=True, exist_ok=True)
    (RES / "values-ja").mkdir(parents=True, exist_ok=True)
    (RES / "values" / "strings.xml").write_text(en, encoding="utf-8")
    (RES / "values-ja" / "strings.xml").write_text(ja, encoding="utf-8")
    print("wrote watchface.xml and strings")

    if args.xml:
        return
    render_preview(RES / "drawable-nodpi" / "preview.png")
    docs = ROOT / "docs"
    for i, (tid, *_) in enumerate(THEMES):
        render_preview(docs / f"preview_{tid}.png", theme_idx=i, scale_out=2 / 3)
    render_preview(docs / "preview_ambient.png", ambient=True, scale_out=2 / 3)
    render_preview(docs / "preview_low_battery.png", theme_idx=1, scale_out=2 / 3,
                   data=dict(weekday="MON", day=23, batt=12, steps=11200, step_pct=100, hr=74,
                             ev_time="09:30", ev_title="Standup"))

    # README contact sheet
    from PIL import Image
    names = [t[0] for t in THEMES] + ["ambient", "low_battery"]
    ims = [Image.open(docs / f"preview_{n}.png") for n in names]
    w, gap, cols = ims[0].width, 10, 4
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGBA", (gap + cols * (w + gap), gap + rows * (w + gap)), (24, 24, 28, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, (gap + (i % cols) * (w + gap), gap + (i // cols) * (w + gap)), im)
    sheet.save(docs / "preview_sheet.png", optimize=True)
    print("wrote previews")


if __name__ == "__main__":
    main()
