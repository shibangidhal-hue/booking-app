from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie  # sets the csrftoken cookie so chatbot.js can send it
def home(request):
    return render(request, 'home.html')