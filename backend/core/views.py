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

# -----------------------
# MongoDB CONNECTION
# -----------------------
client = MongoClient(settings.MONGO_URI)

# Optional: debug connection
try:
    client.admin.command("ping")
    print("✅ MongoDB Connected Successfully")
except Exception as e:
    print("❌ MongoDB Connection Error:", e)

db = client[settings.MONGO_DB]

patients_col = db["patients"]
plans_col = db["plans"]
usage_col = db["usage"]
letters_col = db["letters"]
meds_col = db["medications"]
members_col = db["insurance_members"]  # Kaggle healthcare dataset


# -----------------------
# DEFAULT PLAN HELPER
# -----------------------
def get_or_create_default_plan():
    """
    Fallback plan in case Kaggle / insurance_members has no match.
    """
    plan = plans_col.find_one({"plan_id": "BASIC_PLAN"})
    if not plan:
        plan = {
            "plan_id": "BASIC_PLAN",
            "plan_name": "Basic Health Coverage Plan",
            "description": "Covers primary care, specialists, labs, and generic medications.",
        }
        plans_col.insert_one(plan)
    return plan


# -----------------------
# REGISTER PATIENT (USES KAGGLE DATA IF AVAILABLE)
# -----------------------
@api_view(["POST"])
def register_patient(request):
    """
    Registers / updates a patient and tries to map them to a plan
    based on Kaggle healthcare_dataset.csv (loaded into insurance_members).
    """
    name = request.data.get("name", "").strip()
    dob = request.data.get("dob", "").strip()
    phone = request.data.get("phone", "").strip()

    if not (name and dob and phone):
        return Response(
            {"error": "name, dob, phone are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Try to find matching member from Kaggle-derived collection.
    # Adjust field names below to match your CSV mapping.
    member = members_col.find_one(
        {
            "name_lc": name.lower(),
            "dob": dob,
            # If your Kaggle dataset also has phone column mapped, you can include:
            # "phone": phone
        },
        {"_id": 0},
    )

    if member:
        # Build a "plan" object from Kaggle row.
        # The keys here come from how we insert in load_insurance_members().
        plan = {
            "plan_id": member.get("plan_id", "KAGGLE_PLAN"),
            "plan_name": member.get("plan_name", "Kaggle Imported Plan"),
            "description": f"Coverage level: {member.get('coverage_level', 'N/A')}",
            "deductible": member.get("deductible", 0),
            "copay": member.get("copay", 0),
        }
        # Optionally upsert this plan into plans_col so it can be looked up later:
        plans_col.update_one(
            {"plan_id": plan["plan_id"]},
            {"$set": plan},
            upsert=True,
        )
    else:
        # Fallback to default if no Kaggle match.
        plan = get_or_create_default_plan()

    # Upsert patient record
    existing = patients_col.find_one({"phone": phone})
    if existing:
        patients_col.update_one(
            {"phone": phone},
            {
                "$set": {
                    "name": name,
                    "dob": dob,
                    "plan_id": plan["plan_id"],
                }
            },
        )
    else:
        patients_col.insert_one(
            {
                "name": name,
                "dob": dob,
                "phone": phone,
                "plan_id": plan["plan_id"],
            }
        )

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})

    return Response({"patient": patient, "plan": plan}, status=status.HTTP_200_OK)


