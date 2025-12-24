"""
TOON (Token-Optimized Object Notation) tools for Figma.

These tools output a compact, human-readable format optimized for LLM token consumption.
They are designed for A/B testing against JSON-based tools.

TOON Format Example:
```
FILE: Mobile App [key:abc123]
  PAGE: Authentication
    FRAME: 01_Login [0,0 375x812] form/default #1:100
      Headings: Welcome Back
      Labels: Email | Password
      Buttons: Sign In > auth | Forgot Password? > reset
      Components: Input/Email, Button/Primary
    FRAME: 01_Login_Error [400,0] form/error ~01_Login #1:101
      Errors: Invalid email or password
  FLOWS:
    sequence: 01_Login > 02_Verify > 03_Dashboard
    variants: Login ~ [Login#1:100, Login_Error#1:101, Login_Loading#1:102]
    cta: "Sign In" > authenticated | "Create Account" > registration
```

Legend:
  Headings: Large text, titles
  Labels: Form labels, navigation items, small text
  Buttons: CTAs with inferred destinations
  Components: Component instances used
  Errors: Error messages (red text)
  Text: Body text content
  Image: Image description (if processed)

Flow markers:
  sequence: Sequence inferred from naming (01_, Step 1, etc.)
  variants: True variants of same screen with frame IDs (Login#1:100, Login_Error#1:101)
  cta: CTA text with likely destination
  >: Navigation/flow direction
  ~: Variant of (similar to)
  #: Frame ID (use with get_frame_detail_toon or get_file_nodes for drill-down)
"""

import re
import logging
from typing import Callable, Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field, create_model


# -----------------------------------------------------------------------------
# LLM Structured Output Schemas
# -----------------------------------------------------------------------------

class ExtractedInput(BaseModel):
    """A form input/control extracted from the screen."""
    label: str = Field(description="Label for this input (e.g., 'Email', 'Creativity', 'Model')")
    input_type: str = Field(description="Type: text, email, password, number, slider, radio, checkbox, toggle, select, textarea, display")
    current_value: Optional[str] = Field(default=None, description="Current value shown (if any)")
    options: Optional[List[str]] = Field(default=None, description="Options for select/radio/slider (e.g., ['Low', 'Medium', 'High'])")
    required: bool = Field(default=False, description="Whether this field appears required")


class ScreenExplanation(BaseModel):
    """Structured explanation of a single screen/frame based on visual analysis."""
    frame_id: str = Field(description="Frame ID from TOON data (e.g., '1:100')")
    frame_name: str = Field(description="Frame name from TOON data")
    purpose: str = Field(description="1-2 sentence explanation of screen's purpose")
    user_goal: str = Field(description="What the user is trying to accomplish here")
    primary_action: Optional[str] = Field(default=None, description="The main CTA/action on this screen")
    visual_focus: str = Field(default="", description="What draws the eye first - the visual hierarchy focal point")
    layout_pattern: str = Field(default="", description="Layout pattern used (e.g., card grid, form stack, split view)")
    visual_state: str = Field(default="default", description="Visual state: default, error, success, loading, empty")
    inputs: List[ExtractedInput] = Field(default_factory=list, description="Form inputs/controls visible on screen")


class FlowExplanation(BaseModel):
    """Structured explanation of a user flow/journey."""
    flow_name: str = Field(description="Name of the flow (e.g., 'authentication', 'checkout')")
    description: str = Field(description="1-2 sentence description of the flow")
    entry_point: str = Field(description="Starting screen of the flow")
    exit_point: str = Field(description="End screen of the flow")
    steps: List[str] = Field(description="Ordered list of screen names in the flow")
    happy_path: str = Field(description="Description of the ideal user path")
    error_states: List[str] = Field(default_factory=list, description="Screens showing error states")


class DesignAnalysis(BaseModel):
    """Complete structured analysis of a Figma design."""
    file_name: str = Field(description="Name of the Figma file")
    overall_purpose: str = Field(description="2-3 sentence summary of what this design is for")
    target_user: str = Field(description="Who this design is intended for")
    design_type: str = Field(description="Type: mobile app, web app, landing page, dashboard, etc.")
    screens: List[ScreenExplanation] = Field(description="Explanation of each screen")
    flows: List[FlowExplanation] = Field(default_factory=list, description="Identified user flows")
    design_patterns: List[str] = Field(default_factory=list, description="UI patterns used (cards, forms, modals, etc.)")
    accessibility_notes: List[str] = Field(default_factory=list, description="Accessibility considerations observed")
    gaps_or_concerns: List[str] = Field(default_factory=list, description="Missing screens or UX concerns")


# -----------------------------------------------------------------------------
# LLM Analysis Prompt Templates
# -----------------------------------------------------------------------------

# Vision-based prompt (when image is provided)
SCREEN_VISION_PROMPT = """Analyze this Figma screen image and provide visual insights.

Screen: "{frame_name}" (ID: {frame_id})

Look at the image and identify:
1. purpose: What is this screen for? (1 sentence)
2. user_goal: What is the user trying to accomplish? (1 sentence)
3. primary_action: Which button/CTA is the main action? (just the name you see)
4. visual_focus: What draws the eye first? What's the visual hierarchy focal point?
5. layout_pattern: What layout is used? (card grid, form stack, list, split view, etc.)
6. visual_state: Is this default, error, success, loading, or empty state?
7. inputs: List ALL form inputs/controls you see:
   - For each input: label, type (text/email/password/number/slider/radio/checkbox/toggle/select/textarea/display)
   - Include current value if visible
   - For sliders/radio/select: list the options (e.g., Low/Medium/High)
   - Note if field appears required (has * or "required")
   - Include dropdowns, model selectors, token counters, settings fields

IMPORTANT: Extract ALL inputs visible - settings screens often have many controls.
Be concise - 1 sentence per field except inputs which should be complete."""


# Text-only prompt (fallback when no image)
SCREEN_TEXT_PROMPT = """Analyze this Figma screen based on extracted data.

Screen: "{frame_name}" (ID: {frame_id})

Extracted Data:
{toon_data}

Based on this data, identify:
1. purpose: What is this screen for? (1 sentence)
2. user_goal: What is the user trying to accomplish? (1 sentence)
3. primary_action: Which button/CTA is the main action? (just the name)
4. visual_focus: Based on element hierarchy, what's likely the focal point?
5. layout_pattern: What layout pattern is suggested? (form, list, cards, etc.)
6. visual_state: What state is this? (default, error, success, loading, empty)
7. inputs: Extract form inputs from the data:
   - Look for input fields, sliders, dropdowns, toggles, checkboxes
   - For each: label, type, current value (if shown), options (if applicable)
   - Include display-only fields showing values (like "Remaining Tokens: 10000")

Be concise. DO NOT repeat the element lists - they're already shown separately."""


FILE_ANALYSIS_PROMPT = """Analyze this Figma file design and provide high-level insights.

Extracted TOON Data (reference this, don't repeat it):
{toon_data}

Provide ONLY insights not already visible in the data:
1. design_type: What type of product is this? (mobile app, web app, dashboard, etc.)
2. target_user: Who is this designed for? (1 sentence)
3. overall_purpose: What problem does this solve? (1-2 sentences)
4. flows: List user journeys identified (use frame names from data)
5. design_patterns: UI patterns used (cards, forms, modals - be specific)
6. gaps_or_concerns: What's missing or could be improved? (be specific)

IMPORTANT:
- The TOON data already lists screens, buttons, components - DO NOT repeat
- Focus on SYNTHESIS and INSIGHTS the data doesn't show
- Reference frame names/IDs when discussing flows"""


# Flow analysis prompt for LLM
FLOW_ANALYSIS_PROMPT = """Analyze the user flows in this Figma design.

Frame Names and Key Actions:
{frame_summary}

Identify the main user journeys. For each journey:
1. Name it clearly (e.g., "User Registration", "Checkout Process")
2. List the screens in order (use actual frame names)
3. Describe what the user accomplishes

Focus on:
- Main happy paths (typical successful flows)
- Entry points (where users start)
- Exit points (where users complete their goal)
- Any error/recovery flows

Keep it concise. Use actual frame names from the data."""


class UserFlow(BaseModel):
    """A single user flow/journey through the design."""
    name: str = Field(description="Clear name for this flow (e.g., 'User Registration')")
    description: str = Field(description="1 sentence describing what user accomplishes")
    screens: List[str] = Field(description="Ordered list of frame names in this flow")
    entry_screen: str = Field(description="First screen of the flow")
    exit_screen: str = Field(description="Final screen of the flow")
    flow_type: str = Field(default="happy_path", description="Type: happy_path, error_recovery, or alternate")


class FlowAnalysis(BaseModel):
    """LLM analysis of user flows in a design."""
    main_flows: List[UserFlow] = Field(description="Primary user journeys (2-4 flows)")
    entry_points: List[str] = Field(description="Screens where users typically enter the app")
    completion_points: List[str] = Field(description="Screens indicating task completion")
    navigation_pattern: str = Field(description="Overall navigation style: linear, hub-spoke, hierarchical, etc.")


# -----------------------------------------------------------------------------
# TOON Format Constants
# -----------------------------------------------------------------------------

TOON_INDENT = "  "  # 2 spaces for indentation


# -----------------------------------------------------------------------------
# Flow Inference Helpers
# -----------------------------------------------------------------------------

def extract_sequence_number(name: str) -> Optional[Tuple[int, str]]:
    """
    Extract sequence number from frame name.

    Patterns detected:
      - "01_Login" -> (1, "Login")
      - "Step 1 - Login" -> (1, "Login")
      - "1. Login" -> (1, "Login")
      - "Login (1)" -> (1, "Login")
      - "Screen_001" -> (1, "Screen")

    Returns (sequence_number, base_name) or None if no pattern found.
    """
    patterns = [
        # "01_Login", "001_Login"
        (r'^(\d{1,3})[-_\s]+(.+)$', lambda m: (int(m.group(1)), m.group(2).strip())),
        # "Step 1 - Login", "Step1: Login"
        (r'^step\s*(\d+)\s*[-:_]?\s*(.*)$', lambda m: (int(m.group(1)), m.group(2).strip() or f"Step {m.group(1)}")),
        # "1. Login", "1) Login"
        (r'^(\d+)\s*[.\)]\s*(.+)$', lambda m: (int(m.group(1)), m.group(2).strip())),
        # "Login (1)", "Login [1]"
        (r'^(.+?)\s*[\(\[](\d+)[\)\]]$', lambda m: (int(m.group(2)), m.group(1).strip())),
        # "Screen_001", "Page001"
        (r'^([a-zA-Z]+)[-_]?(\d{2,3})$', lambda m: (int(m.group(2)), m.group(1).strip())),
    ]

    for pattern, extractor in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            return extractor(match)
    return None


def extract_base_name(name: str) -> str:
    """
    Extract base name for variant grouping.

    "Login_Error" -> "Login"
    "Login - Error State" -> "Login"
    "01_Login_Loading" -> "Login"
    """
    # Remove sequence prefix first
    seq_result = extract_sequence_number(name)
    if seq_result:
        name = seq_result[1]

    # Common variant suffixes to strip
    variant_patterns = [
        r'[-_\s]+(error|success|loading|empty|disabled|active|hover|pressed|selected|default|filled|focused)(\s+state)?$',
        r'[-_\s]+(v\d+|variant\s*\d*)$',
        r'[-_\s]+\d+$',  # Trailing numbers
    ]

    base = name
    for pattern in variant_patterns:
        base = re.sub(pattern, '', base, flags=re.IGNORECASE)

    return base.strip()


