"""Genera una imagen PNG con la parrilla de partidos para enviar por Telegram.

Se usa Pillow para no depender de un navegador headless. El diseno es una
tarjeta vertical con un bloque por partido: liga, equipos, hora y canal.
Si hay muchos partidos, se generan varias imagenes (paginas).
"""

import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Colombia: UTC-5 (independiente de la zona horaria del runner).
COL_TZ = timezone(timedelta(hours=-5))

WIDTH = 1080
PADDING = 56
CARD_HEIGHT = 154
CARD_GAP = 16
HEADER_HEIGHT = 238
FOOTER_HEIGHT = 80
MAX_PARTIDOS_POR_IMAGEN = 8

BG_TOP = (8, 13, 24)
BG_BOTTOM = (15, 23, 42)
CARD_BG = (20, 28, 46)
CARD_BORDER = (38, 52, 78)
WHITE = (248, 250, 252)
GRAY = (148, 163, 184)
ACCENT = (34, 211, 238)
AMBER = (251, 191, 36)
CHIP_BG = (30, 41, 59)
CHIP_BORDER = (51, 65, 85)

LEAGUE_COLORS = [
    (56, 189, 248),
    (167, 139, 250),
    (244, 114, 182),
    (251, 191, 36),
    (52, 211, 153),
    (251, 113, 133),
    (96, 165, 250),
    (249, 115, 22),
]

