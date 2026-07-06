"""Keyboard builders for Telegram bot interface."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.interfaces.bot.services import RecentBatchSummary, RecentTaskSummary
from app.interfaces.bot.services import CrawlLaunchSettings
from app.modules.bot_access.application import BotAccessUserDTO
from app.modules.projects.application import ProjectDTO


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build the persistent top-level bot menu."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Парсинг"), KeyboardButton(text="Парсинг sitemap")],
            [KeyboardButton(text="Проекты"), KeyboardButton(text="Статус")],
            [KeyboardButton(text="Доступ")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери раздел",
    )


def build_phone_access_keyboard() -> ReplyKeyboardMarkup:
    """Build a one-button keyboard for sharing the user's phone number."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером телефона", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажми кнопку ниже, чтобы подтвердить доступ",
    )


def build_parsing_actions_keyboard() -> InlineKeyboardMarkup:
    """Build context actions for the parsing section."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Список обычных проектов", callback_data="parsing:projects")
    builder.button(text="Список тяжелых проектов", callback_data="parsing:heavy_projects")
    builder.button(text="Парсить свой URL", callback_data="parsing:adhoc")
    builder.button(text="Список URL", callback_data="parsing:url_list")
    builder.button(text="Настройки обычных", callback_data="parsing:settings")
    builder.button(text="Настройки тяжелых", callback_data="parsing:heavy_settings")
    builder.button(text="Последние запуски", callback_data="parsing:recent")
    builder.button(text="Остановить парсинг", callback_data="parsing:stop")
    builder.adjust(1)
    return builder.as_markup()


def build_adhoc_profile_keyboard() -> InlineKeyboardMarkup:
    """Build a profile picker for ad-hoc crawl launches."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Обычные настройки", callback_data="parsing:adhoc:default")
    builder.button(text="Heavy-настройки", callback_data="parsing:adhoc:heavy")
    builder.button(text="Отмена", callback_data="parsing:adhoc:cancel")
    builder.adjust(1)
    return builder.as_markup()


def build_url_list_profile_keyboard() -> InlineKeyboardMarkup:
    """Build a profile picker for fixed URL list crawl launches."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Обычные настройки", callback_data="parsing:url_list:default")
    builder.button(text="Heavy-настройки", callback_data="parsing:url_list:heavy")
    builder.button(text="Отмена", callback_data="parsing:url_list:cancel")
    builder.adjust(1)
    return builder.as_markup()


def build_url_list_collect_keyboard(*, url_count: int) -> InlineKeyboardMarkup:
    """Build actions for accumulating a multi-message URL list."""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"Запустить список ({url_count})", callback_data="parsing:url_list:launch")
    builder.button(text="Очистить список", callback_data="parsing:url_list:reset")
    builder.button(text="Отмена", callback_data="parsing:url_list:cancel")
    builder.adjust(1)
    return builder.as_markup()


def build_sitemap_actions_keyboard() -> InlineKeyboardMarkup:
    """Build context actions for the sitemap parsing section."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Выбрать проект", callback_data="sitemap:projects")
    builder.button(text="Свой URL", callback_data="sitemap:adhoc")
    builder.button(text="Из robots.txt", callback_data="sitemap:robots")
    builder.button(text="Настройки", callback_data="sitemap:settings")
    builder.adjust(1)
    return builder.as_markup()


def build_sitemap_settings_keyboard(*, resolve_status_codes: bool) -> InlineKeyboardMarkup:
    """Build sitemap parsing settings keyboard."""

    builder = InlineKeyboardBuilder()
    state_text = "ON" if resolve_status_codes else "OFF"
    builder.button(
        text=f"Определять код ответа сервера: {state_text}",
        callback_data="sitemap:settings:toggle:resolve_status_codes",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_sitemap_robots_actions_keyboard() -> InlineKeyboardMarkup:
    """Build actions for robots.txt-based sitemap discovery."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Выбрать проект", callback_data="sitemap:robots:projects")
    builder.button(text="Свой URL", callback_data="sitemap:robots:adhoc")
    builder.adjust(1)
    return builder.as_markup()


def build_projects_actions_keyboard() -> InlineKeyboardMarkup:
    """Build context actions for the projects section."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Список", callback_data="projects:list")
    builder.button(text="Добавить", callback_data="projects:add")
    builder.button(text="Редактировать", callback_data="projects:edit")
    builder.button(text="Удалить", callback_data="projects:delete")
    builder.adjust(1)
    return builder.as_markup()


