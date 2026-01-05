from supabase import create_client, Client
from dotenv import load_dotenv, dotenv_values
import os
from datetime import datetime, timezone
from helpers import fetch_repo_count, get_keys_rate_limits, get_total_apikeys, repo_sync_status_codes, KeyManager
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

# Initialize KeyManager for automatic key rotation
key_manager = KeyManager(dotenv_values(".env"), KeyNames)

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

    if len(topics_to_process) <= 0:
        print("No pending or in-progress topics found. Exiting.")
        print("waiting for webhook trigger or next scheduled sync... in 5 minutes")
        time_module.sleep(300)  # wait for 5 minutes before checking again
        
    else :
        print("Total topics to process which are pending or inprogress:", len(topics_to_process))
        for topic in topics_to_process:
            topic_name = topic['topic']
            topic_response = supabase.table("topic_list").select('total_duplicate_repos,total_repos_fetched,total_api_calls_cost,"total_time_taken(in seconds)",total_pages_fetched,last_cursor').eq("topic", topic_name).execute()
            topic_StartedAt = datetime.now(timezone.utc).replace(microsecond=0)
            topic_EndedAt = None
            topic_data = topic_response.data[0] if topic_response.data else {}
            total_duplicated_repos = topic_data.get("total_duplicate_repos") or 0  #same here
            total_fetched_repos = topic_data.get("total_repos_fetched") or 0 #same here
            actual_total_repos_github = 0
            total_api_calls_cost = topic_data.get("total_api_calls_cost") or 0 #need to fetch incase this is crashed in progress topic from db
            total_time_taken = topic_data.get("total_time_taken(in seconds)") or 0 #same here
            total_pages_fetched = topic_data.get("total_pages_fetched") or 0 #same here
            last_cursor_from_db = topic_data.get("last_cursor") #fetch last cursor to resume from where we left off
            page_size = 50  #repos per page acutally 100 in a page but to be safe we are using 50


            print(f"Processing topic: {topic_name}")
            print(f"started processing at: {topic_StartedAt}")

            if total_fetched_repos > 0 or total_duplicated_repos > 0 or total_api_calls_cost > 0 or total_pages_fetched > 0:
                print(f"Previously fetched repos for this topic: {total_fetched_repos}")
                print(f"Previously duplicated repos for this topic: {total_duplicated_repos}")
                print(f"Previously total api calls cost for this topic: {total_api_calls_cost}")
                print(f"Previously total pages fetched for this topic: {total_pages_fetched}")
                print(f"Previously total time taken for this topic (in seconds): {total_time_taken}")

            #update in db that topic is in_progress
            supabase.table("topic_list").update({
                "status": "in_progress",
                "started_at": topic_StartedAt.isoformat(),
            }).eq("topic", topic_name).execute()

            #select available apikey with available remaining limit
            token_selected = key_manager.get_key()  # KeyManager handles rotation automatically

            #total repos for this topic
            actual_total_repos_github = fetch_repo_count(topic_name, token_selected)

            #start fetching repos for this topic using pagination
            all_repos = []
            after_cursor = last_cursor_from_db #resume from last cursor if available, else start fresh
            
            print("\n" + "="*60)
            if after_cursor:
                print(f"🔄 RESUMING TOPIC: {topic_name}")
                print(f"   Last cursor: {after_cursor[:30]}...")
                print(f"   Already fetched: {total_fetched_repos} repos ({total_pages_fetched} pages)")
                print(f"   Total on GitHub: {actual_total_repos_github} repos")
                print(f"   Remaining: ~{actual_total_repos_github - total_fetched_repos} repos")
            else:
                print(f"🆕 STARTING NEW TOPIC: {topic_name}")
                print(f"   Total on GitHub: {actual_total_repos_github} repos")
                print(f"   Starting from page 1")
            print("="*60 + "\n")
            
            while True:
                token_selected = key_manager.get_key()  # Get best available key (may rotate)
                fetch_repos_result = fetch_repos(topic_name, token_selected, page_size=50, after_cursor=after_cursor)
                
                # Update KeyManager with rate limit info from response
                key_manager.update_from_response(fetch_repos_result['data']['rateLimit'])
                
                total_api_calls_cost += fetch_repos_result['data']['rateLimit']['cost'] #track api cost
                repos_data = fetch_repos_result['data']['topic']['repositories']
                edges = repos_data['edges']
                for edge in edges:
                    repo = edge["node"]
                    graphql_id = repo["id"]
                    repo_id = repo["databaseId"]
                    namewithowner = repo["nameWithOwner"]
                    description = repo["description"] or None
                    stargazer_count = repo["stargazerCount"] or 0
                    fork_count = repo["forkCount"] or 0
                    created_at = repo["createdAt"] 
                    updated_at = repo["updatedAt"] 
                    is_archived = repo["isArchived"] 
                    is_fork = repo["isFork"] 
                    homepage_url = repo["homepageUrl"] or None
                    license_info = repo["licenseInfo"]["name"] if repo["licenseInfo"] else None
                    repository_topics = [node["topic"]["name"] for node in repo["repositoryTopics"]["nodes"]] or None
                    languages = [node["name"] for node in repo["languages"]["nodes"]] or None
                    open_issues_count = repo["issues"]["totalCount"] or 0
                    funding_links = repo["fundingLinks"] or None
                    owner_type = repo["owner"]["__typename"]
                    
                    repo_record = {
                        "repo_id": repo_id,
                        "graphql_id": graphql_id,
                        "nameWithOwner": namewithowner,
                        "description": description,
                        "stargazerCount": stargazer_count,
                        "forkCount": fork_count,
                        "createdAt": created_at,
                        "updatedAt": updated_at,
                        "isArchived": is_archived,
                        "isFork": is_fork,
                        "homepageUrl": homepage_url,
                        "license_name": license_info,
                        "topics": repository_topics,
                        "languages": languages,
                        "open_issues_count": open_issues_count,
                        "funding_links": funding_links,
                        "owner_type": owner_type,
                        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    }

                    all_repos.append(repo_record) # Accumulate repos

                page_info = repos_data['pageInfo']
                total_pages_fetched += 1 


            #save in Reposmeta table in db for every 2 pages fetched
                if len(all_repos) >= page_size * 2 or not page_info['hasNextPage']:
                    total_fetched_repos += len(all_repos) #update total fetched repos count for this topic

                    response = supabase.table("ReposMeta-Research").upsert(all_repos,on_conflict="graphql_id",ignore_duplicates=True).execute() # Insert fetched repos into ReposMeta table
                    inserted_count = len(response.data) if response.data else 0
                    duplicate_count = len(all_repos) - inserted_count
                    total_duplicated_repos += duplicate_count
                    
                    # Progress logging
                    progress_pct = (total_fetched_repos / actual_total_repos_github * 100) if actual_total_repos_github > 0 else 0
                    print(f"📦 Page {total_pages_fetched} | +{inserted_count} new, {duplicate_count} dupes | "
                          f"Total: {total_fetched_repos}/{actual_total_repos_github} ({progress_pct:.1f}%) | "
                          f"Cursor: {page_info['endCursor'][:15]}...")
                    
                    all_repos = []  # Clear the list after saving to DB

                    #update db with all metrics for this topic
                    topic_data = {
                        "topic": topic_name, #this is needed for upsert operation
                        "total_repos_github": actual_total_repos_github,
                        "total_pages_fetched": total_pages_fetched,
                        "total_repos_fetched": total_fetched_repos,#total repos actually fetched for this topic
                        "total_duplicate_repos": total_duplicated_repos, #total duplicate repos for this topic
                        "total_api_calls_cost": total_api_calls_cost, #total cost in terms of api calls for this topic
                        "total_time_taken(in seconds)": (datetime.now(timezone.utc).replace(microsecond=0) - topic_StartedAt).total_seconds(),
                        "status": "in_progress" if page_info['hasNextPage'] else "completed",
                        "last_fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        "last_cursor": page_info['endCursor'] if page_info['hasNextPage'] else None #save cursor for resume, reset on completion
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
            supabase.table("topic_list").upsert({"topic": topic_name, "Ended_At": topic_EndedAt.isoformat() , "total_time_taken(in seconds)": (topic_EndedAt - topic_StartedAt).total_seconds()},on_conflict="topic").execute() # Insert fetched repos into ReposMeta table
            
            print(f"ended processing at: {topic_EndedAt}")
            print(f"Total time taken for topic {topic_name}: {topic_EndedAt - topic_StartedAt}")
            print(f"duplicate repos for this topic: {total_duplicated_repos}")

        time_module.sleep(1)  # interval b/w 2 successive repo syncs (topics)
    



# rows = supabase.table("ReposMeta").select("*").execute()
# print(rows.data)
