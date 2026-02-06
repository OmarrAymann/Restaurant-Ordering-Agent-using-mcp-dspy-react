import asyncio
import os
import sys
from typing import List, Optional

import dspy
import dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

dotenv.load_dotenv()

language_model = dspy.LM(
    model="ollama/llama3.2:latest",
    api_base="http://localhost:11434",
    temperature=0.7
)
dspy.configure(lm=language_model)

mcp_server_parameters = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server_res.py"]
)

RESTAURANT_MENU = {
    "APP_001": {"name": "Falafel", "category": "appetizer", "description": "Crispy chickpea balls with tahini", "price": 9.99},
    "APP_002": {"name": "Koshari Balls", "category": "appetizer", "description": "Mini koshari bites with rice, lentils, pasta, and tomato sauce", "price": 13.99},
    "MAIN_001": {"name": "Grilled Kofta", "category": "main", "description": "Seasoned beef and lamb skewers with rice and vegetables", "price": 26.99},
    "MAIN_002": {"name": "Molokhia with Rabbit", "category": "main", "description": "Traditional molokhia stew with rice", "price": 19.99},
    "MAIN_003": {"name": "Grilled Hamam (Pigeon)", "category": "main", "description": "Stuffed pigeon grilled with Egyptian spices", "price": 34.99},
    "DESS_001": {"name": "Basbousa", "category": "dessert", "description": "Sweet semolina cake with almonds and syrup", "price": 9.99},
    "DRINK_001": {"name": "Karkadeh", "category": "drink", "description": "Refreshing hibiscus tea served hot or cold", "price": 4.99},
}


class CustomerOrderDetails(BaseModel):
    ordered_items: List[str] = Field(default_factory=list)
    customization_requests: List[str] = Field(default_factory=list)
    customer_full_name: Optional[str] = None
    service_location: Optional[str] = None
    contact_number: Optional[str] = None
    email_address: Optional[str] = None


class AgentResponseOutput(BaseModel):
    agent_message: str
    conversation_state: str
    order_details: CustomerOrderDetails
    tools_to_execute: List[str] = Field(default_factory=list)
    needs_confirmation: bool = False
    order_summary: Optional[str] = None


class RestaurantConversationalAgent(dspy.Signature):
    user_input_message: str = dspy.InputField(desc="Customer's message")
    conversation_history: str = dspy.InputField(desc="Chat history")
    agent_response: AgentResponseOutput = dspy.OutputField(desc="Agent's structured response")


class RestaurantChatbotSession:
    def __init__(self, agent_instance, max_history_turns: int = 15):
        self.agent = agent_instance
        self.conversation_log: List[str] = []
        self.max_history_turns = max_history_turns
        self.current_order: Optional[CustomerOrderDetails] = None

    def add_to_history(self, speaker: str, message: str):
        self.conversation_log.append(f"{speaker}: {message}")

    def get_recent_history(self) -> str:
        return "\n".join(self.conversation_log[-self.max_history_turns:])

    async def process_user_message(self, user_message: str) -> AgentResponseOutput:
        self.add_to_history("Customer", user_message)
        result = await self.agent.acall(
            user_input_message=user_message,
            conversation_history=self.get_recent_history()
        )
        response_output = result.agent_response
        self.add_to_history("fat7y", response_output.agent_message)
        self.current_order = response_output.order_details
        return response_output


async def initialize_and_run_chatbot():
    async with stdio_client(mcp_server_parameters) as (input_stream, output_stream):
        async with ClientSession(input_stream, output_stream) as mcp_session:
            await mcp_session.initialize()
            available_tools = await mcp_session.list_tools()
            dspy_compatible_tools = [dspy.Tool.from_mcp_tool(mcp_session, tool) for tool in available_tools.tools]

            print("\n" + "=" * 60)
            print(" RESTAURANT ORDER ASSISTANT")
            print("=" * 60)
            print("Hello! I will guide you through our menu and help place your order.")
            print("You can type 'menu' to see the Egyptian dishes.")
            print("Type 'quit', 'exit', or 'bye' to end the session.\n")

            conversational_agent = dspy.ReAct(RestaurantConversationalAgent, tools=dspy_compatible_tools)
            chat_session = RestaurantChatbotSession(conversational_agent)

            while True:
                customer_input = input("You: ").strip()
                if customer_input.lower() in ['quit', 'exit', 'bye']:
                    print("\nThank you for visiting! Enjoy your meal!\n")
                    break
                if not customer_input:
                    continue
                if "menu" in customer_input.lower() :
                    print("\n Menu:")
                    for item in RESTAURANT_MENU.values():
                        print(f"- {item['name']} ({item['category']}): {item['description']} - ${item['price']}")
                    print()
                    continue

                response_data = await chat_session.process_user_message(customer_input)
                print(f"\n🤖 fat7y: {response_data.agent_message}\n")
                if response_data.order_summary:
                    print(f"📋 Order Summary:\n{response_data.order_summary}\n")


if __name__ == "__main__":
    print(" Starting Restaurant Order Assistant...")
    asyncio.run(initialize_and_run_chatbot())
