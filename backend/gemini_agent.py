from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import uuid
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow both Vite ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google Genai client
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Store chat sessions in memory (in production, use Redis or a database)
chat_sessions: Dict[str, Dict[str, Any]] = {}

# Request/Response models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

class StructuredChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_structured_output: bool = True

class ActionPoint(BaseModel):
    task: str
    priority: str  # low, medium, high
    due: Optional[str] = None  # ISO 8601 date-time format
    context: Optional[str] = None

class ConsiderPoint(BaseModel):
    note: str
    category: str
    related_to_action: Optional[str] = None

class StructuredResponse(BaseModel):
    action_points: List[ActionPoint]
    consider_points: List[ConsiderPoint]

class StructuredChatResponse(BaseModel):
    structured_data: StructuredResponse
    session_id: str

# Define the structured output schema
STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string"
                    },
                    "priority": {
                        "type": "string",
                        "enum": [
                            "low",
                            "medium",
                            "high"
                        ]
                    },
                    "due": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "context": {
                        "type": "string"
                    }
                },
                "required": [
                    "task",
                    "priority"
                ]
            }
        },
        "consider_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string"
                    },
                    "category": {
                        "type": "string"
                    },
                    "related_to_action": {
                        "type": "string"
                    }
                },
                "required": [
                    "note",
                    "category"
                ]
            }
        }
    },
    "required": [
        "action_points",
        "consider_points"
    ]
}

def clean_old_sessions():
    """Remove sessions older than 1 hour"""
    current_time = datetime.now()
    sessions_to_remove = []
    
    for session_id, session_data in chat_sessions.items():
        if current_time - session_data['last_updated'] > timedelta(hours=1):
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        del chat_sessions[session_id]

def load_company_knowledge() -> str:
    """Load all company knowledge from JSON files and format as text"""
    database_path = Path(__file__).parent.parent / "database"
    knowledge_parts = []
    
    # Load each knowledge file
    files_to_load = [
        ("employees.json", "EMPLOYEE DIRECTORY"),
        ("policies.json", "COMPANY POLICIES"),
        ("protocols.json", "PROCEDURES AND PROTOCOLS"),
        ("company.json", "COMPANY INFORMATION"),
        ("strategy.json", "COMPANY STRATEGY")
    ]
    
    for filename, section_title in files_to_load:
        file_path = database_path / filename
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    knowledge_parts.append(f"{section_title}")
                    
                    # Format based on file type
                    if filename == "employees.json" and "employees" in data:
                        for emp in data["employees"]:
                            knowledge_parts.append(f"• {emp['name']} - {emp['role']} ({emp['department']})")
                            knowledge_parts.append(f"  Email: {emp['email']}")
                            knowledge_parts.append(f"  Expertise: {', '.join(emp['expertise'])}")
                            if emp.get('contact_for'):
                                knowledge_parts.append(f"  Contact for: {', '.join(emp['contact_for'])}")
                            knowledge_parts.append("")
                    
                    elif filename == "policies.json" and "policies" in data:
                        for policy in data["policies"]:
                            knowledge_parts.append(f"Policy: {policy['title']}")
                            knowledge_parts.append(f"Category: {policy['category']}")
                            knowledge_parts.append(f"Description: {policy['description']}")
                            knowledge_parts.append("Key Points:")
                            for point in policy['key_points']:
                                knowledge_parts.append(f"  - {point}")
                            knowledge_parts.append(f"Owner: {policy['owner']}")
                            knowledge_parts.append("")
                    
                    elif filename == "protocols.json" and "protocols" in data:
                        for protocol in data["protocols"]:
                            knowledge_parts.append(f"Process: {protocol['name']}")
                            knowledge_parts.append(f"Description: {protocol['description']}")
                            if 'steps' in protocol:
                                knowledge_parts.append("Steps:")
                                for step in protocol['steps']:
                                    knowledge_parts.append(f"  Step {step['step']}: {step['title']}")
                                    for action in step['actions']:
                                        knowledge_parts.append(f"    - {action}")
                                    if 'contact_if_help_needed' in step:
                                        knowledge_parts.append(f"    Contact: {step['contact_if_help_needed']}")
                            knowledge_parts.append("")
                    
                    elif filename == "company.json" and "company" in data:
                        comp = data["company"]
                        knowledge_parts.append(f"Company: {comp['name']}")
                        knowledge_parts.append(f"Mission: {comp['mission']}")
                        knowledge_parts.append(f"Values: {', '.join(comp['values'])}")
                        knowledge_parts.append("Products:")
                        for product in comp['products']:
                            knowledge_parts.append(f"  - {product['name']}: {product['description']}")
                        knowledge_parts.append("")
                    
                    elif filename == "strategy.json" and "strategy" in data:
                        strat = data["strategy"]
                        knowledge_parts.append(f"Fiscal Year: {strat['fiscal_year']}")
                        knowledge_parts.append("Revenue Goals:")
                        for key, value in strat['revenue_goals'].items():
                            knowledge_parts.append(f"  - {key.replace('_', ' ').title()}: {value}")
                        if 'competitive_positioning' in strat:
                            knowledge_parts.append("Competitive Advantages:")
                            for adv in strat['competitive_positioning']['our_advantages']:
                                knowledge_parts.append(f"  - {adv}")
                        knowledge_parts.append("")
                    
                    logger.info(f"Loaded {filename}")
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
    
    return '\n'.join(knowledge_parts)

