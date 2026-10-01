from dotenv import load_dotenv
import os
import json
load_dotenv()

JEV_APIKEY = os.getenv("JEV_APIKEY")


from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient(api_key=JEV_APIKEY)

state = "Hi, we were charged twice for March. Please  accept this complaint and help to fix the duplicate today or we will cancel our plan. In our organization all customer qeuries are first routed to care"
questions = {
    "department": {"type": "choice", "instructions": "Which department should handle this?",
                   "criteria": {"billing": "all fixes on billing system",
                                "care": "customer queries, complaints, feedback, etc.",
                                "technical": "bugs, outages, system errors, etc.",
                                "other": "everything else"}},
    "urgency": {"type": "score", "instructions": "How urgent is this?",
                "criteria": ["not urgent", "soon", "blocking", "critical"]},
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"},
}


response = client.system_one(
    state=state,
    questions=questions,
)

print("-----RESULTS-----", "\n", response, "\n")
# print(json.dumps(response, indent=4))
print(response.answers["department"].choice)  # "technical"
print(response.answers["urgency"].score)  # 1.0
print(response.answers["churn_risk"].noul)     # 1.0