def infer_state_from_name(name: str) -> str:
    """
    Infer screen state from name.

    Returns: default, error, success, loading, empty, or the detected state
    """
    name_lower = name.lower()

    state_keywords = {
        'error': ['error', 'fail', 'invalid', 'wrong'],
        'success': ['success', 'complete', 'done', 'confirmed'],
        'loading': ['loading', 'progress', 'spinner', 'wait'],
        'empty': ['empty', 'no data', 'no results', 'blank'],
        'disabled': ['disabled', 'inactive', 'locked'],
    }

    for state, keywords in state_keywords.items():
        if any(kw in name_lower for kw in keywords):
            return state

    return 'default'


def infer_screen_type(frame_data: Dict) -> str:
    """
    Infer screen type from content.

    Returns: form, list, detail, dashboard, modal, menu, settings, chat, etc.
    """
    name_lower = frame_data.get('name', '').lower()
    components = frame_data.get('components', [])
    buttons = frame_data.get('buttons', [])
    labels = frame_data.get('labels', [])

    components_lower = [c.lower() for c in components]
    buttons_lower = [b.lower() for b in buttons]

    # Check name hints
    type_hints = {
        'form': ['login', 'signup', 'register', 'checkout', 'payment', 'form', 'input'],
        'list': ['list', 'feed', 'timeline', 'results', 'search results'],
        'detail': ['detail', 'profile', 'item', 'product', 'article'],
        'dashboard': ['dashboard', 'home', 'overview', 'summary'],
        'modal': ['modal', 'dialog', 'popup', 'overlay', 'alert'],
        'menu': ['menu', 'navigation', 'sidebar', 'drawer'],
        'settings': ['settings', 'preferences', 'config', 'options'],
        'chat': ['chat', 'message', 'conversation', 'inbox'],
        'onboarding': ['onboarding', 'welcome', 'intro', 'tutorial'],
    }

    for screen_type, keywords in type_hints.items():
        if any(kw in name_lower for kw in keywords):
            return screen_type

    # Check components
    if any('input' in c or 'textfield' in c or 'form' in c for c in components_lower):
        return 'form'
    if any('card' in c or 'listitem' in c for c in components_lower):
        return 'list'
    if any('modal' in c or 'dialog' in c for c in components_lower):
        return 'modal'

    # Check buttons for form indicators
    form_buttons = ['submit', 'save', 'sign in', 'log in', 'register', 'next', 'continue']
    if any(any(fb in b for fb in form_buttons) for b in buttons_lower):
        return 'form'

    return 'screen'  # Generic fallback


def infer_cta_destination(cta_text: str, frame_context: str = '') -> str:
    """
    Infer likely destination/action from CTA/button text with context awareness.

    Args:
        cta_text: The button/CTA text
        frame_context: Optional frame name for additional context

    Returns semantic action category or descriptive action based on text.
    """
    cta_lower = cta_text.lower().strip()
    context_lower = frame_context.lower() if frame_context else ''

    # Skip very short or icon-only buttons
    if len(cta_lower) < 2 or cta_lower in ['x', '+', '-', '...', '→', '←']:
        return None  # Will be filtered out

    # Semantic destination mapping with expanded keywords
    destinations = {
        'authenticate': ['sign in', 'log in', 'login', 'authenticate', 'sign-in', 'log-in'],
        'register': ['sign up', 'register', 'create account', 'join', 'get started', 'sign-up'],
        'navigate_next': ['next', 'continue', 'proceed', 'forward', 'go', 'start'],
        'navigate_back': ['back', 'previous', 'return', 'go back'],
        'cancel': ['cancel', 'nevermind', 'not now', 'maybe later', 'skip'],
        'submit_form': ['submit', 'send', 'apply', 'confirm', 'done', 'complete', 'finish', 'ok', 'okay'],
        'save': ['save', 'save changes', 'update', 'keep'],
        'view_detail': ['view', 'details', 'more', 'see more', 'read more', 'open', 'expand', 'show'],
        'search': ['search', 'find', 'look up', 'filter'],
        'settings': ['settings', 'preferences', 'options', 'configure', 'customize'],
        'help': ['help', 'support', 'faq', 'contact', 'learn more', 'how to', 'guide'],
        'share': ['share', 'invite', 'send to', 'export', 'copy link'],
        'delete': ['delete', 'remove', 'clear', 'trash', 'discard'],
        'edit': ['edit', 'modify', 'change', 'rename'],
        'create': ['add', 'create', 'new', 'plus', 'insert'],
        'close': ['close', 'dismiss', 'exit', 'hide'],
        'reset': ['reset', 'forgot password', 'recover', 'restore'],
        'download': ['download', 'export', 'get', 'install'],
        'upload': ['upload', 'import', 'attach', 'choose file'],
        'refresh': ['refresh', 'reload', 'retry', 'try again'],
        'select': ['select', 'choose', 'pick'],
        'toggle': ['enable', 'disable', 'turn on', 'turn off', 'switch'],
        'connect': ['connect', 'link', 'integrate', 'sync'],
        'pay': ['pay', 'checkout', 'purchase', 'buy', 'order', 'subscribe'],
        'upgrade': ['upgrade', 'premium', 'pro', 'unlock'],
    }

    # Try to match known categories
    for dest, keywords in destinations.items():
        if any(kw in cta_lower for kw in keywords):
            return dest

    # Context-aware inference from frame name
    if context_lower:
        if any(ctx in context_lower for ctx in ['login', 'auth', 'sign']):
            if any(w in cta_lower for w in ['submit', 'go', 'enter']):
                return 'authenticate'
        if any(ctx in context_lower for ctx in ['modal', 'dialog', 'popup']):
            return 'dismiss_modal'
        if any(ctx in context_lower for ctx in ['form', 'input', 'settings']):
            return 'submit_form'
        if any(ctx in context_lower for ctx in ['checkout', 'payment', 'cart']):
            return 'pay'

    # Return cleaned button text as action (more informative than generic 'action')
    # Clean up the text for display
    clean_text = cta_text.strip()
    if len(clean_text) <= 20:
        return f"do:{clean_text}"  # Short enough to show as-is
    return f"do:{clean_text[:17]}..."  # Truncate long text


def _frames_have_content_differences(frames: List[Dict]) -> bool:
    """Check if frames have different content (not just duplicates)."""
    if len(frames) < 2:
        return False

    # Compare content fields
    content_fields = ['headings', 'labels', 'buttons', 'body', 'errors', 'placeholders']

    first_frame = frames[0].get('frame', frames[0])
    first_content = {
        field: frozenset(first_frame.get(field, []))
        for field in content_fields
    }

    for frame_data in frames[1:]:
        frame = frame_data.get('frame', frame_data)
        for field in content_fields:
            current_values = frozenset(frame.get(field, []))
            if current_values != first_content[field]:
                return True  # Found a difference

    return False  # All frames have identical content


def _infer_variant_state(frame: Dict, all_frames: List[Dict]) -> str:
    """
    Infer variant state from content differences.

    Looks at errors, buttons, labels to infer: default, error, hover, active, focus, etc.
    """
    # First check name-based state
    name_state = infer_state_from_name(frame.get('name', ''))
    if name_state != 'default':
        return name_state

    # Check content for state indicators
    errors = frame.get('errors', [])
    if errors:
        return 'error'

    # Check for loading/progress indicators in components
    components = [c.lower() for c in frame.get('components', [])]
    if any('spinner' in c or 'loader' in c or 'progress' in c for c in components):
        return 'loading'

    # Check buttons for state hints
    buttons = [b.lower() for b in frame.get('buttons', [])]
    if any('retry' in b or 'try again' in b for b in buttons):
        return 'error'

    # Check if this frame has fewer elements (could be empty state)
    total_content = sum(len(frame.get(f, [])) for f in ['headings', 'labels', 'buttons', 'body'])
    if total_content == 0:
        return 'empty'

    # Check position relative to others for hover/active/focus detection
    # Frames in the same row are often state variants
    pos = frame.get('position', {})
    frame_x = pos.get('x', 0)

    # If this is not the leftmost frame, infer state from position order
    frame_positions = [(f.get('frame', f).get('position', {}).get('x', 0), i)
                       for i, f in enumerate(all_frames)]
    frame_positions.sort()

    # Position order might indicate: default, hover, active, focus, disabled
    position_states = ['default', 'hover', 'active', 'focus', 'disabled']
    for i, (x, idx) in enumerate(frame_positions):
        if abs(x - frame_x) < 10:  # Same x position
            if i < len(position_states):
                return position_states[i]

    return 'variant'


