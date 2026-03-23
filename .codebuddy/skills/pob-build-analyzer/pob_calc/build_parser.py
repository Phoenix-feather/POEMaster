#!/usr/bin/env python3
"""
POB 构筑 XML 解析器。

职责：
  - parse_build_xml: XML 文件/文本 → BuildInfo dict
  - BuildInfo 包含 level, className, skills, items, tree, config 等全部构筑数据
"""
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_build_xml(source) -> dict:
    """解析 POB 构筑 XML，提取关键信息。

    Args:
        source: XML 文件路径 (str/Path) 或 XML 文本 (str，以 '<' 开头)

    Returns:
        BuildInfo dict，包含：
          level, className, ascendClassName, mainSocketGroup,
          playerStats, treeURL, treeVersion, classId, classInternalId,
          ascendClassId, weaponSets, attrOverride, sockets,
          skillGroups, activeSkillSet, defaultGemLevel, defaultGemQuality,
          items, itemSlots, activeItemSetId, useSecondWeaponSet,
          configInputs
    """
    if isinstance(source, (str, Path)):
        source_str = str(source)
        if source_str.lstrip().startswith('<'):
            root = ET.fromstring(source_str)
        else:
            tree = ET.parse(source_str)
            root = tree.getroot()
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")

    build_info = {}

    for child in root:
        tag = child.tag

        if tag == "Build":
            build_info['level'] = int(child.get('level', '1'))
            build_info['className'] = child.get('className', '')
            build_info['ascendClassName'] = child.get('ascendClassName', '')
            build_info['mainSocketGroup'] = int(child.get('mainSocketGroup', '1'))

            build_info['playerStats'] = {}
            for ps in child:
                if ps.tag == 'PlayerStat':
                    build_info['playerStats'][ps.get('stat', '')] = ps.get('value', '0')

        elif tag == "Tree":
            for spec in child:
                if spec.tag == "Spec":
                    build_info['treeVersion'] = spec.get('treeVersion', '0_4')
                    build_info['classId'] = spec.get('classId', '')
                    build_info['classInternalId'] = spec.get('classInternalId', '')
                    build_info['ascendClassId'] = spec.get('ascendClassId', '0')
                    build_info['weaponSets'] = {}
                    build_info['attrOverride'] = {'str': [], 'dex': [], 'int': []}

                    for sub in spec:
                        if sub.tag == "URL":
                            build_info['treeURL'] = (sub.text or "").strip()
                        elif sub.tag == "Sockets":
                            build_info['sockets'] = []
                            for socket in sub:
                                build_info['sockets'].append(dict(socket.attrib))
                        elif sub.tag.startswith("WeaponSet"):
                            ws_num = int(sub.tag.replace("WeaponSet", ""))
                            nodes_str = sub.get('nodes', '')
                            if nodes_str:
                                for nid in nodes_str.split(','):
                                    nid = nid.strip()
                                    if nid:
                                        build_info['weaponSets'][int(nid)] = ws_num
                        elif sub.tag == "Overrides":
                            for override_child in sub:
                                if override_child.tag == "AttributeOverride":
                                    for attr_key, xml_key in [('str', 'strNodes'), ('dex', 'dexNodes'), ('int', 'intNodes')]:
                                        nodes_str = override_child.get(xml_key, '')
                                        if nodes_str:
                                            for nid in nodes_str.split(','):
                                                nid = nid.strip()
                                                if nid:
                                                    build_info['attrOverride'][attr_key].append(int(nid))

        elif tag == "Skills":
            build_info['skillGroups'] = []
            build_info['activeSkillSet'] = child.get('activeSkillSet', '1')
            build_info['defaultGemLevel'] = child.get('defaultGemLevel', 'normalMaximum')
            build_info['defaultGemQuality'] = int(child.get('defaultGemQuality', '0'))

            active_set_id = build_info['activeSkillSet']
            target = child
            for ss in child:
                if ss.tag == "SkillSet" and ss.get('id', '') == active_set_id:
                    target = ss
                    break

            for skill in target:
                if skill.tag == "Skill":
                    group = dict(skill.attrib)
                    group['gems'] = []
                    for gem in skill:
                        if gem.tag == "Gem":
                            group['gems'].append(dict(gem.attrib))
                    build_info['skillGroups'].append(group)

        elif tag == "Items":
            build_info['items'] = []
            build_info['itemSlots'] = {}
            build_info['activeItemSetId'] = child.get('activeItemSet', '1')
            build_info['useSecondWeaponSet'] = child.get('useSecondWeaponSet', 'false') == 'true'

            for item in child:
                if item.tag == "Item":
                    build_info['items'].append({
                        'id': int(item.get('id', '0')),
                        'text': (item.text or "").strip(),
                    })
                elif item.tag == "ItemSet":
                    if item.get('id', '') == build_info['activeItemSetId']:
                        for slot in item:
                            if slot.tag == "Slot":
                                name = slot.get('name', '')
                                item_id = int(slot.get('itemId', '0'))
                                active = slot.get('active', 'false') == 'true'
                                if name and item_id > 0:
                                    build_info['itemSlots'][name] = {
                                        'itemId': item_id,
                                        'active': active,
                                    }

        elif tag == "Config":
            build_info['config'] = {}
            build_info['configInputs'] = []
            for cs in child:
                if cs.tag == "ConfigSet":
                    for inp in cs:
                        if inp.tag in ("Input", "Placeholder"):
                            build_info['configInputs'].append({
                                'type': inp.tag,
                                'name': inp.get('name', ''),
                                'string': inp.get('string', None),
                                'number': inp.get('number', None),
                                'boolean': inp.get('boolean', None),
                            })

    return build_info
