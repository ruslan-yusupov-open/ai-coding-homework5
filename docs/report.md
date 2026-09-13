# Отчёт по ДЗ №5

Реализован сервер локальной документации: Python, официальный MCP SDK 1.30.0,
stdio, три инструмента и структурированные ответы. Код и автоматическая проверка
готовы; **5 реальных MCP-вызовов в сессии OpenCode внутри VS Code подтверждены**
[экспортом чата и серверным логом](../validation/ide/README.md).
Первый запрос отправлен вручную, запросы 2–5 — через локальный API той же
TUI-сессии; инструменты выбирал и вызывал агент с моделью Qwen.
Отдельно сохранена [демонстрация OpenCode Desktop](../validation/opencode-desktop/README.md).

OpenCode запускает локальный процесс по `opencode.json`, выполняет инициализацию
MCP и получает описания и JSON Schema инструментов через `tools/list`.
По запросу пользователя агент выбирает tool, клиент отправляет `tools/call`
через stdio, а сервер возвращает структурированный результат для ответа агента.
Tool в этом проекте — именованная операция чтения или поиска по Markdown-файлам
фиксированного каталога `knowledge`: `list_docs`, `search_docs`, `get_doc`.

## Подтверждения ссылками на код

Ссылки используют ветку `main` репозитория. В экспортируемых доказательствах
удалены инфраструктурные метаданные; запросы, ответы и call_id сохранены.

| Требование | Файл и диапазон строк |
| --- | --- |
| Создание сервера | [server.py:L20–L23](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L20-L23) |
| Реестр и описания tools | [server.py:L64–L86](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L64-L86) |
| Публикация схем tools | [server.py:L130–L143](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L130-L143) |
| Запуск stdio | [server.py:L210–L217](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L210-L217) |
| list_docs | [documents.py:L90–L96](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/documents.py#L90-L96) |
| search_docs | [documents.py:L98–L107](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/documents.py#L98-L107) |
| get_doc | [documents.py:L109–L115](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/documents.py#L109-L115) |
| Схемы параметров | [server.py:L26–L49](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L26-L49) |
| Контракт оболочки результата | [server.py:L52–L61](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L52-L61) |
| Описание полей результата | [README.md:L113–L130](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/README.md#L113-L130), [таблица tools](../README.md#инструменты) |
| Проверка границы чтения | [documents.py:L18–L63](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/documents.py#L18-L63) |
| Настройка логов, stderr и файл | [server.py:L89–L127](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L89-L127) |
| Логирование каждого из трёх tools | [server.py:L186–L207](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L186-L207) |
| Конфигурация OpenCode | [opencode.json:L1–L15](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/opencode.json#L1-L15) |
| Альтернативная конфигурация Copilot | [.vscode/mcp.json:L1–L10](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/.vscode/mcp.json#L1-L10) |

Логирование общее: любой tool проходит через `call_tool`, который валидирует
параметры, выполняет функцию и пишет запись со статусом и тем же `call_id`, что в ответе.

| Tool | Где логируется | Пример фактического лога |
| --- | --- | --- |
| list_docs | [server.py:L186–L207](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L186-L207) | [server.jsonl:L1](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/validation/ide/server.jsonl#L1) |
| search_docs | [server.py:L186–L207](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L186-L207) | [server.jsonl:L2](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/validation/ide/server.jsonl#L2) |
| get_doc | [server.py:L186–L207](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/server.py#L186-L207) | [server.jsonl:L3](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/validation/ide/server.jsonl#L3) |

## Реальные примеры логов (автоматический клиент)

Ниже сокращённые фрагменты фактических строк из
[validation/automated/server.jsonl](../validation/automated/server.jsonl):

```json
{"tool":"list_docs","params":{},"status":"success"}
{"tool":"search_docs","params":{"query":"stdio"},"status":"success"}
{"tool":"get_doc","params":{"path":"security.md"},"status":"success"}
{"tool":"get_doc","params":{"path":"../README.md"},"status":"error","error_code":"ACCESS_DENIED"}
```

Полный файл содержит timestamps и call_id. Ответы и схемы инструментов сохранены
в [results.json](../validation/automated/results.json).

## Проверки

- Ruff: все проверки пройдены.
- Pytest: **17 passed, 1 skipped** на Windows / Python 3.14.2 (включая HTTP).
- Пропущен symlink-тест: ОС не разрешает создавать символические ссылки.
  Отдельный тест запрета Windows junction прошёл.
- Настоящий MCP stdio: **8 вызовов прошли**, в том числе отказ выхода из knowledge,
  отсутствующий документ, пустой запрос, лишний параметр и пустая выдача поиска.

## Демонстрация выбора tool агентом

Проверочный запрос: «Через MCP-сервер homework5-docs вызови get_doc
с path=\"security.md\". Перечисли ограничения чтения».
Ожидаемый tool — `get_doc`, параметры — `{"path":"security.md"}`.
Фактическое подтверждение: агент в сессии VS Code вызвал `get_doc` в 20:01:08 UTC,
`call_id=61a319d8-ee5b-4fbc-b815-7b2d49f793cf`, статус `success`.
Серверная запись — [server.jsonl:L3](https://github.com/ruslan-yusupov-open/ai-coding-homework5/blob/main/validation/ide/server.jsonl#L3),
ответ агента — [chat.md, запрос 3](../validation/ide/chat.md#запрос-3).
Полная таблица пяти вызовов и методика — [доказательства IDE](../validation/ide/README.md).

В объяснении транспорта в ответе №2 модель перепутала направления потоков.
Клиент пишет запросы в stdin сервера и читает ответы из stdout сервера;
каналы открыты во время работы процесса, логи направляются в stderr.
Исходный ответ сохранён без исправлений, сам MCP-вызов выполнен правильно.

## Дополнение: живой HTTP-сервис

Развёрнут `https://mcp1.leadcm.com/mcp`, защищённый отдельным API-ключом с истечением
срока и лимитами нагрузки. Сервис работает в изолированной файловой системе
без доступа к сети, с исходными тремя инструментами только для чтения.
[Описание и конфигурация](live.md), [публичные проверки](../validation/live/results.json),
[проверка официальным SDK и 429](../validation/live/sdk-results.jsonl).
После добавления HTTP: **17 passed, 1 skipped**, Ruff пройден; остаются два
предупреждения об устаревающих API в тестовом клиенте зависимостей.

## Сверка с заданием

[Полная матрица соответствия и результаты перепроверки](compliance.md).
В чистой копии с новым venv выполнены 17 тестов и 8 настоящих stdio-вызовов.
Исходники, переносимые конфигурации и очищенные доказательства включены
в публикационный комплект. Приватные административные файлы и секреты исключены.
