from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("uploads", views.UploadCreateView.as_view(), name="upload-create"),
    path("uploads/<uuid:upload_id>/complete", views.UploadCompleteView.as_view(), name="upload-complete"),
]
