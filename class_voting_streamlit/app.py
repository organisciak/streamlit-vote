import streamlit as st
import json
import requests
import time
import random
import firebase_admin
from firebase_admin import credentials, db

# Firebase configuration
FIREBASE_URL = "https://ai-ia-6ff81-default-rtdb.firebaseio.com/"

# Initialize Firebase with credentials if not already initialized
if not firebase_admin._apps:
    try:
        # Try to load from Streamlit secrets
        # Firebase admin SDK expects a dictionary, not an object with attributes
        firebase_config = dict(st.secrets["firebase"])
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL
        })
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        # Fallback for local development - will use public access rules
        # This will be removed once proper authentication is set up
        print("Warning: Using unauthenticated Firebase access. Set up firebase_credentials in secrets.toml")
        pass

# Initialize session state for app mode and class access
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "idea_submission"
if "class_code" not in st.session_state:
    st.session_state.class_code = ""
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Firebase helper functions
def get_data(class_code=None):
    """Fetch data from Firebase for a specific class"""
    if not class_code:
        class_code = st.session_state.class_code
    
    try:
        # Try to use Firebase Admin SDK if initialized
        if firebase_admin._apps:
            ref = db.reference(f"/classes/{class_code}")
            data = ref.get()
        else:
            # Fallback to unauthenticated access
            response = requests.get(f"{FIREBASE_URL}/classes/{class_code}.json")
            if response.status_code == 200:
                data = response.json()
            else:
                return {"ideas": [], "votes": {}}
        
        if data:
            # Convert any array-based votes to object format
            if "votes" in data:
                for voter, votes in data["votes"].items():
                    if isinstance(votes, list):
                        # Convert array to object format with prefixed keys
                        object_votes = {}
                        for i, vote in enumerate(votes):
                            object_votes[f"idea_{i}"] = vote
                        data["votes"][voter] = object_votes
                        
                        # Save the converted format back to Firebase
                        if firebase_admin._apps:
                            votes_ref = db.reference(f"/classes/{class_code}/votes/{voter}")
                            votes_ref.set(object_votes)
                        else:
                            requests.put(
                                f"{FIREBASE_URL}/classes/{class_code}/votes/{voter}.json",
                                data=json.dumps(object_votes)
                            )
            return data
        else:
            return {"ideas": [], "votes": {}}
    except Exception as e:
        st.error(f"Error retrieving data: {str(e)}")
        return {"ideas": [], "votes": {}}

def save_data(data, class_code=None):
    """Save data to Firebase for a specific class"""
    if not class_code:
        class_code = st.session_state.class_code
    
    try:
        if firebase_admin._apps:
            # Use authenticated Firebase Admin SDK
            ref = db.reference(f"/classes/{class_code}")
            ref.set(data)
            return True
        else:
            # Fallback to unauthenticated access
            response = requests.put(
                f"{FIREBASE_URL}/classes/{class_code}.json", 
                data=json.dumps(data)
            )
            return response.status_code == 200
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def get_class_codes():
    """Get list of existing class codes"""
    try:
        if firebase_admin._apps:
            # Use authenticated Firebase Admin SDK
            ref = db.reference("/class_access_codes")
            data = ref.get()
            return data or {}
        else:
            # Fallback to unauthenticated access
            response = requests.get(f"{FIREBASE_URL}/class_access_codes.json")
            if response.status_code == 200 and response.json():
                return response.json()
            return {}
    except Exception as e:
        st.error(f"Error getting class codes: {str(e)}")
        return {}

def get_teacher_password():
    """Get teacher password from Streamlit secrets or use fallback"""
    try:
        return st.secrets["teacher_password"]
    except (KeyError, FileNotFoundError):
        # Fallback for local development
        return "teacherpass"

