# Yandex Webmaster Token And Recrawl

The application uses one shared manually issued Yandex OAuth token for Webmaster, Metrika and future Yandex integrations.

## Token setup

Only `SECRETS_ENCRYPTION_KEY` is required in `.env.production`:

```env
SECRETS_ENCRYPTION_KEY=...
```

Generate the Fernet encryption key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not change `SECRETS_ENCRYPTION_KEY` after a token is saved: it encrypts the OAuth token stored in PostgreSQL.

Create a Yandex OAuth application once, issue a personal Webmaster token according to the [Yandex Webmaster guide](https://yandex.ru/dev/webmaster/doc/ru/tasks/how-to-get-oauth), then open `Индексирование -> Подключение Яндекс` as root admin and send the token to the bot. The bot deletes the message after saving it and stores the token encrypted.

Yandex Webmaster documents a token lifetime of up to six months. The bot shows the planned renewal date and lets the root admin replace the token from the same screen.

## Recrawl queue

Place a project queue at:

```text
storage/indexing/yandex_webmaster/recrawl/<project-slug>.csv
```

The input file needs one URL column named `URL`, `url`, `urls`, or `URL страницы`. The application writes a technical `queue_id` column next to it; do not edit this value manually. URLs accepted by Yandex Webmaster are removed from the same queue. The bot can prepend or append more URLs while a worker is running; duplicates are preserved deliberately.

The aggregate report is updated at:

```text
storage/reports/indexing_report.xlsx
```
