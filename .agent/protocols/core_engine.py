import json
import os
import sys
import networkx as nx
from datetime import datetime

class NeuralForgeEngine:
    def __init__(self, project_root=None):
        if not project_root or project_root == ".":
            current_dir = os.getcwd()
            if ".agent" in current_dir:
                self.project_root = current_dir.split(".agent")[0]
            else:
                self.project_root = current_dir
        else:
            self.project_root = os.path.abspath(project_root)

        self.agent_dir = os.path.join(self.project_root, ".agent")
        self.memory_dir = os.path.join(self.agent_dir, "memory")
        self.profiles_dir = os.path.join(self.memory_dir, "profiles")
        self.graph_path = os.path.join(self.memory_dir, "core_brain.graphml")
        self.budget_path = os.path.join(self.memory_dir, "budget.json")
        self.workflow_dir = os.path.join(self.agent_dir, "workflows")
        self.identity_dir = os.path.join(self.agent_dir, "identity")
        
        # Global Memory Hub
        self.global_hub_path = r"C:\Users\Gaurav Nagar\.gemini\antigravity\brain\global_neuralforge\master_experience.json"
        
        self.agents = self._load_json(os.path.join(self.profiles_dir, "profiles.json"))
        self.budget = self._load_json(self.budget_path)
        self.graph = self._load_graph()
        
        os.makedirs(os.path.join(self.agent_dir, "logs"), exist_ok=True)

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _load_graph(self):
        if os.path.exists(self.graph_path):
            try:
                return nx.read_graphml(self.graph_path)
            except Exception as e:
                print(f"Error loading graph: {e}")
        return nx.MultiDiGraph()

    def _save_graph(self):
        nx.write_graphml(self.graph, self.graph_path)

    def report_back(self, swarm_id, outcome_summary, technical_findings, tokens=1000, modified_files=None):
        log_path = os.path.join(self.agent_dir, "logs", f"{swarm_id}.json")
        if not os.path.exists(log_path):
            return {"error": f"Swarm task {swarm_id} not found."}
            
        data = self._load_json(log_path)
        data["status"] = "completed"
        data["outcome"] = outcome_summary
        data["findings"] = technical_findings
        if modified_files:
            data["modified_files"] = modified_files
        self._save_json(log_path, data)
        
        leader_id = data["leader"]
        
        # INCREMENTAL SEMANTIC SYNC
        if modified_files:
            from protocols.semantic_indexer import SemanticIndexer
            indexer = SemanticIndexer(self.project_root)
            for file_path in modified_files:
                indexer._index_python_file(os.path.join(self.project_root, file_path))
            indexer.save(self.graph_path)
            self.graph = self._load_graph() # Reload updated graph
        
        # Budget tracking
        start_time = datetime.fromisoformat(data.get("start_time", datetime.now().isoformat()))
        duration = (datetime.now() - start_time).total_seconds()
        budget_report = self.record_budget(swarm_id, tokens, duration)
        
        # Experience Harvesting
        self._add_experience(leader_id, data["task"], outcome_summary, technical_findings)
        
        return {
            "status": "success", 
            "leader": leader_id, 
            "swarm_id": swarm_id, 
            "semantic_sync": "updated" if modified_files else "skipped",
            "budget_report": budget_report
        }

    def boot(self):
        status = {
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "project_root": self.project_root,
            "agent_os": "Semantic Core (v7.0) Active",
            "graph_nodes": self.graph.number_of_nodes(),
            "graph_edges": self.graph.number_of_edges(),
            "budget_status": f"{self.budget.get('total_spend', 0)} Tokens spent"
        }
        return status

    def get_context(self, agent_id, query=None):
        if agent_id not in self.agents:
            return {"error": "Agent not found"}
            
        dept = self.agents[agent_id].get("department", "").lower()
        workflow = self._read_file(os.path.join(self.workflow_dir, f"{dept}.md"))
        
        # High-Fidelity Graph Retrieval
        graph_context = self.graph_retrieval(query) if query else []
        
        return {
            "profile": self.agents[agent_id],
            "semantic_memory": graph_context,
            "workflow": workflow,
            "culture": self._read_file(os.path.join(self.identity_dir, "culture.md")),
            "innovation_mandate": "Always propose a NEW approach first. Use past graph-memory only as a sanity check."
        }

    def graph_retrieval(self, query):
        """Perform a multi-hop traversal on the project brain."""
        if not query:
            return []
            
        keywords = query.lower().split()
        hits = []
        
        # 1. Find Entry Nodes (Keyword match on node ID or attributes)
        for node, attrs in self.graph.nodes(data=True):
            node_text = (str(node) + " " + str(attrs.get('name', ''))).lower()
            if any(kw in node_text for kw in keywords):
                hits.append(node)
        
        # 2. Multi-hop Traversal (Find neighbors up to 2 hops away)
        context_subgraph = []
        for hit in hits:
            # Add the node itself
            context_subgraph.append({"node": hit, "properties": self.graph.nodes[hit]})
            
            # Add neighbors (Relationships)
            for neighbor in self.graph.neighbors(hit):
                edge_data = self.graph.get_edge_data(hit, neighbor)
                context_subgraph.append({
                    "relationship": "DIRECT",
                    "from": hit,
                    "to": neighbor,
                    "details": edge_data
                })
                
        return context_subgraph[:10] # Cap at 10 semantic links for prompt efficiency

    def add_knowledge(self, node_id, node_type, properties, links=None):
        """Allows agents to manually inject 'Ideas' or 'Statuses' into the graph."""
        self.graph.add_node(node_id, type=node_type, **properties)
        if links:
            for target, relation in links.items():
                self.graph.add_edge(node_id, target, relation=relation)
        self._save_graph()
        return True

    def _read_file(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def record_budget(self, task_id, tokens, duration_sec):
        entry = {"task_id": task_id, "tokens": tokens, "duration": duration_sec, "timestamp": datetime.now().isoformat()}
        self.budget.setdefault("task_ledger", []).append(entry)
        self.budget["total_spend"] = self.budget.get("total_spend", 0) + tokens
        self._save_json(self.budget_path, self.budget)
        return {"status": "recorded"}

    def _add_experience(self, leader_id, task, outcome, findings):
        experience_path = os.path.join(self.memory_dir, "experience.json")
        exp_data = self._load_json(experience_path)
        entry = {
            "leader": leader_id,
            "task": task,
            "outcome": outcome,
            "findings": findings,
            "timestamp": datetime.now().isoformat()
        }
        exp_data.setdefault("lessons", []).append(entry)
        self._save_json(experience_path, exp_data)
        
        # Broadcast to Global Hub (Cross-Project Intelligence)
        self._broadcast_to_hub(entry)

    def update_growth(self, agent_id, learning):
        profile_path = os.path.join(self.profiles_dir, "profiles.json")
        profiles = self._load_json(profile_path)
        if agent_id in profiles:
            profiles[agent_id].setdefault("growth_log", []).append({
                "learning": learning,
                "timestamp": datetime.now().isoformat()
            })
            self._save_json(profile_path, profiles)

    def _broadcast_to_hub(self, entry):
        if not os.path.exists(os.path.dirname(self.global_hub_path)):
            os.makedirs(os.path.dirname(self.global_hub_path), exist_ok=True)
            
        hub_data = self._load_json(self.global_hub_path)
        hub_data.setdefault("global_lessons", []).append(entry)
        self._save_json(self.global_hub_path, hub_data)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python core_engine.py <project_root> <command> [args...]")
        sys.exit(1)
    
    project_root = sys.argv[1]
    command = sys.argv[2]
    engine = NeuralForgeEngine(project_root)
    
    if command == "boot":
        print(json.dumps(engine.boot(), indent=2))
    elif command == "get_agent":
        query = sys.argv[4] if len(sys.argv) > 4 else None
        print(json.dumps(engine.get_context(sys.argv[3], query), indent=2))
    elif command == "add_knowledge":
        # python core_engine.py . add_knowledge "NodeID" "Type" '{"prop": "val"}' '{"Target": "Relation"}'
        props = json.loads(sys.argv[5])
        links = json.loads(sys.argv[6]) if len(sys.argv) > 6 else None
        print(json.dumps(engine.add_knowledge(sys.argv[3], sys.argv[4], props, links), indent=2))
