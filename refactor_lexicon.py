#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
py-locale-extractor — инструмент для автоматической миграции строк с кириллицей
в словарь локализации (LEXICON) в проектах на aiogram.

Автор: Almaz49
Репозиторий: https://github.com/Almaz49/py-locale-extractor
"""

# 💡 Примечание: скрипт предполагает, что в вашем коде есть функция:
#     get_text(key: str, lang: str) -> str
# и что в хэндлерах доступна переменная `lang` (например, через FSM или middleware).


import os
import re
import shutil
from typing import Set, Dict, List, Optional, Tuple

# -----------------------------
# -----------------------------
# ⚙️ НАСТРОЙКИ — измените перед запуском!
# -----------------------------
INPUT_FILE = "handlers/your_handler.py"        # файл для обработки
START_LINE = 1                                 # с какой строки начинать (1 = с начала)
LEXICON_OUTPUT_FILE = "LEXICON_RU.auto.py"     # куда сохранять словарь
# -----------------------------

BASENAME = os.path.basename(INPUT_FILE)
MODULE_PREFIX = BASENAME.replace("_handlers.py", "").replace(".py", "") or "global"
BACKUP_FILE = INPUT_FILE + ".bak"

# Встроенный словарь часто используемых слов для улучшения ключей
RU_TO_EN = {
    "да": "yes",
    "нет": "no",
    "привет": "hello",
    "пока": "goodbye",
    "сообщение": "message",
    "голосование": "voting",
    "название": "title",
    "описание": "description",
    "подтвердить": "confirm",
    "отмена": "cancel",
    # ... добавьте ещё по желанию
}


SEND_FUNCTIONS = {
    "answer", "send_message", "reply", "edit_text",
    "send_photo", "send_document", "send_animation"
}

generated_keys: Set[str] = set()

def translate_word(word: str) -> str:
    word_clean = word.lower().strip(".,;:!?\"'")
    if word_clean in RU_TO_EN:
        return RU_TO_EN[word_clean]
    if word.isdigit():
        return word
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = ""
    for ch in word_clean:
        if ch in translit_map:
            result += translit_map[ch]
        elif ch.isalnum():
            result += ch
    return result or "value"

def smart_slugify(text: str) -> str:
    # Убираем формат-поля вроде {user}, чтобы не мешали
    clean = re.sub(r"\{[^}]+\}", "value", text)
    # Убираем буквальные escape-последовательности из строкового литерала:
    # ищем ОДИН обратный слеш + n/r/t и заменяем на пробел
    clean = re.sub(r"\\[nrtbfv0]", " ", clean)
    # Также убираем одиночные обратные слеши (на всякий случай)
    clean = re.sub(r"\\", " ", clean)
    # Извлекаем слова, включая ё/Ё
    words = re.findall(r"[а-яА-ЯёЁa-zA-Z0-9]+", clean)
    translated = [translate_word(w) for w in words]
    slug = "_".join(translated).strip("_")
    slug = re.sub(r"_+", "_", slug)
    slug = slug[:60] or "text"
    base = slug
    counter = 0
    final = base
    while final in generated_keys:
        counter += 1
        final = f"{base}_{counter}"
    generated_keys.add(final)
    return final

def has_cyrillic(s: str) -> bool:
    return bool(re.search(r'[а-яА-Я]', s))

def load_lexicon() -> Dict:
    if not os.path.exists(LEXICON_OUTPUT_FILE):
        return {}
    with open(LEXICON_OUTPUT_FILE, "r", encoding="utf-8") as f:
        code = f.read()
    try:
        import ast
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and
                len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and
                node.targets[0].id == "LEXICON_RU"):
                d = ast.literal_eval(node.value)
                return d if isinstance(d, dict) else {}
    except:
        pass
    return {}

def save_lexicon(lexicon: Dict):
    os.makedirs(os.path.dirname(LEXICON_OUTPUT_FILE), exist_ok=True)
    with open(LEXICON_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# AUTO-GENERATED — do not edit\n\nLEXICON_RU = {\n")
        for mod in sorted(lexicon):
            f.write(f'    "{mod}": {{\n')
            for k in sorted(lexicon[mod]):
                f.write(f'        "{k}": {repr(lexicon[mod][k])},\n')
            f.write("    },\n")
        f.write("}\n")

def extract_string_literal(lines: List[str], start_line: int, start_col: int) -> Optional[Tuple[str, int, int, bool, str]]:
    line = lines[start_line]
    pos = start_col

    prefix = ""
    while pos < len(line) and line[pos] in "fFrR":
        prefix += line[pos]
        pos += 1
    is_fstring = any(c in "fF" for c in prefix)

    if pos >= len(line):
        return None

    if line[pos:pos+3] in ('"""', "'''"):
        quotes = line[pos:pos+3]
        body_start = pos + 3
        current = line[body_start:]
        if quotes in current:
            end_idx = current.find(quotes)
            body = current[:end_idx]
            end_col = body_start + end_idx + 3
            full_literal = line[start_col:end_col]
            return body, start_line, start_line, is_fstring, full_literal
        else:
            body_lines = [current]
            i = start_line + 1
            while i < len(lines):
                if quotes in lines[i]:
                    end_idx = lines[i].find(quotes)
                    body_lines.append(lines[i][:end_idx])
                    body = "\n".join(body_lines)
                    full_lines = [line[start_col:]] + lines[start_line+1:i+1]
                    last_part = full_lines[-1]
                    end_quote_pos = last_part.find(quotes)
                    if end_quote_pos != -1:
                        full_literal = "".join(full_lines[:-1]) + last_part[:end_quote_pos + 3]
                    else:
                        full_literal = "".join(full_lines)
                    return body, start_line, i, is_fstring, full_literal
                else:
                    body_lines.append(lines[i].rstrip('\n'))
                    i += 1
            return None

    elif line[pos] in ('"', "'"):
        quote = line[pos]
        pos += 1
        body = ""
        escaped = False
        start_pos = start_col
        while pos < len(line):
            ch = line[pos]
            if escaped:
                body += ch
                escaped = False
            elif ch == '\\':
                body += ch
                escaped = True
            elif ch == quote:
                end_col = pos + 1
                full_literal = line[start_pos:end_col]
                return body, start_line, start_line, is_fstring, full_literal
            else:
                body += ch
            pos += 1
        return None

    else:
        return None

