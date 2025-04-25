from typing import Dict
from capmaign_agents.mongo import connect_to_database
from zoneinfo import ZoneInfo
from PyPDF2 import PdfReader
from docx import Document
from google.adk.agents import Agent
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import os
from urllib.parse import urlparse
import requests
from io import BytesIO
from typing import List
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict
import requests
import csv
from io import BytesIO


class CampaignDesignAgentInput(BaseModel):
    message: str
    files: Optional[List[HttpUrl]] = None

class CampaignDesignOutput(BaseModel):
    confirmed_goals: str
    confirmed_financial_metrics: str
    confirmed_timeline: str
    confirmed_budget: str

class ResearchAgentInput(BaseModel):
    goals: Optional[str] = Field(None, description="The high-level objectives of the campaign.")
    financial_metrics: Optional[str] = Field(
        None, 
        description="Key financial goals and KPIs (e.g. ROI, CAC, LTV)."
    )
    timeline: Optional[str] = Field(
        None, 
        description="Timeline details including start and end dates or campaign phases."
    )
    budget: Optional[str] = Field(
        None, 
        description="The total budget for the campaign, including any channel breakdowns if available."
    )


class WorkstreamBrief(BaseModel):
    campaign_message: str
    influencer_profiles: List[str]
    content_formats: List[str]
    timeline_and_deliverables: Dict[str, str]
    summary: str


def get_file_text_from_urls(urls: List[str]) -> str:
    full_text = ""
    for url in urls:
        parsed = urlparse(url)
        name = os.path.basename(parsed.path)

        try:
            resp = requests.get(url)
            resp.raise_for_status()
            content = resp.content

            if name.lower().endswith(".pdf"):
                pdf = PdfReader(BytesIO(content))
                for i, page in enumerate(pdf.pages, 1):
                    full_text += f"\n--- {name} [PDF page {i}] ---\n"
                    full_text += page.extract_text() or ""

            elif name.lower().endswith(".docx"):
                doc = Document(BytesIO(content))
                full_text += f"\n--- {name} [DOCX] ---\n"
                for para in doc.paragraphs:
                    full_text += para.text + "\n"

            elif name.lower().endswith(".csv"):
                full_text += f"\n--- {name} [CSV] ---\n"
                decoded = content.decode("utf-8").splitlines()
                reader = csv.reader(decoded)
                for row in reader:
                    full_text += ", ".join(row) + "\n"

            else:
                full_text += f"\n--- {name} [RAW TEXT] ---\n"
                full_text += content.decode("utf-8", errors="replace") + "\n"

        except Exception as e:
            full_text += f"\n[Error reading {name}]: {e}\n"

    return full_text


def file_review_tool(file_urls: List[str]) -> str:
    return get_file_text_from_urls(file_urls)

def extract_campaign_elements(context: str) -> dict:
    return {
        "campaign_message": "Drive Gen Z buzz and excitement around the product launch.",
        "influencer_profiles": ["Gen Z creators", "Trendy food/lifestyle influencers"],
        "content_formats": ["TikToks", "Reels", "IG Stories"],
        "timeline_and_deliverables": {
            "kickoff": "Immediately after approvals",
            "draft content": "2 weeks",
            "final delivery": "4 weeks"
        }
    }

def insert_brief(brief_data: dict):
    client = connect_to_database()
    db = client["test"]
    collection = db["campaignBrief"]

    result = collection.insert_one(brief_data)
    print(f"Document inserted with ID")
    return f'new_brief_id : {str(result.inserted_id)}'


campaign_design_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="campaign_design_agent",
    description="Extracts campaign inputs from brand files or user input, then validates all required information.",
    instruction=f"""
        You are a Campaign Design Agent. Your job is to gather all the necessary inputs for designing a marketing campaign.

        Start by asking the user to upload or provide access to any of the following:
        - Brand Guidelines
        - Documentation Samples
        - Requests for Proposals (RFPs)

        Once files are received or pasted as text, analyze the content and extract the following required campaign inputs:
        - Campaign Goals
        - Financial Metrics (e.g., expected ROI, CAC, LTV)
        - Timeline (start and end dates, phases if any)
        - Budget (total budget, allocation per channel if available)

        When files are received dont start reviewing them automatically first ask if user want to upload more files if no then analyse files and show what information you get and what info you need more
        It consistently shows the data it has gathered, as well as the information that is yet to be collected.

        After analyzing the documents, check if any of these required fields are missing or unclear.
        If any fields are missing, ask the user to provide that specific information.

        Once all fields are confirmed and validated, pass the completed data to the Research Agent for deeper market analysis.

        Do not proceed until all the required data is fully gathered and validated.

        After presenting your findings, **ask the user**:
        "Should we move to next step to create Competitor Report?"
    """,
    input_schema=CampaignDesignAgentInput,
    tools=[file_review_tool],
    output_key="campaign_design_output"
)

