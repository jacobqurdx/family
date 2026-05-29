import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import networkx as nx
from core.schema import SchemaRegistry
from core.twin import DigitalTwin
from core.dependency import DependencyGraph
from core.models import DependencyType
import config

st.title("Dependency Graph")
st.caption("Visualize and simulate dependency propagation")

registry = SchemaRegistry()
schema_id = st.selectbox("Select Schema", registry.list_schemas())
schema = registry.get(schema_id)
dep_graph = DependencyGraph(schema)

twin_files = list(Path(config.TWINS_DIR).glob("*.json"))
twin_options = [f.stem for f in twin_files]
twin_id = st.selectbox("Select Twin (for propagation simulation)", twin_options)
twin = DigitalTwin.load(twin_id)

st.subheader("Propagation Simulator")
element_ids = [el.id for el in schema.elements]
selected_element = st.selectbox("If this element changes...", element_ids)
downstream = dep_graph.get_downstream(selected_element)
st.write(f"**{len(downstream)} downstream element(s) affected:** {', '.join(downstream) or 'none'}")

st.divider()
st.subheader("Full Dependency Graph")

G = nx.DiGraph()
color_map = {
    DependencyType.ENFORCED: "#E74C3C",
    DependencyType.REQUIRED: "#F39C12",
    DependencyType.INFORMATIONAL: "#27AE60",
}
element_map = {el.id: el for el in schema.elements}

for el in schema.elements:
    G.add_node(el.id)
    for dep in el.depends_on:
        G.add_edge(dep, el.id)

def hierarchical_layout(G, x_gap=2.5, y_gap=1.8):
    try:
        generations = list(nx.topological_generations(G))
    except nx.NetworkXUnfeasible:
        return nx.spring_layout(G, seed=42)
    pos = {}
    for level, nodes in enumerate(generations):
        nodes = sorted(nodes)
        for i, node in enumerate(nodes):
            pos[node] = (
                (i - (len(nodes) - 1) / 2) * x_gap,
                -level * y_gap,
            )
    return pos

pos = hierarchical_layout(G)

edge_traces = []
for edge in G.edges():
    x0, y0 = pos[edge[0]]
    x1, y1 = pos[edge[1]]
    child_el = element_map.get(edge[1])
    color = color_map.get(child_el.dependency_type, "#888") if child_el else "#888"
    edge_traces.append(go.Scatter(
        x=[x0, x1, None], y=[y0, y1, None],
        mode='lines', line=dict(width=2, color=color),
        hoverinfo='none', showlegend=False
    ))

highlight = set([selected_element] + downstream)
node_colors = ["#E74C3C" if n == selected_element
               else "#F39C12" if n in downstream
               else "#2E75B6" for n in G.nodes()]

node_trace = go.Scatter(
    x=[pos[n][0] for n in G.nodes()],
    y=[pos[n][1] for n in G.nodes()],
    mode='markers+text',
    text=list(G.nodes()),
    textposition="top center",
    marker=dict(size=14, color=node_colors),
    hoverinfo='text'
)

legend_traces = [
    go.Scatter(x=[None], y=[None], mode='lines',
               line=dict(color=c, width=3), name=t)
    for t, c in [("enforced", "#E74C3C"), ("required", "#F39C12"), ("informational", "#27AE60")]
]

fig = go.Figure(
    data=edge_traces + [node_trace] + legend_traces,
    layout=go.Layout(
        showlegend=True,
        hovermode='closest',
        height=520,
        margin=dict(b=20, l=20, r=20, t=20),
        xaxis=dict(showgrid=False, zeroline=False,
                   showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False,
                   showticklabels=False, visible=False),
        legend=dict(title="Edge type")
    )
)
st.plotly_chart(fig, use_container_width=True)
st.caption("Red node = selected element. Orange nodes = downstream affected.")
