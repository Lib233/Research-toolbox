"""Numeric math expressions without eval/exec/calls to arbitrary Python objects."""
import ast, operator, math
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,
     ast.Mod:operator.mod}
CMP={ast.Gt:operator.gt,ast.GtE:operator.ge,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Eq:operator.eq}
FUN={'abs':abs,'min':min,'max':max,'sin':math.sin,'cos':math.cos,'tan':math.tan,'exp':math.exp,
     'sqrt':math.sqrt,'log':math.log,'ln':math.log,'log10':math.log10,'log2':math.log2,'tanh':math.tanh,
     'asin':math.asin,'acos':math.acos,'atan':math.atan,'floor':math.floor,'ceil':math.ceil,
     'sinh':math.sinh,'cosh':math.cosh,'pow':pow}

def calculate(expression,variables):
    if len(expression)>600:raise ValueError('公式太长。')
    tree=ast.parse(expression.replace('^','**'),mode='eval')
    def walk(n):
        if isinstance(n,ast.Expression):return walk(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return float(n.value)
        if isinstance(n,ast.Name):
            if n.id in variables:return float(variables[n.id])
            if n.id=='pi':return math.pi
            if n.id=='e':return math.e
            raise ValueError(f'未定义变量：{n.id}')
        if isinstance(n,ast.BinOp) and type(n.op) in OPS:
            a,b=walk(n.left),walk(n.right)
            if isinstance(n.op,ast.Pow) and abs(b)>12:raise ValueError('幂次过大。')
            return OPS[type(n.op)](a,b)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            return walk(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        if isinstance(n,ast.IfExp):
            return walk(n.body if walk(n.test) else n.orelse)
        if isinstance(n,ast.BoolOp) and isinstance(n.op,(ast.And,ast.Or)):
            return all(bool(walk(x)) for x in n.values) if isinstance(n.op,ast.And) else any(bool(walk(x)) for x in n.values)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('where','ifelse') and len(n.args)==3 and not n.keywords:
            return walk(n.args[1] if walk(n.args[0]) else n.args[2])
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUN and not n.keywords:
            return FUN[n.func.id](*[walk(a) for a in n.args])
        if isinstance(n,ast.Compare) and len(n.ops)==1 and type(n.ops[0]) in CMP:
            return CMP[type(n.ops[0])](walk(n.left),walk(n.comparators[0]))
        raise ValueError('公式仅支持基本四则运算、比较和指定数学函数；不可执行Python代码。')
    try:
        v=walk(tree)
        if isinstance(v,bool):return v
        if not math.isfinite(v):raise ValueError('公式得到无穷大或非数值。')
        return float(v)
    except (OverflowError,ZeroDivisionError,ValueError,TypeError,SyntaxError) as exc:
        raise ValueError('公式计算失败：'+str(exc)) from exc
