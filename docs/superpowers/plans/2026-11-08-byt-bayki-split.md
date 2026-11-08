# «Быт» / «Байки и курьезы» Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разделить главу «Быт, байки, курьезы» на две главы — «Быт» и «Байки и курьезы» — сохранив все истории и голоса.

**Architecture:** Существующий файл `12-----_------_-------.md` (ID 72) становится главой «Быт». Новый файл `12a----_-_-------.md` (ID 410) получает главу «Байки и курьезы». Разделы переносятся по смыслу, «Комнаты и декорации» вливаются в «Устройство интерната», добавляются три коротких перехода. Тексты историй не переписываются.

**Tech Stack:** Markdown-файлы Manuskript, Python 3 для переноса блоков и пересчёта `charCount`, mdBook 0.5.4, pytest.

**Spec:** `docs/superpowers/specs/2026-11-08-byt-bayki-split-design.md`

## Review Focus

- Текст истории потерян или задвоен при переносе блоков между файлами.
- Историческая запись в «Что нового» ведёт на старую страницу «Быт, байки, курьезы».
- `charCount` главы или раздела расходится с фактическим текстом.
- Новая глава стоит не после «Быта», а в другом месте оглавления.
- ID новой главы конфликтует с существующим ID Manuskript.

## Global Constraints

- Manuskript должен быть закрыт перед любой правкой.
- Не менять тексты историй, цитаты, голоса рассказчиков и ссылки на фотографии.
- Не удалять ни одной истории.
- «Быт» сохраняет ID 72 и файл `12-----_------_-------.md`.
- «Байки и курьезы» получает ID 410 и файл `12a----_-_-------.md`.
- Порядок в разделе: «Быт» → «Байки и курьезы» → «Окрестности интерната».
- `charCount` глав и `folder.txt` должны сходиться с фактическим текстом.
- Сайт пересобирается; тесты должны проходить.
- Коммит не делать.

---

### Task 1: Резервные копии и исходная инвентаризация

**Files:**
- Read: `internat/outline/3---------_----/12-----_------_-------.md`
- Read: `internat/outline/3---------_----/folder.txt`

**Interfaces:**
- Produces: резервные копии в `/tmp/opencode/internat-backup/`; список 23 разделов и исходный `charCount` 28 366.

- [ ] **Step 1: Проверить, что Manuskript закрыт**

Run: `pgrep -x manuskript || echo 'manuskript closed'`
Expected: `manuskript closed`

- [ ] **Step 2: Сделать резервные копии**

Run:
```bash
mkdir -p /tmp/opencode/internat-backup
cp 'internat/outline/3---------_----/12-----_------_-------.md' \
   /tmp/opencode/internat-backup/byt-before-split.md.bak
cp 'internat/outline/3---------_----/folder.txt' \
   /tmp/opencode/internat-backup/school-folder-before-split.txt.bak
```

- [ ] **Step 3: Зафиксировать исходную структуру**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re
p = Path('3---------_----/12-----_------_-------.md')
for line in p.read_text().splitlines():
    m = re.match(r'\*\*\*(.+?)\*\*\*', line.strip())
    if m:
        print(m.group(1))
PY
```
Expected: 23 строки — от «Байка о подвиге Славы Каргина» до «Фотоаппарат».

---

### Task 2: Создать «Байки и курьезы» и вынести туда истории

**Files:**
- Create: `internat/outline/3---------_----/12a----_-_-------.md`
- Modify: `internat/outline/3---------_----/12-----_------_-------.md`

**Interfaces:**
- Consumes: разделы исходной главы.
- Produces: два файла с полным набором разделов; новый файл с заголовком `title: Байки и курьезы`, `ID: 410`.

- [ ] **Step 1: Создать новый файл с метаданными и вступлением**

```markdown
title:          Байки и курьезы
ID:             410
type:           md
compile:        2
charCount:      0


