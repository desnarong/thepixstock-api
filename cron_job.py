import os
   import asyncpg
   import boto3
   import logging
   from minio import Minio
   from dotenv import load_dotenv
   import schedule
   import time
   import asyncio
   import json
   from datetime import datetime
   import uuid

   load_dotenv()

   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)

   # Database
   DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

   # MinIO
   minio_client = Minio(
       os.getenv('MINIO_ENDPOINT'),
       access_key=os.getenv('MINIO_ACCESS_KEY'),
       secret_key=os.getenv('MINIO_SECRET_KEY'),
       secure=False
   )

   # AWS SNS
   sns_client = boto3.client(
       'sns',
       aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
       aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
       region_name=os.getenv('AWS_REGION')
   )

   async def log_action(conn, action: str, details: dict, notify: bool = False):
       log_id = str(uuid.uuid4())
       details_json = json.dumps(details)
       await conn.execute(
           "INSERT INTO logs (log_id, user_id, action, details, timestamp, notification_sent) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5)",
           log_id, None, action, details_json, notify
       )
       if notify:
           try:
               sns_client.publish(
                   TopicArn=os.getenv('AWS_SNS_TOPIC_ARN'),
                   Message=json.dumps({
                       'log_id': log_id,
                       'action': action,
                       'details': details,
                       'timestamp': datetime.utcnow().isoformat()
                   }),
                   Subject=f"Image System Alert: {action}"
               )
               await conn.execute(
                   "UPDATE logs SET notification_sent = TRUE WHERE log_id = $1",
                   log_id
               )
           except Exception as e:
               logger.error(f"Failed to send SNS notification: {str(e)}")
               await conn.execute(
                   "INSERT INTO logs (log_id, user_id, action, details, timestamp, notification_sent) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, FALSE)",
                   str(uuid.uuid4()), None, "sns_notification_error", json.dumps({"error": str(e)}), False
               )

   async def delete_old_data():
       retention_days = int(os.getenv('IMAGE_RETENTION_DAYS', 365))
       async with asyncpg.create_pool(DATABASE_URL) as pool:
           async with pool.acquire() as conn:
               try:
                   images = await conn.fetch(
                       "SELECT id, event_id, filename FROM images WHERE timestamp < NOW() - INTERVAL '$1 days'",
                       retention_days
                   )
                   deleted_count = 0
                   for image in images:
                       bucket_name = f"event-{image['event_id']}"
                       try:
                           minio_client.remove_object(bucket_name, image['filename'])
                           await conn.execute("DELETE FROM faces WHERE image_id = $1", image['id'])
                           await conn.execute("DELETE FROM consents WHERE image_id = $1", image['id'])
                           await conn.execute("DELETE FROM images WHERE id = $1", image['id'])
                           deleted_count += 1
                       except Exception as e:
                           await log_action(conn, "cron_delete_old_data_failed", {"image_id": image['id'], "error": str(e)}, notify=True)
                   await log_action(conn, "cron_delete_old_data", {"deleted_count": deleted_count}, notify=True)
                   logger.info(f"Deleted {deleted_count} old images")
               except Exception as e:
                   await log_action(conn, "cron_delete_old_data_failed", {"error": str(e)}, notify=True)
                   logger.error(f"Error in cron job: {str(e)}")

   def run_cron():
       asyncio.run(delete_old_data())

   schedule.every().day.at(os.getenv('CRON_SCHEDULE', "00:00")).do(run_cron)

   if __name__ == "__main__":
       while True:
           schedule.run_pending()
           time.sleep(60)
