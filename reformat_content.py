#!/usr/bin/env python3
import os, re, glob
from bs4 import BeautifulSoup, NavigableString, Tag

EMOJI_NUMS_MAP = {
    '1️⃣':'1','2️⃣':'2','3️⃣':'3','4️⃣':'4','5️⃣':'5',
    '6️⃣':'6','7️⃣':'7','8️⃣':'8','9️⃣':'9','\U0001f51f':'10',
}
EMOJI_NUM_PATS = list(EMOJI_NUMS_MAP.keys())
EMOJI_NUM_RE = re.compile(r'^(' + '|'.join(re.escape(e) for e in EMOJI_NUM_PATS) + r')[.:]?\s*(.*)', re.DOTALL)

ICON_BULLETS = {'\U0001f6ab','✔️','✅','\U0001f449','\U0001f4a1','⚠️',
                '\U0001f7e2','\U0001f7e1','\U0001f534','\U0001f4cc','\U0001f525','\U0001f4b0',
                '\U0001f4ca','\U0001f4c8','\U0001f4c9','\U0001f4aa','\U0001f3af','⚡',
                '\U0001f31f','✨','\U0001f48e','\U0001f3c6','\U0001f4dd','\U0001f511',
                '\U0001f446','✓','◾','◽','\U0001f538','\U0001f539','\U0001f536',
                '\U0001f537','☑️','\U0001f514','\U0001f4e3','➡️',
                '⬆️','⬇️','\U0001f53a','\U0001f53b','\U0001f4ac','\U0001f4e2',
                '⭐','\U0001f308','\U0001f389','\U0001f3c5'}

HASHTAG_RE = re.compile(r'^#\w')

EXTRA_CSS = '''
    .case-item{display:flex;gap:1rem;margin:1rem 0 1.25rem;padding:1.25rem 1.5rem;background:#F8FAFC;border-radius:14px;border:1px solid #E2E8F0;align-items:flex-start;transition:all .25s}
    .case-item:hover{border-color:#BAE6FD;background:#F0F9FF}
    .case-num{min-width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#1B365D,#0891B2);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.88rem;flex-shrink:0;font-family:Poppins,sans-serif;margin-top:2px}
    .case-text{line-height:1.9;font-size:1.02rem;flex:1}
    .icon-list{list-style:none;padding:0;margin:.5rem 0 1.25rem;background:#FAFBFC;border-radius:12px;border:1px solid #E8EDF5;overflow:hidden}
    .icon-list li{display:flex;gap:.75rem;padding:.7rem 1.1rem;line-height:1.85;align-items:flex-start;font-size:.98rem;border-bottom:1px solid #F1F5F9}
    .icon-list li:last-child{border-bottom:none}
    .icon-list li .ic{flex-shrink:0;font-size:1.05rem}
    .quote-box{background:linear-gradient(135deg,#EFF6FF,#F0F9FF);border-left:4px solid #0891B2;border-radius:0 14px 14px 0;padding:1.1rem 1.5rem;margin:1.5rem 0;line-height:1.9;font-size:1rem}
    .divider-section{margin:2rem 0 1rem;font-weight:600;font-size:1.1rem;color:#1B365D;padding-bottom:.5rem;border-bottom:2px solid #E2E8F0;font-family:Pridi,serif}
'''
CSS_ANCHOR = '#readProgress{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,#0891B2,#38BDF8);z-index:9999;transition:width .1s linear;width:0%}'

def starts_with_icon(text):
    for icon in ICON_BULLETS:
        if text.startswith(icon):
            return icon
    return None

def is_separator(t):
    s = t.strip()
    return s in ['.','·','•','','..','...','–','—','\U0001f447','\U0001f447\U0001f447','\U0001f446','\U0001f446\U0001f446','..']

def is_hashtag_line(t):
    return bool(HASHTAG_RE.match(t.strip()))

def extract_lines(article_tag):
    segs = []
    for child in list(article_tag.children):
        if isinstance(child, Tag):
            cls = child.get('class', [])
            if 'mt-8' in cls:
                break
            if child.name == 'p':
                inner = str(child)
                inner = re.sub(r'^<p[^>]*>', '', inner)
                inner = re.sub(r'</p>$', '', inner)
                segs.append(inner + '\n')
            elif child.name in ('ul','ol'):
                for li in child.find_all('li', recursive=False):
                    segs.append('BULLET ' + li.get_text(separator=' ', strip=True) + '\n')
            elif child.name in ('h2','h3'):
                segs.append('##' + child.get_text(strip=True) + '\n')
            elif child.name == 'div':
                pass
        elif isinstance(child, NavigableString):
            segs.append(str(child))
    combined = ''.join(segs)
    combined = re.sub(r'<br\s*/?>', '\n', combined, flags=re.IGNORECASE)
    combined = re.sub(r'<[^>]+>', '', combined)
    combined = (combined.replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
                .replace('&nbsp;',' ').replace('&#39;',"'").replace('&quot;','"'))
    lines = [l.strip() for l in combined.split('\n')]
    result, prev_empty = [], False
    for l in lines:
        empty = not l
        if empty and prev_empty:
            continue
        result.append(l)
        prev_empty = empty
    return result