А истории в этом доме любили рассказывать. Одни были правдой, другие — почти правдой, третьи — чистой легендой; со временем граница стиралась.
```

- [ ] **Step 2: Перенести в новый файл разделы в этом порядке**

1. Байка о подвиге Славы Каргина
2. Уточки на Сетуни
3. Топологически невозможно
4. Химия
5. Стенгазета
6. Чуть не сжёг интернат
7. «Клешни звёзд» в консерватории и прятки от «Чучела»
8. Гостья из будущего
9. Клуб Федотова
10. Логистика, автобусы и хитроумный побег домой
11. «И вы, в таком виде?..»
12. Отлучки
13. Фотоаппарат

Переносить блоки вместе с их подзаголовками `***…***` и текстом целиком.

- [ ] **Step 3: Удалить перенесённые блоки из старого файла**

В старом файле остаются только разделы:

1. Устройство интерната
2. Комнаты и декорации
3. 45-я комната
4. Близнецы
5. Столовая
6. Вечерние чаепития
7. Физика, экстрим и спаньё в ушанках
8. Ножички
9. Тапки
10. Крыша

- [ ] **Step 4: Проверить, что ни один раздел не потерян и не задвоен**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re, collections

def heads(path):
    out = []
    for line in Path(path).read_text().splitlines():
        m = re.match(r'\*\*\*(.+?)\*\*\*', line.strip())
        if m:
            out.append(m.group(1))
    return out

old = heads('/tmp/opencode/internat-backup/byt-before-split.md.bak')
new = heads('3---------_----/12-----_------_-------.md') + \
      heads('3---------_----/12a----_-_-------.md')
expected = [h for h in old if h != 'Комнаты и декорации']
counts = collections.Counter(new)
print('разделов:', len(new))
print('повторы:', [h for h, n in counts.items() if n > 1])
print('потеряно:', [h for h in expected if h not in counts])
print('лишнее:', [h for h in new if h not in expected])
PY
```
Expected: `разделов: 22`, `повторы: []`, `потеряно: []`, `лишнее: []`.

---

### Task 3: Собрать «Быт»

**Files:**
- Modify: `internat/outline/3---------_----/12-----_------_-------.md`

**Interfaces:**
- Consumes: оставшиеся разделы из Task 2.
- Produces: глава «Быт» с порядком: Устройство → 45-я → Близнецы → Столовая → Чаепития → Физика → Ножички → Тапки → Крыша.

- [ ] **Step 1: Заменить старый заголовок и вступление**

`title:` должно стать `Быт`. Вступление:

> Интернатская жизнь состояла не только из формул и коллоквиумов. Она состояла из комнат, столовой, чаепитий, окон и крыши. Сначала — как был устроен этот дом.

- [ ] **Step 2: Влить «Комнаты и декорации» в «Устройство интерната»**

Оставить подзаголовок `***Устройство интерната***`. После абзаца о девочках добавить текст про ватманы, картину «Над вечным покоем» и надпись про переменные. Отдельный подзаголовок `***Комнаты и декорации***` убрать.

- [ ] **Step 3: Переставить «45-ю комнату» и «Близнецов» до комнатных забав**

Порядок после «Устройства интерната»:

1. `***45-я комната***`
2. `***Близнецы***`
3. `***Столовая***`
4. `***Вечерние чаепития***`
5. `***Физика, экстрим и спаньё в ушанках***`
6. `***Ножички***`
7. `***Тапки***`
8. `***Крыша***`

- [ ] **Step 4: Проверить порядок разделов**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re
p = Path('3---------_----/12-----_------_-------.md')
for line in p.read_text().splitlines():
    m = re.match(r'\*\*\*(.+?)\*\*\*', line.strip())
    if m:
        print(m.group(1))
