"""Local question-bank import and conservative option matching."""
import re
import unicodedata
from difflib import SequenceMatcher


def signed_today(text):
    if '【今天未签到】' in text:
        return False
    return any(s in text for s in ('【今天已签到】', '您今天已经签到', '您今日已经签到'))


def _number(match):
    digits = dict(zip('零〇一二两三四五六七八九', [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
    s = match.group()
    if not any(c in s for c in '十百千'):
        return ''.join(str(digits[c]) for c in s)
    total = current = 0
    for c in s:
        if c in digits:
            current = digits[c]
        else:
            total += (current or 1) * {'十': 10, '百': 100, '千': 1000}[c]
            current = 0
    return str(total + current)


def normalize(text):
    text = unicodedata.normalize('NFKC', text or '').lower()
    text = re.sub(r'\s+', '', text)
    # Only convert numbers in a numeric context, not song/person names.
    text = re.sub(r'[零〇一二两三四五六七八九十百千]+(?=[个届年月日号场首次张岁人])', _number, text)
    if re.fullmatch(r'[零〇一二两三四五六七八九十百千]+', text):
        text = _number(re.match(r'.+', text))
    return ''.join(c for c in text if c.isalnum())


def parse_bank(text):
    rows, issues = [], []
    pending = None
    for line_no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip().lstrip('\ufeff')
        if not s or re.match(r'^[一二三四五六七八九十]+、', s):
            continue
        s = re.sub(r'^(?:\d+|[a-z])[.、．]\s*', '', s).strip()
        if not s:
            continue
        if pending and re.match(r'^答(?:案)?[：:]', s):
            s = '—' + re.sub(r'^答(?:案)?[：:]\s*', '', s)
        pair = re.split(r'\s*[—–]+\s*', s, maxsplit=1)
        if len(pair) == 2 and not pair[0] and pending:
            question, answer = pending[1], pair[1]
            pending = None
        elif len(pair) == 2 and pair[0] and pair[1]:
            question, answer = pair
        else:
            boundary = max(s.rfind('？'), s.rfind('?'))
            pair = [s[:boundary], s[boundary + 1:].strip()] if boundary >= 0 else [s]
            if len(pair) == 2 and normalize(pair[1]) and not re.search(r'错啦|已收录|啊喂|讲真', pair[1]) and not pair[1].startswith(('（', '(')):
                question, answer = pair[0] + '？', pair[1]
            else:
                if pending:
                    issues.append({'kind':'unparsed', 'line':pending[0], 'text':pending[1]})
                pending = (line_no, s)
                continue
        if pending:
            issues.append({'kind':'unparsed', 'line':pending[0], 'text':pending[1]})
            pending = None
        corrected = re.search(r'正确答案[是为：:]\s*(.+)', answer)
        if corrected:
            answer = corrected.group(1).rstrip('!！。 ')
        if re.search(r'错啦|是错的|不确定|待确认', answer):
            issues.append({'kind':'uncertain', 'line':line_no, 'text':s})
            continue
        rows.append({'question':question.strip(), 'answer':answer.strip(), 'line':line_no})
    if pending:
        issues.append({'kind':'unparsed', 'line':pending[0], 'text':pending[1]})
    groups = {}
    unique = []
    seen = set()
    for row in rows:
        key = (normalize(row['question']), normalize(row['answer']))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        groups.setdefault(key[0], []).append(row)
    for entries in groups.values():
        if len(entries) > 1:
            issues.append({'kind':'conflict', 'entries':entries})
    return unique, issues


def question_score(question, candidate):
    a, b = normalize(question), normalize(candidate)
    if a == b:
        return 1.0
    # Preserve dates and negation: similar wording can ask the opposite question.
    if re.findall(r'\d+', a) != re.findall(r'\d+', b):
        return 0
    if ('不' in a or '没' in a) != ('不' in b or '没' in b):
        return 0
    return SequenceMatcher(None, a, b).ratio()


def answer_matches(answer, option):
    option = re.sub(r'^[A-Da-d][.、:：)）]\s*', '', option.strip())
    target = normalize(option)
    if not target:
        return False
    variants = [answer, re.sub(r'[（(].*?[）)]', '', answer)]
    variants += re.split(r'\s*/\s*', variants[1])
    for variant in variants:
        value = normalize(variant)
        if value == target:
            return True
        # Exact numeric answer may omit the unit used by the option.
        if value.isdigit() and re.fullmatch(re.escape(value) + r'(?:年|个|场|首|次|张|人|岁|号|届)', target):
            return True
    return False


def choose_option(question, options, bank):
    scored = [(question_score(question, variant), row) for row in bank
              for variant in [row['question']] + row['question'].split('/')]
    if not scored:
        return None
    best = max(s for s, _ in scored)
    if best < .88:
        return None
    top = [r for s, r in scored if s >= best - .025]
    if len({normalize(r['answer']) for r in top}) != 1:
        return None
    matches = [i for i, option in enumerate(options) if answer_matches(top[0]['answer'], option)]
    return matches[0] if len(matches) == 1 else None
