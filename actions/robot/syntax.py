import re

LEADING_WHITESPACE_PATTERN = re.compile(r'^(\s+)(.*)$')


def get_first_indent(input_string):
    match = LEADING_WHITESPACE_PATTERN.match(input_string)
    if match:
        return match.groups()
    return '', input_string


class HumanFriendlyPythonSyntaxConverter:
    @staticmethod
    def to_standard_syntax(simplified_code, class_method=False):
        code_prefix = "self." if class_method else ""
        standard_code_lines = []
        lines = simplified_code.lower().split('\n')
        for line in lines:
            indent, line = get_first_indent(line)
            if line.startswith("repeat"):
                times = line.split()[1]
                standard_code_lines.append(f"{indent}for _ in range({times}):")
            elif line.startswith("if"):
                condition = line.split("if")[1].strip()
                if condition.startswith("found"):
                    object_to_find = condition.split("found")[1].strip()
                    standard_code_lines.append(f"{indent}if {code_prefix}found('{object_to_find}'):")
                else:
                    standard_code_lines.append(f"{indent}if {code_prefix}{condition}():")
            elif line.startswith("else"):
                standard_code_lines.append(f"{indent}else:")
            elif line.startswith("while"):
                condition = line.split("while")[1].strip()
                standard_code_lines.append(f"{indent}while {code_prefix}{condition}():")
            elif line.startswith("end"):
                standard_code_lines.append(f"{indent}    pass")
                standard_code_lines.append(f"{indent}# {line}")
            elif line.startswith("find"):
                object_to_find = line.split("find")[1].strip()
                standard_code_lines.append(f"{indent}{code_prefix}find('{object_to_find}')")
            else:
                standard_code_lines.append(f"{indent}{code_prefix}{line.strip()}()")
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
                condition = line.split("if")[1].strip().rstrip(':')
                if condition.startswith(f"{code_prefix}found("):
                    object_to_find = condition.split("found(")[1].split(')')[0].strip('\'').strip('"')
                    simplified_code_lines.append(f"{indent}if found {object_to_find}")
                else:
                    simplified_code_lines.append(f"{indent}if {condition}")
            elif line.startswith("else"):
                simplified_code_lines.append(f"{indent}else")
            elif line.startswith("while"):
                condition = line.split("while")[1].strip().rstrip(':')
                simplified_code_lines.append(f"{indent}while {condition}")
            elif line.startswith("pass"):
                pass
            elif line.startswith("#"):
                simplified_code_lines.append(f"{indent}{line.strip('#').strip()}")
            elif line.startswith(f"{code_prefix}find"):
                object_to_find = line.split("find(")[1].split(')')[0].strip('\'').strip('"')
                simplified_code_lines.append(f"{indent}find {object_to_find}")
            else:
                simplified_code_lines.append(f"{indent}{line.strip()}")
        simplified_code = '\n'.join(simplified_code_lines).replace('()', '').upper()
        if class_method:
            simplified_code = simplified_code.replace('SELF.', '')
        return simplified_code
