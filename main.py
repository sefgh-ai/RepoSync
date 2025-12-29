from supabase import create_client, Client
from dotenv import load_dotenv, dotenv_values
import os
from datetime import datetime, timezone
from helpers import fetch_repo_count, get_keys_rate_limits, get_total_apikeys , repo_sync_status_codes
from githubApp import fetch_repos
import time as time_module

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
        total_duplicated_repos = 0 #same here
        total_fetched_repos = 0 #same here
        actual_total_repos_github = 0
        total_api_calls_cost = 0 #need to fetch incase this is crashed in progress topic from db
        total_time_taken = 0 #same here
        total_pages_fetched = 0 #same here
        page_size = 50  #repos per page acutally 100 in a page but to be safe we are using 50


        print(f"Processing topic: {topic_name}")
        print(f"started processing at: {topic_StartedAt}")

        #update in db that topic is in_progress
        supabase.table("topic_list").update({
            "status": "in_progress",
            "started_at": topic_StartedAt.isoformat(),
        }).eq("topic", topic_name).execute()

        #select available apikey with available remaining limit
        token_selected =  os.getenv(KeyNames[0])  # Using the first key for simplicity need to improve logic here

        #total repos for this topic
        actual_total_repos_github = fetch_repo_count(topic_name,token_selected)  # Using the first key for simplicity

        #start fetching repos for this topic using pagination
        all_repos = []
        after_cursor = None #used for pagination more like indexing number
        
        while True:
            fetch_repos_result = fetch_repos(topic_name, token_selected, page_size=50, after_cursor=after_cursor)
            total_api_calls_cost += fetch_repos_result['data']['rateLimit']['cost'] #track api cost
            repos_data = fetch_repos_result['data']['topic']['repositories']
            edges = repos_data['edges']
            for edge in edges:
                all_repos.append(edge["node"])

            page_info = repos_data['pageInfo']
            total_pages_fetched += 1 


        #save in Reposmeta table in db for every 2 pages fetched
            if len(all_repos) >= page_size * 2 or not page_info['hasNextPage']:
                total_fetched_repos += len(all_repos) #update total fetched repos count for this topic

                response = supabase.table("ReposMeta-Research").upsert(all_repos,on_conflict="id",ignore_duplicates=True).execute() # Insert fetched repos into ReposMeta table
                inserted_count = len(response.data) if response.data else 0
                duplicate_count = len(all_repos) - inserted_count
                total_duplicated_repos += duplicate_count
                print(f"Inserted {inserted_count} repos, Duplicates: {duplicate_count} for topic: {topic_name}")
                all_repos = []  # Clear the list after saving to DB

                #update db with all metrics for this topic
                topic_data = {
                    "topic": topic_name, #this is needed for upsert operation
                    "total_repos_github": actual_total_repos_github,
                    "total_pages_fetched": total_pages_fetched,
                    "total_repos_fetched": total_fetched_repos,#total repos actually fetched for this topic
                    "total_duplicate_repos": total_duplicated_repos, #total duplicate repos for this topic
                    "total_api_calls_cost": total_api_calls_cost, #total cost in terms of api calls for this topic
                    "total_time_taken": (datetime.now(timezone.utc).replace(microsecond=0) - topic_StartedAt).total_seconds(),
                    "status": "in_progress" if page_info['hasNextPage'] else "completed",
                    "last_fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                }
                
                #update topic status in db accordingly
                supabase.table("topic_list").upsert(topic_data,on_conflict="topic").execute() # Insert fetched repos into ReposMeta table

            #continue until last fetched page 
            if not page_info['hasNextPage']:
                print(f"No more repositories found for {topic_name}.")
                break


            after_cursor = page_info["endCursor"] #update cursor for next page
        
        #total time taken for this topic
        topic_EndedAt = datetime.now(timezone.utc).replace(microsecond=0)
        supabase.table("topic_list").upsert({"topic": topic_name, "total_time_taken": (topic_EndedAt - topic_StartedAt).total_seconds()},on_conflict="topic").execute() # Insert fetched repos into ReposMeta table
        
        print(f"ended processing at: {topic_EndedAt}")
        print(f"Total time taken for topic {topic_name}: {topic_EndedAt - topic_StartedAt}")
        print(f"duplicate repos for this topic: {total_duplicated_repos}")

    time_module.sleep(1)  # interval b/w 2 successive repo syncs (topics)
    



# rows = supabase.table("ReposMeta").select("*").execute()
# print(rows.data)
