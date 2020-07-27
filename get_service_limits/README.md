
# Deployment Instructions

1. Create the BigQuery tables. Assuming the datasets has already been created.
```
bq mk --table metric_export.service_limits  ./bigquery_schemas/bigquery_schema_service_limits_table.json
```


2. Set your PROJECT_ID variable, by replacing [YOUR_PROJECT_ID] with your GCP project id
```
export PROJECT_ID=[YOUR_PROJECT_ID]
```

3. Replace the token in the config.py files
```
TOKEN=$(python -c "import uuid;  msg = uuid.uuid4(); print msg")
sed -i s/16b2ecfb-7734-48b9-817d-4ac8bd623c87/$TOKEN/g config.json
```

4. Deploy the App Engine apps
```
pip install -t lib -r requirements.txt
echo "y" | gcloud app deploy
```

5. Create the Pub/Sub topics and subscriptions after setting YOUR_PROJECT_ID
```
export GET_SERVICE_LIMITS_URL=https://get-service-limits-dot-$PROJECT_ID.appspot.com

gcloud pubsub topics create get_service_limits_start
gcloud pubsub subscriptions create get_service_limits_start --topic get_service_limits_start --ack-deadline=60 --message-retention-duration=10m --push-endpoint="$GET_SERVICE_LIMITS_URL/_ah/push-handlers/receive_message"
```

6. Deploy the Cloud Scheduler job
```
gcloud scheduler jobs create pubsub get_service_limits \
--schedule "1 1 * * *" \
--topic get_service_limits_start \
--message-body "{ \"token\":\"$(echo $TOKEN)\"}"
```