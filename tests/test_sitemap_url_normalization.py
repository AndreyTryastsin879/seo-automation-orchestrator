"""Regression checks for malformed URL locations in XML sitemaps."""

import unittest
from xml.etree import ElementTree

from app.interfaces.worker.jobs import _extract_sitemap_locations


class SitemapUrlNormalizationTests(unittest.TestCase):
    """Ensure sitemap URL entries are safe to pass to HTTP clients."""

    def test_raw_space_in_sitemap_location_is_percent_encoded(self) -> None:
        root = ElementTree.fromstring(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://www.stayer.su/catalog/aksessuary gornolyzhnye-men</loc></url>
            </urlset>
            """
        )

        self.assertEqual(
            _extract_sitemap_locations(root),
            ["https://www.stayer.su/catalog/aksessuary%20gornolyzhnye-men"],
        )

    def test_cyrillic_in_sitemap_location_is_percent_encoded(self) -> None:
        root = ElementTree.fromstring(
            """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://example.com/catalog/снаряжение</loc></url>
            </urlset>
            """
        )

        self.assertEqual(
            _extract_sitemap_locations(root),
            ["https://example.com/catalog/%D1%81%D0%BD%D0%B0%D1%80%D1%8F%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5"],
        )