def group_variants(frames: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group frames that are variants of the same screen.

    Detects variants by:
    1. Same base name (with variant suffixes like _error, _hover removed)
    2. Identical names but different content (true state variants)

    Returns dict with frame data including position and inferred state:
    {"Login": [{"name": "Login", "pos": "0,105", "id": "1:100", "state": "default"}, ...]}
    """
    groups = {}

    for frame in frames:
        name = frame.get('name', '')
        base = extract_base_name(name)
        pos = frame.get('position', {})
        pos_str = f"{int(pos.get('x', 0))},{int(pos.get('y', 0))}"

        if base not in groups:
            groups[base] = []
        groups[base].append({
            'name': name,
            'pos': pos_str,
            'id': frame.get('id', ''),
            'frame': frame,  # Keep full frame data for delta computation
        })

    # Return groups that are true variants (different names OR different content)
    result = {}
    for base, variant_list in groups.items():
        if len(variant_list) > 1:
            unique_names = set(v['name'] for v in variant_list)

            # Variants if: different names OR same names but different content
            is_variant_group = (
                len(unique_names) > 1 or
                _frames_have_content_differences(variant_list)
            )

            if is_variant_group:
                # Infer state for each variant
                for v in variant_list:
                    v['state'] = _infer_variant_state(v.get('frame', v), variant_list)
                result[base] = variant_list

    return result


def compute_frame_delta(base_frame: Dict, variant_frame: Dict) -> Dict[str, Any]:
    """
    Compute the differences between a base frame and a variant.

    Returns dict with only the changed/added content:
    {
        'name': 'Login_Error',
        'state': 'error',
        'added': {'errors': ['Invalid email'], 'buttons': ['Retry']},
        'removed': {'buttons': ['Sign In']},
        'changed': {'headings': 'Welcome → Try Again'}
    }
    """
    delta = {
        'name': variant_frame.get('name', ''),
        'id': variant_frame.get('id', ''),
        'state': variant_frame.get('state', 'default'),
        'added': {},
        'removed': {},
        'changed': {},
    }

    # Fields to compare
    content_fields = ['headings', 'labels', 'buttons', 'body', 'errors', 'placeholders']

    for field in content_fields:
        base_values = set(base_frame.get(field, []))
        variant_values = set(variant_frame.get(field, []))

        added = variant_values - base_values
        removed = base_values - variant_values

        if added:
            delta['added'][field] = list(added)[:5]  # Limit to 5
        if removed:
            delta['removed'][field] = list(removed)[:5]

    # Check for changed components
    base_components = set(base_frame.get('components', []))
    variant_components = set(variant_frame.get('components', []))
    added_components = variant_components - base_components
    removed_components = base_components - variant_components

    if added_components:
        delta['added']['components'] = list(added_components)[:5]
    if removed_components:
        delta['removed']['components'] = list(removed_components)[:5]

    # Clean up empty dicts
    if not delta['added']:
        del delta['added']
    if not delta['removed']:
        del delta['removed']
    if not delta['changed']:
        del delta['changed']

    return delta


def get_variant_groups_with_deltas(frames: List[Dict]) -> List[Dict]:
    """
    Get variant groups with computed deltas for efficient output.

    Returns list of variant groups:
    [
        {
            'base_name': 'Login',
            'base_frame': {...full frame data...},
            'variants': [
                {'name': 'Login_Error', 'state': 'error', 'added': {...}, ...},
                ...
            ]
        }
    ]
    """
    groups = group_variants(frames)
    result = []

    for base_name, variant_list in groups.items():
        if len(variant_list) < 2:
            continue

        # Sort variants to find the "default" state as base
        sorted_variants = sorted(variant_list, key=lambda v: (
            0 if infer_state_from_name(v['name']) == 'default' else 1,
            v['name']
        ))

        base_variant = sorted_variants[0]
        base_frame = base_variant.get('frame', {})

        group_data = {
            'base_name': base_name,
            'base_frame': base_frame,
            'variants': [],
        }

        # Compute deltas for other variants
        for variant in sorted_variants[1:]:
            variant_frame = variant.get('frame', {})
            delta = compute_frame_delta(base_frame, variant_frame)
            group_data['variants'].append(delta)

        result.append(group_data)

    return result


def detect_sequences(frames: List[Dict]) -> List[Tuple[str, ...]]:
    """
    Detect sequential flows from frame naming.

    Returns list of sequences: [("01_Login", "02_Verify", "03_Dashboard"), ...]
    """
    # Extract frames with sequence numbers
    sequenced = []
    for frame in frames:
        name = frame.get('name', '')
        seq_info = extract_sequence_number(name)
        if seq_info:
            sequenced.append((seq_info[0], name, frame))

    if not sequenced:
        return []

    # Sort by sequence number
    sequenced.sort(key=lambda x: x[0])

    # Build sequence
    sequence = tuple(item[1] for item in sequenced)
    return [sequence] if len(sequence) > 1 else []


# User journey categories for flow grouping
JOURNEY_CATEGORIES = {
    'authentication': ['login', 'signin', 'sign-in', 'auth', 'password', 'forgot', 'reset'],
    'registration': ['signup', 'sign-up', 'register', 'create account', 'join', 'onboard'],
    'onboarding': ['welcome', 'intro', 'tutorial', 'getting started', 'setup', 'first'],
    'checkout': ['checkout', 'payment', 'cart', 'order', 'purchase', 'billing'],
    'profile': ['profile', 'account', 'settings', 'preferences', 'edit profile'],
    'search': ['search', 'results', 'filter', 'browse', 'explore'],
    'content': ['detail', 'view', 'article', 'post', 'item', 'product'],
}


def infer_journey_category(frame_name: str, buttons: List[str]) -> Optional[str]:
    """
    Infer which user journey a frame belongs to.
    """
    name_lower = frame_name.lower()
    buttons_lower = [b.lower() for b in buttons]
    all_text = name_lower + ' ' + ' '.join(buttons_lower)

    for category, keywords in JOURNEY_CATEGORIES.items():
        if any(kw in all_text for kw in keywords):
            return category
    return None


def detect_user_journeys(frames: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Detect user journeys by analyzing frame names and button actions.

    Returns dict of journeys with frames in order:
    {
        'authentication': [
            {'name': 'Login', 'id': '1:100', 'actions': ['authenticate', 'reset']},
            {'name': 'Forgot Password', 'id': '1:101', 'actions': ['submit_form']},
        ],
        ...
    }
    """
    journeys = {}

    for frame in frames:
        name = frame.get('name', '')
        buttons = frame.get('buttons', [])
        frame_id = frame.get('id', '')

        # Get button destinations
        actions = []
        for btn in buttons:
            btn_text = btn if isinstance(btn, str) else btn.get('text', '')
            if btn_text:
                dest = infer_cta_destination(btn_text, frame_context=name)
                if dest and not dest.startswith('do:'):
                    actions.append(dest)

        # Determine journey category
        category = infer_journey_category(name, buttons)

        if category:
            if category not in journeys:
                journeys[category] = []
            journeys[category].append({
                'name': name,
                'id': frame_id,
                'actions': list(set(actions)),  # Dedupe actions
                'state': infer_state_from_name(name),
            })

    return journeys


def _dedupe_frame_sequence(frame_names: List[str]) -> str:
    """
    Dedupe consecutive identical frame names and show counts.

    "Model Settings > Model Settings > Model Settings" -> "Model Settings (×3)"
    "Login > Login > Dashboard > Dashboard" -> "Login (×2) > Dashboard (×2)"
    "Login > Dashboard > Settings" -> "Login > Dashboard > Settings" (no change)
    """
    if not frame_names:
        return ''

    deduped = []
    count = 1
    prev = frame_names[0]

    for name in frame_names[1:]:
        if name == prev:
            count += 1
        else:
            if count > 1:
                deduped.append(f"{prev} (×{count})")
            else:
                deduped.append(prev)
            prev = name
            count = 1

    # Don't forget the last one
    if count > 1:
        deduped.append(f"{prev} (×{count})")
    else:
        deduped.append(prev)

    return ' > '.join(deduped)


def infer_entry_exit_points(frames: List[Dict]) -> Dict[str, List[str]]:
    """
    Identify entry and exit points in the design.

    Entry points: Frames that are likely starting screens (home, landing, welcome)
    Exit points: Frames with completion/success states or external actions
    """
    entry_keywords = ['home', 'landing', 'welcome', 'splash', 'start', 'main', 'dashboard']
    exit_keywords = ['success', 'complete', 'done', 'confirmed', 'thank', 'finish']

    entry_points = []
    exit_points = []

    for frame in frames:
        name = frame.get('name', '').lower()
        state = frame.get('state', '')

        # Check for entry points
        if any(kw in name for kw in entry_keywords):
            entry_points.append(frame.get('name', ''))

        # Check for exit points
        if any(kw in name for kw in exit_keywords) or state == 'success':
            exit_points.append(frame.get('name', ''))

    return {
        'entry': entry_points[:3],  # Limit to 3
        'exit': exit_points[:3],
    }


# -----------------------------------------------------------------------------
# Text Extraction Helpers
# -----------------------------------------------------------------------------

def extract_text_by_role(
    node: Dict,
    depth: int = 0,
    max_depth: int = 10,
    parent_context: str = ''
) -> Dict[str, List[str]]:
    """
    Recursively extract text content categorized by likely role.

    Improved categorization:
    - Uses font size, weight, and style for heading detection
    - Considers parent container names for context
    - Deduplicates and cleans text
    - Filters out placeholder/system text

    Returns:
        {
            'headings': [...],  # Large/bold text, titles
            'labels': [...],    # Form labels, field names, small descriptive text
            'buttons': [...],   # Text inside interactive elements
            'body': [...],      # Regular body/paragraph text
            'errors': [...],    # Error messages (red text, error containers)
            'placeholders': [...],  # Placeholder/hint text (gray, placeholder in name)
        }
    """
    if depth > max_depth:
        return {'headings': [], 'labels': [], 'buttons': [], 'body': [], 'errors': [], 'placeholders': []}

    result = {'headings': [], 'labels': [], 'buttons': [], 'body': [], 'errors': [], 'placeholders': []}

    node_type = node.get('type', '').upper()
    node_name = node.get('name', '').lower()

    # Build context path for children
    current_context = f"{parent_context}/{node_name}" if parent_context else node_name

    if node_type == 'TEXT':
        text = node.get('characters', '').strip()
        if not text:
            return result

        # Skip very short text that's likely icons or separators
        if len(text) <= 1 and text not in ['?', '!']:
            return result

        # Skip obvious system/template text
        skip_patterns = ['lorem ipsum', 'placeholder', '{{', '}}', 'xxx', '000']
        if any(p in text.lower() for p in skip_patterns):
            return result

        # Get text style info
        style = node.get('style', {})
        font_size = style.get('fontSize', 14)
        font_weight = style.get('fontWeight', 400)
        text_decoration = style.get('textDecoration', '')

        # Check fills for color-based categorization
        fills = node.get('fills', [])
        is_red = any(
            f.get('type') == 'SOLID' and
            f.get('color', {}).get('r', 0) > 0.7 and
            f.get('color', {}).get('g', 0) < 0.3 and
            f.get('color', {}).get('b', 0) < 0.3
            for f in fills if isinstance(f, dict)
        )
        is_gray = any(
            f.get('type') == 'SOLID' and
            abs(f.get('color', {}).get('r', 0) - f.get('color', {}).get('g', 0)) < 0.1 and
            f.get('color', {}).get('r', 0) > 0.4 and
            f.get('color', {}).get('r', 0) < 0.7
            for f in fills if isinstance(f, dict)
        )

        # Categorize based on multiple signals
        # Priority: error > placeholder > heading > label > body

        # Error detection
        if is_red or 'error' in node_name or 'error' in current_context:
            result['errors'].append(text)
        # Placeholder detection
        elif is_gray or 'placeholder' in node_name or 'hint' in node_name:
            result['placeholders'].append(text)
        # Heading detection (large, bold, or semantically marked)
        elif (font_size >= 18 or
              font_weight >= 600 or
              any(h in node_name for h in ['heading', 'title', 'header', 'h1', 'h2', 'h3'])):
            result['headings'].append(text)
        # Label detection (small text, form context, specific naming)
        elif (font_size <= 12 or
              'label' in node_name or
              'caption' in node_name or
              any(ctx in current_context for ctx in ['form', 'input', 'field'])):
            result['labels'].append(text)
        # Everything else is body text
        else:
            result['body'].append(text)

    # Check if this is an interactive element
    is_button = (
        node_type in ['INSTANCE', 'COMPONENT', 'FRAME'] and
        any(kw in node_name for kw in ['button', 'btn', 'cta', 'action', 'link', 'tab', 'chip'])
    )
    is_input = (
        node_type in ['INSTANCE', 'COMPONENT', 'FRAME'] and
        any(kw in node_name for kw in ['input', 'textfield', 'textarea', 'dropdown', 'select'])
    )

    # Recurse into children
    for child in node.get('children', []):
        child_result = extract_text_by_role(child, depth + 1, max_depth, current_context)

        if is_button:
            # All text inside buttons goes to buttons category
            for texts in child_result.values():
                result['buttons'].extend(texts)
        elif is_input:
            # Input text goes to placeholders if gray, otherwise labels
            result['placeholders'].extend(child_result.get('placeholders', []))
            # Other text becomes labels (field values shown)
            for key in ['headings', 'labels', 'body']:
                result['labels'].extend(child_result.get(key, []))
            result['errors'].extend(child_result.get('errors', []))
        else:
            for key in result:
                result[key].extend(child_result.get(key, []))

    return result


def dedupe_and_clean_text(text_list: List[str], max_items: int = 10) -> List[str]:
    """
    Deduplicate and clean a list of text items.

    - Removes duplicates (case-insensitive)
    - Strips whitespace
    - Limits to max_items
    - Preserves order (first occurrence)
    """
    seen = set()
    result = []
    for text in text_list:
        clean = text.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
            if len(result) >= max_items:
                break
    return result


def extract_components(node: Dict, depth: int = 0, max_depth: int = 10) -> List[str]:
    """
    Recursively extract component/instance names.
    """
    if depth > max_depth:
        return []

    components = []
    node_type = node.get('type', '').upper()

    if node_type in ['COMPONENT', 'INSTANCE', 'COMPONENT_SET']:
        name = node.get('name', '')
        if name:
            components.append(name)

    for child in node.get('children', []):
        components.extend(extract_components(child, depth + 1, max_depth))

    return components


# Input field detection - keywords and type mappings
INPUT_TYPE_KEYWORDS = {
    'password': ['password', 'pwd', 'secret'],
    'email': ['email', 'e-mail', 'mail'],
    'phone': ['phone', 'tel', 'mobile', 'cell'],
    'number': ['number', 'numeric', 'amount', 'quantity', 'token', 'tokens', 'max_tokens', 'count', 'limit'],
    'date': ['date', 'calendar'],
    'time': ['time', 'clock'],
    'search': ['search', 'find', 'query'],
    'select': ['select', 'dropdown', 'picker', 'combo', 'menu', 'chooser', 'selector', 'model', 'agent'],
    'textarea': ['textarea', 'multiline', 'description', 'comment', 'message', 'notes', 'prompt'],
    'slider': ['slider', 'range', 'creativity', 'temperature', 'progress', 'reasoning', 'level'],
    'radio': ['radio', 'option', 'choice', 'mode', 'token_mode', 'segment', 'segmented'],
    'toggle': ['toggle', 'switch', 'on/off', 'enable', 'disable', 'active'],
    'checkbox': ['checkbox', 'check', 'agree', 'accept', 'remember'],
    'display': ['display', 'remaining', 'available', 'total', 'used', 'balance', 'info', 'readonly', 'read-only'],
}

# Generic input keywords (fallback to 'text' type)
INPUT_GENERIC_KEYWORDS = ['input', 'textfield', 'field', 'text field', 'text-field',
                          'edittext', 'textbox', 'text box', 'entry', 'form-field', 'form field']

# Required field indicators
REQUIRED_INDICATORS = ['*', 'required', 'mandatory', '(required)', '* required']

# Modal/settings form indicators - deeper extraction needed
MODAL_FORM_KEYWORDS = ['modal', 'dialog', 'settings', 'configuration', 'config', 'preferences', 'options', 'form']


def _extract_all_text_from_node(node: Dict, max_depth: int = 8, depth: int = 0) -> List[Dict]:
    """Extract all text nodes with their context from a node tree."""
    if depth > max_depth:
        return []

    texts = []
    node_type = node.get('type', '').upper()
    node_name = node.get('name', '').lower()

    if node_type == 'TEXT':
        text = node.get('characters', '').strip()
        if text and len(text) > 0:
            # Check if gray (placeholder-like)
            fills = node.get('fills', [])
            is_gray = any(
                f.get('type') == 'SOLID' and
                f.get('color', {}).get('r', 0) > 0.4 and
                f.get('color', {}).get('r', 0) < 0.75 and
                abs(f.get('color', {}).get('r', 0) - f.get('color', {}).get('g', 0)) < 0.15
                for f in fills if isinstance(f, dict)
            )
            # Get font info for better classification
            style = node.get('style', {})
            font_size = style.get('fontSize', 14)
            font_weight = style.get('fontWeight', 400)

            texts.append({
                'text': text,
                'name': node_name,
                'is_gray': is_gray,
                'is_label': 'label' in node_name or font_size <= 12,
                'is_placeholder': 'placeholder' in node_name or 'hint' in node_name,
                'is_value': 'value' in node_name or 'selected' in node_name,
                'is_option': 'option' in node_name or 'item' in node_name,
                'font_size': font_size,
                'is_bold': font_weight >= 600,
            })

    for child in node.get('children', []):
        texts.extend(_extract_all_text_from_node(child, max_depth, depth + 1))

    return texts


def _infer_input_type(name: str, child_count: int = 0) -> Tuple[bool, str]:
    """Infer if node is an input and what type based on name and structure."""
    name_lower = name.lower()

    # Check specific types first
    for input_type, keywords in INPUT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return True, input_type

    # Check generic input keywords
    for kw in INPUT_GENERIC_KEYWORDS:
        if kw in name_lower:
            return True, 'text'

    return False, 'text'


def _clean_input_label(name: str) -> str:
    """Clean up a node name to use as input label."""
    # Get last part if path-like (e.g., "Form/Input/Email" -> "Email")
    label = name.split('/')[-1]

    # Replace separators with spaces
    label = label.replace('_', ' ').replace('-', ' ')

    # Remove common prefixes/suffixes
    remove_patterns = ['input', 'field', 'textfield', 'text field', 'form',
                       'component', 'instance', 'wrapper', 'container', 'group']
    label_lower = label.lower()
    for pattern in remove_patterns:
        label_lower = label_lower.replace(pattern, '')

    # Clean up and title case
    label = ' '.join(label_lower.split()).strip().title()

    return label if label else name


def _detect_form_field_in_subtree(node: Dict, depth: int = 0, max_depth: int = 4) -> Optional[Dict]:
    """
    Detect if a subtree contains a form field with label+input pattern.

    Returns dict with detected field info or None.
    """
    if depth > max_depth:
        return None

    node_type = node.get('type', '').upper()
    node_name = node.get('name', '').lower()
    children = node.get('children', [])

    # Look for label+control patterns
    has_label_node = False
    has_control_node = False
    control_type = 'text'
    label_text = ''
    value_text = ''
    options = []

    for child in children:
        child_name = child.get('name', '').lower()
        child_type = child.get('type', '').upper()

        # Check for label
        if 'label' in child_name or 'title' in child_name:
            has_label_node = True
            texts = _extract_all_text_from_node(child, max_depth=2)
            if texts:
                label_text = texts[0]['text']

        # Check for various control types
        for ctrl_type, keywords in INPUT_TYPE_KEYWORDS.items():
            if any(kw in child_name for kw in keywords):
                has_control_node = True
                control_type = ctrl_type
                # Extract value/options from control
                ctrl_texts = _extract_all_text_from_node(child, max_depth=3)
                for t in ctrl_texts:
                    if t.get('is_value') or t.get('is_option'):
                        if control_type in ['select', 'radio', 'slider']:
                            options.append(t['text'])
                        else:
                            value_text = t['text']
                    elif not value_text and not t.get('is_label'):
                        value_text = t['text']
                break

    # If we found both label and control, return the field info
    if has_label_node and has_control_node and label_text:
        return {
            'name': label_text,
            'type': control_type,
            'value': value_text,
            'options': options[:5],
        }

    return None


def extract_inputs(node: Dict, depth: int = 0, max_depth: int = 12) -> List[Dict[str, Any]]:
    """
    Recursively extract input fields with their labels, types, and options.

    Enhanced to detect:
    - Modal form fields with label+control patterns
    - Sliders with labels (Creativity, Reasoning, etc.)
    - Selectors with current values
    - Display fields (read-only info)
    - Radio/segment controls with options

    Returns list of dicts:
        [{'name': 'Email', 'type': 'email', 'required': True, 'placeholder': '...', 'options': [], 'value': '...'}, ...]
    """
    if depth > max_depth:
        return []

    inputs = []
    node_type = node.get('type', '').upper()
    node_name = node.get('name', '')
    node_name_lower = node_name.lower()
    children = node.get('children', [])

    # Check if this node is a form container (modal, settings panel, etc.)
    is_form_container = any(kw in node_name_lower for kw in MODAL_FORM_KEYWORDS)

    # Strategy 1: Check if this is a direct input component/instance
    is_input = False
    input_type = 'text'

    if node_type in ['COMPONENT', 'INSTANCE', 'COMPONENT_SET', 'FRAME']:
        is_input, input_type = _infer_input_type(node_name, len(children))

    if is_input:
        # Extract all text from this input node
        all_texts = _extract_all_text_from_node(node, max_depth=6)

        label = ''
        placeholder = ''
        value = ''
        options = []
        required = False

        # Check node name for required indicator
        for indicator in REQUIRED_INDICATORS:
            if indicator in node_name_lower:
                required = True
                break

        # Process extracted texts with improved categorization
        for t in all_texts:
            text = t['text']

            # Check for required indicators
            if '*' in text:
                required = True
                text = text.replace('*', '').strip()

            # Skip very short text (but allow numbers)
            if len(text) < 2:
                continue

            # Categorize text more carefully
            if t.get('is_placeholder') or (t.get('is_gray') and not t.get('is_value')):
                if not placeholder:
                    placeholder = text
            elif t.get('is_label') or (t.get('font_size', 14) <= 12 and not t.get('is_value')):
                if not label:
                    label = text
            elif t.get('is_value') or t.get('is_option'):
                # Value or option
                if input_type in ['select', 'radio', 'slider']:
                    options.append(text)
                else:
                    if not value:
                        value = text
            else:
                # Guess based on context and length
                if not label and len(text) < 40:
                    label = text
                elif input_type in ['select', 'radio', 'slider'] and len(text) < 25:
                    options.append(text)
                elif not value:
                    value = text

        # Try to get label from node name if not found
        if not label:
            label = _clean_input_label(node_name)

        # Skip if label is empty or generic
        if not label or label.lower() in ['input', 'field', '', 'text', 'frame']:
            label = _clean_input_label(node_name) or 'Input'

        # Only add if we have a meaningful label
        if label and label.lower() not in ['', 'input', 'field', 'frame', 'instance', 'component']:
            input_data = {
                'name': label,
                'type': input_type,
                'required': required,
                'placeholder': placeholder,
            }
            # Add value if present
            if value:
                input_data['value'] = value
            # Add options for select/radio/slider types
            if options and input_type in ['select', 'radio', 'slider']:
                input_data['options'] = list(dict.fromkeys(options))[:6]  # Dedupe, limit to 6

            inputs.append(input_data)
        # Don't recurse into detected input nodes
        return inputs

    # Strategy 2: For form containers, try to detect label+control patterns
    if is_form_container or node_type == 'FRAME':
        for child in children:
            field = _detect_form_field_in_subtree(child, depth=0, max_depth=4)
            if field:
                input_data = {
                    'name': field['name'],
                    'type': field['type'],
                    'required': False,
                    'placeholder': '',
                }
                if field.get('value'):
                    input_data['value'] = field['value']
                if field.get('options'):
                    input_data['options'] = field['options']
                inputs.append(input_data)

    # Recurse into children
    for child in children:
        inputs.extend(extract_inputs(child, depth + 1, max_depth))

    # Deduplicate by name (keep first occurrence)
    seen_names = set()
    deduped = []
    for inp in inputs:
        name_key = inp['name'].lower()
        if name_key not in seen_names:
            seen_names.add(name_key)
            deduped.append(inp)

    return deduped


# Component category keywords for semantic grouping
COMPONENT_CATEGORIES = {
    'buttons': ['button', 'btn', 'cta', 'action', 'submit'],
    'inputs': ['input', 'textfield', 'textarea', 'field', 'form'],
    'selects': ['dropdown', 'select', 'picker', 'combo', 'menu'],
    'toggles': ['toggle', 'switch', 'checkbox', 'radio'],
    'cards': ['card', 'tile', 'item', 'cell'],
    'navigation': ['nav', 'tab', 'menu', 'breadcrumb', 'link', 'header', 'footer', 'sidebar'],
    'icons': ['icon', 'ico', 'glyph', 'symbol'],
    'images': ['image', 'img', 'photo', 'avatar', 'thumbnail', 'picture'],
    'modals': ['modal', 'dialog', 'popup', 'overlay', 'sheet', 'drawer'],
    'lists': ['list', 'table', 'grid', 'row', 'column'],
    'badges': ['badge', 'tag', 'chip', 'label', 'pill'],
    'progress': ['progress', 'spinner', 'loader', 'loading', 'skeleton'],
    'alerts': ['alert', 'toast', 'notification', 'banner', 'snackbar'],
    'dividers': ['divider', 'separator', 'line', 'hr'],
}


def categorize_components(components: List[str]) -> Dict[str, List[str]]:
    """
    Group components into semantic categories.

    Returns:
        {
            'buttons': ['Button/Primary', 'Button/Secondary'],
            'inputs': ['Input/Text', 'Input/Email'],
            'other': ['CustomComponent'],
            ...
        }
    """
    categorized = {cat: [] for cat in COMPONENT_CATEGORIES}
    categorized['other'] = []

    for component in components:
        comp_lower = component.lower()
        found_category = False

        for category, keywords in COMPONENT_CATEGORIES.items():
            if any(kw in comp_lower for kw in keywords):
                categorized[category].append(component)
                found_category = True
                break

        if not found_category:
            categorized['other'].append(component)

    # Remove empty categories
    return {k: v for k, v in categorized.items() if v}


def format_component_summary(components: List[str]) -> str:
    """
    Format components into a semantic summary.

    Instead of: "Button/Primary, Button/Secondary, Input/Text, Icon/Search"
    Returns: "2 buttons, 1 input, 1 icon"
    """
    if not components:
        return ''

    categorized = categorize_components(components)

    # Build summary parts with counts
    parts = []
    # Priority order for display
    priority = ['buttons', 'inputs', 'selects', 'toggles', 'cards', 'navigation',
                'modals', 'lists', 'alerts', 'badges', 'images', 'icons', 'progress', 'dividers', 'other']

    for cat in priority:
        if cat in categorized:
            count = len(categorized[cat])
            # Use singular/plural
            if cat == 'other':
                label = 'other' if count == 1 else 'other'
            else:
                label = cat.rstrip('s') if count == 1 else cat
            parts.append(f"{count} {label}")

    return ', '.join(parts[:6])  # Limit to 6 categories


def get_key_components(components: List[str], max_items: int = 5) -> List[str]:
    """
    Get the most important/unique component names for display.

    Prioritizes:
    - Interactive elements (buttons, inputs)
    - Unique component names
    - Avoids generic names (icons, dividers)
    """
    if not components:
        return []

    categorized = categorize_components(components)

    result = []
    # Priority order: interactive first
    priority = ['buttons', 'inputs', 'selects', 'modals', 'cards', 'navigation', 'other']

    for cat in priority:
        if cat in categorized:
            # Take first few unique components from this category
            for comp in categorized[cat]:
                if comp not in result:
                    result.append(comp)
                    if len(result) >= max_items:
                        return result

    return result


# -----------------------------------------------------------------------------
# Input Format Standardization
# -----------------------------------------------------------------------------

# Standard limits for input formatting
INPUT_FORMAT_MAX_INPUTS = 10
INPUT_FORMAT_MAX_OPTIONS = 5
INPUT_FORMAT_MAX_VALUE_LEN = 35


def format_single_input(
    label: str,
    input_type: str,
    required: bool = False,
    value: Optional[str] = None,
    options: Optional[List[str]] = None,
    placeholder: Optional[str] = None,
) -> str:
    """
    Format a single input field in standardized TOON format.

    Standard format: Label* (type): "value" or Label* (type): [Opt1/Opt2/...]

    Args:
        label: Input label/name
        input_type: Type (text, email, slider, select, etc.)
        required: Whether field is required (adds * marker)
        value: Current value shown
        options: Options for select/radio/slider types
        placeholder: Placeholder text (fallback if no value/options)

    Returns:
        Formatted input string
    """
    req_marker = '*' if required else ''
    base_str = f"{label}{req_marker} ({input_type})"

    # Priority: value > options > placeholder
    if value and len(str(value)) < INPUT_FORMAT_MAX_VALUE_LEN:
        base_str += f': "{value}"'
    elif options:
        opts_str = '/'.join(options[:INPUT_FORMAT_MAX_OPTIONS])
        base_str += f": [{opts_str}]"
    elif placeholder and len(str(placeholder)) < INPUT_FORMAT_MAX_VALUE_LEN:
        base_str += f': "{placeholder}"'

    return base_str


def format_inputs_list(inputs: List[Dict], max_inputs: int = INPUT_FORMAT_MAX_INPUTS) -> str:
    """
    Format a list of input fields in standardized TOON format.

    Args:
        inputs: List of input dicts with keys: name, type, required, value, options, placeholder
        max_inputs: Maximum inputs to include

    Returns:
        Formatted string: "Input1 (type) | Input2* (type): value | ..."
    """
    if not inputs:
        return ''

    input_strs = []
    for inp in inputs[:max_inputs]:
        formatted = format_single_input(
            label=inp.get('name', inp.get('label', 'Input')),
            input_type=inp.get('type', inp.get('input_type', 'text')),
            required=inp.get('required', False),
            value=inp.get('value', inp.get('current_value')),
            options=inp.get('options'),
            placeholder=inp.get('placeholder'),
        )
        input_strs.append(formatted)

    return ' | '.join(input_strs)


# -----------------------------------------------------------------------------
# TOON Serializer
# -----------------------------------------------------------------------------

class TOONSerializer:
    """Serialize Figma data to TOON format."""

    def __init__(self, indent: str = TOON_INDENT):
        self.indent = indent

    def _i(self, level: int) -> str:
        """Get indentation for level."""
        return self.indent * level

    def serialize_file(self, file_data: Dict) -> str:
        """
        Serialize entire file structure to TOON format.

        Expected input:
        {
            'name': 'File Name',
            'key': 'abc123',
            'pages': [...]
        }
        """
        lines = []

        # File header
        name = file_data.get('name', 'Untitled')
        key = file_data.get('key', '')
        lines.append(f"FILE: {name} [key:{key}]")

        # Pages
        for page in file_data.get('pages', []):
            lines.extend(self.serialize_page(page, level=1))

        # Global flow analysis
        all_frames = []
        for page in file_data.get('pages', []):
            all_frames.extend(page.get('frames', []))

        flow_lines = self.serialize_flows(all_frames, level=1)
        if flow_lines:
            lines.append(f"{self._i(1)}FLOWS:")
            lines.extend(flow_lines)

        return '\n'.join(lines)

    def serialize_page(self, page_data: Dict, level: int = 0, dedupe_variants: bool = True) -> List[str]:
        """
        Serialize a single page.

        Args:
            page_data: Page data dict
            level: Indentation level
            dedupe_variants: If True, group variants and show only deltas (default True)
        """
        lines = []

        name = page_data.get('name', 'Untitled Page')
        page_id = page_data.get('id', '')
        id_str = f" #{page_id}" if page_id else ''
        lines.append(f"{self._i(level)}PAGE: {name}{id_str}")

        frames = page_data.get('frames', [])

        if dedupe_variants and len(frames) > 1:
            # Get variant groups with deltas
            variant_groups = get_variant_groups_with_deltas(frames)

            # Track which frames are in variant groups (to avoid double-output)
            variant_frame_ids = set()
            for group in variant_groups:
                variant_frame_ids.add(group['base_frame'].get('id', ''))
                for v in group['variants']:
                    variant_frame_ids.add(v.get('id', ''))

            # Output non-variant frames normally
            for frame in frames:
                if frame.get('id', '') not in variant_frame_ids:
                    lines.extend(self.serialize_frame(frame, level + 1))

            # Output variant groups with deduplication
            for group in variant_groups:
                lines.extend(self.serialize_variant_group(group, level + 1))
        else:
            # No deduplication - output all frames
            for frame in frames:
                lines.extend(self.serialize_frame(frame, level + 1))

        return lines

    def serialize_variant_group(self, group: Dict, level: int = 0) -> List[str]:
        """
        Serialize a variant group with base frame + deltas.

        Format:
        VARIANT_GROUP: Login (3 variants)
          [base] FRAME: Login [0,0 375x812] form/default #1:100
            Headings: Welcome Back
            ...
          [variant] Login_Error (error) #1:101: +Errors: Invalid email
          [variant] Login_Loading (loading) #1:102: +Components: Spinner
        """
        lines = []

        base_name = group['base_name']
        base_frame = group['base_frame']
        variants = group['variants']
        total_count = 1 + len(variants)

        # Group header
        lines.append(f"{self._i(level)}VARIANT_GROUP: {base_name} ({total_count} states)")

        # Base frame (full output)
        base_lines = self.serialize_frame(base_frame, level + 1)
        if base_lines:
            # Mark first line as [base]
            base_lines[0] = base_lines[0].replace('FRAME:', '[base] FRAME:', 1)
            lines.extend(base_lines)

        # Variant deltas (compact)
        for delta in variants:
            delta_line = self._serialize_delta(delta, level + 1)
            lines.append(delta_line)

        return lines

    def _serialize_delta(self, delta: Dict, level: int) -> str:
        """Serialize a variant delta in compact form."""
        name = delta.get('name', '')
        state = delta.get('state', 'default')
        frame_id = delta.get('id', '')

        parts = [f"{self._i(level)}[{state}] {name}"]
        if frame_id:
            parts[0] += f" #{frame_id}"
        parts[0] += ":"

        # Added content
        added = delta.get('added', {})
        for field, values in added.items():
            if values:
                parts.append(f"+{field.capitalize()}: {', '.join(str(v) for v in values[:3])}")

        # Removed content
        removed = delta.get('removed', {})
        for field, values in removed.items():
            if values:
                parts.append(f"-{field.capitalize()}: {', '.join(str(v) for v in values[:3])}")

        # If no changes, note that
        if not added and not removed:
            parts.append("(no content change)")

        return ' '.join(parts)

    def serialize_frame(self, frame_data: Dict, level: int = 0) -> List[str]:
        """Serialize a single frame with all its content."""
        lines = []

        # Frame header: name [position size] type/state ~variant_of #id
        name = frame_data.get('name', 'Untitled')
        frame_id = frame_data.get('id', '')
        pos = frame_data.get('position', {})
        size = frame_data.get('size', {})
        screen_type = frame_data.get('type', 'screen')
        state = frame_data.get('state', 'default')
        variant_of = frame_data.get('variant_of', '')

        # Build position/size string
        pos_str = ''
        if pos:
            x, y = int(pos.get('x', 0)), int(pos.get('y', 0))
            pos_str = f"[{x},{y}"
            if size:
                w, h = int(size.get('w', 0)), int(size.get('h', 0))
                pos_str += f" {w}x{h}"
            pos_str += "]"

        # Build variant marker
        variant_str = f" ~{variant_of}" if variant_of else ''

        # Build frame ID marker
        id_str = f" #{frame_id}" if frame_id else ''

        header = f"{self._i(level)}FRAME: {name} {pos_str} {screen_type}/{state}{variant_str}{id_str}".strip()
        lines.append(header)

        # Content sections
        content_level = level + 1

        # Headings
        headings = frame_data.get('headings', [])
        if headings:
            lines.append(f"{self._i(content_level)}Headings: {' | '.join(headings[:5])}")

        # Labels
        labels = frame_data.get('labels', [])
        if labels:
            lines.append(f"{self._i(content_level)}Labels: {' | '.join(labels[:10])}")

        # Buttons with destinations
        buttons = frame_data.get('buttons', [])
        if buttons:
            btn_strs = []
            for btn in buttons[:8]:
                if isinstance(btn, dict):
                    text = btn.get('text', '')
                    dest = btn.get('destination', '')
                    btn_strs.append(f"{text} > {dest}" if dest else text)
                else:
                    dest = infer_cta_destination(btn)
                    btn_strs.append(f"{btn} > {dest}")
            lines.append(f"{self._i(content_level)}Buttons: {' | '.join(btn_strs)}")

        # Input fields (using standardized format)
        inputs = frame_data.get('inputs', [])
        if inputs:
            inputs_str = format_inputs_list(inputs)
            if inputs_str:
                lines.append(f"{self._i(content_level)}Inputs: {inputs_str}")

        # Errors
        errors = frame_data.get('errors', [])
        if errors:
            lines.append(f"{self._i(content_level)}Errors: {' | '.join(errors[:3])}")

        # Placeholders (for form fields) - skip if we have inputs
        placeholders = frame_data.get('placeholders', [])
        if placeholders and not inputs:
            lines.append(f"{self._i(content_level)}Placeholders: {' | '.join(placeholders[:5])}")

        # Body text (truncated, only show if meaningful)
        body = frame_data.get('body', [])
        if body:
            # Join and truncate intelligently
            body_text = ' '.join(body)
            if len(body_text) > 150:
                body_text = body_text[:147] + '...'
            lines.append(f"{self._i(content_level)}Text: {body_text}")

        # Components - show semantic summary plus key component names
        components = frame_data.get('components', [])
        if components:
            summary = format_component_summary(components)
            key_comps = get_key_components(components, max_items=5)
            if summary:
                comp_line = f"{self._i(content_level)}Components: {summary}"
                # Add key component names if they add value
                if key_comps and len(key_comps) <= 5:
                    comp_line += f" ({', '.join(key_comps)})"
                lines.append(comp_line)

        # Image description (if any)
        image_desc = frame_data.get('image_description', '')
        if image_desc:
            desc_truncated = image_desc[:300]
            if len(image_desc) > 300:
                desc_truncated += '...'
            lines.append(f"{self._i(content_level)}Image: {desc_truncated}")

        return lines

    def serialize_flows(self, frames: List[Dict], level: int = 0) -> List[str]:
        """Generate flow analysis section with semantic insights."""
        lines = []

        # Entry/exit points
        points = infer_entry_exit_points(frames)
        if points['entry']:
            lines.append(f"{self._i(level + 1)}entry_points: {', '.join(points['entry'])}")
        if points['exit']:
            lines.append(f"{self._i(level + 1)}exit_points: {', '.join(points['exit'])}")

        # Detect user journeys (grouped by purpose)
        journeys = detect_user_journeys(frames)
        for journey_name, journey_frames in journeys.items():
            if journey_frames:
                # Format: journey_name: Frame1 > Frame2 or Frame1 (×3) if repeated
                frame_names = [f['name'] for f in journey_frames[:10]]  # Limit to 10
                journey_str = _dedupe_frame_sequence(frame_names)
                lines.append(f"{self._i(level + 1)}{journey_name}: {journey_str}")

        # Detect sequences (numbered frames suggesting flow order)
        sequences = detect_sequences(frames)
        for seq in sequences:
            # Use dedupe to handle repeated names
            seq_str = _dedupe_frame_sequence(list(seq))
            # Skip if already covered by a journey (check deduped version)
            if not any(seq_str in line for line in lines):
                lines.append(f"{self._i(level + 1)}sequence: {seq_str}")

        # Detect variants (frames that are states of the same screen)
        variants = group_variants(frames)
        for base, variant_list in variants.items():
            if len(variant_list) > 1:
                # Format: base (N variants: state1, state2, state3)
                states = [v.get('state', 'default') for v in variant_list]
                unique_states = list(dict.fromkeys(states))  # Preserve order, dedupe
                count = len(variant_list)
                states_str = ', '.join(unique_states[:5])  # Limit to 5 states
                lines.append(f"{self._i(level + 1)}variants: {base} ({count} variants: {states_str})")

        # Extract CTA destinations with context awareness
        cta_by_category = {}  # Group CTAs by destination category
        for frame in frames:
            frame_name = frame.get('name', '')
            for btn in frame.get('buttons', []):
                btn_text = btn if isinstance(btn, str) else btn.get('text', '')
                if btn_text:
                    dest = infer_cta_destination(btn_text, frame_context=frame_name)
                    if dest:  # None means filtered out (icons, etc.)
                        # Group by destination category for cleaner output
                        if dest not in cta_by_category:
                            cta_by_category[dest] = set()
                        cta_by_category[dest].add(btn_text)

        # Format CTAs grouped by action type
        if cta_by_category:
            # Primary actions first
            priority_order = ['authenticate', 'register', 'submit_form', 'save', 'pay',
                            'navigate_next', 'create', 'view_detail']
            sorted_categories = sorted(cta_by_category.keys(),
                key=lambda x: priority_order.index(x) if x in priority_order else 100)

            cta_strs = []
            for cat in sorted_categories[:8]:  # Limit to 8 categories
                buttons = list(cta_by_category[cat])[:3]  # Max 3 buttons per category
                if cat.startswith('do:'):
                    # Custom action - show as-is
                    cta_strs.append(f'"{buttons[0]}"')
                else:
                    # Known category
                    cta_strs.append(f'{", ".join(buttons)} > {cat}')
            lines.append(f"{self._i(level + 1)}actions: {' | '.join(cta_strs)}")

        return lines


# -----------------------------------------------------------------------------
# Frame Processing
# -----------------------------------------------------------------------------

def process_frame_to_toon_data(frame_node: Dict) -> Dict:
    """
    Process a Figma frame node into TOON-ready data structure.

    Returns structured data that can be serialized to TOON format.
    """
    name = frame_node.get('name', 'Untitled')

    # Extract position and size
    bounds = frame_node.get('absoluteBoundingBox', {})
    position = {'x': bounds.get('x', 0), 'y': bounds.get('y', 0)}
    size = {'w': bounds.get('width', 0), 'h': bounds.get('height', 0)}

    # Extract text by role
    text_data = extract_text_by_role(frame_node)

    # Extract components
    components = extract_components(frame_node)

    # Extract input fields
    inputs = extract_inputs(frame_node)
    # Dedupe inputs by name
    seen_inputs = set()
    unique_inputs = []
    for inp in inputs:
        if inp['name'] not in seen_inputs:
            seen_inputs.add(inp['name'])
            unique_inputs.append(inp)

    # Build frame data with deduplication
    frame_data = {
        'id': frame_node.get('id', ''),
        'name': name,
        'position': position,
        'size': size,
        # Deduplicate and limit text fields
        'headings': dedupe_and_clean_text(text_data['headings'], max_items=5),
        'labels': dedupe_and_clean_text(text_data['labels'], max_items=15),
        'buttons': dedupe_and_clean_text(text_data['buttons'], max_items=10),
        'inputs': unique_inputs[:10],  # Limit to 10 inputs
        'body': dedupe_and_clean_text(text_data['body'], max_items=10),
        'errors': dedupe_and_clean_text(text_data['errors'], max_items=5),
        'placeholders': dedupe_and_clean_text(text_data.get('placeholders', []), max_items=5),
        'components': list(dict.fromkeys(components))[:15],  # Dedupe components too
    }

    # Infer type and state
    frame_data['type'] = infer_screen_type(frame_data)
    frame_data['state'] = infer_state_from_name(name)

    # Check if variant
    base_name = extract_base_name(name)
    if base_name != name:
        frame_data['variant_of'] = base_name

    return frame_data


def process_page_to_toon_data(page_node: Dict, max_frames: int = 50) -> Dict:
    """
    Process a Figma page node into TOON-ready data structure.

    Args:
        page_node: Figma page node dict
        max_frames: Maximum number of frames to process (default 50)
    """
    frames = []

    # Process each child frame (limited by max_frames)
    children = page_node.get('children', [])[:max_frames]
    for child in children:
        child_type = child.get('type', '').upper()

        # Process frames, components, and component sets
        if child_type in ['FRAME', 'COMPONENT', 'COMPONENT_SET', 'SECTION']:
            frame_data = process_frame_to_toon_data(child)
            frames.append(frame_data)

    # Sort frames by position (left-to-right, top-to-bottom)
    frames.sort(key=lambda f: (f['position']['y'], f['position']['x']))

    return {
        'id': page_node.get('id', ''),
        'name': page_node.get('name', 'Untitled Page'),
        'frames': frames,
    }


# -----------------------------------------------------------------------------
# LLM Analysis Functions
# -----------------------------------------------------------------------------

def analyze_frame_with_llm(
    frame_data: Dict,
    llm: Any,
    toon_serializer: Optional['TOONSerializer'] = None,
    image_url: Optional[str] = None,
) -> Optional[ScreenExplanation]:
    """
    Analyze a single frame using LLM with structured output.

    Supports vision-based analysis when image_url is provided (for multimodal LLMs).
    Falls back to text-based analysis using TOON data otherwise.

    Args:
        frame_data: Processed frame data dict
        llm: LangChain LLM instance with structured output support
        toon_serializer: Optional serializer for formatting
        image_url: Optional URL to frame image for vision-based analysis

    Returns:
        ScreenExplanation model or None if analysis fails
    """
    if not llm:
        return None

    frame_name = frame_data.get('name', 'Unknown')
    frame_id = frame_data.get('id', '')

    # Try vision-based analysis first if image available
    if image_url:
        try:
            from langchain_core.messages import HumanMessage

            structured_llm = llm.with_structured_output(ScreenExplanation)
            prompt_text = SCREEN_VISION_PROMPT.format(
                frame_name=frame_name,
                frame_id=frame_id,
            )

            # Create message with image content
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
            )
            result = structured_llm.invoke([message])
            if result:
                return result
        except Exception as e:
            # Vision analysis failed - fall back to text-based
            logging.warning(f"Vision analysis failed for {frame_name}, falling back to text: {type(e).__name__}: {e}")

    # Text-based analysis (fallback or primary if no image)
    try:
        if toon_serializer is None:
            toon_serializer = TOONSerializer()

        toon_lines = toon_serializer.serialize_frame(frame_data, level=0)
        toon_data = '\n'.join(toon_lines)

        prompt = SCREEN_TEXT_PROMPT.format(
            frame_name=frame_name,
            frame_id=frame_id,
            toon_data=toon_data,
        )

        structured_llm = llm.with_structured_output(ScreenExplanation)
        result = structured_llm.invoke(prompt)
        return result

    except Exception as e:
        logging.warning(f"LLM frame analysis failed for {frame_name}: {type(e).__name__}: {e}")
        return None


