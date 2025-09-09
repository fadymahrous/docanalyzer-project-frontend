from django.urls import path,include
from . import views

app_name = "home_app"

urlpatterns = [
    path('',views.home_page,name='home_page'),
    path('upload',views.upload_file,name='upload'),
    path('mydocuments',views.my_documents,name='mydocuments'),
    path('editdocument/<path:file_key_passed>',views.editdocument,name='editdocument'),
]



