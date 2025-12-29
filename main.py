from supabase import create_client, Client
from dotenv import load_dotenv, dotenv_values
import os
from datetime import datetime, time, timezone
from helpers import fetch_repo_count, get_keys_rate_limits, get_total_apikeys , repo_sync_status_codes
from githubApp import QUERY,

BootTime = (datetime.now(timezone.utc).replace(microsecond=0))

def UpTime():
    return (datetime.now(timezone.utc).replace(microsecond=0)) - BootTime

load_dotenv()  # loads .env file from the project root

url = os.getenv("SUPABASE_URL")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


TotalApikeys,KeyNames = get_total_apikeys(dotenv_values(".env"), prefix="githubApiKey") #fetch total apikeys from .env file
# TotalGithubApps,AppsNames = get_total_apps() 

keyLimits =  get_keys_rate_limits(dotenv_values(".env"), KeyNames)

print("Total API Keys Found:", TotalApikeys)
print("Key Limits:", keyLimits)
print("Boot Time:", BootTime)
print("Up Time:", UpTime())
print("Status Codes:", repo_sync_status_codes)

supabase: Client = create_client(url, service_role_key)

while True:
    # check for any pending or inprogress topics to complete due to failure or any other reason
    pending_topics = supabase.table("topic_list").select("topic").eq("status", "pending").execute()
    inprogress_topics = supabase.table("topic_list").select("topic").eq("status", "in_progress").execute()

    topics_to_process = pending_topics.data + inprogress_topics.data

    print("Total topics to process which are pending or inprogress:", len(topics_to_process))
    for topic in topics_to_process:
        topic_name = topic['topic']
        topic_StartedAt = datetime.now(timezone.utc).replace(microsecond=0)
        topic_EndedAt = None
        total_duplicated_repos = 0
        total_fetched_repos = 0
        actual_total_repos_github = 0
        total_api_calls_cost = 0
        total_time_taken = 0
        total_pages_fetched = 0


        print(f"Processing topic: {topic_name}")
        print(f"started processing at: {topic_StartedAt}")

        #update in db that topic is in_progress
        supabase.table("topic_list").update({
            "status": "in_progress",
            "started_at": topic_StartedAt.isoformat()
        }).eq("topic", topic_name).execute()

        #select available apikey with available remaining limit
        token_selected =  os.getenv(KeyNames[0])  # Using the first key for simplicity need to improve logic here

        #total repos for this topic
        actual_total_repos_github = fetch_repo_count(topic_name,token_selected)  # Using the first key for simplicity

        #start fetching repos for this topic using pagination
        

        #save in Reposmeta table in db for every 1 page fetched
        #continue until last fetched page 
        #update topic status in db accordingly
        #update db with all metrics for this topic
        #total repos actually fetched for this topic
        #total duplicate repos for this topic
        #total cost in terms of api calls for this topic
        #total time taken for this topic

        topic_EndedAt = datetime.now(timezone.utc).replace(microsecond=0)
        print(f"ended processing at: {topic_EndedAt}")
        print(f"Total time taken for topic {topic_name}: {topic_EndedAt - topic_StartedAt}")
        print("duplicate repos for this topic: ")
    time.sleep(1)  # interval b/w 2 successive repo syncs
    



# rows = supabase.table("ReposMeta").select("*").execute()
# print(rows.data)