def analyze_file_with_llm(
    file_data: Dict,
    llm: Any,
    max_screens: int = 10,
) -> Optional[DesignAnalysis]:
    """
    Analyze entire Figma file using LLM with structured output.

    Args:
        file_data: Processed file data dict with pages and frames
        llm: LangChain LLM instance with structured output support
        max_screens: Maximum screens to include in analysis (for token limits)

    Returns:
        DesignAnalysis model or None if analysis fails
    """
    if not llm:
        return None

    try:
        # Serialize file to TOON format
        serializer = TOONSerializer()
        toon_output = serializer.serialize_file(file_data)

        # Truncate if too long (rough token estimate: 4 chars per token)
        max_chars = 8000  # ~2000 tokens for input
        if len(toon_output) > max_chars:
            toon_output = toon_output[:max_chars] + "\n... (truncated)"

        # Build prompt
        prompt = FILE_ANALYSIS_PROMPT.format(toon_data=toon_output)

        # Call LLM with structured output
        structured_llm = llm.with_structured_output(DesignAnalysis)
        result = structured_llm.invoke(prompt)

        return result

    except Exception as e:
        logging.warning(f"LLM file analysis failed: {e}")
        return None


def analyze_flows_with_llm(
    frames: List[Dict],
    llm: Any,
) -> Optional[FlowAnalysis]:
    """
    Analyze user flows using LLM with structured output.

    Args:
        frames: List of processed frame data dicts
        llm: LangChain LLM instance with structured output support

    Returns:
        FlowAnalysis model or None if analysis fails
    """
    if not llm or not frames:
        return None

    try:
        # Build compact frame summary for LLM
        frame_lines = []
        for f in frames[:20]:  # Limit to 20 frames
            name = f.get('name', 'Unknown')
            buttons = f.get('buttons', [])[:3]  # Top 3 buttons
            btn_str = ', '.join(buttons) if buttons else '-'
            frame_lines.append(f"- {name}: [{btn_str}]")

        frame_summary = '\n'.join(frame_lines)

        # Build prompt
        prompt = FLOW_ANALYSIS_PROMPT.format(frame_summary=frame_summary)

        # Call LLM with structured output
        structured_llm = llm.with_structured_output(FlowAnalysis)
        result = structured_llm.invoke(prompt)

        return result

    except Exception as e:
        logging.warning(f"LLM flow analysis failed: {e}")
        return None


