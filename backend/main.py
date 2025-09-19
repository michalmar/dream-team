# File: main.py
from fastapi import FastAPI, Depends, UploadFile, HTTPException, Query, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient
# from sqlalchemy.orm import Session
import schemas, crud
from database import CosmosDB
import os
import uuid
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse, Response
import json, asyncio
from magentic_one_helper import MagenticOneHelper
from autogen_agentchat.messages import MultiModalMessage, TextMessage, ToolCallExecutionEvent, ToolCallRequestEvent, SelectSpeakerEvent, ToolCallSummaryMessage
from autogen_agentchat.base import TaskResult
from magentic_one_helper import generate_session_name
import aisearch
import logging

from datetime import datetime, timedelta 
from schemas import AutoGenMessage
from typing import List
import time

print("Starting the server...")
#print(f'AZURE_OPENAI_ENDPOINT:{os.getenv("AZURE_OPENAI_ENDPOINT")}')
#print(f'COSMOS_DB_URI:{os.getenv("COSMOS_DB_URI")}')
#print(f'AZURE_SEARCH_SERVICE_ENDPOINT:{os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")}')

session_data = {}
MAGENTIC_ONE_DEFAULT_AGENTS = [
            {
            "input_key":"0001",
            "type":"MagenticOne",
            "name":"Coder",
            "system_message":"",
            "description":"",
            "icon":"👨‍💻"
            },
            {
            "input_key":"0002",
            "type":"MagenticOne",
            "name":"Executor",
            "system_message":"",
            "description":"",
            "icon":"💻"
            },
            {
            "input_key":"0003",
            "type":"MagenticOne",
            "name":"FileSurfer",
            "system_message":"",
            "description":"",
            "icon":"📂"
            },
            {
            "input_key":"0004",
            "type":"MagenticOne",
            "name":"WebSurfer",
            "system_message":"",
            "description":"",
            "icon":"🏄‍♂️"
            },
            ]

DEFAULT_SYS_PROMPT_MESSAGE_DECORATOR_ORCHESTRATOR = (
        "You are a formatting engine for an AI orchestrator. "
        "Clean and standardize the message for end-user display. Keep only useful content. "
        "Rules:\n"
        "1. If there is a plan with steps, output them as bullet points (- ). Single level only.\n"
        "2. Preserve existing markdown code fences.\n"
        "3. Bold any explicit tool invocation lines (e.g., lines starting with 'Tool:' or containing 'calling tool').\n"
        "4. Remove redundant apologies or meta commentary.\n"
        "5. Do not invent new steps not present in the original.\n"
        "6. Do not invent or generate any new content like code or steps.\n"
        "7. Plan is the main section make it H2, other section make collapsible and collapsed by default.\n"
        "8. Use icons.\n"
    )

DEFAULT_SYS_PROMPT_MESSAGE_DECORATOR_WEBSURFER = (
        "You are a formatting engine for an AI orchestrator. "
        "Clean and standardize the message for end-user display. Keep only useful content. "
        "Rules:\n"
        "1. Summarize the content in a concise manner keep it brief.\n"
    )
# Lifespan handler for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code: initialize database and configure logging
    # app.state.db = None
    app.state.db = CosmosDB()
    logging.basicConfig(level=logging.WARNING,
                        format='%(levelname)s: %(asctime)s - %(message)s')
    print("Database initialized.")
    # Initialize and cache OpenAI client (best-effort)
    app.state.openai_client = None
    try:
        app.state.openai_client = await get_openai_client()
        print("OpenAI client cached.")
    except Exception as e:
        print(f"Warning: Failed to initialize OpenAI client at startup: {e}")
    yield
    # Shutdown code (optional)
    # Cleanup database connection
    app.state.db = None
    app.state.openai_client = None

app = FastAPI(lifespan=lifespan)

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Azure AD Authentication (Mocked for example)
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    tokenUrl="https://login.microsoftonline.com/common/oauth2/v2.0/token"
)

async def validate_tokenx(token: str = Depends(oauth2_scheme)):
    # In production, implement proper token validation
    print("Token:", token)
    return {"sub": "user123", "name": "Test User"}  # Mocked user data

async def validate_token(token: str = None):
    # In production, implement proper token validation
    print("Token:", token)
    return {"sub": "user123", "name": "Test User"}  # Mocked user data

from openai import AsyncAzureOpenAI

# Azure OpenAI Client
async def get_openai_client():
    azure_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        azure_credential, "https://cognitiveservices.azure.com/.default"
    )
    
    return AsyncAzureOpenAI(
        api_version="2025-03-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        # azure_endpoint="https://aoai-eastus-mma-cdn.openai.azure.com/",
        azure_ad_token_provider=token_provider
    )


def write_log(path, log_entry):
    # check if the file exists if not create it
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("")
    # append the log entry to a file
    with open(path, "a") as f:
        try:
            f.write(f"{json.dumps(log_entry)}\n")
        except Exception as e:
            # TODO: better handling of the error
            log_entry["content"] = f"Error writing log entry: {str(e)}"
            f.write(f"{json.dumps(log_entry)}\n")



