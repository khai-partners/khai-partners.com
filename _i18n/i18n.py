"""Segment-level i18n for a static site.
extract: python3 i18n.py extract  -> strings.json  (unique normalised segments, with first page seen)
build:   python3 i18n.py build    -> writes id/*.html using id.json (missing keys reported)
"""
import re, sys, json, glob, os, html as H

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
D = os.path.dirname(os.path.abspath(__file__)) + '/'
PAGES = sorted(os.path.basename(p) for p in glob.glob(R + '*.html') if os.path.basename(p) != '404.html')

TEXT_ATTRS = ['alt', 'title', 'placeholder', 'aria-label', 'data-default']
SKIP_BLOCKS = re.compile(r'(<(script|style|svg)\b.*?</\2\s*>)', re.S | re.I)
TAG = re.compile(r'<[^>]+>', re.S)


def norm(t):
    return re.sub(r'\s+', ' ', t).strip()


def wordy(t):
    k = norm(H.unescape(t))
    if not k or not re.search(r'[A-Za-z]', k):
        return None
    return k


def split_protected(s):
    """yield (is_code, chunk); code = script/style/svg blocks and HTML comments"""
    pat = re.compile(r'(<(script|style|svg)\b.*?</\2\s*>|<!--.*?-->)', re.S | re.I)
    pos = 0
    for m in pat.finditer(s):
        yield False, s[pos:m.start()]
        yield True, m.group(0)
        pos = m.end()
    yield False, s[pos:]


def iter_segments(s):
    """yield ('text'|'attr'|'title'|'meta', key) for every translatable segment."""
    for code, chunk in split_protected(s):
        if code:
            continue
        # text nodes
        for m in re.finditer(r'>([^<]+)<', chunk):
            k = wordy(m.group(1))
            if k:
                yield k
        for t in TAG.findall(chunk):
            for a in TEXT_ATTRS:
                for m in re.finditer(r'\b' + a + r'\s*=\s*"([^"]*)"', t):
                    k = wordy(m.group(1))
                    if k:
                        yield k
            if re.match(r'<meta\b', t, re.I) and re.search(r'name="description"|property="og:(title|description)"', t):
                m = re.search(r'content="([^"]*)"', t)
                if m and wordy(m.group(1)):
                    yield wordy(m.group(1))
            if re.match(r'<input\b', t, re.I) and re.search(r'type="(submit|button)"', t):
                m = re.search(r'\bvalue="([^"]*)"', t)
                if m and wordy(m.group(1)):
                    yield wordy(m.group(1))
            if re.match(r'<input\b', t, re.I) and 'data-default' in t:
                m = re.search(r'\bvalue="([^"]*)"', t)
                if m and wordy(m.group(1)):
                    yield wordy(m.group(1))


def extract():
    seen = {}
    for p in PAGES:
        s = open(R + p, encoding='utf-8').read()
        for k in iter_segments(s):
            seen.setdefault(k, p)
    json.dump(seen, open(D + 'strings.json', 'w'), ensure_ascii=False, indent=1)
    print(len(seen), 'unique segments;', sum(len(k.split()) for k in seen), 'words')


# ------------------------------------------------------------------ build
ASSET_ATTR = re.compile(r'''(\b(?:src|href|data-thumb|data-lazyload|poster|action|data-home)\s*=\s*)(["']?)([^"'\s>]+)\2''', re.I)


def is_relative_asset(u):
    if not u or u.startswith(('#', '/', 'http:', 'https:', 'mailto:', 'tel:', 'data:', 'javascript:', '//', '{', '$')):
        return False
    return True


def fix_urls(chunk):
    return re.sub(r'''url\((['"]?)(?!['"]?(?:https?:|data:|/|\.\./))([^'")]+)\1\)''', lambda m: f'url({m.group(1)}../{m.group(2)}{m.group(1)})', chunk)


def fix_paths(chunk):
    def rep(m):
        pre, q, u = m.groups()
        base = u.split('#')[0].split('?')[0]
        if not is_relative_asset(u):
            return m.group(0)
        if base.endswith('.html') and '/' not in base:
            return m.group(0)                         # sibling page -> stays inside /id/
        return f'{pre}{q}../{u}{q}'
    chunk = ASSET_ATTR.sub(rep, chunk)
    chunk = re.sub(r'''url\((['"]?)(?!['"]?(?:https?:|data:|/|\.\./))([^'")]+)\1\)''', lambda m: f'url({m.group(1)}../{m.group(2)}{m.group(1)})', chunk)
    return chunk