def serialize_flow_analysis(analysis: FlowAnalysis, level: int = 0) -> List[str]:
    """Serialize LLM flow analysis to TOON format."""
    lines = []
    indent = TOON_INDENT * (level + 1)

    # Navigation pattern
    if analysis.navigation_pattern:
        lines.append(f"{indent}pattern: {analysis.navigation_pattern}")

    # Entry/exit points
    if analysis.entry_points:
        lines.append(f"{indent}entry: {', '.join(analysis.entry_points[:3])}")
    if analysis.completion_points:
        lines.append(f"{indent}completion: {', '.join(analysis.completion_points[:3])}")

    # Main flows
    for flow in analysis.main_flows[:4]:  # Limit to 4 flows
        # Format: flow_name: Screen1 > Screen2 or Screen1 (×3) if repeated (description)
        screens_str = _dedupe_frame_sequence(flow.screens[:10])  # Max 10 screens
        flow_line = f"{indent}{flow.name}: {screens_str}"
        if flow.description:
            flow_line += f" ({flow.description})"
        lines.append(flow_line)

    return lines


def serialize_screen_explanation(
    explanation: ScreenExplanation,
    indent: str = TOON_INDENT,
    level: int = 0,
) -> List[str]:
    """
    Serialize a ScreenExplanation to TOON-compatible format.

    Returns list of formatted lines.
    """
    lines = []
    i = indent * level

    lines.append(f"{i}EXPLANATION: {explanation.frame_name} #{explanation.frame_id}")
    lines.append(f"{i}{indent}Purpose: {explanation.purpose}")
    lines.append(f"{i}{indent}User Goal: {explanation.user_goal}")

    if explanation.primary_action:
        lines.append(f"{i}{indent}Primary Action: {explanation.primary_action}")

    if explanation.secondary_actions:
        lines.append(f"{i}{indent}Secondary Actions: {', '.join(explanation.secondary_actions)}")

    if explanation.input_fields:
        lines.append(f"{i}{indent}Inputs Required: {', '.join(explanation.input_fields)}")

    if explanation.state_indicators:
        lines.append(f"{i}{indent}State Indicators: {', '.join(explanation.state_indicators)}")

    # Element mappings (compact format)
    if explanation.element_mappings:
        lines.append(f"{i}{indent}Element Map:")
        for mapping in explanation.element_mappings[:5]:  # Limit to 5
            action_str = f" -> {mapping.user_action}" if mapping.user_action else ""
            lines.append(f"{i}{indent}{indent}{mapping.element_type}: \"{mapping.extracted_value}\" = {mapping.semantic_meaning}{action_str}")

    return lines


