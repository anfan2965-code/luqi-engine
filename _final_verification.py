#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API文档→代码 双向一致性最终验证 (Final Verification)
V1.3.0.12-Beta 发布前关键检查
"""

import os
import re
import sys
import ast
import importlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass, field

RELEASE_DIR = Path(r"G:\AAA研究\02 角色与世界的理解\LuqiAI-Engine-Release")
DOCS_DIR = RELEASE_DIR / "docs" / "api"
CODE_DIR = RELEASE_DIR / "luqi_engine"

@dataclass
class DocSymbol:
    """文档中记录的符号"""
    name: str
    symbol_type: str  # class / function / method / constant
    doc_file: str
    line_num: int = 0
    params: List[str] = field(default_factory=list)
    found_in_code: bool = False
    code_location: str = ""
    mismatch_details: str = ""

@dataclass
class CodeSymbol:
    """代码中的实际符号"""
    name: str
    symbol_type: str
    module_path: str
    line_num: int = 0
    params: List[str] = field(default_factory=list)
    documented: bool = False

@dataclass
class VerificationResult:
    """单个文档的验证结果"""
    doc_file: str
    total_symbols: int = 0
    matched_symbols: int = 0
    missing_in_code: List[DocSymbol] = field(default_factory=list)
    undocumented_code: List[CodeSymbol] = field(default_factory=list)
    signature_mismatches: List[Tuple[DocSymbol, CodeSymbol]] = field(default_factory=list)
    status: str = "PENDING"  # PASS / WARN / FAIL

class APIVerifier:
    def __init__(self):
        self.doc_symbols: Dict[str, List[DocSymbol]] = {}
        self.code_symbols: Dict[str, List[CodeSymbol]] = {}
        self.results: Dict[str, VerificationResult] = {}
        self.all_errors: List[str] = []
        self.all_warnings: List[str] = []

    # ==================== 文档解析 ====================
    def parse_markdown_doc(self, doc_path: Path) -> List[DocSymbol]:
        """从Markdown文档提取所有记录的符号"""
        symbols = []
        content = doc_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # 匹配类定义: class ClassName:
            if re.match(r'^class\s+\w+.*:', line_stripped) or \
               re.match(r'^```python\s*$', line_stripped):
                # 提取类名
                class_match = re.search(r'class\s+(\w+)', line_stripped)
                if class_match:
                    symbols.append(DocSymbol(
                        name=class_match.group(1),
                        symbol_type='class',
                        doc_file=doc_path.name,
                        line_num=i
                    ))

            # 匹配函数/方法定义: def method_name(self, ...):
            func_match = re.match(r'^\s*def\s+(\w+)\s*\(', line_stripped)
            if func_match:
                params_match = re.search(r'\((.*?)\)', line_stripped)
                params = [p.strip() for p in params_match.group(1).split(',')] if params_match else []
                symbols.append(DocSymbol(
                    name=func_match.group(1),
                    symbol_type='method' if 'self' in params else 'function',
                    doc_file=doc_path.name,
                    line_num=i,
                    params=params
                ))

            # 匹配常量: CONSTANT_NAME = 或 CONSTANT_NAME:
            const_match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*[=:]', line_stripped)
            if const_match:
                symbols.append(DocSymbol(
                    name=const_match.group(1),
                    symbol_type='constant',
                    doc_file=doc_path.name,
                    line_num=i
                ))

        return symbols

    # ==================== 代码解析 ====================
    def parse_python_module(self, py_path: Path) -> List[CodeSymbol]:
        """从Python源码提取所有公开符号"""
        symbols = []
        try:
            content = py_path.read_text(encoding='utf-8')
            tree = ast.parse(content, filename=str(py_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 只记录非内部类（不以_开头）
                    if not node.name.startswith('_'):
                        symbols.append(CodeSymbol(
                            name=node.name,
                            symbol_type='class',
                            module_path=str(py_path.relative_to(CODE_DIR)),
                            line_num=node.lineno
                        ))
                        # 提取方法
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                                params = [arg.arg for arg in item.args.args]
                                symbols.append(CodeSymbol(
                                    name=f"{node.name}.{item.name}",
                                    symbol_type='method',
                                    module_path=str(py_path.relative_to(CODE_DIR)),
                                    line_num=item.lineno,
                                    params=params
                                ))

                elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                    params = [arg.arg for arg in node.args.args]
                    symbols.append(CodeSymbol(
                        name=node.name,
                        symbol_type='function',
                        module_path=str(py_path.relative_to(CODE_DIR)),
                        line_num=node.lineno,
                        params=params
                    ))

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith('_'):
                            symbols.append(CodeSymbol(
                                name=target.id,
                                symbol_type='constant',
                                module_path=str(py_path.relative_to(CODE_DIR)),
                                line_num=node.lineno
                            ))

        except SyntaxError as e:
            self.all_warnings.append(f"语法错误 {py_path}: {e}")
        except Exception as e:
            self.all_warnings.append(f"解析失败 {py_path}: {e}")

        return symbols

    # ==================== 核心验证逻辑 ====================
    def verify_document(self, doc_file: str) -> VerificationResult:
        """验证单个文档与代码的一致性"""
        result = VerificationResult(doc_file=doc_file)
        doc_path = DOCS_DIR / doc_file

        if not doc_path.exists():
            result.status = "FAIL"
            self.all_errors.append(f"文档不存在: {doc_file}")
            return result

        # 解析文档
        doc_symbols = self.parse_markdown_doc(doc_path)
        self.doc_symbols[doc_file] = doc_symbols
        result.total_symbols = len(doc_symbols)

        # 确定对应的代码模块
        module_name = doc_file.replace('.md', '')
        code_modules = self._find_code_modules(module_name)

        # 收集代码符号
        all_code_symbols = []
        for mod_path in code_modules:
            code_syms = self.parse_python_module(mod_path)
            all_code_symbols.extend(code_syms)
        self.code_symbols[module_name] = all_code_symbols

        # 双向比对
        code_symbol_names = {s.name.lower(): s for s in all_code_symbols}

        for doc_sym in doc_symbols:
            sym_key = doc_sym.name.lower()

            if sym_key in code_symbol_names:
                code_sym = code_symbol_names[sym_key]
                doc_sym.found_in_code = True
                doc_sym.code_location = f"{code_sym.module_path}:{code_sym.line_num}"
                code_sym.documented = True
                result.matched_symbols += 1

                # 参数签名比对（仅对方法/函数）
                if doc_sym.symbol_type in ('method', 'function') and doc_sym.params and code_sym.params:
                    if not self._params_match(doc_sym.params, code_sym.params):
                        result.signature_mismatches.append((doc_sym, code_sym))
                        self.all_warnings.append(
                            f"[{doc_file}] {doc_sym.name} 参数不匹配: "
                            f"文档={doc_sym.params} vs 代码={code_sym.params}"
                        )
            else:
                result.missing_in_code.append(doc_sym)
                self.all_warnings.append(
                    f"[{doc_file}] 文档中记录但代码中未找到: {doc_sym.name} ({doc_sym.symbol_type})"
                )

        # 检查未文档化的代码符号
        doc_symbol_names_lower = {s.name.lower() for s in doc_symbols}
        for code_sym in all_code_symbols:
            if code_sym.name.lower() not in doc_symbol_names_lower and code_sym.symbol_type == 'class':
                result.undocumented_code.append(code_sym)

        # 判定状态
        missing_count = len(result.missing_in_code)
        mismatch_count = len(result.signature_mismatches)

        if missing_count > 5 or mismatch_count > 3:
            result.status = "FAIL"
        elif missing_count > 0 or mismatch_count > 0:
            result.status = "WARN"
        else:
            result.status = "PASS"

        return result

    def _find_code_modules(self, doc_module: str) -> List[Path]:
        """根据文档名称查找对应代码模块"""
        module_mapping = {
            'character': ['character'],
            'config': ['core'],
            'core': ['core'],
            'engine': ['.'],  # engine.py在根目录
            'game_theory': ['game_theory'],
            'interaction': ['interaction'],
            'llm': ['llm'],
            'local_model': ['local_model'],
            'memory': ['memory'],
            'motivation': ['motivation'],
            'narrative': ['narrative'],
            'orchestration': ['orchestration'],
            'performance': ['performance'],
            'scene': ['scene'],
            'scheduler': ['scheduler'],
            'training': ['training'],
            'voice': ['voice'],
            'worldview': ['worldview'],
            'agents': ['agents'],
            'AGENTS': ['agents'],
        }

        dirs = module_mapping.get(doc_module, [doc_module])
        modules = []

        for d in dirs:
            if d == '.':
                modules.append(CODE_DIR / 'engine.py')
            else:
                target_dir = CODE_DIR / d
                if target_dir.exists():
                    modules.extend(target_dir.rglob('*.py'))

        return modules

    def _params_match(self, doc_params: List[str], code_params: List[str]) -> bool:
        """简化参数匹配（忽略self, **kwargs等）"""
        doc_clean = [p for p in doc_params if p not in ('self', 'cls', '*args', '**kwargs')]
        code_clean = [p for p in code_params if p not in ('self', 'cls', '*args', '**kwargs')]
        return set(doc_clean) == set(code_clean)

    # ==================== 执行验证 ====================
    def run_full_verification(self) -> Dict[str, VerificationResult]:
        """执行完整的双向验证"""
        print("=" * 80)
        print("LuqiAI Engine V1.3.0.12-Beta - API文档最终一致性验证")
        print("=" * 80)
        print()

        # 获取所有文档文件
        doc_files = sorted([f for f in DOCS_DIR.iterdir() if f.suffix == '.md'])

        total_pass = 0
        total_warn = 0
        total_fail = 0

        for doc_file in doc_files:
            result = self.verify_document(doc_file.name)
            self.results[doc_file.name] = result

            if result.status == "PASS":
                total_pass += 1
            elif result.status == "WARN":
                total_warn += 1
            else:
                total_fail += 1

            # 输出简要结果
            status_icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[result.status]
            print(f"{status_icon} {doc_file.name:<25} | "
                  f"符号:{result.total_symbols:>3} | "
                  f"匹配:{result.matched_symbols:>3} | "
                  f"缺失:{len(result.missing_in_code):>2} | "
                  f"签名问题:{len(result.signature_mismatches):>2}")

        # 汇总报告
        print("\n" + "=" * 80)
        print("验证汇总")
        print("=" * 80)
        print(f"总文档数: {len(doc_files)}")
        print(f"通过 (PASS): {total_pass}")
        print(f"警告 (WARN): {total_warn}")
        print(f"失败 (FAIL): {total_fail}")
        print(f"警告总数: {len(self.all_warnings)}")
        print(f"错误总数: {len(self.all_errors)}")

        return self.results

    def generate_detailed_report(self) -> str:
        """生成详细的验证报告"""
        report_lines = [
            "\n" + "=" * 80,
            "详细验证报告",
            "=" * 80,
        ]

        for doc_file, result in sorted(self.results.items()):
            report_lines.append(f"\n{'─' * 60}")
            report_lines.append(f"📄 {doc_file} [{result.status}]")
            report_lines.append(f"   总符号: {result.total_symbols}, 匹配: {result.matched_symbols}")

            if result.missing_in_code:
                report_lines.append(f"\n   ⚠️  文档中记录但代码中未找到 ({len(result.missing_in_code)}项):")
                for sym in result.missing_in_code[:10]:  # 最多显示10个
                    report_lines.append(f"      - {sym.name} ({sym.symbol_type}) L{sym.line_num}")
                if len(result.missing_in_code) > 10:
                    report_lines.append(f"      ... 还有 {len(result.missing_in_code)-10} 项")

            if result.signature_mismatches:
                report_lines.append(f"\n   🔧 签名不匹配 ({len(result.signature_mismatches)}项):")
                for doc_sym, code_sym in result.signature_mismatches[:5]:
                    report_lines.append(f"      - {doc_sym.name}: 文档参数={doc_sym.params} vs 代码参数={code_sym.params}")

            if result.undocumented_code:
                report_lines.append(f"\n   📝 未文档化的公共类 ({len(result.undocumented_code)}项):")
                for sym in result.undocumented_code[:8]:
                    report_lines.append(f"      - {sym.name} @ {sym.module_path}:{sym.line_num}")

        # 错误和警告汇总
        if self.all_errors:
            report_lines.append(f"\n\n❌ 严重错误 ({len(self.all_errors)}项):")
            for err in self.all_errors[:10]:
                report_lines.append(f"   • {err}")

        if self.all_warnings:
            report_lines.append(f"\n⚠️  所有警告 ({len(self.all_warnings)}项):")
            for warn in self.all_warnings[:20]:
                report_lines.append(f"   • {warn}")

        report_lines.append("\n" + "=" * 80)
        return "\n".join(report_lines)


def main():
    verifier = APIVerifier()
    results = verifier.run_full_verification()
    detailed_report = verifier.generate_detailed_report()
    print(detailed_report)

    # 保存完整报告
    report_path = RELEASE_DIR / "_final_verification_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(detailed_report)
    print(f"\n📊 完整报告已保存至: {report_path}")

    # 返回状态码
    fail_count = sum(1 for r in results.values() if r.status == "FAIL")
    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
