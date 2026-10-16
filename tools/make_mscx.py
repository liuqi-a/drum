# 用途：把音符数据（JSON）生成 MuseScore 4 的 .mscx 鼓谱文件，支持标题框、速度、行断与多声部
import json
import sys

# MuseScore 默认鼓组中各音高对应的谱表位置：pos = 距“最低谱线”的半格数
POS_OF_PITCH = {
    36: 1,    # Bass Drum 底鼓（最下间 F4）
    35: 0,    # Bass Drum 2
    38: 5,    # Snare 军鼓（第三间 C5）
    37: 3,    # Cross-stick 边击
    41: 3,    # Floor Tom
    47: 6,    # Low Tom
    50: 7,    # High Tom
    42: 9,    # Closed Hi-Hat 闭镲（最上线之上的间 G5）
    44: -1,   # Pedal Hi-Hat
    46: 9,    # Open Hi-Hat 开镲
    51: 8,    # Ride 叮叮镲（最上线上）
    53: 8,    # Ride Bell
    49: 10,   # Crash 强音镲
    57: 10,   # Crash 2
    55: 12,   # Splash
    52: 11,   # China
}


def drum_table(rows):
    # 生成 Instrument 里的鼓件定义
    out = []
    for d in rows:
        out.append('            <Drum pitch="%d">' % d['pitch'])
        out.append('              <head>%s</head>' % d['head'])
        out.append('              <line>%d</line>' % d['line'])
        out.append('              <voice>%d</voice>' % d['voice'])
        out.append('              <name>%s</name>' % d['name'])
        out.append('              <stem>%d</stem>' % d['stem'])
        out.append('              <panelRow>%d</panelRow>' % d['panelRow'])
        out.append('              <panelColumn>%d</panelColumn>' % d['panelColumn'])
        out.append('            </Drum>')
    return '\n'.join(out)


def note_xml(pitch, voice, track):
    return ('          <Note>\n'
            '            <pitch>%d</pitch>\n'
            '            <track>%d</track>\n'
            '            <voice>%d</voice>\n'
            '            </Note>' % (pitch, track, voice))


def rest_xml(dur_type):
    return '          <Rest>\n            <durationType>%s</durationType>\n            </Rest>' % dur_type


# 时值（以十六分音符为单位）与 MuseScore 记谱名的对应
DUR_NAME = {1: '16th', 2: 'eighth', 3: 'eighth', 4: 'quarter', 6: 'quarter', 8: 'half', 12: 'half', 16: 'whole'}
DUR_DOTS = {3: 1, 6: 1, 12: 1}
REST_PIECES = [(16, 'whole'), (12, 'half'), (8, 'half'), (6, 'quarter'), (4, 'quarter'), (3, 'eighth'), (2, 'eighth'), (1, '16th')]
REST_DOTS = {12: 1, 6: 1, 3: 1}


def rest_xml_dotted(dur_type, dots):
    if dots:
        return ('          <Rest dots="%d">\n            <durationType>%s</durationType>\n            </Rest>'
                % (dots, dur_type))
    return rest_xml(dur_type)


def fill_rests(length):
    # 把任意长度的空隙拆成合法的休止符组合
    out = []
    while length > 0:
        for val, name in REST_PIECES:
            if val <= length:
                out.append(rest_xml_dotted(name, REST_DOTS.get(val, 0)))
                length -= val
                break
    return out