def serialize_design_analysis(
    analysis: DesignAnalysis,
    indent: str = TOON_INDENT,
) -> str:
    """
    Serialize a complete DesignAnalysis to readable format.

    Returns formatted string.
    """
    lines = []

    lines.append(f"DESIGN ANALYSIS: {analysis.file_name}")
    lines.append(f"{indent}Type: {analysis.design_type}")
    lines.append(f"{indent}Target User: {analysis.target_user}")
    lines.append(f"{indent}Purpose: {analysis.overall_purpose}")

    if analysis.design_patterns:
        lines.append(f"{indent}Patterns: {', '.join(analysis.design_patterns)}")

    # Flows
    if analysis.flows:
        lines.append(f"{indent}USER FLOWS:")
        for flow in analysis.flows:
            lines.append(f"{indent}{indent}{flow.flow_name}: {flow.entry_point} > ... > {flow.exit_point}")
            lines.append(f"{indent}{indent}{indent}{flow.description}")
            if flow.error_states:
                lines.append(f"{indent}{indent}{indent}Error states: {', '.join(flow.error_states)}")

    # Screens
    if analysis.screens:
        lines.append(f"{indent}SCREENS ({len(analysis.screens)}):")
        for screen in analysis.screens:
            lines.append(f"{indent}{indent}{screen.frame_name}: {screen.purpose}")
            if screen.primary_action:
                lines.append(f"{indent}{indent}{indent}Primary: {screen.primary_action}")

    # Concerns
    if analysis.gaps_or_concerns:
        lines.append(f"{indent}GAPS/CONCERNS:")
        for concern in analysis.gaps_or_concerns:
            lines.append(f"{indent}{indent}- {concern}")

    # Accessibility
    if analysis.accessibility_notes:
        lines.append(f"{indent}ACCESSIBILITY:")
        for note in analysis.accessibility_notes:
            lines.append(f"{indent}{indent}- {note}")

    return '\n'.join(lines)


