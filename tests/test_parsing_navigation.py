"""Regression checks for inline navigation in the parsing section."""

from types import SimpleNamespace
import unittest

from app.interfaces.bot.keyboards import (
    build_adhoc_profile_keyboard,
    build_confirm_all_projects_keyboard,
    build_confirm_stop_parsing_keyboard,
    build_heavy_project_selection_keyboard,
    build_heavy_settings_menu_keyboard,
    build_indexing_actions_keyboard,
    build_indexnow_actions_keyboard,
    build_indexnow_key_mode_keyboard,
    build_indexnow_project_keyboard,
    build_indexnow_projects_keyboard,
    build_indexnow_sitemap_projects_keyboard,
    build_main_menu_keyboard,
    build_parsing_actions_keyboard,
    build_parsing_back_keyboard,
    build_parsing_settings_keyboard,
    build_project_card_keyboard,
    build_project_fields_keyboard,
    build_project_selection_keyboard,
    build_projects_list_keyboard,
    build_recent_batches_keyboard,
    build_robots_project_selection_keyboard,
    build_sitemap_actions_keyboard,
    build_sitemap_back_keyboard,
    build_sitemap_project_selection_keyboard,
    build_sitemap_robots_actions_keyboard,
    build_sitemap_settings_keyboard,
    build_static_sitemap_actions_keyboard,
    build_static_sitemap_projects_keyboard,
    build_url_list_collect_keyboard,
    build_url_list_profile_keyboard,
    build_yandex_recrawl_project_keyboard,
    build_yandex_recrawl_projects_keyboard,
    build_yandex_token_actions_keyboard,
    build_yandex_webmaster_actions_keyboard,
)
from app.interfaces.bot.services import CrawlLaunchSettings


def _callback_data(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    }


class ParsingNavigationKeyboardTests(unittest.TestCase):
    """Ensure every first-level parsing sub-screen has a return action."""

    def test_parsing_subscreens_include_back_callback(self) -> None:
        project = SimpleNamespace(id=1, project_name="Example")
        batch = SimpleNamespace(
            batch_id=1,
            title="Example",
            status="pending",
            finished_tasks=0,
            total_tasks=1,
        )
        settings = CrawlLaunchSettings(
            max_depth=3,
            max_concurrency=5,
            max_pages=1000,
            respect_robots_disallow=True,
            delay_between_requests_ms=0,
            request_timeout_seconds=30,
            retry_on_5xx=True,
            max_5xx_before_stop=10,
            retry_delay_ms=1000,
        )
        keyboards = (
            build_parsing_back_keyboard(),
            build_adhoc_profile_keyboard(),
            build_url_list_profile_keyboard(),
            build_url_list_collect_keyboard(url_count=0),
            build_project_selection_keyboard([project]),
            build_heavy_project_selection_keyboard([project]),
            build_confirm_all_projects_keyboard(),
            build_confirm_stop_parsing_keyboard(),
            build_recent_batches_keyboard([batch], include_parsing_back=True),
            build_parsing_settings_keyboard(
                current_depth=3,
                current_concurrency=5,
                current_pages=1000,
                current_respect_robots=True,
            ),
            build_heavy_settings_menu_keyboard(settings),
        )

        for keyboard in keyboards:
            self.assertIn("parsing:back", _callback_data(keyboard))

    def test_parsing_menu_does_not_include_recent_launches(self) -> None:
        self.assertNotIn("parsing:recent", _callback_data(build_parsing_actions_keyboard()))

    def test_main_menu_uses_visual_section_markers(self) -> None:
        labels = [button.text for row in build_main_menu_keyboard().keyboard for button in row]
        self.assertEqual(
            labels,
            [
                "🔎 Парсинг",
                "🗺 Парсинг sitemap",
                "📤 Индексирование",
                "📁 Проекты",
                "📊 Статус",
                "👥 Доступ",
            ],
        )

    def test_sitemap_indexing_and_projects_subscreens_include_back_callback(self) -> None:
        project = SimpleNamespace(
            id=1,
            project_name="Example",
            crawl_segment=SimpleNamespace(value="default"),
            sitemap_path="/sitemap.xml",
        )
        indexed_project = SimpleNamespace(project=project, queue_count=0, has_key=True)
        sitemap_project = SimpleNamespace(project=project, has_sitemap_export=True)
        static_project = SimpleNamespace(project=project, static_map_count=1, has_yandex_host=True)
        yandex_project = SimpleNamespace(project=project, queue_count=0, has_yandex_host=True)
        keyboards_and_callbacks = (
            (build_sitemap_project_selection_keyboard([project]), "sitemap:back"),
            (build_robots_project_selection_keyboard([project]), "sitemap:robots:back"),
            (
                build_sitemap_settings_keyboard(
                    resolve_status_codes=True,
                    replace_yandex_recrawl_queue=False,
                ),
                "sitemap:back",
            ),
            (build_sitemap_robots_actions_keyboard(), "sitemap:back"),
            (build_sitemap_back_keyboard(), "sitemap:back"),
            (build_yandex_webmaster_actions_keyboard(), "indexing:back"),
            (build_yandex_recrawl_projects_keyboard([yandex_project]), "indexing:yandex:back"),
            (build_yandex_recrawl_project_keyboard(1, queue_count=0), "indexing:yandex:recrawl:back"),
            (build_yandex_token_actions_keyboard(), "indexing:back"),
            (build_indexnow_actions_keyboard(), "indexing:back"),
            (build_indexnow_projects_keyboard([indexed_project], mode="submit"), "indexing:indexnow:back"),
            (build_indexnow_sitemap_projects_keyboard([sitemap_project]), "indexing:indexnow:back"),
            (build_indexnow_key_mode_keyboard(1), "indexing:indexnow:settings:back"),
            (build_indexnow_project_keyboard(1, queue_count=0), "indexing:indexnow:submit:back"),
            (build_static_sitemap_actions_keyboard(), "indexing:back"),
            (build_static_sitemap_projects_keyboard([static_project], action="create"), "indexing:static:back"),
            (build_projects_list_keyboard([project]), "projects:back"),
            (build_project_card_keyboard(1), "projects:list"),
            (build_project_fields_keyboard(1), "projects:view:1"),
        )

        for keyboard, callback_data in keyboards_and_callbacks:
            self.assertIn(callback_data, _callback_data(keyboard))