def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get_agent_icon(agent_name) -> str:
    if agent_name == "MagenticOneOrchestrator":
        agent_icon = "🎻"
    elif agent_name == "WebSurfer":
        agent_icon = "🏄‍♂️"
    elif agent_name == "Coder":
        agent_icon = "👨‍💻"
    elif agent_name == "FileSurfer":
        agent_icon = "📂"
    elif agent_name == "Executor":
        agent_icon = "💻"
    elif agent_name == "user":
        agent_icon = "👤"
    else:
        agent_icon = "🤖"
    return agent_icon

def orchestrator_formatting_enabled() -> bool:
    """Feature flag for orchestrator formatting (default ON)."""
    val = os.getenv("ORCHESTRATOR_FORMAT_ENABLE", "true").lower()
    return val in ("1", "true", "yes", "on")

async def formatMessage(raw_content: str, system_prompt: str) -> str:
    """Format MagenticOneOrchestrator messages using Azure OpenAI.

    This function sends the raw orchestrator content to the model with a
    focused system prompt that normalizes and improves readability.

    Responsibilities (initial version):
      - Trim excessive whitespace
      - Preserve code blocks
      - Convert numbered or multi-line plan steps into single-level bullet points
      - Highlight tool calls (lines starting with Tool: or similar) using bold
      - Keep response concise (< ~500 tokens target)

    If any exception occurs, the original raw content (stringified) is returned
    so logging/streaming never fails.
    """
    try:
        logger = logging.getLogger("formatter.orchestrator")
        # Basic input metrics
        input_preview = None
        try:
            if raw_content is not None:
                _text = raw_content if isinstance(raw_content, str) else str(raw_content)
                input_preview = (_text[:240] + "…") if len(_text) > 240 else _text
        except Exception:
            pass
        logger.debug("Formatter invoked", extra={
            "event": "start",
            "input_preview": input_preview,
        })
        if raw_content is None:
            return ""
        # Ensure we operate on string
        raw_text = raw_content if isinstance(raw_content, str) else str(raw_content)

        # Feature flag check
        if not orchestrator_formatting_enabled():
            logger.debug("Formatter disabled via feature flag", extra={"event": "flag_disabled"})
            return raw_text

        # Reuse cached client if available else create on-demand
        client = getattr(app.state, "openai_client", None)
        if client is None:
            logger.warning("OpenAI client not initialized; skipping formatting.", extra={
                "event": "client_missing"
            })
            return raw_text + "\n\n[Formatter note: client not initialized; raw output shown.]"
        else:
            logger.debug("Using cached OpenAI client", extra={"event": "client_cached"})

        # Use Chat Completions API (deprecated Responses removal)
        logger.debug("Calling chat.completions.create", extra={
            "event": "api_call_start",
            "api": "chat.completions.create"
        })
        try:
            chat_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text},
                ],
                max_tokens=1200,
                temperature=0.2,
            )
        except Exception as api_err:
            logger.error("Chat completion API exception", extra={
                "event": "api_call_error",
                "api": "chat.completions.create",
                "error": str(api_err)
            })
            return raw_text  # Fail open – return original content

        formatted = ""
        try:
            if getattr(chat_response, "choices", None):
                # Concatenate all non-empty choice message contents (usually first only)
                parts = []
                for ch in chat_response.choices:  # type: ignore[attr-defined]
                    msg = getattr(ch, "message", None)
                    if msg and getattr(msg, "content", None):
                        parts.append(msg.content)
                formatted = "\n".join(p.strip() for p in parts if p and p.strip()).strip()
        except Exception as parse_err:
            logger.warning("Failed parsing chat completion response; using raw text.", extra={
                "event": "parse_fallback",
                "error": str(parse_err)
            })
            return raw_text

        if not formatted:
            logger.info("Chat completion returned empty content; using raw text.", extra={
                "event": "empty_output"
            })
            return raw_text
        logger.debug("API call success", extra={
            "event": "api_call_success",
            "api": "chat.completions.create",
            "output_chars": len(formatted)
        })
        return formatted
    except Exception as e:
        logging.getLogger("formatter.orchestrator").error("Formatter exception", extra={
            "event": "exception",
            "error": str(e)
        })
        return f"{raw_content if isinstance(raw_content, str) else str(raw_content)}\n\n[Formatting error: {e}]"


# ----------------------------- CSV helpers -----------------------------
def _markdown_table_from_csv_rows(
    rows: list[list[str]],
    number_of_rows: int | None = None,
) -> str | None:
    """Convert parsed CSV rows to a Markdown table string.

    Parameters
    ----------
    rows : list[list[str]]
        Full CSV content split into rows (each row is list of columns). First row is assumed header.
    number_of_rows : int | None, optional
        If provided, only the first N data rows (after the header) are included in the table.
        Use None (default) to include all data rows. Values <= 0 produce a table with only headers.

    Returns
    -------
    str | None
        Markdown table or None if the data is not tabular (e.g. fewer than 2 columns).
    """


    if not rows or len(rows[0]) <= 1:
        return None
    headers = rows[0]
    data_rows = rows[1:]

    prefix_text = f"\n> Showing first {number_of_rows} from {len(data_rows)} rows of data:\n\n" if number_of_rows is not None else ""
    
    if number_of_rows is not None:
        if number_of_rows < 0:
            number_of_rows = 0
        data_rows = data_rows[: number_of_rows]
    md_lines: list[str] = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for r in data_rows:
        if len(r) < len(headers):
            r = r + ["" for _ in range(len(headers) - len(r))]
        elif len(r) > len(headers):
            r = r[: len(headers)]
        md_lines.append("| " + " | ".join(r) + " |")
    return prefix_text + "\n".join(md_lines)