_FONT_PATHS = {
    False: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    True: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


@lru_cache(maxsize=64)
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carga una fuente del sistema y cae a la fuente por defecto si no existe."""
    for path in _FONT_PATHS[bold]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _split_teams(text: str) -> Tuple[str, str]:
    """Separa 'Equipo A VS Equipo B' o 'Equipo A-Equipo B'."""
    text = (text or "").strip()
    for separator in (" VS ", " vs ", " Vs ", " - "):
        if separator in text:
            left, right = text.split(separator, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()

    if "-" in text:
        left, right = text.split("-", 1)
        if left.strip() and right.strip():
            return left.strip(), right.strip()

    return text, ""


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(text, font=font))


def _truncate(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    """Recorta el texto con puntos suspensivos si no cabe en el ancho dado."""
    if max_width <= 0 or _text_width(draw, text, font) <= max_width:
        return text

    ellipsis = "..."
    while text and _text_width(draw, text + ellipsis, font) > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    sizes: List[int],
    bold: bool = False,
) -> Tuple[ImageFont.FreeTypeFont, str]:
    """Busca el tamano de fuente mas grande que haga caber el texto."""
    for size in sizes:
        font = _load_font(size, bold)
        if _text_width(draw, text, font) <= max_width:
            return font, text

    font = _load_font(sizes[-1], bold)
    return font, _truncate(draw, text, font, max_width)


def _league_color(league: str) -> Tuple[int, int, int]:
    key = sum(ord(char) for char in (league or ""))
    return LEAGUE_COLORS[key % len(LEAGUE_COLORS)]


def _time_sort_key(partido) -> Tuple[int, int]:
    """Ordena por hora; los 'Por confirmar' quedan al final."""
    hora = (getattr(partido, "hora", "") or "").strip().lower()
    match = re.search(r"(\d{1,2}):(\d{2})", hora)
    if not match:
        return (1, 0)

    hour = int(match.group(1))
    minute = int(match.group(2))
    if "p" in hora and hour < 12:
        hour += 12
    if "a" in hora and hour == 12:
        hour = 0

    return (0, hour * 60 + minute)


def _background(height: int) -> Image.Image:
    """Fondo con degradado vertical y un brillo suave arriba a la derecha."""
    gradient = Image.new("RGB", (1, height))
    pixels = gradient.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        pixels[0, y] = tuple(
            int(top + (bottom - top) * ratio)
            for top, bottom in zip(BG_TOP, BG_BOTTOM)
        )

    image = gradient.resize((WIDTH, height))
    image = image.convert("RGBA")

    glow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [WIDTH - 420, -260, WIDTH + 220, 360],
        fill=(34, 211, 238, 34),
    )
    glow_draw.ellipse(
        [-260, height - 300, 320, height + 160],
        fill=(167, 139, 250, 28),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(110))

    return Image.alpha_composite(image, glow).convert("RGB")


def _draw_header(
    draw: ImageDraw.ImageDraw,
    titulo: str,
    fecha: str,
    fuente: str,
    page: int,
    total_pages: int,
) -> None:
    draw.rectangle([0, 0, WIDTH, 8], fill=ACCENT)

    draw.text((PADDING, 40), "PARRILLA DE FÚTBOL", font=_load_font(22, True), fill=ACCENT)
    draw.text((PADDING, 74), titulo.upper(), font=_load_font(50, True), fill=WHITE)
    draw.text((PADDING, 146), fecha.upper(), font=_load_font(28), fill=GRAY)

    chip_font = _load_font(18, True)
    chip_text = (fuente or "").upper()
    chip_width = _text_width(draw, chip_text, chip_font) + 34
    chip_left = WIDTH - PADDING - chip_width
    chip_top = 52
    draw.rounded_rectangle(
        [chip_left, chip_top, WIDTH - PADDING, chip_top + 40],
        radius=20,
        fill=CHIP_BG,
        outline=CHIP_BORDER,
        width=1,
    )
    draw.text(
        (chip_left + 17, chip_top + 11),
        chip_text,
        font=chip_font,
        fill=GRAY,
    )

    if total_pages > 1:
        page_text = f"{page}/{total_pages}"
        page_font = _load_font(20, True)
        draw.text(
            (WIDTH - PADDING - _text_width(draw, page_text, page_font), 104),
            page_text,
            font=page_font,
            fill=ACCENT,
        )

    draw.line(
        [(PADDING, HEADER_HEIGHT - 24), (WIDTH - PADDING, HEADER_HEIGHT - 24)],
        fill=(30, 41, 59),
        width=2,
    )


def _draw_empty_state(draw: ImageDraw.ImageDraw, top: int) -> None:
    card_bottom = top + 190
    draw.rounded_rectangle(
        [PADDING, top, WIDTH - PADDING, card_bottom],
        radius=22,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=1,
    )
    draw.text(
        (WIDTH // 2, top + 95),
        "No se encontraron partidos para esta fecha.",
        font=_load_font(30, True),
        fill=GRAY,
        anchor="mm",
    )


def _draw_match(
    draw: ImageDraw.ImageDraw,
    partido,
    top: int,
) -> None:
    left = PADDING
    right = WIDTH - PADDING
    bottom = top + CARD_HEIGHT
    card_width = right - left

    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=18,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=1,
    )

    league = (getattr(partido, "liga", "") or "FUTBOL").strip()
    league_color = _league_color(league)
    draw.rounded_rectangle(
        [left, top + 14, left + 8, bottom - 14],
        radius=4,
        fill=league_color,
    )

    league_font = _load_font(21, True)
    draw.text(
        (left + 32, top + 18),
        _truncate(draw, league.upper(), league_font, card_width - 64),
        font=league_font,
        fill=league_color,
    )

    hora = (getattr(partido, "hora", "") or "").strip()
    time_font, hora = _fit_font(draw, hora, 235, [32, 28, 24, 20], bold=True)
    time_width = _text_width(draw, hora, time_font)
    time_left = right - 32 - time_width

    local, visitante = _split_teams(getattr(partido, "equipos_original", ""))
    teams_text = f"{local}  vs  {visitante}" if visitante else local

    teams_max_width = time_left - (left + 32) - 24
    teams_font, teams_text = _fit_font(
        draw,
        teams_text,
        teams_max_width,
        [34, 30, 26, 22],
        bold=True,
    )

    draw.text((left + 32, top + 54), teams_text, font=teams_font, fill=WHITE)
    if hora:
        draw.text((time_left, top + 56), hora, font=time_font, fill=AMBER)

    canal = (getattr(partido, "canal", "") or "").strip()
    if canal:
        channel_font = _load_font(20)
        draw.text(
            (left + 32, top + 112),
            _truncate(draw, f"TV  {canal}", channel_font, card_width - 64),
            font=channel_font,
            fill=GRAY,
        )


def _render_page(
    partidos: list,
    titulo: str,
    fecha: str,
    fuente: str,
    page: int,
    total_pages: int,
) -> bytes:
    if partidos:
        content_height = len(partidos) * CARD_HEIGHT + (len(partidos) - 1) * CARD_GAP
    else:
        content_height = 190

    height = max(720, HEADER_HEIGHT + content_height + 42 + FOOTER_HEIGHT)
    image = _background(height)
    draw = ImageDraw.Draw(image)

    _draw_header(draw, titulo, fecha, fuente, page, total_pages)

    top = HEADER_HEIGHT
    if partidos:
        for partido in partidos:
            _draw_match(draw, partido, top)
            top += CARD_HEIGHT + CARD_GAP
    else:
        _draw_empty_state(draw, top)

    updated = datetime.now(COL_TZ).strftime("%H:%M")
    footer = f"Actualizado {updated}  ·  Fuente: {fuente}"
    footer_font = _load_font(18)
    draw.text(
        ((WIDTH - _text_width(draw, footer, footer_font)) // 2, height - 46),
        footer,
        font=footer_font,
        fill=GRAY,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generar_imagenes_partidos(
    partidos: list,
    titulo: str,
    fecha: str,
    fuente: str,
    max_por_imagen: int = MAX_PARTIDOS_POR_IMAGEN,
) -> List[bytes]:
    """Retorna una o varias imagenes PNG, paginando si hay muchos partidos."""
    ordered = sorted(partidos, key=_time_sort_key) if partidos else []

    if ordered:
        chunks = [
            ordered[index : index + max_por_imagen]
            for index in range(0, len(ordered), max_por_imagen)
        ]
    else:
        chunks = [[]]

    total_pages = len(chunks)
    return [
        _render_page(chunk, titulo, fecha, fuente, page, total_pages)
        for page, chunk in enumerate(chunks, start=1)
    ]
