"""
Knowledge Graph Visualization Utility.

Generates an interactive HTML visualization of the knowledge graph
using D3.js force-directed graph layout.

Usage:
    # From CLI
    alita inventory visualize --graph ./graph.json --output ./graph.html
    
    # From Python
    from alita_sdk.community.inventory.visualize import generate_visualization
    generate_visualization("./graph.json", "./graph.html")
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Color palette for entity types based on ENTITY_TAXONOMY layers
# Each layer has its own distinct hue range to prevent overlap
TYPE_COLORS = {
    # =========================================================================
    # PRODUCT LAYER - Red/Pink/Orange hues (0-30° and 330-360°)
    # =========================================================================
    "epic": "#D32F2F",              # Deep Red
    "feature": "#E53935",           # Red
    "user_story": "#F44336",        # Lighter Red
    "screen": "#FF5722",            # Deep Orange
    "ux_flow": "#FF7043",           # Orange
    "ui_component": "#FF8A65",      # Light Orange
    "ui_field": "#FFAB91",          # Peach
    
    # =========================================================================
    # DOMAIN LAYER - Green hues (90-150°)
    # =========================================================================
    "domain_entity": "#2E7D32",     # Dark Green
    "attribute": "#388E3C",         # Green
    "business_rule": "#43A047",     # Medium Green
    "business_event": "#4CAF50",    # Light Green
    "glossary_term": "#66BB6A",     # Pale Green
    "workflow": "#81C784",          # Very Light Green
    
    # =========================================================================
    # SERVICE LAYER - Cyan/Teal hues (160-200°)
    # =========================================================================
    "service": "#00695C",           # Dark Teal
    "api": "#00796B",               # Teal
    "endpoint": "#00897B",          # Medium Teal
    "payload": "#009688",           # Light Teal
    "integration": "#26A69A",       # Pale Teal
    
    # =========================================================================
    # CODE LAYER - Blue hues (200-240°)
    # =========================================================================
    "module": "#1565C0",            # Dark Blue
    "class": "#1976D2",             # Blue
    "function": "#1E88E5",          # Medium Blue
    "interface": "#2196F3",         # Light Blue
    "constant": "#42A5F5",          # Pale Blue
    "configuration": "#64B5F6",     # Very Light Blue
    
    # =========================================================================
    # DATA LAYER - Brown/Amber hues (30-60°)
    # =========================================================================
    "database": "#E65100",          # Dark Orange/Brown
    "table": "#EF6C00",             # Orange
    "column": "#F57C00",            # Medium Orange
    "constraint": "#FB8C00",        # Light Orange
    "index": "#FF9800",             # Amber
    "migration": "#FFA726",         # Light Amber
    "enum": "#FFB74D",              # Pale Amber
    
    # =========================================================================
    # TESTING LAYER - Purple/Violet hues (260-290°)
    # =========================================================================
    "test_suite": "#4527A0",        # Deep Purple
    "test_case": "#512DA8",         # Dark Purple
    "test_step": "#5E35B1",         # Purple
    "assertion": "#673AB7",         # Medium Purple
    "test_data": "#7E57C2",         # Light Purple
    "defect": "#B71C1C",            # Dark Red (stands out - critical)
    "incident": "#C62828",          # Red (stands out - critical)
    
    # =========================================================================
    # DELIVERY LAYER - Lime/Yellow-Green hues (60-90°)
    # =========================================================================
    "release": "#827717",           # Dark Lime
    "sprint": "#9E9D24",            # Olive
    "commit": "#AFB42B",            # Lime
    "pull_request": "#C0CA33",      # Light Lime
    "ticket": "#CDDC39",            # Yellow-Lime
    "deployment": "#D4E157",        # Pale Lime
    
    # =========================================================================
    # ORGANIZATION LAYER - Magenta/Pink hues (290-330°)
    # =========================================================================
    "team": "#AD1457",              # Dark Magenta
    "owner": "#C2185B",             # Magenta
    "stakeholder": "#D81B60",       # Pink-Magenta
    "repository": "#E91E63",        # Pink
    "documentation": "#EC407A",     # Light Pink
    
    # =========================================================================
    # GENERIC/COMMON TYPES - Distinct colors for frequently used types
    # =========================================================================
    # Documents & Content
    "document": "#5C6BC0",          # Indigo
    "section": "#7986CB",           # Light Indigo
    "chapter": "#9FA8DA",           # Pale Indigo
    "paragraph": "#C5CAE9",         # Very Light Indigo
    "text": "#E8EAF6",              # Faint Indigo
    
    # Process & Actions
    "process": "#00ACC1",           # Cyan
    "action": "#26C6DA",            # Light Cyan
    "step": "#4DD0E1",              # Pale Cyan
    "task": "#80DEEA",              # Very Light Cyan
    "activity": "#B2EBF2",          # Faint Cyan
    
    # Tools & Scripts
    "tool": "#8D6E63",              # Brown
    "toolkit": "#A1887F",           # Light Brown
    "script": "#BCAAA4",            # Pale Brown
    "utility": "#D7CCC8",           # Very Light Brown
    "mcp_server": "#6D4C41",        # Dark Brown (MCP)
    "mcp_tool": "#795548",          # Medium Brown (MCP)
    "mcp_resource": "#8D6E63",      # Brown (MCP)
    "connector": "#5D4037",         # Deep Brown
    
    # Structure & Organization
    "structure": "#78909C",         # Blue Grey
    "component": "#90A4AE",         # Light Blue Grey
    "element": "#B0BEC5",           # Pale Blue Grey
    "item": "#CFD8DC",              # Very Light Blue Grey
    
    # Resources & References
    "resource": "#546E7A",          # Dark Blue Grey
    "reference": "#607D8B",         # Blue Grey
    "link": "#78909C",              # Light Blue Grey
    
    # Requirements & Specs
    "requirement": "#F06292",       # Pink
    "specification": "#F48FB1",     # Light Pink
    "criteria": "#F8BBD9",          # Pale Pink
    
    # Issues & Problems
    "issue": "#EF5350",             # Red
    "bug": "#E57373",               # Light Red
    "error": "#EF9A9A",             # Pale Red
    "problem": "#FFCDD2",           # Very Light Red
    "troubleshooting": "#FFEBEE",   # Faint Red
    
    # States & Status
    "state": "#AB47BC",             # Purple
    "status": "#BA68C8",            # Light Purple
    "condition": "#CE93D8",         # Pale Purple
    
    # Misc common types
    "entity": "#26A69A",            # Teal
    "object": "#4DB6AC",            # Light Teal
    "concept": "#80CBC4",           # Pale Teal
    "idea": "#B2DFDB",              # Very Light Teal
    
    "checklist": "#FFD54F",         # Amber
    "list": "#FFE082",              # Light Amber
    "collection": "#FFECB3",        # Pale Amber
    
    "project": "#7B1FA2",           # Deep Purple
    "program": "#8E24AA",           # Purple
    "initiative": "#9C27B0",        # Light Purple
    
    "platform": "#0097A7",          # Dark Cyan
    "system": "#00ACC1",            # Cyan
    "application": "#00BCD4",       # Light Cyan
    "app": "#26C6DA",               # Pale Cyan
    
    "value": "#689F38",             # Light Green
    "property": "#7CB342",          # Pale Green
    "setting": "#8BC34A",           # Very Light Green
    
    "agent": "#FF7043",             # Deep Orange
    "agent_type": "#FF8A65",        # Orange
    "bot": "#FFAB91",               # Light Orange
    
    "category": "#5D4037",          # Brown
    "type": "#6D4C41",              # Light Brown
    "kind": "#795548",              # Medium Brown
    "group": "#8D6E63",             # Pale Brown
    
    "file": "#455A64",              # Dark Blue Grey
    "folder": "#546E7A",            # Blue Grey
    "directory": "#607D8B",         # Light Blue Grey
    "path": "#78909C",              # Pale Blue Grey
    
    "method": "#1E88E5",            # Blue (code related)
    "parameter": "#42A5F5",         # Light Blue
    "argument": "#64B5F6",          # Pale Blue
    "variable": "#90CAF9",          # Very Light Blue
    
    "event": "#7E57C2",             # Purple
    "trigger": "#9575CD",           # Light Purple
    "handler": "#B39DDB",           # Pale Purple
    "callback": "#D1C4E9",          # Very Light Purple
    
    "rule": "#43A047",              # Green (business related)
    "policy": "#66BB6A",            # Light Green
    "guideline": "#81C784",         # Pale Green
    "standard": "#A5D6A7",          # Very Light Green
    
    "user": "#EC407A",              # Pink (organization related)
    "role": "#F06292",              # Light Pink
    "permission": "#F48FB1",        # Pale Pink
    "access": "#F8BBD9",            # Very Light Pink
    
    # Default fallback
    "default": "#9E9E9E",           # Grey
}

# Relation type colors
RELATION_COLORS = {
    "contains": "#4CAF50",
    "extends": "#2196F3",
    "implements": "#9C27B0",
    "imports": "#FF9800",
    "calls": "#F44336",
    "triggers": "#E91E63",
    "depends_on": "#673AB7",
    "uses": "#00BCD4",
    "stores_in": "#795548",
    "reads_from": "#607D8B",
    "transforms": "#FFC107",
    "maps_to": "#8BC34A",
    "default": "#9E9E9E",
}


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knowledge Graph Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
        }
        
        #container {
            display: flex;
            height: 100vh;
        }
        
        #graph-container {
            flex: 1;
            position: relative;
        }
        
        #sidebar {
            width: 350px;
            background: #16213e;
            border-left: 1px solid #0f3460;
            padding: 20px;
            overflow-y: auto;
        }
        
        #controls {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(22, 33, 62, 0.95);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #0f3460;
            z-index: 100;
        }
        
        #controls h3 {
            margin-bottom: 10px;
            color: #e94560;
        }
        
        #controls label {
            display: block;
            margin: 8px 0;
            font-size: 13px;
        }
        
        #controls input[type="range"] {
            width: 150px;
            margin-left: 10px;
        }
        
        #controls input[type="text"] {
            width: 200px;
            padding: 5px 10px;
            border: 1px solid #0f3460;
            background: #1a1a2e;
            color: #eee;
            border-radius: 4px;
        }
        
        #search-results {
            margin-top: 10px;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .search-result {
            padding: 5px 10px;
            cursor: pointer;
            border-radius: 4px;
            margin: 2px 0;
        }
        
        .search-result:hover {
            background: #0f3460;
        }
        
        #sidebar h2 {
            color: #e94560;
            margin-bottom: 15px;
            border-bottom: 1px solid #0f3460;
            padding-bottom: 10px;
        }
        
        #sidebar h3 {
            color: #eee;
            margin: 15px 0 10px;
            font-size: 14px;
        }
        
        #entity-details {
            font-size: 13px;
            line-height: 1.6;
        }
        
        .detail-label {
            color: #888;
            font-size: 11px;
            text-transform: uppercase;
            margin-top: 10px;
        }
        
        .detail-value {
            color: #eee;
            word-break: break-word;
        }
        
        .entity-type-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .citation-link {
            color: #64b5f6;
            text-decoration: none;
            font-family: monospace;
            font-size: 12px;
        }
        
        .citation-link:hover {
            text-decoration: underline;
        }
        
        /* Context Menu */
        #context-menu {
            display: none;
            position: fixed;
            background: #1a1a2e;
            border: 1px solid #0f3460;
            border-radius: 6px;
            padding: 5px 0;
            min-width: 180px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            z-index: 1000;
        }
        
        .context-menu-item {
            padding: 8px 15px;
            cursor: pointer;
            color: #eee;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .context-menu-item:hover {
            background: #0f3460;
        }
        
        .context-menu-item.danger {
            color: #e94560;
        }
        
        .context-menu-separator {
            height: 1px;
            background: #0f3460;
            margin: 5px 0;
        }
        
        /* Focus Mode Styling */
        .node.faded circle {
            opacity: 0.1;
        }
        
        .node.faded text {
            opacity: 0.1;
        }
        
        .link.faded {
            opacity: 0.05;
        }
        
        .node.focused circle {
            stroke: #e94560;
            stroke-width: 3px;
        }
        
        .node.neighbor circle {
            stroke: #64b5f6;
            stroke-width: 2px;
        }
        
        /* Focus Mode Banner */
        #focus-banner {
            display: none;
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: #e94560;
            color: white;
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 13px;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        #focus-banner button {
            background: white;
            color: #e94560;
            border: none;
            padding: 3px 10px;
            border-radius: 10px;
            margin-left: 10px;
            cursor: pointer;
            font-weight: 600;
        }
        
        #legend {
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #0f3460;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
        }
        
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        #stats {
            background: #0f3460;
            padding: 10px 15px;
            border-radius: 6px;
            margin-bottom: 15px;
        }
        
        #stats span {
            display: inline-block;
            margin-right: 15px;
        }
        
        .stat-value {
            color: #e94560;
            font-weight: 600;
        }
        
        svg {
            width: 100%;
            height: 100%;
        }
        
        .node {
            cursor: pointer;
        }
        
        .node circle {
            stroke: #fff;
            stroke-width: 1.5px;
            transition: r 0.2s;
        }
        
        .node:hover circle {
            stroke-width: 3px;
        }
        
        .node.selected circle {
            stroke: #e94560;
            stroke-width: 3px;
        }
        
        .node text {
            font-size: 10px;
            fill: #ccc;
            pointer-events: none;
        }
        
        .link {
            stroke-opacity: 0.4;
            stroke-width: 1.5px;
        }
        
        .link:hover {
            stroke-opacity: 1;
        }
        
        .link-label {
            font-size: 9px;
            fill: #888;
        }
        
        /* Tooltip */
        .tooltip {
            position: absolute;
            background: rgba(22, 33, 62, 0.95);
            border: 1px solid #0f3460;
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            max-width: 300px;
        }
        
        .tooltip h4 {
            color: #e94560;
            margin-bottom: 5px;
        }
        
        /* Filter panel */
        #type-filters {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 10px;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 5px;
        }
        
        #type-filter-controls {
            display: flex;
            gap: 5px;
            margin-bottom: 8px;
        }
        
        #type-filter-controls button {
            flex: 1;
            padding: 4px 8px;
            font-size: 11px;
            cursor: pointer;
            background: #333;
            color: #fff;
            border: 1px solid #555;
            border-radius: 3px;
        }
        
        #type-filter-controls button:hover {
            background: #444;
        }
        
        #type-filter-search {
            width: 100%;
            padding: 5px;
            margin-bottom: 8px;
            background: #1a1a2e;
            color: #fff;
            border: 1px solid #333;
            border-radius: 3px;
            font-size: 12px;
        }
        
        .type-filter {
            display: flex;
            align-items: center;
            margin: 3px 0;
            font-size: 12px;
        }
        
        .type-filter input {
            margin-right: 8px;
        }
        
        .type-filter .count {
            color: #888;
            margin-left: auto;
        }
        
        .type-filter.hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="graph-container">
            <div id="controls">
                <h3>🔍 Search & Filter</h3>
                <input type="text" id="search-input" placeholder="Search entities...">
                <div id="search-results"></div>
                
                <h3 style="margin-top: 15px;">⚙️ Layout</h3>
                <label>
                    Link Distance
                    <input type="range" id="link-distance" min="50" max="300" value="120">
                </label>
                <label>
                    Charge Strength
                    <input type="range" id="charge-strength" min="-500" max="-50" value="-200">
                </label>
                <label>
                    <input type="checkbox" id="show-labels" checked> Show Labels
                </label>
                <label>
                    <input type="checkbox" id="show-orphans" checked> Show Orphan Nodes
                </label>
                
                <h3 style="margin-top: 15px;">📊 Filter by Type <span id="type-count-display" style="color: #888; font-size: 12px;"></span></h3>
                <input type="text" id="type-filter-search" placeholder="Search types...">
                <div id="type-filter-controls">
                    <button id="select-all-types">All</button>
                    <button id="select-none-types">None</button>
                    <button id="select-top10-types">Top 10</button>
                </div>
                <div id="type-filters"></div>
            </div>
            <svg id="graph"></svg>
        </div>
        
        <div id="sidebar">
            <h2>📋 Entity Details</h2>
            <div id="stats">
                <span>Entities: <span class="stat-value" id="entity-count">0</span></span>
                <span>Relations: <span class="stat-value" id="relation-count">0</span></span>
            </div>
            <div id="entity-details">
                <p style="color: #888;">Click on a node to see details</p>
            </div>
            <div id="legend">
                <h3>🎨 Legend</h3>
                <div id="legend-items"></div>
            </div>
        </div>
    </div>
    
    <div class="tooltip" id="tooltip" style="display: none;"></div>
    
    <!-- Context Menu -->
    <div id="context-menu">
        <div class="context-menu-item" id="ctx-focus-1">🔍 Focus 1 level</div>
        <div class="context-menu-item" id="ctx-focus-2">🔍 Focus 2 levels</div>
        <div class="context-menu-item" id="ctx-focus-3">🔍 Focus 3 levels</div>
        <div class="context-menu-item" id="ctx-focus-5">🔍 Focus 5 levels</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" id="ctx-expand">📈 Expand neighbors</div>
        <div class="context-menu-item" id="ctx-hide">👁️ Hide this node</div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item danger" id="ctx-reset">✖ Clear focus</div>
    </div>
    
    <!-- Focus Mode Banner -->
    <div id="focus-banner">
        <span id="focus-info">Focus mode: showing X levels from "Node"</span>
        <button id="clear-focus">Clear Focus</button>
    </div>
    
    <script>
        // Graph data injected from Python
        const graphData = GRAPH_DATA_PLACEHOLDER;
        const typeColors = TYPE_COLORS_PLACEHOLDER;
        const relationColors = RELATION_COLORS_PLACEHOLDER;
        
        // Process data
        const nodes = graphData.nodes.map(n => {
            // Handle both 'citations' (list) and legacy 'citation' (single)
            let citations = n.citations || [];
            if (n.citation && !citations.length) {
                citations = [n.citation];
            }
            // Get file_path from first citation if not on node directly
            const file_path = n.file_path || (citations[0] ? citations[0].file_path : null);
            
            return {
                id: n.id,
                name: n.name,
                type: n.type,
                citations: citations,
                properties: n.properties || {},
                source_toolkit: n.source_toolkit || (citations[0] ? citations[0].source_toolkit : null),
                file_path: file_path
            };
        });
        
        const links = graphData.links.map(l => ({
            source: l.source,
            target: l.target,
            type: l.relation_type || 'related',
            source_toolkit: l.source_toolkit,
            discovered_in_file: l.discovered_in_file,
            ...l
        }));
        
        // Update stats
        document.getElementById('entity-count').textContent = nodes.length;
        document.getElementById('relation-count').textContent = links.length;
        
        // Count types
        const typeCounts = {};
        nodes.forEach(n => {
            typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
        });
        
        // Build type filters
        const typeFiltersDiv = document.getElementById('type-filters');
        const enabledTypes = new Set(Object.keys(typeCounts));
        const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
        
        // Display type count
        document.getElementById('type-count-display').textContent = `(${sortedTypes.length} types)`;
        
        sortedTypes.forEach(([type, count]) => {
                const div = document.createElement('div');
                div.className = 'type-filter';
                div.dataset.typeName = type.toLowerCase();
                div.innerHTML = `
                    <input type="checkbox" checked data-type="${type}">
                    <span class="legend-color" style="background: ${getColor(type)}"></span>
                    ${type}
                    <span class="count">${count}</span>
                `;
                typeFiltersDiv.appendChild(div);
            });
        
        // Type filter search
        document.getElementById('type-filter-search').addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            document.querySelectorAll('.type-filter').forEach(div => {
                const typeName = div.dataset.typeName;
                div.classList.toggle('hidden', !typeName.includes(searchTerm));
            });
        });
        
        // Select all/none/top10 buttons
        function updateGraphVisibility() {
            node.style('display', d => enabledTypes.has(d.type) ? 'block' : 'none');
            link.style('display', d => {
                const sourceType = typeof d.source === 'object' ? d.source.type : nodes.find(n => n.id === d.source)?.type;
                const targetType = typeof d.target === 'object' ? d.target.type : nodes.find(n => n.id === d.target)?.type;
                return enabledTypes.has(sourceType) && enabledTypes.has(targetType) ? 'block' : 'none';
            });
        }
        
        document.getElementById('select-all-types').addEventListener('click', () => {
            document.querySelectorAll('.type-filter input[type="checkbox"]').forEach(cb => {
                cb.checked = true;
                enabledTypes.add(cb.dataset.type);
            });
            updateGraphVisibility();
        });
        
        document.getElementById('select-none-types').addEventListener('click', () => {
            document.querySelectorAll('.type-filter input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
                enabledTypes.delete(cb.dataset.type);
            });
            updateGraphVisibility();
        });
        
        document.getElementById('select-top10-types').addEventListener('click', () => {
            const top10Types = new Set(sortedTypes.slice(0, 10).map(([type]) => type));
            document.querySelectorAll('.type-filter input[type="checkbox"]').forEach(cb => {
                const isTop10 = top10Types.has(cb.dataset.type);
                cb.checked = isTop10;
                if (isTop10) {
                    enabledTypes.add(cb.dataset.type);
                } else {
                    enabledTypes.delete(cb.dataset.type);
                }
            });
            updateGraphVisibility();
        });
        
        // Build legend
        const legendDiv = document.getElementById('legend-items');
        Object.entries(typeCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .forEach(([type, count]) => {
                const div = document.createElement('div');
                div.className = 'legend-item';
                div.innerHTML = `
                    <span class="legend-color" style="background: ${getColor(type)}"></span>
                    ${type} (${count})
                `;
                legendDiv.appendChild(div);
            });
        
        // Generate a consistent color from a string hash (fallback for unknown types)
        function stringToColor(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            // Use golden ratio to spread hues evenly, avoiding muddy colors
            const h = Math.abs(hash * 137.508) % 360;
            const s = 55 + (Math.abs(hash >> 8) % 25); // 55-80% saturation
            const l = 45 + (Math.abs(hash >> 16) % 20); // 45-65% lightness
            return `hsl(${h}, ${s}%, ${l}%)`;
        }
        
        function getColor(type) {
            // First try exact match in predefined colors
            if (typeColors[type]) return typeColors[type];
            // Try lowercase match
            const lower = type.toLowerCase();
            if (typeColors[lower]) return typeColors[lower];
            // Try with underscores/spaces/dashes replaced (e.g., "UserStory" -> "userstory")
            const normalized = lower.replace(/[_\\s-]/g, '');
            for (const [key, color] of Object.entries(typeColors)) {
                if (key.toLowerCase().replace(/[_\\s-]/g, '') === normalized) {
                    return color;
                }
            }
            // Fallback: generate consistent color from type name
            return stringToColor(type);
        }
        
        function getRelationColor(type) {
            return relationColors[type] || relationColors['default'];
        }
        
        // SVG setup
        const svg = d3.select('#graph');
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        svg.attr('viewBox', [0, 0, width, height]);
        
        // Create zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });
        
        svg.call(zoom);
        
        // Main group for zoom/pan
        const g = svg.append('g');
        
        // Arrow markers for directed edges
        svg.append('defs').selectAll('marker')
            .data(['arrow'])
            .join('marker')
            .attr('id', d => d)
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('fill', '#888')
            .attr('d', 'M0,-5L10,0L0,5');
        
        // Force simulation
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(120))
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(30));
        
        // Draw links
        const link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('class', 'link')
            .attr('stroke', d => getRelationColor(d.type))
            .attr('marker-end', 'url(#arrow)')
            .on('mouseover', function(event, d) {
                // Show tooltip for relations
                tooltip
                    .style('display', 'block')
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY + 10) + 'px')
                    .html(`
                        <h4>${d.type}</h4>
                        ${d.source_toolkit ? `<div><strong>Source:</strong> ${d.source_toolkit}</div>` : ''}
                        ${d.discovered_in_file ? `<div><strong>File:</strong> ${d.discovered_in_file}</div>` : ''}
                        ${d.confidence ? `<div><strong>Confidence:</strong> ${(d.confidence * 100).toFixed(0)}%</div>` : ''}
                    `);
                // Highlight the link
                d3.select(this).attr('stroke-width', 3).attr('stroke-opacity', 1);
            })
            .on('mouseout', function() {
                tooltip.style('display', 'none');
                // Reset link appearance
                d3.select(this).attr('stroke-width', 1.5).attr('stroke-opacity', 0.4);
            });
        
        // Draw nodes
        const node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(nodes)
            .join('g')
            .attr('class', 'node')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));
        
        // Node circles
        node.append('circle')
            .attr('r', d => 8 + Math.min(5, (typeCounts[d.type] || 1) / 2))
            .attr('fill', d => getColor(d.type));
        
        // Node labels
        const labels = node.append('text')
            .attr('dx', 12)
            .attr('dy', 4)
            .text(d => d.name.length > 25 ? d.name.substring(0, 25) + '...' : d.name);
        
        // Tooltip
        const tooltip = d3.select('#tooltip');
        
        node.on('mouseover', (event, d) => {
            tooltip
                .style('display', 'block')
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY + 10) + 'px')
                .html(`
                    <h4>${d.name}</h4>
                    <div><strong>Type:</strong> ${d.type}</div>
                    <div><strong>File:</strong> ${d.file_path || 'N/A'}</div>
                    ${d.citations && d.citations.length > 0 ? `<div><strong>Files:</strong> ${d.citations.length} reference${d.citations.length > 1 ? 's' : ''}</div>` : ''}
                `);
        })
        .on('mouseout', () => {
            tooltip.style('display', 'none');
        })
        .on('click', (event, d) => {
            // Deselect all
            node.classed('selected', false);
            // Select clicked
            d3.select(event.currentTarget).classed('selected', true);
            // Show details
            showEntityDetails(d);
        })
        .on('contextmenu', (event, d) => {
            event.preventDefault();
            showContextMenu(event, d);
        });
        
        // Context Menu
        const contextMenu = document.getElementById('context-menu');
        let contextMenuNode = null;
        
        function showContextMenu(event, d) {
            contextMenuNode = d;
            contextMenu.style.display = 'block';
            contextMenu.style.left = event.pageX + 'px';
            contextMenu.style.top = event.pageY + 'px';
        }
        
        function hideContextMenu() {
            contextMenu.style.display = 'none';
            contextMenuNode = null;
        }
        
        // Hide context menu on click elsewhere
        document.addEventListener('click', hideContextMenu);
        document.addEventListener('contextmenu', (e) => {
            if (!e.target.closest('.node')) {
                hideContextMenu();
            }
        });
        
        // Build adjacency list for BFS
        const adjacency = new Map();
        nodes.forEach(n => adjacency.set(n.id, new Set()));
        links.forEach(l => {
            const srcId = typeof l.source === 'object' ? l.source.id : l.source;
            const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
            adjacency.get(srcId)?.add(tgtId);
            adjacency.get(tgtId)?.add(srcId);
        });
        
        // Get nodes within N levels using BFS
        function getNodesWithinLevels(startId, maxLevels) {
            const visited = new Map(); // nodeId -> level
            const queue = [[startId, 0]];
            visited.set(startId, 0);
            
            while (queue.length > 0) {
                const [currentId, level] = queue.shift();
                if (level >= maxLevels) continue;
                
                const neighbors = adjacency.get(currentId) || new Set();
                for (const neighborId of neighbors) {
                    if (!visited.has(neighborId)) {
                        visited.set(neighborId, level + 1);
                        queue.push([neighborId, level + 1]);
                    }
                }
            }
            
            return visited;
        }
        
        // Focus on node with N levels
        function focusOnNode(nodeData, levels) {
            const focusedNodes = getNodesWithinLevels(nodeData.id, levels);
            
            // Apply styling
            node.classed('faded', d => !focusedNodes.has(d.id))
                .classed('focused', d => d.id === nodeData.id)
                .classed('neighbor', d => focusedNodes.has(d.id) && d.id !== nodeData.id);
            
            link.classed('faded', d => {
                const srcId = typeof d.source === 'object' ? d.source.id : d.source;
                const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
                return !focusedNodes.has(srcId) || !focusedNodes.has(tgtId);
            });
            
            // Show focus banner
            const banner = document.getElementById('focus-banner');
            const info = document.getElementById('focus-info');
            info.textContent = `Focus: ${levels} level${levels > 1 ? 's' : ''} from "${nodeData.name}" (${focusedNodes.size} nodes)`;
            banner.style.display = 'block';
            
            // Select the focused node
            node.classed('selected', d => d.id === nodeData.id);
            showEntityDetails(nodeData);
        }
        
        // Clear focus
        function clearFocus() {
            node.classed('faded', false)
                .classed('focused', false)
                .classed('neighbor', false);
            link.classed('faded', false);
            document.getElementById('focus-banner').style.display = 'none';
        }
        
        // Context menu actions
        document.getElementById('ctx-focus-1').onclick = () => {
            if (contextMenuNode) focusOnNode(contextMenuNode, 1);
            hideContextMenu();
        };
        document.getElementById('ctx-focus-2').onclick = () => {
            if (contextMenuNode) focusOnNode(contextMenuNode, 2);
            hideContextMenu();
        };
        document.getElementById('ctx-focus-3').onclick = () => {
            if (contextMenuNode) focusOnNode(contextMenuNode, 3);
            hideContextMenu();
        };
        document.getElementById('ctx-focus-5').onclick = () => {
            if (contextMenuNode) focusOnNode(contextMenuNode, 5);
            hideContextMenu();
        };
        document.getElementById('ctx-expand').onclick = () => {
            if (contextMenuNode) {
                // Just clear faded state for this node and neighbors
                const neighbors = adjacency.get(contextMenuNode.id) || new Set();
                node.filter(d => d.id === contextMenuNode.id || neighbors.has(d.id))
                    .classed('faded', false);
            }
            hideContextMenu();
        };
        document.getElementById('ctx-hide').onclick = () => {
            if (contextMenuNode) {
                node.filter(d => d.id === contextMenuNode.id).style('display', 'none');
                link.filter(d => {
                    const srcId = typeof d.source === 'object' ? d.source.id : d.source;
                    const tgtId = typeof d.target === 'object' ? d.target.id : d.target;
                    return srcId === contextMenuNode.id || tgtId === contextMenuNode.id;
                }).style('display', 'none');
            }
            hideContextMenu();
        };
        document.getElementById('ctx-reset').onclick = () => {
            clearFocus();
            // Also show all hidden nodes
            node.style('display', 'block');
            link.style('display', 'block');
            hideContextMenu();
        };
        
        // Clear focus button in banner
        document.getElementById('clear-focus').onclick = clearFocus;
        
        // Tick function
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Show entity details in sidebar
        function showEntityDetails(d) {
            const details = document.getElementById('entity-details');
            const propsHtml = Object.entries(d.properties || {})
                .map(([k, v]) => `
                    <div class="detail-label">${k}</div>
                    <div class="detail-value">${typeof v === 'object' ? JSON.stringify(v, null, 2) : v}</div>
                `).join('');
            
            details.innerHTML = `
                <h3>${d.name}</h3>
                <div style="margin: 10px 0;">
                    <span class="entity-type-badge" style="background: ${getColor(d.type)}">${d.type}</span>
                </div>
                
                <div class="detail-label">ID</div>
                <div class="detail-value" style="font-family: monospace; font-size: 11px;">${d.id}</div>
                
                ${d.citations && d.citations.length > 0 ? `
                    <div class="detail-label">Citations (${d.citations.length})</div>
                    <div class="detail-value">
                        ${d.citations.map(c => `
                            <div class="citation-link" style="margin-bottom: 4px;">
                                ${c.file_path}${c.line_start ? `:${c.line_start}-${c.line_end}` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                
                <div class="detail-label">Source</div>
                <div class="detail-value">${d.source_toolkit || 'N/A'}</div>
                
                ${propsHtml ? `
                    <div class="detail-label" style="margin-top: 15px;">Properties</div>
                    ${propsHtml}
                ` : ''}
            `;
        }
        
        // Search functionality
        const searchInput = document.getElementById('search-input');
        const searchResults = document.getElementById('search-results');
        
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            searchResults.innerHTML = '';
            
            if (query.length < 2) return;
            
            const matches = nodes.filter(n => 
                n.name.toLowerCase().includes(query) ||
                n.type.toLowerCase().includes(query)
            ).slice(0, 10);
            
            matches.forEach(n => {
                const div = document.createElement('div');
                div.className = 'search-result';
                div.innerHTML = `<span class="legend-color" style="background: ${getColor(n.type)}; display: inline-block; vertical-align: middle;"></span> ${n.name}`;
                div.onclick = () => {
                    // Center on node
                    const transform = d3.zoomIdentity
                        .translate(width / 2 - n.x, height / 2 - n.y);
                    svg.transition().duration(500).call(zoom.transform, transform);
                    
                    // Select node
                    node.classed('selected', d => d.id === n.id);
                    showEntityDetails(n);
                };
                searchResults.appendChild(div);
            });
        });
        
        // Controls
        document.getElementById('link-distance').addEventListener('input', (e) => {
            simulation.force('link').distance(+e.target.value);
            simulation.alpha(0.3).restart();
        });
        
        document.getElementById('charge-strength').addEventListener('input', (e) => {
            simulation.force('charge').strength(+e.target.value);
            simulation.alpha(0.3).restart();
        });
        
        document.getElementById('show-labels').addEventListener('change', (e) => {
            labels.style('display', e.target.checked ? 'block' : 'none');
        });
        
        document.getElementById('show-orphans').addEventListener('change', (e) => {
            const connectedIds = new Set();
            links.forEach(l => {
                connectedIds.add(typeof l.source === 'object' ? l.source.id : l.source);
                connectedIds.add(typeof l.target === 'object' ? l.target.id : l.target);
            });
            
            node.style('display', d => {
                if (e.target.checked) return 'block';
                return connectedIds.has(d.id) ? 'block' : 'none';
            });
        });
        
        // Type filters
        typeFiltersDiv.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                const type = e.target.dataset.type;
                if (e.target.checked) {
                    enabledTypes.add(type);
                } else {
                    enabledTypes.delete(type);
                }
                
                node.style('display', d => enabledTypes.has(d.type) ? 'block' : 'none');
                link.style('display', d => {
                    const sourceType = typeof d.source === 'object' ? d.source.type : nodes.find(n => n.id === d.source)?.type;
                    const targetType = typeof d.target === 'object' ? d.target.type : nodes.find(n => n.id === d.target)?.type;
                    return enabledTypes.has(sourceType) && enabledTypes.has(targetType) ? 'block' : 'none';
                });
            }
        });
        
        // Initial zoom to fit
        const initialScale = 0.8;
        svg.call(zoom.transform, d3.zoomIdentity
            .translate(width * (1 - initialScale) / 2, height * (1 - initialScale) / 2)
            .scale(initialScale));
    </script>
</body>
</html>
'''


def generate_visualization(
    graph_path: str,
    output_path: str,
    title: str = "Knowledge Graph"
) -> str:
    """
    Generate an interactive HTML visualization of the knowledge graph.
    
    Args:
        graph_path: Path to the knowledge graph JSON file
        output_path: Path to write the HTML file
        title: Title for the visualization
        
    Returns:
        Path to the generated HTML file
    """
    # Load graph
    graph_path = Path(graph_path)
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found: {graph_path}")
    
    with open(graph_path, 'r') as f:
        graph_data = json.load(f)
    
    # Handle NetworkX 3.5+ compatibility: may have "edges" instead of "links"
    if 'edges' in graph_data and 'links' not in graph_data:
        graph_data['links'] = graph_data.pop('edges')
    
    # Prepare data for JavaScript - properly escape for embedding in HTML
    # Convert to JSON strings that will be valid JavaScript
    graph_json = json.dumps(graph_data, default=str, ensure_ascii=True)
    type_colors_json = json.dumps(TYPE_COLORS, ensure_ascii=True)
    relation_colors_json = json.dumps(RELATION_COLORS, ensure_ascii=True)
    
    # Escape special HTML characters that could break the script tag
    # This prevents issues with large JSON data containing HTML-like content
    graph_json = graph_json.replace('</', '<\\/')
    type_colors_json = type_colors_json.replace('</', '<\\/')
    relation_colors_json = relation_colors_json.replace('</', '<\\/')
    
    # Generate HTML - build valid HTML structure first
    html = HTML_TEMPLATE.replace('<title>Knowledge Graph Visualization</title>', 
                                f'<title>{title}</title>')
    
    # Now inject the properly escaped JSON data into the script placeholders
    html = html.replace('GRAPH_DATA_PLACEHOLDER', graph_json)
    html = html.replace('TYPE_COLORS_PLACEHOLDER', type_colors_json)
    html = html.replace('RELATION_COLORS_PLACEHOLDER', relation_colors_json)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logger.info(f"Generated visualization: {output_path} ({len(html)} bytes)")
    return str(output_path)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate knowledge graph visualization')
    parser.add_argument('--graph', '-g', required=True, help='Path to graph JSON file')
    parser.add_argument('--output', '-o', default='graph.html', help='Output HTML file')
    parser.add_argument('--title', '-t', default='Knowledge Graph', help='Visualization title')
    
    args = parser.parse_args()
    
    output = generate_visualization(args.graph, args.output, args.title)
    print(f"Generated: {output}")


if __name__ == '__main__':
    main()