def _decorate_content(content: str) -> str:
    """Decorate content by:
    1. Attempting to parse as JSON list with CSV payload under items' 'text'.
    2. If CSV detected, convert to Markdown table; replace original content with table.
    3. Append suffix (idempotently when decorate_once=True).
    """
    original = content
    transformed = content
    # Attempt JSON -> CSV -> Markdown transformation
    try:
        import json, csv, io
        parsed = json.loads(content)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            # Collect all 'text' fields from items with type 'text'
            texts: list[str] = []
            for item in parsed:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    texts.append(item["text"])
            if texts:
                # Concatenate (some providers might split) then process as CSV
                csv_blob = "\n".join(texts)
                # Strip BOM if present
                if csv_blob.startswith("\ufeff"):
                    csv_blob = csv_blob.lstrip("\ufeff")
                # Heuristic: must contain at least one comma and one newline to be CSV
                if "," in csv_blob and "\n" in csv_blob:
                    reader = csv.reader(io.StringIO(csv_blob))
                    rows = [row for row in reader if row]
                    table = _markdown_table_from_csv_rows(rows, 5)
                    if table:
                        transformed = table
    except json.JSONDecodeError:
        # Not JSON; leave content unchanged
        # transformed = original

        import json
        from json.decoder import JSONDecoder
        from typing import Iterator, List, Any

        # # Raw concatenated JSON string (two arrays) – kept exactly as received.
        # RAW = '[{"type": "text", "text": "\\ufeffTimestamp,EquipmentID,Temperature (\\u00b0C),Vibration (mm/s),Pressure (bar),RunningHours\\n2024-04-01 08:00:00,COMP-001,78.0,3.20,12.00,1500.0\\n2024-04-01 08:05:00,COMP-001,78.2,3.22,12.00,1500.1\\n2024-04-01 08:10:00,COMP-001,78.4,3.24,12.00,1500.2\\n2024-04-01 08:15:00,COMP-001,78.6,3.26,12.01,1500.3\\n2024-04-01 08:20:00,COMP-001,78.8,3.28,12.01,1500.4\\n2024-04-01 08:25:00,COMP-001,79.0,3.30,12.01,1500.5\\n2024-04-01 08:30:00,COMP-001,79.2,3.32,12.02,1500.6\\n2024-04-01 08:35:00,COMP-001,79.4,3.34,12.02,1500.7\\n2024-04-01 08:40:00,COMP-001,79.6,3.36,12.02,1500.8\\n2024-04-01 08:45:00,COMP-001,79.8,3.38,12.03,1500.9\\n2024-04-01 08:50:00,COMP-001,80.0,3.40,12.03,1501.0\\n2024-04-01 08:55:00,COMP-001,80.0,3.40,12.03,1501.1\\n2024-04-01 09:00:00,COMP-001,80.1,3.41,12.03,1501.2\\n2024-04-01 09:05:00,COMP-001,80.2,3.42,12.03,1501.3\\n2024-04-01 09:10:00,COMP-001,80.3,3.43,12.04,1501.4\\n2024-04-01 09:15:00,COMP-001,88.0,4.80,11.80,1501.5\\n2024-04-01 09:20:00,COMP-001,88.5,4.85,11.79,1501.6\\n2024-04-01 09:25:00,COMP-001,89.0,4.90,11.78,1501.7\\n2024-04-01 09:30:00,COMP-001,89.2,4.92,11.78,1501.8\\n2024-04-01 09:35:00,COMP-001,89.5,4.95,11.77,1501.9\\n2024-04-01 09:40:00,COMP-001,89.7,4.98,11.77,1502.0\\n2024-04-01 09:45:00,COMP-001,90.0,5.00,11.76,1502.1\\n2024-04-01 09:50:00,COMP-001,90.2,5.02,11.76,1502.2\\n2024-04-01 09:55:00,COMP-001,90.5,5.05,11.75,1502.3\\n2024-04-01 10:00:00,COMP-001,90.7,5.08,11.75,1502.4\\n2024-04-01 10:05:00,COMP-001,88.0,4.20,12.00,1502.5\\n2024-04-01 10:10:00,COMP-001,86.0,3.90,12.02,1502.6\\n2024-04-01 10:15:00,COMP-001,84.0,3.70,12.03,1502.7\\n2024-04-01 10:20:00,COMP-001,82.0,3.55,12.03,1502.8\\n2024-04-01 10:25:00,COMP-001,81.0,3.50,12.04,1502.9\\n2024-04-01 10:30:00,COMP-001,80.5,3.48,12.04,1503.0\\n2024-04-01 10:35:00,COMP-001,80.3,3.46,12.04,1503.1\\n2024-04-01 10:40:00,COMP-001,80.2,3.45,12.04,1503.2\\n2024-04-01 10:45:00,COMP-001,80.1,3.44,12.05,1503.3\\n2024-04-01 10:50:00,COMP-001,80.0,3.43,12.05,1503.4\\n2024-04-01 10:55:00,COMP-001,79.9,3.42,12.05,1503.5\\n2024-04-01 11:00:00,COMP-001,79.8,3.41,12.05,1503.6\\n2024-04-01 11:05:00,COMP-001,79.7,3.40,12.05,1503.7\\n2024-04-01 11:10:00,COMP-001,79.6,3.39,12.06,1503.8\\n2024-04-01 11:15:00,COMP-001,79.5,3.38,12.06,1503.9\\n2024-04-01 11:20:00,COMP-001,79.4,3.37,12.06,1504.0\\n2024-04-01 11:25:00,COMP-001,79.3,3.36,12.06,1504.1\\n2024-04-01 11:30:00,COMP-001,79.2,3.35,12.06,1504.2\\n2024-04-01 11:35:00,COMP-001,79.1,3.34,12.07,1504.3\\n2024-04-01 11:40:00,COMP-001,79.0,3.33,12.07,1504.4\\n2024-04-01 11:45:00,COMP-001,78.9,3.32,12.07,1504.5\\n2024-04-01 11:50:00,COMP-001,78.8,3.31,12.07,1504.6\\n2024-04-01 11:55:00,COMP-001,78.7,3.30,12.07,1504.7\\n2024-04-01 12:00:00,COMP-001,78.6,3.29,12.08,1504.8\\n2024-04-01 12:05:00,COMP-001,78.5,3.28,12.08,1504.9", "annotations": null}]\n[{"type": "text", "text": "\\ufeffMaintenanceDate,EquipmentID,MaintenanceType,Description,Duration (hrs),Comments\\n2024-03-01,COMP-001,Preventive Repair,Replaced compressor bearings and adjusted belt tension,3.0,Noted slight vibration increase pre-repair\\n2024-03-03,COMP-001,Calibration,Calibrated temperature and pressure sensors per vendor guidelines,1.5,Temperature readings marginally high\\n2024-03-05,COMP-001,Inspection,Visual inspection and ultrasonic testing of compressor casing,2.0,Minor wear observed on mounting brackets\\n2024-03-07,COMP-001,Lubrication,Performed complete lubrication renewal of rotating components,1.0,Lubricant viscosity within specification post-service\\n2024-03-09,COMP-001,Preventive Repair,Replaced worn-out seals on compressor inlet,2.5,Leak detected during routine check\\n2024-03-11,COMP-001,Software Update,Updated data acquisition software to version 4.2 as per Emerson bulletin,1.0,Improved sensor data accuracy observed\\n2024-03-13,COMP-001,Inspection,Infrared and vibration analysis of compressor motor,2.0,Temperature anomaly noted on infrared scan\\n2024-03-15,COMP-001,Calibration,Recalibrated vibration sensors and verified firmware update,1.5,Minor drift detected in baseline readings\\n2024-03-17,COMP-001,Preventive Repair,Replaced compressor oil filter and performed oil analysis,2.0,Oil analysis indicated slight contamination\\n2024-03-19,COMP-001,Inspection,Ultrasonic inspection of compressor drive system,2.5,No structural issues detected\\n2024-03-21,COMP-001,Lubrication,Applied high-performance lubricant to compressor gears,1.0,Lubricant level optimized\\n2024-03-23,COMP-001,Preventive Repair,Replaced worn bearing adapter plates,3.0,Vibration levels reduced post-repair\\n2024-03-25,COMP-001,Calibration,Calibrated pressure transducer on compressor discharge,1.5,Pressure readings now within acceptable range\\n2024-03-27,COMP-001,Inspection,Visual and thermal inspection of compressor base and mounts,2.0,Minor thermal hotspots observed\\n2024-03-29,COMP-001,Preventive Repair,Adjusted compressor belt alignment and tension,2.5,Post-adjustment vibration levels satisfactory\\n2024-03-31,COMP-001,Software Update,Updated sensor integration module per Emerson guidelines,1.0,Data acquisition improved\\n2024-04-02,COMP-001,Inspection,Comprehensive system diagnostic using vibration and thermal analysis,2.5,Anomalies noted; further investigation required\\n2024-04-04,COMP-001,Lubrication,Replenished compressor hydraulic fluid and checked leak points,1.0,Fluid levels optimal\\n2024-04-06,COMP-001,Preventive Repair,Replaced compressor inlet valve seals due to leak,2.0,Leak eliminated post-repair\\n2024-04-08,COMP-001,Calibration,Recalibrated all sensor arrays on the compressor,1.5,Baseline reset completed successfully\\n2024-04-10,COMP-001,Inspection,Conducted detailed ultrasonic test on compressor casing integrity,2.0,No further corrosion detected\\n2024-04-12,COMP-001,Preventive Repair,Replaced aging sensor cables and connectors,1.5,Intermittent signal drop eliminated\\n2024-04-14,COMP-001,Software Update,Installed patch for predictive maintenance algorithm per Emerson guidelines,1.0,Algorithm performance improved\\n2024-04-16,COMP-001,Inspection,Visual inspection of compressor skid and support structures,2.0,Minor abrasions noted; no immediate risk\\n2024-04-18,COMP-001,Lubrication,Performed scheduled lubrication of compressor bearings,1.0,No issues post-lubrication\\n2024-04-20,COMP-001,Preventive Repair,Replaced compressor drive motor brushes due to wear,2.5,Performance improved post-repair\\n2024-04-22,COMP-001,Calibration,Calibrated temperature sensors after repair work,1.5,Readings now stable\\n2024-04-24,COMP-001,Inspection,Conducted infrared thermography on compressor housing,2.0,Identified cooling inefficiency; flagged for monitoring\\n2024-04-26,COMP-001,Preventive Repair,Adjusted compressor valve timings and replaced worn gaskets,3.0,Performance improved significantly\\n2024-04-28,COMP-001,Inspection,Detailed vibration analysis during startup revealed high anomaly,2.5,Anomaly correlates with sensor spike period\\n2024-04-30,COMP-001,Lubrication,Performed lubrication top-up and oil analysis,1.0,Oil quality remains within limits\\n2024-05-02,COMP-001,Preventive Repair,Replaced damaged components on compressor discharge side,2.0,Pressure stability improved\\n2024-05-04,COMP-001,Calibration,Calibrated all measurement devices after routine maintenance,1.5,All sensor readings normalized\\n2024-05-06,COMP-001,Inspection,Visual and acoustic inspection during operation,2.0,No unusual noises detected\\n2024-05-08,COMP-001,Preventive Repair,Adjusted cooling system and cleaned heat exchangers,2.5,Cooling performance enhanced\\n2024-05-10,COMP-001,Software Update,Implemented Emerson-recommended update for diagnostic software,1.0,Real-time analytics now more precise\\n2024-05-12,COMP-001,Inspection,Conducted full operational test with vibration and pressure monitoring,2.0,Test results within thresholds\\n2024-05-14,COMP-001,Lubrication,Replaced lubricant with high-temperature resistant formula,1.0,Temperature stability slightly improved\\n2024-05-16,COMP-001,Preventive Repair,Replaced aging compressor seals and gaskets,2.5,Leakage eliminated post-repair\\n2024-05-18,COMP-001,Calibration,Calibrated vibration sensor module after component replacement,1.5,Vibration baseline updated\\n2024-05-20,COMP-001,Inspection,Performed detailed ultrasonic inspection of compressor bearings,2.0,Bearing condition marginal; further monitoring required\\n2024-05-22,COMP-001,Preventive Repair,Realigned compressor rotor and adjusted shaft balance,3.0,Vibration levels significantly reduced\\n2024-05-24,COMP-001,Software Update,Updated firmware on pressure transducers per new guidelines,1.0,Pressure consistency improved\\n2024-05-26,COMP-001,Inspection,Comprehensive diagnostic test on compressor performance,2.5,Minor thermal anomalies noted; recommend continued monitoring\\n2024-05-28,COMP-001,Lubrication,Performed lubrication of compressor drive and rechecked sensor outputs,1.0,No further issues detected\\n2024-05-30,COMP-001,Preventive Repair,Replaced worn compressor motor components,2.0,Post-repair performance normal\\n2024-06-01,COMP-001,Inspection,Final operational test and certification after series of repairs,2.5,Compressor now meets all performance criteria", "annotations": null}]'


        def parse_concatenated_json(doc: str) -> List[Any]:
            """Parse 1..N concatenated JSON values from a single string.

            Skips leading whitespace between values and returns each top-level JSON
            value in order. Raises the original JSONDecodeError if any individual
            value is malformed.
            """
            decoder = JSONDecoder()
            idx = 0
            out: List[Any] = []
            n = len(doc)
            while idx < n:
                # Skip any whitespace between documents
                while idx < n and doc[idx].isspace():
                    idx += 1
                if idx >= n:
                    break
                obj, end = decoder.raw_decode(doc, idx)
                out.append(obj)
                idx = end
            return out


        def strip_bom(text: str) -> str:
            """Remove a leading UTF-8 BOM if present."""
            return text.lstrip('\ufeff')

        docs = parse_concatenated_json(original)
        print(f"Parsed {len(docs)} top-level JSON values")

        import csv, io
        tables: list[str] = []
        for i, doc in enumerate(docs, 1):
            if isinstance(doc, list) and doc and isinstance(doc[0], dict):
                texts: list[str] = []
                for item in doc:
                    if isinstance(item, dict) and isinstance(item.get('text'), str):
                        texts.append(item['text'])
                if not texts:
                    print(f"  Doc {i}: list with no text fields")
                    continue
                csv_blob = "\n".join(texts)
                if csv_blob.startswith('\ufeff'):
                    csv_blob = strip_bom(csv_blob)
                if ',' in csv_blob and '\n' in csv_blob:
                    reader = csv.reader(io.StringIO(csv_blob))
                    rows = [row for row in reader if row]
                    table = _markdown_table_from_csv_rows(rows, 5)
                    if table:
                        print(f"  Doc {i}: converted to Markdown table with {len(rows)-1} data rows")
                        tables.append(table)
                        continue
                print(f"  Doc {i}: list did not look like CSV (skipped)")
            else:
                print(f"  Doc {i}: type={type(doc).__name__} (not processed)")

        print(f"Generated {len(tables)} markdown table(s)")
        
        # for idx, tbl in enumerate(tables, 1):
        #     print(f"\n--- Markdown Table {idx} ---\n{tbl[:400]}{'...' if len(tbl) > 400 else ''}")

        transformed = "\n\n".join(tables) if tables else original



    except Exception as e:
        print(f"Error occurred during content transformation: {e}")
        # Swallow transformation errors silently; revert to original
        transformed = original

    return transformed