def tr_text(raw, T, missing):
    k = wordy(raw)
    if not k:
        return raw
    if k not in T:
        missing.add(k); return raw
    lead = re.match(r'^\s*', raw).group(0); trail = re.search(r'\s*$', raw).group(0)
    return lead + H.escape(T[k], quote=False) + trail


def tr_attr_val(v, T, missing):
    k = wordy(v)
    if not k:
        return v
    if k not in T:
        missing.add(k); return v
    return H.escape(T[k], quote=True)


def translate_chunk(chunk, T, missing):
    out, pos = [], 0
    for m in TAG.finditer(chunk):
        out.append(tr_text(chunk[pos:m.start()], T, missing) if '<' not in chunk[pos:m.start()] else chunk[pos:m.start()])
        t = m.group(0)
        for a in TEXT_ATTRS:
            t = re.sub(r'(\b' + a + r'\s*=\s*")([^"]*)(")', lambda mm: mm.group(1) + tr_attr_val(mm.group(2), T, missing) + mm.group(3), t)
        if re.match(r'<meta\b', t, re.I) and re.search(r'name="description"|property="og:(title|description)"', t):
            t = re.sub(r'(content=")([^"]*)(")', lambda mm: mm.group(1) + tr_attr_val(mm.group(2), T, missing) + mm.group(3), t)
        if re.match(r'<input\b', t, re.I) and (re.search(r'type="(submit|button)"', t) or 'data-default' in t):
            t = re.sub(r'(\bvalue=")([^"]*)(")', lambda mm: mm.group(1) + tr_attr_val(mm.group(2), T, missing) + mm.group(3), t)
        out.append(t)
        pos = m.end()
    out.append(tr_text(chunk[pos:], T, missing))
    return ''.join(out)


def build():
    T = json.load(open(D + 'id.json', encoding='utf-8'))
    T = {norm(k): v for k, v in T.items()}
    os.makedirs(R + 'id', exist_ok=True)
    missing_all = {}
    for p in PAGES:
        s = open(R + p, encoding='utf-8', newline='').read()
        missing = set()
        parts = []
        for code, chunk in split_protected(s):
            if code:
                low = chunk.lstrip().lower()
                if low.startswith('<style'):
                    parts.append(fix_urls(chunk))
                elif low.startswith('<script'):
                    e = chunk.find('>') + 1
                    parts.append(fix_paths(chunk[:e]) + chunk[e:])
                else:
                    parts.append(chunk)
            else:
                parts.append(fix_paths(translate_chunk(chunk, T, missing)))
        out = ''.join(parts)
        out = post_id(out, p)
        open(R + 'id/' + p, 'w', encoding='utf-8', newline='').write(out)
        if missing:
            missing_all[p] = sorted(missing)
    json.dump(missing_all, open(D + 'missing.json', 'w'), ensure_ascii=False, indent=1)
    print('built', len(PAGES), 'pages; pages with missing strings:', len(missing_all), sum(len(v) for v in missing_all.values()))


def post_id(s, page):
    s = re.sub(r'<html lang="[^"]*"', '<html lang="id"', s, count=1)
    # script-embedded strings
    for a, b in SCRIPT_STR:
        s = s.replace(a, b)
    # language switcher: make ID active, point EN back to the root page
    s = re.sub(r'<a href="([^"]+)" data-lang-link="en" class="is-active"', lambda m: f'<a href="../{m.group(1)}" data-lang-link="en"', s)
    s = re.sub(r'<a href="\.\./id/([^"]+)" data-lang-link="id"', lambda m: f'<a href="{m.group(1)}" data-lang-link="id" class="is-active"', s)
    s = re.sub(r'<a href="\.\./id/([^"]+)" data-lang-link="id-mobile" lang="id" hreflang="id">[^<]*</a>',
               lambda m: f'<a href="../{m.group(1)}" data-lang-link="en-mobile" lang="en" hreflang="en">English</a>', s)
    assert 'data-lang-link="id" class="is-active"' in s and 'data-lang-link="en-mobile"' in s, page
    return s


SCRIPT_STR = []

if __name__ == '__main__':
    {'extract': extract, 'build': build}[sys.argv[1]]()
