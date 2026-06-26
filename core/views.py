from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Course, Category, Enrollment


def course_list(request):
    courses = Course.objects.all()
    categories = Category.objects.all()
    return render(request, 'core/course_list.html', {
        'courses':courses,
        'categories': categories,
    })
    
def course_detail(request, course_id):
    course = get_object_or_404(Course, id= course_id)
    lessons = course.lessons.all() 
    return render(request, 'core/course_detail.html', {
        'course': course,
        'lessons': lessons,
    })   


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'core/signup.html', {'form': form})

@login_required
def enroll(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(student=request.user, course=course)
    return redirect('course_detail', course_id=course.id)


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'price']


@login_required
def create_course(request):
    if request.user.profile.role != 'instructor':
        return redirect('course_list')

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = CourseForm()
    return render(request, 'core/create_course.html', {'form': form})


@login_required
def my_courses(request):
    if request.user.profile.role != 'instructor':
        return redirect('course_list')
    courses = Course.objects.filter(instructor=request.user)
    return render(request, 'core/my_courses.html', {'courses': courses})


@login_required
def my_enrollments(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    return render(request, 'core/my_enrollments.html', {'enrollments': enrollments})