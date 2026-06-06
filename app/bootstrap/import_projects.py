"""Import project settings from the first worksheet of an XLSX file."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import app.core.models  # noqa: F401
from app.core.db import SessionFactory
from app.modules.projects.domain import CrawlSegment
from app.modules.projects.infrastructure import Project, ProjectRepository

XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RELS_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DEFAULT_IMPORT_PATH = Path("storage/imports/settings.xlsx")


@dataclass(slots=True, frozen=True)
class ImportRow:
    """Normalized project import row."""

    project_name: str
    sitemap_path: str
    start_url: str
    crawl_segment: CrawlSegment
    is_multi_sitemap: bool
    pagination_view: str | None
    yandex_webmaster_host: str | None
    pagination_sample: str | None
    pagination_marker: str | None
    card_sample: str | None
    category_sample: str | None
    contain_subdomains: bool


def main() -> None:
    """Run the XLSX import into the projects table."""

    args = _build_parser().parse_args()
    xlsx_path = Path(args.xlsx_path)
    imported_rows = _read_first_worksheet_rows(xlsx_path)

    session = SessionFactory()
    repository = ProjectRepository(session)
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    try:
        for row_number, row_values in imported_rows:
            try:
                import_row = _build_import_row(row_values)
            except ValueError as error:
                skipped += 1
                errors.append(f"Строка {row_number}: {error}")
                continue

            try:
                existing_project = repository.get_by_name(import_row.project_name)
                if existing_project is None:
                    repository.create(_to_project(import_row))
                    session.commit()
                    created += 1
                else:
                    _apply_import_row(existing_project, import_row)
                    repository.update(existing_project)
                    session.commit()
                    updated += 1
            except Exception as error:
                session.rollback()
                skipped += 1
                errors.append(f"Строка {row_number} ({import_row.project_name}): {error}")

    finally:
        session.close()

    print(f"Импорт завершён: создано={created}, обновлено={updated}, пропущено={skipped}")
    if errors:
        print("Проблемные строки:")
        for error in errors:
            print(f"- {error}")


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(description="Import projects from the first worksheet of an XLSX file.")
    parser.add_argument(
        "--xlsx-path",
        default=str(DEFAULT_IMPORT_PATH),
        help="Path to the XLSX file with project settings.",
    )
    return parser


def _read_first_worksheet_rows(xlsx_path: Path) -> list[tuple[int, dict[str, str]]]:
    """Read data rows from the first worksheet of an XLSX workbook."""

    if not xlsx_path.exists():
        raise FileNotFoundError(f"Файл не найден: {xlsx_path}")

    with ZipFile(xlsx_path) as workbook_zip:
        shared_strings = _read_shared_strings(workbook_zip)
        sheet_path = _resolve_first_sheet_path(workbook_zip)
        sheet_xml = ET.fromstring(workbook_zip.read(sheet_path))

    row_maps = _read_sheet_row_maps(sheet_xml, shared_strings)
    if not row_maps:
        return []

    header_row_number, header_row_map = row_maps[0]
    headers = [header_row_map[index].strip() for index in sorted(header_row_map) if header_row_map[index].strip()]
    if not headers:
        raise ValueError(f"В первом листе файла {xlsx_path} не найдены заголовки.")

    header_index_to_name = {
        index: header_row_map[index].strip()
        for index in sorted(header_row_map)
        if header_row_map[index].strip()
    }

    data_rows: list[tuple[int, dict[str, str]]] = []
    for row_number, row_map in row_maps[1:]:
        row_values = {
            header_name: row_map.get(index, "").strip()
            for index, header_name in header_index_to_name.items()
        }
        if not any(value for value in row_values.values()):
            continue
        data_rows.append((row_number, row_values))

    _ = header_row_number
    return data_rows


def _read_shared_strings(workbook_zip: ZipFile) -> list[str]:
    """Read shared strings from an XLSX archive."""

    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    shared_strings_xml = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    shared_strings: list[str] = []
    for item in shared_strings_xml.findall("main:si", XLSX_NS):
        parts = [text_node.text or "" for text_node in item.iterfind(".//main:t", XLSX_NS)]
        shared_strings.append("".join(parts))
    return shared_strings


def _resolve_first_sheet_path(workbook_zip: ZipFile) -> str:
    """Resolve the archive path of the first worksheet."""

    workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
    relationships = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_xml.findall("rel:Relationship", RELS_NS)
    }

    first_sheet = workbook_xml.find("main:sheets/main:sheet", XLSX_NS)
    if first_sheet is None:
        raise ValueError("В XLSX-файле не найден ни один лист.")

    relationship_id = first_sheet.attrib.get(f"{{{OFFICE_REL_NS}}}id")
    if relationship_id is None or relationship_id not in relationships:
        raise ValueError("Не удалось определить путь к первому листу XLSX-файла.")

    return f"xl/{relationships[relationship_id].lstrip('/')}"


def _read_sheet_row_maps(sheet_xml: ET.Element, shared_strings: list[str]) -> list[tuple[int, dict[int, str]]]:
    """Convert worksheet XML rows into column-indexed string maps."""

    rows: list[tuple[int, dict[int, str]]] = []
    for row in sheet_xml.findall(".//main:sheetData/main:row", XLSX_NS):
        row_number = int(row.attrib.get("r", "0"))
        values_by_index: dict[int, str] = {}
        for cell in row.findall("main:c", XLSX_NS):
            cell_ref = cell.attrib.get("r")
            if cell_ref is None:
                continue
            column_index = _column_letters_to_index(cell_ref)
            values_by_index[column_index] = _read_cell_value(cell, shared_strings)
        rows.append((row_number, values_by_index))
    return rows


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    """Return a cell value as plain text."""

    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text_node.text or "" for text_node in cell.findall(".//main:t", XLSX_NS))

    value_node = cell.find("main:v", XLSX_NS)
    if value_node is None or value_node.text is None:
        return ""

    raw_value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return raw_value
    return raw_value


def _column_letters_to_index(cell_ref: str) -> int:
    """Convert an Excel cell reference like C12 into a zero-based column index."""

    letters = "".join(character for character in cell_ref if character.isalpha()).upper()
    index = 0
    for character in letters:
        index = index * 26 + (ord(character) - ord("A") + 1)
    return index - 1


def _build_import_row(row_values: dict[str, str]) -> ImportRow:
    """Validate and normalize one worksheet row."""

    project_name = _required_text(row_values, "project_name")
    sitemap_path = _required_text(row_values, "sitemap_path")

    return ImportRow(
        project_name=project_name,
        sitemap_path=sitemap_path,
        start_url=_derive_start_url_from_sitemap_path(sitemap_path),
        crawl_segment=CrawlSegment.DEFAULT,
        is_multi_sitemap=_as_bool(row_values.get("is_multi_sitemap")),
        pagination_view=_optional_text(row_values.get("pagination_view")),
        yandex_webmaster_host=_optional_text(row_values.get("webmaster_host")),
        pagination_sample=_optional_text(row_values.get("pagination_sample")),
        pagination_marker=_optional_text(row_values.get("pagination_marker")),
        card_sample=_optional_text(row_values.get("card_sample")),
        category_sample=_optional_text(row_values.get("category_sample")),
        contain_subdomains=_as_bool(row_values.get("contain_subdomains")),
    )


def _required_text(row_values: dict[str, str], field_name: str) -> str:
    """Return a required non-empty text field."""

    value = _optional_text(row_values.get(field_name))
    if value is None:
        raise ValueError(f"не заполнено обязательное поле '{field_name}'")
    return value


def _optional_text(value: str | None) -> str | None:
    """Normalize optional text values."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _as_bool(value: str | None) -> bool:
    """Convert spreadsheet boolean-like values to bool."""

    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "да"}


