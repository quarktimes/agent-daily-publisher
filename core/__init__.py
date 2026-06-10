"""
Agent Daily Publisher — Core Agent Framework

A lightweight, self-contained agent framework built from first principles.
No LangChain, no CrewAI, no dependencies beyond Anthropic SDK.

Design philosophy:
  - Agents are not functions — they make decisions via ReAct loops
  - Communication is contract-driven via JSON Schema
  - Tools are dynamically registered, not hard-coded
  - Every decision is observable via the Observer protocol
"""
