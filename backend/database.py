import os
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from typing import Optional, List, Dict

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import MultiModalMessage, TextMessage, ToolCallExecutionEvent, ToolCallRequestEvent, SelectSpeakerEvent, ToolCallSummaryMessage

from schemas import AutoGenMessage
import uuid
from dotenv import load_dotenv
import time
import glob
import json

class CosmosDB:
    def __init__(self):
        load_dotenv("./.env", override=True)
        # Get Cosmos DB account details
        COSMOS_DB_URI = os.getenv("COSMOS_DB_URI", "https://YOURDB.documents.azure.com:443/")
        COSMOS_DB_DATABASE = os.getenv("COSMOS_DB_DATABASE", "ag_demo")
        credential = DefaultAzureCredential()
        self.client = CosmosClient(COSMOS_DB_URI, credential=credential)
        self.database = self.client.create_database_if_not_exists(id=COSMOS_DB_DATABASE)
        self.containers = {}
        # Pre-initialize default containers
        self.containers["ag_demo"] = self.database.create_container_if_not_exists(
            id="ag_demo",
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400
        )
        self.containers["agent_teams"] = self.database.create_container_if_not_exists(
            id="agent_teams",
            partition_key=PartitionKey(path="/team_id"),
            offer_throughput=400
        )
    
    def get_container(self, container_name: str = "ag_demo"):
        if container_name in self.containers:
            return self.containers[container_name]
        container = self.database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400
        )
        self.containers[container_name] = container
        return container
    
    def format_message(self, _log_entry_json):
        _response = AutoGenMessage(
            time="N/A",
            session_id="session_id",
            session_user="session_user",
        )
        # ...existing code...
        if isinstance(_log_entry_json, TaskResult):
            _response.type = "TaskResult"
            _response.source = "TaskResult"
            _response.content = _log_entry_json.messages[-1].content
            _response.stop_reason = _log_entry_json.stop_reason
        elif isinstance(_log_entry_json, MultiModalMessage):
            _response.type = _log_entry_json.type
            _response.source = _log_entry_json.source
            _response.content = _log_entry_json.content[0]
            _response.content_image = _log_entry_json.content[1].data_uri
        elif isinstance(_log_entry_json, TextMessage):
            _response.type = _log_entry_json.type
            _response.source = _log_entry_json.source
            _response.content = _log_entry_json.content
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
            _response.content = _log_entry_json.content[0].content
        elif isinstance(_log_entry_json, ToolCallRequestEvent):
            _response.type = _log_entry_json.type
            _response.source = _log_entry_json.source
            _response.content = _log_entry_json.content[0].arguments
        elif isinstance(_log_entry_json, SelectSpeakerEvent):
            _response.type = _log_entry_json.type
            _response.source = _log_entry_json.source
            _response.content = _log_entry_json.content[0]
        elif isinstance(_log_entry_json, ToolCallSummaryMessage):
            _response.type = _log_entry_json.type
            _response.source = _log_entry_json.source
            _response.content = _log_entry_json.content
        else:
            _response.type = "N/A"
            _response.source = "N/A"
            _response.content = "Agents mumbling."
        return _response

    def store_conversation(self, conversation: TaskResult, conversation_details: AutoGenMessage, conversation_dict: dict):
        _messsages = []
        for message in conversation.messages:
            _m = self.format_message(message)
            _messsages.append(_m.to_json())
        conversation_document_item = {
            "id": str(uuid.uuid4()),
            "user_id": conversation_details.session_user,
            "session_id": conversation_details.session_id,
            "messages": _messsages, 
            "agents": conversation_dict["agents"],
            "run_mode_locally": False,
            "timestamp": conversation_details.time,
        }
        container = self.get_container("ag_demo")
        response = container.create_item(body=conversation_document_item)
        return response

    def fetch_user_conversatons(self, user_id: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict:
        container = self.get_container("ag_demo")
        
        # First, get the total count
        if user_id is None:
            count_query = "SELECT VALUE COUNT(1) FROM c"
            count_parameters = []
        else:
            count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.user_id = @userId"
            count_parameters = [{"name": "@userId", "value": user_id}]
            
        count_results = list(container.query_items(
            query=count_query, 
            parameters=count_parameters, 
            enable_cross_partition_query=True
        ))
        total_count = count_results[0] if count_results else 0
        
        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        # Calculate skip for pagination
        skip = (page - 1) * page_size
        
        # Get paginated results
        if user_id is None:
            query = "SELECT c.user_id, c.session_id, c.timestamp FROM c ORDER BY c.timestamp DESC OFFSET @skip LIMIT @limit"
            parameters = [
                {"name": "@skip", "value": skip},
                {"name": "@limit", "value": page_size}
            ]
        else:
            query = "SELECT c.user_id, c.session_id, c.timestamp FROM c WHERE c.user_id = @userId ORDER BY c.timestamp DESC OFFSET @skip LIMIT @limit"
            parameters = [
                {"name": "@userId", "value": user_id},
                {"name": "@skip", "value": skip},
                {"name": "@limit", "value": page_size}
            ]
            
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        
        return {
            "conversations": items,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages
        }

    def fetch_user_conversation(self, user_id: str, session_id: str):
        container = self.get_container("ag_demo")
        query = "SELECT * FROM c WHERE c.user_id = @userId AND c.session_id = @sessionId"
        parameters = [
            {"name": "@userId", "value": user_id},
            {"name": "@sessionId", "value": session_id},
        ]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return items

    def delete_user_conversation(self, user_id: str, session_id: str):
        container = self.get_container("ag_demo")
        query = "SELECT * FROM c WHERE c.user_id = @userId AND c.session_id = @sessionId"
        parameters = [
            {"name": "@userId", "value": user_id},
            {"name": "@sessionId", "value": session_id},
        ]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if not items:
            return {"error": f"No conversation found with user_id {user_id} and session_id {session_id}."}
        conversation = items[0]
        response = container.delete_item(item=conversation["id"], partition_key=conversation["user_id"])
        return response

    def delete_user_all_conversations(self, user_id: str):
        container = self.get_container("ag_demo")
        query = "SELECT * FROM c WHERE c.user_id = @userId"
        parameters = [{"name": "@userId", "value": user_id}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if not items:
            return {"error": f"No conversation found with user_id {user_id}."}
        for item in items:
            container.delete_item(item=item["id"], partition_key=item["user_id"])
        return True

    def fetch_conversation_stats(self, start_date: str, end_date: str):
        """
        Returns daily counts of conversations for the given date range grouped by date (YYYY-MM-DD) and user.
        Expects documents to have string timestamp in format 'YYYY-MM-DD HH:MM:SS'.
        """
        container = self.get_container("ag_demo")
        # Fetch raw rows (no GROUP BY) and aggregate in Python to avoid cross-partition GROUP BY caveats
        query = (
            "SELECT c.user_id, SUBSTRING(c.timestamp, 0, 10) AS date "
            "FROM c "
            "WHERE SUBSTRING(c.timestamp, 0, 10) >= @startDate AND SUBSTRING(c.timestamp, 0, 10) <= @endDate"
        )
        parameters = [
            {"name": "@startDate", "value": start_date},
            {"name": "@endDate", "value": end_date},
        ]
        rows = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        # Aggregate in Python: {(user_id, date): count}
        counts = {}
        for r in rows:
            user_id = r.get("user_id")
            date = r.get("date")
            if not user_id or not date:
                continue
            key = (user_id, date)
            counts[key] = counts.get(key, 0) + 1

        # Convert to list of dicts like: {"user_id": ..., "date": "YYYY-MM-DD", "count": N}
        items = [
            {"user_id": k[0], "date": k[1], "count": v}
            for k, v in counts.items()
        ]
        # Optional: sort by date then user for stable ordering
        items.sort(key=lambda d: (d["date"], d["user_id"]))
        return items

    def create_team(self, team: dict):
        container = self.get_container("agent_teams")
        team_document = {
            "id": team["id"],
            "team_id": team["team_id"],
            "name": team["name"],
            "agents": team["agents"],
            "description": team.get("description"),
            "logo": team["logo"],
            "plan": team["plan"],
            "starting_tasks": team["starting_tasks"],
        }
        response = container.create_item(body=team_document)
        return response

    def get_teams(self):
        container = self.get_container("agent_teams")
        query = "SELECT * FROM c"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return items

    def get_team(self, team_id: str):
        container = self.get_container("agent_teams")
        query = "SELECT * FROM c WHERE c.team_id = @teamId"
        parameters = [{"name": "@teamId", "value": team_id}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return items[0] if items else None

    def update_team(self, team_id: str, team: dict):
        container = self.get_container("agent_teams")
        existing_team = self.get_team(team_id)
        if not existing_team:
            return {"error": "Team not found"}
        updated_team = {**existing_team, **team}
        response = container.replace_item(item=existing_team["id"], body=updated_team)
        return response

    def delete_team(self, team_id: str):
        container = self.get_container("agent_teams")
        existing_team = self.get_team(team_id)
        if not existing_team:
            return {"error": "Team not found"}
        response = container.delete_item(item=existing_team["id"], partition_key=existing_team["team_id"])
        return response

    def initialize_teams(self):
        teams_folder = os.path.join(os.path.dirname(__file__), "./data/teams-definitions")
        json_files = glob.glob(os.path.join(teams_folder, "*.json"))
        json_files.sort()
        print(f"Found {len(json_files)} JSON files in {teams_folder}.")
        created_items = 0
        for file_path in json_files:
            with open(file_path, "r") as f:
                team = json.load(f)
            response = self.create_team(team)
            print(f"Created team from {os.path.basename(file_path)}")
            created_items += 1
        print(f"Created {created_items}/{len(json_files)} items in the database.")
        return f"Successfully created {created_items} teams."
if __name__ == "__main__":
    db = CosmosDB()
    teams_folder = os.path.join(os.path.dirname(__file__), "./data/teams-definitions")
    json_files = glob.glob(os.path.join(teams_folder, "*.json"))
    json_files.sort()
    print(f"Found {len(json_files)} JSON files in {teams_folder}.")
    created_items = 0
    for file_path in json_files:
        with open(file_path, "r") as f:
            team = json.load(f)
        response = db.create_team(team)
        print(f"Created team from {os.path.basename(file_path)}")
        created_items += 1
    print(f"Created {created_items}/{len(json_files)} items in the database.")
    pass