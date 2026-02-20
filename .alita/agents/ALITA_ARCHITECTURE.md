# Alita SDK - Visual Architecture Diagrams

## 1. Complete System Architecture

```mermaid
graph TB
    subgraph EXT["External Systems"]
        BACKEND[Platform Backend/UI]
        API[External Applications]
    end
    
    subgraph ENTRY["SDK Entry Point"]
        CLIENT[AlitaClient<br/>runtime/clients/client.py<br/>Main SDK Interface]
    end
    
    subgraph ORCH["Orchestration Layer"]
        ASST[Assistant<br/>runtime/langchain/assistant.py<br/>Creates Agents/Pipelines]
    end
    
    subgraph EXEC["Execution Engine"]
        LG[LangGraph Builder<br/>runtime/langchain/langraph_agent.py<br/>Workflow Engine]
        
        subgraph NODES["Node Types"]
            LLM[LLMNode]
            TOOL[ToolNode]
            AGENT[AgentNode]
            LOOP[LoopNode]
            ROUTER[RouterNode]
            INDEX[IndexerNode]
        end
    end
    
    subgraph TKITS["Toolkit System"]
        TL[Toolkit Loader<br/>runtime/toolkits/tools.py]
        
        subgraph PLATFORM["Platform Toolkits<br/>(Use AlitaClient APIs)"]
            MCP[MCP Toolkit]
            APP[Application Toolkit]
            DS[Datasource Toolkit]
            ART[Artifact Toolkit]
            PRMPT[Prompt Toolkit]
        end
        
        subgraph EXTERNAL["External Toolkits<br/>(Direct Integration)"]
            BASE[Base Classes<br/>BaseToolApiWrapper]
            
            GH[GitHub]
            JIRA[Jira]
            CONF[Confluence]
            ADO[Azure DevOps]
            SQL[SQL]
            BROWSER[Browser]
            DOTS[35+ More Toolkits...]
        end
    end
    
    BACKEND --> CLIENT
    API --> CLIENT
    CLIENT --> ASST
    ASST --> LG
    ASST --> TL
    
    LG --> LLM
    LG --> TOOL
    LG --> AGENT
    LG --> LOOP
    LG --> ROUTER
    LG --> INDEX
    
    TOOL --> TL
    TL --> MCP
    TL --> APP
    TL --> DS
    TL --> ART
    TL --> PRMPT
    TL --> BASE
    
    BASE --> GH
    BASE --> JIRA
    BASE --> CONF
    BASE --> ADO
    BASE --> SQL
    BASE --> BROWSER
    BASE --> DOTS
    
    MCP --> CLIENT
    APP --> CLIENT
    DS --> CLIENT
    ART --> CLIENT
    PRMPT --> CLIENT
    
    %% Critical components - Soft Red
    style CLIENT fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    style ASST fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    style LG fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    
    %% High impact - Soft Orange
    style BASE fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style TL fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    
    %% Low impact - Soft Green
    style GH fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style JIRA fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style SQL fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    
    %% Subgraph styling - Light backgrounds
    style EXT fill:#f0f9ff,stroke:#1864ab,stroke-width:2px
    style ENTRY fill:#fff5f5,stroke:#c92a2a,stroke-width:3px
    style ORCH fill:#fff5f5,stroke:#c92a2a,stroke-width:2px
    style EXEC fill:#fff5f5,stroke:#c92a2a,stroke-width:2px
    style NODES fill:#fffbeb,stroke:#d9480f,stroke-width:1px
    style TKITS fill:#fffbeb,stroke:#d9480f,stroke-width:2px
    style PLATFORM fill:#e7f5ff,stroke:#1864ab,stroke-width:1px
    style EXTERNAL fill:#f4fce3,stroke:#2b8a3e,stroke-width:1px
```

**Color Legend:**
- 🔴 Soft Red = CRITICAL (SDK entry point and core components)
- 🟠 Soft Orange = HIGH impact (base classes and loaders)
- 🟢 Soft Green = LOW impact (individual toolkit implementations)

