#!/usr/bin/env python

# Copyright 2019 Google Inc.
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

SERVICE_INCLUSIONS = {
    "include_all_enabled_service": "",
    "include_services":[
        "dialogflow.googleapis.com",
        # "monitoring.googleapis.com",
        # "compute.googleapis.com",
    ],
}

# https://cloud.google.com/resource-manager/reference/rest/v1/projects/list
PROJECT_INCLUSIONS = {
    "include_all_projects": "",
    "filter": "name:*",
    "include_projects": [
        "your-project-id",
        # "bank-app-3a968",
    ],
}

BIGQUERY_DATASET='metric_export'
BIGQUERY_STATS_TABLE='service_limits'
PUBSUB_VERIFICATION_TOKEN = '16b2ecfb-7734-48b9-817d-4ac8bd623c87'
