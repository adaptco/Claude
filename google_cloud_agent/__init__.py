"""
Google Cloud Industry Discovery Agent

Intelligent agent for discovering and recommending industry-specific GCP solutions.
"""

from agent import VertexAIDiscoveryAgent, ConversationContext, SimulatedDiscoverySession
from industry_data import (
    get_industry_info,
    list_industries,
    get_gcp_products_for_industry,
    get_solutions_by_challenge
)

__version__ = "1.0.0"
__author__ = "Google Cloud"

__all__ = [
    "VertexAIDiscoveryAgent",
    "ConversationContext",
    "SimulatedDiscoverySession",
    "get_industry_info",
    "list_industries",
    "get_gcp_products_for_industry",
    "get_solutions_by_challenge",
]
