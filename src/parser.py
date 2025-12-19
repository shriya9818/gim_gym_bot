from functools import wraps
from typing import Any

from lark import Lark, Token, Transformer, v_args
from pydantic import BaseModel


class ArgSpec(BaseModel):
    name: str
    optional: bool = False
    arg_type: str = "str"
    choices: list[str] | None = None


class CommandSpec(BaseModel):
    command: str
    args: list[ArgSpec] = []


# -------------------------
# Grammar
# -------------------------
grammar = r"""
    start: command

    # command token is slash + one or more lowercase letters
    command: COMMAND (WS arg)*

    arg: "{" IDENT opt_flag? type? choices? "}"

    opt_flag: "?"
    type: ":" IDENT
    choices: "=" choice_list

    choice_list: IDENT ("|" IDENT)*

    IDENT: /[A-Za-z_][A-Za-z0-9_]*/
    COMMAND: /\/[a-z]+/
    WS: " "

    %ignore /[\t]+/
"""


# -------------------------
# Transformer using v_args(inline=True)
# -------------------------
@v_args(inline=True)
class CommandTransformer(Transformer):
    """
    With v_args(inline=True) methods get children as positional args instead of a list.
    """

    def start(self, cmd_spec: CommandSpec) -> CommandSpec:
        # cmd_spec comes from command()
        return cmd_spec

    def command(self, command_token: Token, *args: Any) -> CommandSpec:
        """
        command_token: Token like "/setmode"
        args: zero or more ArgSpec (or things convertible)
        """
        name = str(command_token).lstrip("/")
        arg_objs: list[ArgSpec] = []
        for it in args:
            if isinstance(it, ArgSpec):
                arg_objs.append(it)
            elif isinstance(it, dict):
                arg_objs.append(ArgSpec(**it))
            # else ignore
        return CommandSpec(command=name, args=arg_objs)

    def arg(self, ident: Token, *rest: Any) -> ArgSpec:
        """
        ident: IDENT token (arg name)
        rest: optional items in order (opt_flag -> "?", type -> ("type", "int"), choices -> ("choices", [..]))
        """
        name = str(ident)
        optional = False
        arg_type = "str"
        choices: list[str] | None = None

        for item in rest:
            # opt_flag returns "?"
            if item == "?":
                optional = True
            # type() returns tuple ("type", type_name)
            elif isinstance(item, tuple) and item[0] == "type":
                arg_type = str(item[1])
            # choices() returns tuple ("choices", [..])
            elif isinstance(item, tuple) and item[0] == "choices":
                choices = list(item[1])

        return ArgSpec(name=name, optional=optional, arg_type=arg_type, choices=choices)

    def opt_flag(self) -> str:
        return "?"

    def type(self, ident: Token) -> tuple:
        return ("type", ident)

    def choices(self, eq: Token, choice_list: list[str]) -> tuple:
        # As with type(), we guard shapes. Return tuple to be interpreted by arg().
        # choice_list already converted by choice_list()
        return ("choices", list(choice_list))

    def choice_list(self, first: Token, *rest: Token) -> list[str]:
        # first + zero or more '|' IDENT tokens; due to grammar it will receive IDENTs only.
        out = [str(first)]
        for r in rest:
            out.append(str(r))
        return out

    def IDENT(self, token: Token) -> str:
        return str(token)

    def COMMAND(self, token: Token) -> str:
        return str(token)


# parser instance that returns CommandSpec via transformer
format_parser = Lark(grammar, parser="lalr", transformer=CommandTransformer())


# -------------------------
# Type casting helpers
# -------------------------
def cast_value(type_name: str, token: str) -> Any:
    if type_name == "str":
        return token
    if type_name == "int":
        try:
            return int(token)
        except Exception:
            raise ValueError(f"expected int but got '{token}'")
    if type_name == "float":
        try:
            return float(token)
        except Exception:
            raise ValueError(f"expected float but got '{token}'")
    if type_name == "bool":
        low = token.lower()
        if low in ("true", "1", "yes", "y", "on"):
            return True
        if low in ("false", "0", "no", "n", "off"):
            return False
        raise ValueError(f"expected bool (true/false) but got '{token}'")
    # fallback: unknown types -> string
    return token


