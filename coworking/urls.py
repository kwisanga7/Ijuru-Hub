from django.urls import path

from . import views


app_name = "coworking"

urlpatterns = [
    path("", views.home, name="home"),
    path("members/profile/edit/", views.profile_edit, name="profile_edit"),
    path("members/profile/card/", views.profile_card, name="profile_card"),
    path("members/<str:username>/qr.png", views.profile_qr, name="profile_qr"),
    path("members/<str:username>/", views.member_profile, name="member_profile"),
    path("community/post/", views.community_post_create, name="community_post_create"),
    path("spaces/", views.listing_list, name="listing_list"),
    path("spaces/<slug:slug>/", views.listing_detail, name="listing_detail"),
    path("spaces/<slug:slug>/book/", views.booking_create, name="booking_create"),
    path("bookings/", views.my_bookings, name="my_bookings"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
    path("notifications/mark-all-read/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("bookings/<int:pk>/", views.booking_detail, name="booking_detail"),
    path("staff/check-in/<uuid:token>/", views.staff_check_in, name="staff_check_in"),
    path("payments/mtn-momo/callback/", views.momo_callback, name="momo_callback"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/spaces/", views.staff_spaces, name="staff_spaces"),
    path("staff/spaces/new/", views.staff_space_edit, name="staff_space_create"),
    path("staff/spaces/<int:pk>/edit/", views.staff_space_edit, name="staff_space_edit"),
    path("staff/bookings/", views.staff_bookings, name="staff_bookings"),
    path("staff/people/", views.staff_people, name="staff_people"),
    path("staff/community/", views.staff_community_posts, name="staff_community_posts"),
    path("staff/community/<int:pk>/<str:action>/", views.staff_community_post_review, name="staff_community_post_review"),
    path("staff/people/create-staff/", views.staff_create_account, name="staff_create_account"),
    path("staff/people/<int:pk>/toggle/", views.staff_toggle_account, name="staff_toggle_account"),
    path("staff/bookings/<int:pk>/<str:action>/", views.staff_booking_review, name="staff_booking_review"),
    path("bookings/<int:pk>/qr.png", views.booking_qr, name="booking_qr"),
]
