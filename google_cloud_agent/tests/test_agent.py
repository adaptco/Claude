"""
Test suite for the Google Cloud Industry Discovery Agent

Tests local functionality without requiring Vertex AI credentials.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import VertexAIDiscoveryAgent, ConversationContext
from industry_data import (
    get_industry_info,
    list_industries,
    get_gcp_products_for_industry,
    get_solutions_by_challenge
)


class TestIndustryData:
    """Test industry knowledge base functionality."""
    
    def test_list_industries(self):
        """Test that all industries are available."""
        industries = list_industries()
        assert len(industries) > 0
        assert "Financial Services" in industries
        assert "Retail" in industries
        assert "Healthcare" in industries
    
    def test_get_industry_info(self):
        """Test retrieving industry information."""
        info = get_industry_info("financial_services")
        assert info is not None
        assert "description" in info
        assert "key_challenges" in info
        assert "gcp_solutions" in info
        assert "recommended_gcp_products" in info
    
    def test_get_industry_info_case_insensitive(self):
        """Test that industry lookup is case-insensitive."""
        info1 = get_industry_info("financial_services")
        info2 = get_industry_info("Financial Services")
        info3 = get_industry_info("FINANCIAL_SERVICES")
        
        assert info1 == info2 == info3
    
    def test_get_gcp_products(self):
        """Test retrieving GCP products for an industry."""
        products = get_gcp_products_for_industry("retail")
        assert len(products) > 0
        assert isinstance(products, list)
        assert "BigQuery" in products or "Vertex AI" in products
    
    def test_get_solutions_by_challenge(self):
        """Test mapping challenges to solutions."""
        solutions = get_solutions_by_challenge("healthcare")
        assert len(solutions) > 0
        assert all("description" in sol for sol in solutions.values())
        assert all("services" in sol for sol in solutions.values())


class TestDiscoveryAgent:
    """Test Discovery Agent functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.agent = VertexAIDiscoveryAgent()
        self.context = ConversationContext()
    
    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        assert self.agent is not None
        assert self.agent.conversation_turns == 0
        assert self.agent.max_turns == 10
    
    def test_interview_user(self):
        """Test user interview greeting."""
        greeting = self.agent.interview_user(self.context)
        assert greeting is not None
        assert len(greeting) > 0
        assert "Welcome" in greeting or "industry" in greeting.lower()
    
    def test_analyze_requirements_without_industry(self):
        """Test analysis fails gracefully without industry."""
        analysis = self.agent.analyze_requirements(self.context)
        assert "error" in analysis
    
    def test_analyze_requirements_with_industry(self):
        """Test requirement analysis with industry specified."""
        self.context.industry = "financial_services"
        self.context.challenges = [
            "Real-time fraud detection",
            "Compliance requirements"
        ]
        
        analysis = self.agent.analyze_requirements(self.context)
        assert "error" not in analysis
        assert analysis["industry"] == "financial_services"
        assert "recommended_gcp_products" in analysis
    
    def test_generate_solution_without_industry(self):
        """Test solution generation fails gracefully without industry."""
        solution = self.agent.generate_solution(self.context)
        assert "error" in solution.lower() or "cannot" in solution.lower()
    
    def test_generate_solution_with_industry(self):
        """Test comprehensive solution generation."""
        self.context.industry = "manufacturing"
        self.context.challenges = [
            "Predictive maintenance",
            "Quality control"
        ]
        self.context.budget_range = "$1-5M"
        self.context.timeline = "6-12 months"
        
        solution = self.agent.generate_solution(self.context)
        assert "Manufacturing" in solution or "manufacturing" in solution.lower()
        assert "GCP" in solution
        assert len(solution) > 100
    
    def test_conversation_context_initialization(self):
        """Test conversation context initializes with defaults."""
        ctx = ConversationContext()
        assert ctx.industry is None
        assert ctx.challenges == []
        assert ctx.current_systems == []
        assert ctx.conversation_history == []
    
    def test_conversation_context_with_data(self):
        """Test conversation context stores data correctly."""
        ctx = ConversationContext(
            industry="healthcare",
            challenges=["Patient data privacy", "Interoperability"],
            budget_range="$5-10M",
            timeline="12-18 months"
        )
        
        assert ctx.industry == "healthcare"
        assert len(ctx.challenges) == 2
        assert ctx.budget_range == "$5-10M"
        assert ctx.timeline == "12-18 months"


class TestE2EScenarios:
    """End-to-end scenario testing."""
    
    def test_financial_services_discovery(self):
        """Test complete financial services discovery scenario."""
        agent = VertexAIDiscoveryAgent()
        context = ConversationContext(
            industry="financial_services",
            challenges=[
                "Real-time fraud detection",
                "Regulatory compliance",
                "Legacy system modernization"
            ],
            budget_range="$1-5M",
            timeline="6-12 months"
        )
        
        solution = agent.generate_solution(context)
        assert "financial" in solution.lower() or "banking" in solution.lower()
        assert "BigQuery" in solution or "Vertex AI" in solution
        assert "Fraud" in solution or "fraud" in solution
    
    def test_retail_discovery(self):
        """Test complete retail discovery scenario."""
        agent = VertexAIDiscoveryAgent()
        context = ConversationContext(
            industry="retail",
            challenges=[
                "Inventory management",
                "Customer personalization",
                "Demand forecasting"
            ],
            budget_range="$2-10M",
            timeline="9-15 months"
        )
        
        solution = agent.generate_solution(context)
        assert "Retail" in solution or "retail" in solution.lower()
        assert "GCP" in solution or "Services" in solution
    
    def test_healthcare_discovery(self):
        """Test complete healthcare discovery scenario."""
        agent = VertexAIDiscoveryAgent()
        context = ConversationContext(
            industry="healthcare",
            challenges=[
                "Patient data security",
                "AI-powered diagnostics",
                "Genomic research"
            ],
            budget_range="$3-8M",
            timeline="12-18 months"
        )
        
        solution = agent.generate_solution(context)
        assert "healthcare" in solution.lower() or "health" in solution.lower()
        assert "Cloud Healthcare API" in solution or "API" in solution


class TestRobustness:
    """Test agent robustness and error handling."""
    
    def test_invalid_industry_handling(self):
        """Test handling of invalid industry input."""
        agent = VertexAIDiscoveryAgent()
        context = ConversationContext(industry="nonexistent_industry")
        
        analysis = agent.analyze_requirements(context)
        assert "error" in analysis
    
    def test_empty_challenges_list(self):
        """Test handling of empty challenges."""
        agent = VertexAIDiscoveryAgent()
        context = ConversationContext(
            industry="financial_services",
            challenges=[]
        )
        
        solution = agent.generate_solution(context)
        # Should still generate solution even with empty challenges
        assert len(solution) > 0
    
    def test_special_characters_in_input(self):
        """Test handling special characters in industry name."""
        agent = VertexAIDiscoveryAgent()
        
        # Should normalize and handle gracefully
        info = get_industry_info("Media & Entertainment")
        # May or may not find it depending on normalization
        # but should not crash
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
