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
                        if rows and len(rows[0]) > 1:
                            headers = rows[0]
                            data_rows = rows[1:]
                            # Build Markdown table
                            md_lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
                            for r in data_rows:
                                # Pad or trim row length to headers
                                if len(r) < len(headers):
                                    r = r + ["" for _ in range(len(headers) - len(r))]
                                elif len(r) > len(headers):
                                    r = r[: len(headers)]
                                md_lines.append("| " + " | ".join(r) + " |")
                            transformed = "\n".join(md_lines)
        except Exception:
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
                self._decorate_response(item)
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