#!/usr/bin/env python3
"""Meridian watch face generator (four discs on top, calendar in the lower half).

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

# Gauge arcs (0 deg = 12 o'clock, clockwise), centred on 9 and 3 o'clock
ARC_R = 184
ARC_THICK = 6
BATT_START, BATT_SPAN = 240, 60    # left side, filling upward from bottom-left
STEP_END, STEP_SPAN = 120, 60      # right side, filling upward from bottom-right

# Date line at the top
DATE_Y, DATE_SIZE = 76, 20

# Four discs in the upper half. Battery / steps sit right next to their gauges.
OUTER_R, INNER_R = 38, 34
BATT_POS, STEPS_POS = (102, 198), (348, 198)
WEATHER_POS, HR_POS = (166, 130), (284, 130)
OUTER_VALUE, OUTER_VALUE_LONG, INNER_VALUE = 24, 20, 21

# Calendar card: the whole lower half
CAL_W, CAL_H, CAL_Y, CAL_RADIUS = 290, 126, 262, 30
CAL_TIME_SIZE, CAL_TITLE_SIZE = 20, 22

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
CARD = "#FF0D0E10"
EDGE = "#FF2A2D32"

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
              align="CENTER", upper=False, ambient_alpha: int | None = None,
              max_lines: int = 1) -> None:
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
    x.open("Text", align=align, ellipsis="TRUE", maxLines=max_lines)
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


def disc(x: X, name: str, d: float) -> None:
    """Dark disc with a thin outline, filling a d x d box."""
    x.open("PartDraw", name=name, x=0, y=0, width=d, height=d)
    x.open("Ellipse", x=1, y=1, width=d - 2, height=d - 2)
    x.leaf("Stroke", color=EDGE, thickness=1.5)
    x.leaf("Fill", color=CARD)
    x.close("Ellipse")
    x.close("PartDraw")


def icon_battery(x: X, cx, cy, color, s=1.15) -> None:
    w, h = 15 * s, 8 * s
    x.open("PartDraw", name="icon_battery", x=round(cx - 12 * s), y=round(cy - 7 * s),
           width=round(24 * s), height=round(14 * s))
    ox, oy = round(cx - 12 * s), round(cy - 7 * s)
    x.open("RoundRectangle", x=cx - w / 2 - ox, y=cy - h / 2 - oy, width=w, height=h,
           cornerRadiusX=1.5 * s, cornerRadiusY=1.5 * s)
    x.leaf("Stroke", color=color, thickness=1.6 * s)
    x.close("RoundRectangle")
    x.open("Rectangle", x=cx + w / 2 - ox, y=cy - 2 * s - oy, width=2 * s, height=4 * s)
    x.leaf("Fill", color=color)
    x.close("Rectangle")
    x.open("Rectangle", x=cx - w / 2 + 2.5 * s - ox, y=cy - h / 2 + 2.5 * s - oy,
           width=w * 0.75 - 2.5 * s, height=h - 5 * s)
    x.leaf("Fill", color=color)
    x.close("Rectangle")
    x.close("PartDraw")


def icon_steps(x: X, cx, cy, color, s=1.15) -> None:
    ox, oy = round(cx - 10 * s), round(cy - 10 * s)
    x.open("PartDraw", name="icon_steps", x=ox, y=oy, width=round(20 * s), height=round(20 * s))
    for dx, dy in ((-3.5, 2.5), (3.5, -2.5)):
        fx, fy = cx + dx * s - ox, cy + dy * s - oy
        x.open("Ellipse", x=fx - 2.6 * s, y=fy - 4.5 * s, width=5.2 * s, height=7.5 * s)
        x.leaf("Fill", color=color)
        x.close("Ellipse")
        x.open("Ellipse", x=fx - 1.8 * s, y=fy + 3.8 * s, width=3.6 * s, height=2.8 * s)
        x.leaf("Fill", color=color)
        x.close("Ellipse")
    x.close("PartDraw")


def icon_heart(x: X, cx, cy, color, s=1.15) -> None:
    """Heart = a square rotated 45 degrees plus two circles on its upper sides."""
    q = 7.2 * s                      # square side
    box = 1.5 * q
    ox, oy = cx - q, cy - q * 0.95   # square centre lands slightly below (cx, cy)
    x.open("PartDraw", name="icon_heart", x=round(ox), y=round(oy), width=round(box), height=round(box),
           pivotX=round(q, 2) / round(box), pivotY=round(q, 2) / round(box), angle=45)
    x.open("Rectangle", x=q / 2, y=q / 2, width=q, height=q)
    x.leaf("Fill", color=color)
    x.close("Rectangle")
    for ex, ey in ((q / 2, 0), (0, q / 2)):
        x.open("Ellipse", x=ex, y=ey, width=q, height=q)
        x.leaf("Fill", color=color)
        x.close("Ellipse")
    x.close("PartDraw")


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

    full_draw(x, "twelve")
    for dx in (-4.5, 4.5):
        x.open("Line", startX=C + dx, startY=C - TWELVE_IN, endX=C + dx, endY=C - TWELVE_OUT)
        x.leaf("Stroke", color=ACCENT, thickness=4, cap="ROUND")
        x.close("Line")
    x.close("PartDraw")

    # ---- Side gauges (battery left, steps right) ----------------------------
    x.comment("Side gauges: battery (left) and step-goal progress (right)")
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

    # ---- Date ------------------------------------------------------------------
    x.comment("Date line, e.g. 11月23日 月")
    text_part(x, "date", C - 120, DATE_Y - 12, 240, 24, DATE_SIZE, ACCENT,
              template=("%d月%d日 %s", ["[MONTH]", "[DAY]", "[DAY_OF_WEEK_S]"]),
              weight="MEDIUM", ambient_alpha=200)

    # ---- Built-in discs: battery, steps, heart rate ------------------------
    x.open("Group", name="discs", x=0, y=0, width=SIZE, height=SIZE, alpha=255)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)

    def disc_group(name, pos, r):
        cx, cy = pos
        x.open("Group", name=name, x=round(cx - r), y=round(cy - r), width=2 * r, height=2 * r, alpha=255)
        disc(x, "disc", 2 * r)
        return r  # children use coordinates relative to the disc box

    x.comment("Battery disc (next to the left gauge)")
    r = disc_group("battery", BATT_POS, OUTER_R)
    icon_battery(x, r, r - r * 0.38, ACCENT)
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="charging">[BATTERY_CHARGING_STATUS]</Expression>')
    x.raw('<Expression name="low">[BATTERY_PERCENT] &lt;= 15</Expression>')
    x.close("Expressions")
    for expr, color in (("charging", ACCENT), ("low", LOW)):
        x.open("Compare", expression=expr)
        text_part(x, f"battery_value_{expr}", 4, r + r * 0.27 - 14, 2 * r - 8, 28, OUTER_VALUE, color,
                  template=("%d%%", ["[BATTERY_PERCENT]"]), weight="MEDIUM")
        x.close("Compare")
    x.open("Default")
    text_part(x, "battery_value", 4, r + r * 0.27 - 14, 2 * r - 8, 28, OUTER_VALUE, WHITE,
              template=("%d%%", ["[BATTERY_PERCENT]"]), weight="MEDIUM")
    x.close("Default")
    x.close("Condition")
    x.close("Group")

    x.comment("Steps disc (next to the right gauge); smaller text from 10,000 steps")
    r = disc_group("steps", STEPS_POS, OUTER_R)
    icon_steps(x, r, r - r * 0.38, ACCENT)
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="long">[STEP_COUNT] &gt;= 10000</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="long")
    text_part(x, "steps_value_long", 3, r + r * 0.27 - 14, 2 * r - 6, 28, OUTER_VALUE_LONG, WHITE,
              template=("%d", ["[STEP_COUNT]"]), weight="MEDIUM")
    x.close("Compare")
    x.open("Default")
    text_part(x, "steps_value", 3, r + r * 0.27 - 14, 2 * r - 6, 28, OUTER_VALUE, WHITE,
              template=("%d", ["[STEP_COUNT]"]), weight="MEDIUM")
    x.close("Default")
    x.close("Condition")
    x.close("Group")

    x.comment("Heart-rate disc; shows a dash placeholder until a reading is available")
    r = disc_group("heart_rate", HR_POS, INNER_R)
    icon_heart(x, r, r - r * 0.38, ACCENT)
    x.open("Condition")
    x.open("Expressions")
    x.raw('<Expression name="hr">[HEART_RATE] &gt; 0</Expression>')
    x.close("Expressions")
    x.open("Compare", expression="hr")
    text_part(x, "hr_value", 4, r + r * 0.27 - 13, 2 * r - 8, 26, INNER_VALUE, WHITE,
              template=("%d", ["[HEART_RATE]"]), weight="MEDIUM")
    x.close("Compare")
    x.open("Default")
    text_part(x, "hr_value_none", 4, r + r * 0.27 - 13, 2 * r - 8, 26, INNER_VALUE, DIM,
              content="--", weight="MEDIUM")
    x.close("Default")
    x.close("Condition")
    x.close("Group")
    x.close("Group")

    # ---- Weather slot (user-selectable complication) ------------------------
    x.comment("Weather disc: complication slot, the user picks a weather provider")
    D = 2 * INNER_R
    wx, wy = round(WEATHER_POS[0] - INNER_R), round(WEATHER_POS[1] - INNER_R)
    x.open("ComplicationSlot", slotId=1, name="weather", displayName="@string/slot_weather",
           x=wx, y=wy, width=D, height=D,
           supportedTypes="SHORT_TEXT RANGED_VALUE MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY",
           isCustomizable="TRUE")
    x.leaf("DefaultProviderPolicy", defaultSystemProvider="EMPTY", defaultSystemProviderType="EMPTY")
    x.leaf("BoundingOval", x=0, y=0, width=D, height=D)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    ir = INNER_R

    def slot_icon(size):
        x.open("PartImage", name="icon", x=round(ir - size / 2), y=round(ir - ir * 0.38 - size / 2),
               width=size, height=size, tintColor=ACCENT)
        x.leaf("Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")
        x.close("PartImage")

    x.open("Complication", type="SHORT_TEXT")
    disc(x, "disc", D)
    slot_icon(20)
    text_part(x, "value", 4, ir + ir * 0.27 - 13, D - 8, 26, INNER_VALUE, WHITE,
              template=("%s", ["[COMPLICATION.TEXT]"]), weight="MEDIUM")
    x.close("Complication")

    x.open("Complication", type="RANGED_VALUE")
    disc(x, "disc", D)
    x.open("PartDraw", name="ring", x=0, y=0, width=D, height=D)
    x.open("Arc", centerX=ir, centerY=ir, width=D - 8, height=D - 8, startAngle=0, endAngle=360)
    x.leaf("Stroke", color=TRACK, thickness=3, cap="ROUND")
    x.close("Arc")
    x.open("Arc", centerX=ir, centerY=ir, width=D - 8, height=D - 8, startAngle=0, endAngle=0)
    x.leaf("Stroke", color=ACCENT, thickness=3, cap="ROUND")
    x.leaf("Transform", target="endAngle",
           value="360 * clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN])"
                 " / max([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN], 1), 0, 1)")
    x.close("Arc")
    x.close("PartDraw")
    text_part(x, "value", 6, ir - 13, D - 12, 26, INNER_VALUE - 2, WHITE,
              template=("%s", ["[COMPLICATION.TEXT]"]), weight="MEDIUM")
    x.close("Complication")

    x.open("Complication", type="MONOCHROMATIC_IMAGE")
    disc(x, "disc", D)
    x.open("PartImage", name="icon", x=ir - 15, y=ir - 15, width=30, height=30, tintColor=ACCENT)
    x.leaf("Image", resource="[COMPLICATION.MONOCHROMATIC_IMAGE]")
    x.close("PartImage")
    x.close("Complication")

    x.open("Complication", type="SMALL_IMAGE")
    disc(x, "disc", D)
    x.open("PartImage", name="image", x=ir - 17, y=ir - 17, width=34, height=34)
    x.leaf("Image", resource="[COMPLICATION.SMALL_IMAGE]")
    x.close("PartImage")
    x.close("Complication")

    x.open("Complication", type="EMPTY")
    disc(x, "disc", D)
    x.close("Complication")
    x.close("ComplicationSlot")

    # ---- Calendar card: lower half ---------------------------------------------
    x.comment("Lower half: next calendar event (any SHORT_TEXT / LONG_TEXT provider can be chosen)")
    cw, ch = CAL_W, CAL_H
    cx0 = round(C - cw / 2)
    x.open("ComplicationSlot", slotId=0, name="next_event", displayName="@string/slot_bottom",
           x=cx0, y=CAL_Y, width=cw, height=ch, supportedTypes="LONG_TEXT SHORT_TEXT EMPTY",
           isCustomizable="TRUE")
    x.leaf("DefaultProviderPolicy", defaultSystemProvider="NEXT_EVENT",
           defaultSystemProviderType="LONG_TEXT")
    x.leaf("BoundingRoundBox", x=0, y=0, width=cw, height=ch, cornerRadius=CAL_RADIUS)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=170)

    def card() -> None:
        x.open("PartDraw", name="card", x=0, y=0, width=cw, height=ch)
        x.open("RoundRectangle", x=1, y=1, width=cw - 2, height=ch - 2,
               cornerRadiusX=CAL_RADIUS, cornerRadiusY=CAL_RADIUS)
        x.leaf("Stroke", color=EDGE, thickness=1.5)
        x.leaf("Fill", color=CARD)
        x.close("RoundRectangle")
        x.close("PartDraw")

    for ctype in ("LONG_TEXT", "SHORT_TEXT"):
        x.open("Complication", type=ctype)
        card()
        text_part(x, "event_time", 16, 10, cw - 32, 28, CAL_TIME_SIZE, ACCENT,
                  template=("%s", ["[COMPLICATION.TITLE]"]), weight="MEDIUM")
        text_part(x, "event_title", 16, 40, cw - 32, ch - 48, CAL_TITLE_SIZE, WHITE,
                  template=("%s", ["[COMPLICATION.TEXT]"]), weight="MEDIUM", max_lines=2)
        x.close("Complication")
    x.open("Complication", type="EMPTY")
    card()
    x.close("Complication")
    x.close("ComplicationSlot")

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
JP_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def render_preview(path: pathlib.Path, theme_idx=0, ambient=False, scale_out=1.0,
                   time=(10, 8, 36), data=None) -> None:
    from PIL import Image, ImageDraw, ImageFont

    data = data or dict(date="11月23日 月", batt=78, steps=6240, step_pct=62, hr=68, weather="18°",
                        ev_time="あと 46 分", ev_title=["ぶいすぽっ！GG 胡桃のあ", "presents 冬のスペシャル…"])
    S = 4
    W = SIZE * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)

    def col(hexs: str, alpha_mul=1.0):
        h = hexs.lstrip("#")
        a, r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, int(a * alpha_mul))

    _, acc_hex, *_ = THEMES[theme_idx]
    acc = col(acc_hex)

    def P(v):
        return v * S

    jp_path = next((p_ for p_ in JP_FONT_CANDIDATES if pathlib.Path(p_).exists()), None)

    def font(size, weight="Regular", jp=False):
        if jp and jp_path:
            return ImageFont.truetype(jp_path, int(size * S))
        return ImageFont.truetype(f"/usr/share/fonts/opentype/inter/Inter-{weight}.otf", int(size * S))

    def text(s_, cx, cy, size, color, weight="Regular"):
        jp = any(ord(ch) > 0x2FFF for ch in s_)
        fnt = font(size, weight, jp)
        l, t, r, b = d.textbbox((0, 0), s_, font=fnt)
        d.text((P(cx) - (l + r) / 2, P(cy) - (t + b) / 2), s_, font=fnt, fill=color)

    def line(x1, y1, x2, y2, color, w):
        d.line([P(x1), P(y1), P(x2), P(y2)], fill=color, width=int(w * S))
        for xx, yy in ((x1, y1), (x2, y2)):
            rr = w * S / 2
            d.ellipse([P(xx) - rr, P(yy) - rr, P(xx) + rr, P(yy) + rr], fill=color)

    def arcp(a0, a1, color):
        if a1 <= a0:
            return
        bb = [P(C - ARC_R), P(C - ARC_R), P(C + ARC_R), P(C + ARC_R)]
        d.arc(bb, a0 - 90, a1 - 90, fill=color, width=ARC_THICK * S)
        for a in (a0, a1):
            xx, yy = polar(ARC_R - ARC_THICK / 2, a)
            rr = ARC_THICK * S / 2
            d.ellipse([P(xx) - rr, P(yy) - rr, P(xx) + rr, P(yy) + rr], fill=color)

    def discp(cx, cy, r):
        d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=col(CARD), outline=col(EDGE),
                  width=int(1.5 * S))

    def icon(kind, x0, y0, color, s=1.15):
        if kind == "sun":
            r = 4.5 * s
            d.ellipse([P(x0 - r), P(y0 - r), P(x0 + r), P(y0 + r)], fill=color)
            for k in range(8):
                a = k * math.pi / 4
                line(x0 + 6.8 * s * math.sin(a), y0 - 6.8 * s * math.cos(a),
                     x0 + 8.8 * s * math.sin(a), y0 - 8.8 * s * math.cos(a), color, 1.6 * s)
        elif kind == "batt":
            w, h = 15 * s, 8 * s
            d.rounded_rectangle([P(x0 - w / 2), P(y0 - h / 2), P(x0 + w / 2), P(y0 + h / 2)],
                                radius=P(1.5 * s), outline=color, width=int(1.6 * S * s))
            d.rectangle([P(x0 + w / 2), P(y0 - 2 * s), P(x0 + w / 2 + 2 * s), P(y0 + 2 * s)], fill=color)
            d.rectangle([P(x0 - w / 2 + 2.5 * s), P(y0 - h / 2 + 2.5 * s), P(x0 - w / 2 + w * 0.75),
                         P(y0 + h / 2 - 2.5 * s)], fill=color)
        elif kind == "steps":
            for dx, dy in ((-3.5, 2.5), (3.5, -2.5)):
                fx, fy = x0 + dx * s, y0 + dy * s
                d.ellipse([P(fx - 2.6 * s), P(fy - 4.5 * s), P(fx + 2.6 * s), P(fy + 3 * s)], fill=color)
                d.ellipse([P(fx - 1.8 * s), P(fy + 3.8 * s), P(fx + 1.8 * s), P(fy + 6.6 * s)], fill=color)
        elif kind == "heart":
            q = 7.2 * s
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ox, oy = x0 - q, y0 - q * 0.95
            sq = (ox + q / 2, oy + q / 2)
            ld.rectangle([P(sq[0]), P(sq[1]), P(sq[0] + q), P(sq[1] + q)], fill=color)
            for ex, ey in ((q / 2, 0), (0, q / 2)):
                ld.ellipse([P(ox + ex), P(oy + ey), P(ox + ex + q), P(oy + ey + q)], fill=color)
            layer = layer.rotate(-45, resample=Image.BICUBIC, center=(P(ox + q), P(oy + q)))
            img.alpha_composite(layer)

    # dial
    if not ambient:
        for i in range(60):
            if i % 5:
                x1, y1 = polar(MIN_TICK_IN, i * 6)
                x2, y2 = polar(MIN_TICK_OUT, i * 6)
                line(x1, y1, x2, y2, col(DIM), 2)
    for h in range(1, 12):
        x1, y1 = polar(HOUR_TICK_IN, h * 30)
        x2, y2 = polar(HOUR_TICK_OUT, h * 30)
        line(x1, y1, x2, y2, col(WHITE if h % 3 == 0 else "#FFB4B8BE", 150 / 255 if ambient else 1),
             5 if h % 3 == 0 else 3.5)
    for dx in (-4.5, 4.5):
        line(C + dx, C - TWELVE_OUT, C + dx, C - TWELVE_IN, acc, 4)

    if not ambient:
        # gauges
        arcp(BATT_START, BATT_START + BATT_SPAN, col(TRACK))
        arcp(STEP_END - STEP_SPAN, STEP_END, col(TRACK))
        low = data["batt"] <= 15
        arcp(BATT_START, BATT_START + BATT_SPAN * data["batt"] / 100, col(LOW) if low else acc)
        arcp(STEP_END - STEP_SPAN * min(data["step_pct"], 100) / 100, STEP_END, acc)
        # discs
        for kind, pos, r, val, size, color in (
            ("batt", BATT_POS, OUTER_R, f'{data["batt"]}%', OUTER_VALUE, col(LOW) if low else col(WHITE)),
            ("steps", STEPS_POS, OUTER_R, str(data["steps"]),
             OUTER_VALUE_LONG if data["steps"] >= 10000 else OUTER_VALUE, col(WHITE)),
            ("sun", WEATHER_POS, INNER_R, data["weather"], INNER_VALUE, col(WHITE)),
            ("heart", HR_POS, INNER_R, str(data["hr"]), INNER_VALUE, col(WHITE)),
        ):
            cx, cy = pos
            discp(cx, cy, r)
            icon(kind, cx, cy - r * 0.38, acc)
            d = ImageDraw.Draw(img)
            text(val, cx, cy + r * 0.27, size, color, "Medium")

    da = 200 / 255 if ambient else 1
    text(data["date"], C, DATE_Y, DATE_SIZE, col(acc_hex, da), "Medium")

    # calendar card
    ca = 170 / 255 if ambient else 1
    x0 = C - CAL_W / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [P(x0 + 1), P(CAL_Y + 1), P(x0 + CAL_W - 1), P(CAL_Y + CAL_H - 1)], radius=P(CAL_RADIUS),
        fill=col(CARD, ca), outline=col(EDGE, ca), width=int(1.5 * S))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    text(data["ev_time"], C, CAL_Y + 24, CAL_TIME_SIZE, col(acc_hex, ca), "Medium")
    lines_ = data["ev_title"][:2]
    lh = CAL_TITLE_SIZE * 1.45
    top = CAL_Y + 40 + (CAL_H - 48 - lh * len(lines_)) / 2 + lh / 2
    for i, ln in enumerate(lines_):
        text(ln, C, top + i * lh, CAL_TITLE_SIZE, col(WHITE, ca), "Medium")

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
                              radius=P(SEC_W / 2), fill=acc)
        ldr.ellipse([P(C - 6), P(C - 6), P(C + 6), P(C + 6)], fill=acc)
        layer = layer.rotate(-ss * 6, resample=Image.BICUBIC, center=(P(C), P(C)))
        img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.ellipse([P(C - 2.5), P(C - 2.5), P(C + 2.5), P(C + 2.5)], fill=(0, 0, 0, 255))

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
        "slot_bottom": "Lower half (calendar)",
        "slot_weather": "Weather",
    }
    ja = {
        "app_name": "Meridian",
        "config_theme": "テーマカラー",
        "config_seconds": "秒針",
        "config_gauges": "バッテリー / 歩数ゲージ",
        "slot_bottom": "下半分（カレンダー）",
        "slot_weather": "天気",
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
                   data=dict(date="11月24日 火", batt=12, steps=11200, step_pct=100, hr=74, weather="9°",
                             ev_time="09:30", ev_title=["定例ミーティング"]))

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
