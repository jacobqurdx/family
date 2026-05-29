import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import networkx as nx
from core.schema import SchemaRegistry

st.title("Schema Explorer")
registry = SchemaRegistry()
schema_id = st.selectbox("Select Schema", registry.list_schemas())
schema = registry.get(schema_id)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Elements")
    for el in registry.get_authoring_order(schema_id):
        with st.expander(f"{el.id} ({el.dependency_type.value})"):
            st.write(el.description)
            if el.depends_on:
                st.write(f"**Depends on:** {', '.join(el.depends_on)}")
            if el.inference_rule:
                st.write(f"**Inference:** {el.inference_rule}")

with col2:
    st.subheader("Dependency Graph")
    G = nx.DiGraph()
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
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_text = list(G.nodes())

    fig = go.Figure(
        data=[
            go.Scatter(x=edge_x, y=edge_y, mode='lines',
                       line=dict(width=1, color='#aaa'), hoverinfo='none'),
            go.Scatter(x=node_x, y=node_y, mode='markers+text',
                       text=node_text, textposition="top center",
                       marker=dict(size=12, color='#2E75B6'),
                       textfont=dict(size=11),
                       hoverinfo='text')
        ],
        layout=go.Layout(
            showlegend=False,
            hovermode='closest',
            height=480,
            margin=dict(b=20, l=20, r=20, t=20),
            xaxis=dict(showgrid=False, zeroline=False,
                       showticklabels=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False,
                       showticklabels=False, visible=False),
        )
    )
    st.plotly_chart(fig, use_container_width=True)
