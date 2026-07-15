"""Telegram bot handlers."""

from __future__ import annotations

import asyncio
import io

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.modules.projects.domain import CrawlSegment
from app.interfaces.bot.access import is_root_admin_user
from app.interfaces.bot.keyboards import (
    build_access_actions_keyboard,
    build_access_users_keyboard,
    build_adhoc_profile_keyboard,
    build_batch_actions_keyboard,
    build_confirm_all_projects_keyboard,
    build_confirm_delete_project_keyboard,
    build_confirm_stop_batch_keyboard,
    build_confirm_stop_parsing_keyboard,
    build_heavy_project_selection_keyboard,
    build_heavy_setting_values_keyboard,
    build_heavy_settings_menu_keyboard,
    build_indexing_actions_keyboard,
    build_main_menu_keyboard,
    build_parsing_actions_keyboard,
    build_parsing_settings_keyboard,
    build_project_boolean_keyboard,
    build_project_card_keyboard,
    build_project_fields_keyboard,
    build_project_segment_keyboard,
    build_project_selection_keyboard,
    build_project_text_action_keyboard,
    build_projects_list_keyboard,
    build_projects_actions_keyboard,
    build_recent_batches_keyboard,
    build_recent_tasks_keyboard,
    build_sitemap_actions_keyboard,
    build_sitemap_project_selection_keyboard,
    build_sitemap_robots_actions_keyboard,
    build_sitemap_settings_keyboard,
    build_yandex_recrawl_collect_keyboard,
    build_yandex_recrawl_project_keyboard,
    build_yandex_recrawl_projects_keyboard,
    build_yandex_token_actions_keyboard,
    build_yandex_webmaster_actions_keyboard,
    build_url_list_profile_keyboard,
    build_robots_project_selection_keyboard,
    build_status_actions_keyboard,
    build_url_list_collect_keyboard,
)
from app.interfaces.bot.services import (
    add_allowed_bot_user,
    add_yandex_recrawl_urls,
    launch_ad_hoc_robots,
    launch_ad_hoc_sitemap,
    launch_ad_hoc_url_list_crawl,
    launch_all_projects_sitemap,
    CrawlLaunchSettings,
    build_default_crawl_settings,
    build_heavy_crawl_settings,
    cancel_task_batch,
    cancel_active_crawl_tasks,
    create_project,
    delete_project,
    list_allowed_bot_users,
    list_root_admin_phone_numbers,
    get_project,
    get_batch_status,
    get_task_status,
    launch_all_projects_yandex_recrawl,
    launch_project_yandex_recrawl,
    launch_all_projects_crawl,
    launch_project_crawl,
    launch_project_robots,
    launch_project_sitemap,
    launch_ad_hoc_crawl,
    list_all_projects,
    list_yandex_recrawl_projects,
    list_recent_batches,
    list_projects,
    remove_allowed_bot_user,
    update_project,
)
from app.modules.yandex_oauth.service import get_yandex_connection_status, save_yandex_access_token

router = Router(name="main_bot")
CRAWL_SETTINGS_STATE_KEY = "crawl_settings"
HEAVY_CRAWL_SETTINGS_STATE_KEY = "heavy_crawl_settings"
ADHOC_CRAWL_PROFILE_STATE_KEY = "adhoc_crawl_profile"
SITEMAP_SETTINGS_STATE_KEY = "sitemap_settings"
ADHOC_URL_LIST_BUFFER_STATE_KEY = "adhoc_url_list_buffer"
YANDEX_RECRAWL_URL_BUFFER_STATE_KEY = "yandex_recrawl_url_buffer"
YANDEX_RECRAWL_PROJECT_ID_STATE_KEY = "yandex_recrawl_project_id"
YANDEX_RECRAWL_POSITION_STATE_KEY = "yandex_recrawl_position"
HEAVY_CONCURRENCY_OPTIONS = (1, 2, 3, 4, 5)
HEAVY_PAGE_OPTIONS = (5000, 25000, 100000, 150000, 200000, 250000)
HEAVY_DELAY_OPTIONS = (250, 500, 1000, 2000, 5000)
HEAVY_TIMEOUT_OPTIONS = (10, 15, 20, 30, 60)
HEAVY_MAX_5XX_OPTIONS = (3, 5, 10, 20, 50)
HEAVY_RETRY_DELAY_OPTIONS = (1000, 3000, 5000, 10000, 30000)
_URL_LIST_BUFFER_LOCKS: dict[tuple[int, int], asyncio.Lock] = {}


class AdHocCrawlStates(StatesGroup):
    """FSM states for launching an ad-hoc crawl."""

    waiting_for_url = State()


class AdHocUrlListStates(StatesGroup):
    """FSM states for launching a fixed URL list crawl."""

    waiting_for_urls = State()


class YandexRecrawlUrlListStates(StatesGroup):
    """FSM states for adding URLs to a Yandex recrawl queue."""

    waiting_for_urls = State()


class YandexAccessTokenStates(StatesGroup):
    """FSM state for receiving the shared Yandex OAuth token from the root admin."""

    waiting_for_token = State()


class AdHocSitemapStates(StatesGroup):
    """FSM states for launching an ad-hoc sitemap parsing task."""

    waiting_for_url = State()


class AdHocRobotsStates(StatesGroup):
    """FSM states for launching an ad-hoc robots parsing task."""

    waiting_for_url = State()


class AccessUserStates(StatesGroup):
    """FSM states for bot access management."""

    waiting_for_phone = State()


class TaskStatusStates(StatesGroup):
    """FSM states for checking a task status."""

    waiting_for_task_id = State()


class ProjectWizardStates(StatesGroup):
    """FSM states for creating and editing projects."""

    waiting_for_project_name = State()
    waiting_for_segment = State()
    waiting_for_start_url = State()
    waiting_for_sitemap_path = State()
    waiting_for_yandex_webmaster_host = State()
    waiting_for_contain_subdomains = State()
    waiting_for_is_multi_sitemap = State()
    waiting_for_pagination_view = State()
    waiting_for_pagination_sample = State()
    waiting_for_pagination_marker = State()
    waiting_for_card_sample = State()
    waiting_for_category_sample = State()


def _get_url_list_buffer_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    """Return a per-chat/user lock for URL list buffer mutations."""

    key = (chat_id, user_id)
    existing = _URL_LIST_BUFFER_LOCKS.get(key)
    if existing is not None:
        return existing
    lock = asyncio.Lock()
    _URL_LIST_BUFFER_LOCKS[key] = lock
    return lock


PROJECT_WIZARD_STATE_KEY = "project_wizard"
PROJECT_WIZARD_FIELD_ORDER = (
    "project_name",
    "crawl_segment",
    "start_url",
    "sitemap_path",
    "yandex_webmaster_host",
    "contain_subdomains",
    "is_multi_sitemap",
    "pagination_view",
    "pagination_sample",
    "pagination_marker",
    "card_sample",
    "category_sample",
)
PROJECT_WIZARD_STATE_BY_FIELD = {
    "project_name": ProjectWizardStates.waiting_for_project_name,
    "crawl_segment": ProjectWizardStates.waiting_for_segment,
    "start_url": ProjectWizardStates.waiting_for_start_url,
    "sitemap_path": ProjectWizardStates.waiting_for_sitemap_path,
    "yandex_webmaster_host": ProjectWizardStates.waiting_for_yandex_webmaster_host,
    "contain_subdomains": ProjectWizardStates.waiting_for_contain_subdomains,
    "is_multi_sitemap": ProjectWizardStates.waiting_for_is_multi_sitemap,
    "pagination_view": ProjectWizardStates.waiting_for_pagination_view,
    "pagination_sample": ProjectWizardStates.waiting_for_pagination_sample,
    "pagination_marker": ProjectWizardStates.waiting_for_pagination_marker,
    "card_sample": ProjectWizardStates.waiting_for_card_sample,
    "category_sample": ProjectWizardStates.waiting_for_category_sample,
}


def register_handlers(dispatcher: Dispatcher) -> None:
    """Register all bot handlers on the dispatcher."""

    dispatcher.include_router(router)


@router.message(Command("start"))
async def handle_start(message: Message, state: FSMContext) -> None:
    """Show the main bot menu."""

    await _clear_flow_state_preserving_settings(state)
    text = (
        "Mega Tools бот запущен.\n\n"
        "Сейчас доступны базовые разделы интерфейса. "
        "Начни с кнопок ниже."
    )
    await message.answer(text, reply_markup=build_main_menu_keyboard())


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Show a short help message."""

    await message.answer(
        "Команды:\n"
        "/start — открыть главное меню\n"
        "/help — показать эту подсказку\n"
        "/cancel — прервать текущий сценарий"
    )


@router.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Handle user cancellation."""

    await _clear_flow_state_preserving_settings(state)
    await message.answer("Текущий сценарий сброшен.", reply_markup=build_main_menu_keyboard())


@router.message(F.text == "Парсинг")
async def handle_parsing_menu(message: Message) -> None:
    """Open parsing section."""

    await message.answer(
        "Раздел парсинга.\nВыбери, как запускать задачу:",
        reply_markup=build_parsing_actions_keyboard(),
    )


@router.message(F.text == "Проекты")
async def handle_projects_menu(message: Message) -> None:
    """Open projects section."""

    await message.answer(
        "Раздел проектов.\nВыбери действие ниже.",
        reply_markup=build_projects_actions_keyboard(),
    )


@router.message(F.text == "Доступ")
async def handle_access_menu(message: Message, state: FSMContext) -> None:
    """Open bot access management section for root admins."""

    user = message.from_user
    if user is None or not is_root_admin_user(user.id):
        await message.answer("Раздел доступа доступен только root-админу.")
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Раздел доступа.\nВыбери действие ниже.",
        reply_markup=build_access_actions_keyboard(),
    )


@router.message(F.text == "Парсинг sitemap")
async def handle_sitemap_menu(message: Message) -> None:
    """Open sitemap parsing section."""

    await message.answer(
        "Раздел парсинга sitemap.\nВыбери, как запускать задачу:",
        reply_markup=build_sitemap_actions_keyboard(),
    )


@router.message(F.text == "Индексирование")
async def handle_indexing_menu(message: Message, state: FSMContext) -> None:
    """Open the indexing section."""

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Раздел индексирования.\nВыбери сервис и действие.",
        reply_markup=build_indexing_actions_keyboard(),
    )


@router.message(F.text == "Статус")
async def handle_status_menu(message: Message) -> None:
    """Open task status section."""

    await message.answer(
        "Раздел статусов.\nЗдесь можно проверить запуск или задачу.",
        reply_markup=build_status_actions_keyboard(),
    )


@router.callback_query(F.data == "parsing:projects")
async def handle_parsing_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle parsing from saved projects."""

    await callback.answer()
    projects = list_projects()
    if not projects:
        await callback.message.answer("Список обычных проектов пока пуст.")
        return

    settings = await _get_crawl_settings(state)
    await callback.message.answer(
        "Выбери обычный проект для запуска парсинга.\n\n"
        f"{_format_default_project_settings(settings)}",
        reply_markup=build_project_selection_keyboard(projects),
    )


@router.callback_query(F.data == "access:list")
async def handle_access_list(callback: CallbackQuery) -> None:
    """Show root admins and DB-managed allowed users."""

    await callback.answer()
    user = callback.from_user
    if user is None or not is_root_admin_user(user.id):
        await callback.message.answer("Раздел доступа доступен только root-админу.")
        return

    root_numbers = list_root_admin_phone_numbers()
    db_users = list_allowed_bot_users()
    lines = ["Root-админы:"]
    if root_numbers:
        lines.extend(f"- {phone}" for phone in root_numbers)
    else:
        lines.append("- —")

    lines.append("")
    lines.append("Пользователи из БД:")
    if db_users:
        for access_user in db_users:
            title = access_user.phone_number
            if access_user.username:
                title += f" (@{access_user.username})"
            lines.append(f"- {title}")
    else:
        lines.append("- —")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=build_access_users_keyboard(db_users) if db_users else None,
    )


@router.callback_query(F.data == "access:add")
async def handle_access_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Start the allowlist add flow for root admins."""

    await callback.answer()
    user = callback.from_user
    if user is None or not is_root_admin_user(user.id):
        await callback.message.answer("Раздел доступа доступен только root-админу.")
        return

    await state.set_state(AccessUserStates.waiting_for_phone)
    await callback.message.answer(
        "Пришли номер телефона пользователя.\n\n"
        "Можно отправить номер текстом или контактом.\n"
        "Пример: 79213793537",
    )