research_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="research_agent",
    description="Performs campaign-related research and produces a competitor report.",
    instruction="""
    You are the Research Agent. After receiving a campaign's goals, financial metrics, timeline, and budget, your role is to:

    1. Conduct a generative web search to gather:
        - Historical Data relevant to the campaign type
        - Assumptions to support planning (e.g., platform trends, average CPMs)
        - Priorities to apply to both first-party and third-party data

    2. Produce a detailed Competitor Report(based on the data provided and not too long) that includes:
        - Campaigns Run by Competitors
        - What to Copy, What to Avoid

    3. Formulate a campaign design statement(based on the data provided) like:
       "Working for McDonald's With $500 budget To see if we can get creators to promote their new sandwich."

    Be data-driven and strategic in your analysis. Your output should be clear, actionable, and formatted for campaign planning. Return your complete response all at once, not in parts.

    After presenting your findings, **ask the user**:
    "Would you like to create the campaign brief now?"
    """,
    input_schema=ResearchAgentInput,
    output_key="competitor_report"
)

brief_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="brief_agent",
    description="Creates a structured campaign brief from brand documents and templates.",
    instruction="""
        You are the Brief Agent. Your job is to create a structured campaign brief using brand-provided material.
        Also include a **campaign idea**, like: "Find creators to run a campaign about competitive eating a new sandwich" or "Find chicken sandwich fans and ask them to do a review."

        From these materials, extract the following:
        1. Type of Brief – Define what kind of job or campaign this is.
        2. Campaign Design Aspects to be Fulfilled – What specific needs or creative elements must the campaign achieve?
        3. Brand Attributes to be considered:
            - Brand Tone
            - Brand History
            - Overall Brand Strategy
            - How this campaign fits the strategy

        Combine all of this into a **Campaign Brief** with:
        - Clear Goals
        - Specific Objectives
        - Strategic Context

        Do not make assumptions. Extract directly from provided documents. If anything is missing, ask the user for it.
        And give your response at once not in parts

        After completing the campaign brief, ask the user: "Would you like to initiate creator research now?"
    """,
    # tools=[insert_brief],
    output_key="campaign_brief"
)

creator_research_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="creator_research_agent",
    description="Conducts structured research to identify creators, evaluate scope, assess storage needs, and define data sources.",
    instruction="""
        You are the Creator Research Agent. Your job is to run a multi-step process to identify and evaluate creators for a campaign.

        Your tasks include:
        
        1. **Make a List of Creators**  
           Identify potential creators that match the campaign’s audience and platform requirements (e.g., TikTok, Instagram). List their handles, follower count, niche, and engagement metrics.

        2. **Evaluate Amount of Creators Needed**  
           Based on the campaign goals and budget, estimate the number of creators required to meet reach and engagement targets.

        3. it also provides these data as a json like this
        Data as JSON:
        {
            'Goals': [List<string> of Goals... with /n(new line) to seperate these],
            'KPIs': [List<string> of KPIs... with /n(new line) to seperate these],
            'Timeline': ["..."](just 1 string in list),
            'Budget': ["..."](just 1 string in list)
        }
        Output your full findings in structured text. Do not skip steps or return partial responses.
    """,
    output_key="creator_research"
)

