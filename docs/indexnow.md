# IndexNow Setup

The bot sends queued URLs through Yandex's IndexNow endpoint. A successful `200` or `202` response means that the batch has been accepted; it does not guarantee immediate indexing.

## Prepare A Site

1. In the bot, open `Индексирование -> IndexNow -> Настроить ключ` and select the project.
2. Choose `Создать новый ключ` to receive a ready `<key>.txt` file, or `Ввести существующий ключ` if the file is already on the site.
3. Place a UTF-8 `.txt` file containing that exact key on the site's host.
4. For an existing key, send the key and then the full public URL of its `.txt` file.

If the file is stored at the host root and is named `<key>.txt`, send `-` instead of its URL. The protocol will use the default location.

The key is encrypted in the application database and is never shown by the bot after saving. The `.txt` file must remain publicly available on the website.

## Queue Behaviour

- Queue files are stored under `storage/indexing/indexnow/submit/<project-slug>.csv`.
- A manually placed CSV may contain just a `URL` column; the application adds its internal identifiers on the first successful queue update.
- Add URLs in the bot at the beginning or end of a project's queue. Text split by Telegram and `.txt` attachments are both supported.
- One IndexNow request contains at most 10,000 URLs for one host.
- Accepted batches are removed from the queue. Failed batches remain for a later retry.
- A project queue must contain URLs belonging to its configured start-URL host.
- Every completed attempt appends an aggregate row to `storage/reports/indexing_report.xlsx` with channel `indexnow`.

Only submit URLs that were added, updated, or removed. IndexNow confirms notification delivery, not an indexing guarantee.