def is_simple_placeholder(expr: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", expr.strip()))

def extract_placeholders(body: str) -> Tuple[bool, List[str]]:
    all_expr = re.findall(r"(?<!\{)\{([^}]*)\}(?!\})", body)
    simple_vars = []
    for expr in all_expr:
        if is_simple_placeholder(expr):
            simple_vars.append(expr.strip())
        else:
            return False, []
    return True, simple_vars

def is_in_valid_context(lines: List[str], line_idx: int, col: int) -> bool:
    current_line = lines[line_idx]

    # Правило 1: есть '=' перед литералом на той же строке?
    before_literal = current_line[:col].rstrip()
    if '=' in before_literal:
        last_eq = before_literal.rfind('=')
        if last_eq == 0 or before_literal[last_eq - 1] not in ('!', '<', '>', '='):
            return True

    # Ищем ближайшую '(' на текущей или предыдущей строке
    open_paren_line = -1
    open_paren_col = -1

    for j in range(col - 1, -1, -1):
        if current_line[j] == '(':
            open_paren_line = line_idx
            open_paren_col = j
            break

    if open_paren_line == -1 and line_idx > 0:
        prev_line = lines[line_idx - 1].rstrip()
        if prev_line.endswith('('):
            open_paren_line = line_idx - 1
            open_paren_col = len(prev_line) - 1

    if open_paren_line == -1:
        return False

    line_with_paren = lines[open_paren_line]
    before_paren = line_with_paren[:open_paren_col].rstrip()

    if not before_paren:
        return False

    # Правило 2: перед '(' есть '='?
    if '=' in before_paren:
        last_eq = before_paren.rfind('=')
        if last_eq == 0 or before_paren[last_eq - 1] not in ('!', '<', '>', '='):
            return True

    # Правило 3: перед '(' — функция из списка?
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', before_paren)
    if words:
        func_name = words[-1]
        if func_name in SEND_FUNCTIONS:
            return True

    return False

def main():
    global generated_keys
    generated_keys = set()

    if not os.path.exists(INPUT_FILE):
        print("❌ Файл не найден")
        return

    shutil.copy2(INPUT_FILE, BACKUP_FILE)
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lexicon = load_lexicon()
    if MODULE_PREFIX not in lexicon:
        lexicon[MODULE_PREFIX] = {}

    replacements = []

    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        if lineno < START_LINE:
            i += 1
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        comment_pos = line.find('#')
        j = 0
        while j < len(line):
            if comment_pos != -1 and j >= comment_pos:
                break  # пропускаем комментарии
            # Определяем начало кавычек
            if j < len(line) and line[j] in ('"', "'"):
                quote_start = j
            elif j + 2 < len(line) and line[j:j+3] in ('"""', "'''"):
                quote_start = j
            else:
                j += 1
                continue

            # Ищем f/F перед кавычкой
            literal_start = quote_start
            k = quote_start - 1
            while k >= 0 and line[k] in "fFrR":
                k -= 1
            if k + 1 < quote_start:
                literal_start = k + 1

            result = extract_string_literal(lines, i, literal_start)
            if result:
                body, start_line, end_line, is_fstring, full_literal = result
                if has_cyrillic(body):
                    if is_in_valid_context(lines, i, literal_start):
                        if is_fstring:
                            is_simple, placeholders = extract_placeholders(body)
                            slug_body = re.sub(r"(?<!\{)\{[^}]*\}(?!\})", "value", body)
                            key = smart_slugify(slug_body)
                            full_key = f"{MODULE_PREFIX}.{key}"
                            if key not in lexicon[MODULE_PREFIX]:
                                lexicon[MODULE_PREFIX][key] = body

                            base_call = f'get_text("{full_key}", lang)'
                            if is_simple and placeholders:
                                fmt_args = ", ".join(f"{v}={v}" for v in sorted(set(placeholders)))
                                replacement = f"{base_call}.format({fmt_args})"
                            else:
                                replacement = f"{base_call}.format(/*** NEED MANUAL FIX ***/)"
                        else:
                            key = smart_slugify(body)
                            full_key = f"{MODULE_PREFIX}.{key}"
                            if key not in lexicon[MODULE_PREFIX]:
                                lexicon[MODULE_PREFIX][key] = body
                            replacement = f'get_text("{full_key}", lang)'

                        replacements.append((
                            start_line, end_line, full_literal, replacement, body
                        ))
                        j = literal_start + len(full_literal)
                        continue

            j += 1
        i += 1

    # === ИСПРАВЛЕННАЯ ЛОГИКА ЗАМЕНЫ ===
    new_lines = lines[:]
    for start_line, end_line, full_literal, replacement, _ in reversed(replacements):
        # Собираем весь блок строк, где находится литерал
        block_lines = lines[start_line:end_line + 1]
        block_text = "".join(block_lines)

        # Находим позицию литерала в блоке
        idx = block_text.find(full_literal)
        if idx == -1:
            # Если не найден — пропускаем (маловероятно, но на всякий случай)
            continue

        # Разделяем на префикс, литерал, суффикс
        prefix = block_text[:idx]
        suffix = block_text[idx + len(full_literal):]

        # Удаляем 'f' или 'F' из конца prefix
        if prefix.endswith('f') or prefix.endswith('F'):
            prefix = prefix[:-1]

        # Формируем новую строку кода
        new_code_line = prefix + replacement + suffix

        # Подготавливаем закомментированный оригинал
        commented_block = []
        for k in range(start_line, end_line + 1):
            orig_line = lines[k]
            stripped_orig = orig_line.rstrip()
            if stripped_orig and not stripped_orig.lstrip().startswith('#'):
                commented_block.append("# " + stripped_orig + "\n")
            else:
                commented_block.append(stripped_orig + "\n")

        # Заменяем блок: сначала комментарии, потом новая строка
        replacement_block = commented_block + [new_code_line + "\n"]

        new_lines = (
            new_lines[:start_line] +
            replacement_block +
            new_lines[end_line + 1:]
        )

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    save_lexicon(lexicon)
    print(f"✅ Обработано {len(replacements)} строк.")

if __name__ == "__main__":

    main()