Key Architecture Notes:
- **AlitaClient** is the MAIN SDK ENTRY POINT - called by platform backend/UI
- **Platform Toolkits** (MCP, Application, Datasource, Artifact, Prompt) use AlitaClient APIs
- **External Toolkits** (GitHub, Jira, SQL, Browser, etc.) connect directly to their services
- CLI and Streamlit are development/testing tools, not the production entry point

---

## 2. Dependency Layers & Impact Zones

```mermaid
graph BT
    subgraph L0["Layer 0: Foundation - CRITICAL IMPACT"]
        BASE[BaseToolApiWrapper]
        BASECODE[BaseCodeToolApiWrapper]
        BASEACTION[BaseAction]
        BASEINDEX[BaseIndexerToolkit]
    end
    
    subgraph L1["Layer 1: Core Runtime - CRITICAL IMPACT"]
        CLIENT[AlitaClient<br/>SDK Entry Point]
        ASST[Assistant]
        GRAPH[LangGraph Builder]
        NODES[Node Types]
        TKLOADER[Toolkit Loader]
    end
    
    subgraph L2["Layer 2: Implementations - LOW IMPACT"]
        TK1[GitHub Toolkit]
        TK2[Jira Toolkit]
        TK3[Confluence Toolkit]
        TK4[40+ Other Toolkits]
    end
    
    subgraph EXT["External Callers"]
        BACKEND[Platform Backend]
        UI[Platform UI]
        EXTAPP[External Apps]
    end
    
    TK1 --> BASE
    TK2 --> BASE
    TK3 --> BASE
    TK4 --> BASE
    
    TK1 --> BASEINDEX
    TK2 --> BASEINDEX
    TK3 --> BASEINDEX
    
    NODES --> BASE
    NODES --> BASEACTION
    
    TKLOADER --> BASE
    TKLOADER --> BASEACTION
    
    GRAPH --> NODES
    ASST --> GRAPH
    ASST --> TKLOADER
    ASST --> CLIENT
    
    BACKEND --> CLIENT
    UI --> CLIENT
    EXTAPP --> CLIENT
    
    %% Critical components - Soft Red
    style BASE fill:#ffccd5,stroke:#c92a2a,stroke-width:3px,color:#000
    style BASECODE fill:#ffccd5,stroke:#c92a2a,stroke-width:3px,color:#000
    style BASEACTION fill:#ffccd5,stroke:#c92a2a,stroke-width:3px,color:#000
    style BASEINDEX fill:#ffccd5,stroke:#c92a2a,stroke-width:3px,color:#000
    
    style CLIENT fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    style ASST fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    style GRAPH fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    style NODES fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    
    %% High impact - Soft Orange
    style TKLOADER fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    
    %% Low impact - Soft Green
    style TK1 fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style TK2 fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style TK3 fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style TK4 fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    
    %% External callers - Soft Blue
    style BACKEND fill:#d0ebff,stroke:#1864ab,stroke-width:2px,color:#000
    style UI fill:#d0ebff,stroke:#1864ab,stroke-width:2px,color:#000
    style EXTAPP fill:#d0ebff,stroke:#1864ab,stroke-width:2px,color:#000
    
    %% Subgraph styling
    style L0 fill:#fff5f5,stroke:#c92a2a,stroke-width:2px
    style L1 fill:#fff5f5,stroke:#c92a2a,stroke-width:2px
    style L2 fill:#f4fce3,stroke:#2b8a3e,stroke-width:2px
    style EXT fill:#f0f9ff,stroke:#1864ab,stroke-width:2px
```

**Layer Impact Levels:**
- 🔴 **Layers 0 & 1** = CRITICAL IMPACT - Changes require full regression testing
- 🟢 **Layer 2** = LOW IMPACT - Changes isolated to specific toolkit
- 🔵 **External** = Entry points calling the SDK

---

## 3. Change Impact Flow

```mermaid
graph LR
    subgraph "Change in Base Classes"
        BC[BaseToolApiWrapper<br/>or BaseAction]
    end
    
    subgraph "Affected Systems"
        direction TB
        ALL1[ALL 40+ Toolkits]
        ALL2[ALL Agents]
        ALL3[ALL Pipelines]
        ALL4[ALL Chats]
    end
    
    BC -->|Cascades to| ALL1
    BC -->|Cascades to| ALL2
    BC -->|Cascades to| ALL3
    BC -->|Cascades to| ALL4
    
    style BC fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    style ALL1 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style ALL2 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style ALL3 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style ALL4 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
```

