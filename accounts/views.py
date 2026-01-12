from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from .models import UserProfile


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Create UserProfile for the new user
                UserProfile.objects.create(user=user)
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("accounts:login")
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    # Get the 'next' parameter from query string or POST data
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Validate and redirect to 'next' URL if provided and safe, otherwise use LOGIN_REDIRECT_URL
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts=None
                ):
                    redirect_url = next_url
                else:
                    redirect_url = settings.LOGIN_REDIRECT_URL
                return redirect(redirect_url)
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect(settings.LOGOUT_REDIRECT_URL)