@router.callback_query(F.data.startswith("access:delete:"))
async def handle_access_delete(callback: CallbackQuery) -> None:
    """Delete one DB-managed allowed user."""

    await callback.answer()
    user = callback.from_user
    if user is None or not is_root_admin_user(user.id):
        await callback.message.answer("Раздел доступа доступен только root-админу.")
        return

    raw_id = callback.data.rsplit(":", 1)[-1]
    try:
        access_user_id = int(raw_id)
    except ValueError:
        await callback.message.answer("Не удалось определить пользователя.")
        return

    deleted = remove_allowed_bot_user(access_user_id)
    if deleted:
        await callback.message.answer("Пользователь удалён из доступа.")
    else:
        await callback.message.answer("Пользователь уже отсутствует.")


@router.callback_query(F.data == "parsing:heavy_projects")
async def handle_parsing_heavy_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle parsing from the heavy project list."""

    await callback.answer()
    projects = list_projects(crawl_segment=CrawlSegment.HEAVY)
    if not projects:
        await callback.message.answer("Список heavy-проектов пока пуст.")
        return

    settings = await _get_heavy_crawl_settings(state)
    await callback.message.answer(
        "Выбери heavy-проект для запуска.\n\n"
        f"{_format_crawl_settings(settings)}",
        reply_markup=build_heavy_project_selection_keyboard(projects),
    )


@router.callback_query(F.data == "parsing:adhoc")
async def handle_parsing_adhoc(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask which settings profile to use for an ad-hoc crawl."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        "Выбери, какие настройки применить к разовому запуску.",
        reply_markup=build_adhoc_profile_keyboard(),
    )


@router.callback_query(F.data == "parsing:url_list")
async def handle_parsing_url_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask which settings profile to use for a fixed URL list crawl."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        "Выбери, какие настройки применить к запуску по списку URL.",
        reply_markup=build_url_list_profile_keyboard(),
    )


@router.callback_query(F.data == "sitemap:projects")
async def handle_sitemap_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle sitemap parsing from all saved projects."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    projects = [project for project in list_all_projects() if project.sitemap_path]
    if not projects:
        await callback.message.answer("Нет проектов с заполненным sitemap.")
        return

    projects.sort(key=lambda project: (project.crawl_segment == CrawlSegment.HEAVY, project.project_name.lower()))
    await callback.message.answer(
        "Выбери проект для парсинга sitemap.\n\n"
        "Список включает обычные и heavy-проекты. Кнопка «Парсить все» сначала запустит обычные, потом heavy.",
        reply_markup=build_sitemap_project_selection_keyboard(projects),
    )


@router.callback_query(F.data == "indexing:yandex")
async def handle_yandex_indexing_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Open Yandex Webmaster indexing actions."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        "Яндекс Вебмастер.\nВыбери действие.",
        reply_markup=build_yandex_webmaster_actions_keyboard(),
    )


@router.callback_query(F.data == "indexing:yandex:connection")
async def handle_yandex_connection(callback: CallbackQuery, state: FSMContext) -> None:
    """Show current shared Yandex OAuth connection state."""

    await callback.answer()
    connected, expires_at, is_manual_token = get_yandex_connection_status()
    user = callback.from_user
    if not connected:
        if user is not None and is_root_admin_user(user.id):
            await _request_yandex_access_token(callback.message, state)
            return
        await callback.message.answer(
            "Яндекс пока не подключён.\n\n"
            "Попроси root-админа подключить аккаунт Яндекс в этом разделе."
        )
        return
    lines = ["Яндекс подключён."]
    if expires_at is not None:
        lines.append(f"Обновить токен до: {expires_at.date().isoformat()}")
    if is_manual_token:
        lines.append("Токен введён вручную и хранится в зашифрованном виде.")
    reply_markup = build_yandex_token_actions_keyboard() if user is not None and is_root_admin_user(user.id) else None
    await callback.message.answer("\n".join(lines), reply_markup=reply_markup)


@router.callback_query(F.data == "indexing:yandex:connection:update")
async def handle_yandex_connection_update(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask the root admin for a replacement Yandex OAuth token."""

    await callback.answer()
    user = callback.from_user
    if user is None or not is_root_admin_user(user.id):
        await callback.message.answer("Заменить токен может только root-админ.")
        return
    await _request_yandex_access_token(callback.message, state)


async def _request_yandex_access_token(message: Message, state: FSMContext) -> None:
    """Start secure manual Yandex token collection for the root admin."""

    await _clear_flow_state_preserving_settings(state)
    await state.set_state(YandexAccessTokenStates.waiting_for_token)
    await message.answer(
        "Пришли OAuth-токен Яндекс Вебмастера одним сообщением.\n\n"
        "После сохранения бот удалит сообщение с токеном и зашифрует его в базе.\n"
        "Инструкция по выпуску токена: https://yandex.ru/dev/webmaster/doc/ru/tasks/how-to-get-oauth\n\n"
        "Для отмены отправь /cancel."
    )


@router.callback_query(F.data == "indexing:yandex:recrawl")
async def handle_yandex_recrawl_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """List every project for Yandex Webmaster recrawl actions."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    projects = list_yandex_recrawl_projects()
    if not projects:
        await callback.message.answer("Список проектов пока пуст.")
        return
    await callback.message.answer(
        "Выбери проект.\n\n"
        "В строке показано число URL в очереди и состояние хоста Яндекс Вебмастера.",
        reply_markup=build_yandex_recrawl_projects_keyboard(projects),
    )


@router.callback_query(F.data.startswith("indexing:yandex:project:"))
async def handle_yandex_recrawl_project(callback: CallbackQuery) -> None:
    """Show actions for one selected Yandex recrawl queue."""

    await callback.answer()
    raw_project_id = callback.data.rsplit(":", 1)[-1]
    try:
        project_id = int(raw_project_id)
    except ValueError:
        await callback.message.answer("Не удалось определить проект.")
        return
    summary = next(
        (item for item in list_yandex_recrawl_projects() if item.project.id == project_id),
        None,
    )
    if summary is None:
        await callback.message.answer("Проект не найден.")
        return
    host_text = "настроен" if summary.has_yandex_host else "не заполнен"
    await callback.message.answer(
        f"Проект: {summary.project.project_name}\n"
        f"URL в очереди: {summary.queue_count}\n"
        f"Хост Яндекс Вебмастера: {host_text}",
        reply_markup=build_yandex_recrawl_project_keyboard(project_id, queue_count=summary.queue_count),
    )


@router.callback_query(F.data == "indexing:yandex:all")
async def handle_yandex_recrawl_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch all ready project recrawl queues sequentially."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    try:
        result = launch_all_projects_yandex_recrawl()
    except Exception:
        await callback.message.answer("Не удалось запустить переобход всех проектов.")
        return
    if result.batch is None:
        await callback.message.answer("Нет проектов с URL в очереди и настроенным хостом Яндекс Вебмастера.")
        return
    await callback.message.answer(
        "Переобход запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проектов в запуске: {result.total_projects}\n"
        f"Пропущено: {result.skipped_projects}\n\n"
        "Проекты будут обработаны по очереди."
    )


@router.callback_query(F.data.startswith("indexing:yandex:send:"))
async def handle_yandex_recrawl_send(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch a selected project recrawl queue."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    try:
        project_id = int(callback.data.rsplit(":", 1)[-1])
        result = launch_project_yandex_recrawl(project_id)
    except ValueError as exc:
        await callback.message.answer(str(exc))
        return
    except Exception:
        await callback.message.answer("Не удалось запустить переобход проекта.")
        return
    await callback.message.answer(
        "Переобход запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project.project_name}\n"
        f"Task ID: {result.task.id}\n\n"
        "Статус и обновлённый отчет будут доступны в разделе «Статус»."
    )


@router.callback_query(F.data.startswith("indexing:yandex:add:"))
async def handle_yandex_recrawl_add_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Start, clear, save or cancel URL collection for a selected queue edge."""

    await callback.answer()
    action = callback.data.split(":")[3]
    if action in {"first", "last"}:
        try:
            project_id = int(callback.data.rsplit(":", 1)[-1])
        except ValueError:
            await callback.message.answer("Не удалось определить проект.")
            return
        await state.set_state(YandexRecrawlUrlListStates.waiting_for_urls)
        await state.update_data(
            {
                YANDEX_RECRAWL_PROJECT_ID_STATE_KEY: project_id,
                YANDEX_RECRAWL_POSITION_STATE_KEY: action,
                YANDEX_RECRAWL_URL_BUFFER_STATE_KEY: [],
            }
        )
        position_text = "в начало" if action == "first" else "в конец"
        await callback.message.answer(
            f"Отправь список URL для добавления {position_text} очереди.\n\n"
            "Можно прислать список в нескольких сообщениях или `.txt` файл.\n"
            "Когда закончишь, нажми «Добавить в очередь»."
        )
        return
    if action == "reset":
        lock = _get_url_list_buffer_lock(callback.message.chat.id, callback.from_user.id)
        async with lock:
            await state.update_data({YANDEX_RECRAWL_URL_BUFFER_STATE_KEY: []})
        await callback.message.answer("Список очищен. Пришли новые URL.")
        return
    if action == "cancel":
        await _clear_flow_state_preserving_settings(state)
        await callback.message.answer("Добавление URL отменено.")
        return
    if action != "save":
        return
    lock = _get_url_list_buffer_lock(callback.message.chat.id, callback.from_user.id)
    async with lock:
        data = await state.get_data()
        raw_urls = data.get(YANDEX_RECRAWL_URL_BUFFER_STATE_KEY)
        project_id = data.get(YANDEX_RECRAWL_PROJECT_ID_STATE_KEY)
        position = data.get(YANDEX_RECRAWL_POSITION_STATE_KEY)
        urls = [item for item in raw_urls if isinstance(item, str) and item.strip()] if isinstance(raw_urls, list) else []
    if not isinstance(raw_urls, list) or not raw_urls or not isinstance(project_id, int):
        await callback.message.answer("Список URL пока пуст.")
        return
    try:
        project, added_count, total_count = add_yandex_recrawl_urls(
            project_id,
            urls,
            prepend=position == "first",
        )
    except ValueError as exc:
        await callback.message.answer(str(exc))
        return
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        f"Очередь проекта «{project.project_name}» обновлена.\n\n"
        f"Добавлено: {added_count}\n"
        f"Всего в очереди: {total_count}"
    )


@router.callback_query(F.data == "sitemap:adhoc")
async def handle_sitemap_adhoc(callback: CallbackQuery, state: FSMContext) -> None:
    """Start ad-hoc sitemap parsing by URL."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await state.set_state(AdHocSitemapStates.waiting_for_url)
    await callback.message.answer(
        "Пришли полный URL sitemap.\n\n"
        "Пример: https://example.com/sitemap.xml\n\n"
        "Для отмены отправь /cancel.",
    )


@router.callback_query(F.data == "sitemap:robots")
async def handle_sitemap_robots_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Open robots.txt-based sitemap discovery actions."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        "Парсинг robots.txt.\nВыбери, откуда запускать проверку.",
        reply_markup=build_sitemap_robots_actions_keyboard(),
    )


@router.callback_query(F.data == "sitemap:robots:projects")
async def handle_sitemap_robots_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """Show projects for robots.txt parsing."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    projects = list_all_projects()
    if not projects:
        await callback.message.answer("Список проектов пока пуст.")
        return

    await callback.message.answer(
        "Выбери проект для парсинга robots.txt.",
        reply_markup=build_robots_project_selection_keyboard(projects),
    )


@router.callback_query(F.data == "sitemap:robots:adhoc")
async def handle_sitemap_robots_adhoc(callback: CallbackQuery, state: FSMContext) -> None:
    """Start ad-hoc robots parsing by URL."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    await state.set_state(AdHocRobotsStates.waiting_for_url)
    await callback.message.answer(
        "Пришли URL сайта или robots.txt.\n\n"
        "Примеры:\n"
        "- https://example.com\n"
        "- https://example.com/robots.txt\n\n"
        "Для отмены отправь /cancel.",
    )


@router.callback_query(F.data == "sitemap:all")
async def handle_sitemap_all_projects(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch sitemap parsing for all projects with sitemap URLs."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    try:
        sitemap_settings = await _get_sitemap_settings(state)
        result = launch_all_projects_sitemap(
            resolve_status_codes=sitemap_settings["resolve_status_codes"],
            replace_yandex_recrawl_queue=sitemap_settings["replace_yandex_recrawl_queue"],
        )
    except ValueError as exc:
        await callback.message.answer(str(exc))
        return
    except Exception:
        await callback.message.answer("Не удалось запустить парсинг sitemap для всех проектов.")
        return

    if result.batch is None:
        await callback.message.answer("Нет проектов с заполненным sitemap.")
        return

    await callback.message.answer(
        "Парсинг sitemap запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проектов в запуске: {result.total_projects}\n"
        f"Задач создано: {len(result.task_ids)}\n\n"
        "Сначала будут обработаны обычные проекты, затем heavy.\n"
        "Проверить запуск можно через раздел Статус.",
    )


@router.callback_query(F.data == "sitemap:settings")
async def handle_sitemap_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Show sitemap parsing settings."""

    await callback.answer()
    await _send_sitemap_settings(callback.message, state)


