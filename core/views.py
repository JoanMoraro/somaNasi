from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Course, Category, Enrollment, Lesson, Profile, Payment, Message, StudentProgress, Assignment, AssignmentSubmission, Quiz, Question, QuizResult, Certificate, Achievement
from .mpesa import stk_push
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.http import JsonResponse


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    featured_courses = Course.objects.all()[:3]
    total_courses = Course.objects.count()
    total_students = Enrollment.objects.values('student').distinct().count()
    return render(request, 'core/home.html', {
        'featured_courses': featured_courses,
        'total_courses': total_courses,
        'total_students': total_students,
    })


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
        try:
            response = stk_push(
                phone_number=phone_number,
                amount=int(course.price),
                account_reference=f"course-{course.id}",
                transaction_desc=f"Payment for {course.title}",
            )
            print("MPESA RESPONSE:", response)
            if response.get('ResponseCode') == '0':
                payment.checkout_request_id = response.get('CheckoutRequestID', '')
                payment.save()
                return render(request, 'core/payment_pending.html', {'course': course})
            else:
                payment.status = 'failed'
                payment.save()
                error = response.get('errorMessage', 'M-Pesa request failed')
                return render(request, 'core/payment_form.html', {'course': course, 'error': error})
        except Exception as e:
            print("MPESA ERROR:", str(e))
            payment.status = 'failed'
            payment.save()
            return render(request, 'core/payment_form.html', {'course': course, 'error': str(e)})

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
        progress, _ = StudentProgress.objects.get_or_create(student=request.user)
        return render(request, 'core/dashboard_student.html', {
            'enrollments': enrollments,
            'total_enrolled': total_enrolled,
            'completed': completed,
            'payments': payments,
            'notifications': payments,
            'unread_count': unread_count,
            'xp': progress.xp,
            'streak': progress.streak,
            'badges': progress.badges,
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
    progress, _ = StudentProgress.objects.get_or_create(student=request.user)
    profile_form = ProfileForm(instance=profile)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                if request.POST.get('first_name'):
                    request.user.first_name = request.POST.get('first_name')
                    request.user.save()
                return redirect('settings')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect('settings')

    pref_fields = [
        {'label': 'Learning Goal', 'options': ['Get Certified', 'Learn Skills', 'Career Change'], 'icon': '🎯', 'color': '#8B5CF6'},
        {'label': 'Experience Level', 'options': ['Beginner', 'Intermediate', 'Advanced'], 'icon': '📊', 'color': '#3B82F6'},
        {'label': 'Study Time', 'options': ['< 1 hour/day', '1-3 hours/day', '3-5 hours/day'], 'icon': '⏰', 'color': '#34D399'},
        {'label': 'Preferred Language', 'options': ['English', 'Swahili', 'French'], 'icon': '🌍', 'color': '#F59E0B'},
        {'label': 'Content Type', 'options': ['Video & Text', 'Video Only', 'Text Only'], 'icon': '🎬', 'color': '#EC4899'},
        {'label': 'Difficulty', 'options': ['Easy', 'Medium', 'Hard', 'Mixed'], 'icon': '🔥', 'color': '#EF4444'},
    ]
    connected_accounts = [
        {'name': 'Google', 'icon': '🌐', 'handle': 'Connect your Google account', 'connected': False},
        {'name': 'GitHub', 'icon': '🐙', 'handle': 'Connect your GitHub account', 'connected': False},
        {'name': 'LinkedIn', 'icon': '💼', 'handle': 'Connect your LinkedIn account', 'connected': False},
    ]
    quick_actions = [
        {'icon': 'bi-pencil', 'label': 'Edit Profile', 'url': '/profile/'},
        {'icon': 'bi-lock', 'label': 'Change Password', 'url': '#'},
        {'icon': 'bi-download', 'label': 'Download My Data', 'url': '#'},
        {'icon': 'bi-trash', 'label': 'Deactivate Account', 'url': '#'},
    ]
    privacy_items = [
        {'label': 'Profile Visibility', 'value': 'Public'},
        {'label': 'Activity Status', 'value': 'Friends'},
        {'label': 'Course Progress', 'value': 'Private'},
        {'label': 'Search Visibility', 'value': 'Visible'},
    ]
    storage_items = [
        {'label': 'Course Downloads', 'size': '1.2 GB', 'color': '#8B5CF6'},
        {'label': 'Certificates', 'size': '0.6 GB', 'color': '#3B82F6'},
        {'label': 'Resources', 'size': '0.4 GB', 'color': '#F59E0B'},
        {'label': 'Others', 'size': '0.2 GB', 'color': '#34D399'},
    ]

    return render(request, 'core/settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': profile,
        'xp': progress.xp,
        'pref_fields': pref_fields,
        'connected_accounts': connected_accounts,
        'quick_actions': quick_actions,
        'privacy_items': privacy_items,
        'storage_items': storage_items,
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


@login_required
def assignments(request):
    if request.user.profile.role == 'instructor':
        courses = Course.objects.filter(instructor=request.user)
        assignments = Assignment.objects.filter(course__in=courses)
    else:
        enrollments = Enrollment.objects.filter(student=request.user)
        assignments = Assignment.objects.filter(course__in=enrollments.values('course'))
    return render(request, 'core/assignments.html', {'assignments': assignments})


@login_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=request.user,
            content=content,
        )
        return redirect('assignments')
    return render(request, 'core/submit_assignment.html', {'assignment': assignment})



@login_required
def quizzes(request):
    if request.user.profile.role == 'instructor':
        courses = Course.objects.filter(instructor=request.user)
        quizzes = Quiz.objects.filter(course__in=courses)
    else:
        enrollments = Enrollment.objects.filter(student=request.user)
        quizzes = Quiz.objects.filter(course__in=enrollments.values('course'))
    return render(request, 'core/quizzes.html', {'quizzes': quizzes})


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total = questions.count()
        for question in questions:
            answer = request.POST.get(f'question_{question.id}')
            if answer == question.correct_option:
                score += 1
        QuizResult.objects.create(
            quiz=quiz,
            student=request.user,
            score=score,
            total=total,
        )
        progress, _ = StudentProgress.objects.get_or_create(student=request.user)
        progress.xp += score * 10
        progress.save()
        if score == total:
            Achievement.objects.get_or_create(student=request.user, badge='quiz_master')
        return render(request, 'core/quiz_result.html', {'quiz': quiz, 'score': score, 'total': total})

    return render(request, 'core/take_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def certificates(request):
    certs = Certificate.objects.filter(student=request.user)
    return render(request, 'core/certificates.html', {'certificates': certs})


@login_required
def achievements(request):
    progress, _ = StudentProgress.objects.get_or_create(student=request.user)
    earned = Achievement.objects.filter(student=request.user)
    all_badges = [
        {'key': 'early_bird', 'name': 'Early Bird', 'emoji': '🐦', 'desc': 'Log in 7 days in a row', 'color': '#EF4444'},
        {'key': 'quiz_master', 'name': 'Quiz Master', 'emoji': '🧠', 'desc': 'Score 100% on a quiz', 'color': '#8B5CF6'},
        {'key': 'consistent', 'name': 'Consistent Learner', 'emoji': '🛡️', 'desc': 'Complete 10 lessons', 'color': '#3B82F6'},
        {'key': 'first_course', 'name': 'First Course', 'emoji': '📚', 'desc': 'Enroll in your first course', 'color': '#F59E0B'},
        {'key': 'streak_7', 'name': '7 Day Streak', 'emoji': '🔥', 'desc': 'Maintain a 7 day streak', 'color': '#F97316'},
        {'key': 'streak_30', 'name': '30 Day Streak', 'emoji': '⚡', 'desc': 'Maintain a 30 day streak', 'color': '#34D399'},
    ]
    earned_keys = list(earned.values_list('badge', flat=True))
    for badge in all_badges:
        badge['earned'] = badge['key'] in earned_keys
    return render(request, 'core/achievements.html', {
        'badges': all_badges,
        'xp': progress.xp,
        'streak': progress.streak,
        'earned_count': len(earned_keys),
    })


@login_required
def students(request):
    if request.user.profile.role != 'instructor':
        return redirect('dashboard')
    courses = Course.objects.filter(instructor=request.user)
    enrollments = Enrollment.objects.filter(course__in=courses).select_related('student', 'course')
    return render(request, 'core/students.html', {'enrollments': enrollments, 'courses': courses})



@login_required
def analytics(request):
    if request.user.profile.role != 'instructor':
        return redirect('dashboard')
    return render(request, 'core/analytics.html')

@login_required
def earnings(request):
    if request.user.profile.role != 'instructor':
        return redirect('dashboard')
    return render(request, 'core/earnings.html')


@login_required
def reviews(request):
    if request.user.profile.role != 'instructor':
        return redirect('dashboard')
    courses = Course.objects.filter(instructor=request.user)
    return render(request, 'core/reviews.html', {'courses': courses})


import json
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = data['Body']['stkCallback']
            result_code = result['ResultCode']
            checkout_request_id = result['CheckoutRequestID']

            payment = Payment.objects.filter(checkout_request_id=checkout_request_id).first()
            if not payment:
                return JsonResponse({'status': 'payment not found'})

            if result_code == 0:
                payment.status = 'completed'
                payment.save()
                Enrollment.objects.get_or_create(
                    student=payment.student,
                    course=payment.course,
                )
                progress, _ = StudentProgress.objects.get_or_create(student=payment.student)
                progress.xp += 50
                progress.save()
                Achievement.objects.get_or_create(
                    student=payment.student,
                    badge='first_course'
                )
            else:
                payment.status = 'failed'
                payment.save()

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'ok'})