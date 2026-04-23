import json
import logging

import networkx as nx

logger = logging.getLogger(__name__)


class HardwareGraph:
    def __init__(self, log_path: str = "canonical_log.jsonl"):
        self.log_path = log_path
        self.graph = nx.DiGraph()
        self.load_from_log()

    def load_from_log(self):
        """Build the graph from the canonical JSONL log."""
        if not os.path.exists(self.log_path):
            return

        with open(self.log_path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    schema = data.get("_schema")

                    if schema == "BaseEntity":
                        # Add node with properties
                        self.graph.add_node(
                            data["id"],
                            label=data["label"],
                            type=data["type"],
                            properties=data.get("properties", {}),
                        )
                    elif schema == "Edge":
                        # Add edge
                        self.graph.add_edge(
                            data["source_id"],
                            data["target_id"],
                            relationship=data["relationship"],
                            properties=data.get("properties", {}),
                        )
                except Exception as e:
                    logger.error(f"Error parsing log line: {e}")

    def find_signal_path(self, start_label: str, end_label: str) -> list[dict]:
        """Find the path between two components by their labels (e.g. 'R602', 'TR601')."""
        # Find node IDs by label
        start_node = None
        end_node = None

        for n, d in self.graph.nodes(data=True):
            props = d.get("properties", {})
            if props.get("designator") == start_label:
                start_node = n
            if props.get("designator") == end_label:
                end_node = n

        if not start_node or not end_node:
            return []

        try:
            path_ids = nx.shortest_path(self.graph, start_node, end_node)
            path_details = []
            for node_id in path_ids:
                path_details.append(self.graph.nodes[node_id])
            return path_details
        except nx.NetworkXNoPath:
            return []

    def get_neighbors(self, label: str) -> list[dict]:
        """Get all components connected to a specific component."""
        node_id = None
        for n, d in self.graph.nodes(data=True):
            if d.get("properties", {}).get("designator") == label:
                node_id = n
                break

        if not node_id:
            return []

        neighbors = []
        for target_id in self.graph.successors(node_id):
            neighbors.append(self.graph.nodes[target_id])
        for source_id in self.graph.predecessors(node_id):
            neighbors.append(self.graph.nodes[source_id])

        return neighbors


import os
