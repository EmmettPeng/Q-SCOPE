from __future__ import annotations

from typing import Any


SIGNAL_COLORS = (
    "#5f7f67", "#b36b4d", "#6c78a8", "#b08a3e", "#8a6d9c",
    "#4f8587", "#9a6f4b", "#6f8f4f", "#a45f72", "#557a9b",
)


def network_statistics(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    metrics = {
        node["sample_id"]: {
            "sample_id": node["sample_id"],
            "display_name": node["label"],
            "in_degree": 0,
            "out_degree": 0,
            "total_degree": 0,
            "unique_neighbors": 0,
            "self_edge_count": 0,
        }
        for node in nodes
    }
    neighbors: dict[str, set[str]] = {sample_id: set() for sample_id in metrics}
    for edge in edges:
        source = edge["source_sample"]
        target = edge["target_sample"]
        metrics[source]["out_degree"] += 1
        metrics[target]["in_degree"] += 1
        if source == target:
            metrics[source]["self_edge_count"] += 1
        else:
            neighbors[source].add(target)
            neighbors[target].add(source)
    for sample_id, item in metrics.items():
        item["total_degree"] = item["in_degree"] + item["out_degree"]
        item["unique_neighbors"] = len(neighbors[sample_id])
    node_metrics = [metrics[node["sample_id"]] for node in nodes]
    summary = {
        "total_nodes": len(nodes),
        "isolated_nodes": sum(item["total_degree"] == 0 for item in node_metrics),
        "total_edges": len(edges),
        "self_edges": sum(bool(edge["self_communication"]) for edge in edges),
        "non_self_edges": sum(not edge["self_communication"] for edge in edges),
        "pathway_count": len({edge["pathway_id"] for edge in edges}),
        "signal_count": len({edge["signal_name"] for edge in edges}),
    }
    return summary, node_metrics


def build_network(
    database_version_id: str,
    database_source: str,
    sample_names: dict[str, str],
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = [
        {
            "id": f"genome:{sample_id}",
            "kind": "genome",
            "sample_id": sample_id,
            "label": display_name,
        }
        for sample_id, display_name in sample_names.items()
    ]
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for call in capabilities:
        if call["capable"]:
            grouped.setdefault(call["pathway_id"], {"sending": [], "receiving": []})[
                call["role"]
            ].append(call)

    signal_names = sorted(
        {call["signal_name"] for roles in grouped.values() for calls in roles.values() for call in calls}
    )
    color_by_signal = {
        signal_name: SIGNAL_COLORS[index % len(SIGNAL_COLORS)]
        for index, signal_name in enumerate(signal_names)
    }
    edges: list[dict[str, Any]] = []
    for pathway_id, roles in grouped.items():
        for sender in roles["sending"]:
            for receiver in roles["receiving"]:
                source_sample = sender["sample_id"]
                target_sample = receiver["sample_id"]
                references = list(dict.fromkeys(sender.get("references", [])))
                edges.append(
                    {
                        "id": f"communication:{pathway_id}:{source_sample}:{target_sample}",
                        "source": f"genome:{source_sample}",
                        "target": f"genome:{target_sample}",
                        "kind": "potential_communication",
                        "pathway_id": pathway_id,
                        "pathway_name": sender["pathway_name"],
                        "signal_name": sender["signal_name"],
                        "color": color_by_signal[sender["signal_name"]],
                        "database_version_id": database_version_id,
                        "database_source": database_source,
                        "source_sample": source_sample,
                        "source_label": sample_names[source_sample],
                        "target_sample": target_sample,
                        "target_label": sample_names[target_sample],
                        "self_communication": source_sample == target_sample,
                        "evidence_level": "potential_communication",
                        "sender_components": sender["observed_components"],
                        "receiver_components": receiver["observed_components"],
                        "references": references,
                    }
                )
    summary, node_metrics = network_statistics(nodes, edges)
    legend = [
        {
            "signal_name": signal_name,
            "color": color_by_signal[signal_name],
            "pathway_ids": sorted(
                {edge["pathway_id"] for edge in edges if edge["signal_name"] == signal_name}
            ),
        }
        for signal_name in signal_names
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": summary,
        "node_metrics": node_metrics,
        "legend": legend,
    }
