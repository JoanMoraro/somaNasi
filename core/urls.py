from django.urls import path
from . import views

urlpatterns = [
    path('', views.course_list, name='course_list'),
    path('course/<int:course_id>/', views.course_detail, name= 'course_detail'),
    path('signup/', views.signup, name='signup'),
    path('enroll/<int:course_id>/', views.enroll, name='enroll'),
    path('course/create/', views.create_course, name='create_course'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('my-enrollments/', views.my_enrollments, name='my_enrollments'),
    path('course/<int:course_id>/lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('course/<int:course_id>/add-lesson/', views.add_lesson, name='add_lesson'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('inbox/', views.inbox, name='inbox'),
    path('message/<int:recipient_id>/', views.send_message, name='send_message'),
    
]
