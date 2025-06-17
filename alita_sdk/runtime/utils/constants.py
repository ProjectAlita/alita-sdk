STYLES = r"""
        <style>
        /* Import Montserrat font */
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
        
        /* Global dark theme styling */
        .stApp {
            background: linear-gradient(180deg, #0F1E33 0%, #1B172C 100%);
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Hide default Streamlit elements */
        [data-testid="stStatusWidget"] { display: none; }
        .stDeployButton { display: none; }
        header[data-testid="stHeader"] { display: none; }
        .stToolbar { display: none; }
        
        /* Main content area styling */
        .main .block-container {
            padding: 1rem 2rem 2rem;
            background: transparent;
        }
        
        /* Sidebar styling to match Figma */
        section[data-testid="stSidebarContent"] { 
            width: 400px !important;
            background: linear-gradient(180deg, #0F1E33 0%, #1B172C 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sidebar .element-container {
            background: transparent;
        }
        
        /* Sidebar expander styling */
        .sidebar .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 12px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            font-size: 14px;
            padding: 12px 16px;
            margin: 8px 0;
        }
        
        .sidebar .streamlit-expanderHeader:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: #6AE8FA;
        }
        
        .sidebar .streamlit-expanderContent {
            background: #181F2A;
            border: 1px solid #3B3E46;
            border-radius: 0 0 12px 12px;
            border-top: none;
            padding: 16px;
        }
        
        /* Form styling */
        .sidebar .stForm {
            background: transparent;
            border: none;
        }
        
        /* Input field styling */
        .sidebar .stTextInput > div > div > input,
        .sidebar .stNumberInput > div > div > input,
        .sidebar .stTextArea > div > div > textarea {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            padding: 12px 16px;
        }
        
        .sidebar .stTextInput > div > div > input:focus,
        .sidebar .stNumberInput > div > div > input:focus,
        .sidebar .stTextArea > div > div > textarea:focus {
            border-color: #6AE8FA;
            box-shadow: 0 0 0 1px #6AE8FA;
        }
        
        /* Label styling */
        .sidebar .stTextInput > label,
        .sidebar .stNumberInput > label,
        .sidebar .stTextArea > label {
            color: #A9B7C1;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            font-size: 12px;
            margin-bottom: 8px;
        }
        
        /* Button styling */
        .sidebar .stButton > button {
            background: rgba(106, 232, 250, 0.2);
            border: 1px solid #6AE8FA;
            border-radius: 28px;
            color: #6AE8FA;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            font-size: 14px;
            padding: 8px 24px;
            transition: all 0.3s ease;
            width: 100%;
        }
        
        .sidebar .stButton > button:hover {
            background: rgba(106, 232, 250, 0.3);
            border-color: #6AE8FA;
            color: #FFFFFF;
            transform: translateY(-1px);
        }
        
        /* Success/error message styling in sidebar */
        .sidebar .stSuccess {
            background: rgba(42, 179, 122, 0.2);
            border: 1px solid #2AB37A;
            border-radius: 8px;
            color: #2AB37A;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            padding: 12px 16px;
        }
        
        .sidebar .stError {
            background: rgba(215, 22, 22, 0.2);
            border: 1px solid #D71616;
            border-radius: 8px;
            color: #D71616;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            padding: 12px 16px;
        }
        
        .sidebar .stInfo {
            background: rgba(169, 183, 193, 0.2);
            border: 1px solid #A9B7C1;
            border-radius: 8px;
            color: #A9B7C1;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            padding: 12px 16px;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 4px;
            gap: 4px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border: none;
            border-radius: 8px;
            color: #A9B7C1;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            font-size: 14px;
            padding: 12px 24px;
            transition: all 0.3s ease;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #FFFFFF;
        }
        
        .stTabs [aria-selected="true"] {
            background: rgba(255, 255, 255, 0.1) !important;
            color: #FFFFFF !important;
        }
        
        /* Main content styling */
        .main .stMarkdown h1,
        .main .stMarkdown h2,
        .main .stMarkdown h3 {
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        
        .main .stMarkdown h1 {
            font-size: 32px;
            margin-bottom: 24px;
        }
        
        .main .stMarkdown h2 {
            font-size: 24px;
            margin-bottom: 20px;
        }
        
        .main .stMarkdown h3 {
            font-size: 20px;
            margin-bottom: 16px;
        }
        
        .main .stMarkdown p,
        .main .stMarkdown li {
            color: #A9B7C1;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            line-height: 1.6;
        }
        
        /* Chat-like area styling */
        .main .stContainer > div {
            background: #181F2A;
            border: 1px solid #3B3E46;
            border-radius: 16px;
            padding: 24px;
            margin: 16px 0;
        }
        
        /* Selectbox styling */
        .main .stSelectbox > div > div > div {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
        }
        
        .main .stSelectbox > div > div > div:hover {
            border-color: #6AE8FA;
        }
        
        /* Text input styling in main area */
        .main .stTextInput > div > div > input,
        .main .stNumberInput > div > div > input,
        .main .stTextArea > div > div > textarea {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-size: 14px;
            padding: 12px 16px;
        }
        
        .main .stTextInput > div > div > input:focus,
        .main .stNumberInput > div > div > input:focus,
        .main .stTextArea > div > div > textarea:focus {
            border-color: #6AE8FA;
            box-shadow: 0 0 0 1px #6AE8FA;
        }
        
        /* Button styling in main area */
        .main .stButton > button {
            background: rgba(106, 232, 250, 0.2);
            border: 1px solid #6AE8FA;
            border-radius: 8px;
            color: #6AE8FA;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            font-size: 14px;
            padding: 12px 24px;
            transition: all 0.3s ease;
        }
        
        .main .stButton > button:hover {
            background: rgba(106, 232, 250, 0.3);
            border-color: #6AE8FA;
            color: #FFFFFF;
            transform: translateY(-1px);
        }
        
        .main .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #6AE8FA 0%, #24E1FA 100%);
            border: none;
            color: #0E131D;
            font-weight: 600;
        }
        
        .main .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #24E1FA 0%, #6AE8FA 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(106, 232, 250, 0.3);
        }
        
        /* Message styling */
        .main .stSuccess {
            background: rgba(42, 179, 122, 0.2);
            border: 1px solid #2AB37A;
            border-radius: 12px;
            color: #2AB37A;
            font-family: 'Montserrat', sans-serif;
            padding: 16px 20px;
        }
        
        .main .stError {
            background: rgba(215, 22, 22, 0.2);
            border: 1px solid #D71616;
            border-radius: 12px;
            color: #D71616;
            font-family: 'Montserrat', sans-serif;
            padding: 16px 20px;
        }
        
        .main .stWarning {
            background: rgba(255, 176, 84, 0.2);
            border: 1px solid #FFB054;
            border-radius: 12px;
            color: #FFB054;
            font-family: 'Montserrat', sans-serif;
            padding: 16px 20px;
        }
        
        .main .stInfo {
            background: rgba(169, 183, 193, 0.2);
            border: 1px solid #A9B7C1;
            border-radius: 12px;
            color: #A9B7C1;
            font-family: 'Montserrat', sans-serif;
            padding: 16px 20px;
        }
        
        /* Form styling in main area */
        .main .stForm {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid #3B3E46;
            border-radius: 16px;
            padding: 24px;
        }
        
        /* Expander styling in main area */
        .main .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
        }
        
        .main .streamlit-expanderContent {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid #3B3E46;
            border-radius: 0 0 8px 8px;
            border-top: none;
            padding: 16px;
        }
        
        /* Code block styling */
        .main .stCode {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Divider styling */
        hr {
            border: none;
            height: 1px;
            background: rgba(255, 255, 255, 0.1);
            margin: 24px 0;
        }
        
        /* Tooltip styling */
        .main [data-testid="stTooltipContent"] {
            background: #101721;
            border: 1px solid #3B3E46;
            border-radius: 8px;
            color: #FFFFFF;
            font-family: 'Montserrat', sans-serif;
            font-size: 12px;
        }
        
        /* JSON display styling */
        .main .stJson {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3B3E46;
            border-radius: 8px;
            padding: 16px;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(169, 183, 193, 0.3);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(169, 183, 193, 0.5);
        }
        
        /* Animation for interactive elements */
        .main .stButton > button,
        .sidebar .stButton > button,
        .stSelectbox > div > div > div,
        .streamlit-expanderHeader {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            section[data-testid="stSidebarContent"] { 
                width: 300px !important;
            }
            
            .main .block-container {
                padding: 1rem;
            }
        }
        
        /* Custom spinner styling */
        .stSpinner > div {
            border-color: #6AE8FA !important;
        }
        
        /* Progress bar styling */
        .stProgress > div > div {
            background: linear-gradient(90deg, #6AE8FA 0%, #24E1FA 100%);
        }
        
        /* Balloons animation enhancement */
        .balloons {
            filter: hue-rotate(180deg) brightness(1.2);
        }
        </style>
        """