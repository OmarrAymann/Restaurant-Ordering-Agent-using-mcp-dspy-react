import asyncio
import os
from typing import List, Optional, Literal
from pathlib import Path

import dspy
import dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field


# ============================================================================
# Configuration & Setup
# ============================================================================

dotenv.load_dotenv()

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Language Model Configuration
language_model = dspy.LM(
    model="gemini/gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    temperature=0.7  # Balanced between creativity and consistency
)
dspy.configure(lm=language_model)

# MCP Server Configuration
mcp_server_parameters = StdioServerParameters(
    command="python",
    args=["restaurant_mcp_server_enhanced.py"],
    env=None,
)


# ============================================================================
# Data Models
# ============================================================================

class CustomerOrderDetails(BaseModel):
    """
    Comprehensive structure containing all customer order information.
    This model ensures type safety and validation for order data.
    """
    
    ordered_items: List[str] = Field(
        default_factory=list,
        description="List of menu item IDs or names the customer wishes to order (e.g., ['main_001', 'drink_002'])"
    )
    
    customization_requests: List[str] = Field(
        default_factory=list,
        description="Special modifications or dietary requirements (e.g., 'no pickles', 'extra sauce', 'gluten-free')"
    )
    
    customer_full_name: Optional[str] = Field(
        default=None,
        description="Full name of the customer for order identification"
    )
    
    service_location: Optional[str] = Field(
        default=None,
        description="Table number, room number, or delivery address (e.g., 'Table 12', 'Room 305')"
    )
    
    contact_number: Optional[str] = Field(
        default=None,
        description="Customer's phone number for order updates and delivery coordination"
    )
    
    email_address: Optional[str] = Field(
        default=None,
        description="Customer's email for order confirmation and receipts"
    )


class ConversationState(BaseModel):
    """
    Represents the current state of the conversation flow.
    Helps track where the customer is in the ordering process.
    """
    
    current_phase: Literal[
        'INITIAL_GREETING',
        'BROWSING_MENU', 
        'TAKING_ORDER',
        'MODIFYING_ORDER',
        'COLLECTING_CUSTOMER_INFO',
        'ORDER_CONFIRMATION',
        'ORDER_CANCELLATION',
        'ORDER_FINALIZED',
        'PROVIDING_ASSISTANCE'
    ] = Field(
        description="Current phase of the customer interaction"
    )
    
    requires_user_confirmation: bool = Field(
        default=False,
        description="Flag indicating if agent is waiting for customer confirmation"
    )
    
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of required information still needed (e.g., ['name', 'table_number'])"
    )


class AgentResponseOutput(BaseModel):
    """
    Complete output structure for a single conversational turn.
    Includes response text, state management, order data, and tool execution info.
    """
    
    agent_message: str = Field(
        description="Natural, friendly response to be displayed to the customer"
    )
    
    conversation_state: str = Field(
        description="Current state after processing this turn"
    )
    
    order_details: CustomerOrderDetails = Field(
        description="Updated order information with all current items and preferences"
    )
    
    tools_to_execute: List[str] = Field(
        default_factory=list,
        description="List of MCP tool functions to invoke (e.g., ['fetch_menu', 'create_order'])"
    )
    
    needs_confirmation: bool = Field(
        default=False,
        description="Whether the agent needs explicit customer confirmation before proceeding"
    )
    
    order_summary: Optional[str] = Field(
        default=None,
        description="Formatted summary of the current order for confirmation"
    )


# ============================================================================
# DSPy Signature
# ============================================================================

class RestaurantConversationalAgent(dspy.Signature):
    """
    Intelligent restaurant service agent that handles the complete ordering workflow.
    
    Responsibilities:
    - Greet customers warmly and guide them through the menu
    - Understand natural language queries about menu items
    - Accurately capture orders with all customizations
    - Collect necessary customer information (name, location, contact)
    - Confirm orders by repeating back details
    - Handle modifications and cancellations gracefully
    - Coordinate with kitchen through MCP tools
    
    Behavior Guidelines:
    - Always be polite, warm, and professional
    - Use the customer's name once you know it
    - Repeat order details before final confirmation
    - Proactively ask for missing required information
    - Suggest popular items when appropriate
    - Handle errors and unclear requests gracefully
    """

    user_input_message: str = dspy.InputField(
        desc="The customer's latest message in natural language"
    )
    
    conversation_history: str = dspy.InputField(
        desc="Complete chat history for context and continuity (formatted as 'Speaker: message' pairs)"
    )
    
    agent_response: AgentResponseOutput = dspy.OutputField(
        desc="Structured output containing response text, updated state, order data, and actions to take"
    )


