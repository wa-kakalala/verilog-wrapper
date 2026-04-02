import sys
import os
from optparse import OptionParser

# the next line can be removed after installation
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyverilog
from pyverilog.vparser.parser import parse

import json

class NodeVisitor:
    def visit(self, node):
        if node is None: return
        if isinstance(node, (tuple, list)):
            for n in node: self.visit(n)
            return
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        if hasattr(node, 'children'):
            for child in node.children():
                self.visit(child)

class VerilogFormatExtractor(NodeVisitor):
    def __init__(self):
        self.module_data = {"mdl_name": "", "params": [], "in_ports": [], "out_ports": []}
        self.param_dict = {}
        self.in_paramlist = False

    def visit_ModuleDef(self, node):
        self.module_data["mdl_name"] = node.name
        self.generic_visit(node)

    def visit_Paramlist(self, node):
        self.in_paramlist = True
        self.generic_visit(node)
        self.in_paramlist = False

    def visit_Parameter(self, node):
        val_node = node.value.var if hasattr(node.value, 'var') else node.value
        val_str, is_expr = self._format_expression(val_node)
        try:
            actual_val = self._evaluate_expression(val_node)
            self.param_dict[node.name] = actual_val
        except:
            actual_val = val_str
        
        if self.in_paramlist:
            self.module_data["params"].append({
                "param_name": node.name, "param_value": actual_val, "param_is_num": 1 if isinstance(actual_val, int) else 0
            })

    def visit_Input(self, node):
        l_raw, r_raw, l_is_p, r_is_p = self._parse_width_raw(node.width)
        l_eval, r_eval = self._evaluate_width(node.width)
        self.module_data["in_ports"].append({
            "port_name": node.name, "left_raw": l_raw, "right_raw": r_raw,
            "left": l_eval, "right": r_eval, "left_is_param": l_is_p, "right_is_param": r_is_p, "_from": []
        })

    def visit_Output(self, node):
        l_raw, r_raw, l_is_p, r_is_p = self._parse_width_raw(node.width)
        l_eval, r_eval = self._evaluate_width(node.width)
        self.module_data["out_ports"].append({
            "port_name": node.name, "left_raw": l_raw, "right_raw": r_raw,
            "left": l_eval, "right": r_eval, "left_is_param": l_is_p, "right_is_param": r_is_p, "_to": []
        })

    def _parse_width_raw(self, width_node):
        if width_node is None: return "0", "0", 0, 0
        return self._format_expression(width_node.msb)[0], self._format_expression(width_node.lsb)[0], 1, 1

    def _format_expression(self, node):
        if node is None: return "", 0
        
        t = type(node).__name__
        
        if t == 'IntConst': 
            return node.value, 0
        if t == 'Identifier': 
            return node.name, 1
            
        # 恢复对数学表达式的递归拼接
        if t == 'Minus': 
            return f"{self._format_expression(node.left)[0]}-{self._format_expression(node.right)[0]}", 1
        if t == 'Plus': 
            return f"{self._format_expression(node.left)[0]}+{self._format_expression(node.right)[0]}", 1
        if t == 'Times': 
            return f"{self._format_expression(node.left)[0]}*{self._format_expression(node.right)[0]}", 1
        if t == 'Divide': 
            return f"{self._format_expression(node.left)[0]}/{self._format_expression(node.right)[0]}", 1
            
        # 其他未知的复杂类型兜底
        return f"<{t}>", 1

    def _evaluate_width(self, width_node):
        if width_node is None: return 0, 0
        return self._evaluate_expression(width_node.msb), self._evaluate_expression(width_node.lsb)

    def _evaluate_expression(self, node):
        if node is None: return 0
        t = type(node).__name__
        if t == 'IntConst': return int(node.value.split("'")[-1].replace('h',''), 16) if 'h' in node.value else int(node.value)
        if t == 'Identifier': return self.param_dict.get(node.name, 0)
        if t == 'Minus': return self._evaluate_expression(node.left) - self._evaluate_expression(node.right)
        if t == 'Plus': return self._evaluate_expression(node.left) + self._evaluate_expression(node.right)
        return 0

def main():
    INFO = "Verilog code parser"
    VERSION = pyverilog.__version__
    USAGE = "Usage: python example_parser.py file ..."

    def showVersion():
        print(INFO)
        print(VERSION)
        print(USAGE)
        sys.exit()

    optparser = OptionParser()
    optparser.add_option("-v", "--version", action="store_true", dest="showversion",
                         default=False, help="Show the version")
    optparser.add_option("-I", "--include", dest="include", action="append",
                         default=[], help="Include path")
    optparser.add_option("-D", dest="define", action="append",
                         default=[], help="Macro Definition")
    (options, args) = optparser.parse_args()

    filelist = args
    if options.showversion:
        showVersion()

    for f in filelist:
        if not os.path.exists(f):
            raise IOError("file not found: " + f)

    if len(filelist) == 0:
        showVersion()

    ast, directives = parse(filelist,
                            preprocess_include=options.include,
                            preprocess_define=options.define)

    # ast.show()
    # print("==================")
    # # for lineno, directive in directives:
    # #     print('Line %d : %s' % (lineno, directive))
    # for mdl in  ast.description.definitions:
    #     print("module name: %s"%(mdl.name))

    #     if mdl.paramlist.params:
    #         for param_decl in mdl.paramlist.params:
    #             # param_decl 是 Decl 节点，它的 list 属性里装着真正的 Parameter
    #             param = param_decl.list[0] 
    #             print(f"发现参数: {param.name}, 默认值: {param.value.var}")

    #     for port in mdl.portlist.ports:
    #         # 这里的 port 是 Ioport 节点，它的 first 属性才是真正的 Input/Output 节点
    #         actual_port = port.first
    #         port_type = type(actual_port).__name__ # 获取类名，比如 'Input' 或 'Output'
    #         print(f"发现端口: 方向={port_type}, 名字={actual_port.name}")

    extractor = VerilogFormatExtractor()
    extractor.visit(ast)

    # 打印最终生成的 JSON 数据
    output_json = json.dumps(extractor.module_data, indent=4, ensure_ascii=False)
    print(output_json)

if __name__ == '__main__':
    main()