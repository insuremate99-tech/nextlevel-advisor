#!/usr/bin/env python3
import glob, re
from bs4 import BeautifulSoup

ICON_BULLETS = {'📍','🚫','✔️','✅','👉','💡','⚠️','🟢','🟡','🔴','📌','🔥','💰',
                '📊','📈','📉','💪','🎯','⚡','🌟','✨','💎','🏆','📝','🔑','➡️',
                '⭐','🎉','👇','👆','◾','◽','🔸','🔹','🔶','🔷','☑️','🔔','📣',
                '💬','📢','🏅','▶️','🔺','🔻'}

NUM_RE   = re.compile(r'^(\d+)[.)]\s+(.+)', re.DOTALL)
DASH_RE  = re.compile(r'^[-–]\s+(.+)', re.DOTALL)
HASH_RE  = re.compile(r'^#\w')
ARROW_RE = re.compile(r'^>>\s*(.+)', re.DOTALL)

def starts_with_icon(t):
    for ic in ICON_BULLETS:
        if t.startswith(ic):
            return ic
    return None

def split_inline_icons(text):
    """'📍 item1 📍 item2' → [(ic, txt), ...]"""
    positions = []
    for ic in ICON_BULLETS:
        for m in re.finditer(re.escape(ic), text):
            positions.append((m.start(), ic))
    if not positions:
        return None
    positions.sort()
    items = []
    for i, (pos, ic) in enumerate(positions):
        start = pos + len(ic)
        end = positions[i+1][0] if i+1 < len(positions) else len(text)
        txt = text[start:end].strip()
        if txt:
            items.append((ic, txt))
    return items if len(items) >= 2 else None

def make_card(num, text):
    return f'<div class="case-item"><div class="case-num">{num}</div><div class="case-text font-noto">{text}</div></div>\n'

def make_icon_list(items):
    lis = ''.join(f'<li><span class="ic">{ic}</span><span>{txt}</span></li>' for ic, txt in items)
    return f'<ul class="icon-list font-noto">{lis}</ul>\n'

def make_dash_list(items):
    lis = ''.join(f'<li><span class="ic">•</span><span>{txt}</span></li>' for txt in items)
    return f'<ul class="icon-list font-noto">{lis}</ul>\n'

def process_article(article):
    share = article.find('div', class_='mt-8')
    share_html = str(share) if share else ''

    # Collect content tags before share section
    content_tags = []
    for child in list(article.children):
        if child == share:
            break
        if hasattr(child, 'name') and child.name:
            content_tags.append(child)

    # Check if any tag needs processing
    needs_work = False
    for tag in content_tags:
        if tag.name == 'p':
            t = tag.get_text(strip=True)
            if (NUM_RE.match(t) or DASH_RE.match(t) or HASH_RE.match(t) or
                    ARROW_RE.match(t) or split_inline_icons(t)):
                needs_work = True
                break

    if not needs_work:
        return None

    parts = []
    dash_buf = []
    icon_buf = []
    pending_num_card = None  # (num, text, sub_dashes)

    def flush_dash():
        nonlocal dash_buf
        if dash_buf:
            h = make_dash_list(dash_buf[:])
            dash_buf = []
            return h
        return ''

    def flush_icons():
        nonlocal icon_buf
        if icon_buf:
            h = make_icon_list(icon_buf[:])
            icon_buf = []
            return h
        return ''

    def flush_pending_card():
        nonlocal pending_num_card, dash_buf
        if pending_num_card is None:
            return ''
        num, text, sub = pending_num_card
        pending_num_card = None
        if sub:
            sub_html = '<ul style="margin-top:.75rem;padding-left:1.25rem;list-style:disc">'
            for s in sub:
                sub_html += f'<li style="margin-bottom:.4rem">{s}</li>'
            sub_html += '</ul>'
            return make_card(num, text + sub_html)
        return make_card(num, text)

    for tag in content_tags:
        if tag.name != 'p':
            # Non-p tags (h2, ul, div, etc) — flush buffers and emit as-is
            parts.append(flush_pending_card())
            parts.append(flush_dash())
            parts.append(flush_icons())
            parts.append(str(tag))
            continue

        text = tag.get_text(strip=True)

        # Skip empty / hashtag lines
        if not text or HASH_RE.match(text):
            continue

        # Inline multiple icons in one para → split
        inline = split_inline_icons(text)
        if inline:
            parts.append(flush_pending_card())
            parts.append(flush_dash())
            parts.append(flush_icons())
            parts.append(make_icon_list(inline))
            continue

        # Numbered item "1. text" or "1) text"
        nm = NUM_RE.match(text)
        if nm:
            # Flush previous dash buffer as sub-bullets of LAST card if pending
            if pending_num_card and dash_buf:
                n, t, _ = pending_num_card
                pending_num_card = (n, t, dash_buf[:])
                dash_buf = []
            parts.append(flush_pending_card())
            parts.append(flush_dash())
            parts.append(flush_icons())
            pending_num_card = (nm.group(1), nm.group(2).strip(), [])
            continue

        # Dash bullet "- text" → may be sub-item of numbered card OR standalone
        dm = DASH_RE.match(text)
        if dm:
            parts.append(flush_icons())
            if pending_num_card:
                # Sub-bullet under current numbered card
                n, t, sub = pending_num_card
                sub.append(dm.group(1))
                pending_num_card = (n, t, sub)
            else:
                dash_buf.append(dm.group(1))
            continue

        # Single icon bullet "📍 text"
        ic = starts_with_icon(text)
        if ic:
            parts.append(flush_pending_card())
            parts.append(flush_dash())
            icon_buf.append((ic, text[len(ic):].strip().lstrip(':').strip()))
            continue

        # Arrow quote ">> text"
        am = ARROW_RE.match(text)
        if am:
            parts.append(flush_pending_card())
            parts.append(flush_dash())
            parts.append(flush_icons())
            parts.append(f'<div class="quote-box font-noto">{am.group(1)}</div>\n')
            continue

        # Regular paragraph — flush pending
        parts.append(flush_pending_card())
        parts.append(flush_dash())
        parts.append(flush_icons())
        parts.append(str(tag) + '\n')

    parts.append(flush_pending_card())
    parts.append(flush_dash())
    parts.append(flush_icons())

    new_content = ''.join(p for p in parts if p)
    new_inner = '\n    \n    ' + new_content.strip() + '\n    ' + share_html + '\n  '
    new_art = BeautifulSoup(
        f'<article class="prose font-noto" style="color:#334155">{new_inner}</article>',
        'html.parser'
    ).find('article')
    return new_art


def main():
    files = sorted(glob.glob('/tmp/nla3/articles/*-25*.html'))
    fixed, skipped, errors = 0, 0, []

    for fp in files:
        try:
            content = open(fp).read()
            soup = BeautifulSoup(content, 'html.parser')
            article = soup.find('article', class_='prose')
            if not article:
                skipped += 1
                continue

            new_art = process_article(article)
            if new_art is None:
                skipped += 1
                continue

            article.replace_with(new_art)
            open(fp, 'w').write(str(soup))
            fixed += 1
        except Exception as e:
            errors.append((fp.split('/')[-1], str(e)))

    print(f'\n✅ Fixed: {fixed}  ⏭ Skipped: {skipped}  ❌ Errors: {len(errors)}')
    for fn, e in errors[:10]:
        print(f'  {fn}: {e}')

if __name__ == '__main__':
    main()
