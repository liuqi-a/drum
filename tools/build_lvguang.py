# 用途：生成《绿光》完整 85 小节的鼓谱数据（依据谱面结构 + 段落化节奏型）
import json
import sys

# 谱面（1–60 小节）之外用重复编排补到歌曲结束：鼓组从 14.33 秒进入，
# (191.85-14.33)/2.2642 ≈ 78.4，因此整首共 79 小节
TOTAL_BARS = 79


def ev(pitch, pos, dur=2, voice=0):
    return {'pitch': pitch, 'pos': pos, 'dur': dur, 'voice': voice}


def eighth_groove(with_crash=False):
    # 谱面主织体：16 分踩镲 + 2/4 拍边击(cross-stick) + 1/3 拍底鼓
    out = []
    if with_crash:
        out.append(ev(49, 0, 4))
    for p in range(16):
        out.append(ev(42, p, 1))
    out += [ev(37, 4, 2), ev(37, 12, 2)]
    out += [ev(36, 0, 2, 1), ev(36, 8, 2, 1)]
    return out


def sixteenth_groove(with_crash=False):
    return eighth_groove(with_crash)


def sparse_intro_bar(with_kick=True):
    # 引子：2、4 拍打镲（边击），可选 1 拍底鼓
    out = [ev(42, 4, 2), ev(42, 12, 2), ev(37, 4, 2), ev(37, 12, 2)]
    if with_kick:
        out.append(ev(36, 0, 2, 1))
    return out


def intro_accent():
    # 引子里 1/3/5/7 小节的开镲重音（谱面用带圈 x 标注）
    return [ev(46, 4, 2), ev(46, 12, 2)]


def fill_bar(start_pitch):
    # 整小节 16 分过门：军鼓起、下行嗵鼓收，最后落底鼓
    seq = [38, 38, 38, 38, 50, 50, 47, 47, 41, 41, 38, 38, 36, 36, 36, 36]
    out = []
    for i, pitch in enumerate(seq):
        out.append(ev(pitch, i, 1))
    return out


def main():
    bars = []
    for n in range(1, TOTAL_BARS + 1):
        events = []
        if n == 1:
            events = [ev(49, 0, 4), ev(36, 0, 4, 1)] + intro_accent()
        elif 2 <= n <= 7:
            events = sparse_intro_bar()
            if n % 2 == 1:
                events += intro_accent()
        elif 8 <= n <= 15:
            events = eighth_groove(with_crash=(n == 8))
        elif 16 <= n <= 31:
            if n in (16, 20, 24, 28):
                events = sixteenth_groove(with_crash=True)
            elif n in (19, 23, 27, 31):
                events = fill_bar(38)
            else:
                events = eighth_groove()
        elif 32 <= n <= 35:
            events = fill_bar(38 if n % 2 else 41)
        elif 36 <= n <= 47:
            events = eighth_groove(with_crash=(n == 36))
        elif 48 <= n <= 59:
            if n in (48, 52, 56):
                events = sixteenth_groove(with_crash=True)
            elif n == 59:
                events = fill_bar(38)
            else:
                events = eighth_groove()
        elif 60 <= n <= 61:
            if n == 60:
                events = [ev(49, 0, 4), ev(36, 0, 4, 1)]
            else:
                events = sparse_intro_bar(with_kick=(n % 2 == 1))
        elif n >= 62:
            if n == 62:
                events = sixteenth_groove(with_crash=True)
            elif n == 79:
                events = fill_bar(38)
            else:
                events = sixteenth_groove() if n % 4 == 0 else eighth_groove()
        else:
            events = [ev(49, 0, 4)]
        bars.append({'events': events})
    # 每行 4 小节，与纸谱排版一致
    for i in range(3, TOTAL_BARS, 4):
        bars[i]['lineBreak'] = True
    data = {'title': '绿光', 'brand': '绿光新编排', 'tempo': 106, 'total16': 16, 'bars': bars}
    json.dump(data, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已生成 %d 小节 -> %s' % (TOTAL_BARS, sys.argv[1]))


if __name__ == '__main__':
    main()
