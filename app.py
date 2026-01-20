import ast
import subprocess
import tempfile
import os
import time
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_code():
    data = request.json
    code = data['code']
    user_inputs = data.get('inputs', [])
    output = ""
    error = ""
    trace = []
    time_complexity = "Unknown"
    execution_time = 0
    temp = None

    try:
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as temp_file:
            temp = temp_file.name
            temp_file.write(code)
            temp_file.flush()

        # Capture start time
        start_time = time.time()

        # Run the code
        result = subprocess.run(
            ['python', temp],
            input='\n'.join(user_inputs).encode(),
            capture_output=True,
            timeout=10  # prevent infinite loops
        )

        output = result.stdout.decode()
        error = result.stderr.decode()

        # Capture end time
        execution_time = time.time() - start_time

        # Generate trace with input substitutions
        trace = generate_trace(code, user_inputs)

        # Estimate time complexity
        time_complexity = estimate_time_complexity(code)

    except subprocess.TimeoutExpired:
        output = ''
        error = 'Execution timed out.'
    except Exception as e:
        output = ''
        error = f"Error: {str(e)}"
    finally:
        if temp:
            try:
                os.remove(temp)
            except Exception:
                pass

    return jsonify({
        'output': output.strip(),
        'error': error.strip(),
        'trace': trace if trace else [{'type': 'info', 'content': 'No trace available.'}],
        'time_complexity': time_complexity,
        'execution_time': round(execution_time, 4)
    })


def generate_trace(code, user_inputs=None):
    """
    Very clean trace: Only variable = value when assigned and print outputs.
    Substitute real input values properly.
    """
    class SimpleTracer(ast.NodeVisitor):
        def __init__(self, inputs):
            self.steps = []
            self.variables = {}
            self.inputs = inputs or []
            self.input_counter = 0

        def visit_Assign(self, node):
            if isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id

                # Handle input assignment
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                    func_name = node.value.func.id
                    if func_name == 'input':
                        value = self.get_next_input()
                        self.variables[var_name] = value
                        self.steps.append({'type': 'assign', 'content': f"{var_name} = '{value}'"})
                        return
                    elif func_name == 'int':
                        # int(input())
                        if node.value.args and isinstance(node.value.args[0], ast.Call):
                            inner_func = node.value.args[0].func.id
                            if inner_func == 'input':
                                value = self.get_next_input()
                                try:
                                    value = int(value)
                                except:
                                    value = 'error'
                                self.variables[var_name] = value
                                self.steps.append({'type': 'assign', 'content': f"{var_name} = {value}"})
                                return

                # Evaluate normal assignment
                value = self.evaluate(node.value)
                self.variables[var_name] = value
                self.steps.append({'type': 'assign', 'content': f"{var_name} = {value}"})

        def visit_Expr(self, node):
            # Handle print statements
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id == 'print':
                    parts = []
                    for arg in node.value.args:
                        parts.append(str(self.evaluate(arg)))
                    output = ' '.join(parts)
                    self.steps.append({'type': 'print', 'content': output})

        def visit_If(self, node):
            # Handle conditional statements
            test_result = self.evaluate(node.test)
            self.steps.append({'type': 'if', 'content': f"if {test_result}:"})
            for body_node in node.body:
                self.visit(body_node)

        def visit_For(self, node):
            # Handle for loops
            target = node.target.id
            iter_obj = self.evaluate(node.iter)
            self.steps.append({'type': 'for', 'content': f"for {target} in {iter_obj}:"})

            # Create a list of values to iterate over
            if isinstance(iter_obj, list):
                for value in iter_obj:
                    self.variables[target] = value
                    self.steps.append({'type': 'assign', 'content': f"{target} = {value}"})
                    for body_node in node.body:
                        self.visit(body_node)
                    # Ensure the loop variable `i` is printed in every iteration
                    if target == 'i':
                        self.steps.append({'type': 'print', 'content': f"Print i: {value}"})

        def visit_While(self, node):
            # Handle while loops
            test_result = self.evaluate(node.test)
            self.steps.append({'type': 'while', 'content': f"while {test_result}:"})
            while test_result:
                for body_node in node.body:
                    self.visit(body_node)
                test_result = self.evaluate(node.test)

        def get_next_input(self):
            if self.input_counter < len(self.inputs):
                val = self.inputs[self.input_counter]
                self.input_counter += 1
                return val
            return "input_missing"

        def evaluate(self, node):
            try:
                if isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.Name):
                    return self.variables.get(node.id, f"<unresolved {node.id}>")
                elif isinstance(node, ast.BinOp):
                    left = self.evaluate(node.left)
                    right = self.evaluate(node.right)
                    op = self.operator_symbol(node.op)
                    try:
                        return eval(f"{repr(left)} {op} {repr(right)}")
                    except:
                        return f"({left} {op} {right})"
                elif isinstance(node, ast.List):
                    return [self.evaluate(elt) for elt in node.elts]
                elif isinstance(node, ast.Dict):
                    return {self.evaluate(key): self.evaluate(value) for key, value in zip(node.keys, node.values)}
                elif isinstance(node, ast.Subscript):
                    value = self.evaluate(node.value)
                    index = self.evaluate(node.slice)
                    if isinstance(value, list) and isinstance(index, int):
                        try:
                            return value[index]
                        except IndexError:
                            return "<index_error>"
                    else:
                        return "<complex_subscript>"
                elif isinstance(node, ast.Index):
                    return self.evaluate(node.value)
                elif isinstance(node, ast.Call):
                    func_name = node.func.id if isinstance(node.func, ast.Name) else "<unknown>"
                    args = [self.evaluate(arg) for arg in node.args]
                    return f"{func_name}({', '.join(map(str, args))})"
                else:
                    return "<complex_expression>"
            except Exception as e:
                return f"<error {str(e)}>"

        def operator_symbol(self, op):
            if isinstance(op, ast.Add):
                return '+'
            if isinstance(op, ast.Sub):
                return '-'
            if isinstance(op, ast.Mult):
                return '*'
            if isinstance(op, ast.Div):
                return '/'
            if isinstance(op, ast.FloorDiv):
                return '//'
            if isinstance(op, ast.Mod):
                return '%'
            if isinstance(op, ast.Pow):
                return '**'
            return '?'

    try:
        tree = ast.parse(code)
        tracer = SimpleTracer(user_inputs)
        tracer.visit(tree)
        return tracer.steps
    except Exception as e:
        return [{'type': 'error', 'content': f"Error generating trace: {str(e)}"}]


def estimate_time_complexity(code):
    """
    Improved estimator for time complexity based on simple AST structure analysis.
    """
    try:
        tree = ast.parse(code)
        loop_depth = 0

        def analyze(node, current_depth=0):
            nonlocal loop_depth
            if isinstance(node, (ast.For, ast.While)):
                current_depth += 1
                loop_depth = max(loop_depth, current_depth)
            for child in ast.iter_child_nodes(node):
                analyze(child, current_depth)

        analyze(tree)

        if loop_depth == 0:
            return "O(1)"  # No loops
        elif loop_depth == 1:
            return "O(n)"  # Single loop
        elif loop_depth == 2:
            return "O(n^2)"  # Nested loop
        elif loop_depth == 3:
            return "O(n^3)"  # Triple nested loop
        else:
            return f"O(n^{loop_depth})"  # Higher nesting
    except Exception as e:
        return "O(?)"  # If parsing fails

if __name__ == '__main__':
    app.run(debug=True)
