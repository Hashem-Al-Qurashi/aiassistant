"""Streamlit frontend scaffold for StratOS War Room.

3-column layout: engagement navigation, AI consultant chat, consulting context.
"""

import streamlit as st
import asyncio
from uuid import uuid4


def render_war_room(engagement_id: str = None):
    """Render the StratOS war room interface."""
    if not engagement_id:
        engagement_id = str(uuid4())

    # 3-column layout
    col1, col2, col3 = st.columns([2, 5, 3])

    with col1:
        st.markdown("## Engagement")
        st.markdown("### Sections")
        sections = [
            "Overview", "Discovery", "Evidence", "Research",
            "Analysis", "Hypotheses", "Recommendations",
            "Decisions", "Deliverables", "Meetings", "Activity",
        ]
        for section in sections:
            if st.button(section, key=f"btn_{section}"):
                st.session_state.selected_section = section

    with col2:
        st.markdown("### AI Consultant")
        render_consultant_chat()
        render_entity_cards()

    with col3:
        st.markdown("### Consulting Context")
        render_context_summary()


def render_consultant_chat():
    """Render chat interface with structured entity creation."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about market entry strategy..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        response = "Based on our research, I recommend entering the Saudi market through a phased approach."  # placeholder
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)


def render_entity_cards():
    """Render rich interactive objects inline."""
    st.markdown("#### Research Questions")
    questions = [
        "What is the total addressable market?",
        "What regulatory barriers exist?",
        "Who are the key competitors?",
    ]
    for q in questions:
        st.markdown(f"- [ ] {q}")


def render_context_summary():
    """Render right sidebar context summary."""
    st.markdown("#### Objective")
    st.markdown("Saudi Market Expansion - Logistics Sector")

    st.markdown("#### Progress")
    st.markdown("Discovery: ✅ Complete")
    st.markdown("Research: ✅ Complete")
    st.markdown("Analysis: 🔄 In Progress")


if __name__ == "__main__":
    render_war_room()
