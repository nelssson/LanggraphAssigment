import os
import sqlite3
from typing import Annotated, TypedDict, Dict, Optional, Tuple
from datetime import datetime
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, END, START
import requests
from bs4 import BeautifulSoup
import re

# Initialize SQLite database and create certification points table
def init_db():
    """Initialize the SQLite database and create the certification points table."""
    conn = sqlite3.connect('certification_points.db')
    cursor = conn.cursor()
    
    # Create the certification points table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certification_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cert_type TEXT NOT NULL,
        points REAL NOT NULL
    )
    ''')
    
    # Insert default values if they don't exist
    default_values = [
        ("Professional or Specialty", 10.0),
        ("Associate or Hashicorp", 5.0),
        ("Other", 2.5)
    ]
    
    # Check if table is empty
    cursor.execute("SELECT COUNT(*) FROM certification_points")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO certification_points (cert_type, points) VALUES (?, ?)",
            default_values
        )
    
    conn.commit()
    conn.close()

# Initialize the database when the module loads
init_db()

# Read GROQ_API_KEY from environment
groq_api_key = os.environ.get("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY environment variable not set.")

# -------------------- Tool Definitions --------------------
 
   
def is_certificate_expired(date_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Check if a certificate is expired based on its expiration date string."""
    if not date_str:
        return False, None
        
    try:
        # Try different date formats
        date_formats = [
            '%Y-%m-%d',           # 2025-10-18
            '%d/%m/%Y',           # 18/10/2025
            '%B %d, %Y',          # October 18, 2025
            '%b %d, %Y',          # Oct 18, 2025
            '%Y-%m-%dT%H:%M:%SZ'  # ISO format
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
                
        if parsed_date:
            is_expired = parsed_date.date() < datetime.now().date()
            return is_expired, parsed_date.strftime('%Y-%m-%d')
            
        return False, None
    except Exception:
        return False, None

@tool
def get_credly_badge_details(url: str) -> str:
    """Fetch and extract details from a Credly badge URL.
    
    Args:
        url: The Credly badge URL to fetch details from
        
    Returns:
        A string containing the badge details including title, issuer, skills, description,
        and expiration status. If the certificate is expired, it will be noted.
    """
    print(f"[TOOL CALL] get_credly_badge_details called with: url={url}")
    
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract badge details
        details = {}
        
        # Badge title - multiple possible selectors
        title = (
            soup.find('h1', {'data-testid': 'badge-title'}) or
            soup.find('h1', class_='badge-name') or
            soup.find('h1', class_='cr-badge-name') or
            soup.select_one('[class*="badge-title"]') or
            soup.select_one('[class*="badgeName"]')
        )
        if title:
            details['title'] = title.get_text(strip=True)
        
        # Issuer - multiple possible selectors
        issuer = (
            soup.find('div', {'data-testid': 'badge-issuer'}) or
            soup.find('div', class_='issuer-name') or
            soup.find('div', class_='cr-issuer-name') or
            soup.select_one('[class*="issuer-name"]') or
            soup.select_one('[class*="issuerName"]')
        )
        if issuer:
            details['issuer'] = issuer.get_text(strip=True)
        
        # Issue date - multiple possible selectors
        issued_date = (
            soup.find('div', {'data-testid': 'badge-issued'}) or
            soup.find('div', class_='issued-on') or
            soup.find('div', class_='cr-issued-on') or
            soup.select_one('[class*="issuedOn"]') or
            soup.select_one('time') or
            soup.select_one('[datetime]')
        )
        if issued_date:
            details['issued_on'] = issued_date.get_text(strip=True)
        
        # Badge description - multiple possible selectors
        description = (
            soup.find('div', {'data-testid': 'badge-description'}) or
            soup.find('div', class_='badge-description') or
            soup.find('div', class_='cr-badge-description') or
            soup.select_one('[class*="description"]')
        )
        if description:
            details['description'] = description.get_text(strip=True)
        
        # Skills - multiple possible selectors
        skills = []
        skill_elements = (
            soup.find_all('div', {'data-testid': 'badge-skills'}) or
            soup.find_all('div', class_='skill-name') or
            soup.find_all('div', class_='cr-skill-name') or
            soup.select('[class*="skill-tag"]') or
            soup.select('[class*="skillTag"]')
        )
        if skill_elements:
            skills = [skill.get_text(strip=True) for skill in skill_elements if skill.get_text(strip=True)]
            if skills:
                details['skills'] = skills
        
        # Format the results
        result = "Credly Badge Details:\n\n"
        
        if not details:
            # Try to extract any structured data
            for meta in soup.find_all('meta', {'property': True, 'content': True}):
                prop = meta['property'].lower()
                if 'title' in prop:
                    details['title'] = meta['content']
                elif 'description' in prop:
                    details['description'] = meta['content']
        
        for key, value in details.items():
            if isinstance(value, list):
                result += f"{key.title()}: {', '.join(value)}\n"
            else:
                result += f"{key.title()}: {value}\n"
        
        if not details:
            result = "Could not extract badge details from the URL. Please verify:\n1. The URL is a valid Credly badge URL\n2. The badge is publicly accessible\n3. The badge hasn't been archived or removed"
        
        print("[TOOL RESULT] get_credly_badge_details returned:", result[:200] + "...")
        return result
        
    except requests.RequestException as e:
        error_msg = f"Error fetching Credly badge: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error parsing Credly badge details: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg

@tool
def get_certification_points(cert_type: str) -> str:
    """
    Get the points for a certification type.
    
    Args:
        cert_type: The type of certification to look up (e.g., certification title or type)
        
    Returns:
        A string containing the points value and certification type
    """
    print(f"[TOOL CALL] get_certification_points called with: cert_type={cert_type}")
    
    try:
        conn = sqlite3.connect('certification_points.db')
        cursor = conn.cursor()
        
        # First try exact match
        cursor.execute(
            "SELECT points FROM certification_points WHERE LOWER(cert_type) = LOWER(?)",
            (cert_type,)
        )
        result = cursor.fetchone()
        
        if not result:
            # If no exact match, apply the classification rules
            cert_lower = cert_type.lower()
            if "professional" in cert_lower or "specialty" in cert_lower:
                points = 10.0
            elif "associate" in cert_lower or "hashicorp" in cert_lower:
                points = 5.0
            else:
                points = 2.5
        else:
            points = result[0]
            
        response = f"Certification '{cert_type}' is worth {points} points"
        print("[TOOL RESULT] get_certification_points returned:", response)
        return response
        
    except Exception as e:
        error_msg = f"Error getting certification points: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg
    finally:
        conn.close()

@tool
def get_badge_details_with_points(url: str) -> str:
    """
    Fetch Credly badge details from URL and automatically calculate certification points.
    This is the recommended tool for analyzing Credly badges - it combines badge detail extraction
    with points calculation in one step.
    
    Args:
        url: The Credly badge URL to analyze
        
    Returns:
        A formatted string with badge details and calculated points
    """
    print(f"[TOOL CALL] get_badge_details_with_points called with: url={url}")
    
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract badge details
        title = None
        issuer = None
        issued_on = None
        description = None
        
        # Badge title
        title_el = (
            soup.find('h1', {'data-testid': 'badge-title'}) or
            soup.find('h1', class_='badge-name') or
            soup.find('h1', class_='cr-badge-name') or
            soup.select_one('[class*="badge-title"]') or
            soup.select_one('[class*="badgeName"]')
        )
        if title_el:
            title = title_el.get_text(strip=True)
        
        # Issuer
        issuer_el = (
            soup.find('div', {'data-testid': 'badge-issuer'}) or
            soup.find('div', class_='issuer-name') or
            soup.find('div', class_='cr-issuer-name') or
            soup.select_one('[class*="issuer-name"]') or
            soup.select_one('[class*="issuerName"]')
        )
        if issuer_el:
            issuer = issuer_el.get_text(strip=True)
        
        # Issue date
        issued_date_el = (
            soup.find('div', {'data-testid': 'badge-issued'}) or
            soup.find('div', class_='issued-on') or
            soup.find('div', class_='cr-issued-on') or
            soup.select_one('[class*="issuedOn"]') or
            soup.select_one('time')
        )
        if issued_date_el:
            issued_on = issued_date_el.get_text(strip=True)
        
        # Description
        description_el = (
            soup.find('div', {'data-testid': 'badge-description'}) or
            soup.find('div', class_='badge-description') or
            soup.find('div', class_='cr-badge-description')
        )
        if description_el:
            description = description_el.get_text(strip=True)
        
        # If we couldn't find title, try meta tags
        if not title:
            for meta in soup.find_all('meta', {'property': True, 'content': True}):
                if 'title' in meta['property'].lower():
                    title = meta['content']
                    break
        
        # Calculate points based on the title
        if not title:
            return "Could not extract badge title from URL. Unable to calculate points."
        
        # Look up points using the title
        conn = sqlite3.connect('certification_points.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT points FROM certification_points WHERE LOWER(cert_type) = LOWER(?)",
            (title,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Apply classification rules
            title_lower = title.lower()
            if "professional" in title_lower or "specialty" in title_lower:
                points = 10.0
                matched_category = "Professional or Specialty"
            elif "associate" in title_lower or "hashicorp" in title_lower:
                points = 5.0
                matched_category = "Associate or Hashicorp"
            else:
                points = 2.5
                matched_category = "Other"
        else:
            points = result[0]
            matched_category = "Exact match in database"
        
        conn.close()
        
        # Format the output
        output = "=" * 60 + "\n"
        output += "CREDLY BADGE ANALYSIS\n"
        output += "=" * 60 + "\n\n"
        
        output += f"📜 Certificate Title: {title}\n"
        if issuer:
            output += f"🏢 Issuer: {issuer}\n"
        if issued_on:
            output += f"📅 Issued On: {issued_on}\n"
        
        output += f"\n⭐ POINTS AWARDED: {points}\n"
        output += f"📊 Category: {matched_category}\n"
        
        if description:
            output += f"\n📝 Description:\n{description[:200]}{'...' if len(description) > 200 else ''}\n"
        
        output += "\n" + "=" * 60
        
        print("[TOOL RESULT] get_badge_details_with_points returned:", output[:300] + "...")
        return output
        
    except requests.RequestException as e:
        error_msg = f"Error fetching Credly badge: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error analyzing badge: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg

@tool
def update_certification_points(cert_type: str, points: float) -> str:
    """
    Update or add points for a certification type.
    
    Args:
        cert_type: The type of certification to update
        points: The number of points for this certification
        
    Returns:
        A string confirming the update
    """
    print(f"[TOOL CALL] update_certification_points called with: cert_type={cert_type}, points={points}")
    
    try:
        conn = sqlite3.connect('certification_points.db')
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute(
            "SELECT id FROM certification_points WHERE LOWER(cert_type) = LOWER(?)",
            (cert_type,)
        )
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute(
                "UPDATE certification_points SET points = ? WHERE LOWER(cert_type) = LOWER(?)",
                (points, cert_type)
            )
            action = "updated"
        else:
            cursor.execute(
                "INSERT INTO certification_points (cert_type, points) VALUES (?, ?)",
                (cert_type, points)
            )
            action = "added"
        
        conn.commit()
        response = f"Successfully {action} points for '{cert_type}' to {points}"
        print("[TOOL RESULT] update_certification_points returned:", response)
        return response
        
    except Exception as e:
        error_msg = f"Error updating certification points: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg
    finally:
        conn.close()

@tool
def list_all_certification_points() -> str:
    """
    List all certification types and their points.
    
    Returns:
        A formatted string containing all certification types and their points
    """
    print("[TOOL CALL] list_all_certification_points called")
    
    try:
        conn = sqlite3.connect('certification_points.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT cert_type, points FROM certification_points ORDER BY points DESC")
        results = cursor.fetchall()
        
        if not results:
            return "No certification points found in the database."
            
        response = "Certification Points:\n\n"
        response += "| Certification Type | Points |\n"
        response += "|-------------------|--------|\n"
        
        for cert_type, points in results:
            response += f"| {cert_type} | {points} |\n"
            
        print("[TOOL RESULT] list_all_certification_points returned:", response[:200] + "...")
        return response
        
    except Exception as e:
        error_msg = f"Error listing certification points: {str(e)}"
        print("[TOOL ERROR]", error_msg)
        return error_msg
    finally:
        conn.close()

# Helper function to extract badge fields (kept for backward compatibility)
def extract_badge_fields(url: str) -> Dict[str, Optional[str]]:
    """Return {'title':..., 'issuer':..., 'error':...} by scraping the given URL with requests/BS4."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        title_el = (
            soup.find('h1', {'data-testid': 'badge-title'}) or
            soup.find('h1', class_='badge-name') or
            soup.find('h1', class_='cr-badge-name') or
            soup.select_one('[class*="badge-title"]') or
            soup.select_one('[class*="badgeName"]')
        )
        issuer_el = (
            soup.find('div', {'data-testid': 'badge-issuer'}) or
            soup.find('div', class_='issuer-name') or
            soup.find('div', class_='cr-issuer-name') or
            soup.select_one('[class*="issuer-name"]') or
            soup.select_one('[class*="issuerName"]')
        )

        return {
            'title': title_el.get_text(strip=True) if title_el else None,
            'issuer': issuer_el.get_text(strip=True) if issuer_el else None,
            'error': None
        }
    except Exception as e:
        return {'title': None, 'issuer': None, 'error': str(e)}


def lookup_points_by_cert_type(cert_type: str) -> tuple[float, Optional[str], str]:
    """Return (points, matched_label, source) where source is 'db' or 'rule'"""
    try:
        conn = sqlite3.connect('certification_points.db')
        cursor = conn.cursor()
        cursor.execute("SELECT cert_type, points FROM certification_points WHERE LOWER(cert_type) = LOWER(?)", (cert_type,))
        row = cursor.fetchone()
        if row:
            return float(row[1]), row[0], 'db'
        cert_lower = cert_type.lower()
        if 'professional' in cert_lower or 'specialty' in cert_lower:
            return 10.0, 'Professional or Specialty', 'rule'
        if 'associate' in cert_lower or 'hashicorp' in cert_lower:
            return 5.0, 'Associate or Hashicorp', 'rule'
        return 2.5, 'Other', 'rule'
    except Exception:
        return 2.5, 'Other', 'error'
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def compute_points_from_badge_question(question: str) -> str:
    """Extract URL from a human question, scrape badge fields, look up points and return a summary string."""
    print(f"[TOOL CALL] compute_points_from_badge_question called with: question={question}")
    m = re.search(r"(https?://[^\s]+)", question)
    if not m:
        return "No URL found in the question. Please include a Credly badge URL."
    url = m.group(1)

    details = extract_badge_fields(url)
    if details.get('error'):
        return f"Failed to fetch badge details: {details['error']}"

    title = details.get('title') or ''
    issuer = details.get('issuer') or ''

    lookup_key = title if title else issuer if issuer else url
    points, matched_label, source = lookup_points_by_cert_type(lookup_key)

    parts = []
    if title:
        parts.append(f"Badge title: '{title}'")
    if issuer:
        parts.append(f"Issuer: '{issuer}'")
    parts.append(f"Points: {points} (matched by {source}: {matched_label})")
    parts.append(f"Source URL: {url}")

    response = " | ".join(parts)
    print("[TOOL RESULT] compute_points_from_badge_question returned:", response)
    return response

# List of available tools - updated to include the new combined tool
tools = [ get_credly_badge_details, 
         get_certification_points, get_badge_details_with_points,
         update_certification_points, list_all_certification_points,
         compute_points_from_badge_question]

# -------------------- LLM Setup --------------------
# Initialize the LLM with Groq API key and model
llm = ChatGroq(groq_api_key=groq_api_key, model="openai/gpt-oss-20b")

# -------------------- Create Agent --------------------
# Create the agent using the built-in create_react_agent
graph = create_react_agent(llm, tools)