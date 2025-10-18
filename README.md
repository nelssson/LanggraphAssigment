# Credly Badge Points Calculator

An AI-powered agent that automatically fetches Credly certification badge details and calculates points based on certification types. Built with LangGraph and ChatGroq.

## Overview

This application uses an AI agent to analyze Credly certification badges and assign points based on certification levels. It scrapes badge information from Credly URLs, stores certification point values in a SQLite database, and provides intelligent responses about certifications.

## Features

- **Automatic Badge Scraping**: Extracts title, issuer, issue date, description, and skills from Credly badge URLs
- **Points Calculation**: Automatically assigns points based on certification type:
  - Professional/Specialty Certifications: 10 points
  - Associate/HashiCorp Certifications: 5 points
  - Other Certifications: 2.5 points
- **Database Management**: SQLite database to store and manage custom certification point values
- **AI Agent**: Uses LangGraph with ChatGroq to intelligently process queries and call appropriate tools
- **Multiple Tools**: Six specialized tools for different badge analysis tasks

## Prerequisites

- Python 3.8+
- GROQ API key (for ChatGroq LLM)

## Installation

1. **Clone or download the project files**

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install required dependencies**:
```bash
pip install langchain-groq langgraph langchain-core requests beautifulsoup4 sqlite3
```

4. **Set up your GROQ API key**:
```bash
export GROQ_API_KEY="your_api_key_here"  # On Windows: set GROQ_API_KEY=your_api_key_here
```

## Database Structure

The application creates a SQLite database (`certification_points.db`) with the following structure:

```sql
CREATE TABLE certification_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cert_type TEXT NOT NULL,
    points REAL NOT NULL
)
```

**Default Values**:
- Professional or Specialty: 10.0 points
- Associate or Hashicorp: 5.0 points
- Other: 2.5 points

## Available Tools

The agent has access to six tools:

### 1. `get_credly_badge_details(url: str)`
Fetches and extracts detailed information from a Credly badge URL.

**Returns**: Badge title, issuer, issue date, description, and skills

### 2. `get_certification_points(cert_type: str)`
Looks up points for a specific certification type.

**Returns**: Points value and certification category

### 3. `get_badge_details_with_points(url: str)` ⭐ **Recommended**
Combines badge detail extraction with automatic points calculation in one step.

**Returns**: Formatted analysis with badge details and calculated points

### 4. `update_certification_points(cert_type: str, points: float)`
Updates or adds points for a certification type in the database.

**Returns**: Confirmation message

### 5. `list_all_certification_points()`
Lists all certification types and their point values from the database.

**Returns**: Formatted table of certifications and points

### 6. `compute_points_from_badge_question(question: str)`
Extracts URL from a natural language question and returns badge analysis.

**Returns**: Summary with badge details and points

## Usage Examples

### Basic Usage

```python
from langchain_core.messages import HumanMessage

# Initialize the agent (already done in the code)
# graph is the created agent

# Example 1: Analyze a Credly badge
response = graph.invoke({
    "messages": [HumanMessage(content="Analyze this badge: https://www.credly.com/badges/example-badge-id")]
})
print(response["messages"][-1].content)

# Example 2: Get points for a certification
response = graph.invoke({
    "messages": [HumanMessage(content="How many points is an AWS Solutions Architect Professional worth?")]
})
print(response["messages"][-1].content)

# Example 3: List all certifications
response = graph.invoke({
    "messages": [HumanMessage(content="Show me all certification point values")]
})
print(response["messages"][-1].content)

# Example 4: Update certification points
response = graph.invoke({
    "messages": [HumanMessage(content="Update Azure Administrator Associate to 7 points")]
})
print(response["messages"][-1].content)
```

### Running the Agent

```python
import os
from langchain_core.messages import HumanMessage

# Ensure GROQ_API_KEY is set
os.environ["GROQ_API_KEY"] = "your_api_key_here"

# The agent is ready to use
while True:
    user_input = input("\nYou: ")
    if user_input.lower() in ['exit', 'quit']:
        break
    
    response = graph.invoke({
        "messages": [HumanMessage(content=user_input)]
    })
    
    print(f"\nAgent: {response['messages'][-1].content}")
```

## Points Classification Rules

The system automatically classifies certifications based on keywords in the title:

1. **10 Points**: Contains "professional" OR "specialty"
   - Example: AWS Certified Solutions Architect - Professional
   
2. **5 Points**: Contains "associate" OR "hashicorp"
   - Example: AWS Certified Developer - Associate
   
3. **2.5 Points**: All other certifications
   - Example: Microsoft Certified: Azure Fundamentals

## How It Works

1. **User Query**: User asks a question about a Credly badge or certification
2. **Agent Decision**: The AI agent analyzes the query and decides which tool(s) to use
3. **Tool Execution**: The agent calls the appropriate tool(s) to fetch data or perform actions
4. **Response Generation**: The agent synthesizes the tool results into a natural language response

## Architecture

- **LangGraph**: Orchestrates the agent workflow and tool execution
- **ChatGroq**: Provides the LLM for intelligent decision-making (using `openai/gpt-oss-20b` model)
- **SQLite**: Stores certification point mappings
- **BeautifulSoup4**: Scrapes Credly badge pages
- **Requests**: Handles HTTP requests to Credly

## Troubleshooting

### Badge Scraping Issues

If badge details cannot be extracted:
- Verify the URL is a valid, public Credly badge URL
- Check if the badge page has changed its HTML structure
- Ensure the badge hasn't been archived or removed

### Database Errors

If you encounter database errors:
```bash
# Delete the database and restart (will reinitialize with defaults)
rm certification_points.db
python your_script.py
```

### API Key Issues

Ensure your GROQ API key is properly set:
```python
import os
print(os.environ.get("GROQ_API_KEY"))  # Should not be None
```

## Customization

### Change Point Values

Update default point values by modifying the `default_values` list in `init_db()`:

```python
default_values = [
    ("Professional or Specialty", 15.0),  # Changed from 10.0
    ("Associate or Hashicorp", 7.5),      # Changed from 5.0
    ("Other", 3.0)                         # Changed from 2.5
]
```

### Add Custom Classification Rules

Modify the `lookup_points_by_cert_type()` function to add custom rules:

```python
if 'expert' in cert_lower:
    return 15.0, 'Expert Level', 'rule'
```

### Change LLM Model

Update the model in the `ChatGroq` initialization:

```python
llm = ChatGroq(groq_api_key=groq_api_key, model="llama3-70b-8192")
```

## Limitations

- Only works with public Credly badges
- Scraping depends on Credly's HTML structure (may break if they update their site)
- Requires internet connection to fetch badge details
- Rate limiting may apply for excessive requests

## Future Enhancements

- Add support for other certification platforms (LinkedIn Learning, Coursera, etc.)
- Implement caching to reduce redundant requests
- Add expiration date tracking and alerts
- Create a web interface for easier interaction
- Export certification data to CSV/Excel

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Verify all dependencies are installed correctly
3. Ensure your GROQ API key is valid and has available credits

---

**Note**: This application uses web scraping which may be affected by changes to the Credly website structure. Always respect rate limits and terms of service when scraping websites.
