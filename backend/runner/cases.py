"""Read a deliberately small test language without executing test source.

Comparisons remain in the API supervisor. Only inputs, never expected answers or
assertions, are mounted into the execution container.
"""
import ast
import math
import operator
from dataclasses import dataclass


@dataclass
class Case:
    function: str
    args: list
    kwargs: dict
    expected: object = None
    exception: str | None = None
    approximate: bool = False


def value(node, names):
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [value(x, names) for x in node.elts]
    if isinstance(node, ast.Dict):
        return {value(k, names): value(v, names)
                for k, v in zip(node.keys, node.values, strict=True)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        result = value(node.operand, names)
        return -result if isinstance(node.op, ast.USub) else +result
    if isinstance(node, ast.BinOp) and type(node.op) in {ast.Add, ast.Sub, ast.Mult, ast.Div}:
        left, right = value(node.left, names), value(node.right, names)
        if type(left) not in {int, float} or type(right) not in {int, float}:
            raise ValueError('Only numeric literal arithmetic is supported')
        return {ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv}[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = [value(x, names) for x in node.args]
        if node.func.id == 'float' and len(args) == 1 and args[0] in {'inf', '-inf', 'nan'}:
            return float(args[0])
        if node.func.id == 'round' and len(args) in {1, 2}:
            return round(*args)
    raise ValueError('Unsupported test expression')


def extract(source):
    if len(source) > 60000:
        raise ValueError('Test module is too large')
    tree = ast.parse(source)
    if len(list(ast.walk(tree))) > 4000:
        raise ValueError('Test module is too complex')
    imported = set()
    cases = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'submission':
            if any(x.asname or x.name.startswith('_') for x in node.names):
                raise ValueError('Unsupported submission import')
            imported.update(x.name for x in node.names)
            continue
        if isinstance(node, ast.Import) and [x.name for x in node.names] == ['pytest']:
            continue
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
            raise ValueError('Only deterministic function tests are supported')
        rows = [{}]
        if node.decorator_list:
            if len(node.decorator_list) != 1:
                raise ValueError('Unsupported test decorators')
            d = node.decorator_list[0]
            if (not isinstance(d, ast.Call) or ast.unparse(d.func) != 'pytest.mark.parametrize'
                    or len(d.args) != 2 or d.keywords):
                raise ValueError('Only literal parametrization is supported')
            keys = value(d.args[0], {}).split(',')
            raw_rows = value(d.args[1], {})
            rows = [dict(zip(keys, [r] if len(keys) == 1 else r, strict=True)) for r in raw_rows]
        elif node.args.args:
            raise ValueError('Fixtures are unsupported')
        for names in rows:
            body = node.body
            exception = None
            approximate = False
            expected = None
            if len(body) == 1 and isinstance(body[0], ast.With):
                ctx = body[0]
                call = ctx.items[0].context_expr
                if (len(ctx.items) != 1 or not isinstance(call, ast.Call)
                        or ast.unparse(call.func) != 'pytest.raises' or len(call.args) != 1
                        or not isinstance(call.args[0], ast.Name) or call.keywords
                        or len(ctx.body) != 1 or not isinstance(ctx.body[0], ast.Expr)):
                    raise ValueError('Unsupported exception case')
                exception = call.args[0].id
                if exception not in {'ValueError', 'TypeError', 'ZeroDivisionError', 'KeyError',
                                     'IndexError', 'RuntimeError', 'OverflowError'}:
                    raise ValueError('Unsupported expected exception')
                invocation = ctx.body[0].value
            else:
                if len(body) == 2 and isinstance(body[0], ast.Assign):
                    assign = body[0]
                    if len(assign.targets) != 1 or not isinstance(assign.targets[0], ast.Name):
                        raise ValueError('Unsupported assertion binding')
                    invocation = assign.value
                    assertion = body[1]
                    binding = assign.targets[0].id
                elif len(body) == 1:
                    assertion = body[0]
                    invocation = None
                    binding = None
                else:
                    raise ValueError('Unsupported test body')
                if (not isinstance(assertion, ast.Assert)
                        or not isinstance(assertion.test, ast.Compare)
                        or len(assertion.test.ops) != 1
                        or not isinstance(assertion.test.ops[0], ast.Eq)):
                    raise ValueError('Expected one equality assertion')
                comparison = assertion.test
                if invocation is None:
                    invocation = comparison.left
                elif not isinstance(comparison.left, ast.Name) or comparison.left.id != binding:
                    raise ValueError('Assertion does not observe the invocation')
                rhs = comparison.comparators[0]
                if isinstance(rhs, ast.Call) and ast.unparse(rhs.func) == 'pytest.approx':
                    if len(rhs.args) != 1 or rhs.keywords:
                        raise ValueError('Unsupported approximate comparison')
                    approximate = True
                    rhs = rhs.args[0]
                expected = value(rhs, names)
            if (not isinstance(invocation, ast.Call) or not isinstance(invocation.func, ast.Name)
                    or invocation.func.id not in imported):
                raise ValueError('Expected a direct submitted function call')
            args, kwargs = [], {}
            for a in invocation.args:
                if isinstance(a, ast.Starred):
                    args.extend(value(a.value, names))
                else:
                    args.append(value(a, names))
            for k in invocation.keywords:
                if k.arg is None:
                    kwargs.update(value(k.value, names))
                else:
                    kwargs[k.arg] = value(k.value, names)
            cases.append(Case(invocation.func.id, args, kwargs, expected, exception, approximate))
            if len(cases) > 64:
                raise ValueError('Too many cases in one module')
    if not cases:
        raise ValueError('No supported test cases')
    return cases


def matches(actual, expected, approximate=False):
    if approximate and type(expected) in {int, float} and type(actual) in {int, float}:
        return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-12)
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(
            matches(a, e, approximate) for a, e in zip(actual, expected, strict=True))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            matches(actual[k], expected[k], approximate) for k in expected)
    return actual == expected
