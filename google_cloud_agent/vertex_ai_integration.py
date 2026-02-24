"""
Vertex AI Integration Module

Connects the Discovery Agent to Vertex AI using the Vertex AI SDK.
Requires Google Cloud credentials to be configured.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    from vertexai.preview.reasoning_engines import LangchainAgent
    import vertexai
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("Warning: Vertex AI SDK not installed. Install with: pip install google-cloud-aiplatform")

from langchain.agents import Tool, AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent import VertexAIDiscoveryAgent, ConversationContext
from industry_data import (
    get_industry_info,
    list_industries,
    get_gcp_products_for_industry,
    get_solutions_by_challenge
)


@dataclass
class VertexAIConfig:
    """Configuration for Vertex AI connection."""
    project_id: Optional[str] = None
    location: str = "us-central1"
    model_name: str = "gemini-1.5-pro"
    temperature: float = 0.7
    
    def __post_init__(self):
        if not self.project_id:
            self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")


class VertexAIIntegratedAgent(VertexAIDiscoveryAgent):
    """
    Discovery Agent integrated with Vertex AI's LangChain capabilities.
    """
    
    def __init__(self, config: Optional[VertexAIConfig] = None):
        """
        Initialize the Vertex AI integrated agent.
        
        Args:
            config: VertexAI configuration (uses environment if not provided)
        """
        super().__init__()
        
        if not VERTEX_AI_AVAILABLE:
            raise ImportError("Vertex AI SDK is required. Install with: pip install google-cloud-aiplatform")
        
        self.config = config or VertexAIConfig()
        self._initialize_vertex_ai()
        self._setup_tools()
        self._setup_agent()
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI with project credentials."""
        try:
            vertexai.init(
                project=self.config.project_id,
                location=self.config.location
            )
            print(f"✓ Vertex AI initialized: {self.config.project_id} ({self.config.location})")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Vertex AI: {e}")
    
    def _setup_tools(self):
        """Set up LangChain tools for the agent."""
        
        @tool
        def get_industry_data(industry_name: str) -> str:
            """
            Get comprehensive information about a specific industry.
            
            Args:
                industry_name: Name of the industry (e.g., 'Financial Services', 'Retail')
                
            Returns:
                Formatted industry information including challenges and solutions
            """
            info = get_industry_info(industry_name)
            if not info:
                return f"Industry '{industry_name}' not found. Available: {', '.join(list_industries())}"
            
            result = f"""
Industry: {industry_name}
Description: {info.get('description')}

Key Challenges:
"""
            for challenge in info.get('key_challenges', []):
                result += f"• {challenge}\n"
            
            result += "\nRecommended GCP Products:\n"
            for product in info.get('recommended_gcp_products', []):
                result += f"• {product}\n"
            
            return result
        
        @tool
        def get_gcp_solutions(industry_name: str) -> str:
            """
            Get GCP solutions mapped to industry challenges.
            
            Args:
                industry_name: Name of the industry
                
            Returns:
                Formatted list of solutions with services and use cases
            """
            solutions = get_solutions_by_challenge(industry_name)
            if not solutions:
                return f"No solutions found for '{industry_name}'"
            
            result = f"GCP Solutions for {industry_name}:\n\n"
            for solution_name, solution_data in solutions.items():
                result += f"""
Solution: {solution_name.replace('_', ' ').title()}
Description: {solution_data.get('description')}
GCP Services: {', '.join(solution_data.get('services', []))}
Use Case: {solution_data.get('use_case')}
"""
            return result
        
        @tool
        def list_available_industries() -> str:
            """
            List all industries available in the knowledge base.
            
            Returns:
                Comma-separated list of available industries
            """
            industries = list_industries()
            return "Available industries:\n" + "\n".join(f"• {ind}" for ind in industries)
        
        @tool
        def recommend_gcp_products(industry_name: str) -> str:
            """
            Get recommended GCP products for a specific industry.
            
            Args:
                industry_name: Name of the industry
                
            Returns:
                List of recommended GCP products
            """
            products = get_gcp_products_for_industry(industry_name)
            if not products:
                return f"No products recommended for '{industry_name}'"
            
            return f"""
Recommended GCP Products for {industry_name}:
{chr(10).join(f'• {p}' for p in products)}
"""
        
        self.tools = [
            Tool(
                name="get_industry_data",
                func=get_industry_data.func,
                description=get_industry_data.description
            ),
            Tool(
                name="get_gcp_solutions",
                func=get_gcp_solutions.func,
                description=get_gcp_solutions.description
            ),
            Tool(
                name="list_available_industries",
                func=list_available_industries.func,
                description=list_available_industries.description
            ),
            Tool(
                name="recommend_gcp_products",
                func=recommend_gcp_products.func,
                description=recommend_gcp_products.description
            )
        ]
    
    def _setup_agent(self):
        """Set up the LangChain agent with Vertex AI model."""
        
        # Initialize the LLM
        self.llm = ChatVertexAI(
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            max_output_tokens=2048
        )
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create the tool-calling agent
        self.agent = create_tool_calling_agent(
            self.llm,
            self.tools,
            self.prompt
        )
        
        # Create the executor
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10
        )
    
    def chat(self, user_message: str, context: Optional[ConversationContext] = None) -> str:
        """
        Chat with the agent using Vertex AI.
        
        Args:
            user_message: User's message or question
            context: Optional conversation context
            
        Returns:
            Agent's response
        """
        try:
            response = self.executor.invoke({"input": user_message})
            return response.get("output", "No response generated")
        except Exception as e:
            return f"Error: {str(e)}"
    
    def start_interactive_session(self):
        """Start an interactive chat session with the agent."""
        print("\n" + "=" * 80)
        print("GOOGLE CLOUD INDUSTRY DISCOVERY AGENT - INTERACTIVE SESSION")
        print("=" * 80)
        print("\nType 'exit' to quit, 'help' for available commands\n")
        
        context = ConversationContext()
        
        # Display initial greeting
        greeting = self.interview_user(context)
        print("Agent:", greeting)
        print()
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() == 'exit':
                print("\nThank you for using the Google Cloud Industry Discovery Agent!")
                break
            
            if user_input.lower() == 'help':
                print("""
Available commands:
- Type your question or response naturally
- Examples:
  • "I'm in financial services"
  • "What are the best GCP services for retail?"
  • "Show me solutions for healthcare"
  • "exit" - Exit the session
""")
                continue
            
            if not user_input:
                continue
            
            # Get agent response
            response = self.chat(user_input, context)
            print(f"\nAgent: {response}\n")


def create_agent_from_env() -> VertexAIIntegratedAgent:
    """
    Create a Vertex AI integrated agent using environment variables.
    
    Environment variables:
    - GOOGLE_CLOUD_PROJECT: Google Cloud project ID
    - VERTEX_AI_LOCATION: Vertex AI location (default: us-central1)
    - VERTEX_AI_MODEL: Model name (default: gemini-1.5-pro)
    - VERTEX_AI_TEMPERATURE: Model temperature (default: 0.7)
    
    Returns:
        VertexAIIntegratedAgent instance
    """
    config = VertexAIConfig(
        project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
        model_name=os.environ.get("VERTEX_AI_MODEL", "gemini-1.5-pro"),
        temperature=float(os.environ.get("VERTEX_AI_TEMPERATURE", "0.7"))
    )
    
    return VertexAIIntegratedAgent(config)


if __name__ == "__main__":
    print("Vertex AI Integration Module")
    print("This module requires Vertex AI SDK and Google Cloud credentials")
    print("\nTo use this module:")
    print("1. Install: pip install google-cloud-aiplatform")
    print("2. Set GOOGLE_CLOUD_PROJECT environment variable")
    print("3. Authenticate: gcloud auth application-default login")