def emit_voice(events, total=16):
    # 把一个声部的事件流（位置/时值，单位十六分）写成 mscx 片段，空缺处补休止符
    events = sorted(events, key=lambda e: (e['pos'], e.get('dur', 1)))
    lines = []
    cursor = 0
    i = 0
    while i < len(events):
        ev = events[i]
        if ev['pos'] > cursor:
            lines.extend(fill_rests(ev['pos'] - cursor))
            cursor = ev['pos']
        group = [ev]
        j = i + 1
        while j < len(events) and events[j]['pos'] == ev['pos']:
            group.append(events[j])
            j += 1
        dur = ev.get('dur', 1)
        name = DUR_NAME.get(dur, '16th')
        d = '<Chord dots="%d">' % DUR_DOTS[dur] if dur in DUR_DOTS else '<Chord>'
        lines.append('        %s' % d)
        lines.append('          <durationType>%s</durationType>' % name)
        for g in group:
            lines.append(note_xml(g['pitch'], g['voice'], g['track']))
        lines.append('          </Chord>')
        cursor = ev['pos'] + dur
        i = j
    if cursor < total:
        lines.extend(fill_rests(total - cursor))
    return lines


def main():
    data = json.load(open(sys.argv[1], encoding='utf-8'))
    drums = json.load(open(sys.argv[2], encoding='utf-8'))
    out_path = sys.argv[3]
    total = data.get('total16', 16)
    body = []
    body.append('<?xml version="1.0" encoding="UTF-8"?>')
    body.append('<museScore version="4.70">')
    body.append('  <Score>')
    body.append('    <Division>480</Division>')
    body.append('    <showFrames>1</showFrames>')
    body.append('    <Part>')
    body.append('      <Staff id="1">')
    body.append('        <StaffType group="percussion">')
    body.append('          <name>perc5Line</name>')
    body.append('          <keysig>0</keysig>')
    body.append('          </StaffType>')
    body.append('        <defaultClef>PERC</defaultClef>')
    body.append('        </Staff>')
    body.append('      <Instrument id="drum-kit-5">')
    body.append('        <trackName>Drumset</trackName>')
    body.append('        <useDrumset>1</useDrumset>')
    body.append('        <singleNoteDynamics>0</singleNoteDynamics>')
    body.append(drum_table(drums))
    body.append('        </Instrument>')
    body.append('      </Part>')
    body.append('    <Staff id="1">')
    body.append('      <VBox>')
    body.append('        <height>10</height>')
    body.append('        <Text>')
    body.append('          <style>title</style>')
    body.append('          <text>%s</text>' % data.get('title', ''))
    body.append('          </Text>')
    # 右上署名：品牌名 + 一行小字（对应参考视频里「罗曼音乐 / 贝壳制谱」的版式）
    if data.get('brand'):
        body.append('        <Text>')
        body.append('          <style>composer</style>')
        body.append('          <text>%s</text>' % data['brand'])
        body.append('          </Text>')
    if data.get('brand2'):
        body.append('        <Text>')
        body.append('          <style>poet</style>')
        body.append('          <text>%s</text>' % data['brand2'])
        body.append('          </Text>')
    body.append('        </VBox>')
    for idx, bar in enumerate(data['bars'], 1):
        body.append('      <Measure>')
        if idx == 1:
            body.append('        <voice>')
            body.append('          <TimeSig>')
            body.append('            <sigN>4</sigN>')
            body.append('            <sigD>4</sigD>')
            body.append('            </TimeSig>')
            body.append('          </voice>')
            body.append('        <Tempo>')
            body.append('          <tempo>%.4f</tempo>' % (data.get('tempo', 105) / 60.0))
            body.append('          </Tempo>')
        if bar.get('lineBreak'):
            body.append('        <LayoutBreak>')
            body.append('          <subtype>line</subtype>')
            body.append('          </LayoutBreak>')
        for voice in (0, 1):
            evs = [dict(e, voice=voice, track=voice) for e in bar['events'] if e.get('voice', 0) == voice]
            body.append('        <voice>')
            body.extend(emit_voice(evs, total))
            body.append('        </voice>')
        body.append('        </Measure>')
    body.append('      </Staff>')
    body.append('    </Score>')
    body.append('  </museScore>')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(body) + '\n')
    print('已生成:', out_path, '小节数:', len(data['bars']))


if __name__ == '__main__':
    main()
