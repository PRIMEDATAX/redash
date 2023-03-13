import datetime
import logging
import os
import time
from base64 import b64decode
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import httplib2
from cachetools import cached, TTLCache

from redash import settings
from redash.models import UserGroupMemberList, TableColumnPolicyTagMapping, QueryIdPolicyTagMapping
# from redash.models import User, TableColumnPolicyTagMapping, UserGroupMemberList
from redash.query_runner import *
from redash.settings import parse_boolean
from redash.utils import json_dumps, json_loads
from redash.utils.permission_denied_exception import PermissionDeniedException

logger = logging.getLogger(__name__)

try:

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from oauth2client.service_account import ServiceAccountCredentials

    enabled = True
except ImportError:
    enabled = False

ANNOTATE_QUERY = parse_boolean(os.environ.get("BIGQUERY_ANNOTATE_QUERY", "true"))

types_map = {
    "INTEGER": TYPE_INTEGER,
    "FLOAT": TYPE_FLOAT,
    "BOOLEAN": TYPE_BOOLEAN,
    "STRING": TYPE_STRING,
    "TIMESTAMP": TYPE_DATETIME,
}


def transform_cell(field_type, cell_value):
    if cell_value is None:
        return None
    if field_type == "INTEGER":
        return int(cell_value)
    elif field_type == "FLOAT":
        return float(cell_value)
    elif field_type == "BOOLEAN":
        return cell_value.lower() == "true"
    elif field_type == "TIMESTAMP":
        return datetime.datetime.fromtimestamp(float(cell_value))
    return cell_value


def transform_row(row, fields):
    row_data = {}

    for column_index, cell in enumerate(row["f"]):
        field = fields[column_index]
        if field.get("mode") == "REPEATED":
            cell_value = [
                transform_cell(field["type"], item["v"]) for item in cell["v"]
            ]
        else:
            cell_value = transform_cell(field["type"], cell["v"])

        row_data[field["name"]] = cell_value

    return row_data


def _load_key(filename):
    return Path(filename).read_text()


def _get_query_results(jobs, project_id, location, job_id, start_index):
    query_reply = jobs.getQueryResults(
        projectId=project_id, location=location, jobId=job_id, startIndex=start_index
    ).execute()
    logging.debug("query_reply %s", query_reply)
    if not query_reply["jobComplete"]:
        time.sleep(5)
        return _get_query_results(jobs, project_id, location, job_id, start_index)

    return query_reply


def _get_total_bytes_processed_for_resp(bq_response):
    # BigQuery hides the total bytes processed for queries to tables with row-level access controls.
    # For these queries the "totalBytesProcessed" field may not be defined in the response.
    return int(bq_response.get("totalBytesProcessed", "0"))


def _get_total_slots_for_resp(bq_response):
    logger.debug(bq_response)
    if "endTime" in bq_response:
        return int(bq_response.get("totalSlotMs")) / (int(bq_response.get("finalExecutionDurationMs")))
    else:
        return 0


