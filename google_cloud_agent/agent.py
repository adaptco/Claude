"""
Google Cloud Industry Discovery Agent

Uses Vertex AI with LangChain to conduct intelligent interviews about
industry-specific cloud solutions and provide tailored GCP recommendations.
"""

import os
from typing import Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

from industry_data import (
    get_industry_info,
    list_industries,
    get_gcp_products_for_industry,
    get_solutions_by_challenge
)


@dataclass
class ConversationContext:
    """Maintains conversation state during agent interaction."""
    industry: Optional[str] = None
    challenges: list = None
    budget_range: Optional[str] = None
    current_systems: list = None
    timeline: Optional[str] = None
    conversation_history: list = None
    
    def __post_init__(self):
        if self.challenges is None:
            self.challenges = []
        if self.current_systems is None:
            self.current_systems = []
        if self.conversation_history is None:
            self.conversation_history = []


class DiscoveryAgent(ABC):
    """Abstract base for Industry Discovery Agent implementations."""
    
    @abstractmethod
    def interview_user(self, context: ConversationContext) -> str:
        """Conduct user interview and gather requirements."""
        pass
    
    @abstractmethod
    def analyze_requirements(self, context: ConversationContext) -> dict:
        """Analyze gathered requirements and generate recommendations."""
        pass
    
    @abstractmethod
    def generate_solution(self, context: ConversationContext) -> str:
        """Generate tailored GCP solution recommendations."""
        pass


class VertexAIDiscoveryAgent(DiscoveryAgent):
    """
    Industry Discovery Agent using Vertex AI with LangChain.
    
    This agent:
    1. Interviews the user about their industry and challenges
    2. Gathers information about current systems and budget
    3. Recommends relevant GCP services and solutions
    4. Provides implementation guidance
    """
    
    SYSTEM_PROMPT = """You are a Google Cloud Industry Solutions Expert with deep knowledge 
of how enterprises across different industries use Google Cloud Platform to solve their 
business challenges.

Your role is to:
1. Understand the user's industry and specific challenges
2. Ask clarifying questions about their current infrastructure and budget
3. Recommend relevant GCP services and solutions
4. Provide business value and ROI insights
5. Create an implementation roadmap

Be conversational but professional. Ask one or two questions at a time. 
Focus on understanding business problems, not just technical requirements.
Reference specific GCP services and industry best practices.

When the user provides their industry, acknowledge it and ask about their top 3 challenges.
When they mention challenges, map them to relevant GCP solutions.
Always provide specific service recommendations with use cases.
"""
    
    def __init__(self):
        """Initialize the agent."""
        self.conversation_turns = 0
        self.max_turns = 10
        
    def interview_user(self, context: ConversationContext) -> str:
        """
        Conduct structured interview to gather requirements.
        
        Returns:
            Initial greeting and first question for the user
        """
        greeting = """Welcome to the Google Cloud Industry Discovery Agent!

I'm here to help you understand how Google Cloud Platform can solve your 
industry-specific challenges and drive business value.

To get started, could you tell me:
1. What industry are you in?
2. What are your top 3 business challenges?

Available industries: Financial Services, Retail, Healthcare, Manufacturing, 
Media & Entertainment, Energy & Utilities, Telecommunications, Government, Education

Feel free to describe them in your own words!"""
        
        return greeting
    
    def analyze_requirements(self, context: ConversationContext) -> dict:
        """
        Analyze gathered requirements against industry knowledge base.
        
        Returns:
            Dictionary with analysis including matched solutions and recommendations
        """
        if not context.industry:
            return {"error": "Industry not yet identified"}
        
        industry_info = get_industry_info(context.industry)
        if not industry_info:
            return {"error": f"Industry '{context.industry}' not found in knowledge base"}
        
        analysis = {
            "industry": context.industry,
            "industry_description": industry_info.get("description"),
            "key_challenges_in_industry": industry_info.get("key_challenges"),
            "user_challenges": context.challenges,
            "matched_solutions": []
        }
        
        # Map user challenges to industry solutions
        solutions = get_solutions_by_challenge(context.industry)
        if context.challenges:
            for challenge in context.challenges:
                for solution_name, solution_data in solutions.items():
                    if any(keyword in challenge.lower() 
                           for keyword in solution_data.get("description", "").lower().split()):
                        analysis["matched_solutions"].append({
                            "solution": solution_name,
                            "description": solution_data.get("description"),
                            "gcp_services": solution_data.get("services"),
                            "use_case": solution_data.get("use_case")
                        })
        
        # Get recommended products
        analysis["recommended_gcp_products"] = get_gcp_products_for_industry(context.industry)
        
        return analysis
    
    def generate_solution(self, context: ConversationContext) -> str:
        """
        Generate comprehensive GCP solution recommendations.
        
        Returns:
            Formatted solution recommendation report
        """
        analysis = self.analyze_requirements(context)
        
        if "error" in analysis:
            return f"Cannot generate solution: {analysis['error']}"
        
        report = f"""
{'='*80}
GCP SOLUTION RECOMMENDATION REPORT
{'='*80}

INDUSTRY PROFILE
{'-'*20}
Industry: {analysis.get('industry', 'Not specified').title()}
Description: {analysis.get('industry_description', 'N/A')}

YOUR CHALLENGES
{'-'*20}
"""
        for i, challenge in enumerate(analysis.get("user_challenges", []), 1):
            report += f"{i}. {challenge}\n"
        
        report += f"""
RECOMMENDED GCP SERVICES
{'-'*28}
"""
        for product in analysis.get("recommended_gcp_products", []):
            report += f"• {product}\n"
        
        report += f"""
MATCHED SOLUTIONS
{'-'*17}
"""
        for solution in analysis.get("matched_solutions", []):
            report += f"""
Solution: {solution['solution'].replace('_', ' ').title()}
Description: {solution['description']}
GCP Services: {', '.join(solution['gcp_services'])}
Use Case: {solution['use_case']}
"""
        
        if context.budget_range:
            report += f"""
BUDGET CONSIDERATION
{'-'*22}
Your Budget Range: {context.budget_range}

This affects recommended deployment model and scaling strategy.
"""
        
        if context.timeline:
            report += f"""
IMPLEMENTATION TIMELINE
{'-'*26}
Expected Timeline: {context.timeline}

Phased approach recommended based on complexity and dependencies.
"""
        
        report += f"""
NEXT STEPS
{'-'*10}
1. Detailed technical assessment
2. Proof of concept (PoC) planning
3. Migration strategy development
4. Cost analysis and ROI calculation
5. Organizational change management

For more information, visit: https://cloud.google.com/solutions

{'='*80}
"""
        
        return report


