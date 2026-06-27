from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Course, Category, Enrollment, Lesson


def course_list(request):
    courses = Course.objects.all()
    categories = Category.objects.all()

    query = request.GET.get('q')
    category_id = request.GET.get('category')

    if query:
        courses = courses.filter(title__icontains=query)
    if category_id:
        courses = courses.filter(category_id=category_id)

    return render(request, 'core/course_list.html', {
        'courses': courses,
        'categories': categories,
        'query': query or '',
        'selected_category': category_id or '',
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


def lesson_detail(request, course_id, lesson_id):
    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()
    return render(request, 'core/lesson_detail.html', {
        'course': course,
        'lesson': lesson,
        'is_enrolled': is_enrolled,
    })
    

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'video_url', 'order']


@login_required
def add_lesson(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.instructor:
        return redirect('course_detail', course_id=course.id)

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = LessonForm()

    return render(request, 'core/add_lesson.html', {'form': form, 'course': course})    


@login_required
def dashboard(request):
    if request.user.profile.role == 'instructor':
        courses = Course.objects.filter(instructor=request.user)
        total_courses = courses.count()
        total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
        return render(request, 'core/dashboard_instructor.html', {
            'courses': courses,
            'total_courses': total_courses,
            'total_students': total_students,
        })
    else:
        enrollments = Enrollment.objects.filter(student=request.user)
        total_enrolled = enrollments.count()
        completed = enrollments.filter(completed=True).count()
        return render(request, 'core/dashboard_student.html', {
            'enrollments': enrollments,
            'total_enrolled': total_enrolled,
            'completed': completed,
        })