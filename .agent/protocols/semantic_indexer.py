import os
import ast
import networkx as nx
from datetime import datetime

class SemanticIndexer:
    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)
        self.graph = nx.MultiDiGraph()
        self.ignore_dirs = {'.git', '.agent', '__pycache__', 'node_modules', 'venv', '.venv', '.uv-python', 'tools'}

    def scan(self):
        print(f"Starting Semantic Scan of {self.project_root}...")
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    self._index_python_file(os.path.join(root, file))
        
        print(f"Scan complete. Nodes: {self.graph.number_of_nodes()}, Edges: {self.graph.number_of_edges()}")

    def _index_python_file(self, file_path):
        rel_path = os.path.relpath(file_path, self.project_root)
        self.graph.add_node(rel_path, type='file', last_indexed=datetime.now().isoformat())

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
                
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_id = f"{rel_path}::{node.name}"
                    self.graph.add_node(class_id, type='class', name=node.name, file=rel_path)
                    self.graph.add_edge(rel_path, class_id, relation='contains')
                    
                elif isinstance(node, ast.FunctionDef):
                    func_id = f"{rel_path}::{node.name}"
                    self.graph.add_node(func_id, type='function', name=node.name, file=rel_path)
                    self.graph.add_edge(rel_path, func_id, relation='contains')
                    
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Simplified import tracking
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.graph.add_edge(rel_path, alias.name, relation='imports')
                    else:
                        module = node.module or ""
                        self.graph.add_edge(rel_path, module, relation='imports')

        except Exception as e:
            print(f"Error indexing {rel_path}: {e}")

    def save(self, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        nx.write_graphml(self.graph, output_path)
        print(f"Project Brain saved to {output_path}")

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    indexer = SemanticIndexer(root)
    indexer.scan()
    indexer.save(os.path.join(root, ".agent", "memory", "core_brain.graphml"))