def build_access_actions_keyboard() -> InlineKeyboardMarkup:
    """Build actions for bot access management."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Список пользователей", callback_data="access:list")
    builder.button(text="Добавить пользователя", callback_data="access:add")
    builder.adjust(1)
    return builder.as_markup()


def build_access_users_keyboard(users: list[BotAccessUserDTO]) -> InlineKeyboardMarkup:
    """Build a removable user list keyboard for non-root bot users."""

    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(
            text=f"Удалить {user.phone_number}",
            callback_data=f"access:delete:{user.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_projects_list_keyboard(projects: list[ProjectDTO], *, mode: str = "view") -> InlineKeyboardMarkup:
    """Build a project selection keyboard for management flows."""

    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(text=project.project_name, callback_data=f"projects:{mode}:{project.id}")
    builder.adjust(1)
    return builder.as_markup()


def build_project_card_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Build actions for a single project card."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить поле", callback_data=f"projects:fields:{project_id}")
    builder.button(text="Удалить", callback_data=f"projects:delete:{project_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_project_fields_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Build a field selection keyboard for one project."""

    builder = InlineKeyboardBuilder()
    fields = (
        ("Название", "project_name"),
        ("Сегмент", "crawl_segment"),
        ("Start URL", "start_url"),
        ("Sitemap", "sitemap_path"),
        ("Yandex host", "yandex_webmaster_host"),
        ("Subdomains", "contain_subdomains"),
        ("Multi sitemap", "is_multi_sitemap"),
        ("Pagination view", "pagination_view"),
        ("Pagination sample", "pagination_sample"),
        ("Pagination marker", "pagination_marker"),
        ("Card sample", "card_sample"),
        ("Category sample", "category_sample"),
    )
    for label, field_name in fields:
        builder.button(text=label, callback_data=f"projects:field:{project_id}:{field_name}")
    builder.adjust(1)
    return builder.as_markup()


def build_project_segment_keyboard(*, callback_prefix: str, current_segment: str | None = None) -> InlineKeyboardMarkup:
    """Build a keyboard for choosing the project segment."""

    builder = InlineKeyboardBuilder()
    default_prefix = "• " if current_segment == "default" else ""
    heavy_prefix = "• " if current_segment == "heavy" else ""
    builder.button(text=f"{default_prefix}Обычный", callback_data=f"{callback_prefix}:default")
    builder.button(text=f"{heavy_prefix}Heavy", callback_data=f"{callback_prefix}:heavy")
    builder.adjust(1)
    return builder.as_markup()


def build_project_boolean_keyboard(*, callback_prefix: str, current_value: bool | None = None) -> InlineKeyboardMarkup:
    """Build a yes/no keyboard for project boolean steps."""

    builder = InlineKeyboardBuilder()
    yes_prefix = "• " if current_value is True else ""
    no_prefix = "• " if current_value is False else ""
    builder.button(text=f"{yes_prefix}Да", callback_data=f"{callback_prefix}:yes")
    builder.button(text=f"{no_prefix}Нет", callback_data=f"{callback_prefix}:no")
    builder.adjust(1)
    return builder.as_markup()


