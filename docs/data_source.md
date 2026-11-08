# FlightInsight — происхождение данных

## Источник

- Организация: **Bureau of Transportation Statistics (BTS)**, Department of Transportation, США.
- Набор данных: **Reporting Carrier On-Time Performance (1987–present)**.
- Каталог: https://www.transtats.bts.gov/
- Период для MVP: **январь, февраль и март 2025 года**.

## Официальные файлы

| Месяц | Ссылка на официальный архив | Локальное имя |
| --- | --- | --- |
| Январь | [2025_1.zip](https://www.transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2025_1.zip) | `data/raw/bts_2025_01.zip` |
| Февраль | [2025_2.zip](https://www.transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2025_2.zip) | `data/raw/bts_2025_02.zip` |
| Март | [2025_3.zip](https://www.transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2025_3.zip) | `data/raw/bts_2025_03.zip` |

В каждом скачанном ZIP обнаружен CSV и `readme.html`. Наличие файлов, чтение заголовков и проверка данных подтверждены выводом локальных команд в этапе 2. Размеры февраля и марта в выводе скачивания: **25 302 583** и **30 544 825** байт соответственно. Размер январского архива в предоставленном логе не указан.

## Способ получения и обновления

```bat
python scripts\download_bts.py
python scripts\inspect_bts.py
```

`download_bts.py` пропускает существующий корректный ZIP-файл, а отсутствующий скачивает с сайта BTS. `inspect_bts.py` читает CSV без распаковки на диск. Для строгой повторной проверки происхождения и неизменности будущих наборов данных желательно фиксировать SHA-256 каждого архива; на текущем этапе хэши не получены, поэтому не указаны.

## Политика хранения

- **В Git:** код скачивания и проверки, словарь полей, правила вычисления метрик, отчёт о качестве и эта запись об источнике.
- **Только локально:** большие исходные ZIP/CSV в `data/raw/`; каталог исключён в `.gitignore`.
- **Не хранить в Git:** локальные секреты `.env`, виртуальные окружения и временные файлы.

При будущей обработке следует документировать версию ETL, дату импорта и число обработанных / загруженных / отклонённых записей в таблице `import_batches`.
