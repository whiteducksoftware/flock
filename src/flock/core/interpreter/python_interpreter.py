# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
import ast
import builtins
import difflib
import importlib
import re
import typing
from collections.abc import Mapping
from typing import (
    Any,
)

from opentelemetry import trace

from flock.core.logging.logging import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger("interpreter")


class InterpreterError(ValueError):
    r"""An error raised when the interpreter cannot evaluate a Python
    expression, due to syntax error or unsupported operations.
    """

    pass


class PythonInterpreter:
    r"""A customized python interpreter to control the execution of
    LLM-generated codes. The interpreter makes sure the code can only execute
    functions given in action space and import white list. It also supports
    fuzzy variable matching to receive uncertain input variable name.

    [Documentation omitted for brevity]

    Args:
        action_space (Dict[str, Any]): A dictionary mapping action names to
            their corresponding functions or objects.
        import_white_list (Optional[List[str]], optional): A list of allowed modules.
        verbose (bool, optional): If True, the interpreter prints log messages
            as it executes the code. (default: False)
    """

    def __init__(
        self,
        action_space: dict[str, Any],
        import_white_list: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        self.action_space = action_space
        self.state = self.action_space.copy()
        self.fuzz_state: dict[str, Any] = {}
        self.import_white_list = import_white_list or [
            "math",
            "random",
            "datetime",
            "time",
            "string",
            "collections",
            "itertools",
            "functools",
            "typing",
            "enum",
            "json",
            "ast",
        ]  # default imports
        self.verbose = verbose

    def log(self, message: str) -> None:
        """Print a log message immediately."""
        # print(message, flush=True)
        logger.info(message, flush=True)

    def execute(
        self,
        code: str,
        state: dict[str, Any] | None = None,
        fuzz_state: dict[str, Any] | None = None,
        keep_state: bool = True,
    ) -> Any:
        r"""Execute the input python codes in a secure environment.

        [Documentation omitted for brevity]
        """
        if state is not None:
            self.state.update(state)
        if fuzz_state is not None:
            self.fuzz_state.update(fuzz_state)

        try:
            expression = ast.parse(code)
        except SyntaxError as e:
            error_line = code.splitlines()[e.lineno - 1]
            raise InterpreterError(
                f"Syntax error in code at line {e.lineno}: {error_line}\nError: {e}"
            )

        result = None
        if self.verbose:
            self.log("[Interpreter] Starting code execution...")

        for idx, node in enumerate(expression.body):
            # Log the AST node being executed (using unparse if available)
            if self.verbose:
                try:
                    node_repr = ast.unparse(node)
                except Exception:
                    node_repr = ast.dump(node)
                self.log(f"[Interpreter] Executing node {idx}: {node_repr}")

            try:
                line_result = self._execute_ast(node)
            except InterpreterError as e:
                if not keep_state:
                    self.clear_state()
                msg = f"Evaluation of the code stopped at node {idx}. See:\n{e}"
                raise InterpreterError(msg)
            if line_result is not None:
                result = line_result
                if self.verbose:
                    self.log(f"[Interpreter] Node {idx} result: {result}")

        if self.verbose:
            self.log("[Interpreter] Finished code execution.")
        if not keep_state:
            self.clear_state()

        return result

    def clear_state(self) -> None:
        r"""Initialize :obj:`state` and :obj:`fuzz_state`"""
        self.state = self.action_space.copy()
        self.fuzz_state = {}

    # ast.Index is deprecated after python 3.9, which cannot pass type check,
    # but is still necessary for older versions.
    @typing.no_type_check
    def _execute_ast(self, expression: ast.AST) -> Any:
        if isinstance(expression, ast.Assign):
            return self._execute_assign(expression)
        elif isinstance(expression, ast.Attribute):
            value = self._execute_ast(expression.value)
            return getattr(value, expression.attr)
        elif isinstance(expression, ast.AugAssign):
            return self._execute_augassign(expression)
        elif isinstance(expression, ast.BinOp):
            return self._execute_binop(expression)
        elif isinstance(expression, ast.BoolOp):
            return self._execute_condition(expression)
        elif isinstance(expression, ast.Call):
            return self._execute_call(expression)
        elif isinstance(expression, ast.Compare):
            return self._execute_condition(expression)
        elif isinstance(expression, ast.Constant):
            return expression.value
        elif isinstance(expression, ast.Dict):
            result: dict = {}
            for k, v in zip(expression.keys, expression.values):
                if k is not None:
                    result[self._execute_ast(k)] = self._execute_ast(v)
                else:
                    result.update(self._execute_ast(v))
            return result
        elif isinstance(expression, ast.Expr):
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.For):
            return self._execute_for(expression)
        elif isinstance(expression, ast.FormattedValue):
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.FunctionDef):
            self.state[expression.name] = expression
            return None
        elif isinstance(expression, ast.GeneratorExp):
            return self._execute_generatorexp(expression)
        elif isinstance(expression, ast.If):
            return self._execute_if(expression)
        elif isinstance(expression, ast.IfExp):
            return self._execute_ifexp(expression)
        elif isinstance(expression, ast.Import):
            self._execute_import(expression)
            return None
        elif isinstance(expression, ast.ImportFrom):
            self._execute_import_from(expression)
            return None
        elif hasattr(ast, "Index") and isinstance(expression, ast.Index):
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.JoinedStr):
            return "".join(
                [str(self._execute_ast(v)) for v in expression.values]
            )
        elif isinstance(expression, ast.Lambda):
            return self._execute_lambda(expression)
        elif isinstance(expression, ast.List):
            return [self._execute_ast(elt) for elt in expression.elts]
        elif isinstance(expression, ast.Name):
            return self._execute_name(expression)
        elif isinstance(expression, ast.Return):
            return self._execute_ast(expression.value)
        elif isinstance(expression, ast.Subscript):
            return self._execute_subscript(expression)
        elif isinstance(expression, ast.Tuple):
            return tuple([self._execute_ast(elt) for elt in expression.elts])
        elif isinstance(expression, ast.UnaryOp):
            return self._execute_unaryop(expression)
        elif isinstance(expression, ast.While):
            return self._execute_while(expression)
        elif isinstance(expression, ast.ListComp):
            return self._execute_listcomp(expression)
        elif isinstance(expression, ast.DictComp):
            return self._execute_dictcomp(expression)
        elif isinstance(expression, ast.SetComp):
            return self._execute_setcomp(expression)
        elif isinstance(expression, ast.Break):
            raise BreakException()
        elif isinstance(expression, ast.Continue):
            raise ContinueException()
        elif isinstance(expression, ast.Try):
            return self._execute_try(expression)
        elif isinstance(expression, ast.Raise):
            return self._execute_raise(expression)
        elif isinstance(expression, ast.Pass):
            return None
        elif isinstance(expression, ast.Assert):
            return self._execute_assert(expression)
        else:
            raise InterpreterError(
                f"{expression.__class__.__name__} is not supported."
            )

    def _execute_assign(self, assign: ast.Assign) -> Any:
        targets = assign.targets
        result = self._execute_ast(assign.value)

        for target in targets:
            self._assign(target, result)
        return result

    def _assign(self, target: ast.expr, value: Any):
        if isinstance(target, ast.Name):
            self.state[target.id] = value
        elif isinstance(target, ast.Tuple):
            if not isinstance(value, tuple):
                raise InterpreterError(
                    f"Expected type tuple, but got {value.__class__.__name__} instead."
                )
            if len(target.elts) != len(value):
                raise InterpreterError(
                    f"Expected {len(target.elts)} values but got {len(value)}."
                )
            for t, v in zip(target.elts, value):
                self.state[self._execute_ast(t)] = v
        else:
            raise InterpreterError(
                f"Unsupported variable type. Expected ast.Name or ast.Tuple, got {target.__class__.__name__} instead."
            )

    def _execute_call(self, call: ast.Call) -> Any:
        callable_func = self._execute_ast(call.func)

        args = [self._execute_ast(arg) for arg in call.args]
        kwargs = {
            keyword.arg: self._execute_ast(keyword.value)
            for keyword in call.keywords
        }
        if isinstance(callable_func, ast.FunctionDef):
            old_state = self.state.copy()
            for param_name, arg_value in zip(
                [param.arg for param in callable_func.args.args], args
            ):
                self.state[param_name] = arg_value
            result = None
            for stmt in callable_func.body:
                result = self._execute_ast(stmt)
                if isinstance(stmt, ast.Return):
                    break
            self.state = old_state
            return result
        return callable_func(*args, **kwargs)

    def _execute_augassign(self, augassign: ast.AugAssign):
        current_value = self.state[augassign.target.id]
        increment_value = self._execute_ast(augassign.value)
        if not (
            isinstance(current_value, (int, float))
            and isinstance(increment_value, (int, float))
        ):
            raise InterpreterError(
                f"Invalid types for augmented assignment: {type(current_value)}, {type(increment_value)}"
            )
        if isinstance(augassign.op, ast.Add):
            new_value = current_value + increment_value
        elif isinstance(augassign.op, ast.Sub):
            new_value = current_value - increment_value
        elif isinstance(augassign.op, ast.Mult):
            new_value = current_value * increment_value
        elif isinstance(augassign.op, ast.Div):
            new_value = current_value / increment_value
        else:
            raise InterpreterError(
                f"Augmented assignment operator {augassign.op} is not supported"
            )
        self._assign(augassign.target, new_value)
        return new_value

    def _execute_subscript(self, subscript: ast.Subscript):
        index = self._execute_ast(subscript.slice)
        value = self._execute_ast(subscript.value)
        if not isinstance(subscript.ctx, ast.Load):
            raise InterpreterError(
                f"{subscript.ctx.__class__.__name__} is not supported for subscript."
            )
        if isinstance(value, (list, tuple)):
            return value[int(index)]
        if index in value:
            return value[index]
        if isinstance(index, str) and isinstance(value, Mapping):
            close_matches = difflib.get_close_matches(index, list(value.keys()))
            if len(close_matches) > 0:
                return value[close_matches[0]]
        raise InterpreterError(f"Could not index {value} with '{index}'.")

    def _execute_name(self, name: ast.Name):
        if name.id in dir(builtins):
            return getattr(builtins, name.id)
        if isinstance(name.ctx, ast.Store):
            return name.id
        elif isinstance(name.ctx, ast.Load):
            return self._get_value_from_state(name.id)
        else:
            raise InterpreterError(f"{name.ctx} is not supported.")

    def _execute_condition(self, condition):
        if isinstance(condition, ast.BoolOp):
            if isinstance(condition.op, ast.And):
                results = [
                    self._execute_ast(value) for value in condition.values
                ]
                return all(results)
            elif isinstance(condition.op, ast.Or):
                results = [
                    self._execute_ast(value) for value in condition.values
                ]
                return any(results)
            else:
                raise InterpreterError(
                    f"Boolean operator {condition.op} is not supported"
                )
        elif isinstance(condition, ast.Compare):
            if len(condition.ops) > 1:
                raise InterpreterError(
                    "Cannot evaluate conditions with multiple operators"
                )
            left = self._execute_ast(condition.left)
            comparator = condition.ops[0]
            right = self._execute_ast(condition.comparators[0])
            if isinstance(comparator, ast.Eq):
                return left == right
            elif isinstance(comparator, ast.NotEq):
                return left != right
            elif isinstance(comparator, ast.Lt):
                return left < right
            elif isinstance(comparator, ast.LtE):
                return left <= right
            elif isinstance(comparator, ast.Gt):
                return left > right
            elif isinstance(comparator, ast.GtE):
                return left >= right
            elif isinstance(comparator, ast.Is):
                return left is right
            elif isinstance(comparator, ast.IsNot):
                return left is not right
            elif isinstance(comparator, ast.In):
                return left in right
            elif isinstance(comparator, ast.NotIn):
                return left not in right
            else:
                raise InterpreterError("Unsupported comparison operator")
        elif isinstance(condition, ast.UnaryOp):
            return self._execute_unaryop(condition)
        elif isinstance(condition, ast.Name) or isinstance(condition, ast.Call):
            return bool(self._execute_ast(condition))
        elif isinstance(condition, ast.Constant):
            return bool(condition.value)
        else:
            raise InterpreterError(
                f"Unsupported condition type: {type(condition).__name__}"
            )

    def _execute_if(self, if_statement: ast.If):
        result = None
        if self._execute_condition(if_statement.test):
            for line in if_statement.body:
                line_result = self._execute_ast(line)
                if line_result is not None:
                    result = line_result
        else:
            for line in if_statement.orelse:
                line_result = self._execute_ast(line)
                if line_result is not None:
                    result = line_result
        return result

    def _execute_ifexp(self, ifexp: ast.IfExp) -> Any:
        test_result = self._execute_condition(ifexp.test)
        if test_result:
            return self._execute_ast(ifexp.body)
        else:
            return self._execute_ast(ifexp.orelse)

    def _execute_import(self, import_module: ast.Import) -> None:
        for module in import_module.names:
            self._validate_import(module.name)
            alias = module.asname or module.name
            self.state[alias] = importlib.import_module(module.name)

    def _execute_import_from(self, import_from: ast.ImportFrom):
        if import_from.module is None:
            raise InterpreterError('"from . import" is not supported.')
        for import_name in import_from.names:
            full_name = import_from.module + f".{import_name.name}"
            self._validate_import(full_name)
            imported_module = importlib.import_module(import_from.module)
            alias = import_name.asname or import_name.name
            self.state[alias] = getattr(imported_module, import_name.name)

    # Note: Two versions of _execute_for and _execute_while appear in this file.
    # We keep both as provided, but you may wish to consolidate these in your code.

    def _execute_for(self, for_statement: ast.For):
        class BreakException(Exception):
            pass

        class ContinueException(Exception):
            pass

        result = None
        try:
            for value in self._execute_ast(for_statement.iter):
                self._assign(for_statement.target, value)
                try:
                    for line in for_statement.body:
                        line_result = self._execute_ast(line)
                        if line_result is not None:
                            result = line_result
                except ContinueException:
                    continue
        except BreakException:
            pass
        return result

    def _execute_while(self, while_statement: ast.While):
        class BreakException(Exception):
            pass

        class ContinueException(Exception):
            pass

        result = None
        try:
            while self._execute_condition(while_statement.test):
                try:
                    for line in while_statement.body:
                        line_result = self._execute_ast(line)
                        if line_result is not None:
                            result = line_result
                except ContinueException:
                    continue
        except BreakException:
            pass
        return result

    def _execute_try(self, try_statement: ast.Try):
        try:
            for line in try_statement.body:
                self._execute_ast(line)
        except Exception as e:
            handled = False
            for handler in try_statement.handlers:
                if handler.type is None or isinstance(
                    e, self._execute_ast(handler.type)
                ):
                    if handler.name:
                        self.state[handler.name.id] = e
                    for line in handler.body:
                        self._execute_ast(line)
                    handled = True
                    break
            if not handled:
                raise
        finally:
            for line in try_statement.finalbody:
                self._execute_ast(line)

    def _execute_raise(self, raise_statement: ast.Raise):
        if raise_statement.exc:
            exception = self._execute_ast(raise_statement.exc)
            raise exception
        else:
            raise

    def _execute_assert(self, assert_statement: ast.Assert):
        test_result = self._execute_condition(assert_statement.test)
        if not test_result:
            if assert_statement.msg:
                msg = self._execute_ast(assert_statement.msg)
                raise AssertionError(msg)
            else:
                raise AssertionError

    def _execute_lambda(self, lambda_node: ast.Lambda) -> Any:
        def lambda_function(*args):
            old_state = self.state.copy()
            for param, arg in zip(lambda_node.args.args, args):
                self.state[param.arg] = arg
            result = self._execute_ast(lambda_node.body)
            self.state = old_state  # Restore the state
            return result

        return lambda_function

    def _validate_import(self, full_name: str):
        tmp_name = ""
        found_name = False
        for name in full_name.split("."):
            tmp_name += name if tmp_name == "" else f".{name}"
            if tmp_name in self.import_white_list:
                found_name = True
                return
        if not found_name:
            raise InterpreterError(
                f"It is not permitted to import modules "
                f"than module white list (try to import {full_name})."
            )

    def _execute_binop(self, binop: ast.BinOp):
        left = self._execute_ast(binop.left)
        operator = binop.op
        right = self._execute_ast(binop.right)

        if isinstance(operator, ast.Add):
            return left + right
        elif isinstance(operator, ast.Sub):
            return left - right
        elif isinstance(operator, ast.Mult):
            return left * right
        elif isinstance(operator, ast.Div):
            return left / right
        elif isinstance(operator, ast.FloorDiv):
            return left // right
        elif isinstance(operator, ast.Mod):
            return left % right
        elif isinstance(operator, ast.Pow):
            return left**right
        elif isinstance(operator, ast.LShift):
            return left << right
        elif isinstance(operator, ast.RShift):
            return left >> right
        elif isinstance(operator, ast.BitAnd):
            return left & right
        elif isinstance(operator, ast.BitOr):
            return left | right
        elif isinstance(operator, ast.BitXor):
            return left ^ right
        elif isinstance(operator, ast.MatMult):
            return left @ right
        else:
            raise InterpreterError(f"Operator not supported: {operator}")

    def _execute_unaryop(self, unaryop: ast.UnaryOp):
        operand = self._execute_ast(unaryop.operand)
        operator = unaryop.op

        if isinstance(operator, ast.UAdd):
            return +operand
        elif isinstance(operator, ast.USub):
            return -operand
        elif isinstance(operator, ast.Not):
            return not operand
        elif isinstance(operator, ast.Invert):
            return ~operand
        else:
            raise InterpreterError(f"Operator not supported: {operator}")

    def _execute_listcomp(self, comp: ast.ListComp):
        return [self._execute_comp(comp.elt, comp.generators)]

    def _execute_dictcomp(self, comp: ast.DictComp):
        return {
            self._execute_comp(comp.key, comp.generators): self._execute_comp(
                comp.value, comp.generators
            )
        }

    def _execute_setcomp(self, comp: ast.SetComp):
        return {self._execute_comp(comp.elt, comp.generators)}

    def _execute_comp(self, elt, generators):
        if not generators:
            return self._execute_ast(elt)
        gen = generators[0]
        result = []
        for value in self._execute_ast(gen.iter):
            self._assign(gen.target, value)
            if all(self._execute_condition(if_cond) for if_cond in gen.ifs):
                result.extend(self._execute_comp(elt, generators[1:]))
        return result

    def _execute_generatorexp(self, genexp: ast.GeneratorExp):
        def generator():
            for value in self._execute_comp(genexp.elt, genexp.generators):
                yield value

        return generator()

    def _get_value_from_state(self, key: str) -> Any:
        if key in self.state:
            return self.state[key]
        elif key in self.fuzz_state:
            return self.fuzz_state[key]
        else:
            raise InterpreterError(f"The variable `{key}` is not defined.")


