from django.urls import path
from . import views

app_name = "presente"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "admin-activities/",
        views.AdminActivitiesView.as_view(),
        name="admin_activities",
    ),
    path("activity/", views.ActivityListView.as_view(), name="activity_list"),
    path("activity/add", views.ActivityCreateView.as_view(), name="activity_add"),
    path(
        "activity/<int:pk>/", views.ActivityDetailView.as_view(), name="activity_view"
    ),
    path("minhas-pontuacoes/", views.minhas_pontuacoes, name="minhas_pontuacoes"),
 
    path("ranking/", views.RankingListView.as_view(), name="ranking"),

    path(
        "activity/<int:pk>/update/",
        views.ActivityUpdateView.as_view(),
        name="activity_change",
    ),
    path(
        "activity/<int:pk>/delete/",
        views.ActivityDeleteView.as_view(),
        name="activity_delete",
    ),
    path(
        "activity/<int:pk>/attendances/",
        views.ActivityAttendanceListView.as_view(),
        name="activity_attendances",
    ),
    path(
        "activity/<int:pk>/attendances/export/config/",
        views.ActivityAttendanceExportConfigView.as_view(),
        name="activity_attendance_export_config",
    ),
    path(
        "activity/<int:pk>/attendances/pdf/",
        views.ActivityAttendancePDFView.as_view(),
        name="activity_attendance_pdf",
    ),
    path(
        "activity/<int:pk>/attendances/csv/",
        views.ActivityAttendanceCSVExportView.as_view(),
        name="activity_attendance_csv",
    ),
    path(
        "activity/<int:activity_pk>/attendance/<int:pk>/delete/",
        views.AttendanceDeleteView.as_view(),
        name="attendance_delete",
    ),
    path(
        "eventos/<int:evento_pk>/atividades/",
        views.EventoActivityListView.as_view(),
        name="evento-atividades",
    ),
    # Network CRUD URLs
    path("network/", views.NetworkListView.as_view(), name="network_list"),
    path("network/add", views.NetworkCreateView.as_view(), name="network_add"),
    path("network/<int:pk>/", views.NetworkDetailView.as_view(), name="network_view"),
    path(
        "network/<int:pk>/update/",
        views.NetworkUpdateView.as_view(),
        name="network_change",
    ),
    path(
        "network/<int:pk>/delete/",
        views.NetworkDeleteView.as_view(),
        name="network_delete",
    ),
    # Evento CRUD URLs
    path("evento/", views.EventoListView.as_view(), name="evento_list"),
    path("evento/add", views.EventoCreateView.as_view(), name="evento_add"),
    path("evento/<int:pk>/", views.EventoDetailView.as_view(), name="evento_view"),
    path("evento/<int:pk>/update/", views.EventoUpdateView.as_view(), name="evento_change"),
    path("evento/<int:pk>/delete/", views.EventoDeleteView.as_view(), name="evento_delete"),
    # User attendances
    path("my-attendances/", views.MyAttendancesView.as_view(), name="my_attendances"),
    # Public attendance URLs
    path(
        "a/<str:encoded_id>/",
        views.PublicActivityView.as_view(),
        name="public_activity",
    ),
    path(
        "a/<str:encoded_id>/qr/", views.ActivityQRCodeView.as_view(), name="activity_qr"
    ),
    path("checkin/<str:token>/", views.CheckInView.as_view(), name="checkin"),
]
