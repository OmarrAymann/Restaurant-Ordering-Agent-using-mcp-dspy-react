# Restaurant Ordering Agent using MCP and DSpy

## System Overview

The Restaurant Ordering Agent is an AI-powered chatbot designed to guide customers through an Egyptian food menu, take orders, handle customizations, and coordinate with kitchen staff. The system integrates a local Llama 3.2 model for natural language understanding and MCP (Model Context Protocol) to handle backend tools and services.

### Key Features:
- Conversational ordering with natural language
- Egyptian menu items with categories, prices, and descriptions
- Real-time order summary and management
- Integration with kitchen workflow via MCP tools
- Automated email notifications for orders (optional)

## AI Agent

The AI agent uses DSpy and Ollama Llama 3.2 for natural language understanding and reasoning.

### Responsibilities:
- Interpret customer messages and queries
- Suggest menu items and guide the ordering flow
- Parse item quantities and dietary requirements
- Maintain conversation history and current order state
- Ask clarifying questions if needed

### Implementation:
- `RestaurantConversationalAgent` defines input (`user_input_message`) and output (`agent_response`) schemas
- `RestaurantChatbotSession` manages session history, orders, and agent interaction

## MCP Server

The MCP Server acts as a bridge between the AI agent and backend services (tools).

### Features:
- Exposes functions for sending emails, logging orders, or interacting with external services
- Handles `CallToolRequest` events from the agent
- Runs locally via `mcp_server_res.py`

### Configuration:
- Python executable (`sys.executable`) is used to launch MCP server
- `.env` file stores credentials and configuration variables:
SENDER_EMAIL=youremail@example.com
SENDER_PASSWORD=yourpassword
CHEF_EMAIL=chef@restaurant.com

text

## Architecture
+---------------------+
| Customer |
| (Chat Interface) |
+----------+----------+
|
v
+---------------------+
| AI Conversational |
| Agent (Llama 3.2) |
+----------+----------+
|
v
+---------------------+
| MCP Server |
| - Email Tool |
| - Logging Tool |
+----------+----------+
|
v
+---------------------+
| Kitchen / Database |
+---------------------+

text

**Flow:** User sends messages → AI agent interprets → MCP server executes tools → Kitchen/log updated.

## Sample Menu (Egyptian Cuisine)

| Item Code | Name                  | Category | Description                                      | Price   |
|-----------|-----------------------|----------|--------------------------------------------------|---------|
| APP_001   | Falafel               | Appetizer| Crispy chickpea balls with tahini                | $9.99   |
| APP_002   | Koshari Balls         | Appetizer| Mini koshari bites with rice, lentils, pasta, sauce | $13.99 |
| MAIN_001  | Grilled Kofta         | Main     | Beef & lamb skewers with rice & vegetables       | $26.99  |
| MAIN_002  | Molokhia with Rabbit  | Main     | Traditional molokhia stew with rice              | $19.99  |
| MAIN_003  | Grilled Hamam (Pigeon)| Main     | Stuffed pigeon grilled with Egyptian spices      | $34.99  |
| DESS_001  | Basbousa              | Dessert  | Sweet semolina cake with almonds & syrup         | $9.99   |
| DRINK_001 | Karkadeh              | Drink    | Refreshing hibiscus tea served hot or cold       | $4.99   |

## MCP Tools

The system uses MCP tools to automate backend actions:

- **Email Notification Tool:** Sends completed orders to the chef
- **Order Logging Tool:** Records orders in `restaurant_orders_log.xlsx`
- **Menu Query Tool:** Provides menu information on request
- **Custom Tool Integration:** Additional tools can be added to support payments, delivery, or analytics

## Project Structure
Restaurant-Ordering-Agent-using-mcp-dspy-react/
│
├── Agent.py # Main chatbot interface
├── mcp_server_res.py # MCP server backend
├── Requirements.txt # Python dependencies
├── .env # Environment variables (email credentials)
├── restaurant_menu.py # Menu definition and item models
├── test.py # Test scripts and examples
└── README.md # Project documentation

text

## Getting Started

### Install Dependencies

```bash
pip install -r Requirements.txt
Setup Environment Variables
Create a .env file with the required credentials:

bash
SENDER_EMAIL=youremail@example.com
SENDER_PASSWORD=yourpassword
CHEF_EMAIL=chef@restaurant.com
Start MCP Server
bash
python3 mcp_server_res.py
Run Chatbot
bash
python3 Agent.py
Interact with Chatbot
Type menu to view menu

Type orders naturally: "I want 2 Falafel and 1 Basbousa"

Type quit to exit
