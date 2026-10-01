from laya import Router
import json
router = Router()  # downloads a checkpoint on first use; Router(preload=True) loads all three up front

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

result = router.predict(state, questions)
print("-----RESULTS-----", "\n", result, "\n")
print(json.dumps(result, indent=4))
print(result["answers"]["department"]["choice"])  # billing
print(result["answers"]["urgency"]["score"])  # 1.0
print(result["answers"]["churn_risk"]["noul"])    # probability the answer is yes