root_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="campaign_agent",
    description="Orchestrates the design, research, brief creation, and creator discovery process for a new campaign.",
    instruction="""
        You are the Campaign Orchestrator. Your job is to control the flow between agents — you do not generate responses yourself. Only the sub-agents should handle user interactions and generate outputs.

        Step 1: Run the `campaign_design_agent`. Guide the user to provide or upload necessary campaign inputs (Brand Guidelines, RFPs, Budget, Timeline, etc.). Validate all inputs.

        Step 2: Once all required data is confirmed then show user that required data is complete now passing to research_agent, automatically pass the structured output directly to the `research_agent` without asking the user again .

        Do NOT show the output of the `campaign_design_agent` to the user. Just inform the user that the research process has started and generate output automatically and show.

        Step 3: Let the `research_agent` analyze the campaign details, generate insights (historical data, assumptions, priorities), and produce a competitor report.
        Your show the result of the `research_agent`, not the intermediate output of the design agent.

        Step 4: After the competitor report is generated, pass all information to the `brief_agent`. The `brief_agent` must generate a complete campaign brief in one go, not in parts.

        Step 5: Finally, run the `creator_research_agent`. It will:
            - List potential creators aligned with the campaign
            - Estimate how many creators are needed

        Only show final results from each step to the user, not intermediate data.
        And Remember dont shift agents in the middle of response only 1 agent response at a time before moving to next you should ask user ...
    """,
    sub_agents=[campaign_design_agent, research_agent, brief_agent, creator_research_agent],
    output_key="root_agent"
)


        # 3. **Evaluate Efforts Required for Storing the Data**  
        #    Outline technical requirements to handle and store creator data — changes needed in database structure, updates to ETL (Extract, Transform, Load) processes, and any potential bottlenecks.

        # 4. **Define Data Sources to Fetch Missing Attributes**  
        #    If any important data is missing (like audience demographics or average engagement), identify the data sources (e.g., influencer databases, social analytics tools) from which this data can be pulled.

            # - Evaluate technical storage and data-handling needs
            # - Identify sources to fetch any missing attributes

# root_agent = Agent(
#     model="gemini-2.0-flash-exp",
#     name="campaign_brief_agent",
#     description="Assists in planning influencer marketing campaigns by gathering initial requirements and reviewing provided documentation.",
#     instruction="""You are an AI Campaign Brief Agent that helps kickstart influencer campaigns.
#         You interact with a human creative director and follow these steps:
#         1. Ask the user to upload all relevant files (e.g., Brand Guidelines, Documentation Samples, Pitch Decks).
#         2. Once the files are uploaded, acknowledge receipt and confirm the file types.
#         3. Review the uploaded documents to extract relevant campaign inputs such as:
#             - Key campaign message
#             - Ideal influencer profiles
#             - Content format ideas (Reels, TikToks, Stories, etc.)
#             - Suggested timeline and deliverables
#         4. Fill in the campaign workstream settings with the extracted information.
#         5. Communicate clearly and professionally throughout.

#         Wait to review files before proceeding to planning details. Do not make assumptions about campaign goals—always derive them from the user's uploads and instructions.
#         """,
#     input_schema=CampaignDesignAgentInput,
#     tools=[file_review_tool, extract_campaign_elements],
#     output_key="workstream_brief_result"
# )


# root_agent = Agent(
#         name="weather_agent_v2", 
#         model="gemini-2.0-flash-exp",
#         description="You are the main Weather Agent, coordinating a team. - Your main task: Provide weather using the `get_weather` tool. Handle its 'status' response ('report' or 'error_message'). - Delegation Rules: - If the user gives a simple greeting (like 'Hi', 'Hello'), delegate to `greeting_agent`. - If the user gives a simple farewell (like 'Bye', 'See you'), delegate to `farewell_agent`. - Handle weather requests yourself using `get_weather`. - For other queries, state clearly if you cannot handle them.",
#         tools=[get_weather], # Root agent still needs the weather tool
#         sub_agents=[greeting_agent, farewell_agent]
# )

# campaign_flow_agent = Agent(
#     model="gemini-2.0-flash-exp",
#     name="campaign_flow_agent",
#     description="Orchestrates the design and research process for a new campaign.",
#     instruction="First run the Campaign Design Agent to gather all required inputs, then pass the results to the Research Agent.",
#     children=[campaign_design_agent, research_agent]
# )



        # and also insert brief in database using the tool and here is its format.
        # {
        #     "brief_type": "...",
        #     "design_aspects": "...",
        #     "brand_tone": "...",
        #     "brand_history": "...",
        #     "brand_strategy": "...",
        #     "strategic_fit": "...",
        #     "campaign_goals": "...",
        #     "campaign_objectives": "..."
        # }
        # When brief created the tool returns the id of newly created brief you have to show the new_brief_id also
        # Remember not only show json format on screen just show text on screen and json format for insert in database