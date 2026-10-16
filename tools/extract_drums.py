# 用途：从 MuseScore 自带模板里提取鼓组映射表（音高/符头/谱表位置/声部/符干），供生成鼓谱时复用
import json
import re
import sys


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    text = open(src, encoding='utf-8').read()
    m = re.search(r'<Instrument id="drum-kit-5">.*?</Instrument>', text, re.S)
    if not m:
        print('没找到鼓组定义')
        return
    blk = m.group(0)
    drums = []
    for d in re.finditer(r'<Drum pitch="(\d+)">(.*?)</Drum>', blk, re.S):
        pitch = int(d.group(1))
        body = d.group(2)
        def pick(tag, default=''):
            mm = re.search(r'<%s>(.*?)</%s>' % (tag, tag), body, re.S)
            return mm.group(1).strip() if mm else default
        drums.append({
            'pitch': pitch,
            'line': int(pick('line', '0')),
            'head': pick('head', 'normal'),
            'voice': int(pick('voice', '0')),
            'stem': int(pick('stem', '1')),
            'name': pick('name'),
            'shortcut': pick('shortcut'),
            'panelRow': int(pick('panelRow', '0')),
            'panelColumn': int(pick('panelColumn', '0')),
        })
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(drums, f, ensure_ascii=False, indent=1)
    print('鼓组条目数:', len(drums))
    for d in drums:
        print('pitch=%-3d line=%-3d head=%-8s voice=%d stem=%d  %s' % (
            d['pitch'], d['line'], d['head'], d['voice'], d['stem'], d['name']))


if __name__ == '__main__':
    main()
