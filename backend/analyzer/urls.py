from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("health/live", views.LiveView.as_view(), name="health-live"),
    path("uploads", views.UploadCreateView.as_view(), name="upload-create"),
    path("uploads/<uuid:upload_id>/complete", views.UploadCompleteView.as_view(), name="upload-complete"),
    path("analyses", views.AnalysisListCreateView.as_view(), name="analyses"),
    path("analyses/sample/<str:name>", views.SampleAnalysisView.as_view(), name="analysis-sample"),
    path("analyses/<uuid:analysis_id>", views.AnalysisDetailView.as_view(), name="analysis-detail"),
    path("sample-size", views.SampleSizeView.as_view(), name="sample-size"),
    path("reports", views.ReportsView.as_view(), name="reports"),
]
