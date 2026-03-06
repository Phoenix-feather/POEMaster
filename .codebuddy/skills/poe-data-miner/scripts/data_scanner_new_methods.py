#!/usr/bin/env python3
"""
新增的提取方法 - 用于data_scanner.py
将此文件中的方法添加到data_scanner.py的_extract_reservation方法之后
"""

def _extract_cast_time(self, table_content: str) -> Optional[float]:
    """提取施法时间"""
    match = re.search(r'castTime\s*=\s*([\d.]+)', table_content)
    return float(match.group(1)) if match else None

def _extract_quality_stats(self, table_content: str) -> List[List[Any]]:
    """提取品质加成"""
    result = []
    
    # 查找 qualityStats = { ... }
    quality_match = re.search(r'qualityStats\s*=\s*\{', table_content)
    if not quality_match:
        return result
    
    # 提取qualityStats表
    quality_start = quality_match.end() - 1
    quality_table = self.extract_lua_table(table_content, quality_start)
    if not quality_table:
        return result
    
    # 匹配 { "stat_name", value } 格式
    pattern = r'\{\s*"([^"]+)"\s*,\s*([\d.]+)\s*\}'
    matches = re.findall(pattern, quality_table)
    
    for name, value in matches:
        result.append([name, float(value) if '.' in value else int(value)])
    
    return result

def _extract_levels(self, table_content: str) -> Dict[str, Any]:
    """提取技能等级数据（完整）"""
    levels = {}
    
    # 查找 levels = { ... }
    levels_match = re.search(r'levels\s*=\s*\{', table_content)
    if not levels_match:
        return levels
    
    # 提取levels表
    levels_start = levels_match.end() - 1
    levels_table = self.extract_lua_table(table_content, levels_start)
    if not levels_table:
        return levels
    
    # 匹配每个等级 [n] = { ... }
    level_pattern = r'\[\s*(\d+)\s*\]\s*=\s*\{([^}]+)\}'
    level_matches = re.finditer(level_pattern, levels_table)
    
    for level_match in level_matches:
        level_num = level_match.group(1)
        level_content = level_match.group(2)
        
        level_data = {}
        
        # 提取 levelRequirement
        req_match = re.search(r'levelRequirement\s*=\s*(\d+)', level_content)
        if req_match:
            level_data['levelRequirement'] = int(req_match.group(1))
        
        # 提取 cost = { Mana = X, Spirit = Y }
        cost = {}
        mana_match = re.search(r'cost\s*=\s*\{\s*Mana\s*=\s*(\d+)', level_content)
        if mana_match:
            cost['Mana'] = int(mana_match.group(1))
        
        spirit_match = re.search(r'spiritReservationFlat\s*=\s*(\d+)', level_content)
        if spirit_match:
            cost['Spirit'] = int(spirit_match.group(1))
        
        if cost:
            level_data['cost'] = cost
        
        # 提取 cooldown
        cooldown_match = re.search(r'cooldown\s*=\s*([\d.]+)', level_content)
        if cooldown_match:
            level_data['cooldown'] = float(cooldown_match.group(1))
        
        # 提取 critChance
        crit_match = re.search(r'critChance\s*=\s*(\d+)', level_content)
        if crit_match:
            level_data['critChance'] = int(crit_match.group(1))
        
        # 提取 damageEffectiveness
        dmg_eff_match = re.search(r'damageEffectiveness\s*=\s*([\d.]+)', level_content)
        if dmg_eff_match:
            level_data['damageEffectiveness'] = float(dmg_eff_match.group(1))
        
        # 提取 spiritReservationFlat
        spirit_match = re.search(r'spiritReservationFlat\s*=\s*(\d+)', level_content)
        if spirit_match:
            level_data['spiritReservationFlat'] = int(spirit_match.group(1))
        
        if level_data:
            levels[level_num] = level_data
    
    return levels

def _extract_support_flag(self, table_content: str) -> bool:
    """提取是否辅助宝石标志"""
    match = re.search(r'support\s*=\s*true', table_content)
    return bool(match)

def _extract_require_skill_types(self, table_content: str) -> List[str]:
    """提取需求技能类型"""
    types = []
    
    # 查找 requireSkillTypes = { ... }
    match = re.search(r'requireSkillTypes\s*=\s*\{([^}]+)\}', table_content)
    if match:
        content = match.group(1)
        # 匹配 SkillType.XXX 或 "XXX"
        type_pattern = r'SkillType\.(\w+)|"(\w+)"'
        type_matches = re.findall(type_pattern, content)
        
        for type_tuple in type_matches:
            # type_tuple可能是 (xxx, '') 或 ('', xxx)
            type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
            if type_name:
                types.append(type_name)
    
    return types

def _extract_add_skill_types(self, table_content: str) -> List[str]:
    """提取添加技能类型"""
    types = []
    
    match = re.search(r'addSkillTypes\s*=\s*\{([^}]+)\}', table_content)
    if match:
        content = match.group(1)
        type_pattern = r'SkillType\.(\w+)|"(\w+)"'
        type_matches = re.findall(type_pattern, content)
        
        for type_tuple in type_matches:
            type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
            if type_name:
                types.append(type_name)
    
    return types

def _extract_exclude_skill_types(self, table_content: str) -> List[str]:
    """提取排除技能类型"""
    types = []
    
    match = re.search(r'excludeSkillTypes\s*=\s*\{([^}]+)\}', table_content)
    if match:
        content = match.group(1)
        type_pattern = r'SkillType\.(\w+)|"(\w+)"'
        type_matches = re.findall(type_pattern, content)
        
        for type_tuple in type_matches:
            type_name = type_tuple[0] if type_tuple[0] else type_tuple[1]
            if type_name:
                types.append(type_name)
    
    return types

def _extract_is_trigger(self, table_content: str) -> bool:
    """提取是否触发器标志"""
    match = re.search(r'isTrigger\s*=\s*true', table_content)
    return bool(match)

def _extract_hidden(self, table_content: str) -> bool:
    """提取是否隐藏标志"""
    match = re.search(r'hidden\s*=\s*true', table_content)
    return bool(match)
