from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Course, Category, Enrollment, Lesson, Profile, Payment, Message
from .mpesa import stk_push
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User


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

    if course.price == 0:
        Enrollment.objects.get_or_create(student=request.user, course=course)
        return redirect('course_detail', course_id=course.id)

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        payment = Payment.objects.create(
            student=request.user,
            course=course,
            phone_number=phone_number,
            amount=course.price,
            status='pending',
        )
        response = stk_push(
            phone_number=phone_number,
            amount=int(course.price),
            account_reference=f"course-{course.id}",
            transaction_desc=f"Payment for {course.title}",
        )
        payment.checkout_request_id = response.get('CheckoutRequestID', '')
        payment.save()
        return render(request, 'core/payment_pending.html', {'course': course})

    return render(request, 'core/payment_form.html', {'course': course})


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
    unread_count = Message.objects.filter(recipient=request.user, is_read=False).count()

    if request.user.profile.role == 'instructor':
        courses = Course.objects.filter(instructor=request.user)
        total_courses = courses.count()
        total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
        recent_enrollments = Enrollment.objects.filter(course__in=courses).order_by('-enrolled_at')[:5]
        return render(request, 'core/dashboard_instructor.html', {
            'courses': courses,
            'total_courses': total_courses,
            'total_students': total_students,
            'notifications': recent_enrollments,
            'unread_count': unread_count,
        })
    else:
        enrollments = Enrollment.objects.filter(student=request.user)
        total_enrolled = enrollments.count()
        completed = enrollments.filter(completed=True).count()
        payments = Payment.objects.filter(student=request.user).order_by('-created_at')[:5]
        return render(request, 'core/dashboard_student.html', {
            'enrollments': enrollments,
            'total_enrolled': total_enrolled,
            'completed': completed,
            'payments': payments,
            'notifications': payments,
            'unread_count': unread_count,
        })

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar']


@login_required
def profile_view(request):
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'core/profile.html', {'form': form, 'profile': profile})



@login_required
def settings_view(request):
    profile = request.user.profile

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            password_form = PasswordChangeForm(request.user)
            if profile_form.is_valid():
                profile_form.save()
                return redirect('settings')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            profile_form = ProfileForm(instance=profile)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect('settings')
    else:
        profile_form = ProfileForm(instance=profile)
        password_form = PasswordChangeForm(request.user)

    return render(request, 'core/settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': profile,
    })


@login_required
def inbox(request):
    messages = Message.objects.filter(recipient=request.user)
    messages.filter(is_read=False).update(is_read=True)
    return render(request, 'core/inbox.html', {'messages': messages})


@login_required
def send_message(request, recipient_id):
    recipient = get_object_or_404(User, id=recipient_id)

    if request.method == 'POST':
        content = request.POST.get('content')
        course_id = request.POST.get('course_id')
        course = Course.objects.filter(id=course_id).first() if course_id else None
        Message.objects.create(
            sender=request.user,
            recipient=recipient,
            course=course,
            content=content,
        )
        return redirect('inbox')

    return render(request, 'core/send_message.html', {'recipient': recipient})