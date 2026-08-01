# Static Sitemaps

This workflow creates a local, publishable copy of a project's sitemap structure without flattening all URLs into one file.

## Create A Snapshot

In Telegram open `Индексирование` -> `Статические карты` -> `Создать статическую карту` and choose one project or `Сделать всем`.

For a sitemap index, every leaf `urlset` is saved separately. A generated `sitemap-index.xml` references those files. A new successful run replaces the previous snapshot for that project completely.

The files are stored here:

```text
storage/static_sitemaps/<project-slug>/
```

## Publish And Register

1. Upload the XML files from the project folder to the site's `/static_sitemap/` directory. Do not upload the local `manifest.json`.
2. Confirm that `https://example.com/static_sitemap/sitemap-index.xml` is publicly available.
3. Set the project's Yandex Webmaster host in the bot.
4. Open `Индексирование` -> `Статические карты` -> `Отправить карты в Яндекс Вебмастер`.

The application sends the generated index and every saved leaf sitemap URL to the configured Yandex Webmaster host. It does not upload files to the server and does not alter sitemap contents. Subdomain-specific publishing is intentionally out of scope for now.
