#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面瘦身：从桶下载 -> 压小 -> freeimage 上传 -> 输出 map2。列表格式: <fn> <width>"""
import io, os, sys, time, json, queue, threading, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

SB = 'https://rkhdkoewhwjtzxpjpjim.supabase.co'
FI_KEY = '6d207e02198a847aa98d0a2a901485a5'
OUT = '/tmp/imgsmall'
os.makedirs(OUT, exist_ok=True)
MAP = OUT + '/map2.txt'
lock = threading.Lock()
done = [0]
total = [0]

def bucket_get(fn):
    return urllib.request.urlopen(SB + '/storage/v1/object/public/tb-packs/' + urllib.parse.quote(fn), timeout=90).read()

def shrink(raw, width):
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (245, 245, 247))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert('RGB')
    if im.width > width:
        im = im.resize((width, max(1, int(im.height * width / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85, optimize=True)
    return buf.getvalue()

def fi_upload(jpg, name):
    b = '----fi%d' % int(time.time() * 1000)
    parts = []
    for k, v in (('key', FI_KEY), ('format', 'json')):
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="source"; filename="%s"\r\nContent-Type: image/jpeg\r\n\r\n' % (b, name)).encode())
    parts.append(jpg)
    parts.append(('\r\n--%s--\r\n' % b).encode())
    body = b''.join(parts)
    r = urllib.request.Request('https://freeimage.host/api/1/upload', data=body,
        headers={'Content-Type': 'multipart/form-data; boundary=' + b})
    resp = json.load(urllib.request.urlopen(r, timeout=120))
    return (resp.get('image') or {}).get('url', '')

def one(item):
    fn, width = item
    for attempt in range(3):
        try:
            jpg = shrink(bucket_get(fn), int(width))
            url = fi_upload(jpg, fn.replace('.png', '.jpg'))
            if not url:
                raise RuntimeError('empty url')
            with lock:
                open(MAP, 'a').write('%s %s %d\n' % (fn, url, len(jpg)))
                done[0] += 1
                if done[0] % 50 == 0:
                    print('progress %d/%d' % (done[0], total[0]), flush=True)
            return
        except Exception as e:
            if attempt == 2:
                with lock:
                    open(MAP + '.fail', 'a').write('%s %s\n' % (fn, str(e)[:60]))
                    done[0] += 1
            else:
                time.sleep(1.2)

def main():
    items = []
    for line in open('imglist_small.txt'):
        parts = line.split()
        if len(parts) >= 2:
            items.append((parts[0], parts[1]))
    total[0] = len(items)
    print('total', total[0], flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(one, items))
    print('DONE map=%d' % sum(1 for _ in open(MAP)) if os.path.exists(MAP) else 'DONE map=0', flush=True)

if __name__ == '__main__':
    main()
