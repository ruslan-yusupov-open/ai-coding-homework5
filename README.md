# Домашнее задание №5 — Local Docs MCP

MCP-сервер для **OpenCode** (также есть конфигурация VS Code Copilot): три инструмента для локальной
документации, структурированные ответы, безопасное чтение и JSON-логи.
Локальному stdio-серверу API-ключ не нужен; живой HTTPS endpoint защищён отдельным ключом.

## Принципы MCP

OpenCode запускает `server.py` по [opencode.json](opencode.json), выполняет
инициализацию MCP и получает инструменты через `tools/list`. Агент выбирает
инструмент по описанию и схеме параметров; клиент отправляет `tools/call`. Сервер
возвращает `structuredContent`, а агент использует результат в своём ответе.
Транспорт stdio передаёт JSON-RPC через stdin/stdout процесса, логи идут в stderr.

Tool здесь — именованная операция над публичными Markdown-файлами `knowledge/`.
Сервер публикует JSON Schema параметров и результата, Python-функции реализуют
чтение и поиск. Это локальный вариант подхода «дать агенту нужную справку»;
устанавливать Context7 или обращаться к внешнему сервису не требуется.

## Инструменты

| Tool | Параметры | Поля `data` в результате |
| --- | --- | --- |
| `list_docs` | `{}` | `documents: [{path, title, lines}], count` |
| `search_docs` | `query: string`, `limit: integer = 10` | `matches: [{path, line, snippet}], count, truncated` |
| `get_doc` | `path: string` | `path, content, lines` |

Документы: [обзор](knowledge/overview.md), [безопасность](knowledge/security.md),
[отладка](knowledge/troubleshooting.md). Поиск буквальный, без учёта регистра.

## Подготовка и запуск