# -----------------------
# PATIENT DASHBOARD
# -----------------------
@api_view(["GET"])
def get_patient_dashboard(request, phone):
    """
    Returns coverage, usage summary, and latest letter.
    """
    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response({"error": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0}) or get_or_create_default_plan()

    # For demo: fake simple usage summary (you can enrich from usage_col or Kaggle).
    usage_summary = fake_usage_summary()

    latest_letter = letters_col.find_one(
        {"patient_phone": phone},
        {"_id": 0},
        sort=[("created_at", -1)]
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


# -----------------------
# LETTER GENERATION
# -----------------------
@api_view(["POST"])
def generate_letter(request):
    """
    Generates an AI-style letter and stores it in Mongo.
    """
    phone = request.data.get("phone")
    letter_type = request.data.get("letter_type", "coverage_summary")

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response({"error": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0}) or get_or_create_default_plan()
    usage_summary = fake_usage_summary()

    content = simple_llm_letter(patient, plan, usage_summary, template_type=letter_type)
    redacted = simple_phi_redact(content, patient)

    letter_record = generate_letter_record(patient, plan, redacted, letter_type)
    letters_col.insert_one(letter_record)

    return Response(letter_record, status=status.HTTP_200_OK)


@api_view(["GET"])
def download_letter(request, letter_id):
    """
    Returns letter content as plain text (frontend can trigger browser download).
    """
    letter = letters_col.find_one({"letter_id": letter_id}, {"_id": 0})
    if not letter:
        return Response({"error": "Letter not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {"filename": f"letter_{letter_id}.txt", "content": letter["content"]},
        status=status.HTTP_200_OK,
    )


# -----------------------
# CHATBOT
# -----------------------
@api_view(["POST"])
def chatbot(request):
    """
    Simple chatbot for insurance / medication coverage queries.
    """
    phone = request.data.get("phone")
    message = request.data.get("message", "")

    patient = patients_col.find_one({"phone": phone}, {"_id": 0})
    if not patient:
        return Response(
            {"reply": "I could not find your record. Please register first."},
            status=status.HTTP_200_OK,
        )

    plan = plans_col.find_one({"plan_id": patient["plan_id"]}, {"_id": 0}) or get_or_create_default_plan()

    reply = chatbot_reply(message, patient, plan, meds_col)
    return Response({"reply": reply}, status=status.HTTP_200_OK)


# -----------------------
# KAGGLE LOADER (MEDICATIONS) – OPTIONAL
# -----------------------
@api_view(["POST"])
def load_kaggle_data(request):
    """
    Very simple loader: expects CSVs downloaded manually from Kaggle
    and placed into backend/kaggle_data/
    For demo: load a csv with columns: name, covered_plans (semicolon separated)
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    meds_path = os.path.join(base_dir, "kaggle_data", "insurance_members.csv")


    if not os.path.exists(meds_path):
        return Response(
            {"error": "insurance_members.csv not found in kaggle_data/"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    meds_col.delete_many({})

    with open(meds_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            covered_plans = row.get("covered_plans", "").split(";")
            doc = {
                "name": name,
                "name_lc": name.lower(),
                "covered_plans": [p.strip() for p in covered_plans if p.strip()],
            }
            meds_col.insert_one(doc)

    return Response({"status": "Kaggle medications loaded."}, status=status.HTTP_200_OK)


# -----------------------
# KAGGLE LOADER (HEALTHCARE DATASET -> insurance_members)
# -----------------------
@api_view(["POST"])
def load_insurance_members(request):
    """
    Load insurance members from the Kaggle healthcare dataset into Mongo.

    Expected file (already uploaded by you):
        backend/kaggle_data/insurance_members.csv

    IMPORTANT:
        You may need to adjust the column names below to match the actual CSV.

    Example assumed columns:
        - 'Name'
        - 'Date_of_Birth'  (or 'DOB')
        - 'Phone'          (optional)
        - 'InsurancePlan'  (plan name)
        - 'CoverageLevel'  (e.g., Basic / Silver / Gold)
        - 'Annual_Deductible'
        - 'CoPay'

    We'll map them into a standardized internal schema.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "kaggle_data", "insurance_members.csv")

    if not os.path.exists(csv_path):
        return Response(
            {"error": "insurance_members.csv not found in kaggle_data/"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Clear old data
    members_col.delete_many({})

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # 🔴 IMPORTANT: adjust these field names based on your actual CSV columns.
            name = (
                row.get("Name")
                or row.get("name")
                or ""
            ).strip()

            dob = (
                row.get("Date_of_Birth")
                or row.get("DOB")
                or row.get("dob")
                or ""
            ).strip()

            phone = (
                row.get("Phone")
                or row.get("phone")
                or ""
            ).strip()

            plan_name = (
                row.get("InsurancePlan")
                or row.get("Plan_Name")
                or row.get("plan_name")
                or "Kaggle Imported Plan"
            ).strip()

            coverage_level = (
                row.get("CoverageLevel")
                or row.get("coverage_level")
                or "N/A"
            ).strip()

            # Monetary fields - convert safely to float
            def to_float(val, default=0.0):
                try:
                    if val is None or val == "":
                        return default
                    return float(val)
                except ValueError:
                    return default

            deductible = to_float(
                row.get("Annual_Deductible") or row.get("deductible") or 0
            )
            copay = to_float(
                row.get("CoPay") or row.get("copay") or 0
            )

            # Skip rows without a name
            if not name:
                continue

            members_col.insert_one(
                {
                    "name": name,
                    "name_lc": name.lower(),
                    "dob": dob,
                    "phone": phone,
                    "plan_id": f"KAGGLE_{plan_name.replace(' ', '_').upper()}",
                    "plan_name": plan_name,
                    "coverage_level": coverage_level,
                    "deductible": deductible,
                    "copay": copay,
                }
            )

    return Response(
        {"status": "Insurance members loaded from insurance_members.csv."},
        status=status.HTTP_200_OK,
    )
