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
PADDING = 48
CARD_HEIGHT = 192
CARD_GAP = 18
HEADER_HEIGHT = 330
FOOTER_HEIGHT = 86
MAX_PARTIDOS_POR_IMAGEN = 8

BG_TOP = (10, 21, 26)
BG_BOTTOM = (7, 13, 20)
CARD_BG = (18, 30, 38)
CARD_BORDER = (37, 53, 62)
WHITE = (248, 250, 252)
GRAY = (148, 163, 184)
ACCENT = (193, 249, 95)
AMBER = (193, 249, 95)

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
        fill=(118, 190, 86, 35),
    )
    glow_draw.ellipse(
        [-260, height - 300, 320, height + 160],
        fill=(51, 141, 165, 22),
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
    # Geometría de campo: decoración discreta, sin recursos externos.
    field = (38, 57, 58)
    draw.rounded_rectangle([755, 90, 1170, 260], radius=20, outline=field, width=2)
    draw.line([(962, 90), (962, 260)], fill=field, width=2)
    draw.ellipse([907, 120, 1017, 230], outline=field, width=2)
    draw.ellipse([957, 170, 967, 180], fill=field)

    draw.rounded_rectangle([PADDING, 42, PADDING + 42, 84], radius=12, fill=ACCENT)
    draw.ellipse([PADDING + 10, 52, PADDING + 32, 74], outline=BG_TOP, width=2)
    draw.line([(PADDING + 21, 53), (PADDING + 21, 73)], fill=BG_TOP, width=2)
    draw.text((PADDING + 58, 63), "FÚTBOL / AGENDA TV", font=_load_font(20, True), fill=ACCENT, anchor="lm")

    page_text = f"EDICIÓN  {page:02d} / {total_pages:02d}"
    draw.text((WIDTH - PADDING, 63), page_text, font=_load_font(18, True), fill=GRAY, anchor="rm")
    title_font, title = _fit_font(draw, titulo.upper(), WIDTH - 2 * PADDING, [62, 56, 50, 44, 36], True)
    draw.text((PADDING, 140), title, font=title_font, fill=WHITE, anchor="lm")
    draw.text((PADDING, 204), fecha.upper(), font=_load_font(28), fill=WHITE, anchor="lm")

    draw.line([(PADDING, 251), (WIDTH - PADDING, 251)], fill=CARD_BORDER, width=2)
    draw.rounded_rectangle([PADDING, 250, PADDING + 80, 253], radius=1, fill=ACCENT)
    draw.text((PADDING, 284), "LA JORNADA, DE UN VISTAZO", font=_load_font(17, True), fill=GRAY, anchor="lm")
    draw.text((WIDTH - PADDING, 284), "HORARIO COLOMBIA · UTC−5", font=_load_font(17, True), fill=ACCENT, anchor="rm")


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

    # Sombra dura sutil y borde superior para separar las superficies.
    draw.rounded_rectangle([left, top + 5, right, bottom + 5], radius=22, fill=(5, 10, 15))
    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=22,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=1,
    )

    league = (getattr(partido, "liga", "") or "FUTBOL").strip()
    league_color = _league_color(league)
    draw.ellipse([left + 25, top + 24, left + 33, top + 32], fill=league_color)
    league_font = _load_font(17, True)
    draw.text(
        (left + 44, top + 29),
        _truncate(draw, league.upper(), league_font, card_width - 325),
        font=league_font,
        fill=league_color,
        anchor="lm",
    )

    hora = (getattr(partido, "hora", "") or "").strip()
    time_font, hora = _fit_font(draw, hora or "Por confirmar", 208, [29, 26, 22, 18], bold=True)
    time_left = right - 254
    draw.rounded_rectangle([time_left, top + 20, right - 20, top + 125], radius=17, fill=(30, 46, 40), outline=(53, 76, 48))
    time_center = (time_left + right - 20) // 2
    draw.text((time_center, top + 43), "INICIO", font=_load_font(13, True), fill=(151, 173, 147), anchor="mm")
    draw.text((time_center, top + 84), hora, font=time_font, fill=AMBER, anchor="mm")

    local, visitante = _split_teams(getattr(partido, "equipos_original", ""))
    teams_max_width = time_left - (left + 28) - 24
    # Dos líneas: los nombres largos no compiten con el horario.
    for team, y in ((local, top + 72), (visitante, top + 112)):
        if team:
            team_font, label = _fit_font(draw, team, teams_max_width, [32, 29, 26, 23, 20], True)
            draw.text((left + 28, y), label, font=team_font, fill=WHITE, anchor="lm")

    draw.line([(left + 24, top + 141), (right - 24, top + 141)], fill=CARD_BORDER, width=1)

    canal = (getattr(partido, "canal", "") or "").strip()
    if canal:
        channel_font = _load_font(18)
        # Icono TV vectorial: no depende de soporte de emojis.
        draw.rounded_rectangle([left + 28, top + 155, left + 50, top + 171], radius=3, outline=GRAY, width=2)
        draw.line([(left + 34, top + 175), (left + 44, top + 175)], fill=GRAY, width=2)
        draw.text(
            (left + 64, top + 164),
            _truncate(draw, canal, channel_font, card_width - 92),
            font=channel_font,
            fill=GRAY,
            anchor="lm",
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
    footer_font = _load_font(16)
    draw.ellipse([PADDING, height - 48, PADDING + 6, height - 42], fill=ACCENT)
    draw.text((PADDING + 17, height - 45), f"Actualizado {updated} · Colombia", font=footer_font, fill=GRAY, anchor="lm")
    source_label = _truncate(draw, f"Fuente: {fuente}", footer_font, 480)
    draw.text((WIDTH - PADDING, height - 45), source_label, font=footer_font, fill=GRAY, anchor="rm")

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
    if not 1 <= max_por_imagen <= MAX_PARTIDOS_POR_IMAGEN:
        raise ValueError(f"max_por_imagen debe estar entre 1 y {MAX_PARTIDOS_POR_IMAGEN}")
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
