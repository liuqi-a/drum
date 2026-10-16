# 用途：把网易云音乐的 .ncm 加密文件还原成原始音频（mp3/flac），并打印其元数据
import base64
import json
import os
import struct
import sys

from Crypto.Cipher import AES

CORE_KEY = bytes.fromhex('687A4852416D736F356B496E62617857')  # "hzHRAmso5kInbaxW"
META_KEY = bytes.fromhex('2331346C6A6B5F215C5D2630553C2728')  # "#14ljk_!\\]&0U<'("


def build_key_box(key: bytes) -> bytearray:
    # 生成音频解密用的 key box（网易云自定义的 RC4 变体）
    box = bytearray(range(256))
    c = 0
    last = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last + key[i % len(key)]) & 0xFF
        box[i] = box[c]
        box[c] = swap
        last = c
    return box


def unpad(data: bytes) -> bytes:
    # 去掉 PKCS#7 填充
    return data[:-data[-1]]


def decrypt_ncm(path: str, outdir: str):
    # 解析 ncm 容器：头部 -> 密钥 -> 元数据 -> 封面 -> 音频
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'CTENFDAM':
        raise ValueError('不是合法的 ncm 文件')
    pos = 10
    key_len = struct.unpack('<I', data[pos:pos + 4])[0]
    pos += 4
    key_data = bytes(b ^ 0x64 for b in data[pos:pos + key_len])
    pos += key_len
    key_data = unpad(AES.new(CORE_KEY, AES.MODE_ECB).decrypt(key_data))[17:]
    key_box = build_key_box(key_data)

    meta_len = struct.unpack('<I', data[pos:pos + 4])[0]
    pos += 4
    meta = {}
    if meta_len:
        meta_data = bytes(b ^ 0x63 for b in data[pos:pos + meta_len])
        pos += meta_len
        meta_data = base64.b64decode(meta_data[22:])
        meta_data = unpad(AES.new(META_KEY, AES.MODE_ECB).decrypt(meta_data))[6:]
        meta = json.loads(meta_data.decode('utf-8'))
    pos += 9  # 跳过 CRC32(4 字节) 与间隔(5 字节)
    image_size = struct.unpack('<I', data[pos:pos + 4])[0]
    pos += 4 + image_size

    audio = bytearray(data[pos:])
    for i in range(len(audio)):
        j = i & 0xFF
        audio[i] ^= key_box[(key_box[j] + key_box[(key_box[j] + j) & 0xFF]) & 0xFF]

    fmt = (meta.get('format') or 'mp3').lower()
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f'{name}.{fmt}')
    with open(out, 'wb') as f:
        f.write(bytes(audio))
    return out, meta


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(src)
    out, meta = decrypt_ncm(src, dst)
    print('输出文件:', out)
    print('大小: %d 字节' % os.path.getsize(out))
    for k in ('musicName', 'artist', 'album', 'bitrate', 'format', 'duration'):
        if k in meta:
            print('%s: %s' % (k, meta[k]))
