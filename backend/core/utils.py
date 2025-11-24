import re
from uuid import uuid4
from datetime import datetime


def simple_llm_letter(patient, plan, usage_summary, template_type="coverage_summary"):
    """Very simple pseudo-LLM template generator."""
    name = patient.get("name", "Member")
    plan_name = plan.get("plan_name", "your current plan")
    total_visits = usage_summary.get("visits", 0)
    total_spend = usage_summary.get("total_spend", 0)

    if template_type == "coverage_summary":
        return (
            f"Dear {name},\n\n"
            f"This letter summarizes your coverage under {plan_name}.\n"
            f"You have used {total_visits} visits so far with an estimated "
            f"spend of ${total_spend:.2f}.\n\n"
            "Your plan covers primary care, specialist visits, and most "
            "generic medications according to formulary rules.\n\n"
            "Sincerely,\nMediSecure AI"
        )

    if template_type == "medication_coverage":
        return (
            f"Dear {name},\n\n"
            "This letter explains medication coverage under your current plan.\n"
            "Most generic medications are covered at the lowest copay tier, "
            "while some brand-name medications may require prior authorization.\n\n"
            "Please check with your pharmacist or provider for exact costs.\n\n"
            "Sincerely,\nMediSecure AI"
        )

    return f"Dear {name},\n\nThis is an automatically generated correspondence.\n\nMediSecure AI"


def simple_phi_redact(text, patient):
    """Very light PHI-style redaction (demo only)."""
    name = patient.get("name")
    if name:
        text = re.sub(re.escape(name), "[PATIENT_NAME]", text, flags=re.IGNORECASE)
    return text


def fake_usage_summary(visits=3, spend=240.50):
    return {"visits": visits, "total_spend": spend}


def generate_letter_record(patient, plan, content, letter_type):
    return {
        "letter_id": str(uuid4()),
        "patient_phone": patient.get("phone"),
        "letter_type": letter_type,
        "plan_id": plan.get("plan_id"),
        "content": content,
        "created_at": datetime.utcnow().isoformat(),
    }


def chatbot_reply(message, patient, plan, meds_collection):
    """
    Super simple chatbot:
    - if user mentions a medication name we find in DB, say if it's covered.
    - otherwise generic helpful answer.
    """
    text = message.lower()

    # naive extraction: look for any med in DB whose name appears in message
    med = meds_collection.find_one({
        "name_lc": {"$in": [w.strip(",.") for w in text.split()]}
    })

    if med:
        covered_plans = med.get("covered_plans", [])
        plan_id = plan.get("plan_id")
        if plan_id in covered_plans:
            return f"Yes, {med['name']} is covered under your plan."
        else:
            return f"{med['name']} is not listed as covered by your current plan."

    if "coverage" in text or "what does my plan cover" in text:
        return "Your plan covers primary care, specialist visits, and most generic medications."

    if "help" in text or "hi" in text:
        return "Hello! I can help you check if a medication is covered or summarize your benefits."

    return "I’m not sure about that, but you can ask me if a specific medication is covered."
