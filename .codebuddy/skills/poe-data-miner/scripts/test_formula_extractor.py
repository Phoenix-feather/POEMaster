#!/usr/bin/env python3
"""
测试公式提取器

使用已有的calculation_module实体测试特征提取功能
"""
import sys
import sqlite3
import json
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from formula_extractor import FormulaExtractor


def test_formula_extractor_with_existing_data():
    """使用已有的calculation_module数据测试"""
    print("=" * 70)
    print("测试公式提取器")
    print("=" * 70)
    
    # 使用已有的知识库
    kb_path = Path("g:/POEMaster/.codebuddy/skills/poe-data-miner/knowledge_base")
    entities_db = kb_path / "entities.db"
    test_db = kb_path / "test_formulas.db"
    
    # 1. 测试加载官方stat ID
    print("\n1. 测试加载官方stat ID...")
    extractor = FormulaExtractor(
        pob_path="dummy_path",  # 暂时不需要POB路径
        db_path=str(test_db),
        entities_db_path=str(entities_db)
    )
    
    print(f"   官方stat ID数量: {len(extractor.official_stats)}")
    print(f"   示例: {list(extractor.official_stats)[:10]}")
    
    # 2. 测试特征提取
    print("\n2. 测试特征提取...")
    
    # 从已有的calculation_module提取代码进行测试
    conn = sqlite3.connect(str(entities_db))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, data_json 
        FROM entities 
        WHERE type = 'calculation_module'
        LIMIT 3
    """)
    
    test_cases = []
    for row in cursor.fetchall():
        data = json.loads(row[2]) if row[2] else {}
        body = data.get('body', '')
        
        if body:
            features = extractor._extract_features(body)
            test_cases.append({
                'name': row[1],
                'features': features
            })
    
    conn.close()
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n   [{i}] {case['name']}")
        print(f"       精确stat: {case['features'].exact_stats[:5]}")
        print(f"       模糊stat: {case['features'].fuzzy_stats[:5]}")
        print(f"       标签: {case['features'].inferred_tags}")
        print(f"       调用: {case['features'].calls[:5]}")
    
    # 3. 测试stat名称提取
    print("\n3. 测试stat名称提取...")
    test_code = """
    function test()
        local energy = activeSkill.skillData.triggerEnergy
        local speed = skillModList:Sum("INC", cfg, "Speed")
        local cooldown = skillModList:More(cfg, "CooldownRecovery")
        return energy + speed
    end
    """
    
    stats = extractor._extract_stat_names(test_code)
    print(f"   提取到的stat: {stats}")
    
    # 4. 测试标签推断
    print("\n4. 测试标签推断...")
    test_code2 = """
    if activeSkill.triggerSource then
        return activeSkill.triggerSource.energy
    end
    """
    
    tags = extractor._infer_tags(test_code2)
    print(f"   推断的标签: {tags}")
    
    # 5. 测试数据库初始化
    print("\n5. 测试数据库初始化...")
    if test_db.exists():
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   创建的表: {tables}")
        
        # 检查索引是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"   创建的索引: {indexes[:10]}")
        
        conn.close()
    
    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)


def test_with_sample_lua():
    """使用示例Lua代码测试"""
    print("\n" + "=" * 70)
    print("测试Lua函数解析")
    print("=" * 70)
    
    sample_lua = """
    -- 标准函数定义
    function calcTriggerEnergy(activeSkill)
        local baseEnergy = activeSkill.skillData.triggerEnergy or 0
        
        if activeSkill.triggerSource then
            if activeSkill.triggerSource.type == "corpse_explosion" then
                return activeSkill.triggerSource.energy
            end
            return math.min(baseEnergy, activeSkill.triggerSource.energy)
        end
        
        return baseEnergy
    end
    
    -- local函数定义
    local function calcCooldown(activeSkill)
        local baseCooldown = activeSkill.skillData.cooldown or 0
        local energy = calcTriggerEnergy(activeSkill)
        
        if energy > 0 then
            return baseCooldown * (1 - energy / 100)
        end
        
        return baseCooldown
    end
    
    -- 表方法定义
    calcs.createActiveSkill = function(env, actor)
        local skillFlags = actor.mainSkill.activeEffect.statSetCalcs.skillFlags
        return skillFlags
    end
    """
    
    # 创建临时提取器
    extractor = FormulaExtractor(
        pob_path="dummy_path",
        db_path=":memory:",  # 内存数据库
        entities_db_path=None
    )
    
    # 解析函数
    functions = extractor._parse_lua_functions_from_string(sample_lua)
    
    print(f"\n解析到 {len(functions)} 个函数:")
    for i, func in enumerate(functions, 1):
        print(f"\n[{i}] {func.name}")
        print(f"    参数: {func.params}")
        print(f"    行号: {func.start_line}-{func.end_line}")
        print(f"    local: {func.is_local}")
        print(f"    代码长度: {len(func.body)} 字符")
        
        # 提取特征
        features = extractor._extract_features(func.body)
        print(f"    精确stat: {features.exact_stats[:3]}")
        print(f"    模糊stat: {features.fuzzy_stats[:3]}")
        print(f"    标签: {features.inferred_tags}")
        print(f"    调用: {features.calls[:3]}")


if __name__ == "__main__":
    test_formula_extractor_with_existing_data()
    test_with_sample_lua()