async def display_log_message(log_entry, logs_dir, session_id, user_id, conversation=None):
    _log_entry_json = log_entry
    _user_id = user_id
    
    _response = AutoGenMessage(
        time=get_current_time(),
        session_id=session_id,
        session_user=_user_id
        )

    # Check if the message is a TaskResult class
    if isinstance(_log_entry_json, TaskResult):
        _response.type = "TaskResult"
        _response.source = "TaskResult"
        _response.content = _log_entry_json.messages[-1].content
        _response.stop_reason = _log_entry_json.stop_reason
        app.state.db.store_conversation(_log_entry_json, _response, conversation)

    elif isinstance(_log_entry_json, MultiModalMessage):
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source
        if _log_entry_json.source == "WebSurfer" and orchestrator_formatting_enabled():
            _response.content = await formatMessage(_log_entry_json.content[0], DEFAULT_SYS_PROMPT_MESSAGE_DECORATOR_WEBSURFER)
        else:
            _response.content = _log_entry_json.content[0] # text without image
        _response.content_image = _log_entry_json.content[1].data_uri # TODO: base64 encoded image -> text / serialize

    elif isinstance(_log_entry_json, TextMessage):
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source
        # Base content assignment (may be overridden below for specific sources)
        _response.content = _log_entry_json.content
        # Special formatting for orchestrator messages
        if _log_entry_json.source == "MagenticOneOrchestrator" and orchestrator_formatting_enabled():
            _response.content = await formatMessage(_log_entry_json.content, DEFAULT_SYS_PROMPT_MESSAGE_DECORATOR_ORCHESTRATOR)
        # Custom logic for Executor with base64 image
        if _log_entry_json.source == "Executor":
            import ast
            import re
            content = _log_entry_json.content
            try:
                if isinstance(content, str) and "'type': 'image'" in content and "'base64_data':" in content:
                    pattern = r"\{[^{}]*'type': 'image'[^{}]*'base64_data':[^{}]*\}"
                    match = re.search(pattern, content)
                    if match:
                        img_dict_str = match.group(0)
                        img_dict = ast.literal_eval(img_dict_str)
                        if (
                            isinstance(img_dict, dict)
                            and img_dict.get('type') == 'image'
                            and img_dict.get('format') == 'png'
                            and 'base64_data' in img_dict
                        ):
                            _response.content_image = f"data:image/png;base64,{img_dict['base64_data']}"
                            # Remove the dict substring from the content
                            cleaned_content = content.replace(img_dict_str, "").strip()
                            _response.content = cleaned_content
            except Exception:
                pass

    elif isinstance(_log_entry_json, ToolCallExecutionEvent):
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source
        _response.content = _log_entry_json.content[0].content # tool execution

    elif isinstance(_log_entry_json, ToolCallRequestEvent):
        # _models_usage = _log_entry_json.models_usage
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source
        _response.content = _log_entry_json.content[0].arguments # tool execution

    elif isinstance(_log_entry_json, SelectSpeakerEvent):
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source
        _response.content = _log_entry_json.content[0]

    elif isinstance(_log_entry_json, ToolCallSummaryMessage):
        _response.type = _log_entry_json.type
        _response.source = _log_entry_json.source

        # Special handling for data_provider tool to decorate content -> convert CSV to Markdown table
        if (_log_entry_json.tool_calls[0].name == "data_provider"):
            _response.content = _decorate_content(_log_entry_json.content)
        else:
            _response.content = _log_entry_json.content

    else:
        _response.type = "N/A"
        _response.source = "N/A"
        _response.content = "Agents mumbling."

    _ = crud.save_message(
            id=None, # it is auto-generated
            user_id=_user_id,
            session_id=session_id,
            message=_response.to_json(),
            agents=None,
            run_mode_locally=None,
            timestamp=_response.time
        )

    return _response