Нужны Python 3.11+ и [uv](https://docs.astral.sh/uv/getting-started/installation/).
Для демонстрации — OpenCode с моделью, поддерживающей tools; для интеграции с IDE — VS Code.
Зависимости закреплены в `pyproject.toml` и полном `uv.lock`; MCP SDK — **1.30.0**.

```powershell
git clone https://github.com/ruslan-yusupov-open/ai-coding-homework5.git
cd ai-coding-homework5
uv sync --frozen
uv run --frozen python server.py
```

При ручном запуске сервер ожидает MCP-сообщения на stdin: отсутствие приглашения
нормально. Завершение — Ctrl+C. Для IDE ручной запуск не нужен.
При необходимости выбрать локальный Python:
`uv sync --frozen --python 3.14`.

[.env.example](.env.example) описывает необязательный `MCP_LOG_FILE`.
`.env` автоматически не загружается: переменную задают в окружении или поле `env`
конфигурации MCP. По умолчанию лог — `logs/server.jsonl`, для Copilot настроен
`logs/copilot.jsonl`, для OpenCode — `logs/opencode.jsonl`. Секретов stdio-серверу не нужно;
авторизация провайдера модели настраивается отдельно в агенте.

## Подключение OpenCode

В OpenCode Desktop откройте корень этого репозитория как проект: здесь лежит
`opencode.json`. После установки Python-зависимостей (`uv sync --frozen`) клиент
может запустить сервер по этой конфигурации. Если проект уже открыт, перезапустите
сессию/приложение для загрузки нового MCP-сервера. Рабочий лог — `logs/opencode.jsonl`.
Если приложение не находит `uv`, укажите полный путь к `uv.exe` первым элементом `command`.

Для выполнения именно требования «агент в IDE» используйте OpenCode внутри VS Code:

1. Откройте корень репозитория в VS Code; установите OpenCode CLI и расширение `sst-dev.opencode`.
2. Во встроенном терминале выполните `uv sync --frozen`.
3. Запустите **Open opencode** из палитры команд; CLI загрузит `opencode.json` из корня проекта.
4. Выберите подключённую модель с tool calling. Команда `opencode mcp list` в другом
   терминале проекта позволяет проверить состояние MCP-сервера.
5. Отправьте пять запросов из [сценария](docs/demo.md), сохраните раскрытые вызовы
   и строки `logs/opencode.jsonl` в `validation/ide/`.

OpenCode использует собственный `opencode.json`, не `.vscode/mcp.json`.
Отдельная демонстрация Desktop подтверждает работу агента с MCP, но не заменяет
требование интеграции с IDE. Источники: [MCP](https://opencode.ai/docs/mcp-servers/),
[интеграция с IDE](https://opencode.ai/docs/ide/).

Конфигурация `opencode.json` содержит только локальный MCP. Через `/connect`
подключите своего провайдера и выберите модель с поддержкой tools. Python и `uv`
должны быть доступны в PATH. Дополнительный пример —
[examples/opencode.local.json](examples/opencode.local.json).

## Альтернатива: Copilot в VS Code — 5 шагов

1. Откройте **корень этого репозитория** в VS Code (`code .`), а не родительскую папку.
2. Выполните `uv sync --frozen` в терминале проекта.
3. Откройте `.vscode/mcp.json`, нажмите **Start** над `homework5-docs` либо используйте
   **MCP: List Servers → homework5-docs → Start**. При запросе IDE подтвердите доверие.
4. В Copilot Chat выберите **Agent**, в **Configure Tools** включите три инструмента
   сервера `homework5-docs`.
5. Отправьте по очереди пять запросов из [сценария](docs/demo.md), раскройте карточки
   вызовов и сохраните подтверждения в `validation/ide/`.

Настройка сверена с [официальной документацией VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers).
Если `uv` не находится, перезапустите IDE после настройки PATH или укажите полный
путь к `uv.exe` в `command`. При устаревшем списке tools перезапустите сервер.

## Безопасность

- Читаются только `.md` внутри фиксированной `knowledge` рядом с `server.py`.
- Запрещены абсолютные пути, `..`, скрытые компоненты, Windows ADS, symlink и junction.
- Нет исполнения команд, сетевых запросов, изменения файлов через tools.
- Документ ограничен 128 КиБ; дерево — 1000 элементами и 200 документами.
- Поиск: 1–200 символов, `limit` от 1 до 20, фрагменты до 300 символов.
- Параметры строго проверяются, лишние поля отклоняются.
- В логах маскируются распространённые форматы токенов и неизвестные поля.
  Это не универсальный детектор секретов: не передавайте секреты в запросах
  и не помещайте их в `knowledge`. `.env`, окружение и рабочие логи исключены из Git.
- Граница рассчитана на доверенную локальную папку. Это не защита от локального
  злоумышленника, который может менять каталог между проверкой пути и чтением
  или создавать hardlink. Параллельная подмена дерева не поддерживается.

## Контракт результатов

И успех, и ошибка возвращаются в `structuredContent`. Для совместимости тот же
объект дублируется JSON-текстом в `content[0].text`.

```json
{"status":"success","call_id":"UUID","data":{"documents":[],"count":0},"error":null}
```

```json
{"status":"error","call_id":"UUID","data":null,"error":{"code":"ACCESS_DENIED","message":"Use a relative Markdown path inside knowledge."}}
```

У ошибки дополнительно `isError: true`. Коды: `INVALID_PARAMS`, `ACCESS_DENIED`,
`NOT_FOUND`, `LIMIT_EXCEEDED`, `INVALID_ENCODING`, `READ_ERROR`, `UNKNOWN_TOOL`,
`INTERNAL_ERROR`. Нулевой результат поиска — успех с пустым `matches`.
`line` начинается с 1; `truncated` означает наличие дополнительных совпадений.
Схема общей оболочки — `outputSchema`; поля `data` описаны в таблице инструментов.

## Проверки

```powershell
uv run --frozen pytest -q --basetemp .pytest-tmp
uv run --frozen ruff check server.py documents.py http_server.py validate.py tests deploy
uv run --frozen python validate.py
```

`validate.py` запускает отдельный процесс, выполняет initialization, `tools/list`
и 8 настоящих `tools/call`, проверяет схемы ответов, ошибки и серверные логи.
Результаты — [results.json](validation/automated/results.json),
логи — [server.jsonl](validation/automated/server.jsonl).
Эта проверка протокола сама по себе не доказывает вызовы из IDE.
Состояние демонстрации: [validation/ide/README.md](validation/ide/README.md).

Тесты проверяют кириллицу, пустую выдачу, лимиты, обход каталога, ADS, параметры,
кодировку и junction. Symlink-тест пропускается, если Windows не разрешает
создать тестовую ссылку; junction проверяется отдельно.

## Логи и подтверждения кодом

Одна JSON-строка на вызов: `timestamp`, `call_id`, `tool`, `params`, `status`,
`error_code`. Записывается одновременно в stderr и `logs/*.jsonl`.
Примеры фактического вывода: [server.jsonl](validation/automated/server.jsonl).
Ссылки на файлы и диапазоны строк собраны в [отчёте](docs/report.md).

Основа: [официальный MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).

## Выполненная демонстрация в VS Code

Все пять запросов выполнены в одной сессии OpenCode внутри VS Code:
список документов, поиск, чтение, пустой поиск и ожидаемый `ACCESS_DENIED`.
Первый запрос введён вручную; остальные отправлены через локальный API той же
сессии, инструменты вызывал агент. Экспорт вызовов с удалёнными служебными метаданными
и сопоставленные по `call_id` логи — в
[validation/ide/README.md](validation/ide/README.md).

Установлены OpenCode CLI 1.18.30 и расширение `sst-dev.opencode` 0.0.13.
Запуск расширения: `Ctrl+Shift+P` → **Open opencode**.
Если PowerShell сообщает, что выполнение `opencode.ps1` запрещено,
используйте `opencode.cmd --port 40302` (порт — из команды расширения).
Изменять политику выполнения PowerShell не требуется.

## Живой MCP по HTTPS

Развёрнут **https://mcp1.leadcm.com/mcp**: те же три инструмента документации,
Streamable HTTP, отдельный API-ключ на 30 дней, ограничения запросов и процесс
в песочнице без сети. [Подключение, границы доступа и эксплуатация](docs/live.md).
Публичные вызовы, отказы авторизации и лимит частоты проверены:
[результаты](validation/live/results.json), [официальный SDK](validation/live/sdk-results.jsonl).
