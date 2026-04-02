import os
from typing import List, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pyverilog 相关导入
import pyverilog.vparser.ast as vast
from pyverilog.vparser.parser import parse
from fastapi import FastAPI, HTTPException, UploadFile, File
import tempfile
import os
app = FastAPI()

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =======================================================
# 1. 基础遍历器与提取器逻辑
# =======================================================
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

# =======================================================
# 2. Pydantic 数据模型 (用于接收前端回传)
# =======================================================
class Connection(BaseModel):
    inst_id: str
    port: str

class PortData(BaseModel):
    port_name: str
    left: int
    right: int
    _from: List[Connection] = []
    _to: List[Connection] = []

class ParamData(BaseModel):
    param_name: str
    param_value: Any

class ModuleInst(BaseModel):
    inst_id: str
    mdl_name: str
    params: List[ParamData]
    in_ports: List[PortData]
    out_ports: List[PortData]

# =======================================================
# 3. 核心生成算法：Top 模块合成
# =======================================================
def generate_top_module(instances: List[ModuleInst]):
    wire_defs = []
    instantiations = []
    net_map = {} # 用于存储哪些 (inst, port) 属于同一个 wire
    
    wire_count = 0
    
    # 建立连线映射
    for inst in instances:
        # 处理输出端口，分配 wire
        for out_p in inst.out_ports:
            if out_p._to:
                # 为每一个输出端口点对点或点对多创建一个独一无二的 wire
                wire_name = f"net_{wire_count}"
                wire_count += 1
                wire_defs.append(f"  wire [{out_p.left}:{out_p.right}] {wire_name};")
                
                # 记录：当前输出端口连接到这个 wire
                net_map[(inst.inst_id, out_p.port_name)] = wire_name
                # 记录：所有目标输入端口也连接到这个 wire
                for conn in out_p._to:
                    net_map[(conn.inst_id, conn.port)] = wire_name

    # 生成实例化代码
    for inst in instances:
        s = f"\n  {inst.mdl_name} "
        # 处理参数
        if inst.params:
            p_list = [f".{p.param_name}({p.param_value})" for p in inst.params]
            s += f"#(\n    {', '.join(p_list)}\n  ) "
        
        s += f"{inst.inst_id} (\n"
        
        # 合并所有端口映射
        all_ports = inst.in_ports + inst.out_ports
        port_mappings = []
        for p in all_ports:
            # 如果在网表中有连接，则连到 wire，否则悬空
            conn_wire = net_map.get((inst.inst_id, p.port_name), "")
            port_mappings.append(f"    .{p.port_name}({conn_wire})")
            
        s += ",\n".join(port_mappings)
        s += "\n  );"
        instantiations.append(s)

    # 组装
    header = "module top_design();\n"
    footer = "\n\nendmodule"
    return header + "\n".join(wire_defs) + "\n".join(instantiations) + footer

# =======================================================
# 4. API 路由
# =======================================================
@app.post("/library")
async def get_library(file: UploadFile = File(...)):
    """
    接收前端上传的 .v 文件，解析并返回模块定义
    """
    # 1. 检查文件名后缀
    if not file.filename.endswith('.v'):
        raise HTTPException(status_code=400, detail="只支持 .v 后缀的 Verilog 文件")

    # 2. 创建临时文件来存储上传的内容
    # 因为 pyverilog 的解析器需要一个物理路径
    fd, temp_path = tempfile.mkstemp(suffix='.v')
    try:
        content = await file.read()
        with os.fdopen(fd, 'wb') as tmp:
            tmp.write(content)

        # 3. 执行解析逻辑
        # 注意：parse 函数接收的是一个列表 [path]
        ast, _ = parse([temp_path])
        extractor = VerilogFormatExtractor()
        extractor.visit(ast)

        # 返回解析出的 JSON 结构
        return extractor.module_data

    except Exception as e:
        print(f"解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析 Verilog 失败: {str(e)}")
    
    finally:
        # 4. 无论成功失败，一定要删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/generate")
def handle_generate(netlist: List[ModuleInst]):
    try:
        verilog_code = generate_top_module(netlist)
        return {"code": verilog_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)