# ============================================================================
# Main Application Logic
# ============================================================================

class RestaurantChatbotSession:
    """
    Manages a complete chatbot session including conversation history,
    state management, and tool coordination.
    """
    
    def __init__(self, agent_instance, max_history_turns: int = 15):
        self.agent = agent_instance
        self.conversation_log: List[str] = []
        self.max_history_turns = max_history_turns
        self.current_order: Optional[CustomerOrderDetails] = None
        
    def add_to_history(self, speaker: str, message: str):
        """Add a message to conversation history with speaker label."""
        self.conversation_log.append(f"{speaker}: {message}")
        
    def get_recent_history(self) -> str:
        """Get the most recent conversation turns for context."""
        recent_turns = self.conversation_log[-self.max_history_turns:]
        return "\n".join(recent_turns)
    
    async def process_user_message(self, user_message: str) -> AgentResponseOutput:
        """
        Process a user message and generate an appropriate response.
        
        Args:
            user_message: The customer's input text
            
        Returns:
            AgentResponseOutput with response and metadata
        """
        self.add_to_history("Customer", user_message)
        
        result = await self.agent.acall(
            user_input_message=user_message,
            conversation_history=self.get_recent_history()
        )
        
        response_output = result.agent_response
        self.add_to_history("Agent", response_output.agent_message)
        
        # Update current order state
        self.current_order = response_output.order_details
        
        return response_output


async def initialize_and_run_chatbot():
    """
    Main entry point for the restaurant chatbot.
    Initializes MCP connection, sets up the agent, and runs the conversation loop.
    """
    
    async with stdio_client(mcp_server_parameters) as (input_stream, output_stream):
        async with ClientSession(input_stream, output_stream) as mcp_session:
            # Initialize MCP session
            await mcp_session.initialize()

            # Retrieve available MCP tools
            available_tools = await mcp_session.list_tools()
            dspy_compatible_tools = [
                dspy.Tool.from_mcp_tool(mcp_session, tool) 
                for tool in available_tools.tools
            ]

            if not dspy_compatible_tools:
                print("⚠️  Warning: No MCP tools detected. Some features may be unavailable.")
            else:
                print(f"✓ Loaded {len(dspy_compatible_tools)} MCP tools")

            # Display welcome banner
            print("\n" + "=" * 60)
            print("🍽️  RESTAURANT ORDER ASSISTANT")
            print("=" * 60)
            print("Welcome! I'm here to help you place your order.")
            print("Type 'quit', 'exit', or 'bye' to end the conversation.")
            print("=" * 60 + "\n")

            # Initialize agent with ReAct reasoning
            conversational_agent = dspy.ReAct(
                RestaurantConversationalAgent, 
                tools=dspy_compatible_tools
            )
            
            # Create session manager
            chat_session = RestaurantChatbotSession(conversational_agent)

            # Main conversation loop
            while True:
                try:
                    # Get user input
                    customer_input = input("You: ").strip()

                    # Check for exit commands
                    if customer_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                        print("\n🙏 Thank you for visiting! Have a wonderful day!\n")
                        break

                    # Skip empty inputs
                    if not customer_input:
                        continue

                    # Process the message
                    response_data = await chat_session.process_user_message(customer_input)
                    
                    # Display agent response
                    print(f"\n🤖 Agent: {response_data.agent_message}\n")
                    
                    # Show order summary if available (useful for debugging/confirmation)
                    if response_data.order_summary:
                        print(f"📋 Order Summary:\n{response_data.order_summary}\n")

                except KeyboardInterrupt:
                    print("\n\n👋 Session interrupted. Goodbye!\n")
                    break
                    
                except Exception as error:
                    print(f"\n❌ Error occurred: {error}")
                    print("Please try rephrasing your request.\n")


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    print("🚀 Starting Restaurant Order Assistant...")
    asyncio.run(initialize_and_run_chatbot())