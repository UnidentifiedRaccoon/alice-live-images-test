# S3-пакет видео для PROMOPAGES-10060

Этот каталог фиксирует раскладку всех 21 публикации из тикета по кабинетам и готовит воспроизводимую загрузку 508 MP4 в `promopages-front-bundles`. Для статьи 02 исправлен исходный URL и добавлены 11 изображений с 33 видео из отдельного v2 sidecar; статьи 19–21 подключены из финального кампанийного sidecar за 2026-08-07. Два ранее зафиксированных результата Veo имеют финальный статус `provider-filtered`; они сохраняются в отчётах, но файлов для них нет.

## Раскладка

`build` создаёт локальный staging-каталог:

```text
PROMOPAGES-10060/s3-export/output/
├── upload/
│   └── <cabinet-slug>__<cabinet-id>/
│       └── <publication-id>/
│           ├── wan_2_2/
│           ├── wan_2_7/
│           └── veo_3_1/
│               └── image_<image-id>--sha256-<12-hex>.mp4
├── manifest.json
├── links.csv
├── missing.csv
├── SHA256SUMS
└── upload-command.txt
```

В S3 уходит только содержимое `output/upload/`. Полный ключ объекта:

```text
front-images/exp_video/<cabinet-slug>__<cabinet-id>/<publication-id>/<experiment>/image_<image-id>--sha256-<12-hex>.mp4
```

Эксперименты маппятся строго:

| model_id | Папка |
| --- | --- |
| `alibaba/wan-2.2` | `wan_2_2` |
| `alibaba/wan-2.7` | `wan_2_7` |
| `google/veo-3.1-lite` | `veo_3_1` |

Имя кабинета в пути — закреплённый ASCII-slug из `articles.json`, а не динамическая транслитерация. Суффикс SHA-256 делает имена контентно-адресуемыми: повторная генерация не перезапишет старое видео и не попадёт под устаревший CDN-кеш.

Конечная ссылка вычисляется без ручной сборки:

```text
https://yastatic.net/s3/promopages-front-bundles/front-images/exp_video/<cabinet>/<publication>/<experiment>/<file>
```

Все плановые ссылки находятся в `output/links.csv`; они детерминированы до загрузки. Только после того, как `upload --execute` подтвердит в S3 и через yastatic каждый готовый объект, загрузчик атомарно создаёт `output/delivery-manifest.json` для публичной демки. В нём нет provider ID и внутренних S3-ответов: только логический ключ результата, исходный repository path, S3/yastatic-адрес, размер и SHA-256. При частичной или неуспешной загрузке delivery-манифест не публикуется.

## Сборка и проверка

Из корня репозитория:

```bash
python3 scripts/promopages_10060_s3_export.py build
python3 scripts/promopages_10060_s3_export.py verify
```

По умолчанию результат создаётся в `PROMOPAGES-10060/s3-export/output`. Режим `--materialize auto` сначала использует hardlink, а при невозможности делает копию. Это экономит около 3.81 GiB локального места и при этом оставляет в staging обычные файлы, не симлинки. Для самостоятельного переносимого каталога используйте:

```bash
python3 scripts/promopages_10060_s3_export.py build --materialize copy
```

Другой каталог задаётся одинаково для всех команд:

```bash
python3 scripts/promopages_10060_s3_export.py build --output /absolute/path/to/output
python3 scripts/promopages_10060_s3_export.py verify --output /absolute/path/to/output
```

Источниками служат только финальные `video_path` из четырёх агрегатных манифестов:

- `clipmaker-lite-test/promopages-10060-manifest.json`;
- `clipmaker-lite-test/promopages-10060-campaigns-20260805-v1-manifest.json`;
- `clipmaker-lite-test/promopages-10060-article-02-20260806-v2-manifest.json`;
- `clipmaker-lite-test/promopages-10060-campaigns-20260807-v1-manifest.json`.

Глобить каталоги генерации нельзя: часть выбранных результатов находится в retry/supersede namespaces. Сборка проверяет соответствие `articles.json`, финальных статусов, размера и SHA-256 каждого исходного MP4.

Ожидаемый итог:

| Сущность | Количество |
| --- | ---: |
| Кабинеты | 11 |
| Доступные статьи | 21 |
| Недоступные статьи | 0 |
| Изображения | 170 |
| Логические результаты | 510 |
| MP4 для загрузки | 508 |
| Provider-filtered без MP4 | 2 |

Два отсутствующих MP4 — Veo для изображения 06 статьи 07 и изображения 05 статьи 08. Они перечисляются в `missing.csv`; подменять их видео другой модели нельзя.

## Внутренний профиль `yc`

Бакет размещён во внутреннем Object Storage. Обычный публичный профиль `yc` смотрит в другой контур и для этого имени возвращает `NoSuchBucket`. Нужен отдельный корпоративный профиль с внутренним API и MDS endpoint.

Минимальная конфигурация профиля (интерактивный `init` не меняет обычный
`default`-профиль):

```bash
yc config profile create promopages-internal
yc init --profile promopages-internal --endpoint gw.db.yandex-team.ru:443
yc config set storage-endpoint s3.mds.yandex.net --profile promopages-internal
```

В `yc init` выберите cloud `zennativead` и folder с ID
`foo470qcnjoilujnp1te` из ссылки на бакет.

Авторизацию добавьте в этот профиль принятым в команде способом. Токены и ключи нельзя передавать аргументами экспортера, сохранять в репозитории или вставлять в `upload-command.txt`.

Перед загрузкой проверьте, что профиль видит именно нужный бакет и префикс:

```bash
yc storage s3api list-objects-v2 --profile promopages-internal \
  --bucket promopages-front-bundles \
  --prefix front-images/exp_video/ \
  --max-keys 1
```

Если проверка возвращает `NoSuchBucket`, не запускайте `--execute`: профиль или endpoint всё ещё относятся к другому контуру.

## Dry-run и загрузка

Загрузка по умолчанию работает без внешних изменений:

```bash
python3 scripts/promopages_10060_s3_export.py upload \
  --yc-profile promopages-internal
```

После проверки плана загрузки запустите явный execute:

```bash
python3 scripts/promopages_10060_s3_export.py upload \
  --yc-profile promopages-internal \
  --execute
```

Загрузчик не удаляет объекты и не выставляет `public-read`: доступ через yastatic задаётся политикой бакета/CDN. MP4 загружаются с `Content-Type: video/mp4` и `Cache-Control: public,max-age=31536000,immutable`. Повторный запуск должен быть идемпотентным: совпадающий объект пропускается, а коллизия с другим содержимым считается ошибкой.

Во время execute прогресс атомарно сохраняется в `output/upload-report.json`,
поэтому уже записанный объект не потеряется из отчёта, даже если последующая
проверка S3 или yastatic завершится ошибкой. После проверки всех объектов
создаётся `output/verified-links.csv` — это конечный список доступных ссылок.

Для загрузки требуется явное внешнее действие и корректно авторизованный внутренний профиль. Сначала всегда запускайте dry-run, затем `verify`, и только после этого — `--execute`.