def _derive_start_url_from_sitemap_path(sitemap_path: str) -> str:
    """Derive a crawl start URL from the sitemap location."""

    normalized = sitemap_path.strip()
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlsplit(normalized)
    if not parsed.netloc:
        raise ValueError("не удалось вывести start_url из sitemap_path")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "/", "", ""))


def _to_project(import_row: ImportRow) -> Project:
    """Convert an import row into a new ORM project."""

    return Project(
        project_name=import_row.project_name,
        sitemap_path=import_row.sitemap_path,
        start_url=import_row.start_url,
        crawl_segment=import_row.crawl_segment,
        is_multi_sitemap=import_row.is_multi_sitemap,
        pagination_view=import_row.pagination_view,
        yandex_webmaster_host=import_row.yandex_webmaster_host,
        pagination_sample=import_row.pagination_sample,
        pagination_marker=import_row.pagination_marker,
        card_sample=import_row.card_sample,
        category_sample=import_row.category_sample,
        contain_subdomains=import_row.contain_subdomains,
    )


def _apply_import_row(project: Project, import_row: ImportRow) -> None:
    """Apply imported values to an existing project."""

    project.sitemap_path = import_row.sitemap_path
    project.start_url = import_row.start_url
    project.crawl_segment = import_row.crawl_segment
    project.is_multi_sitemap = import_row.is_multi_sitemap
    project.pagination_view = import_row.pagination_view
    project.yandex_webmaster_host = import_row.yandex_webmaster_host
    project.pagination_sample = import_row.pagination_sample
    project.pagination_marker = import_row.pagination_marker
    project.card_sample = import_row.card_sample
    project.category_sample = import_row.category_sample
    project.contain_subdomains = import_row.contain_subdomains


if __name__ == "__main__":
    main()