def build_project_text_action_keyboard(*, skip_label: str) -> InlineKeyboardMarkup:
    """Build a one-button keyboard for optional text steps."""

    builder = InlineKeyboardBuilder()
    builder.button(text=skip_label, callback_data="projects:wizard:text:skip")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_delete_project_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Build a confirmation keyboard for deleting a project."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=f"projects:delete:confirm:{project_id}")
    builder.button(text="Отмена", callback_data=f"projects:delete:cancel:{project_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_status_actions_keyboard() -> InlineKeyboardMarkup:
    """Build context actions for task status section."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Последние запуски", callback_data="status:recent")
    builder.button(text="Проверить по task_id", callback_data="status:by_id")
    builder.adjust(1)
    return builder.as_markup()


def build_project_selection_keyboard(projects: list[ProjectDTO]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for choosing a project to crawl."""

    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(
            text=project.project_name,
            callback_data=f"parsing:project:{project.id}",
        )
    builder.button(text="Парсить все", callback_data="parsing:all")
    builder.adjust(1)
    return builder.as_markup()


def build_sitemap_project_selection_keyboard(projects: list[ProjectDTO]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for choosing a project for sitemap parsing."""

    builder = InlineKeyboardBuilder()
    for project in projects:
        suffix = " [heavy]" if project.crawl_segment.value == "heavy" else ""
        builder.button(
            text=f"{project.project_name}{suffix}",
            callback_data=f"sitemap:project:{project.id}",
        )
    builder.button(text="Парсить все", callback_data="sitemap:all")
    builder.adjust(1)
    return builder.as_markup()


def build_robots_project_selection_keyboard(projects: list[ProjectDTO]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for choosing a project for robots.txt parsing."""

    builder = InlineKeyboardBuilder()
    for project in projects:
        suffix = " [heavy]" if project.crawl_segment.value == "heavy" else ""
        builder.button(
            text=f"{project.project_name}{suffix}",
            callback_data=f"sitemap:robots:project:{project.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_heavy_project_selection_keyboard(projects: list[ProjectDTO]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for choosing a heavy project to crawl."""

    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(
            text=project.project_name,
            callback_data=f"parsing:heavy_project:{project.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_all_projects_keyboard() -> InlineKeyboardMarkup:
    """Build a confirmation keyboard for bulk crawl launch."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, запустить", callback_data="parsing:all:confirm")
    builder.button(text="Отмена", callback_data="parsing:all:cancel")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_stop_parsing_keyboard() -> InlineKeyboardMarkup:
    """Build a confirmation keyboard for stopping active crawl tasks."""

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, остановить", callback_data="parsing:stop:confirm")
    builder.button(text="Отмена", callback_data="parsing:stop:cancel")
    builder.adjust(1)
    return builder.as_markup()


def build_batch_actions_keyboard(*, batch_id: int, can_stop: bool, supports_soft_stop: bool = False) -> InlineKeyboardMarkup:
    """Build actions for a specific launch card."""

    builder = InlineKeyboardBuilder()
    if can_stop:
        builder.button(text="Остановить этот запуск", callback_data=f"recent:batch:stop:{batch_id}")
    builder.button(text="Обновить", callback_data=f"recent:batch:{batch_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_stop_batch_keyboard(batch_id: int, *, soft: bool = False) -> InlineKeyboardMarkup:
    """Build a confirmation keyboard for stopping a specific launch."""

    builder = InlineKeyboardBuilder()
    action = "stopsoft" if soft else "stop"
    builder.button(text="Да, остановить", callback_data=f"recent:batch:{action}:confirm:{batch_id}")
    builder.button(text="Отмена", callback_data=f"recent:batch:{action}:cancel:{batch_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_recent_tasks_keyboard(tasks: list[RecentTaskSummary]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for recent tasks."""

    builder = InlineKeyboardBuilder()
    for task in tasks:
        builder.button(
            text=f"#{task.task_id} {task.label} [{task.status}]",
            callback_data=f"recent:task:{task.task_id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_recent_batches_keyboard(batches: list[RecentBatchSummary]) -> InlineKeyboardMarkup:
    """Build an inline keyboard for recent launches."""

    builder = InlineKeyboardBuilder()
    for batch in batches:
        builder.button(
            text=(
                f"#{batch.batch_id} {batch.title} "
                f"[{batch.status}] {batch.finished_tasks}/{batch.total_tasks}"
            ),
            callback_data=f"recent:batch:{batch.batch_id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def build_parsing_settings_keyboard(
    *,
    callback_prefix: str = "parsing:settings",
    current_depth: int,
    current_concurrency: int,
    current_pages: int,
    current_respect_robots: bool,
    current_delay_between_requests_ms: int | None = None,
    current_request_timeout_seconds: int | None = None,
    current_retry_on_5xx: bool | None = None,
    current_max_5xx_before_stop: int | None = None,
    current_retry_delay_ms: int | None = None,
    depth_options: tuple[int, ...] = (1, 2, 3, 4, 5),
    concurrency_options: tuple[int, ...] = (1, 2, 5, 10),
    page_options: tuple[int, ...] = (100, 1000, 8000, 20000),
    delay_options: tuple[int, ...] = (),
    timeout_options: tuple[int, ...] = (),
    max_5xx_options: tuple[int, ...] = (),
    retry_delay_options: tuple[int, ...] = (),
) -> InlineKeyboardMarkup:
    """Build inline controls for crawl settings."""

    builder = InlineKeyboardBuilder()

    for depth in depth_options:
        prefix = "• " if depth == current_depth else ""
        builder.button(
            text=f"{prefix}D{depth}",
            callback_data=f"{callback_prefix}:depth:{depth}",
        )

    for concurrency in concurrency_options:
        prefix = "• " if concurrency == current_concurrency else ""
        builder.button(
            text=f"{prefix}P{concurrency}",
            callback_data=f"{callback_prefix}:concurrency:{concurrency}",
        )

    for pages in page_options:
        prefix = "• " if pages == current_pages else ""
        builder.button(
            text=f"{prefix}{pages}",
            callback_data=f"{callback_prefix}:pages:{pages}",
        )
    builder.adjust(
        len(depth_options),
        len(concurrency_options),
        len(page_options),
    )

    robots_text = "robots: ON" if current_respect_robots else "robots: OFF"
    builder.button(
        text=robots_text,
        callback_data=f"{callback_prefix}:robots:toggle",
    )
    if current_retry_on_5xx is not None:
        retry_text = "retry 5xx: ON" if current_retry_on_5xx else "retry 5xx: OFF"
        builder.button(
            text=retry_text,
            callback_data=f"{callback_prefix}:retry5xx:toggle",
        )
    builder.button(text="Сбросить", callback_data=f"{callback_prefix}:reset")
    tail_row_size = 3 if current_retry_on_5xx is not None else 2

    if current_delay_between_requests_ms is not None and delay_options:
        for delay_ms in delay_options:
            prefix = "• " if delay_ms == current_delay_between_requests_ms else ""
            builder.button(
                text=f"{prefix}delay {delay_ms}",
                callback_data=f"{callback_prefix}:delay:{delay_ms}",
            )

    if current_request_timeout_seconds is not None and timeout_options:
        for timeout_seconds in timeout_options:
            prefix = "• " if timeout_seconds == current_request_timeout_seconds else ""
            builder.button(
                text=f"{prefix}timeout {timeout_seconds}",
                callback_data=f"{callback_prefix}:timeout:{timeout_seconds}",
            )

    if current_max_5xx_before_stop is not None and max_5xx_options:
        for max_5xx in max_5xx_options:
            prefix = "• " if max_5xx == current_max_5xx_before_stop else ""
            builder.button(
                text=f"{prefix}5xx stop {max_5xx}",
                callback_data=f"{callback_prefix}:max5xx:{max_5xx}",
            )

    if current_retry_delay_ms is not None and retry_delay_options:
        for retry_delay_ms in retry_delay_options:
            prefix = "• " if retry_delay_ms == current_retry_delay_ms else ""
            builder.button(
                text=f"{prefix}retry wait {retry_delay_ms}",
                callback_data=f"{callback_prefix}:retrydelay:{retry_delay_ms}",
            )

    adjust_rows: list[int] = [
        len(depth_options),
        len(concurrency_options),
        len(page_options),
        tail_row_size,
    ]
    if delay_options:
        adjust_rows.append(len(delay_options))
    if timeout_options:
        adjust_rows.append(len(timeout_options))
    if max_5xx_options:
        adjust_rows.append(len(max_5xx_options))
    if retry_delay_options:
        adjust_rows.append(len(retry_delay_options))
    builder.adjust(*adjust_rows)
    return builder.as_markup()


def build_heavy_settings_menu_keyboard(settings: CrawlLaunchSettings) -> InlineKeyboardMarkup:
    """Build a compact multi-step menu for heavy crawl settings."""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"Глубина: {settings.max_depth}", callback_data="parsing:heavy_settings:item:depth")
    builder.button(text=f"Потоки: {settings.max_concurrency}", callback_data="parsing:heavy_settings:item:concurrency")
    builder.button(text=f"Страниц: {_format_pages_short(settings.max_pages)}", callback_data="parsing:heavy_settings:item:pages")
    builder.button(
        text=f"Robots: {'вкл' if settings.respect_robots_disallow else 'выкл'}",
        callback_data="parsing:heavy_settings:toggle:robots",
    )
    builder.button(
        text=f"Задержка: {_format_delay_short(settings.delay_between_requests_ms)}",
        callback_data="parsing:heavy_settings:item:delay",
    )
    builder.button(
        text=f"Таймаут: {settings.request_timeout_seconds}с",
        callback_data="parsing:heavy_settings:item:timeout",
    )
    builder.button(
        text=f"Retry 5xx: {'вкл' if settings.retry_on_5xx else 'выкл'}",
        callback_data="parsing:heavy_settings:toggle:retry5xx",
    )
    builder.button(
        text=f"Стоп 5xx: {settings.max_5xx_before_stop}",
        callback_data="parsing:heavy_settings:item:max5xx",
    )
    builder.button(
        text=f"Пауза retry: {_format_delay_short(settings.retry_delay_ms)}",
        callback_data="parsing:heavy_settings:item:retrydelay",
    )
    builder.button(text="Сбросить", callback_data="parsing:heavy_settings:reset")
    builder.adjust(1)
    return builder.as_markup()


def build_heavy_setting_values_keyboard(
    *,
    setting_name: str,
    options: list[tuple[str, str]],
    current_value: str,
) -> InlineKeyboardMarkup:
    """Build a value selection keyboard for one heavy setting."""

    builder = InlineKeyboardBuilder()
    for value, label in options:
        prefix = "• " if value == current_value else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=f"parsing:heavy_settings:set:{setting_name}:{value}",
        )
    builder.button(text="Назад", callback_data="parsing:heavy_settings:back")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def _format_pages_short(value: int) -> str:
    """Format page limits for compact button labels."""

    if value >= 1000:
        thousands = value // 1000
        return f"{thousands}k"
    return str(value)


def _format_delay_short(value: int) -> str:
    """Format millisecond values for compact button labels."""

    if value >= 1000 and value % 1000 == 0:
        return f"{value // 1000}с"
    return f"{value}мс"
