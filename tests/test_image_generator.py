"""Pruebas locales del render: sin scraping ni envíos a Telegram."""

import sys
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from image_generator import generar_imagenes_partidos, WIDTH, _time_sort_key


def match(**changes):
    values = dict(
        equipos_original="Atlético Nacional VS Independiente Medellín",
        liga="Liga BetPlay Dimayor",
        hora="18:30",
        canal="Win Sports+ / Win Play",
    )
    values.update(changes)
    return SimpleNamespace(**values)


class ImageGeneratorTests(unittest.TestCase):
    def render(self, items, **kwargs):
        return generar_imagenes_partidos(
            items, "Partidos de hoy", "12 de noviembre", "futbolred.com", **kwargs
        )

    def test_pagination_and_telegram_dimensions(self):
        pages = self.render([match() for _ in range(19)])
        self.assertEqual(len(pages), 3)
        for png in pages:
            with Image.open(BytesIO(png)) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.width, WIDTH)
                self.assertLess(image.width + image.height, 10000)
                self.assertLess(max(image.size) / min(image.size), 20)
                image.verify()
            self.assertLess(len(png), 10 * 1024 * 1024)

    def test_empty_and_long_fields(self):
        for items in ([], [match(
            equipos_original="Equipo con un nombre muy largo " * 8,
            liga="Competición internacional " * 12,
            hora="Por confirmar",
            canal="Canal de televisión / " * 20,
        )]):
            pages = self.render(items)
            self.assertEqual(len(pages), 1)
            with Image.open(BytesIO(pages[0])) as image:
                image.verify()

    def test_sort_does_not_mutate_input(self):
        items = [match(hora="20:00"), match(hora="08:00")]
        self.render(items)
        self.assertEqual(items[0].hora, "20:00")
        self.assertLess(_time_sort_key(items[1]), _time_sort_key(items[0]))

    def test_invalid_page_size(self):
        for size in (0, -1, 9):
            with self.assertRaises(ValueError):
                self.render([match()], max_por_imagen=size)


if __name__ == "__main__":
    unittest.main()