```mermaid
graph LR
    subgraph "Change in Core Runtime"
        CR[Assistant or<br/>LangGraph Builder]
    end
    
    subgraph "Affected Systems"
        direction TB
        AGT[ALL Agents]
        PIP[ALL Pipelines]
        CHT[ALL Chats]
    end
    
    CR -->|Affects| AGT
    CR -->|Affects| PIP
    CR -->|Affects| CHT
    
    style CR fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    style AGT fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style PIP fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style CHT fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
```

```mermaid
graph LR
    subgraph "Change in Toolkit"
        TK[GitHub Toolkit]
    end
    
    subgraph "Affected Systems"
        direction TB
        ONLY[Only GitHub Toolkit]
    end
    
    TK -->|Isolated to| ONLY
    
    style TK fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
    style ONLY fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
```

---

## 4. Toolkit Inheritance Hierarchy

```mermaid
graph TB
    BASE[BaseToolApiWrapper<br/>elitea_base.py]
    
    subgraph "Code Indexing"
        BASECODE[BaseCodeToolApiWrapper<br/>extends BaseToolApiWrapper]
        CODEINDEX[CodeIndexerToolkit<br/>extends BaseIndexerToolkit]
        
        BASECODE --> GH[GitHub]
        BASECODE --> GL[GitLab]
        BASECODE --> BB[Bitbucket]
        BASECODE --> ADOR[ADO Repos]
        BASECODE --> LG[LocalGit]
    end
    
    subgraph "Non-Code Indexing"
        BASEINDEX[BaseIndexerToolkit<br/>extends VectorStoreWrapperBase]
        NONCODEINDEX[NonCodeIndexerToolkit<br/>extends BaseIndexerToolkit]
        
        NONCODEINDEX --> JIRA[Jira]
        NONCODEINDEX --> CONF[Confluence]
        NONCODEINDEX --> TR[TestRail]
        NONCODEINDEX --> ADOB[ADO Boards]
        NONCODEINDEX --> QT[QTest]
        NONCODEINDEX --> ZS[Zephyr Scale]
    end
    
    subgraph "Simple Toolkits"
        BASE --> SQL[SQL]
        BASE --> SLACK[Slack]
        BASE --> YAG[Yagmail]
        BASE --> OCR[OCR]
        BASE --> PPTX[PPTX]
    end
    
    BASE --> BASECODE
    BASE --> BASEINDEX
    BASEINDEX --> CODEINDEX
    BASEINDEX --> NONCODEINDEX
    
    %% Critical - Soft Red
    style BASE fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    
    %% High impact - Soft Orange
    style BASECODE fill:#ffe8cc,stroke:#d9480f,stroke-width:3px,color:#000
    style BASEINDEX fill:#ffe8cc,stroke:#d9480f,stroke-width:3px,color:#000
    
    %% Medium impact - Soft Blue
    style CODEINDEX fill:#d0ebff,stroke:#1864ab,stroke-width:2px,color:#000
    style NONCODEINDEX fill:#d0ebff,stroke:#1864ab,stroke-width:2px,color:#000
```

---

## 5. SDK Usage Flow (Platform Integration)

```mermaid
sequenceDiagram
    participant Backend as Platform Backend/UI
    participant Client as AlitaClient
    participant Assistant
    participant LangGraph
    participant Nodes
    participant Toolkits
    participant APIWrapper
    participant ExternalAPI as External Services
    
    Backend->>Client: Initialize SDK<br/>(base_url, project_id, auth_token)
    Client->>Client: Setup platform API endpoints
    
    Backend->>Client: application(app_id, version_id)
    Client->>Backend: Fetch app definition from platform
    Backend->>Client: Return app config
    Client->>Assistant: Create Assistant with config
    
    Assistant->>Assistant: Parse agent/pipeline definition
    Assistant->>Toolkits: get_tools(toolkit_configs)
    Toolkits->>APIWrapper: Initialize API wrappers
    APIWrapper-->>Toolkits: Return tool instances
    Toolkits-->>Assistant: Return tool list
    
    Assistant->>LangGraph: Create graph (agent/pipeline)
    LangGraph->>Nodes: Create node instances
    LangGraph-->>Assistant: Return executable graph
    Client-->>Backend: Return runnable app
    
    Backend->>Client: app.invoke(input, messages)
    Client->>LangGraph: Execute graph
    
    loop Execution Steps
        LangGraph->>Nodes: Execute node
        Nodes->>Toolkits: Call tool
        Toolkits->>APIWrapper: Execute
        APIWrapper->>ExternalAPI: API call (GitHub, Jira, etc.)
        ExternalAPI-->>APIWrapper: Response
        APIWrapper-->>Toolkits: Return result
        Toolkits-->>Nodes: Return tool result
        Nodes-->>LangGraph: Update state
    end
    
    LangGraph-->>Client: Return final result
    Client-->>Backend: Return response
```

