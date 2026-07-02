from django.contrib import admin
from .models import Category, Profile, Course, Lesson, Enrollment, Payment, Message, StudentProgress


admin.site.register(Category)
admin.site.register(Profile)
admin.site.register(Course)
admin.site.register(Lesson)
admin.site.register(Enrollment)
admin.site.register(Payment)
admin.site.register(Message)
admin.site.register(StudentProgress)