# Azure Services Setup (Mocked for example)
blob_service_client = BlobServiceClient.from_connection_string(
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;" + \
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;" + \
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)

# Chat Endpoint
@app.post("/chat")
async def chat_endpoint(
    message: schemas.ChatMessageCreate,
    user: dict = Depends(validate_token)
):
    # ...existing code...
    mock_response = "This is a mock AI response (Markdown formatted)."
    # Log the user message.
    crud.save_message(
        user_id=user["sub"],
        session_id="session_direct",  # or generate a session id if needed
        message={"content": message.content, "role": "user"}
    )
    # Log the AI response message.
    response = {
        "time": get_current_time(),
        "type": "Muj",
        "source": "MagenticOneOrchestrator",
        "content": mock_response,
        "stop_reason": None,
        "models_usage": None,
        "content_image": None,
    }
    crud.save_message(
        user_id=user["sub"],
        session_id="session_direct",
        message=response
    )

    return Response(content=json.dumps(response), media_type="application/json")


# Chat Endpoint
@app.post("/start", response_model=schemas.ChatMessageResponse)
async def chat_endpoint(
    message: schemas.ChatMessageCreate,
    user: dict = Depends(validate_token)
):
    logger = logging.getLogger("chat_endpoint")
    logger.setLevel(logging.INFO)
    logger.info(f"Starting agent session with message: {message.content}")
    # print("User:", user["sub"])
    _user_id=message.user_id if message.user_id else user["sub"]
    # print("Provided user_id:", message.user_id)
    logger.info(f"User ID: {_user_id}")
    _agents = json.loads(message.agents) if message.agents else MAGENTIC_ONE_DEFAULT_AGENTS
    _session_id = generate_session_name()
    conversation = crud.save_message(
        id=uuid.uuid4(),
        user_id=_user_id,
        session_id=_session_id,
        message={"content": message.content, "role": "user"},
        agents=_agents,
        run_mode_locally=False,
        timestamp=get_current_time()
    )

    logger.info(f"Conversation saved with session_id: {_session_id} and user_id: {_user_id}")
    # Return session_id as the conversation identifier
    db_message = schemas.ChatMessageResponse(
        id=uuid.uuid4(),
        content=message.content,
        response=_session_id,
        timestamp="2021-01-01T00:00:00",
        user_id=_user_id,
        orm_mode=True
    )
    return db_message