def main():
    # App header
    st.title("AI Ethics Collaborative Voting")
    
    # Get teacher password from secrets
    teacher_password = get_teacher_password()
    
    # Initialize session state variables
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "idea_submission"
    if "class_code" not in st.session_state:
        st.session_state.class_code = ""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # Class access authentication
    if not st.session_state.authenticated:
        st.header("Class Access")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Join Existing Class")
            class_code = st.text_input("Enter Class Code:")
            
            if st.button("Join Class"):
                # Check if class code exists
                class_codes = get_class_codes()
                if class_code in class_codes:
                    st.session_state.class_code = class_code
                    st.session_state.authenticated = True
                    st.success(f"Joined class: {class_codes[class_code]}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Invalid class code. Please try again.")
        
        with col2:
            st.subheader("Create New Class")
            teacher_password = st.text_input("Teacher Password:", type="password")
            new_class_name = st.text_input("Class Name:")
            new_class_code = st.text_input("Create Class Code:")
            
            if st.button("Create Class"):
                if teacher_password != get_teacher_password():
                    st.error("Incorrect teacher password")
                elif not new_class_name or not new_class_code:
                    st.error("Please provide both class name and code")
                else:
                    # Save new class code
                    class_codes = get_class_codes()
                    class_codes[new_class_code] = new_class_name
                    
                    success = False
                    if firebase_admin._apps:
                        try:
                            ref = db.reference("/class_access_codes")
                            ref.set(class_codes)
                            success = True
                        except Exception as e:
                            st.error(f"Error creating class: {str(e)}")
                    else:
                        response = requests.put(
                            f"{FIREBASE_URL}/class_access_codes.json",
                            data=json.dumps(class_codes)
                        )
                        success = response.status_code == 200
                    
                    if success:
                        # Initialize empty data for the new class
                        save_data({"ideas": [], "votes": {}}, new_class_code)
                        
                        st.session_state.class_code = new_class_code
                        st.session_state.authenticated = True
                        st.success(f"Created and joined class: {new_class_name}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to create class. Please try again.")
        
        # Stop execution here if not authenticated
        st.stop()
    
    # Display current class info
    class_codes = get_class_codes()
    if st.session_state.class_code in class_codes:
        st.info(f"Current Class: {class_codes[st.session_state.class_code]} (Code: {st.session_state.class_code})")
    
    # Load current data for the authenticated class
    data = get_data()
    
    # Admin controls in sidebar
    with st.sidebar:
        st.header("Teacher Controls")
        
        # Add logout button
        if st.button("Switch Class"):
            st.session_state.authenticated = False
            st.session_state.class_code = ""
            st.rerun()
        
        # Reset button (only shown to teacher)
        teacher_password = st.text_input("Teacher Password (for reset)", type="password")
        if st.button("Reset All Data"):
            if teacher_password == get_teacher_password():  # Password from secrets
                if save_data({"ideas": [], "votes": {}}, st.session_state.class_code):
                    st.success("Data reset successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to reset data. Check Firebase connection.")
            else:
                st.error("Incorrect password")
    
    # Student name input
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""
    
    student_name = st.text_input("Your Name or Group Name:", value=st.session_state.student_name)
    if student_name != st.session_state.student_name:
        # Name has changed, reset current votes in session state
        if "current_votes" in st.session_state:
            del st.session_state.current_votes
        if "randomized_ideas" in st.session_state:
            del st.session_state.randomized_ideas
        st.session_state.student_name = student_name
        st.rerun()
    
    # Create tabs for the different modes
    idea_tab, voting_tab, results_tab = st.tabs(["💡 Scenario Submission", "🗳️ Voting", "📊 Results"])
    
    # Main app logic based on tabs
    with idea_tab:
        st.header("Submit Your AI Ethics Scenarios")
        st.markdown("""
        In your group, generate AI use cases that span the ethical spectrum:
        1. **Clearly Ethical ("Good")**: An AI use case where benefits are obvious and risks minimal
        2. **Clearly Unethical/Inappropriate ("Bad")**: A use case where the negative impact or misuse is evident
        3. **Borderline/Gray Area**: A scenario that isn't immediately obvious and could be seen as both ethical and problematic
        
        Submit each scenario separately below. The class will vote on where each scenario falls on the ethical spectrum.
        """)
        
        # Input for new idea
        new_idea = st.text_area("Enter your scenario:", height=100)
        
        if st.button("Submit Scenario"):
            # Refresh data before modifying to reduce conflicts
            data = get_data()
            
            if not student_name:
                st.error("Please enter your group name first!")
            elif not new_idea:
                st.error("Please enter a scenario!")
            else:
                # Add new idea with student name
                if "ideas" not in data:
                    data["ideas"] = []
                
                data["ideas"].append({
                    "idea": new_idea,
                    "submitted_by": student_name,
                    "timestamp": time.time()  # Add timestamp to help with conflict resolution
                })
                
                if save_data(data, st.session_state.class_code):
                    st.success("Scenario submitted successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to submit scenario. Please try again.")
        
        # Display existing ideas
        if data.get("ideas"):
            st.subheader("Current Scenarios")
            
            # Display all ideas without categorization
            for i, idea_data in enumerate(data["ideas"]):
                # Check if idea_data has the required fields
                if isinstance(idea_data, dict) and 'idea' in idea_data and 'submitted_by' in idea_data:
                    st.markdown(f"**Scenario {i+1}:** {idea_data['idea']} _(by {idea_data['submitted_by']})_")
                else:
                    # Handle case where idea data is malformed
                    idea_text = idea_data.get('idea', 'Unknown scenario') if isinstance(idea_data, dict) else 'Unknown scenario'
                    submitted_by = idea_data.get('submitted_by', 'Unknown') if isinstance(idea_data, dict) else 'Unknown'
                    st.markdown(f"**Scenario {i+1}:** {idea_text} _(by {submitted_by})_")
    
    with voting_tab:
        st.header("Vote on AI Ethics Scenarios")
        st.markdown("""
        **Recommended: Switch from group to individual voting. Change your name above.**
        
        Review each scenario and rate it on a scale of 1-5:
        - **1**: This is a clearly *unethical* or *inappropriate* use of AI
        - **5**: This is a clearly *ethical* or *good* use of AI
        
        Your votes help us understand our collective ethical judgments.
        """)
        
        # Refresh data for latest ideas
        data = get_data()
        
        if not student_name:
            st.error("Please enter your name to vote!")
        else:
            if data.get("ideas"):
                st.write("Rate each scenario from 1 to 5 (where 5 is the highest).")
                
                # Auto-save toggle
                if "auto_save" not in st.session_state:
                    st.session_state.auto_save = False
                
                auto_save = st.checkbox("Auto-save votes when slider changes", 
                                       value=st.session_state.auto_save,
                                       help="When enabled, votes are saved automatically when you move the slider")
                
                if auto_save != st.session_state.auto_save:
                    st.session_state.auto_save = auto_save
                    st.rerun()
                
                # Initialize votes in session state if needed
                if "current_votes" not in st.session_state:
                    st.session_state.current_votes = {}
                    
                    # Pre-populate with any existing votes from this user
                    if "votes" in data and student_name in data["votes"]:
                        # Handle both array and object formats for backward compatibility
                        if isinstance(data["votes"][student_name], dict):
                            st.session_state.current_votes = data["votes"][student_name].copy()
                        elif isinstance(data["votes"][student_name], list):
                            # Convert array format to object format with prefixed keys
                            for i, vote in enumerate(data["votes"][student_name]):
                                if i < len(data["ideas"]):
                                    st.session_state.current_votes[f"idea_{i}"] = vote
                
                # Create a randomized list of ideas with their original indices
                ideas_with_indices = [(i, idea) for i, idea in enumerate(data["ideas"])]
                
                # Use session state to maintain the same random order between reruns
                if "randomized_ideas" not in st.session_state:
                    random.shuffle(ideas_with_indices)
                    st.session_state.randomized_ideas = ideas_with_indices
                else:
                    ideas_with_indices = st.session_state.randomized_ideas
                
                # Function to save vote
                def save_vote(idea_id, rating):
                    # Refresh data to minimize conflicts
                    updated_data = get_data()
                    
                    # Initialize votes dict if needed
                    if "votes" not in updated_data:
                        updated_data["votes"] = {}
                    
                    # Initialize this user's votes as an object/dict, not an array
                    if student_name not in updated_data["votes"]:
                        updated_data["votes"][student_name] = {}
                    elif isinstance(updated_data["votes"][student_name], list):
                        # Convert array to object format with prefixed keys
                        old_votes = updated_data["votes"][student_name]
                        updated_data["votes"][student_name] = {}
                        for j, vote in enumerate(old_votes):
                            if j < len(updated_data["ideas"]):
                                updated_data["votes"][student_name][f"idea_{j}"] = vote
                    
                    # Update the vote in the object
                    updated_data["votes"][student_name][idea_id] = rating
                    
                    # Save the entire updated votes structure
                    success = False
                    if firebase_admin._apps:
                        try:
                            votes_ref = db.reference(f"/classes/{st.session_state.class_code}/votes/{student_name}")
                            votes_ref.set(updated_data["votes"][student_name])
                            success = True
                        except Exception as e:
                            st.error(f"Error saving vote: {str(e)}")
                    else:
                        vote_response = requests.put(
                            f"{FIREBASE_URL}/classes/{st.session_state.class_code}/votes/{student_name}.json",
                            data=json.dumps(updated_data["votes"][student_name])
                        )
                        success = vote_response.status_code == 200
                    
                    if success:
                        # Update session state
                        st.session_state.current_votes[idea_id] = rating
                        return True
                    return False
                
                # Display each idea with its own voting controls
                for i, idea_data in ideas_with_indices:
                    # Use prefixed idea_id to prevent Firebase from converting to array
                    idea_id = f"idea_{i}"
                    
                    with st.container():
                        st.divider()
                        # Display idea without category and submitter's name - handle missing data
                        if isinstance(idea_data, dict) and 'idea' in idea_data:
                            st.markdown(f"**Scenario:** {idea_data['idea']}")
                        else:
                            # Fallback for malformed data
                            idea_text = idea_data.get('idea', 'Unknown scenario') if isinstance(idea_data, dict) else 'Unknown scenario'
                            st.markdown(f"**Scenario:** {idea_text}")
                        
                        # Get current vote value - default to 0 (no vote)
                        current_value = 0
                        if idea_id in st.session_state.current_votes:
                            current_value = st.session_state.current_votes[idea_id]
                        
                        # Create columns for rating and submit button
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            # Callback for auto-save
                            def on_slider_change(key):
                                if st.session_state.auto_save:
                                    # Extract idea_id from the key
                                    slider_key = key
                                    idx = int(slider_key.split('_')[-1])
                                    idea_key = f"idea_{idx}"
                                    new_value = st.session_state[slider_key]
                                    
                                    # Only save if value changed and not 0 (no vote)
                                    if new_value > 0:
                                        if idea_key not in st.session_state.current_votes or st.session_state.current_votes[idea_key] != new_value:
                                            success = save_vote(idea_key, new_value)
                                            if success:
                                                st.toast(f"Vote automatically saved: {new_value}/5")
                                    # If value is 0 and there was a previous vote, remove it
                                    elif idea_key in st.session_state.current_votes:
                                        # Remove vote from Firebase
                                        updated_data = get_data()
                                        if "votes" in updated_data and student_name in updated_data["votes"]:
                                            if idea_key in updated_data["votes"][student_name]:
                                                # Create a copy without this vote
                                                updated_votes = updated_data["votes"][student_name].copy()
                                                updated_votes.pop(idea_key, None)
                                                
                                                # Save the updated votes
                                                success = False
                                                if firebase_admin._apps:
                                                    try:
                                                        votes_ref = db.reference(f"/classes/{st.session_state.class_code}/votes/{student_name}")
                                                        votes_ref.set(updated_votes)
                                                        success = True
                                                    except Exception as e:
                                                        st.error(f"Error removing vote: {str(e)}")
                                                else:
                                                    vote_response = requests.put(
                                                        f"{FIREBASE_URL}/classes/{st.session_state.class_code}/votes/{student_name}.json",
                                                        data=json.dumps(updated_votes)
                                                    )
                                                    success = vote_response.status_code == 200
                                                
                                                if success:
                                                    # Update session state
                                                    st.session_state.current_votes.pop(idea_key, None)
                                                    st.toast("Vote removed")
                            
                            # Slider for rating with 0 as "No Vote"
                            slider_key = f"vote_slider_{i}"
                            new_rating = st.select_slider(
                                f"Your rating:",
                                options=[0, 1, 2, 3, 4, 5],
                                value=current_value,
                                key=slider_key,
                                on_change=on_slider_change,
                                args=(slider_key,),
                                format_func=lambda x: {
                                    0: "No Vote",
                                    1: "1 - Clearly Unacceptable",
                                    2: "2 - Somewhat Unacceptable",
                                    3: "3 - Neutral/Borderline",
                                    4: "4 - Somewhat Acceptable",
                                    5: "5 - Clearly Acceptable"
                                }.get(x, str(x))
                            )
                        
                        with col2:
                            # Only show submit button if auto-save is disabled
                            if not st.session_state.auto_save:
                                # Only enable button if rating changed and not 0 (no vote)
                                button_disabled = (new_rating == 0 or 
                                                  (idea_id in st.session_state.current_votes and 
                                                   st.session_state.current_votes[idea_id] == new_rating))
                                
                                if new_rating > 0:
                                    if st.button("Submit Vote", key=f"submit_vote_{i}", 
                                                disabled=button_disabled):
                                        if save_vote(idea_id, new_rating):
                                            st.success(f"Vote submitted for this scenario!")
                                            time.sleep(0.5)
                                            st.rerun()
                                        else:
                                            st.error("Failed to submit vote. Please try again.")
                                else:
                                    # Show remove vote button if there's an existing vote
                                    if idea_id in st.session_state.current_votes:
                                        if st.button("Remove Vote", key=f"remove_vote_{i}"):
                                            # Remove vote from Firebase
                                            updated_data = get_data()
                                            if "votes" in updated_data and student_name in updated_data["votes"]:
                                                if idea_id in updated_data["votes"][student_name]:
                                                    # Create a copy without this vote
                                                    updated_votes = updated_data["votes"][student_name].copy()
                                                    updated_votes.pop(idea_id, None)
                                                    
                                                    # Save the updated votes
                                                    success = False
                                                    if firebase_admin._apps:
                                                        try:
                                                            votes_ref = db.reference(f"/classes/{st.session_state.class_code}/votes/{student_name}")
                                                            votes_ref.set(updated_votes)
                                                            success = True
                                                        except Exception as e:
                                                            st.error(f"Error removing vote: {str(e)}")
                                                    else:
                                                        vote_response = requests.put(
                                                            f"{FIREBASE_URL}/classes/{st.session_state.class_code}/votes/{student_name}.json",
                                                            data=json.dumps(updated_votes)
                                                        )
                                                        success = vote_response.status_code == 200
                                                    
                                                    if success:
                                                        # Update session state
                                                        st.session_state.current_votes.pop(idea_id, None)
                                                        st.success("Vote removed!")
                                                        time.sleep(0.5)
                                                        st.rerun()
                                                    else:
                                                        st.error("Failed to remove vote. Please try again.")
                                    else:
                                        # Placeholder button that's disabled
                                        st.button("Submit Vote", key=f"submit_vote_{i}", disabled=True)
                        
                        # Show current vote if already voted
                        if idea_id in st.session_state.current_votes:
                            st.info(f"Your current rating: {st.session_state.current_votes[idea_id]}/5")
                        else:
                            st.info("No vote submitted yet")
                
                # Add a button to clear all votes
                st.divider()
                if st.button("Clear All My Votes"):
                    # Delete just this user's votes using a direct path
                    success = False
                    if firebase_admin._apps:
                        try:
                            votes_ref = db.reference(f"/classes/{st.session_state.class_code}/votes/{student_name}")
                            votes_ref.delete()
                            success = True
                        except Exception as e:
                            st.error(f"Error clearing votes: {str(e)}")
                    else:
                        vote_path = f"votes/{student_name}"
                        vote_response = requests.delete(
                            f"{FIREBASE_URL}/classes/{st.session_state.class_code}/{vote_path}.json"
                        )
                        success = vote_response.status_code == 200
                    
                    if success:
                        # Clear session state
                        st.session_state.current_votes = {}
                        st.session_state.pop("randomized_ideas", None)
                        st.success("All your votes have been cleared!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed to clear votes. Please try again.")
            else:
                st.info("No scenarios have been submitted yet!")
    
    with results_tab:
        st.header("Collective Ethical Judgments")
        st.markdown("""
        This shows our class's collective judgment on each AI ethics scenario.
        Higher scores indicate stronger agreement with the scenario's ethical categorization.
        """)
        
        # Refresh data for latest results
        data = get_data()
        
        if data.get("ideas"):
            # Import pandas for results processing
            import pandas as pd
            import numpy as np  # Add numpy for handling NaN values
            
            # Calculate average scores for each scenario
            results = []
            for i, idea_data in enumerate(data["ideas"]):
                # Use prefixed idea_id to match the new format
                idea_id = f"idea_{i}"
                
                # Extract idea details with fallbacks for missing data
                if isinstance(idea_data, dict):
                    idea_text = idea_data.get('idea', 'Unknown scenario')
                    submitted_by = idea_data.get('submitted_by', 'Unknown')
                else:
                    idea_text = 'Unknown scenario'
                    submitted_by = 'Unknown'
                
                # Collect all votes for this scenario
                votes = []
                if "votes" in data:
                    for voter, voter_votes in data["votes"].items():
                        # Check if voter_votes is a dictionary and contains this idea_id
                        if isinstance(voter_votes, dict) and idea_id in voter_votes:
                            try:
                                votes.append(int(voter_votes[idea_id]))
                            except (ValueError, TypeError):
                                # Skip invalid votes
                                pass
                        # Handle legacy array format
                        elif isinstance(voter_votes, list) and i < len(voter_votes):
                            try:
                                votes.append(int(voter_votes[i]))
                            except (ValueError, TypeError):
                                # Skip invalid votes
                                pass
                
                # Fix: Handle case when there are no votes
                avg_score = sum(votes) / len(votes) if votes else 0
                num_votes = len(votes)
                
                results.append({
                    "idea_num": i + 1,
                    "idea": idea_text,
                    "submitted_by": submitted_by,
                    "avg_score": avg_score,
                    "num_votes": num_votes
                })
            
            # Create results DataFrame and sort by average score
            results_df = pd.DataFrame(results)
            
            # Fix: Check if DataFrame is empty or if all avg_scores are 0
            if not results_df.empty and results_df['avg_score'].sum() > 0:
                # Sort by average score, handling NaN values
                results_df = results_df.sort_values("avg_score", ascending=False)
                
                # Display results as a table
                st.dataframe(
                    results_df[["idea_num", "idea", "submitted_by", "avg_score", "num_votes"]],
                    column_config={
                        "idea_num": "Scenario #",
                        "idea": "Scenario",
                        "submitted_by": "Submitted By",
                        "avg_score": st.column_config.NumberColumn("Ethical Score", format="%.2f/5"),
                        "num_votes": "Number of Votes"
                    },
                    hide_index=True
                )
                
                # Create a bar chart of results
                st.subheader("Average Scores (Higher is Better)")
                chart_data = results_df.copy()
                chart_data["idea_label"] = chart_data.apply(lambda x: f"Scenario {x['idea_num']}", axis=1)
                
                # Fix: Ensure we have valid data for the chart
                if not chart_data.empty and chart_data['avg_score'].sum() > 0:
                    st.bar_chart(data=chart_data, x="idea_label", y="avg_score", height=400)
                else:
                    st.info("No votes have been submitted yet for the chart visualization.")
                
                # Show who has voted
                if "votes" in data:
                    st.subheader("Participation")
                    voters_count = sum(1 for voter, votes in data["votes"].items() if isinstance(votes, dict) and votes)
                    st.write(f"Total number of voters: {voters_count}")
                    st.write("Students who have voted:")
                    voters = [voter for voter, votes in data["votes"].items() if isinstance(votes, dict) and votes]
                    st.write(", ".join(voters) if voters else "No one has voted yet")
            else:
                st.info("No votes have been submitted yet!")
        else:
            st.info("No scenarios have been submitted yet!")


if __name__ == "__main__":
    main()