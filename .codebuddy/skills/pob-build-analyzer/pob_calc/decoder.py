#!/usr/bin/env python3
"""
POB 分享码与天赋树 URL 编解码器。

职责：
  - decode_share_code: POB 分享码 → XML 文本
  - decode_tree_url:   天赋树 URL → (节点 ID 列表, mastery 选择)
"""
import base64
import zlib


def decode_share_code(code: str) -> str:
    """POB 分享码解码: URL-safe-Base64(Deflate(XML)) → XML

    POB 编码流程: XML → Deflate(zlib) → Base64 → URL-safe(+→-, /→_)
    解码是反向: URL-safe 还原 → Base64 解码 → Inflate(zlib) → XML
    """
    # 清理输入
    code = code.strip().replace('\n', '').replace('\r', '').replace(' ', '')

    # URL-safe 还原标准 Base64
    b64 = code.replace("-", "+").replace("_", "/")

    # 添加 padding
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding

    # Base64 解码
    raw = base64.b64decode(b64)

    # zlib 解压 — 自动检测格式
    errors = []
    for name, wbits in [
        ("zlib header", None),
        ("raw deflate", -zlib.MAX_WBITS),
        ("auto-detect", 32 + zlib.MAX_WBITS),
        ("gzip", zlib.MAX_WBITS | 16),
    ]:
        try:
            if wbits is None:
                xml_bytes = zlib.decompress(raw)
            else:
                xml_bytes = zlib.decompress(raw, wbits)
            return xml_bytes.decode('utf-8', errors='replace')
        except zlib.error as e:
            errors.append(f"{name}: {e}")

    raise RuntimeError(
        f"所有解压方式均失败 (raw {len(raw)} bytes, header={raw[:2].hex()}):\n"
        + "\n".join(f"  - {e}" for e in errors)
    )


def decode_tree_url(tree_url: str) -> tuple[list[int], dict[int, int]]:
    """Python 解码天赋树 URL，提取已分配的节点 ID 和 mastery 选择。

    Returns:
        (node_ids, mastery_selections)
        - node_ids: 已分配节点 ID 列表
        - mastery_selections: {node_id: effect_id} mastery 选择映射
    """
    if not tree_url:
        return [], {}

    # 提取编码部分
    encoded = tree_url.rsplit('/', 1)[-1]
    encoded = encoded.replace('-', '+').replace('_', '/')
    padding = 4 - len(encoded) % 4
    if padding < 4:
        encoded += '=' * padding

    b = base64.b64decode(encoded)
    if len(b) < 6:
        return [], {}

    ver = b[0] * 16777216 + b[1] * 65536 + b[2] * 256 + b[3]

    nodes_start = 7 if ver >= 4 else 6
    if ver >= 5:
        node_count = b[6]
        nodes_end = nodes_start + node_count * 2
    else:
        nodes_end = len(b)

    # 提取节点 ID (big-endian uint16)
    node_ids = []
    for i in range(nodes_start, nodes_end, 2):
        if i + 1 < len(b):
            node_id = b[i] * 256 + b[i + 1]
            node_ids.append(node_id)

    # Mastery selections (ver >= 5)
    mastery_selections = {}
    if ver >= 5 and nodes_end < len(b):
        cluster_start = nodes_end
        cluster_count = b[cluster_start]
        cluster_end = cluster_start + 1 + cluster_count * 2

        # cluster 节点
        for i in range(cluster_start + 1, cluster_end, 2):
            if i + 1 < len(b):
                cid = b[i] * 256 + b[i + 1]
                node_ids.append(cid + 65536)

        if ver >= 6 and cluster_end < len(b):
            mastery_start = cluster_end
            mastery_count = b[mastery_start]
            for i in range(mastery_start + 1, mastery_start + 1 + mastery_count * 4, 4):
                if i + 3 < len(b):
                    effect_id = b[i] * 256 + b[i + 1]
                    node_id = b[i + 2] * 256 + b[i + 3]
                    mastery_selections[node_id] = effect_id

    return node_ids, mastery_selections