# Streaming Chat Endpoint
@app.get("/chat-stream")
async def chat_stream(
    session_id: str = Query(...),
    user_id: str = Query(...),
    # db: Session = Depends(get_db),
    user: dict = Depends(validate_token)
):
    
   
    logger = logging.getLogger("chat_stream")
    logger.setLevel(logging.WARNING)
    logger.info(f"Chat stream started for session_id: {session_id} and user_id: {user_id}")
    # create folder for logs if not exists
    logs_dir="./logs"
    if not os.path.exists(logs_dir):    
        os.makedirs(logs_dir)

    # get the conversation from the database using user and session id
    conversation = crud.get_conversation(user_id, session_id)
    logger.info(f"Conversation retrieved: {conversation}")
    # get first message from the conversation
    first_message = conversation["messages"][0]
    # get the task from the first message as content
    task = first_message["content"]
    print("Task:", task)

    _run_locally = conversation["run_mode_locally"]
    _agents = conversation["agents"]


    #  Initialize the MagenticOne system with user_id
    magentic_one = MagenticOneHelper(logs_dir=logs_dir, save_screenshots=False, run_locally=_run_locally, user_id=user_id)
    logger.info(f"Initializing MagenticOne with agents: {len(_agents)} and session_id: {session_id} and user_id: {user_id}")
    await magentic_one.initialize(agents=_agents, session_id=session_id)
    logger.info(f"Initialized MagenticOne with agents: {len(_agents)} and session_id: {session_id} and user_id: {user_id}")

    stream, cancellation_token = magentic_one.main(task = task)
    logger.info(f"Stream and cancellation token created for task: {task}")


    async def event_generator(stream, conversation):

        async for log_entry in stream:
            json_response = await display_log_message(log_entry=log_entry, logs_dir=logs_dir, session_id=magentic_one.session_id, conversation=conversation, user_id=user_id)    
            yield f"data: {json.dumps(json_response.to_json())}\n\n"


    return StreamingResponse(event_generator(stream, conversation), media_type="text/event-stream")

