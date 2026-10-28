# -*- coding: utf-8 -*-
"""与前端 licH() 完全一致的散列实现（构建端签发授权码用）。

注意：前端用 Math.imul 做 32 位乘法，Python 这边用 & 0xFFFFFFFF 取模，
两边在模 2^32 意义下等价，因此结果可交叉验证。
"""
M32 = 0xFFFFFFFF


def _one(s, seed):
    h = seed & M32
    for ch in s:
        h ^= ord(ch)
        h &= M32
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) & M32
    h ^= (h >> 16)
    h &= M32
    h = (h * 2246822507) & M32
    h ^= (h >> 13)
    h &= M32
    h = (h * 3266489909) & M32
    h ^= (h >> 16)
    h &= M32
    return ("%08x" % h)


def licH(s):
    return _one(s, 0x811C9DC5) + _one(s, 0x01000193) + _one("x" + s, 0x9E3779B9)