def command_parser(command_name: str, format_string: str):
    """
    Decorator factory.
    - command_name: e.g. "setmode" (no leading slash)
    - format_string: Args ("{mode:str=...}") if any
    """
    # We try to parse format_string directly. If it doesn't begin with '/'
    # we prepend "/{command_name} " so the grammar can parse it.
    parse_input = f"/{command_name} " + format_string.strip()
    print(parse_input)
    try:
        spec: CommandSpec = format_parser.parse(parse_input)  # type: ignore[assignment]
    except Exception as e:
        raise ValueError(f"invalid command format: {e}")

    if spec.command != command_name:
        raise ValueError(
            f"format command '/{spec.command}' does not match provided command_name '/{command_name}'"
        )

    arg_specs: list[ArgSpec] = spec.args

    def decorator(func):
        @wraps(func)
        def wrapper(message: str, *args, **kwargs):
            if not message or not message.strip():
                raise ValueError("empty message")

            parts = message.strip().split()
            if not parts:
                raise ValueError("empty message tokenization")

            if parts[0] != f"/{command_name}":
                raise ValueError(
                    f"expected command '/{command_name}' but got '{parts[0]}'"
                )

            tokens = parts[1:]
            parsed_kwargs: Dict[str, Any] = {}

            t_idx = 0
            for i, a in enumerate(arg_specs):
                name = a.name
                optional = a.optional
                typ = a.arg_type
                choices = a.choices

                if t_idx >= len(tokens):
                    if optional:
                        parsed_kwargs[name] = None
                        continue
                    else:
                        raise ValueError(f"missing required argument '{name}'")

                # If last arg and string with no choices -> take rest of message
                is_last = i == len(arg_specs) - 1
                if is_last and typ == "str" and choices is None:
                    raw = " ".join(tokens[t_idx:])
                    t_idx = len(tokens)
                else:
                    raw = tokens[t_idx]
                    t_idx += 1

                if choices is not None:
                    if raw not in choices:
                        raise ValueError(
                            f"argument '{name}' must be one of {choices}, got '{raw}'"
                        )

                try:
                    value = cast_value(typ, raw)
                except ValueError as e:
                    raise ValueError(f"argument '{name}': {e}")

                parsed_kwargs[name] = value
                print(parsed_kwargs)

            if t_idx < len(tokens):
                leftover = " ".join(tokens[t_idx:])
                raise ValueError(f"unexpected extra tokens: '{leftover}'")

            return func(*args, **parsed_kwargs, **kwargs)

        return wrapper

    return decorator


# -------------------------
# Examples / quick tests
# -------------------------
if __name__ == "__main__":

    @command_parser("setmode", "{mode:str=easy|medium|hard}")
    def setmode(mode):
        print("setmode ->", mode)
        return mode

    @command_parser("lock", "{reason:str}")
    def lock(reason):
        print("lock ->", reason)
        return reason

    @command_parser("increase", "/increase {base:int} {inc:int}")
    def increase(base, inc):
        print("increase ->", base + inc)
        return base + inc

    tests_good = [
        (setmode, "/setmode easy"),
        (lock, "/lock I forgot my keys"),
        (increase, "/increase 5 7"),
    ]

    tests_bad = [
        (setmode, "/setmode impossible"),
        (increase, "/increase five 2"),
        (lock, "/lock"),  # missing reason
    ]

    print("GOOD")
    for fn, msg in tests_good:
        try:
            fn(msg)
        except Exception as e:
            print("unexpected fail:", e)

    print("\nBAD")
    for fn, msg in tests_bad:
        try:
            fn(msg)
            print("unexpected success for:", msg)
        except Exception as e:
            print("expected fail ->", e)
