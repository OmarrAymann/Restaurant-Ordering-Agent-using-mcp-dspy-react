import asyncio
import os
from typing import List, Optional, Literal

import dspy
import dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

dotenv.load_dotenv()

# Language Model Configuration - Ollama Llama 3.2
language_model = dspy.LM(
    model="ollama/llama3.2:latest",
    api_base="http://localhost:11434",
    temperature=0.7
)
dspy.configure(lm=language_model)

# MCP Server Configuration
mcp_server_parameters = StdioServerParameters(
    command="python",
    args=["restaurant_mcp_server_enhanced.py"],
    env=None,
)


class CustomerOrderDetails(BaseModel):
    """Comprehensive structure containing all customer order information."""
    
    ordered_items: List[str] = Field(
        default_factory=list,
        description="List of menu item IDs or names the customer wishes to order"
    )
    
    customization_requests: List[str] = Field(
        default_factory=list,
        description="Special modifications or dietary requirements"
    )
    
    customer_full_name: Optional[str] = Field(
        default=None,
        description="Full name of the customer for order identification"
    )
    
    service_location: Optional[str] = Field(
        default=None,
        description="Table number, room number, or delivery address"
    )
    
    contact_number: Optional[str] = Field(
        default=None,
        description="Customer's phone number for order updates"
    )
    
    email_address: Optional[str] = Field(
        default=None,
        description="Customer's email for order confirmation"
    )


class AgentResponseOutput(BaseModel):
    """Complete output structure for a single conversational turn."""
    
    agent_message: str = Field(
        description="Natural, friendly response to be displayed to the customer"
    )
    
    conversation_state: str = Field(
        description="Current state after processing this turn"
    )
    
    order_details: CustomerOrderDetails = Field(
        description="Updated order information with all current items"
    )
    
    tools_to_execute: List[str] = Field(
        default_factory=list,
        description="List of MCP tool functions to invoke"
    )
    
    needs_confirmation: bool = Field(
        default=False,
        description="Whether the agent needs explicit customer confirmation"
    )
    
    order_summary: Optional[str] = Field(
        default=None,
        description="Formatted summary of the current order"
    )


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
        desc="Complete chat history for context and continuity"
    )
    
    agent_response: AgentResponseOutput = dspy.OutputField(
        desc="Structured output containing response text, updated state, and order data"
    )


class RestaurantChatbotSession:
    """Manages a complete chatbot session including conversation history and state."""
    
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
        """Process a user message and generate an appropriate response."""
        self.add_to_history("Customer", user_message)
        
        result = await self.agent.acall(
            user_input_message=user_message,
            conversation_history=self.get_recent_history()
        )
        
        response_output = result.agent_response
        self.add_to_history("Agent", response_output.agent_message)
        
        self.current_order = response_output.order_details
        
        return response_output


async def initialize_and_run_chatbot():
    """Main entry point for the restaurant chatbot."""
    
    async with stdio_client(mcp_server_parameters) as (input_stream, output_stream):
        async with ClientSession(input_stream, output_stream) as mcp_session:
            await mcp_session.initialize()

            available_tools = await mcp_session.list_tools()
            dspy_compatible_tools = [
                dspy.Tool.from_mcp_tool(mcp_session, tool) 
                for tool in available_tools.tools
            ]

            if not dspy_compatible_tools:
                print("⚠️  Warning: No MCP tools detected.")
            else:
                print(f"✓ Loaded {len(dspy_compatible_tools)} MCP tools")

            print("\n" + "=" * 60)
            print("🍽️  RESTAURANT ORDER ASSISTANT")
            print("=" * 60)
            print("Welcome! I'm here to help you place your order.")
            print("Type 'quit', 'exit', or 'bye' to end the conversation.")
            print("=" * 60 + "\n")

            conversational_agent = dspy.ReAct(
                RestaurantConversationalAgent, 
                tools=dspy_compatible_tools
            )
            
            chat_session = RestaurantChatbotSession(conversational_agent)

            while True:
                try:
                    customer_input = input("You: ").strip()

                    if customer_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                        print("\n🙏 Thank you for visiting! Have a wonderful day!\n")
                        break

                    if not customer_input:
                        continue

                    response_data = await chat_session.process_user_message(customer_input)
                    
                    print(f"\n🤖 Agent: {response_data.agent_message}\n")
                    
                    if response_data.order_summary:
                        print(f"📋 Order Summary:\n{response_data.order_summary}\n")

                except KeyboardInterrupt:
                    print("\n\n👋 Session interrupted. Goodbye!\n")
                    break
                    
                except Exception as error:
                    print(f"\n❌ Error occurred: {error}")
                    print("Please try rephrasing your request.\n")


if __name__ == "__main__":
    print("🚀 Starting Restaurant Order Assistant...")
    asyncio.run(initialize_and_run_chatbot())