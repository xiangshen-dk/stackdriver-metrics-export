#!/usr/bin/env python

# Copyright 2020 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import webapp2
import json
import base64
import config
from datetime import datetime
from googleapiclient import discovery
from googleapiclient.discovery import build
from googleapiclient.discovery import HttpError
from google.appengine.api import app_identity

def build_bigquery_data(proj_id, svc_name, limit_data):
    fields = []
    for k, v in limit_data.get("values").items():
        fields.append({"key": k, "value": v})
    update_time = datetime.now().isoformat()
    # Build the data structure to for BigQuery
    bq_msg = {
        "project_id": proj_id,
        "service": svc_name,
        "name": limit_data.get("name"),
        "description": limit_data.get("description"),
        "defaultLimit": limit_data.get("defaultLimit"),
        "maxLimit": limit_data.get("maxLimit"),
        "freeTier": limit_data.get("freeTier"),
        "duration": limit_data.get("duration"),
        "metric": limit_data.get("metric"),
        "unit": limit_data.get("unit"),
        "displayName": limit_data.get("displayName"),
        "update_time": update_time,
        "values": fields,
    }
    json_msg = {
        "json": bq_msg
    }
    logging.debug("json_msg {}".format(json.dumps(json_msg, sort_keys=True, indent=4)))
    return json_msg

def write_to_bigquery(json_row_list):
    """ Write rows to the BigQuery stats table using the googleapiclient and the streaming insertAll method
        https://cloud.google.com/bigquery/docs/reference/rest/v2/tabledata/insertAll
    """
    logging.debug("write_to_bigquery")
    bigquery = build('bigquery', 'v2', cache_discovery=True)
    body = {
        "kind": "bigquery#tableDataInsertAllRequest",
        "skipInvalidRows": "true",
        "ignoreUnknownValues": "true",
        "rows": json_row_list
    }
    logging.debug('body: {}'.format(json.dumps(body, sort_keys=True, indent=4)))
    response = bigquery.tabledata().insertAll(
        projectId=app_identity.get_application_id(),
        datasetId=config.BIGQUERY_DATASET,
        tableId=config.BIGQUERY_STATS_TABLE,
        body=body
    ).execute()
    logging.debug("BigQuery said... = {}".format(response))
    bq_msgs_with_errors = 0
    if "insertErrors" in response:
        if len(response["insertErrors"]) > 0:
            logging.error("Error: {}".format(response))
            bq_msgs_with_errors = len(response["insertErrors"])
            logging.debug("bq_msgs_with_errors: {}".format(bq_msgs_with_errors))
    else:
        logging.debug("Completed writing limits data, there are no errors, response = {}".format(response))
    return response

def get_projects():
    # Get projects
    all_projects = []
    crm = discovery.build("cloudresourcemanager", "v1", cache_discovery=True)
    if config.PROJECT_INCLUSIONS["include_all_projects"]:
        proj_filter = config.PROJECT_INCLUSIONS.get("filter", "name:s*")
        result = crm.projects().list(filter=proj_filter).execute()
        all_projects.extend(result["projects"])
        while result.get("nextPageToken", ""):
            result = crm.projects().list(filter=proj_filter, pageToken=result["nextPageToken"]).execute()
            all_projects.extend(result["projects"])
    else:
        for proj in config.PROJECT_INCLUSIONS.get("include_projects"):
            result = crm.projects().get(projectId=proj).execute()
            all_projects.append(result)
    
    return all_projects

def get_json_rows(all_projects):
    # Get service limits
    all_limits = {}
    service = discovery.build('serviceusage', 'v1', cache_discovery=True)
    for proj_data in all_projects:
        project_id = proj_data["projectId"]
        all_limits[project_id] = {}
        if config.SERVICE_INCLUSIONS["include_all_enabled_service"]:
            response = service.services().list(parent="projects/{}".format(project_id)).execute()
            services = response.get('services')
            for s in services:
                if s['state'] == "ENABLED":
                    svc_name = s["config"]["name"]
                    all_limits[project_id][svc_name] = {}
            while response.get("nextPageToken", ""):
                response = service.services().list(parent="projects/{}".format(project_id), pageToken=response["nextPageToken"]).execute()
                services = response.get('services')
                for s in services:
                    if s['state'] == "ENABLED":
                        svc_name = s["config"]["name"]
                        all_limits[project_id][svc_name] = {}
        else:
            for svc in config.SERVICE_INCLUSIONS.get("include_services"):
                all_limits[project_id][svc] = {}

        for k_svc in all_limits[project_id].keys():   
            proj_svc = "projects/{}/services/{}".format(proj_data["projectNumber"], k_svc)
            response = service.services().get(name=proj_svc).execute()
            state = response['state']
            if state == "ENABLED":
                all_limits[project_id][k_svc] = response["config"].get("quota")
    
    all_json_rows = []

    for proj_id in all_limits.keys():
        for svc_name in all_limits[proj_id].keys():
            for limit in all_limits[proj_id][svc_name]["limits"]:
                all_json_rows.append(build_bigquery_data(proj_id, svc_name, limit))
    return(all_json_rows)

def save_svc_limits():
    all_projects = get_projects()
    all_json_rows = get_json_rows(all_projects)
    write_to_bigquery(all_json_rows)

class ReceiveMessage(webapp2.RequestHandler):

    def post(self):
        """ Receive the Pub/Sub message via POST
            Validate the input and then process the message
        """

        logging.debug("received message")

        response_code = 200
        try:
            if not self.request.body:
                raise ValueError("No request body received")
            envelope = json.loads(self.request.body.decode('utf-8'))
            logging.debug("Raw pub/sub message: {}".format(envelope))

            if "message" not in envelope:
                raise ValueError("No message in envelope")

            if "messageId" in envelope["message"]:
                logging.debug("messageId: {}".format(envelope["message"]["messageId"]))
            message_id = envelope["message"]["messageId"]

            if "data" not in envelope["message"]:
                raise ValueError("No data in message")
            payload = base64.b64decode(envelope["message"]["data"])
            logging.debug('payload: {} '.format(payload))

            data = json.loads(payload)
            logging.debug('data: {} '.format(data))

            # Check the input parameters
            if not data:
                raise ValueError("No data in Pub/Sub Message")
            
            # if the pubsub PUBSUB_VERIFICATION_TOKEN isn't included or doesn't match, don't continue
            if "token" not in data:
                raise ValueError("token missing from request")
            if not data["token"] == config.PUBSUB_VERIFICATION_TOKEN:
                raise ValueError("token from request doesn't match, received: {}".format(data["token"]))

            save_svc_limits()

        except ValueError as ve:
            logging.error("Missing inputs from Pub/Sub: {}".format(ve))
            self.response.write(ve)
        except KeyError as ke:
            logging.error("Key Error: {}".format(ke))
            self.response.write(ke)
        except HttpError as he:
            logging.error("Encountered exception calling APIs: {}".format(he))
            self.response.write(he)

        self.response.status = response_code


app = webapp2.WSGIApplication([
    ('/_ah/push-handlers/receive_message', ReceiveMessage)
], debug=True)