def needs_reformat(lines):
    if not lines:
        return False
    for l in lines:
        if EMOJI_NUM_RE.match(l.strip()):
            return True
    for l in lines:
        if starts_with_icon(l.strip()):
            return True
    sep = sum(1 for l in lines if is_separator(l))
    return sep > 3 and sep / max(len(lines),1) > 0.12

def lines_to_html(lines):
    parts = []
    i = 0
    icon_items = []
    para_lines = []

    def flush_icons():
        nonlocal icon_items
        if not icon_items:
            return ''
        h = '<ul class="icon-list font-noto">\n'
        for ic, tx in icon_items:
            h += f'  <li><span class="ic">{ic}</span><span>{tx}</span></li>\n'
        h += '</ul>\n'
        icon_items = []
        return h

    def flush_para():
        nonlocal para_lines
        if para_lines:
            text = ' '.join(para_lines).strip()
            para_lines = []
            if text:
                return f'<p>{text}</p>\n'
        return ''

    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if is_separator(line) or is_hashtag_line(line):
            parts.append(flush_icons())
            parts.append(flush_para())
            continue
        if not line:
            continue
        if line.startswith('##'):
            parts.append(flush_icons())
            parts.append(flush_para())
            text = line[2:].strip()
            text = re.sub(r'^[✔️✅✓]\s*', '', text).strip()
            parts.append(f'<h2 class="divider-section">{text}</h2>\n')
            continue
        if line.startswith('>>>') or line.startswith('>>'):
            parts.append(flush_icons())
            parts.append(flush_para())
            text = line.lstrip('>').strip()
            if text:
                parts.append(f'<div class="quote-box font-noto">{text}</div>\n')
            continue
        if line.startswith('[['):
            parts.append(flush_icons())
            parts.append(flush_para())
            text = line.lstrip('[').rstrip(']').strip()
            if text:
                parts.append(f'<div class="highlight-box font-noto">{text}</div>\n')
            continue
        m = EMOJI_NUM_RE.match(line)
        if m:
            parts.append(flush_icons())
            parts.append(flush_para())
            num = EMOJI_NUMS_MAP[m.group(1)]
            text = m.group(2).strip().lstrip('.').strip()
            sub = []
            while i < len(lines):
                nl = lines[i].strip()
                if nl.startswith('BULLET '):
                    sub.append(nl[7:])
                    i += 1
                elif is_separator(nl) or not nl:
                    i += 1
                    break
                else:
                    break
            card = f'<div class="case-item"><div class="case-num">{num}</div><div class="case-text font-noto">{text}'
            if sub:
                card += '<ul style="margin-top:.75rem;padding-left:1.25rem;list-style:disc">'
                for b in sub:
                    card += f'<li style="margin-bottom:.4rem">{b}</li>'
                card += '</ul>'
            card += '</div></div>\n'
            parts.append(card)
            continue
        if line.startswith('BULLET '):
            parts.append(flush_para())
            icon_items.append(('•', line[7:].strip()))
            continue
        icon = starts_with_icon(line)
        if icon:
            parts.append(flush_para())
            text = line[len(icon):].strip().lstrip(':').strip()
            icon_items.append((icon, text))
            continue
        parts.append(flush_icons())
        para_lines.append(line)
    parts.append(flush_icons())
    parts.append(flush_para())
    return ''.join(p for p in parts if p)

def reformat_article(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    modified = False
    if 'case-item' not in content and CSS_ANCHOR in content:
        content = content.replace(CSS_ANCHOR, CSS_ANCHOR + EXTRA_CSS)
        modified = True
    soup = BeautifulSoup(content, 'html.parser')
    article = soup.find('article', class_='prose')
    if not article:
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        return
    share_div = article.find('div', class_='mt-8')
    share_html = str(share_div) if share_div else ''
    lines = extract_lines(article)
    if not lines or not needs_reformat(lines):
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))
        return
    new_html = lines_to_html(lines)
    if not new_html.strip():
        return
    new_inner = '\n    \n    ' + new_html.strip() + '\n    ' + share_html + '\n  '
    new_art = BeautifulSoup(
        f'<article class="prose font-noto" style="color:#334155">{new_inner}</article>',
        'html.parser'
    ).find('article')
    article.replace_with(new_art)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(soup))

def main():
    files = sorted(glob.glob('/tmp/nla3/articles/*-25*.html'))
    skip = {'annuity-250114.html'}
    done, errs = 0, []
    for fp in files:
        fname = os.path.basename(fp)
        if fname in skip:
            continue
        try:
            reformat_article(fp)
            done += 1
            if done % 50 == 0:
                print(f'  {done}/{len(files)} done...')
        except Exception as e:
            errs.append((fname, str(e)))
    print(f'\n✅ Done: {done}')
    if errs:
        print(f'❌ Errors: {len(errs)}')
        for f,e in errs[:10]:
            print(f'  {f}: {e}')

if __name__ == '__main__':
    main()