@router.callback_query(F.data.startswith("sitemap:settings:toggle:"))
async def handle_sitemap_settings_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Toggle one sitemap parsing setting."""

    await callback.answer()
    settings = await _get_sitemap_settings(state)
    setting_name = callback.data.rsplit(":", 1)[-1]
    if setting_name not in {"resolve_status_codes", "replace_yandex_recrawl_queue"}:
        await callback.message.answer("Неизвестная настройка sitemap.")
        return
    settings[setting_name] = not settings[setting_name]
    await _set_sitemap_settings(state, settings)
    await _send_sitemap_settings(callback.message, state)


@router.callback_query(F.data == "parsing:adhoc:cancel")
async def handle_parsing_adhoc_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel ad-hoc crawl profile selection."""

    await callback.answer("Отменено")
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer("Запуск по своему URL отменён.")


@router.callback_query(F.data == "parsing:adhoc:default")
async def handle_parsing_adhoc_default(callback: CallbackQuery, state: FSMContext) -> None:
    """Start ad-hoc flow with default crawl settings."""

    await callback.answer()
    await state.set_state(AdHocCrawlStates.waiting_for_url)
    settings = await _get_crawl_settings(state)
    await state.update_data({ADHOC_CRAWL_PROFILE_STATE_KEY: "default"})
    await callback.message.answer(
        "Отправь URL сайта для разового запуска.\n\n"
        "Пример: https://example.com\n\n"
        "Будут применены обычные настройки:\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Для отмены отправь /cancel."
    )


@router.callback_query(F.data == "parsing:adhoc:heavy")
async def handle_parsing_adhoc_heavy(callback: CallbackQuery, state: FSMContext) -> None:
    """Start ad-hoc flow with heavy crawl settings."""

    await callback.answer()
    await state.set_state(AdHocCrawlStates.waiting_for_url)
    settings = await _get_heavy_crawl_settings(state)
    await state.update_data({ADHOC_CRAWL_PROFILE_STATE_KEY: "heavy"})
    await callback.message.answer(
        "Отправь URL сайта для разового запуска.\n\n"
        "Пример: https://example.com\n\n"
        "Будут применены heavy-настройки:\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Для отмены отправь /cancel."
    )


@router.callback_query(F.data == "parsing:url_list:cancel")
async def handle_parsing_url_list_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel fixed URL list profile selection."""

    await callback.answer("Отменено")
    await _clear_flow_state_preserving_settings(state)
    await callback.message.answer("Запуск по списку URL отменён.")


@router.callback_query(F.data == "parsing:url_list:default")
async def handle_parsing_url_list_default(callback: CallbackQuery, state: FSMContext) -> None:
    """Start fixed URL list flow with default crawl settings."""

    await callback.answer()
    await state.set_state(AdHocUrlListStates.waiting_for_urls)
    settings = await _get_crawl_settings(state)
    await state.update_data(
        {
            ADHOC_CRAWL_PROFILE_STATE_KEY: "default",
            ADHOC_URL_LIST_BUFFER_STATE_KEY: [],
        }
    )
    await callback.message.answer(
        "Отправь список URL, каждый с новой строки.\n\n"
        "Если URL больше 200, лучше отправить `.txt` файл.\n"
        "Внутри файла — один URL на строку.\n\n"
        "Будут обработаны только переданные URL, без дальнейшего обхода ссылок.\n\n"
        "Будут применены обычные настройки:\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Можно отправить список в несколько сообщений. Когда закончишь, нажми «Запустить список».\n\n"
        "Для отмены отправь /cancel."
    )


@router.callback_query(F.data == "parsing:url_list:heavy")
async def handle_parsing_url_list_heavy(callback: CallbackQuery, state: FSMContext) -> None:
    """Start fixed URL list flow with heavy crawl settings."""

    await callback.answer()
    await state.set_state(AdHocUrlListStates.waiting_for_urls)
    settings = await _get_heavy_crawl_settings(state)
    await state.update_data(
        {
            ADHOC_CRAWL_PROFILE_STATE_KEY: "heavy",
            ADHOC_URL_LIST_BUFFER_STATE_KEY: [],
        }
    )
    await callback.message.answer(
        "Отправь список URL, каждый с новой строки.\n\n"
        "Если URL больше 200, лучше отправить `.txt` файл.\n"
        "Внутри файла — один URL на строку.\n\n"
        "Будут обработаны только переданные URL, без дальнейшего обхода ссылок.\n\n"
        "Будут применены heavy-настройки:\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Можно отправить список в несколько сообщений. Когда закончишь, нажми «Запустить список».\n\n"
        "Для отмены отправь /cancel."
    )


@router.callback_query(F.data == "parsing:url_list:reset")
async def handle_parsing_url_list_reset(callback: CallbackQuery, state: FSMContext) -> None:
    """Clear the accumulated URL list while keeping the selected profile."""

    await callback.answer("Список очищен")
    lock = _get_url_list_buffer_lock(callback.message.chat.id, callback.from_user.id)
    async with lock:
        await state.update_data({ADHOC_URL_LIST_BUFFER_STATE_KEY: []})
    await callback.message.answer(
        "Список URL очищен. Отправь новые адреса, каждый с новой строки.",
        reply_markup=build_url_list_collect_keyboard(url_count=0),
    )


@router.callback_query(F.data == "parsing:url_list:launch")
async def handle_parsing_url_list_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch a fixed URL list crawl from accumulated messages."""

    await callback.answer()
    lock = _get_url_list_buffer_lock(callback.message.chat.id, callback.from_user.id)
    async with lock:
        data = await state.get_data()
        raw_urls = data.get(ADHOC_URL_LIST_BUFFER_STATE_KEY)
        if not isinstance(raw_urls, list) or not raw_urls:
            await callback.message.answer("Список URL пока пуст. Сначала пришли хотя бы один адрес.")
            return

        normalized_input_urls = [item for item in raw_urls if isinstance(item, str) and item.strip()]
        if not normalized_input_urls:
            await callback.message.answer("Список URL пока пуст. Сначала пришли хотя бы один адрес.")
            return

        try:
            settings = await _get_adhoc_crawl_settings(state)
            result = launch_ad_hoc_url_list_crawl(normalized_input_urls, settings=settings)
        except ValueError as exc:
            await callback.message.answer(str(exc))
            return
        except Exception:
            await callback.message.answer(
                "Не удалось запустить парсинг по списку URL. Попробуй ещё раз чуть позже."
            )
            return

        await _clear_flow_state_preserving_settings(state)
    await callback.message.answer(
        "Парсинг по списку URL запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project_name}\n"
        f"URL в списке: {result.url_count}\n"
        f"Первый URL: {result.start_url}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == "parsing:settings")
async def handle_parsing_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Open crawl settings editor."""

    await callback.answer()
    await _send_parsing_settings(callback.message, state)


@router.callback_query(F.data == "parsing:heavy_settings")
async def handle_heavy_parsing_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Open heavy crawl settings editor."""

    await callback.answer()
    await _send_heavy_parsing_settings(callback.message, state)


@router.callback_query(F.data == "parsing:heavy_settings:back")
async def handle_heavy_parsing_settings_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to the heavy settings overview."""

    await callback.answer()
    await _send_heavy_parsing_settings(callback.message, state)


@router.callback_query(F.data == "parsing:heavy_settings:reset")
async def handle_heavy_parsing_settings_reset(callback: CallbackQuery, state: FSMContext) -> None:
    """Reset heavy settings to defaults."""

    await callback.answer()
    await _set_heavy_crawl_settings(state, build_heavy_crawl_settings())
    await _send_heavy_parsing_settings(callback.message, state)


@router.callback_query(F.data.startswith("parsing:heavy_settings:toggle:"))
async def handle_heavy_parsing_settings_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Toggle boolean heavy settings."""

    await callback.answer()
    setting_name = callback.data.rsplit(":", 1)[-1]
    settings = await _get_heavy_crawl_settings(state)

    if setting_name == "robots":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=not settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "retry5xx":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=not settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    else:
        await callback.message.answer("Не удалось изменить настройку.")
        return

    await _set_heavy_crawl_settings(state, updated)
    await _send_heavy_parsing_settings(callback.message, state)


@router.callback_query(F.data.startswith("parsing:heavy_settings:item:"))
async def handle_heavy_parsing_settings_item(callback: CallbackQuery, state: FSMContext) -> None:
    """Open one heavy setting value picker."""

    await callback.answer()
    setting_name = callback.data.rsplit(":", 1)[-1]
    settings = await _get_heavy_crawl_settings(state)
    await _send_heavy_setting_picker(callback.message, settings, setting_name)


@router.callback_query(F.data.startswith("parsing:heavy_settings:set:"))
async def handle_heavy_parsing_settings_set(callback: CallbackQuery, state: FSMContext) -> None:
    """Apply a selected heavy setting value."""

    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.message.answer("Не удалось изменить настройку.")
        return

    setting_name = parts[3]
    setting_value = parts[4]
    settings = await _get_heavy_crawl_settings(state)
    updated = _with_updated_heavy_setting(settings, setting_name, setting_value)
    if updated is None:
        await callback.message.answer("Не удалось изменить настройку.")
        return

    await _set_heavy_crawl_settings(state, updated)
    await _send_heavy_setting_picker(callback.message, updated, setting_name)


@router.callback_query(F.data.startswith("parsing:settings:"))
async def handle_parsing_settings_change(callback: CallbackQuery, state: FSMContext) -> None:
    """Update crawl settings in FSM data."""

    await callback.answer()
    settings = await _get_crawl_settings(state)
    await _apply_settings_change(
        callback=callback,
        state=state,
        settings=settings,
        setter=_set_crawl_settings,
        refresh=_send_parsing_settings,
        prefix="parsing:settings:",
        default_settings=build_default_crawl_settings(),
    )


@router.callback_query(F.data == "parsing:recent")
async def handle_parsing_recent(callback: CallbackQuery) -> None:
    """Handle recent parsing launches."""

    await callback.answer()
    await _send_recent_batches(callback.message)


@router.callback_query(F.data == "parsing:all")
async def handle_parsing_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for confirmation before launching crawl for all projects."""

    await callback.answer()
    settings = await _get_crawl_settings(state)
    await callback.message.answer(
        "Запустить парсинг для всех обычных проектов?\n\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Задачи будут поставлены в очередь. Если worker один, они пойдут последовательно.",
        reply_markup=build_confirm_all_projects_keyboard(),
    )


@router.callback_query(F.data == "parsing:stop")
async def handle_parsing_stop(callback: CallbackQuery) -> None:
    """Ask for confirmation before stopping active crawl tasks."""

    await callback.answer()
    await callback.message.answer(
        "Остановить все активные запуски парсинга?\n\n"
        "Ожидающие задачи будут сняты с очереди, а выполняющиеся получат запрос на остановку.",
        reply_markup=build_confirm_stop_parsing_keyboard(),
    )


@router.callback_query(F.data == "parsing:stop:cancel")
async def handle_parsing_stop_cancel(callback: CallbackQuery) -> None:
    """Cancel stop confirmation."""

    await callback.answer("Отменено")
    await callback.message.answer("Остановка парсинга отменена.")


@router.callback_query(F.data == "parsing:stop:confirm")
async def handle_parsing_stop_confirm(callback: CallbackQuery) -> None:
    """Stop active crawl tasks."""

    await callback.answer()
    result = cancel_active_crawl_tasks()
    await callback.message.answer(
        "Остановка парсинга запрошена.\n\n"
        f"Снято с очереди: {result.pending_cancelled}\n"
        f"Отмечено на остановку: {result.running_cancel_requested}\n\n"
        "Выполняющиеся задачи остановятся после ближайшей проверки флага отмены.",
    )


@router.callback_query(F.data == "parsing:all:cancel")
async def handle_parsing_all_cancel(callback: CallbackQuery) -> None:
    """Cancel bulk crawl confirmation."""

    await callback.answer("Отменено")
    await callback.message.answer("Массовый запуск отменён.")


@router.callback_query(F.data == "parsing:all:confirm")
async def handle_parsing_all_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch crawl tasks for all projects."""

    await callback.answer()
    settings = await _get_crawl_settings(state)
    result = launch_all_projects_crawl(settings=settings)
    if result.total_projects == 0:
        await callback.message.answer("Список проектов пока пуст.")
        return

    first_task_id = result.task_ids[0]
    last_task_id = result.task_ids[-1]
    await callback.message.answer(
        "Массовый парсинг запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проектов в очереди: {result.total_projects}\n"
        f"Task ID: {first_task_id}-{last_task_id}\n\n"
        "Задачи поставлены в очередь. Если worker один, они будут обработаны последовательно.",
    )
    if result.tasks:
        await callback.message.answer(
            "Задачи этого запуска:",
            reply_markup=build_recent_tasks_keyboard(result.tasks),
        )


@router.callback_query(F.data.startswith("parsing:project:"))
async def handle_parsing_project_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch crawl for a selected project."""

    await callback.answer()
    project_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        project_id = int(project_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить проект для запуска.")
        return

    settings = await _get_crawl_settings(state)
    result = launch_project_crawl(project_id, settings=settings)
    if result is None:
        await callback.message.answer("Проект не найден.")
        return

    await callback.message.answer(
        "Парсинг запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project.project_name}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
    )


@router.callback_query(F.data.startswith("sitemap:project:"))
async def handle_sitemap_project_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch sitemap parsing for a selected project."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    project_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        project_id = int(project_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить проект для парсинга sitemap.")
        return

    try:
        sitemap_settings = await _get_sitemap_settings(state)
        result = launch_project_sitemap(
            project_id,
            resolve_status_codes=sitemap_settings["resolve_status_codes"],
            replace_yandex_recrawl_queue=sitemap_settings["replace_yandex_recrawl_queue"],
        )
    except ValueError as exc:
        await callback.message.answer(str(exc))
        return
    except Exception:
        await callback.message.answer("Не удалось запустить парсинг sitemap.")
        return

    if result is None:
        await callback.message.answer("Проект не найден.")
        return

    await callback.message.answer(
        "Парсинг sitemap запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project.project_name}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
    )


@router.callback_query(F.data.startswith("sitemap:robots:project:"))
async def handle_robots_project_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch robots parsing for a selected project."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    project_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        project_id = int(project_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить проект для парсинга robots.txt.")
        return

    try:
        sitemap_settings = await _get_sitemap_settings(state)
        result = launch_project_robots(
            project_id,
            resolve_status_codes=sitemap_settings["resolve_status_codes"],
        )
    except ValueError as exc:
        await callback.message.answer(str(exc))
        return
    except Exception:
        await callback.message.answer("Не удалось запустить парсинг robots.txt.")
        return

    if result is None:
        await callback.message.answer("Проект не найден.")
        return

    await callback.message.answer(
        "Парсинг robots.txt запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project.project_name}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
    )


@router.callback_query(F.data.startswith("parsing:heavy_project:"))
async def handle_parsing_heavy_project_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """Launch crawl for a selected heavy project."""

    await callback.answer()
    project_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        project_id = int(project_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить heavy-проект для запуска.")
        return

    settings = await _get_heavy_crawl_settings(state)
    result = launch_project_crawl(project_id, settings=settings)
    if result is None:
        await callback.message.answer("Проект не найден.")
        return

    await callback.message.answer(
        "Парсинг heavy-проекта запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project.project_name}\n"
        f"Task ID: {result.task.id}\n"
        f"Очередь: {result.task.queue_name}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
    )


@router.callback_query(F.data.startswith("projects:"))
async def handle_projects_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle projects section callbacks."""

    await callback.answer()
    data = callback.data or ""

    if data == "projects:list":
        projects = list_all_projects()
        if not projects:
            await callback.message.answer("Список проектов пока пуст.")
            return
        await callback.message.answer(
            "Проекты:\nВыбери проект, чтобы открыть карточку.",
            reply_markup=build_projects_list_keyboard(projects, mode="view"),
        )
        return

    if data == "projects:add":
        await _start_project_wizard(callback.message, state)
        return

    if data == "projects:edit":
        projects = list_all_projects()
        if not projects:
            await callback.message.answer("Список проектов пока пуст.")
            return
        await callback.message.answer(
            "Выбери проект для редактирования.",
            reply_markup=build_projects_list_keyboard(projects, mode="fields"),
        )
        return

    if data == "projects:delete":
        projects = list_all_projects()
        if not projects:
            await callback.message.answer("Список проектов пока пуст.")
            return
        await callback.message.answer(
            "Выбери проект для удаления.",
            reply_markup=build_projects_list_keyboard(projects, mode="delete"),
        )
        return

    if data.startswith("projects:fields:"):
        project_id = _parse_callback_id(data)
        if project_id is None:
            await callback.message.answer("Не удалось определить проект.")
            return
        project = get_project(project_id)
        if project is None:
            await callback.message.answer("Проект не найден.")
            return
        await callback.message.answer(
            f"Выбери поле проекта {project.project_name}.",
            reply_markup=build_project_fields_keyboard(project_id),
        )
        return

    if data.startswith("projects:field:"):
        parts = data.split(":")
        if len(parts) != 4:
            await callback.message.answer("Не удалось определить поле проекта.")
            return
        try:
            project_id = int(parts[2])
        except ValueError:
            await callback.message.answer("Не удалось определить проект.")
            return
        field_name = parts[3]
        await _start_project_field_edit(callback.message, state, project_id=project_id, field_name=field_name)
        return

    if data.startswith("projects:view:"):
        project_id = _parse_callback_id(data)
        if project_id is None:
            await callback.message.answer("Не удалось определить проект.")
            return
        await _send_project_card(callback.message, project_id)
        return

    if data.startswith("projects:delete:confirm:"):
        project_id = _parse_callback_id(data)
        if project_id is None:
            await callback.message.answer("Не удалось определить проект.")
            return
        deleted = delete_project(project_id)
        if not deleted:
            await callback.message.answer("Проект не найден.")
            return
        await callback.message.answer("Проект удалён.")
        return

    if data.startswith("projects:delete:cancel:"):
        await callback.message.answer("Удаление отменено.")
        return

    if data.startswith("projects:delete:"):
        project_id = _parse_callback_id(data)
        if project_id is None:
            await callback.message.answer("Не удалось определить проект.")
            return
        project = get_project(project_id)
        if project is None:
            await callback.message.answer("Проект не найден.")
            return
        await callback.message.answer(
            f"Удалить проект {project.project_name}?",
            reply_markup=build_confirm_delete_project_keyboard(project_id),
        )
        return

    if data.startswith("projects:wizard:segment:"):
        await _handle_project_wizard_segment(callback, state)
        return

    if data.startswith("projects:wizard:boolean:"):
        await _handle_project_wizard_boolean(callback, state)
        return

    if data == "projects:wizard:text:skip":
        await _handle_project_wizard_skip(callback.message, state)
        return

    await callback.message.answer("Неизвестное действие в разделе проектов.")


@router.message(ProjectWizardStates.waiting_for_project_name)
@router.message(ProjectWizardStates.waiting_for_start_url)
@router.message(ProjectWizardStates.waiting_for_sitemap_path)
@router.message(ProjectWizardStates.waiting_for_yandex_webmaster_host)
@router.message(ProjectWizardStates.waiting_for_pagination_view)
@router.message(ProjectWizardStates.waiting_for_pagination_sample)
@router.message(ProjectWizardStates.waiting_for_pagination_marker)
@router.message(ProjectWizardStates.waiting_for_card_sample)
@router.message(ProjectWizardStates.waiting_for_category_sample)
async def handle_project_wizard_text_input(message: Message, state: FSMContext) -> None:
    """Handle text input steps for the project wizard."""

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("Не вижу значения. Пришли текст или нажми кнопку пропуска.")
        return
    if raw_text.startswith("/"):
        await message.answer("Сначала заверши сценарий через /cancel или введи значение.")
        return

    wizard = await _get_project_wizard(state)
    current_field = wizard.get("current_field")
    if not isinstance(current_field, str):
        await message.answer("Не удалось определить шаг мастера.")
        return

    await _set_project_wizard_field(state, current_field, _normalize_project_text_value(raw_text))
    await _advance_project_wizard(message, state, current_field)


@router.callback_query(F.data.startswith("status:"))
async def handle_status_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle task status callbacks."""

    await callback.answer()
    if callback.data == "status:by_id":
        await state.set_state(TaskStatusStates.waiting_for_task_id)
        await callback.message.answer(
            "Отправь task_id, который нужно проверить.\n\n"
            "Пример: 80\n\n"
            "Для отмены отправь /cancel.",
        )
        return

    if callback.data == "status:recent":
        await _send_recent_batches(callback.message)
        return

    await callback.message.answer("Сценарий пока не реализован.")


@router.callback_query(F.data.startswith("recent:task:"))
async def handle_recent_task_open(callback: CallbackQuery, state: FSMContext) -> None:
    """Open a recent task from the inline list."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    task_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        task_id = int(task_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить task_id.")
        return

    await _send_task_status(callback.message, task_id, clear_to_menu=False)