@app.get("/stop")
async def stop(session_id: str = Query(...)):
    try:
        print("Stopping session:", session_id)
        cancellation_token = session_data[session_id].get("cancellation_token")
        if (cancellation_token):
            cancellation_token.cancel()
            return {"status": "success", "message": f"Session {session_id} cancelled successfully."}
        else:
            return {"status": "error", "message": "Cancellation token not found."}
    except Exception as e:
        print(f"Error stopping session {session_id}: {str(e)}")
        return {"status": "error", "message": f"Error stopping session: {str(e)}"}

# New endpoint to retrieve all conversations with pagination.
@app.post("/conversations")
async def list_all_conversations(
    request_data: dict,
    user: dict = Depends(validate_token)
    ):
    try:
        user_id = request_data.get("user_id")
        page = request_data.get("page", 1)
        page_size = request_data.get("page_size", 20)
        conversations = app.state.db.fetch_user_conversatons(
            user_id=None, 
            page=page, 
            page_size=page_size
        )
        return conversations
    except Exception as e:
        print(f"Error retrieving conversations: {str(e)}")
        return {"conversations": [], "total_count": 0, "page": 1, "total_pages": 1}

# New endpoint to retrieve conversations for the authenticated user.
@app.post("/conversations/user")
async def list_user_conversation(request_data: dict = None, user: dict = Depends(validate_token)):
    session_id = request_data.get("session_id") if request_data else None
    user_id = request_data.get("user_id") if request_data else None
    conversations = app.state.db.fetch_user_conversation(user_id, session_id=session_id)
    return conversations

