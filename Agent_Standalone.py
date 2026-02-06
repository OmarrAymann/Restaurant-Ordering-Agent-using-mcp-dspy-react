from typing import List, Optional, Dict, Any
import dspy
import dotenv
from pydantic import BaseModel, Field

dotenv.load_dotenv()


language_model = dspy.LM(
    model="ollama/llama3.2:latest",
    api_base="http://localhost:11434",
    temperature=0.7
)
dspy.configure(lm=language_model)


# ============================================================================
# Menu Database
# ============================================================================

RESTAURANT_MENU = {
    "APP_001": {
        "name": "Falafel",
        "category": "appetizer",
        "description": "Crispy chickpea balls served with tahini sauce and pickles",
        "price": 10,
        "ingredients": ["chickpeas", "onion", "garlic", "parsley", "tahini"],
        "dietary": ["vegetarian", "vegan"],
        "prep_time": 12
    },
    "APP_002": {
        "name": "fatosh Salad",
        "category": "appetizer",
        "description": "Fresh mixed greens with tomatoes, cucumbers, radishes, and crispy pita chips",
        "price": 68,
        "ingredients": ["mixed greens", "tomatoes", "cucumber", "radishes", "pita chips"],
        "dietary": ["vegetarian", "spicy"],
        "prep_time": 15
    },
    "MAIN_001": {
        "name": "Grilled Kofta",
        "category": "main",
        "description": "Seasoned minced beef and lamb skewers with rice and vegetables",
        "price": 170,
        "ingredients": ["beef", "lamb", "onion", "spices", "rice", "vegetables"],
        "dietary": [],
        "prep_time": 25
    },
    "MAIN_002": {
        "name": "Molokhia with Rabbit",
        "category": "main",
        "description": "Traditional molokhia stew served with tender rabbit and rice",
        "price": 150,
        "ingredients": ["molokhia leaves", "rabbit", "garlic", "coriander", "rice"],
        "dietary": [],
        "prep_time": 30
    },
    "MAIN_003": {
        "name": "Hamam Mahshi",
        "category": "main",
        "description": "Stuffed pigeon grilled to perfection with Egyptian spices",
        "price": 120,
        "ingredients": ["pigeon", "rice", "onion", "spices", "butter"],
        "dietary": [],
        "prep_time": 35
    },
    "DESS_001": {
        "name": "Basbousa",
        "category": "dessert",
        "description": "Sweet semolina cake topped with almonds and soaked in syrup",
        "price": 30,
        "ingredients": ["semolina", "sugar", "yogurt", "almonds", "syrup"],
        "dietary": ["vegetarian"],
        "prep_time": 20
    },
    "DRINK_001": {
        "name": "Karkadeh",
        "category": "drink",
        "description": "Refreshing hibiscus tea served hot or cold",
        "price": 10,
        "ingredients": ["hibiscus petals", "sugar", "water"],
        "dietary": ["vegan", "vegetarian"],
        "prep_time": 5
    },
}

ORDERS = {}
TAX_RATE = 0.14


# ============================================================================
# Tool Functions (Simulated without MCP)
# ============================================================================

def get_menu_display(category: str = "all") -> str:
    if category == "all":

        items = RESTAURANT_MENU.values()
    else:
        items = [item for item in RESTAURANT_MENU.values() if item["category"] == category]
    output = []
    for code, item in RESTAURANT_MENU.items():
        if category == "all" or item["category"] == category:
            output.append(f"{item['name']} (${item['price']:.2f}) - {item['description']}")
    
    return "\n".join(output) if output else "No items found"


def calculate_total(item_codes: List[str]) -> Dict[str, float]:
    subtotal = sum(RESTAURANT_MENU[code]["price"] for code in item_codes if code in RESTAURANT_MENU)
    tax = subtotal * TAX_RATE
    total = subtotal + tax
    return {"subtotal": subtotal, "tax": tax, "total": total}


# ============================================================================
# Data Models
# ============================================================================

class CustomerOrderDetails(BaseModel):
    """Customer order information."""
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