class BigQuery(BaseSQLQueryRunner):
    should_annotate_query = ANNOTATE_QUERY
    noop_query = "SELECT 1"

    @classmethod
    def enabled(cls):
        return enabled

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "projectId": {"type": "string", "title": "Project ID"},
                "jsonKeyFile": {"type": "string", "title": "JSON Key File"},
                "totalMBytesProcessedLimit": {
                    "type": "number",
                    "title": "Scanned Data Limit (MB)",
                },
                "userDefinedFunctionResourceUri": {
                    "type": "string",
                    "title": "UDF Source URIs (i.e. gs://bucket/date_utils.js, gs://bucket/string_utils.js )",
                },
                "useStandardSql": {
                    "type": "boolean",
                    "title": "Use Standard SQL",
                    "default": True,
                },
                "location": {"type": "string", "title": "Processing Location"},
                "loadSchema": {"type": "boolean", "title": "Load Schema"},
                "jobTimeoutMillis": {"type": "number", "title": "Job timeout in milliseconds", "default": 1800000},
                "maximumBillingTier": {
                    "type": "number",
                    "title": "Maximum Billing Tier",
                },
            },
            "required": ["jsonKeyFile", "projectId"],
            "order": [
                "projectId",
                "jsonKeyFile",
                "loadSchema",
                "useStandardSql",
                "location",
                "totalMBytesProcessedLimit",
                "jobTimeoutMillis",
                "maximumBillingTier",
                "userDefinedFunctionResourceUri",
            ],
            "secret": ["jsonKeyFile"],
        }

    def _get_bigquery_service(self):
        scope = [
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/drive",
        ]

        key = json_loads(b64decode(self.configuration["jsonKeyFile"]))

        creds = ServiceAccountCredentials.from_json_keyfile_dict(key, scope)
        http = httplib2.Http(timeout=settings.BIGQUERY_HTTP_TIMEOUT)
        http = creds.authorize(http)

        return build("bigquery", "v2", http=http, cache_discovery=False)

    def _get_project_id(self):
        return self.configuration["projectId"]

    def _get_location(self):
        return self.configuration.get("location")

    def _get_total_bytes_processed(self, jobs, query):
        job_data = {"query": query, "dryRun": True}

        if self._get_location():
            job_data["location"] = self._get_location()

        if self.configuration.get("useStandardSql", False):
            job_data["useLegacySql"] = False

        response = jobs.query(projectId=self._get_project_id(), body=job_data).execute()
        return _get_total_bytes_processed_for_resp(response)

    def _get_job_data(self, query):
        job_data = {"configuration": {"query": {"query": query}}}

        if self._get_location():
            job_data["jobReference"] = {"location": self._get_location()}

        if self.configuration.get("useStandardSql", False):
            job_data["configuration"]["query"]["useLegacySql"] = False

        if self.configuration.get("userDefinedFunctionResourceUri"):
            resource_uris = self.configuration["userDefinedFunctionResourceUri"].split(
                ","
            )
            job_data["configuration"]["query"]["userDefinedFunctionResources"] = [
                {"resourceUri": resource_uri} for resource_uri in resource_uris
            ]

        if "maximumBillingTier" in self.configuration:
            job_data["configuration"]["query"][
                "maximumBillingTier"
            ] = self.configuration["maximumBillingTier"]

        if "jobTimeoutMillis" in self.configuration:
            job_data["configuration"]["jobTimeoutMs"] = self.configuration["jobTimeoutMillis"]

        job_data["configuration"]["query"]["useQueryCache"] = False
        job_data["configuration"]["query"]["priority"] = "BATCH"
        return job_data

    def _get_columns_used_in_query(self, query_plan):
        substeps = []
        for input in query_plan:
            for step in input["steps"]:
                if step["kind"] == 'READ':
                    for substep in step["substeps"]:
                        if 'FROM' in substep and not substep.startswith("FROM __"):
                            substeps.append(step["substeps"])

        results = {}
        for substep in substeps:
            table_name = substep[1].split(" ")[-1]
            if str(table_name) not in results:
                results[str(table_name)] = set()
            substep = substep[0].split(",")
            for column in substep:
                results[table_name].add(str(column.split(":")[-1]))
        return results

    @cached(cache=TTLCache(maxsize=3000, ttl=600))
    def _get_policy_tags(self) -> Dict[str, List[Tuple[str, str]]]:
        all_policy_tag_mappings: List[TableColumnPolicyTagMapping] = TableColumnPolicyTagMapping.get_all()
        grouped_map = defaultdict(list)
        for policy_tags in all_policy_tag_mappings:
            policy_tag_table_name = f"{policy_tags.project_id}.{policy_tags.dataset_id}.{policy_tags.table_name}"
            grouped_map[policy_tag_table_name].append((policy_tags.column_name, policy_tags.policy_tag))
        return grouped_map

    def _get_query_result(self, jobs, query, user):
        project_id = self._get_project_id()
        job_data = self._get_job_data(query)
        insert_response = jobs.insert(projectId=project_id, body=job_data).execute()
        self.current_job_id = insert_response["jobReference"]["jobId"]
        current_row = 0
        query_reply = _get_query_results(
            jobs,
            project_id=project_id,
            location=self._get_location(),
            job_id=self.current_job_id,
            start_index=current_row,
        )

        logger.debug("bigquery replied: %s", query_reply)

        job_stats = jobs.get(
            **{"projectId": project_id, "jobId": self.current_job_id, "location": self._get_location()}).execute()
        table_column_map: Dict[str, Set[str]] = self._get_columns_used_in_query(
            job_stats["statistics"]["query"]["queryPlan"])
        get_policy_tag_mapping: Dict[str, Tuple[str, str]] = self._get_policy_tags()
        policy_tags_accessed = self.get_policy_tags_in_query(get_policy_tag_mapping, table_column_map)

        self.update_query_policy_tags(policy_tags_accessed, query)

        self._check_for_policy_tags_in_query(policy_tags_accessed, user)

        rows = []

        while ("rows" in query_reply) and current_row < int(query_reply["totalRows"]):
            for row in query_reply["rows"]:
                rows.append(transform_row(row, query_reply["schema"]["fields"]))

            current_row += len(query_reply["rows"])

            query_result_request = {
                "projectId": project_id,
                "jobId": query_reply["jobReference"]["jobId"],
                "startIndex": current_row,
            }

            if self._get_location():
                query_result_request["location"] = self._get_location()

            query_reply = jobs.getQueryResults(**query_result_request).execute()

        columns = [
            {
                "name": f["name"],
                "friendly_name": f["name"],
                "type": "string"
                if f.get("mode") == "REPEATED"
                else types_map.get(f["type"], "string"),
            }
            for f in query_reply["schema"]["fields"]
        ]

        current_job_statistics = job_stats["statistics"]
        logger.debug(current_job_statistics)

        data = {
            "columns": columns,
            "rows": rows,
            "metadata": {"data_scanned": _get_total_bytes_processed_for_resp(query_reply),
                         "slots_used": _get_total_slots_for_resp(current_job_statistics)},
        }

        return data

    def _check_for_policy_tags_in_query(self, policy_tags_accessed, user):
        if policy_tags_accessed:
            # Check if user email has access
            access: List[str] = UserGroupMemberList.get_by_policy_name(policy_names=list(policy_tags_accessed.keys()),
                                                                       user_email=user.email)
            if len(access) != len(policy_tags_accessed):
                missing_access_policy_tags = set(policy_tags_accessed.keys()) - set(access)
                filtered_results: dict = {k: v for k, v in policy_tags_accessed.items() if
                                          k in missing_access_policy_tags}
                f = [f"Policy tag- {k}, Columns accessed- {v}" for k, v in filtered_results.items()]

                raise PermissionDeniedException(
                    "User does not have permission to query columns. \n{} ".format('\n'.join(f)))

    def update_query_policy_tags(self, policy_tags_accessed, query):
        query_hash = self.gen_query_hash(query)
        query_policy_tags = [QueryIdPolicyTagMapping(query_id=query_hash, policy_name=tag) for tag in
                             policy_tags_accessed.keys()]
        QueryIdPolicyTagMapping.update_table(query_hash, query_policy_tags)

    def get_policy_tags_in_query(self, get_policy_tag_mapping, table_column_map):
        policy_tags_accessed = defaultdict(set)
        for table_name, column_list in table_column_map.items():
            if table_name in get_policy_tag_mapping.keys():
                for column, tag in get_policy_tag_mapping[table_name]:
                    if column in column_list:
                        policy_tags_accessed[tag].add((table_name, column))
        return policy_tags_accessed

    def _get_project_datasets(self, project_id):
        result = []
        service = self._get_bigquery_service()

        datasets = service.datasets().list(projectId=project_id).execute()
        result.extend(datasets.get("datasets", []))
        nextPageToken = datasets.get('nextPageToken', None)

        while nextPageToken is not None:
            datasets = service.datasets().list(projectId=project_id, pageToken=nextPageToken).execute()
            result.extend(datasets.get("datasets", []))
            nextPageToken = datasets.get('nextPageToken', None)

        return result

    def get_schema(self, get_stats=False):
        schema_project_id = os.getenv('BIGQUERY_SCHEMA_PROJECT_ID', self._get_project_id())
        if not self.configuration.get("loadSchema", False):
            return []

        datasets = self._get_project_datasets(schema_project_id)

        query_base = """SELECT table_schema, table_name, column_name, data_type FROM
         `{schema_project_id}.{dataset_id}`.INFORMATION_SCHEMA.COLUMNS
          WHERE table_schema NOT IN ('information_schema')"""

        schema = {}
        queries = []
        for dataset in datasets:
            dataset_id = dataset["datasetReference"]["datasetId"]
            query = query_base.format(schema_project_id=schema_project_id, dataset_id=dataset_id)
            queries.append(query)

        query = '\nUNION ALL\n'.join(queries)
        results, error = self.run_query(query, None)
        if error is not None:
            self._handle_run_query_error(error)

        results = json_loads(results)
        for row in results["rows"]:
            table_name = "{0}.{1}".format(row["table_schema"], row["table_name"])
            if table_name not in schema:
                schema[table_name] = {"name": table_name, "columns": []}
            schema[table_name]["columns"].append(f"{row['column_name']} ({row['data_type']})")

        return list(schema.values())

    def run_query(self, query, user):
        logger.debug("BigQuery got query: %s", query)

        bigquery_service = self._get_bigquery_service()
        jobs = bigquery_service.jobs()

        try:
            if "totalMBytesProcessedLimit" in self.configuration:
                limitMB = self.configuration["totalMBytesProcessedLimit"]
                processedMB = (
                    self._get_total_bytes_processed(jobs, query) / 1000.0 / 1000.0
                )
                if limitMB < processedMB:
                    return (
                        None,
                        "Larger than %d MBytes will be processed (%f MBytes)"
                        % (limitMB, processedMB),
                    )

            data = self._get_query_result(jobs, query, user)
            error = None

            json_data = json_dumps(data, ignore_nan=True)
        except HttpError as e:
            json_data = None
            if e.resp.status in [400, 404]:
                error = json_loads(e.content)["error"]["message"]
            else:
                error = e.content
        except (KeyboardInterrupt, InterruptException, JobTimeoutException):
            if self.current_job_id:
                self._get_bigquery_service().jobs().cancel(
                    projectId=self._get_project_id(),
                    jobId=self.current_job_id,
                    location=self._get_location(),
                ).execute()

            raise

        return json_data, error


register(BigQuery)