@router.callback_query(F.data.startswith("recent:batch:stop:confirm:"))
async def handle_recent_batch_stop_confirm(callback: CallbackQuery) -> None:
    """Stop a specific launch after confirmation."""

    await callback.answer()
    batch_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        batch_id = int(batch_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить запуск.")
        return

    result = cancel_task_batch(batch_id)
    if result is None:
        await callback.message.answer("Запуск с таким ID не найден.")
        return

    await callback.message.answer(
        "Остановка запуска запрошена.\n\n"
        f"ID запуска: {result.batch_id}\n"
        f"Снято с очереди: {result.pending_cancelled}\n"
        f"Отмечено на остановку: {result.running_cancel_requested}",
    )
    await _send_batch_status(callback.message, batch_id)


@router.callback_query(F.data.startswith("recent:batch:stop:cancel:"))
async def handle_recent_batch_stop_cancel(callback: CallbackQuery) -> None:
    """Cancel stop confirmation for a specific launch."""

    await callback.answer("Отменено")
    batch_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        batch_id = int(batch_id_raw)
    except ValueError:
        await callback.message.answer("Остановка запуска отменена.")
        return
    await _send_batch_status(callback.message, batch_id)


@router.callback_query(F.data.startswith("recent:batch:stop:"))
async def handle_recent_batch_stop(callback: CallbackQuery) -> None:
    """Ask for confirmation before stopping a specific launch."""

    await callback.answer()
    batch_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        batch_id = int(batch_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить запуск.")
        return

    await callback.message.answer(
        "Остановить этот запуск?\n\n"
        "Будут остановлены только задачи внутри выбранного запуска.",
        reply_markup=build_confirm_stop_batch_keyboard(batch_id, soft=False),
    )


@router.callback_query(F.data.startswith("recent:batch:"))
async def handle_recent_batch_open(callback: CallbackQuery, state: FSMContext) -> None:
    """Open a recent launch from the inline list."""

    await callback.answer()
    await _clear_flow_state_preserving_settings(state)
    batch_id_raw = callback.data.rsplit(":", 1)[-1]
    try:
        batch_id = int(batch_id_raw)
    except ValueError:
        await callback.message.answer("Не удалось определить запуск.")
        return

    await _send_batch_status(callback.message, batch_id)


@router.message(AdHocCrawlStates.waiting_for_url)
async def handle_adhoc_url_input(message: Message, state: FSMContext) -> None:
    """Create an ad-hoc crawl task from a user-provided URL."""

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("Не вижу URL. Отправь адрес сайта, например https://example.com")
        return

    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли URL сайта.")
        return

    try:
        settings = await _get_adhoc_crawl_settings(state)
        result = launch_ad_hoc_crawl(raw_text, settings=settings)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer(
            "Не удалось запустить парсинг. Попробуй ещё раз чуть позже."
        )
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Парсинг запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Проект: {result.project_name}\n"
        f"Стартовый URL: {result.start_url}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(AdHocUrlListStates.waiting_for_urls)
async def handle_adhoc_url_list_input(message: Message, state: FSMContext) -> None:
    """Accumulate a fixed URL list from one or more user messages."""

    raw_text = (message.text or "").strip()
    raw_urls: list[str]

    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли список URL.")
        return

    if raw_text:
        raw_urls = [line.strip() for line in raw_text.splitlines() if line.strip()]
    elif message.document is not None:
        file_name = (message.document.file_name or "").lower()
        mime_type = (message.document.mime_type or "").lower()
        if not file_name.endswith(".txt") and mime_type not in {"text/plain", "application/octet-stream"}:
            await message.answer("Поддерживается только `.txt` файл со списком URL, один URL на строку.")
            return

        file = await message.bot.get_file(message.document.file_id)
        buffer = io.BytesIO()
        await message.bot.download(file, destination=buffer)
        file_bytes = buffer.getvalue()
        decoded_text = None
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                decoded_text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded_text is None:
            await message.answer("Не удалось прочитать `.txt` файл. Сохрани его в UTF-8 или Windows-1251.")
            return

        raw_urls = [line.strip() for line in decoded_text.splitlines() if line.strip()]
    else:
        await message.answer("Не вижу список URL. Отправь адреса сообщением или `.txt` файлом.")
        return

    if not raw_urls:
        await message.answer("Не удалось распознать URL. Отправь адреса сообщением или `.txt` файлом.")
        return

    user_id = message.from_user.id if message.from_user else 0
    lock = _get_url_list_buffer_lock(message.chat.id, user_id)
    async with lock:
        data = await state.get_data()
        buffered_urls = data.get(ADHOC_URL_LIST_BUFFER_STATE_KEY)
        if not isinstance(buffered_urls, list):
            buffered_urls = []
        buffered_urls.extend(raw_urls)
        await state.update_data({ADHOC_URL_LIST_BUFFER_STATE_KEY: buffered_urls})
        total_count = len(buffered_urls)
    await message.answer(
        "Список URL обновлён.\n\n"
        f"Добавлено в этом сообщении: {len(raw_urls)}\n"
        f"Всего в буфере: {total_count}\n\n"
        "Можешь прислать ещё одну порцию URL или нажать «Запустить список».",
        reply_markup=build_url_list_collect_keyboard(url_count=total_count),
    )


@router.message(YandexRecrawlUrlListStates.waiting_for_urls)
async def handle_yandex_recrawl_url_list_input(message: Message, state: FSMContext) -> None:
    """Accumulate URL additions, including Telegram-split text and TXT documents."""

    raw_urls = await _extract_urls_from_message(message)
    if raw_urls is None:
        return
    if not raw_urls:
        await message.answer("Не удалось распознать URL. Отправь адреса сообщением или `.txt` файлом.")
        return
    user_id = message.from_user.id if message.from_user else 0
    lock = _get_url_list_buffer_lock(message.chat.id, user_id)
    async with lock:
        data = await state.get_data()
        buffered_urls = data.get(YANDEX_RECRAWL_URL_BUFFER_STATE_KEY)
        if not isinstance(buffered_urls, list):
            buffered_urls = []
        buffered_urls.extend(raw_urls)
        await state.update_data({YANDEX_RECRAWL_URL_BUFFER_STATE_KEY: buffered_urls})
        total_count = len(buffered_urls)
    await message.answer(
        "Список URL обновлён.\n\n"
        f"Добавлено в этом сообщении: {len(raw_urls)}\n"
        f"Всего в буфере: {total_count}\n\n"
        "Можешь прислать ещё одну порцию URL или нажать «Добавить в очередь».",
        reply_markup=build_yandex_recrawl_collect_keyboard(url_count=total_count),
    )


@router.message(YandexAccessTokenStates.waiting_for_token)
async def handle_yandex_access_token_input(message: Message, state: FSMContext) -> None:
    """Store the root-admin's manually issued Yandex OAuth token."""

    user = message.from_user
    if user is None or not is_root_admin_user(user.id):
        await _clear_flow_state_preserving_settings(state)
        await message.answer("Добавить токен может только root-админ.")
        return
    token = (message.text or "").strip()
    if not token or token.startswith("/"):
        await message.answer("Пришли OAuth-токен Яндекс одним сообщением или отправь /cancel.")
        return
    try:
        expires_at = save_yandex_access_token(token)
    except (RuntimeError, ValueError) as error:
        await message.answer(f"Не удалось сохранить токен: {error}")
        return
    try:
        await message.delete()
    except Exception:
        pass
    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Токен Яндекс сохранён.\n\n"
        f"Плановая дата обновления: {expires_at.date().isoformat()}.\n"
        "Сообщение с токеном удалено из чата."
    )


async def _extract_urls_from_message(message: Message) -> list[str] | None:
    """Extract URL lines from text or a supported TXT attachment."""

    raw_text = (message.text or "").strip()
    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли список URL.")
        return None
    if raw_text:
        return [line.strip() for line in raw_text.splitlines() if line.strip()]
    if message.document is None:
        await message.answer("Не вижу список URL. Отправь адреса сообщением или `.txt` файлом.")
        return None

    file_name = (message.document.file_name or "").lower()
    mime_type = (message.document.mime_type or "").lower()
    if not file_name.endswith(".txt") and mime_type not in {"text/plain", "application/octet-stream"}:
        await message.answer("Поддерживается только `.txt` файл со списком URL, один URL на строку.")
        return None
    file = await message.bot.get_file(message.document.file_id)
    buffer = io.BytesIO()
    await message.bot.download(file, destination=buffer)
    file_bytes = buffer.getvalue()
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            decoded_text = file_bytes.decode(encoding)
            return [line.strip() for line in decoded_text.splitlines() if line.strip()]
        except UnicodeDecodeError:
            continue
    await message.answer("Не удалось прочитать `.txt` файл. Сохрани его в UTF-8 или Windows-1251.")
    return None


@router.message(AdHocSitemapStates.waiting_for_url)
async def handle_adhoc_sitemap_url_input(message: Message, state: FSMContext) -> None:
    """Create an ad-hoc sitemap parsing task from a user-provided URL."""

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("Не вижу URL. Отправь адрес sitemap, например https://example.com/sitemap.xml")
        return


@router.message(AccessUserStates.waiting_for_phone)
async def handle_access_user_phone_input(message: Message, state: FSMContext) -> None:
    """Add a bot allowlist user by phone number."""

    user = message.from_user
    if user is None or not is_root_admin_user(user.id):
        await _clear_flow_state_preserving_settings(state)
        await message.answer("Раздел доступа доступен только root-админу.")
        return

    phone_number: str | None = None
    if message.contact is not None:
        phone_number = message.contact.phone_number
    else:
        raw_text = (message.text or "").strip()
        if raw_text.startswith("/"):
            await message.answer("Сначала заверши текущий сценарий через /cancel или пришли номер телефона.")
            return
        if raw_text:
            phone_number = raw_text

    if not phone_number:
        await message.answer("Не вижу номер телефона. Пришли его текстом или контактом.")
        return

    try:
        access_user = add_allowed_bot_user(phone_number)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось добавить пользователя. Попробуй ещё раз чуть позже.")
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Пользователь добавлен в доступ.\n\n"
        f"Номер: {access_user.phone_number}",
        reply_markup=build_main_menu_keyboard(),
    )

    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли URL sitemap.")
        return

    try:
        sitemap_settings = await _get_sitemap_settings(state)
        result = launch_ad_hoc_sitemap(
            raw_text,
            resolve_status_codes=sitemap_settings["resolve_status_codes"],
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer(
            "Не удалось запустить парсинг sitemap. Попробуй ещё раз чуть позже."
        )
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Парсинг sitemap запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Sitemap URL: {result.sitemap_url}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(AdHocRobotsStates.waiting_for_url)
async def handle_adhoc_robots_url_input(message: Message, state: FSMContext) -> None:
    """Create an ad-hoc robots parsing task from a user-provided URL."""

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("Не вижу URL. Отправь адрес сайта или robots.txt.")
        return

    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли URL.")
        return

    try:
        sitemap_settings = await _get_sitemap_settings(state)
        result = launch_ad_hoc_robots(
            raw_text,
            resolve_status_codes=sitemap_settings["resolve_status_codes"],
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer(
            "Не удалось запустить парсинг robots.txt. Попробуй ещё раз чуть позже."
        )
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(
        "Парсинг robots.txt запущен.\n\n"
        f"ID запуска: {result.batch.id}\n"
        f"Robots URL: {result.robots_url}\n"
        f"Task ID: {result.task.id}\n"
        f"Тип задачи: {result.task.task_type}\n"
        f"Статус: {result.task.status.value}\n\n"
        "Проверить запуск можно через раздел Статус.",
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(TaskStatusStates.waiting_for_task_id)
async def handle_task_status_input(message: Message, state: FSMContext) -> None:
    """Check a task status and send its XLSX file when available."""

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer("Не вижу task_id. Отправь число, например 80.")
        return

    if raw_text.startswith("/"):
        await message.answer("Сначала заверши текущий сценарий через /cancel или пришли task_id.")
        return

    try:
        task_id = int(raw_text)
    except ValueError:
        await message.answer("Task ID должен быть числом, например 80.")
        return

    await _send_task_status(message, task_id, clear_to_menu=True)
    await _clear_flow_state_preserving_settings(state)


async def _send_recent_batches(message: Message) -> None:
    """Send recent launches with inline selection buttons."""

    recent_batches = list_recent_batches(limit=10)
    if not recent_batches:
        await message.answer("Пока нет ни одного запуска.")
        return

    await message.answer(
        "Последние запуски:\nВыбери нужный запуск кнопкой ниже.",
        reply_markup=build_recent_batches_keyboard(recent_batches),
    )


async def _send_parsing_settings(message: Message, state: FSMContext) -> None:
    """Send current crawl settings with quick inline controls."""

    settings = await _get_crawl_settings(state)
    await message.answer(
        "Настройки обычного парсинга:\n\n"
        f"{_format_default_project_settings(settings)}\n\n"
        "Как работают кнопки ниже:\n"
        "- ряд D1-D5 меняет глубину обхода\n"
        "- ряд P1-P5 меняет количество потоков\n"
        "- кнопки 100, 1000, 8000 и 20 000 задают максимум страниц\n"
        "- robots ON/OFF включает или выключает следование правилам robots.txt",
        reply_markup=build_parsing_settings_keyboard(
            callback_prefix="parsing:settings",
            current_depth=settings.max_depth,
            current_concurrency=settings.max_concurrency,
            current_pages=settings.max_pages,
            current_respect_robots=settings.respect_robots_disallow,
        ),
    )


async def _send_heavy_parsing_settings(message: Message, state: FSMContext) -> None:
    """Send current heavy crawl settings with quick inline controls."""

    settings = await _get_heavy_crawl_settings(state)
    await _edit_or_answer(
        message,
        "Настройки для тяжелых сайтов:\n\n"
        f"{_format_crawl_settings(settings)}\n\n"
        "Что за что отвечает:\n"
        "- глубина определяет, насколько далеко обход уходит по ссылкам\n"
        "- потоки задают, сколько страниц парсить одновременно\n"
        "- максимум страниц ограничивает общий объем обхода\n"
        "- robots.txt включает или выключает следование правилам сайта\n"
        "- задержка снижает нагрузку между запросами\n"
        "- таймаут ограничивает ожидание ответа от сайта\n"
        "- retry 5xx включает повтор при серверных ошибках\n"
        "- стоп по 5xx останавливает запуск, если ошибок слишком много\n"
        "- пауза retry задает ожидание перед повторной попыткой\n\n"
        "Нажми на нужный пункт ниже.",
        reply_markup=build_heavy_settings_menu_keyboard(settings),
    )


async def _send_sitemap_settings(message: Message, state: FSMContext) -> None:
    """Send current sitemap parsing settings."""

    settings = await _get_sitemap_settings(state)
    resolve_status_codes = settings["resolve_status_codes"]
    await _edit_or_answer(
        message,
        "Настройки парсинга sitemap:\n\n"
        f"- определять код ответа сервера: {'да' if resolve_status_codes else 'нет'}\n"
        "- добавлять в очередь на переобход: "
        f"{'да' if settings['replace_yandex_recrawl_queue'] else 'нет'}\n\n"
        "Если настройка выключена, sitemap будет разбираться и выгружаться без проверки HTTP-статуса каждой URL. "
        "Это особенно полезно для очень больших карт сайта.\n\n"
        "При включении URL из sitemap выбранного проекта заменят его файл очереди "
        "на переобход. Для режимов «Свой URL» и «Из robots.txt» очередь не меняется.",
        reply_markup=build_sitemap_settings_keyboard(
            resolve_status_codes=resolve_status_codes,
            replace_yandex_recrawl_queue=settings["replace_yandex_recrawl_queue"],
        ),
    )


async def _send_heavy_setting_picker(
    message: Message,
    settings: CrawlLaunchSettings,
    setting_name: str,
) -> None:
    """Send a compact picker for one heavy setting."""

    title, current_value, options = _get_heavy_setting_picker_data(settings, setting_name)
    if title is None or current_value is None or options is None:
        await message.answer("Не удалось открыть настройку.")
        return

    await _edit_or_answer(
        message,
        f"{title}\n\n"
        f"Сейчас: {current_value}\n\n"
        "Выбери значение:",
        reply_markup=build_heavy_setting_values_keyboard(
            setting_name=setting_name,
            options=options,
            current_value=_get_heavy_setting_raw_value(settings, setting_name),
        ),
    )


async def _edit_or_answer(message: Message, text: str, *, reply_markup) -> None:
    """Edit an existing bot message when possible, otherwise send a new one."""

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)


async def _send_batch_status(message: Message, batch_id: int) -> None:
    """Send launch status details and related tasks."""

    result = get_batch_status(batch_id)
    if result is None:
        await message.answer("Запуск с таким ID не найден.")
        return

    batch = result.batch
    tasks = result.tasks
    finished_tasks = sum(1 for task in tasks if task.status in {"success", "failed"})
    lines = [
        "Статус запуска:",
        "",
        f"ID запуска: {batch.id}",
        f"Название: {batch.title}",
        f"Тип запуска: {batch.batch_type.value}",
        f"Статус: {batch.status.value}",
        f"Задач всего: {len(tasks)}",
        f"Завершено: {finished_tasks}/{len(tasks)}",
    ]
    if batch.error_message:
        lines.extend(["", "Запуск завершился с ошибкой.", f"Ошибка: {batch.error_message}"])

    if len(tasks) == 1:
        task_status = get_task_status(tasks[0].task_id)
        if task_status is not None:
            progress_lines = _format_task_progress(task_status.task.result_payload)
            if progress_lines:
                lines.extend(["", "Прогресс:"])
                lines.extend(progress_lines)

    can_stop = batch.status.value in {"pending", "running"}
    await message.answer(
        "\n".join(lines),
        reply_markup=build_batch_actions_keyboard(
            batch_id=batch.id,
            can_stop=can_stop,
        ),
    )
    if tasks:
        await message.answer(
            "Задачи этого запуска:",
            reply_markup=build_recent_tasks_keyboard(tasks),
        )


async def _send_task_status(message: Message, task_id: int, *, clear_to_menu: bool) -> None:
    """Send task status details and XLSX file when ready."""

    result = get_task_status(task_id)
    if result is None:
        await message.answer("Задача с таким task_id не найдена.")
        return

    task = result.task
    lines = [
        "Статус задачи:",
        "",
        f"Task ID: {task.id}",
        f"ID запуска: {task.batch_id or '—'}",
        f"Тип задачи: {task.task_type}",
        f"Статус: {task.status.value}",
    ]
    if task.error_message:
        lines.extend(["", "Задача завершилась с ошибкой.", f"Ошибка: {task.error_message}"])

    progress_lines = _format_task_progress(task.result_payload)
    if progress_lines:
        lines.extend(["", "Прогресс:"])
        lines.extend(progress_lines)

    has_xlsx = result.xlsx_path is not None and result.xlsx_path.exists()
    has_csv = result.csv_path is not None and result.csv_path.exists()

    if task.status.value in {"pending", "running"}:
        if has_csv or has_xlsx:
            lines.extend(
                [
                    "",
                    "Запуск ещё выполняется, но уже доступен промежуточный результат из последней точки сохранения.",
                ]
            )
            await message.answer("\n".join(lines))
            if has_xlsx and result.xlsx_path is not None:
                await message.answer_document(FSInputFile(result.xlsx_path))
            if has_csv and result.csv_path is not None:
                await message.answer_document(FSInputFile(result.csv_path))
            if clear_to_menu:
                await message.answer("Готово.", reply_markup=build_main_menu_keyboard())
            return

        lines.append("")
        lines.append("Файлы результата ещё не готовы. Проверь задачу чуть позже.")
        await message.answer("\n".join(lines))
        return

    if task.status.value == "failed":
        if has_csv or has_xlsx:
            lines.extend(["", "Доступен частичный результат из последней точки сохранения."])
            await message.answer("\n".join(lines))
            if has_xlsx and result.xlsx_path is not None:
                await message.answer_document(FSInputFile(result.xlsx_path))
            if has_csv and result.csv_path is not None:
                await message.answer_document(FSInputFile(result.csv_path))
            if clear_to_menu:
                await message.answer("Готово.", reply_markup=build_main_menu_keyboard())
            return
        reply_markup = build_main_menu_keyboard() if clear_to_menu else None
        await message.answer("\n".join(lines), reply_markup=reply_markup)
        return

    if not has_xlsx and not has_csv:
        if task.task_type == "yandex_webmaster_recrawl":
            lines.extend(_format_yandex_recrawl_completion(task.result_payload, has_report=False))
        elif task.task_type == "fetch_robots":
            lines.extend(["", "Парсинг robots.txt завершён."])
        else:
            lines.extend(["", "Парсинг завершён, но файлы результата пока не найдены."])
        reply_markup = build_main_menu_keyboard() if clear_to_menu else None
        await message.answer("\n".join(lines), reply_markup=reply_markup)
        return

    if task.task_type == "yandex_webmaster_recrawl":
        lines.extend(_format_yandex_recrawl_completion(task.result_payload, has_report=True))
    else:
        lines.extend(["", "Парсинг завершён.", "Файлы результата готовы."])
    await message.answer("\n".join(lines))
    if has_xlsx and result.xlsx_path is not None:
        await message.answer_document(FSInputFile(result.xlsx_path))
    if has_csv and result.csv_path is not None:
        await message.answer_document(FSInputFile(result.csv_path))
    if clear_to_menu:
        await message.answer("Готово.", reply_markup=build_main_menu_keyboard())


def _format_yandex_recrawl_completion(result_payload: object, *, has_report: bool) -> list[str]:
    """Describe a recrawl task without calling it a parsing result."""

    payload = result_payload if isinstance(result_payload, dict) else {}
    status = payload.get("indexing_status")
    remaining_pages = payload.get("remaining_pages")
    lines = [""]
    if status == "completed":
        lines.append("Отправка на переобход завершена.")
    elif status == "quota_reached":
        lines.append("Достигнута квота Яндекс Вебмастера. Неотправленные URL остались в очереди.")
    elif isinstance(status, str) and status.startswith("api_error_"):
        lines.append("Отправка на переобход приостановлена из-за ошибки API. Неотправленные URL остались в очереди.")
    else:
        lines.append("Отправка на переобход завершена.")
    if isinstance(remaining_pages, int) and remaining_pages:
        lines.append(f"В очереди осталось: {remaining_pages} URL.")
    if has_report:
        lines.append("Файл отчета готов.")
    return lines


async def _get_crawl_settings(state: FSMContext) -> CrawlLaunchSettings:
    """Load crawl settings from FSM context or return defaults."""

    data = await state.get_data()
    raw_settings = data.get(CRAWL_SETTINGS_STATE_KEY)
    return _coerce_crawl_settings(raw_settings, build_default_crawl_settings())


async def _get_heavy_crawl_settings(state: FSMContext) -> CrawlLaunchSettings:
    """Load heavy crawl settings from FSM context or return heavy defaults."""

    data = await state.get_data()
    raw_settings = data.get(HEAVY_CRAWL_SETTINGS_STATE_KEY)
    return _coerce_crawl_settings(raw_settings, build_heavy_crawl_settings())


async def _get_adhoc_crawl_settings(state: FSMContext) -> CrawlLaunchSettings:
    """Load ad-hoc crawl settings according to the selected profile."""

    data = await state.get_data()
    profile = data.get(ADHOC_CRAWL_PROFILE_STATE_KEY)
    if profile == "heavy":
        return await _get_heavy_crawl_settings(state)
    return await _get_crawl_settings(state)


async def _get_sitemap_settings(state: FSMContext) -> dict[str, bool]:
    """Load sitemap parsing settings from FSM context or return defaults."""

    data = await state.get_data()
    raw_settings = data.get(SITEMAP_SETTINGS_STATE_KEY)
    if not isinstance(raw_settings, dict):
        return {
            "resolve_status_codes": True,
            "replace_yandex_recrawl_queue": False,
        }
    return {
        "resolve_status_codes": bool(raw_settings.get("resolve_status_codes", True)),
        "replace_yandex_recrawl_queue": bool(raw_settings.get("replace_yandex_recrawl_queue", False)),
    }


async def _set_crawl_settings(state: FSMContext, settings: CrawlLaunchSettings) -> None:
    """Persist crawl settings in FSM context."""

    await state.update_data(
        {
            CRAWL_SETTINGS_STATE_KEY: {
                "max_depth": settings.max_depth,
                "max_concurrency": settings.max_concurrency,
                "max_pages": settings.max_pages,
                "respect_robots_disallow": settings.respect_robots_disallow,
                "delay_between_requests_ms": settings.delay_between_requests_ms,
                "request_timeout_seconds": settings.request_timeout_seconds,
                "retry_on_5xx": settings.retry_on_5xx,
                "max_5xx_before_stop": settings.max_5xx_before_stop,
                "retry_delay_ms": settings.retry_delay_ms,
            }
        }
    )


async def _set_heavy_crawl_settings(state: FSMContext, settings: CrawlLaunchSettings) -> None:
    """Persist heavy crawl settings in FSM context."""

    await state.update_data(
        {
            HEAVY_CRAWL_SETTINGS_STATE_KEY: {
                "max_depth": settings.max_depth,
                "max_concurrency": settings.max_concurrency,
                "max_pages": settings.max_pages,
                "respect_robots_disallow": settings.respect_robots_disallow,
                "delay_between_requests_ms": settings.delay_between_requests_ms,
                "request_timeout_seconds": settings.request_timeout_seconds,
                "retry_on_5xx": settings.retry_on_5xx,
                "max_5xx_before_stop": settings.max_5xx_before_stop,
                "retry_delay_ms": settings.retry_delay_ms,
            }
        }
    )


async def _set_sitemap_settings(state: FSMContext, settings: dict[str, bool]) -> None:
    """Persist sitemap parsing settings in FSM context."""

    await state.update_data(
        {
            SITEMAP_SETTINGS_STATE_KEY: {
                "resolve_status_codes": bool(settings.get("resolve_status_codes", True)),
                "replace_yandex_recrawl_queue": bool(settings.get("replace_yandex_recrawl_queue", False)),
            }
        }
    )


async def _clear_flow_state_preserving_settings(state: FSMContext) -> None:
    """Clear conversational state while keeping crawl settings."""

    settings = await _get_crawl_settings(state)
    heavy_settings = await _get_heavy_crawl_settings(state)
    sitemap_settings = await _get_sitemap_settings(state)
    await state.clear()
    await _set_crawl_settings(state, settings)
    await _set_heavy_crawl_settings(state, heavy_settings)
    await _set_sitemap_settings(state, sitemap_settings)


def _format_crawl_settings(settings: CrawlLaunchSettings) -> str:
    """Format crawl settings for bot messages."""

    return (
        f"- глубина: {settings.max_depth}\n"
        f"- потоков: {settings.max_concurrency}\n"
        f"- максимум страниц: {settings.max_pages}\n"
        f"- robots.txt: {'да' if settings.respect_robots_disallow else 'нет'}\n"
        f"- задержка: {_format_ms(settings.delay_between_requests_ms)}\n"
        f"- таймаут: {settings.request_timeout_seconds} с\n"
        f"- retry 5xx: {'да' if settings.retry_on_5xx else 'нет'}\n"
        f"- стоп по 5xx: {settings.max_5xx_before_stop}\n"
        f"- пауза retry: {_format_ms(settings.retry_delay_ms)}"
    )


def _format_default_project_settings(settings: CrawlLaunchSettings) -> str:
    """Format a short settings block for ordinary project selection."""

    return (
        f"- глубина: {settings.max_depth}\n"
        f"- потоков: {settings.max_concurrency}\n"
        f"- максимум страниц: {settings.max_pages}\n"
        f"- robots.txt: {'да' if settings.respect_robots_disallow else 'нет'}"
    )


def _format_ms(value: int) -> str:
    """Format milliseconds in short Russian form."""

    if value >= 1000 and value % 1000 == 0:
        return f"{value // 1000} с"
    return f"{value} мс"


def _format_task_progress(result_payload: object) -> list[str]:
    """Extract compact progress lines from a task result payload."""

    if not isinstance(result_payload, dict):
        return []

    pages_crawled = result_payload.get("pages_crawled")
    pages_discovered = result_payload.get("pages_discovered")
    submitted_pages = result_payload.get("submitted_pages")
    remaining_pages = result_payload.get("remaining_pages")
    indexing_status = result_payload.get("indexing_status")
    indexing_error = result_payload.get("indexing_error")
    recrawl_pages_per_minute = result_payload.get("recrawl_pages_per_minute")
    recrawl_checkpoint_at = result_payload.get("recrawl_checkpoint_at")
    recrawl_queue_replaced = result_payload.get("recrawl_queue_replaced")
    recrawl_queue_url_count = result_payload.get("recrawl_queue_url_count")
    suspicious_relative_links_count = result_payload.get("suspicious_relative_links_count")
    url_count = result_payload.get("url_count")
    resolve_status_codes = result_payload.get("resolve_status_codes")
    resolved_status_count = result_payload.get("resolved_status_count")
    status_code = result_payload.get("status_code")
    sitemap_type = result_payload.get("sitemap_type")
    sitemaps = result_payload.get("sitemaps")
    rules = result_payload.get("rules")
    final_url = result_payload.get("final_url")

    if (
        not isinstance(pages_crawled, int)
        and not isinstance(pages_discovered, int)
        and not isinstance(url_count, int)
        and not isinstance(status_code, int)
        and not isinstance(submitted_pages, int)
    ):
        return []

    lines: list[str] = []
    if isinstance(status_code, int):
        lines.append(f"- HTTP-статус: {status_code}")
    if isinstance(final_url, str) and final_url:
        lines.append(f"- итоговый URL: {final_url}")
    if isinstance(sitemap_type, str) and sitemap_type:
        lines.append(f"- тип sitemap: {sitemap_type}")
    if isinstance(url_count, int):
        lines.append(f"- найдено URL в sitemap: {url_count}")
        if isinstance(resolve_status_codes, bool):
            lines.append(
                "- определение кода ответа сервера: "
                + ("включено" if resolve_status_codes else "выключено")
            )
        if isinstance(resolved_status_count, int) and resolve_status_codes:
            lines.append(f"- URL с определённым кодом ответа: {resolved_status_count}")
    if recrawl_queue_replaced is True and isinstance(recrawl_queue_url_count, int):
        lines.append(f"- очередь на переобход обновлена: {recrawl_queue_url_count} URL")

    if isinstance(pages_crawled, int):
        lines.append(f"- последняя точка сохранения: {pages_crawled} страниц")
    if isinstance(pages_discovered, int):
        lines.append(f"- найдено URL: {pages_discovered}")
    if isinstance(submitted_pages, int):
        lines.append(f"- отправлено на переобход: {submitted_pages}")
    if isinstance(remaining_pages, int):
        lines.append(f"- осталось в очереди: {remaining_pages}")
    if isinstance(recrawl_pages_per_minute, int | float):
        lines.append(f"- скорость отправки: {recrawl_pages_per_minute:.1f} URL/мин")
    if isinstance(recrawl_checkpoint_at, str) and recrawl_checkpoint_at:
        lines.append(f"- обновлено: {recrawl_checkpoint_at}")
    if isinstance(indexing_status, str) and indexing_status:
        lines.append(f"- результат отправки: {indexing_status}")
    if isinstance(indexing_error, str) and indexing_error:
        lines.append(f"- ошибка API: {indexing_error}")
    if isinstance(suspicious_relative_links_count, int) and suspicious_relative_links_count:
        lines.append(
            "- относительных ссылок без / исключено из обхода: "
            f"{suspicious_relative_links_count}"
        )

    status_summary = result_payload.get("status_summary")
    if isinstance(status_summary, dict) and status_summary:
        summary_chunks: list[str] = []
        for key, value in sorted(status_summary.items(), key=lambda item: item[0]):
            summary_chunks.append(f"{key}={value}")
        lines.append(f"- статусы: {', '.join(summary_chunks)}")

    progress = result_payload.get("progress")
    if isinstance(progress, dict):
        last_processed_url = progress.get("last_processed_url")
        last_checkpoint_at = progress.get("last_checkpoint_at")
        if isinstance(last_processed_url, str) and last_processed_url:
            lines.append(f"- последний URL: {last_processed_url}")
        if isinstance(last_checkpoint_at, str) and last_checkpoint_at:
            lines.append(f"- checkpoint: {last_checkpoint_at}")

    if isinstance(sitemaps, list):
        lines.append(f"- sitemap-директив найдено: {len(sitemaps)}")
        preview = [item for item in sitemaps[:3] if isinstance(item, str) and item]
        if preview:
            lines.append(f"- первые sitemap: {', '.join(preview)}")

    if isinstance(rules, list):
        lines.append(f"- групп правил найдено: {len(rules)}")

    return lines


def _get_heavy_setting_picker_data(
    settings: CrawlLaunchSettings,
    setting_name: str,
) -> tuple[str | None, str | None, list[tuple[str, str]] | None]:
    """Return title, current value and options for one heavy setting picker."""

    if setting_name == "depth":
        return (
            "Глубина обхода",
            str(settings.max_depth),
            [(str(value), str(value)) for value in (1, 2, 3, 4, 5)],
        )
    if setting_name == "concurrency":
        return (
            "Количество потоков",
            str(settings.max_concurrency),
            [(str(value), str(value)) for value in HEAVY_CONCURRENCY_OPTIONS],
        )
    if setting_name == "pages":
        return (
            "Максимум страниц",
            _format_pages_label(settings.max_pages),
            [(str(value), _format_pages_label(value)) for value in HEAVY_PAGE_OPTIONS],
        )
    if setting_name == "delay":
        return (
            "Задержка между запросами",
            _format_ms(settings.delay_between_requests_ms),
            [(str(value), _format_ms(value)) for value in HEAVY_DELAY_OPTIONS],
        )
    if setting_name == "timeout":
        return (
            "Таймаут запроса",
            f"{settings.request_timeout_seconds} с",
            [(str(value), f"{value} с") for value in HEAVY_TIMEOUT_OPTIONS],
        )
    if setting_name == "max5xx":
        return (
            "Стоп по ответам 5xx",
            str(settings.max_5xx_before_stop),
            [(str(value), str(value)) for value in HEAVY_MAX_5XX_OPTIONS],
        )
    if setting_name == "retrydelay":
        return (
            "Пауза перед retry",
            _format_ms(settings.retry_delay_ms),
            [(str(value), _format_ms(value)) for value in HEAVY_RETRY_DELAY_OPTIONS],
        )
    return None, None, None


def _get_heavy_setting_raw_value(settings: CrawlLaunchSettings, setting_name: str) -> str:
    """Return raw current value string for the heavy setting picker."""

    mapping = {
        "depth": str(settings.max_depth),
        "concurrency": str(settings.max_concurrency),
        "pages": str(settings.max_pages),
        "delay": str(settings.delay_between_requests_ms),
        "timeout": str(settings.request_timeout_seconds),
        "max5xx": str(settings.max_5xx_before_stop),
        "retrydelay": str(settings.retry_delay_ms),
    }
    return mapping.get(setting_name, "")


def _with_updated_heavy_setting(
    settings: CrawlLaunchSettings,
    setting_name: str,
    setting_value: str,
) -> CrawlLaunchSettings | None:
    """Return updated heavy settings after changing one scalar field."""

    try:
        numeric_value = int(setting_value)
    except ValueError:
        return None

    if setting_name == "depth":
        return CrawlLaunchSettings(
            max_depth=numeric_value,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "concurrency":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=numeric_value,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "pages":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=numeric_value,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "delay":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=numeric_value,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "timeout":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=numeric_value,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "max5xx":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=numeric_value,
            retry_delay_ms=settings.retry_delay_ms,
        )
    if setting_name == "retrydelay":
        return CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=numeric_value,
        )
    return None


def _format_pages_label(value: int) -> str:
    """Format page count for human-readable heavy pickers."""

    if value >= 1000:
        return f"{value // 1000}k"
    return str(value)


def _coerce_crawl_settings(raw_settings: object, defaults: CrawlLaunchSettings) -> CrawlLaunchSettings:
    """Convert FSM data to CrawlLaunchSettings with fallback defaults."""

    if not isinstance(raw_settings, dict):
        return defaults

    try:
        return CrawlLaunchSettings(
            max_depth=int(raw_settings.get("max_depth", defaults.max_depth)),
            max_concurrency=int(raw_settings.get("max_concurrency", defaults.max_concurrency)),
            max_pages=int(raw_settings.get("max_pages", defaults.max_pages)),
            respect_robots_disallow=bool(
                raw_settings.get("respect_robots_disallow", defaults.respect_robots_disallow)
            ),
            delay_between_requests_ms=int(
                raw_settings.get("delay_between_requests_ms", defaults.delay_between_requests_ms)
            ),
            request_timeout_seconds=int(
                raw_settings.get("request_timeout_seconds", defaults.request_timeout_seconds)
            ),
            retry_on_5xx=bool(raw_settings.get("retry_on_5xx", defaults.retry_on_5xx)),
            max_5xx_before_stop=int(
                raw_settings.get("max_5xx_before_stop", defaults.max_5xx_before_stop)
            ),
            retry_delay_ms=int(raw_settings.get("retry_delay_ms", defaults.retry_delay_ms)),
        )
    except (TypeError, ValueError):
        return defaults


async def _apply_settings_change(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    settings: CrawlLaunchSettings,
    setter,
    refresh,
    prefix: str,
    default_settings: CrawlLaunchSettings,
) -> None:
    """Apply one inline settings change and refresh the settings screen."""

    if callback.data == f"{prefix}reset":
        await setter(state, default_settings)
        await refresh(callback.message, state)
        return

    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.message.answer("Не удалось изменить настройку.")
        return

    setting_name = parts[2]
    setting_value = parts[3]
    updated = settings

    if setting_name == "depth":
        updated = CrawlLaunchSettings(
            max_depth=int(setting_value),
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "concurrency":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=int(setting_value),
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "pages":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=int(setting_value),
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "robots" and setting_value == "toggle":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=not settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "delay":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=int(setting_value),
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "timeout":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=int(setting_value),
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "retry5xx" and setting_value == "toggle":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=not settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "max5xx":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=int(setting_value),
            retry_delay_ms=settings.retry_delay_ms,
        )
    elif setting_name == "retrydelay":
        updated = CrawlLaunchSettings(
            max_depth=settings.max_depth,
            max_concurrency=settings.max_concurrency,
            max_pages=settings.max_pages,
            respect_robots_disallow=settings.respect_robots_disallow,
            delay_between_requests_ms=settings.delay_between_requests_ms,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_on_5xx=settings.retry_on_5xx,
            max_5xx_before_stop=settings.max_5xx_before_stop,
            retry_delay_ms=int(setting_value),
        )
    else:
        await callback.message.answer("Неизвестная настройка.")
        return

    await setter(state, updated)
    await refresh(callback.message, state)


async def _start_project_wizard(message: Message, state: FSMContext, *, project_id: int | None = None) -> None:
    """Start project creation or editing wizard."""

    await _clear_flow_state_preserving_settings(state)
    project = get_project(project_id) if project_id is not None else None
    if project_id is not None and project is None:
        await message.answer("Проект не найден.")
        return

    wizard = {
        "mode": "edit" if project is not None else "create",
        "project_id": project.id if project is not None else None,
        "project_name": project.project_name if project is not None else None,
        "crawl_segment": project.crawl_segment.value if project is not None else CrawlSegment.DEFAULT.value,
        "start_url": project.start_url if project is not None else None,
        "sitemap_path": project.sitemap_path if project is not None else None,
        "yandex_webmaster_host": project.yandex_webmaster_host if project is not None else None,
        "contain_subdomains": project.contain_subdomains if project is not None else False,
        "is_multi_sitemap": project.is_multi_sitemap if project is not None else False,
        "pagination_view": project.pagination_view if project is not None else None,
        "pagination_sample": project.pagination_sample if project is not None else None,
        "pagination_marker": project.pagination_marker if project is not None else None,
        "card_sample": project.card_sample if project is not None else None,
        "category_sample": project.category_sample if project is not None else None,
        "current_field": "project_name",
    }
    await state.update_data({PROJECT_WIZARD_STATE_KEY: wizard})
    await state.set_state(ProjectWizardStates.waiting_for_project_name)

    title = "Редактирование проекта" if project is not None else "Добавление проекта"
    current_hint = f"\n\nТекущее значение: {project.project_name}" if project is not None else ""
    await message.answer(
        f"{title}\n\nШаг 1/12\nНазвание проекта.{current_hint}\n\nПришли новое значение.",
        reply_markup=build_main_menu_keyboard(),
    )


async def _get_project_wizard(state: FSMContext) -> dict:
    """Return current project wizard draft."""

    data = await state.get_data()
    wizard = data.get(PROJECT_WIZARD_STATE_KEY)
    return wizard if isinstance(wizard, dict) else {}


async def _set_project_wizard_field(state: FSMContext, field_name: str, value: object) -> None:
    """Persist one field inside the project wizard draft."""

    wizard = await _get_project_wizard(state)
    wizard[field_name] = value
    await state.update_data({PROJECT_WIZARD_STATE_KEY: wizard})


async def _advance_project_wizard(message: Message, state: FSMContext, current_field: str) -> None:
    """Move the wizard to the next field or finish it."""

    wizard = await _get_project_wizard(state)
    if wizard.get("mode") == "edit_field":
        await _finish_project_wizard(message, state)
        return

    try:
        current_index = PROJECT_WIZARD_FIELD_ORDER.index(current_field)
    except ValueError:
        await message.answer("Не удалось продолжить мастер проекта.")
        return

    next_index = current_index + 1
    if next_index >= len(PROJECT_WIZARD_FIELD_ORDER):
        await _finish_project_wizard(message, state)
        return

    next_field = PROJECT_WIZARD_FIELD_ORDER[next_index]
    wizard = await _get_project_wizard(state)
    wizard["current_field"] = next_field
    await state.update_data({PROJECT_WIZARD_STATE_KEY: wizard})
    await _prompt_project_wizard_field(message, state, next_field)


async def _prompt_project_wizard_field(message: Message, state: FSMContext, field_name: str) -> None:
    """Prompt the user for one project wizard field."""

    wizard = await _get_project_wizard(state)
    mode = wizard.get("mode", "create")
    is_edit = mode == "edit"
    is_edit_field = mode == "edit_field"
    current_value = wizard.get(field_name)
    step_number = PROJECT_WIZARD_FIELD_ORDER.index(field_name) + 1
    keep_label = "Очистить" if is_edit_field else ("Оставить как есть" if is_edit else "Пропустить")
    current_line = f"\n\nТекущее значение: {current_value}" if current_value not in {None, ""} else ""

    await state.set_state(PROJECT_WIZARD_STATE_BY_FIELD[field_name])

    if field_name == "crawl_segment":
        await message.answer(
            f"Шаг {step_number}/12\nСегмент проекта.{current_line}",
            reply_markup=build_project_segment_keyboard(
                callback_prefix="projects:wizard:segment",
                current_segment=str(current_value) if current_value else None,
            ),
        )
        return

    if field_name in {"contain_subdomains", "is_multi_sitemap"}:
        await message.answer(
            f"Шаг {step_number}/12\n{_project_field_label(field_name)}.{current_line}",
            reply_markup=build_project_boolean_keyboard(
                callback_prefix=f"projects:wizard:boolean:{field_name}",
                current_value=bool(current_value),
            ),
        )
        return

    optional_fields = {
        "sitemap_path",
        "yandex_webmaster_host",
        "pagination_view",
        "pagination_sample",
        "pagination_marker",
        "card_sample",
        "category_sample",
    }
    reply_markup = None
    if field_name in optional_fields:
        reply_markup = build_project_text_action_keyboard(skip_label=keep_label)

    await message.answer(
        f"Шаг {step_number}/12\n{_project_field_label(field_name)}.{current_line}\n\n"
        f"{_project_field_prompt(field_name, is_edit=is_edit)}",
        reply_markup=reply_markup,
    )


async def _handle_project_wizard_segment(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle project segment selection."""

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.message.answer("Не удалось определить сегмент проекта.")
        return

    segment_value = parts[3]
    if segment_value not in {CrawlSegment.DEFAULT.value, CrawlSegment.HEAVY.value}:
        await callback.message.answer("Не удалось определить сегмент проекта.")
        return

    await _set_project_wizard_field(state, "crawl_segment", segment_value)
    await _advance_project_wizard(callback.message, state, "crawl_segment")


async def _handle_project_wizard_boolean(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle yes/no project wizard steps."""

    parts = (callback.data or "").split(":")
    if len(parts) != 5:
        await callback.message.answer("Не удалось определить значение.")
        return

    field_name = parts[3]
    raw_value = parts[4]
    if raw_value not in {"yes", "no"}:
        await callback.message.answer("Не удалось определить значение.")
        return

    await _set_project_wizard_field(state, field_name, raw_value == "yes")
    await _advance_project_wizard(callback.message, state, field_name)


async def _handle_project_wizard_skip(message: Message, state: FSMContext) -> None:
    """Skip current optional project wizard field."""

    wizard = await _get_project_wizard(state)
    current_field = wizard.get("current_field")
    if not isinstance(current_field, str):
        await message.answer("Не удалось определить шаг мастера.")
        return

    if wizard.get("mode") == "create" or wizard.get("mode") == "edit_field":
        await _set_project_wizard_field(state, current_field, None)

    await _advance_project_wizard(message, state, current_field)


async def _finish_project_wizard(message: Message, state: FSMContext) -> None:
    """Create or update the project from the wizard draft."""

    wizard = await _get_project_wizard(state)
    mode = wizard.get("mode", "create")

    try:
        project_name = _require_project_value(wizard.get("project_name"), "Название проекта обязательно.")
        start_url = _normalize_project_url_value(wizard.get("start_url"))
        if start_url is None:
            raise ValueError("Нужен хотя бы start_url проекта.")
        sitemap_path = _normalize_optional_project_value(wizard.get("sitemap_path"))
        crawl_segment = CrawlSegment(wizard.get("crawl_segment", CrawlSegment.DEFAULT.value))
        yandex_webmaster_host = _normalize_optional_project_value(wizard.get("yandex_webmaster_host"))
        pagination_view = _normalize_optional_project_value(wizard.get("pagination_view"))
        pagination_sample = _normalize_optional_project_value(wizard.get("pagination_sample"))
        pagination_marker = _normalize_optional_project_value(wizard.get("pagination_marker"))
        card_sample = _normalize_optional_project_value(wizard.get("card_sample"))
        category_sample = _normalize_optional_project_value(wizard.get("category_sample"))
        contain_subdomains = bool(wizard.get("contain_subdomains", False))
        is_multi_sitemap = bool(wizard.get("is_multi_sitemap", False))

        if mode in {"edit", "edit_field"}:
            project_id = wizard.get("project_id")
            if not isinstance(project_id, int):
                await message.answer("Не удалось определить проект для сохранения.")
                return
            project = update_project(
                project_id,
                project_name=project_name,
                sitemap_path=sitemap_path,
                start_url=start_url,
                crawl_segment=crawl_segment,
                is_multi_sitemap=is_multi_sitemap,
                pagination_view=pagination_view,
                yandex_webmaster_host=yandex_webmaster_host,
                pagination_sample=pagination_sample,
                pagination_marker=pagination_marker,
                card_sample=card_sample,
                category_sample=category_sample,
                contain_subdomains=contain_subdomains,
            )
            if project is None:
                await message.answer("Проект не найден.")
                return
            result_text = f"Проект обновлён.\n\nID проекта: {project.id}\nНазвание: {project.project_name}"
        else:
            project = create_project(
                project_name=project_name,
                sitemap_path=sitemap_path,
                start_url=start_url,
                crawl_segment=crawl_segment,
                is_multi_sitemap=is_multi_sitemap,
                pagination_view=pagination_view,
                yandex_webmaster_host=yandex_webmaster_host,
                pagination_sample=pagination_sample,
                pagination_marker=pagination_marker,
                card_sample=card_sample,
                category_sample=category_sample,
                contain_subdomains=contain_subdomains,
            )
            result_text = f"Проект создан.\n\nID проекта: {project.id}\nНазвание: {project.project_name}"
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await _clear_flow_state_preserving_settings(state)
    await message.answer(result_text, reply_markup=build_main_menu_keyboard())
    if mode in {"edit", "edit_field"}:
        await _send_project_card(message, project.id)


async def _send_project_card(message: Message, project_id: int) -> None:
    """Send one project card with its settings."""

    project = get_project(project_id)
    if project is None:
        await message.answer("Проект не найден.")
        return

    lines = [
        f"Проект: {project.project_name}",
        "",
        f"ID проекта: {project.id}",
        f"Сегмент: {project.crawl_segment.value}",
        f"Стартовый URL: {project.start_url or '—'}",
        f"Sitemap: {project.sitemap_path or '—'}",
        f"Хост Яндекс Вебмастера: {project.yandex_webmaster_host or '—'}",
        f"Несколько sitemap: {'да' if project.is_multi_sitemap else 'нет'}",
        f"Поддомены: {'да' if project.contain_subdomains else 'нет'}",
        f"Вид пагинации: {project.pagination_view or '—'}",
        f"Пример пагинации: {project.pagination_sample or '—'}",
        f"Маркер пагинации: {project.pagination_marker or '—'}",
        f"Пример карточки: {project.card_sample or '—'}",
        f"Пример категории: {project.category_sample or '—'}",
    ]
    await message.answer("\n".join(lines), reply_markup=build_project_card_keyboard(project.id))


def _parse_callback_id(value: str) -> int | None:
    """Parse trailing integer from callback data."""

    try:
        return int(value.rsplit(":", 1)[-1])
    except ValueError:
        return None


async def _start_project_field_edit(message: Message, state: FSMContext, *, project_id: int, field_name: str) -> None:
    """Start focused editing for a single project field."""

    project = get_project(project_id)
    if project is None:
        await message.answer("Проект не найден.")
        return

    if field_name not in PROJECT_WIZARD_FIELD_ORDER:
        await message.answer("Не удалось определить поле проекта.")
        return

    await _clear_flow_state_preserving_settings(state)
    wizard = {
        "mode": "edit_field",
        "project_id": project.id,
        "project_name": project.project_name,
        "crawl_segment": project.crawl_segment.value,
        "start_url": project.start_url,
        "sitemap_path": project.sitemap_path,
        "yandex_webmaster_host": project.yandex_webmaster_host,
        "contain_subdomains": project.contain_subdomains,
        "is_multi_sitemap": project.is_multi_sitemap,
        "pagination_view": project.pagination_view,
        "pagination_sample": project.pagination_sample,
        "pagination_marker": project.pagination_marker,
        "card_sample": project.card_sample,
        "category_sample": project.category_sample,
        "current_field": field_name,
    }
    await state.update_data({PROJECT_WIZARD_STATE_KEY: wizard})
    await _prompt_project_wizard_field(message, state, field_name)


def _project_field_label(field_name: str) -> str:
    """Return Russian label for one project wizard field."""

    labels = {
        "project_name": "Название проекта",
        "start_url": "Стартовый URL",
        "sitemap_path": "Путь к sitemap",
        "yandex_webmaster_host": "Хост Яндекс Вебмастера",
        "contain_subdomains": "Содержит поддомены",
        "is_multi_sitemap": "Multi sitemap",
        "pagination_view": "Вид пагинации",
        "pagination_sample": "Пример пагинации",
        "pagination_marker": "Маркер пагинации",
        "card_sample": "Пример карточки",
        "category_sample": "Пример категории",
    }
    return labels.get(field_name, field_name)


def _project_field_prompt(field_name: str, *, is_edit: bool) -> str:
    """Return a short prompt for one project wizard field."""

    base_prompts = {
        "project_name": "Пришли название проекта.",
        "start_url": "Пришли URL сайта или нажми кнопку пропуска.",
        "sitemap_path": "Пришли полный URL sitemap или нажми кнопку пропуска.",
        "yandex_webmaster_host": "Пришли хост Яндекс Вебмастера или нажми кнопку пропуска.",
        "pagination_view": "Пришли значение или нажми кнопку пропуска.",
        "pagination_sample": "Пришли значение или нажми кнопку пропуска.",
        "pagination_marker": "Пришли значение или нажми кнопку пропуска.",
        "card_sample": "Пришли значение или нажми кнопку пропуска.",
        "category_sample": "Пришли значение или нажми кнопку пропуска.",
    }
    prompt = base_prompts.get(field_name, "Пришли значение.")
    if is_edit and field_name != "sitemap_path":
        return prompt.replace("нажми кнопку пропуска", "нажми «Оставить как есть»")
    return prompt


def _normalize_project_text_value(value: str) -> str:
    """Normalize text received from the project wizard."""

    return value.strip()


def _normalize_optional_project_value(value: object) -> str | None:
    """Normalize optional wizard values to strings or None."""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_project_url_value(value: object) -> str | None:
    """Normalize optional URL-like project values."""

    normalized = _normalize_optional_project_value(value)
    if normalized is None:
        return None
    if "://" not in normalized:
        return f"https://{normalized}"
    return normalized


def _require_project_value(value: object, error_message: str) -> str:
    """Ensure a required wizard field has a non-empty value."""

    normalized = _normalize_optional_project_value(value)
    if normalized is None:
        raise ValueError(error_message)
    return normalized