PY
```
Expected ровно:
`Устройство интерната`, `45-я комната`, `Близнецы`, `Столовая`, `Вечерние чаепития`, `Физика, экстрим и спаньё в ушанках`, `Ножички`, `Тапки`, `Крыша`.

---

### Task 4: Собрать «Байки и курьезы»

**Files:**
- Modify: `internat/outline/3---------_----/12a----_-_-------.md`

**Interfaces:**
- Consumes: перенесённые разделы из Task 2.
- Produces: глава с 13 разделами и переходами.

- [ ] **Step 1: Поставить переход после «Уточек»**

Перед `***Топологически невозможно***` добавить отдельным абзацем:

> Но не все истории были такими героическими.

- [ ] **Step 2: Поставить переход перед «Химией»**

Перед `***Химия***` добавить отдельным абзацем:

> Школа подкидывала свои сюжеты.

- [ ] **Step 3: Поправить первое предложение «Химии»**

Заменить начало раздела на:

> Химию у нас преподавала Валентина Викторовна Присяжнюк, которую за глаза звали Химозой.

Остальной текст раздела не трогать.

- [ ] **Step 4: Проверить порядок разделов**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re
p = Path('3---------_----/12a----_-_-------.md')
for line in p.read_text().splitlines():
    m = re.match(r'\*\*\*(.+?)\*\*\*', line.strip())
    if m:
        print(m.group(1))
PY
```
Expected: 13 строк в порядке из Task 2.

---

### Task 5: Метаданные, сборка и проверки

**Files:**
- Modify: `internat/outline/3---------_----/12-----_------_-------.md`
- Modify: `internat/outline/3---------_----/12a----_-_-------.md`
- Modify: `internat/outline/3---------_----/folder.txt`
- Modify: `site/updates.json`

**Interfaces:**
- Consumes: две готовые главы.
- Produces: корректные `charCount`, запись в «Что нового», собранный сайт.

- [ ] **Step 1: Пересчитать `charCount` всех глав и `folder.txt`**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re

def size(p):
    return sum(len(x) for x in p.read_text().splitlines()[5:])

for p in sorted(Path('.').rglob('*.md')):
    if p.name == 'folder.txt':
        continue
    t = p.read_text()
    p.write_text(re.sub(r'charCount:\s*\d+', f'charCount:      {size(p)}', t, count=1))

for f in sorted(Path('.').glob('*/folder.txt')):
    d = f.parent
    total = sum(size(p) for p in d.glob('*.md') if p.name != 'folder.txt')
    t = f.read_text()
    f.write_text(re.sub(r'charCount:\s*\d+', f'charCount:      {total}', t, count=1))
PY
```

- [ ] **Step 2: Проверить, что счётчики сходятся**

Run:
```bash
cd internat/outline
python3 - <<'PY'
from pathlib import Path
import re
bad = []
for p in sorted(Path('.').rglob('*.md')):
    if p.name == 'folder.txt':
        continue
    c = sum(len(x) for x in p.read_text().splitlines()[5:])
    m = int(re.search(r'charCount:\s*(\d+)', p.read_text()).group(1))
    if c != m:
        bad.append((str(p), m, c))
print('bad:', bad or 'none')
PY
```
Expected: `bad: none`

- [ ] **Step 3: Добавить запись в «Что нового»**

В начало массива `site/updates.json`:

```json
{
  "date": "2026-11-08",
  "chapter": "Байки и курьезы",
  "note": "новая глава"
}
```

- [ ] **Step 4: Собрать сайт**

Run:
```bash
python3 tools/build_site.py
mdbook build site
```
Expected: сборка без ошибок.

- [ ] **Step 5: Проверить порядок глав**

Run:
```bash
grep -n -A3 -B3 'Байки и курьезы' site/src/SUMMARY.md
```
Expected: «Быт» выше, «Байки и курьезы» ниже, «Окрестности интерната» ещё ниже.

- [ ] **Step 6: Прогнать тесты**

Run:
```bash
uv run --with pytest python -m pytest -q
```
Expected: все тесты проходят.

- [ ] **Step 7: Проверить, что старый заголовок не остался**

Run:
```bash
grep -rn 'Быт, байки, курьезы' internat/outline site/src || echo 'old title gone'
```
Expected: `old title gone`.
