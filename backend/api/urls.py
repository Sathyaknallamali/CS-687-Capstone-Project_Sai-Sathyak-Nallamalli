from django.urls import path
from . import views

urlpatterns = [
    path('patient/register/', views.register_patient),
    path('patient/<str:phone>/', views.get_patient_dashboard),

    path('letters/generate/', views.generate_letter),
    path('letters/<str:letter_id>/download/', views.download_letter),

    path('chatbot/', views.chatbot),

    path('init/load_insurance_members/', views.load_insurance_members),
]
