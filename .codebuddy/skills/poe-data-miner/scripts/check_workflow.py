#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流程检查器 - 确保强制规则被执行

用法：
  在开始处理问题前运行此脚本，检查是否遵循了强制规则
"""
import sys
from pathlib import Path

class WorkflowChecker:
    """工作流程检查器"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def check_query_strategy(self, question):
        """检查是否使用了查询策略"""
        print("\n【检查1】查询策略")
        print("-" * 60)
        print("是否运行了 query_router.py？")
        print(f"  问题: {question}")
        print("\n必须执行:")
        print(f"  python scripts/query_router.py \"{question}\"")
        print("\n输入结果类型 (attribute/relation/bypass/comprehensive): ", end="")

        result_type = input().strip()
        if result_type not in ['attribute', 'relation', 'bypass', 'comprehensive']:
            self.errors.append("未正确使用query_router")
            print("❌ 错误：必须先运行query_router")
            return False
        else:
            print(f"✅ 查询类型: {result_type}")
            return True

    def check_verification_workflow(self, has_bypass=False):
        """检查验证流程"""
        print("\n【检查2】验证流程")
        print("-" * 60)

        if has_bypass:
            print("发现潜在绕过/新知识，必须执行验证流程：")
            print("  1. 代码验证（搜索POB原始代码）")
            print("  2. 更新知识状态")
            print("  3. 保存验证结果到 knowledge_base/verification_records.yaml")
            print("\n是否已执行验证？(y/n): ", end="")

            verified = input().strip().lower()
            if verified != 'y':
                self.errors.append("发现潜在绕过但未验证")
                print("❌ 错误：必须验证潜在机制")
                return False
            else:
                print("✅ 验证流程已执行")
                return True
        else:
            print("不涉及绕过/新知识，无需验证")
            return True

    def check_temp_file_policy(self, will_create_file=False, file_desc=""):
        """检查临时文件策略"""
        print("\n【检查3】临时文件管理")
        print("-" * 60)

        if will_create_file:
            print(f"计划创建文件: {file_desc}")
            print("\n必须检查:")
            print("  [ ] 这个脚本会长期使用吗？")
            print("  [ ] 能否用execute_command直接执行？")
            print("  [ ] 执行后是否需要删除？")
            print("  [ ] 结果应该保存在哪里？")
            print("\n选择: (1)长期保留 (2)执行后删除 (3)改用execute_command: ", end="")

            choice = input().strip()
            if choice == '1':
                print("✅ 长期工具，创建并保留")
                return True
            elif choice == '2':
                print("✅ 临时脚本，执行后删除")
                print("  结果必须保存到: knowledge_base/")
                return True
            elif choice == '3':
                print("✅ 改用execute_command")
                print("  不创建文件，直接执行")
                return True
            else:
                self.errors.append("未正确选择文件处理方式")
                print("❌ 错误：必须选择文件处理方式")
                return False
        else:
            print("不创建新文件，无需检查")
            return True

    def check_knowledge_state(self, has_new_knowledge=False):
        """检查知识状态管理"""
        print("\n【检查4】知识状态管理")
        print("-" * 60)

        if has_new_knowledge:
            print("发现新知识，必须管理状态：")
            print("  状态: HYPOTHESIS → PENDING → VERIFIED/REJECTED")
            print("  保存: knowledge_base/verification_records.yaml")
            print("\n当前状态 (hypothesis/pending/verified/rejected): ", end="")

            state = input().strip()
            if state not in ['hypothesis', 'pending', 'verified', 'rejected']:
                self.errors.append("知识状态未正确设置")
                print("❌ 错误：必须设置知识状态")
                return False
            else:
                print(f"✅ 知识状态: {state}")
                return True
        else:
            print("不涉及新知识，无需管理状态")
            return True

    def print_summary(self):
        """打印检查摘要"""
        print("\n" + "=" * 60)
        print("工作流程检查摘要")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ 发现 {len(self.errors)} 个错误：")
            for error in self.errors:
                print(f"  - {error}")
            print("\n必须修正错误后才能继续！")
            return False
        elif self.warnings:
            print(f"\n⚠️ 发现 {len(self.warnings)} 个警告：")
            for warning in self.warnings:
                print(f"  - {warning}")
            print("\n建议修正警告后继续")
            return True
        else:
            print("\n✅ 所有检查通过")
            print("可以继续处理问题")
            return True


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python check_workflow.py <用户问题>")
        print("\n示例:")
        print("  python check_workflow.py \"如何绕过Triggerable限制？\"")
        return

    question = " ".join(sys.argv[1:])

    print("=" * 60)
    print("工作流程检查器")
    print("=" * 60)
    print(f"\n用户问题: {question}")

    checker = WorkflowChecker()

    # 检查1：查询策略
    checker.check_query_strategy(question)

    # 询问是否发现绕过/新知识
    print("\n是否发现潜在绕过或新知识？(y/n): ", end="")
    has_bypass = input().strip().lower() == 'y'

    # 检查2：验证流程
    checker.check_verification_workflow(has_bypass)

    # 询问是否计划创建文件
    print("\n是否计划创建新的脚本文件？(y/n): ", end="")
    will_create = input().strip().lower() == 'y'

    if will_create:
        print("文件描述: ", end="")
        file_desc = input().strip()
        checker.check_temp_file_policy(will_create, file_desc)
    else:
        checker.check_temp_file_policy(False)

    # 检查4：知识状态
    checker.check_knowledge_state(has_bypass)

    # 打印摘要
    success = checker.print_summary()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
