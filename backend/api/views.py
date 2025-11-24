# backend/api/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from pymongo import MongoClient
import csv
import os

from .utils import (
    simple_llm_letter,
    simple_phi_redact,
    fake_usage_summary,
    generate_letter_record,
    chatbot_reply,
)

# ---- Mongo setup ----
client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

patients_col = db["patients"]
plans_col = db["plans"]
usage_col = db["usage"]
letters_col = db["letters"]
meds_col = db["medications"]
members_col = db["insurance_members"]   # Kaggle members


# ---- Helper: default plan ----
def get_or_create_default_plan():
    plan = plans_col.find_one({"plan_id": "BASIC_PLAN"})
    if not plan:
        plan = {
            "plan_id": "BASIC_PLAN",
            "plan_name": "Basic Health Coverage Plan",
            "description": "Covers primary care, specialists, labs, and generic medications.",
        }
        plans_col.insert_one(plan)
    return plan


# ---- 1) Load Kaggle → Mongo (run once) ----
@api_view(["POST"])
def load_insurance_members(request):
    """
    Load insurance members from Kaggle CSV into Mongo.
    CSV path: backend/kaggle_data/healthcare_dataset.csv
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    csv_path = os.path.join(base_dir, "kaggle_data", "healthcare_dataset.csv")

    if not os.path.exists(csv_path):
        return Response(
            {"error": f"{csv_path} not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Clear old data
    members_col.delete_many({})

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # ⚠️ IMPORTANT:
            # Adjust these keys to match the EXACT column names in your CSV.
            # Example mapping – open the CSV and check:
            #  - "Name"
            #  - "DateOfBirth"
            #  - "PhoneNumber"
            #  - "PlanName"
            #  - "CoverageLevel"
            #  - "Deductible"
            #  - "Copay"
            name = row.get("Name", "").strip()
            dob = row.get("DateOfBirth", "").strip()
            phone = row.get("PhoneNumber", "").strip()
            plan_name = row.get("PlanName", "Imported Plan").strip()
            coverage_level = row.get("CoverageLevel", "Standard").strip()

            # numeric fields – default to 0 if blank
            deductible_raw = row.get("Deductible", "") or "0"
            copay_raw = row.get("Copay", "") or "0"
            try:
                deductible = float(deductible_raw)
            except ValueError:
                deductible = 0.0
            try:
                copay = float(copay_raw)
            except ValueError:
                copay = 0.0

            if not name:
                continue  # skip bad rows

            members_col.insert_one(
                {
                    "name": name,
                    "name_lc": name.lower(),
                    "dob": dob,
                    "phone": phone,
                    "plan_name": plan_name,
                    "coverage_level": coverage_level,
                    "deductible": deductible,
                    "copay": copay,
                }
            )

    return Response(
        {"status": "Insurance members loaded from healthcare_dataset.csv."},
        status=status.HTTP_200_OK,
    )


# ---- 2) Register patient – looks into Kaggle-backed collection ----
@api_view(["POST"])
def register_patient(request):
    name = request.data.get("name", "").strip()
    dob = request.data.get("dob", "").strip()
    phone = request.data.get("phone", "").strip()

    if not (name and dob and phone):
        return Response(
            {"error": "name, dob, phone are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Try to match against Kaggle-imported members
    member = members_col.find_one(
        {
            "name_lc": name.lower(),
            "dob": dob,
            # You can also include phone here if your CSV has it:
            # "phone": phone,
        },
        {"_id": 0},
    )

    if member:
        plan = {
            "plan_id": "KAGGLE_PLAN",
            "plan_name": member.get("plan_name", "Kaggle Imported Plan"),
            "description": f"Coverage level: {member.get('coverage_level', 'N/A')}",
            "deductible": member.get("deductible", 0),
            "copay": member.get("copay", 0),
        }
        # upsert that plan in plans_col for later lookups
        plans_col.update_one(
            {"plan_id": "KAGGLE_PLAN"},
            {"$set": plan},
            upsert=True,
        )
    else:
        plan = get_or_create_default_plan()

    # Upsert patient
    patients_col.update_one(
        {"phone": phone},
        {
            "$set": {
                "name": name,
                "dob": dob,
                "phone": phone,
                "plan_id": plan["plan_id"],
            }
        },
        upsert=True,
    )

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})

    return Response({"patient": patient, "plan": plan}, status=status.HTTP_200_OK)


# ---- 3) Dashboard: coverage + usage + latest letter ----
@api_view(["GET"])
def get_patient_dashboard(request, phone):
    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0})
    if not plan:
        plan = get_or_create_default_plan()

    usage_summary = fake_usage_summary()

    latest_letter = letters_col.find_one(
        {"patient_phone": phone},
        {"_id": 0},
        sort=[("created_at", -1)],
    )

    return Response(
        {
            "patient": patient,
            "plan": plan,
            "usage_summary": usage_summary,
            "latest_letter": latest_letter,
        },
        status=status.HTTP_200_OK,
    )


# ---- 4) Letter generation ----
@api_view(["POST"])
def generate_letter(request):
    phone = request.data.get("phone")
    letter_type = request.data.get("letter_type", "coverage_summary")

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0})
    if not plan:
        plan = get_or_create_default_plan()

    usage_summary = fake_usage_summary()

    content = simple_llm_letter(patient, plan, usage_summary, template_type=letter_type)
    redacted = simple_phi_redact(content, patient)
    letter_record = generate_letter_record(patient, plan, redacted, letter_type)

    letters_col.insert_one(letter_record)

    return Response(letter_record, status=status.HTTP_200_OK)


# ---- 5) Download letter ----
@api_view(["GET"])
def download_letter(request, letter_id):
    letter = letters_col.find_one({"letter_id": letter_id}, {"_id": 0})
    if not letter:
        return Response({"error": "Letter not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {"filename": f"letter_{letter_id}.txt", "content": letter["content"]},
        status=status.HTTP_200_OK,
    )


# ---- 6) Chatbot ----
@api_view(["POST"])
def chatbot(request):
    phone = request.data.get("phone")
    message = request.data.get("message", "")

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response(
            {"reply": "Please enter and save your details first so I can access your plan info."},
            status=status.HTTP_200_OK,
        )

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0})
    if not plan:
        plan = get_or_create_default_plan()

    reply = chatbot_reply(message, patient, plan, meds_col)
    return Response({"reply": reply}, status=status.HTTP_200_OK)