# Load company knowledge once at startup
COMPANY_KNOWLEDGE = load_company_knowledge()
logger.info(f"Loaded company knowledge: {len(COMPANY_KNOWLEDGE)} characters")

@app.get("/")
async def root():
    return {"message": "TechVision AI Assistant with Company Knowledge Base and Structured Output"}

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        # Clean old sessions periodically
        clean_old_sessions()
        
        # Get or create session
        session_id = message.session_id or str(uuid.uuid4())
        logger.info(f"Processing chat request for session: {session_id}")
        
        if session_id not in chat_sessions:
            # Create new session with company knowledge as first message
            chat_sessions[session_id] = {
                'contents': [
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"You are a helpful AI assistant for Enterprise AI. You have access to the following company knowledge base. Use this information to answer questions and help employees.\n\n{COMPANY_KNOWLEDGE}\n\nPlease acknowledge that you have this knowledge.")]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I have access to Enterprise AI' complete knowledge base including employee directory, company policies, procedures and protocols, company information, and business strategy. I'm ready to help you with any questions about the company, processes, or to guide you through tasks." \
                        "You may receive a prompt such as 'Client meeting in 5 minutes, please give me a todo list or action plan considering company policies.")]
                    )
                ],
                'created': datetime.now(),
                'last_updated': datetime.now()
            }
        
        session = chat_sessions[session_id]
        session['last_updated'] = datetime.now()
        
        # Configure generation without tools
        config = types.GenerateContentConfig(
            temperature=0.7
        )
        
        # Add the new user message to the conversation
        session['contents'].append(
            types.Content(
                role="user", 
                parts=[types.Part(text=message.message)]
            )
        )
        
        # Send request with full conversation history
        logger.info(f"Sending request to Gemini model with {len(session['contents'])} messages")
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=session['contents'],
            config=config
        )
        
        # Add the response to history and return
        print(f"Response: {response.text}")
        print(f"Response candidates: {response.candidates}")
        
        session['contents'].append(response.candidates[0].content)
        
        return ChatResponse(
            response=response.text,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/structured-chat", response_model=StructuredChatResponse)
async def structured_chat(message: StructuredChatMessage):
    try:
        # Clean old sessions periodically
        clean_old_sessions()
        
        # Get or create session
        session_id = message.session_id or str(uuid.uuid4())
        logger.info(f"Processing structured chat request for session: {session_id}")
        
        if session_id not in chat_sessions:
            # Create new session with company knowledge as first message
            chat_sessions[session_id] = {
                'contents': [
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"You are a helpful AI assistant for Enterprise AI. You have access to the following company knowledge base. Use this information to answer questions and help employees.\n\n{COMPANY_KNOWLEDGE}\n\nYou should extract action points and consideration points from conversations and meetings. Action points are tasks that need to be completed with priorities and optional due dates. Consideration points are important notes, observations, or things to keep in mind.")]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I have access to Enterprise AI's complete knowledge base and I'm ready to help extract action points and consideration points from your conversations and meetings in a structured format.")]
                    )
                ],
                'created': datetime.now(),
                'last_updated': datetime.now()
            }
        
        session = chat_sessions[session_id]
        session['last_updated'] = datetime.now()
        
        # Configure generation with structured output
        config = types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json",
            response_schema=STRUCTURED_OUTPUT_SCHEMA
        )
        
        # Add the new user message to the conversation
        enhanced_message = f"""
        Please analyze the following text and extract action points and consideration points:
        
        {message.message}
        
        Extract:
        - Action points: Specific tasks that need to be completed, with priority levels (low/medium/high) and optional due dates
        - Consideration points: Important notes, observations, decisions, or things to keep in mind, categorized appropriately
        """
        
        session['contents'].append(
            types.Content(
                role="user", 
                parts=[types.Part(text=enhanced_message)]
            )
        )
        
        # Send request with full conversation history
        logger.info(f"Sending structured request to Gemini model with {len(session['contents'])} messages")
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-05-06",
            contents=session['contents'],
            config=config
        )
        
        # Parse the structured response
        try:
            structured_data = json.loads(response.text)
            parsed_response = StructuredResponse(**structured_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse structured response: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse structured response")
        
        # Add the response to history
        session['contents'].append(response.candidates[0].content)
        
        return StructuredChatResponse(
            structured_data=parsed_response,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Error in structured chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session history for debugging"""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = chat_sessions[session_id]
    return {
        "session_id": session_id,
        "created": session['created'],
        "last_updated": session['last_updated'],
        "message_count": len(session['contents'])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 