---

## 6. Testing Scope Decision Matrix

```mermaid
flowchart TD
    START([What did you change?])
    
    START --> Q1{Which component?}
    
    Q1 -->|AlitaClient<br/>SDK Entry Point| CRIT0[🔴 CRITICAL<br/>Platform APIs]
    Q1 -->|Base Classes<br/>Foundation| CRIT1[🔴 CRITICAL<br/>Full System Test]
    Q1 -->|Assistant or<br/>LangGraph| CRIT2[🔴 CRITICAL<br/>All Agents/Pipelines]
    Q1 -->|Toolkit<br/>Implementation| MED[🟢 LOW<br/>Single Toolkit]
    
    CRIT0 --> TEST0[Test:<br/>- Application loading<br/>- Agent execution<br/>- Pipeline execution<br/>- Platform APIs]
    
    CRIT1 --> TEST1[Test:<br/>- All 40+ toolkits<br/>- All agents<br/>- All pipelines<br/>- All chats]
    
    CRIT2 --> TEST2[Test:<br/>- All agents<br/>- All pipelines<br/>- All chats<br/>- Memory/checkpoints]
    
    MED --> Q2{Changed registry<br/>or base?}
    Q2 -->|Yes| HIGH[🟠 HIGH<br/>All toolkit loading]
    Q2 -->|No| TEST3[Test:<br/>- That toolkit only<br/>- Unit tests<br/>- Integration tests]
    
    HIGH --> TEST4[Test:<br/>- Toolkit discovery<br/>- Toolkit loading<br/>- Dynamic instantiation]
    
    style START fill:#f8f9fa,color:#000
    
    %% Critical - Soft Red
    style CRIT0 fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    style CRIT1 fill:#ffccd5,stroke:#c92a2a,stroke-width:3px,color:#000
    style CRIT2 fill:#ffe0e6,stroke:#c92a2a,stroke-width:3px,color:#000
    
    %% High - Soft Orange
    style HIGH fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    
    %% Low - Soft Green
    style MED fill:#d3f9d8,stroke:#2b8a3e,stroke-width:2px,color:#000
```

---

## 7. Module Communication Patterns

```mermaid
graph TB
    subgraph "Agent Execution Flow"
        direction LR
        A1[Backend Request] --> A2[AlitaClient]
        A2 --> A3[Assistant]
        A3 --> A4[LangGraph]
        A4 --> A5[Nodes]
        A5 --> A6[Tools]
        A6 --> A7[API Wrappers]
        A7 --> A8[External APIs]
    end
    
    subgraph "Pipeline Execution Flow"
        direction LR
        P1[Backend Trigger] --> P2[AlitaClient]
        P2 --> P3[Assistant]
        P3 --> P4[LangGraph]
        P4 --> P5[Nodes]
        P5 --> P6[Sequential Steps]
        P6 --> P7[Tools]
        P7 --> P8[Results]
    end
    
    subgraph "Toolkit Loading Flow"
        direction LR
        T1[Config] --> T2[Toolkit Loader]
        T2 --> T3[Toolkit Class]
        T3 --> T4[API Wrapper]
        T4 --> T5[Tool Instances]
    end
    
    %% Critical components - Soft Red
    style A2 fill:#ffccd5,stroke:#c92a2a,stroke-width:2px,color:#000
    style A3 fill:#ffe0e6,stroke:#c92a2a,stroke-width:2px,color:#000
    style A4 fill:#ffe0e6,stroke:#c92a2a,stroke-width:2px,color:#000
    style P2 fill:#ffccd5,stroke:#c92a2a,stroke-width:2px,color:#000
    style P3 fill:#ffe0e6,stroke:#c92a2a,stroke-width:2px,color:#000
    style P4 fill:#ffe0e6,stroke:#c92a2a,stroke-width:2px,color:#000
    
    %% High impact - Soft Orange
    style T4 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
```

