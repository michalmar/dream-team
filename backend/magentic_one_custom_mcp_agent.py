import os
from typing import Any, AsyncGenerator, Iterable, List, Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage
from autogen_core import CancellationToken
from autogen_core.models import ChatCompletionClient
from autogen_ext.tools.mcp import (
    SseMcpToolAdapter,
    StdioServerParams,
    StdioMcpToolAdapter,
    SseServerParams,
)

# TODO add checks to user inputs to make sure it is a valid definition of custom agent
class MagenticOneCustomMCPAgent(AssistantAgent):
    """Custom MCP-enabled AssistantAgent with message decoration.

    This subclass augments the final emitted message (TextMessage / ToolCallSummaryMessage /
    StructuredMessage) by appending a configurable suffix. Streaming mode is supported by
    intercepting the final `Response` object in `on_messages_stream`.

    Parameters
    ----------
    message_suffix: str
        Text appended to the final response message content (only if the content is a string).
    decorate_once: bool
        If True (default) avoids double-appending when agent output is post-processed elsewhere.
    """

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        system_message: str,
        description: str,
        adapter: Iterable[Any],  # adapter / tool list provided by async factory method
        user_id: str | None = None,
        message_suffix: str = "",
        decorate_once: bool = True,
    ) -> None:
        super().__init__(
            name,
            model_client,
            description=description,
            system_message=system_message,
            tools=list(adapter),
        )
        self.user_id = user_id
        self._message_suffix = message_suffix
        self._decorate_once = decorate_once

    # ----------------------------- CSV helpers -----------------------------
    def _markdown_table_from_csv_rows(
        self,
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

    # ----------------------------- internal helpers -----------------------------
    def _decorate_content(self, content: str) -> str:
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
                        table = self._markdown_table_from_csv_rows(rows, 5)
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
                        table = self._markdown_table_from_csv_rows(rows, 5)
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

        # Append suffix if configured
        if self._message_suffix:
            if not (self._decorate_once and transformed.endswith(self._message_suffix)):
                transformed = transformed + self._message_suffix
        return transformed


    def _decorate_response(self, response: Response) -> None:
        """Mutate the response's final chat message content if it is a string.

        We intentionally do not touch non-string payloads (e.g. binary / images) or
        messages without a `content` attribute.
        """
        chat_msg = response.chat_message  # type: ignore[attr-defined]
        if chat_msg is None:
            return
        
        # only decorate if from data_provider tool -> CSV file, conversion to markdown table
        if hasattr(chat_msg, "tool_calls") and isinstance(getattr(chat_msg, "tool_calls"), list):
            if chat_msg.tool_calls[0].name == "data_provider":
                # Many message types (TextMessage, ToolCallSummaryMessage, StructuredMessage) expose `content`.
                if hasattr(chat_msg, "content") and isinstance(getattr(chat_msg, "content"), str):
                    new_content = self._decorate_content(getattr(chat_msg, "content"))
                    setattr(chat_msg, "content", new_content)
                return
            return

    # ----------------------------- overrides -----------------------------
    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:  # type: ignore[override]
        response = await super().on_messages(messages, cancellation_token)
        self._decorate_response(response)
        return response

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Any, None]:  # type: ignore[override]
        async for item in super().on_messages_stream(messages, cancellation_token):
            if isinstance(item, Response):
                # self._decorate_response(item)
                yield item

    # ----------------------------- factory -----------------------------
    @classmethod
    async def create(
        cls,
        name: str,
        model_client: ChatCompletionClient,
        system_message: str,
        description: str,
        user_id: str | None = None,
        message_suffix: str = "",
        decorate_once: bool = True,
    ) -> "MagenticOneCustomMCPAgent":
        """Asynchronous factory building MCP tool adapters then returning the agent.

        Environment variables expected:
            MCP_SERVER_URI       Base URI of the MCP server (without trailing /sse)
            MCP_SERVER_API_KEY   API key (sent as x-api-key header)
        """

        # Example for using a local stdio server (kept for reference):
        # server_params = StdioServerParams(
        #     command="python",
        #     args=["mcp_math_server.py"],
        # )
        # adapter_addition = await StdioMcpToolAdapter.from_server_params(server_params, "add")

        print("Creating MagenticOneCustomMCPAgent...")
        print("MCP_SERVER_URI:", os.environ.get("MCP_SERVER_URI"))
        # NOTE: Avoid printing API key contents in production logs.

        base_uri = os.environ.get("MCP_SERVER_URI")
        if not base_uri:
            raise ValueError("Environment variable MCP_SERVER_URI is required to create MagenticOneCustomMCPAgent")
        api_key = os.environ.get("MCP_SERVER_API_KEY")
        if not api_key:
            raise ValueError("Environment variable MCP_SERVER_API_KEY is required to create MagenticOneCustomMCPAgent")

        server_params = SseServerParams(
            url=base_uri.rstrip("/") + "/sse",
            headers={"x-api-key": api_key},
        )

        # Acquire MCP tools concurrently (could be optimized with asyncio.gather if many tools)
        adapter_data_provider = await SseMcpToolAdapter.from_server_params(server_params, "data_provider")
        adapter_data_list_tables = await SseMcpToolAdapter.from_server_params(server_params, "show_tables")
        adapter_mailer = await SseMcpToolAdapter.from_server_params(server_params, "mailer")

        return cls(
            name,
            model_client,
            system_message,
            description,
            [adapter_data_provider, adapter_data_list_tables, adapter_mailer],
            user_id=user_id,
            message_suffix=message_suffix,
            decorate_once=decorate_once,
        )