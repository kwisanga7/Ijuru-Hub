from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from pathlib import Path
import re
import subprocess
import tempfile

from .models import Booking, CommunityPost, MemberProfile, SpaceListing


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class MemberProfileForm(forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = ("photo", "display_name", "job_title", "company", "bio", "website", "public_email", "show_email")
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].label = "Profile picture"
        self.fields["photo"].help_text = "Choose a clear image of yourself. Maximum file size: 5 MB."
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if isinstance(photo, UploadedFile) and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Choose an image smaller than 5 MB.")
        return photo


class CommunityPostForm(forms.ModelForm):
    class Meta:
        model = CommunityPost
        fields = ("body", "media")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].label = "Description"
        self.fields["body"].help_text = "Keep your description under 300 words."
        self.fields["media"].label = "Photo or video"
        self.fields["media"].required = True
        self.fields["media"].help_text = "Add one photo or video (up to 100 MB). Videos must be 2 minutes or shorter."
        self.fields["media"].widget.attrs.update({"accept": "image/*,video/*"})

    def clean_body(self):
        description = self.cleaned_data["body"].strip()
        if len(description.split()) >= 300:
            raise forms.ValidationError("Keep your description under 300 words (maximum 299).")
        return description

    def clean_media(self):
        media = self.cleaned_data.get("media")
        if not media:
            return media
        if media.size > 100 * 1024 * 1024:
            raise forms.ValidationError("Choose a file smaller than 100 MB.")
        extension = Path(media.name).suffix.lower()
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
        video_extensions = {".mp4", ".mov", ".webm", ".m4v", ".ogv"}
        if extension not in image_extensions | video_extensions:
            raise forms.ValidationError("Choose an image or video file.")
        if extension in image_extensions:
            try:
                from PIL import Image
                image = Image.open(media)
                image.verify()
                media.seek(0)
            except Exception:
                raise forms.ValidationError("This image file could not be opened.")
        else:
            self._validate_video_duration(media, extension)
        return media

    @staticmethod
    def _validate_video_duration(media, extension):
        temporary_path = None
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporary_file:
                temporary_path = temporary_file.name
                for chunk in media.chunks():
                    temporary_file.write(chunk)
            media.seek(0)
            result = subprocess.run(
                [get_ffmpeg_exe(), "-hide_banner", "-i", temporary_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            match = re.search(r"Duration:\s*(\d+):(\d{2}):(\d+(?:\.\d+)?)", output)
            if not match:
                raise forms.ValidationError("The video duration could not be verified. Try a standard MP4 or WebM video.")
            hours, minutes, seconds = match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            if duration > 120:
                raise forms.ValidationError("Videos must be 2 minutes or shorter.")
        except forms.ValidationError:
            raise
        except (ImportError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            raise forms.ValidationError("Video duration checking is unavailable. Please try again later.") from exc
        finally:
            media.seek(0)
            if temporary_path:
                try:
                    Path(temporary_path).unlink(missing_ok=True)
                except OSError:
                    pass

class BookingRequestForm(forms.Form):
    period = forms.ChoiceField(choices=Booking.Period.choices, label="Booking period")
    starts_on = forms.DateField(
        label="Start date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    momo_phone_number = forms.CharField(
        required=False,
        max_length=24,
        label="MTN MoMo number",
        help_text="Enter the phone number that will receive the payment approval prompt, for example +250 78X XXX XXX.",
    )
    payment_reference = forms.CharField(required=False, max_length=140, label="Payment reference (manual payment)")

    def clean_momo_phone_number(self):
        value = self.cleaned_data["momo_phone_number"].strip()
        if not value:
            return ""
        digits = "".join(character for character in value if character.isdigit())
        if digits.startswith("0"):
            digits = "250" + digits[1:]
        elif digits.startswith("7"):
            digits = "250" + digits
        if len(digits) != 12 or not digits.startswith("250"):
            raise forms.ValidationError("Enter a valid Rwanda mobile number, such as +250 78X XXX XXX.")
        return digits


class StaffBookingForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True, is_staff=False).order_by("username"),
        label="Customer",
        help_text="Choose the member who will pay for this booking.",
    )
    listing = forms.ModelChoiceField(
        queryset=SpaceListing.objects.filter(is_active=True).order_by("name"),
        label="Space",
    )
    period = forms.ChoiceField(choices=Booking.Period.choices, label="Booking period")
    starts_on = forms.DateField(
        label="Start date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    momo_phone_number = forms.CharField(
        max_length=24,
        label="Customer’s MTN MoMo number",
        help_text="The payment approval request will be sent to the customer’s phone when MoMo is enabled.",
    )

    def clean_momo_phone_number(self):
        value = self.cleaned_data["momo_phone_number"].strip()
        digits = "".join(character for character in value if character.isdigit())
        if digits.startswith("0"):
            digits = "250" + digits[1:]
        elif digits.startswith("7"):
            digits = "250" + digits
        if len(digits) != 12 or not digits.startswith("250"):
            raise forms.ValidationError("Enter a valid Rwanda mobile number, such as +250 78X XXX XXX.")
        return digits


class SpaceListingForm(forms.ModelForm):
    class Meta:
        model = SpaceListing
        fields = (
            "name", "slug", "category", "description", "quantity", "max_people",
            "currency_code", "daily_price", "weekly_price", "monthly_price", "photo", "is_active",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Leave blank to create a web address from the space name."

    def clean_slug(self):
        slug = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name", ""))
        candidate, suffix = slug, 2
        while SpaceListing.objects.filter(slug=candidate).exclude(pk=self.instance.pk).exists():
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate


class StaffAccountCreationForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_staff = True
        user.is_superuser = False
        if commit:
            user.save()
        return user
