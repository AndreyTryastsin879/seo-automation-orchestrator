"""Regression checks for partial crawl report exports."""

import io
import unittest

from openpyxl import load_workbook

from app.interfaces.bot.services import _build_xlsx_bytes_from_rows


class PartialCrawlReportTests(unittest.TestCase):
    """Ensure checkpoint XLSX exports retain relative-link diagnostics."""

    def test_checkpoint_xlsx_has_relative_link_issues_sheet(self) -> None:
        workbook_bytes = _build_xlsx_bytes_from_rows(
            [
                ["Ответ сервера", "URL страницы"],
                ["200", "https://example.com/"],
            ],
            [
                ["Источник", "Исходный href", "Получившийся URL"],
                ["https://example.com/", "catalog", "https://example.com/catalog"],
            ],
        )

        workbook = load_workbook(io.BytesIO(workbook_bytes), read_only=True)
        self.assertEqual(workbook.sheetnames, ["crawl_pages", "relative_link_issues"])
        self.assertEqual(
            list(workbook["relative_link_issues"].iter_rows(values_only=True)),
            [
                ("Источник", "Исходный href", "Получившийся URL"),
                ("https://example.com/", "catalog", "https://example.com/catalog"),
            ],
        )
