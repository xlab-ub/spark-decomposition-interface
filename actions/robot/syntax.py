import re

LEADING_WHITESPACE_PATTERN = re.compile(r'^(\s+)(.*)$')
# Matches a converted call such as  self.pick('cup', 'left')  /  find('cup')  /  self.near()
CALL_PATTERN = re.compile(r"^(?:self\.)?(\w+)\((.*)\)$")


def get_first_indent(input_string):
    match = LEADING_WHITESPACE_PATTERN.match(input_string)
    if match:
        return match.groups()
    return '', input_string


def _to_call(name, args, code_prefix):
    """FIND CUP -> self.find('cup');  PICK CUP LEFT -> self.pick('cup', 'left');  STAND_UP -> self.stand_up()."""
    quoted = ", ".join(f"'{arg}'" for arg in args)
    return f"{code_prefix}{name}({quoted})"


def _from_call(call_text, code_prefix):
    """self.pick('cup', 'left') -> pick cup left  (None if not a call)."""
    match = CALL_PATTERN.match(call_text.strip())
    if not match:
        return None
    name, raw_args = match.groups()
    args = [a.strip().strip('\'"') for a in raw_args.split(',') if a.strip()]
    return " ".join([name] + args)


class HumanFriendlyPythonSyntaxConverter:
    @staticmethod
    def to_standard_syntax(simplified_code, class_method=False):
        code_prefix = "self." if class_method else ""
        standard_code_lines = []
        lines = simplified_code.lower().split('\n')
        for line in lines:
            indent, line = get_first_indent(line)
            tokens = line.split()
            if not tokens:
                continue
            head, rest = tokens[0], tokens[1:]
            if head == "repeat":
                times = rest[0] if rest else "1"
                standard_code_lines.append(f"{indent}for _ in range({times}):")
            elif head == "if":
                # IF NEAR -> if self.near():   IF FOUND CUP -> if self.found('cup'):
                condition = _to_call(rest[0], rest[1:], code_prefix) if rest else "False"
                standard_code_lines.append(f"{indent}if {condition}:")
            elif head == "else":
                standard_code_lines.append(f"{indent}else:")
            elif head == "while":
                condition = _to_call(rest[0], rest[1:], code_prefix) if rest else "False"
                standard_code_lines.append(f"{indent}while {condition}:")
            elif head == "end":
                standard_code_lines.append(f"{indent}    pass")
                standard_code_lines.append(f"{indent}# {line}")
            else:
                # Any action: first token is the method, remaining tokens are string arguments.
                # FIND CUP -> self.find('cup');  PICK CUP -> self.pick('cup');  STAND_UP -> self.stand_up()
                standard_code_lines.append(f"{indent}{_to_call(head, rest, code_prefix)}")
        return '\n'.join(standard_code_lines)

    @staticmethod
    def to_simplified_syntax(standard_code, class_method=False):
        code_prefix = "self." if class_method else ""
        simplified_code_lines = []
        lines = standard_code.split('\n')
        for line in lines:
            indent, line = get_first_indent(line)
            if line.startswith("for"):
                times = line.split('(')[1].split(')')[0]
                simplified_code_lines.append(f"{indent}repeat {times} times")
            elif line.startswith("if"):
                condition = line[len("if"):].strip().rstrip(':')
                simplified_code_lines.append(f"{indent}if {_from_call(condition, code_prefix) or condition}")
            elif line.startswith("else"):
                simplified_code_lines.append(f"{indent}else")
            elif line.startswith("while"):
                condition = line[len("while"):].strip().rstrip(':')
                simplified_code_lines.append(f"{indent}while {_from_call(condition, code_prefix) or condition}")
            elif line.startswith("pass"):
                pass
            elif line.startswith("#"):
                simplified_code_lines.append(f"{indent}{line.strip('#').strip()}")
            else:
                simplified_code_lines.append(f"{indent}{_from_call(line, code_prefix) or line.strip()}")
        simplified_code = '\n'.join(simplified_code_lines).replace('()', '').upper()
        if class_method:
            simplified_code = simplified_code.replace('SELF.', '')
        return simplified_code