@app.post("/conversations/delete")
async def delete_conversation(session_id: str = Query(...), user_id: str = Query(...), user: dict = Depends(validate_token)):
    logger = logging.getLogger("delete_conversation")
    logger.setLevel(logging.INFO)
    logger.info(f"Deleting conversation with session_id: {session_id} for user_id: {user_id}")
    try:
        # result = crud.delete_conversation(user["sub"], session_id)
        result = app.state.db.delete_user_conversation(user_id=user_id, session_id=session_id)
        if result:
            logger.info(f"Conversation {session_id} deleted successfully.")
            return {"status": "success", "message": f"Conversation {session_id} deleted successfully."}
        else:
            logger.warning(f"Conversation {session_id} not found.")
            return {"status": "error", "message": f"Conversation {session_id} not found."}
    except Exception as e:
        logger.error(f"Error deleting conversation {session_id}: {str(e)}")
        return {"status": "error", "message": f"Error deleting conversation: {str(e)}"}
    
@app.get("/health")
async def health_check():
    logger = logging.getLogger("health_check")
    logger.setLevel(logging.INFO)
    logger.info("Health check endpoint called")
    # print("Health check endpoint called")
    return {"status": "healthy"}

@app.post("/upload")
async def upload_files(indexName: str = Form(...), files: List[UploadFile] = File(...)):
    logger = logging.getLogger("upload_files")
    logger.setLevel(logging.INFO)
    logger.info(f"Received indexName: {indexName}")
    # print("Received indexName:", indexName)
    for file in files:
        # print("Uploading file:", file.filename)
        logger.info(f"Uploading file: {file.filename}")
    try:
        aisearch.process_upload_and_index(indexName, files)
        logger.info(f"Files processed and indexed successfully.")
    except Exception as err:
        logger.error(f"Error processing upload and index: {str(err)}")
        return {"status": "error", "message": str(err)}
    return {"status": "success", "filenames": [f.filename for f in files]}

from fastapi import HTTPException
from team_export import convert_team_for_download

@app.get("/teams")
async def get_teams_api():
    try:
        teams = app.state.db.get_teams()
        # teams= []
        return teams
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving teams: {str(e)}")

@app.get("/teams/{team_id}")
async def get_team_api(team_id: str):
    try:
        team = app.state.db.get_team(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        return team
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving team: {str(e)}")

@app.post("/teams/{team_id}")
async def download_team_api(team_id: str):
    """Download a single team definition as JSON.
    Returns the team object from the DB. The frontend will handle saving it as a file.
    """
    try:
        team = app.state.db.get_team(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        # Shape/filter the team representation for download
        return convert_team_for_download(team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving team: {str(e)}")

@app.post("/teams")
async def create_team_api(team: dict):
    try:
        team["agents"] = MAGENTIC_ONE_DEFAULT_AGENTS
        response = app.state.db.create_team(team)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating team: {str(e)}")

@app.put("/teams/{team_id}")
async def update_team_api(team_id: str, team: dict):
    logger = logging.getLogger("update_team_api")
    logger.info(f"Updating team with ID: {team_id} and data: {team}")
    try:
        response = app.state.db.update_team(team_id, team)
        if "error" in response:
            logger.error(f"Error updating team: {response['error']}")
            raise HTTPException(status_code=404, detail=response["error"])
        return response
    except Exception as e:
        logger.error(f"Error updating team: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating team: {str(e)}")

@app.delete("/teams/{team_id}")
async def delete_team_api(team_id: str):
    try:
        response = app.state.db.delete_team(team_id)
        if "error" in response:
            raise HTTPException(status_code=404, detail=response["error"])
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting team: {str(e)}")
    

@app.post("/inititalize-teams")
async def initialize_teams_api():
    try:
        # Initialize the teams in the database
        msg = app.state.db.initialize_teams()
        msg = "DUMMY: Teams initialized successfully."
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing teams: {str(e)}")

# New endpoint to retrieve conversation statistics (last 6 months, daily counts grouped by date and user)
@app.get("/conversations/stats")
async def conversation_stats():
    try:
        # Determine date range: last 6 months (approx. 180 days)
        end_dt = datetime.utcnow().date()
        start_dt = (end_dt - timedelta(days=180))
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        rows = app.state.db.fetch_conversation_stats(start_date=start_date, end_date=end_date)

        # Build summary
        total_runs = sum(r.get("count", 0) for r in rows)
        users = {r.get("user_id") for r in rows}
        # Response contract
        return {
            "start_date": start_date,
            "end_date": end_date,
            "buckets": rows,  # [{ user_id, date: 'YYYY-MM-DD', count }]
            "summary": {
                "total_runs": int(total_runs),
                "unique_users": len(users),
                "days": (end_dt - start_dt).days + 1,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")