class SimulatedDiscoverySession:
    """
    Simulated discovery session for testing the agent locally
    without Vertex AI credentials.
    """
    
    def __init__(self):
        self.agent = VertexAIDiscoveryAgent()
        self.context = ConversationContext()
    
    def run_demo_session(self):
        """Run a simulated discovery session."""
        print("=" * 80)
        print("GOOGLE CLOUD INDUSTRY DISCOVERY AGENT - DEMO SESSION")
        print("=" * 80)
        print()
        
        # Display greeting
        greeting = self.agent.interview_user(self.context)
        print(greeting)
        print()
        
        # Simulate user responses
        print("-" * 80)
        print("USER RESPONSE (Simulated):")
        print("-" * 80)
        
        user_response = """I'm in Financial Services. Our main challenges are:
1. Real-time fraud detection
2. Compliance and audit requirements
3. Modernizing legacy systems"""
        
        print(user_response)
        print()
        
        # Update context with simulated user input
        self.context.industry = "financial_services"
        self.context.challenges = [
            "Real-time fraud detection",
            "Compliance and audit requirements",
            "Modernizing legacy systems"
        ]
        self.context.budget_range = "$1-5M"
        self.context.timeline = "6-12 months"
        
        # Generate solution
        print("-" * 80)
        print("AGENT RESPONSE:")
        print("-" * 80)
        
        solution = self.agent.generate_solution(self.context)
        print(solution)
        
        # Show analysis details
        print("-" * 80)
        print("DETAILED ANALYSIS:")
        print("-" * 80)
        
        analysis = self.agent.analyze_requirements(self.context)
        print(f"\nMatched Solutions: {len(analysis.get('matched_solutions', []))}")
        print(f"Recommended GCP Products: {len(analysis.get('recommended_gcp_products', []))}")
        print()
        
        # Conversation history
        self.context.conversation_history.append({
            "user": user_response,
            "agent": solution,
            "turn": 1
        })
        
        print(f"Conversation turns: {len(self.context.conversation_history)}")
        print()


def main():
    """Run the discovery agent demo."""
    session = SimulatedDiscoverySession()
    session.run_demo_session()


if __name__ == "__main__":
    main()