class RestaurantAgent(dspy.Signature):
    
    user_input_message: str = dspy.InputField(desc="Customer's message")
    conversation_history: str = dspy.InputField(desc="Chat history")
    menu_context: str = dspy.InputField(desc="Available menu items")
    
    response_text: str = dspy.OutputField(desc="Friendly response to the customer")


# ============================================================================
# Session Management
# ============================================================================

class ChatSession:
    """Manages conversation session."""
    
    def __init__(self):
        self.history: List[str] = []
        self.current_order = CustomerOrderDetails()
        self.agent = dspy.Predict(RestaurantAgent)
        
    def add_history(self, speaker: str, message: str):
        """Add to conversation history."""
        self.history.append(f"{speaker}: {message}")
        
    def get_history(self) -> str:
        """Get recent history."""
        return "\n".join(self.history[-10:])
    
    def process_message(self, user_input: str) -> str:
        """Process user message and return response."""
        self.add_history("Customer", user_input)
        
        # Get menu context
        menu_text = get_menu_display("all")
        
        try:
            # Call agent
            result = self.agent(
                user_input_message=user_input,
                conversation_history=self.get_history(),
                menu_context=menu_text
            )
            
            response_text = result.response_text
            self.add_history("Agent", response_text)
            
            # Parse order details from conversation
            user_lower = user_input.lower()
            
            # Check for menu items
            for code, item in RESTAURANT_MENU.items():
                if item["name"].lower() in user_lower:
                    if code not in self.current_order.ordered_items:
                        self.current_order.ordered_items.append(code)
            
            # Check for name
            if "name is" in user_lower or "i'm" in user_lower or "my name" in user_lower:
                words = user_input.split()
                for i, word in enumerate(words):
                    if word.lower() in ["is", "i'm", "im"] and i + 1 < len(words):
                        potential_name = " ".join(words[i+1:i+3])
                        if len(potential_name) > 2:
                            self.current_order.customer_full_name = potential_name.strip(",.")
                            break
            
            # Check for table/location
            if "table" in user_lower or "room" in user_lower:
                words = user_input.split()
                for i, word in enumerate(words):
                    if word.lower() in ["table", "room"] and i + 1 < len(words):
                        self.current_order.service_location = " ".join(words[i:i+2]).strip(",.")
                        break
            
            # Check for phone
            if any(char.isdigit() for char in user_input):
                import re
                phone_match = re.search(r'(\d{3}[-.\s]?\d{4}|\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', user_input)
                if phone_match:
                    self.current_order.contact_number = phone_match.group(0)
            
            # Show order summary if complete
            if self.current_order.ordered_items and all([
                self.current_order.customer_full_name,
                self.current_order.service_location,
                self.current_order.contact_number
            ]):
                pricing = calculate_total(self.current_order.ordered_items)
                items_list = [RESTAURANT_MENU[code]["name"] for code in self.current_order.ordered_items]
                
                summary = f"\n{'='*50}\n"
                summary += f"📋 ORDER SUMMARY\n"
                summary += f"{'='*50}\n"
                summary += f"Customer: {self.current_order.customer_full_name}\n"
                summary += f"Location: {self.current_order.service_location}\n"
                summary += f"Phone: {self.current_order.contact_number}\n"
                summary += f"\nItems:\n"
                for item in items_list:
                    summary += f"  • {item}\n"
                summary += f"\nSubtotal: ${pricing['subtotal']:.2f}\n"
                summary += f"Tax: ${pricing['tax']:.2f}\n"
                summary += f"Total: ${pricing['total']:.2f}\n"
                summary += f"{'='*50}\n"
                
                return response_text + "\n" + summary
            
            return response_text
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"I apologize, I encountered an error. Could you please try again?"


# ============================================================================
# Main Application
# ============================================================================

def main():

    print("RESTAURANT ORDER ASSISTANT :")
    print("\n Hello how can i help you today? \n")

    session = ChatSession()
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print("\n🙏 Thank you for visiting! Have a wonderful day!\n")
                break
            
            if not user_input:
                continue
            
            response = session.process_message(user_input)
            print(f"\n🤖 fat7y: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n Session interrupted. Goodbye!\n")
            break
            
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":

    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            print("checking ollama server")
    except:
        print("can not connect to ollama server")
    
    main()