def enrich_toon_with_llm_analysis(
    toon_output: str,
    file_data: Dict,
    llm: Any,
    analysis_level: str = 'summary',
    frame_images: Optional[Dict[str, str]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    include_design_insights: bool = True,
    parallel_workers: int = 5,
    max_frames_to_analyze: int = 50,
) -> str:
    """
    Enrich TOON output with LLM-generated explanations.

    For 'detailed' mode, explanations are merged inline with each FRAME.
    Supports vision-based analysis when frame_images are provided.
    For 'summary' mode, only file-level analysis is appended.

    Args:
        toon_output: Base TOON formatted string
        file_data: Processed file data
        llm: LangChain LLM instance
        analysis_level: 'summary' (file-level only) or 'detailed' (per-screen inline)
        frame_images: Optional dict mapping frame_id -> image_url for vision analysis
        status_callback: Optional callback for progress updates
        include_design_insights: Whether to include DESIGN INSIGHTS section (default True)
        parallel_workers: Number of parallel LLM workers (default 5)
        max_frames_to_analyze: Maximum frames to analyze with LLM (default 50)

    Returns:
        Enriched TOON output with LLM analysis
    """
    if not llm:
        return toon_output

    if analysis_level == 'detailed':
        # Re-serialize with inline LLM explanations (with optional vision)
        return serialize_file_with_llm_explanations(
            file_data, llm, frame_images=frame_images, status_callback=status_callback,
            include_design_insights=include_design_insights,
            parallel_workers=parallel_workers,
            max_frames_to_analyze=max_frames_to_analyze,
        )

    # For summary mode, just append file-level analysis
    lines = [toon_output]
    analysis = analyze_file_with_llm(file_data, llm)
    if analysis:
        lines.append("")
        lines.append("=" * 60)
        lines.append("DESIGN ANALYSIS")
        lines.append("=" * 60)
        lines.append(serialize_design_analysis(analysis))

    return '\n'.join(lines)


def serialize_file_with_llm_explanations(
    file_data: Dict,
    llm: Any,
    frame_images: Optional[Dict[str, str]] = None,
    max_frames_to_analyze: int = 50,
    status_callback: Optional[Callable[[str], None]] = None,
    parallel_workers: int = 5,
    include_design_insights: bool = True,
) -> str:
    """
    Serialize file with LLM explanations merged inline with each FRAME.

    Supports vision-based analysis when frame_images dict is provided.
    Uses parallel LLM processing for faster analysis.
    Output uses visual insights instead of element mappings.

    Args:
        file_data: Processed file data dict
        llm: LangChain LLM instance
        frame_images: Optional dict mapping frame_id -> image_url for vision analysis
        max_frames_to_analyze: Maximum frames to analyze with LLM (default 50)
        status_callback: Optional callback function for progress updates
        parallel_workers: Number of parallel LLM workers (default 5)
        include_design_insights: Whether to include DESIGN INSIGHTS section (default True)

    Output format:
    FILE: Name [key:xxx]
      PAGE: Page Name #id
        FRAME: Frame Name [pos] type/state #id
          Purpose: Authentication screen for returning users
          Goal: Sign into account | Action: "Sign In"
          Visual: [focus] title and form | [layout] form-stack | [state] default
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _log_status(msg: str):
        """Log status via callback if provided."""
        logging.info(msg)
        if status_callback:
            try:
                status_callback(msg)
            except Exception:
                pass  # Don't let callback failures break processing

    lines = []
    serializer = TOONSerializer()
    frame_images = frame_images or {}

    # File header
    name = file_data.get('name', 'Untitled')
    key = file_data.get('key', '')
    lines.append(f"FILE: {name} [key:{key}]")

    # Collect all frames first for parallel processing
    all_frames = []
    frame_to_page = {}  # Map frame_id to page info for later

    for page in file_data.get('pages', []):
        for frame in page.get('frames', []):
            all_frames.append(frame)
            frame_to_page[frame.get('id', '')] = {
                'page_name': page.get('name', 'Untitled Page'),
                'page_id': page.get('id', ''),
            }

    total_frames = len(all_frames)
    frames_to_analyze = all_frames[:max_frames_to_analyze]
    _log_status(f"Starting LLM analysis for {len(frames_to_analyze)} of {total_frames} frames...")

    # Parallel LLM analysis
    frame_explanations = {}  # frame_id -> explanation

    def _analyze_single_frame(frame: Dict) -> Tuple[str, Optional[Any]]:
        """Worker function to analyze a single frame."""
        frame_id = frame.get('id', '')
        image_url = frame_images.get(frame_id)
        try:
            explanation = analyze_frame_with_llm(
                frame, llm, serializer, image_url=image_url
            )
            return frame_id, explanation
        except Exception as e:
            logging.warning(f"LLM analysis failed for frame {frame.get('name')}: {e}")
            return frame_id, None

    # Use parallel processing for LLM calls
    if frames_to_analyze:
        workers = min(parallel_workers, len(frames_to_analyze))
        _log_status(f"Analyzing frames with {workers} parallel LLM workers...")
        completed = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_frame = {
                executor.submit(_analyze_single_frame, frame): frame
                for frame in frames_to_analyze
            }

            for future in as_completed(future_to_frame):
                frame = future_to_frame[future]
                frame_name = frame.get('name', 'Untitled')
                try:
                    frame_id, explanation = future.result()
                    if explanation:
                        frame_explanations[frame_id] = explanation
                        _log_status(f"Analyzed {completed + 1}/{len(frames_to_analyze)}: {frame_name} ✓")
                    else:
                        _log_status(f"Analyzed {completed + 1}/{len(frames_to_analyze)}: {frame_name} (no result)")
                    completed += 1
                except Exception as e:
                    completed += 1
                    logging.warning(f"Frame analysis failed for {frame_name}: {e}")
                    _log_status(f"Analyzed {completed}/{len(frames_to_analyze)}: {frame_name} (error: {type(e).__name__})")

    # Summary of LLM analysis results
    success_count = len(frame_explanations)
    _log_status(f"Frame analysis complete: {success_count}/{len(frames_to_analyze)} frames analyzed successfully")

    # Now generate output with pre-computed explanations
    for page in file_data.get('pages', []):
        page_name = page.get('name', 'Untitled Page')
        page_id = page.get('id', '')
        lines.append(f"  PAGE: {page_name} #{page_id}")

        for frame in page.get('frames', []):
            frame_name = frame.get('name', 'Untitled')
            frame_id = frame.get('id', '')
            frame_type = frame.get('type', 'screen')
            frame_state = frame.get('state', 'default')

            # Compact frame header
            pos = frame.get('position', {})
            size = frame.get('size', {})
            pos_str = f"[{int(pos.get('x', 0))},{int(pos.get('y', 0))} {int(size.get('w', 0))}x{int(size.get('h', 0))}]"
            lines.append(f"    FRAME: {frame_name} {pos_str} {frame_type}/{frame_state} #{frame_id}")

            # Get frame content
            headings = frame.get('headings', [])
            buttons = frame.get('buttons', []).copy()  # Copy to allow modification
            inputs = frame.get('inputs', [])
            primary_action = None  # Track LLM-identified action

            # LLM analysis from pre-computed results
            explanation = frame_explanations.get(frame_id)
            if explanation:
                lines.append(f"      Purpose: {explanation.purpose}")
                goal_action = f"Goal: {explanation.user_goal}"
                if explanation.primary_action:
                    primary_action = explanation.primary_action
                    goal_action += f" | Action: \"{primary_action}\""
                lines.append(f"      {goal_action}")

                # Visual insights
                visual_parts = []
                if explanation.visual_focus:
                    visual_parts.append(f"[focus] {explanation.visual_focus}")
                if explanation.layout_pattern:
                    visual_parts.append(f"[layout] {explanation.layout_pattern}")
                if explanation.visual_state and explanation.visual_state != 'default':
                    visual_parts.append(f"[state] {explanation.visual_state}")
                if visual_parts:
                    lines.append(f"      Visual: {' | '.join(visual_parts)}")

            # Ensure primary_action from LLM appears in buttons (button completeness)
            if primary_action:
                # Check if action is already in buttons (case-insensitive)
                buttons_lower = [b.lower() for b in buttons]
                action_lower = primary_action.lower()
                if not any(action_lower in b or b in action_lower for b in buttons_lower):
                    # Add the LLM-identified action to buttons list
                    buttons.insert(0, f"[LLM] {primary_action}")

            # Use LLM-extracted inputs if available (preferred), else fall back to heuristic
            llm_inputs = []
            if explanation and hasattr(explanation, 'inputs') and explanation.inputs:
                llm_inputs = explanation.inputs

            # Extracted content (Headings, Buttons, Inputs)
            if headings:
                lines.append(f"      Headings: {' | '.join(headings[:3])}")
            if buttons:
                # Show buttons with inferred actions
                btn_strs = []
                for btn in buttons[:6]:  # Increased limit to accommodate added LLM action
                    dest = infer_cta_destination(btn, frame_context=frame_name)
                    btn_strs.append(f"{btn} > {dest}" if dest else btn)
                lines.append(f"      Buttons: {' | '.join(btn_strs)}")

            # Prefer LLM-extracted inputs over heuristic extraction (standardized format)
            if llm_inputs:
                # Convert LLM ExtractedInput objects to dicts for standardized formatting
                llm_inputs_dicts = [
                    {
                        'name': inp.label,
                        'type': inp.input_type,
                        'required': inp.required,
                        'value': inp.current_value,
                        'options': inp.options,
                    }
                    for inp in llm_inputs
                ]
                inputs_str = format_inputs_list(llm_inputs_dicts)
                if inputs_str:
                    lines.append(f"      Inputs: {inputs_str}")
            elif inputs:
                # Fallback to heuristic-extracted inputs (standardized format)
                inputs_str = format_inputs_list(inputs)
                if inputs_str:
                    lines.append(f"      Inputs: {inputs_str}")

        lines.append("")  # Blank line after page

    _log_status("Analyzing flows and variants (parallel)...")

    # Run LLM flow analysis and design insights in parallel
    flow_analysis_result = None
    design_analysis_result = None
    flow_error = None
    design_error = None

    def _analyze_flows():
        """Worker for flow analysis."""
        nonlocal flow_analysis_result, flow_error
        try:
            flow_analysis_result = analyze_flows_with_llm(all_frames, llm)
        except Exception as e:
            flow_error = e

    def _analyze_design():
        """Worker for design insights."""
        nonlocal design_analysis_result, design_error
        try:
            design_analysis_result = analyze_file_with_llm(file_data, llm)
        except Exception as e:
            design_error = e

    # Run flow analysis and optionally design insights in parallel
    if all_frames:
        parallel_tasks = [_analyze_flows]
        if include_design_insights:
            parallel_tasks.append(_analyze_design)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(task) for task in parallel_tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.warning(f"Parallel analysis task failed: {e}")

    # Add FLOWS section
    if all_frames:
        lines.append("FLOWS:")
        if flow_analysis_result:
            flow_lines = serialize_flow_analysis(flow_analysis_result, level=0)
            lines.extend(flow_lines)
        elif flow_error:
            logging.warning(f"LLM flow analysis failed, using heuristics: {flow_error}")
            flow_lines = serializer.serialize_flows(all_frames, level=0)
            lines.extend(flow_lines)
        else:
            # Fallback to heuristic flows if LLM returned nothing
            flow_lines = serializer.serialize_flows(all_frames, level=0)
            lines.extend(flow_lines)

    # Explicit VARIANTS section with frame differences (fast heuristic, no parallelization needed)
    if all_frames:
        variants = group_variants(all_frames)
        if variants:
            lines.append("")
            lines.append("VARIANTS:")
            for base, variant_list in variants.items():
                if len(variant_list) > 1:
                    # Group by states
                    states_by_id = {}
                    for v in variant_list:
                        state = v.get('state', 'default')
                        frame_id = v.get('id', '')[:6]  # Short ID
                        states_by_id[f"#{frame_id}"] = state

                    # Detect potential duplicates (same state, similar content)
                    state_groups = {}
                    for v in variant_list:
                        state = v.get('state', 'default')
                        if state not in state_groups:
                            state_groups[state] = []
                        state_groups[state].append(v)

                    # Build variant line
                    lines.append(f"  {base} ({len(variant_list)} frames):")

                    # List variants by state
                    for state, variants_in_state in state_groups.items():
                        ids = [f"#{v.get('id', '')[:6]}" for v in variants_in_state]
                        if len(variants_in_state) > 1:
                            # Potential duplicates or responsive variants
                            lines.append(f"    {state}: {', '.join(ids)} - potential duplicates or responsive")
                        else:
                            # Unique state
                            frame = variants_in_state[0].get('frame', {})
                            # Try to identify distinguishing feature
                            distinguisher = ""
                            if frame.get('headings'):
                                distinguisher = f" - \"{frame['headings'][0][:30]}...\""
                            elif frame.get('inputs'):
                                inp = frame['inputs'][0]
                                distinguisher = f" - {inp.get('type', 'text')} labeled \"{inp.get('name', '')[:20]}\""
                            lines.append(f"    {state}: {ids[0]}{distinguisher}")

    # Add DESIGN INSIGHTS section (if enabled and analysis succeeded)
    if include_design_insights:
        if design_analysis_result:
            _log_status("Adding design insights...")
            lines.append("")
            lines.append("DESIGN INSIGHTS:")
            lines.append(f"  Type: {design_analysis_result.design_type} | Target: {design_analysis_result.target_user}")
            lines.append(f"  Purpose: {design_analysis_result.overall_purpose}")
            if design_analysis_result.design_patterns:
                lines.append(f"  Patterns: {', '.join(design_analysis_result.design_patterns[:5])}")
            if design_analysis_result.gaps_or_concerns:
                lines.append(f"  Gaps: {'; '.join(design_analysis_result.gaps_or_concerns[:3])}")
        elif design_error:
            logging.warning(f"File-level LLM analysis failed: {design_error}")

    return '\n'.join(lines)


# -----------------------------------------------------------------------------
# Args Schemas for New Tools
# -----------------------------------------------------------------------------

FileStructureTOONSchema = create_model(
    "FileStructureTOON",
    url=(
        Optional[str],
        Field(
            description=(
                "Full Figma URL with file key and optional node-id. "
                "Example: 'https://www.figma.com/file/<FILE_KEY>/...?node-id=<NODE_ID>'. "
                "If provided, overrides file_key parameter."
            ),
            default=None,
        ),
    ),
    file_key=(
        Optional[str],
        Field(
            description="Figma file key (used only if URL not provided).",
            default=None,
            examples=["Fp24FuzPwH0L74ODSrCnQo"],
        ),
    ),
    include_pages=(
        Optional[str],
        Field(
            description="Comma-separated page IDs to include. Example: '1:2,1:3'",
            default=None,
        ),
    ),
    exclude_pages=(
        Optional[str],
        Field(
            description="Comma-separated page IDs to exclude (only if include_pages not set).",
            default=None,
        ),
    ),
    max_frames=(
        Optional[int],
        Field(
            description="Maximum frames per page to process. Default: 50",
            default=50,
            ge=1,
            le=200,
        ),
    ),
)


PageFlowsTOONSchema = create_model(
    "PageFlowsTOON",
    url=(
        Optional[str],
        Field(
            description="Full Figma URL pointing to a specific page.",
            default=None,
        ),
    ),
    file_key=(
        Optional[str],
        Field(
            description="Figma file key.",
            default=None,
        ),
    ),
    page_id=(
        Optional[str],
        Field(
            description="Page ID to analyze. Required if URL doesn't include node-id.",
            default=None,
        ),
    ),
)


FrameDetailTOONSchema = create_model(
    "FrameDetailTOON",
    file_key=(
        str,
        Field(
            description="Figma file key.",
            examples=["Fp24FuzPwH0L74ODSrCnQo"],
        ),
    ),
    frame_ids=(
        str,
        Field(
            description="Comma-separated frame IDs to get details for.",
            examples=["1:100,1:200,1:300"],
        ),
    ),
)


# Unified TOON tool with detail levels
AnalyzeFileSchema = create_model(
    "AnalyzeFile",
    url=(
        Optional[str],
        Field(
            description=(
                "Full Figma URL with file key and optional node-id. "
                "Example: 'https://www.figma.com/file/<FILE_KEY>/...?node-id=<NODE_ID>'. "
                "If provided, overrides file_key parameter."
            ),
            default=None,
        ),
    ),
    file_key=(
        Optional[str],
        Field(
            description="Figma file key (used only if URL not provided).",
            default=None,
            examples=["Fp24FuzPwH0L74ODSrCnQo"],
        ),
    ),
    node_id=(
        Optional[str],
        Field(
            description=(
                "Optional node ID to focus on. Can be a page ID or frame ID. "
                "If a frame ID is provided, returns detailed frame analysis."
            ),
            default=None,
        ),
    ),
    include_pages=(
        Optional[str],
        Field(
            description="Comma-separated page IDs to include. Example: '1:2,1:3'",
            default=None,
        ),
    ),
    exclude_pages=(
        Optional[str],
        Field(
            description="Comma-separated page IDs to exclude (only if include_pages not set).",
            default=None,
        ),
    ),
    max_frames=(
        int,
        Field(
            description="Maximum frames per page to process. Default: 50",
            default=50,
            ge=1,
            le=200,
        ),
    ),
    include_design_insights=(
        bool,
        Field(
            description="Include DESIGN INSIGHTS section with file-level LLM analysis. Set to False to skip and speed up processing. Default: True",
            default=True,
        ),
    ),
)