class TextPrompt(str):
    r"""A class that represents a text prompt. The :obj:`TextPrompt` class
    extends the built-in :obj:`str` class to provide a property for retrieving
    the set of keywords in the prompt.
    """

    @property
    def key_words(self) -> set[str]:
        pattern = re.compile(r"\{([^{}]+)\}")
        found = pattern.findall(self)
        return set(found)

    def format(self, *args: Any, **kwargs: Any) -> "TextPrompt":
        default_kwargs = {key: "{" + f"{key}" + "}" for key in self.key_words}
        default_kwargs.update(kwargs)
        return TextPrompt(super().format(*args, **default_kwargs))


class CodePrompt(TextPrompt):
    r"""A class that represents a code prompt. It extends the :obj:`TextPrompt`
    class with a :obj:`code_type` property.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> "CodePrompt":
        code_type = kwargs.pop("code_type", None)
        instance = super().__new__(cls, *args, **kwargs)
        instance._code_type = code_type
        return instance

    @property
    def code_type(self) -> str | None:
        return self._code_type

    def set_code_type(self, code_type: str) -> None:
        self._code_type = code_type

    def execute(
        self,
        interpreter: PythonInterpreter | None = None,
        user_variable: dict[str, Any] | None = None,
    ) -> tuple[Any, PythonInterpreter]:
        if not interpreter:
            interpreter = PythonInterpreter(action_space=globals())
        execution_res = interpreter.execute(
            self, fuzz_state=user_variable, keep_state=True
        )
        return execution_res, interpreter