---

## 8. Risk Assessment Matrix

| Component | Change Frequency | Impact Level | Risk Level | Test Priority |
|-----------|-----------------|--------------|------------|---------------|
| BaseToolApiWrapper | Very Low | Critical | 🔴 Extreme | P0 - Full Regression |
| BaseAction | Very Low | Critical | 🔴 Extreme | P0 - Full Regression |
| AlitaClient | Low | Critical | 🔴 High | P0 - Platform APIs |
| Assistant | Low | Critical | 🔴 High | P0 - Full Regression |
| LangGraph Builder | Low | Critical | 🔴 High | P0 - Full Regression |
| Node Types | Medium | Critical | 🔴 High | P1 - Node-specific |
| Toolkit Loader | Medium | High | 🟠 Medium | P1 - Loading tests |
| Individual Toolkits | High | Low | 🟢 Low | P2 - Toolkit-specific |
| Configurations | Low | Low | 🟢 Very Low | P3 - Config validation |

**Risk Calculation**: `Change Frequency × Impact Level = Risk Level`

---

## 9. Toolkit Ecosystem Map

```mermaid
mindmap
  root((Alita SDK<br/>Toolkits))
    Issue Tracking
      Jira
      ADO Boards
      Rally
    Test Management
      TestRail
      QTest
      Xray
      Zephyr Scale
      Zephyr Squad
      Zephyr Enterprise
      Zephyr Essential
      Report Portal
      TestIO
    Code Repositories
      GitHub
      GitLab
      Bitbucket
      ADO Repos
      LocalGit
    Collaboration
      Confluence
      Slack
      SharePoint
    API & Integration
      OpenAPI
      Postman
      Elastic
      Keycloak
    Cloud Services
      AWS
      Azure
      GCP
      Kubernetes
    Business Apps
      Salesforce
      ServiceNow
    Development Tools
      Browser
      Figma
      SQL
      OCR
      PPTX
    Internal Tools
      MCP
      Planning
      Artifact
      Datasource
      Vector Store
      Memory
```

---

## 10. Change Propagation Example

### Example: Changing BaseToolApiWrapper.run()

```mermaid
graph TD
    CHANGE[Change: BaseToolApiWrapper.run<br/>Modified error handling]
    
    CHANGE --> TK1[GitHub Toolkit]
    CHANGE --> TK2[Jira Toolkit]
    CHANGE --> TK3[Confluence Toolkit]
    CHANGE --> TK4[40+ Other Toolkits]
    
    TK1 --> A1[Agent using GitHub]
    TK2 --> A2[Agent using Jira]
    TK3 --> A3[Agent using Confluence]
    TK4 --> A4[All other agents]
    
    A1 --> P1[Pipeline with GitHub]
    A2 --> P2[Pipeline with Jira]
    A3 --> P3[Pipeline with Confluence]
    A4 --> P4[All other pipelines]
    
    P1 --> R1[Retest Required]
    P2 --> R1
    P3 --> R1
    P4 --> R1
    
    %% Critical change - Soft Red
    style CHANGE fill:#ffccd5,stroke:#c92a2a,stroke-width:4px,color:#000
    
    %% Affected toolkits - Soft Orange
    style TK1 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style TK2 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style TK3 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    style TK4 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px,color:#000
    
    %% Retest required - Soft Yellow
    style R1 fill:#fff3bf,stroke:#f08c00,stroke-width:3px,color:#000
```

**Result**: One change propagates to 40+ toolkits → 100+ agents → 50+ pipelines = **Full regression required**

---

*These diagrams complement the ARCHITECTURE_ANALYSIS.md document and provide visual representations of the system architecture and impact relationships.*