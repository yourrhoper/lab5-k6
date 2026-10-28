# ЛР5. Нагрузочное тестирование (k6)

Объект: учебный стенд API формы подачи достижения по культурно-творческой деятельности
(упрощённая копия бэкенда формы из ЛР1–ЛР4). Нагрузка подаётся только на локальный стенд.

## Структура

```
server/server.js            учебный стенд (Node.js, без зависимостей), порт 3000
k6/achievements-test.js     сценарии browse + submit, профили smoke/load/stress/spike,
                            checks, thresholds, custom metrics
run-all.sh                  последовательный прогон load → stress → spike
analysis/analyze.py         агрегирование CSV k6, графики и таблицы
results/                    сырые результаты (CSV, summary JSON, HTML-дашборды, графики)
.github/workflows/k6.yml    запуск k6 в GitHub Actions (бонус)
```

## Запуск

```bash
node server/server.js &                          # стенд
k6 run -e PROFILE=smoke  k6/achievements-test.js # проверка скрипта (20 с)
k6 run -e PROFILE=load   k6/achievements-test.js # 50 VU, 5 мин удержания
k6 run -e PROFILE=stress k6/achievements-test.js # ступени ×1…×5
k6 run -e PROFILE=spike  k6/achievements-test.js # 10 → 250 VU за 10 с
./run-all.sh                                      # всё сразу с выгрузкой в results/
python3 analysis/analyze.py results               # графики
```

Адрес стенда можно переопределить: `-e BASE_URL=http://host:port`.
