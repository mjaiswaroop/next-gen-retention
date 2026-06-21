"""
components/tab_graph.py
"""
import streamlit as st
import pandas as pd
import requests
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

import networkx as nx
import plotly.graph_objects as go
import numpy as np
from components.utils import dark_chart_layout

def generate_network_plot(nodes_data, links_data):
    if not nodes_data or not links_data:
        return None
        
    G = nx.Graph()
    
    # Add nodes
    for node in nodes_data:
        G.add_node(
            node["user_id"], 
            churn_score=node.get("churn_probability", 0), 
            pagerank=node.get("cascade_risk", 0),
            vip_shield=node.get("vip_shield", False)
        )
        
    # Add edges
    for link in links_data:
        G.add_edge(
            link["source"], 
            link["target"], 
            type=link.get("type", "explicit"),
            confidence=link.get("confidence", 1.0)
        )
    
    # Only layout connected components or main subgraphs if needed, but spring_layout handles it
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    
    edge_x = []
    edge_y = []
    edge_colors = []
    edge_texts = []
    
    # Let's draw explicit and inferred edges differently
    explicit_x, explicit_y = [], []
    inferred_x, inferred_y = [], []
    inferred_texts = []
    inferred_x_mid, inferred_y_mid = [], []
    
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_data = edge[2]
        
        if edge_data.get("type") == "inferred":
            inferred_x.extend([x0, x1, None])
            inferred_y.extend([y0, y1, None])
            inferred_x_mid.append((x0+x1)/2)
            inferred_y_mid.append((y0+y1)/2)
            inferred_texts.append(f"Inferred Edge (Confidence: {edge_data.get('confidence', 0.0):.2f})")
        else:
            explicit_x.extend([x0, x1, None])
            explicit_y.extend([y0, y1, None])

    traces = []
    
    if explicit_x:
        traces.append(go.Scatter(
            x=explicit_x, y=explicit_y,
            line=dict(width=1.5, color='#666'),
            hoverinfo='none',
            mode='lines',
            name='Explicit Edge'
        ))
        
    if inferred_x:
        traces.append(go.Scatter(
            x=inferred_x, y=inferred_y,
            line=dict(width=1, color='#e6a122', dash='dash'),
            hoverinfo='none',
            mode='lines',
            name='Inferred Edge'
        ))
        # Add invisible markers for hover text on inferred edges
        traces.append(go.Scatter(
            x=inferred_x_mid, y=inferred_y_mid,
            mode='markers',
            marker=dict(size=10, color='rgba(0,0,0,0)'),
            hoverinfo='text',
            text=inferred_texts,
            showlegend=False
        ))

    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []
    
    for node_id, data in G.nodes(data=True):
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        
        vip_str = "🛡️ VIP" if data.get("vip_shield") else ""
        node_text.append(f"<b>Customer:</b> {node_id}<br><b>Churn Score:</b> {data.get('churn_score', 0):.2f}<br><b>Cascade Risk:</b> {data.get('pagerank', 0):.4f} {vip_str}")
        
        node_color.append(data.get('churn_score', 0))
        size = 10 + (data.get('pagerank', 0) * 5)
        node_size.append(min(size, 40))

    traces.append(go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        text=node_text,
        marker=dict(
            showscale=True,
            colorscale='YlOrRd',
            reversescale=False,
            color=node_color,
            size=node_size,
            colorbar=dict(
                thickness=15,
                title='Churn Risk',
                xanchor='left',
                titleside='right'
            ),
            line_width=1,
            line_color='white'
        ),
        name='Customer Node'
    ))

    layout = dark_chart_layout()
    layout.update(
        title='Interactive Contagion Network',
        showlegend=True,
        hovermode='closest',
        margin=dict(b=20,l=5,r=5,t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return go.Figure(data=traces, layout=layout)

def render(tenant_id: int):
    st.header("Social Contagion Network")
    st.markdown("Monitor how churn risk propagates through B2B teams and referral networks via Independent Cascade modeling.")
    
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    
    # Config toggles
    st.subheader("Graph Configuration")
    colA, colB = st.columns([1, 2])
    with colA:
        try:
            cfg_resp = requests.get(f"{API_BASE}/api/v1/graph/config", headers=headers)
            if cfg_resp.status_code == 200:
                current_config = cfg_resp.json()
                enable_inferred = st.toggle("Enable Inferred Edges", value=current_config.get("enable_inferred_edges", False), help="Include relationships inferred from shared signals (e.g. payment methods)")
                if enable_inferred != current_config.get("enable_inferred_edges", False):
                    requests.put(f"{API_BASE}/api/v1/graph/config", json={"enable_inferred_edges": enable_inferred}, headers=headers)
                    st.rerun()
        except Exception as e:
            st.error("Failed to load config")
            
    with colB:
        if st.button("Trigger Relationship Inference", type="secondary"):
            with st.spinner("Analyzing signals to infer relationships..."):
                inf_resp = requests.post(f"{API_BASE}/api/v1/graph/infer", headers=headers)
                if inf_resp.status_code == 200:
                    st.success(f"Inference completed! {inf_resp.json().get('inferred_edges_count', 0)} edges inferred.")
                    st.rerun()
    
    st.divider()
    
    try:
        resp = requests.get(f"{API_BASE}/api/v1/graph/contagion-risk", headers=headers)
        if resp.status_code == 200:
            payload = resp.json()
            nodes_data = payload.get("high_risk_nodes", [])
            links_data = payload.get("links", [])
            
            if not nodes_data and not links_data:
                st.info("No network data available. Ensure graph edges have been ingested.")
                return
                
            df = pd.DataFrame(nodes_data)
            
            # KPI Cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Nodes Tracked", len(nodes_data))
            
            if not df.empty:
                col2.metric("Avg Cascade Risk", f"{df['cascade_risk'].mean():.4f}")
                # Use monetary value * cascade risk for total revenue at risk (simplified)
                total_risk = sum([n.get("cascade_risk", 0) * n.get("monetary_value", 0) for n in nodes_data])
                col3.metric("Total Cascade Revenue at Risk", f"${total_risk:,.2f}")
            
            st.divider()
            
            # Graph Visualization
            fig = generate_network_plot(nodes_data, links_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Top Risk Nodes (Centrality & Cascade Effect)")
            st.markdown("Nodes with highest cascade risk score.")
            
            if not df.empty:
                # Format DataFrame for display
                df_display = df.copy()
                if "vip_shield" not in df_display.columns:
                    df_display["vip_shield"] = False
                    
                df_display["monetary_value"] = df_display["monetary_value"].apply(lambda x: f"${x:,.2f}")
                df_display["vip_shield"] = df_display["vip_shield"].apply(lambda x: "🛡️ VIP" if x else "")
                
                st.dataframe(
                    df_display[["user_id", "churn_probability", "cascade_risk", "monetary_value", "vip_shield"]],
                    use_container_width=True,
                    hide_index=True
                )
            
        else:
            st.error("Failed to load contagion risk data.")
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
