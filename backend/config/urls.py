from django.urls import include, path

urlpatterns = [path("api/", include("analyzer.urls"))]

handler404 = "analyzer.errors.json_404"
handler500 = "analyzer.errors.json_500"
