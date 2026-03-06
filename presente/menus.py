from django.urls import reverse
from simple_menu import Menu, MenuItem

Menu.add_item(
    "presente",
    MenuItem(
        "Início",
        reverse("presente:index"),
        icon="bi bi-house-fill",
        exact_url=reverse("presente:index"),
        weight=1,  # controla a ordem,
    ),
)

Menu.add_item(
    "presente",
    MenuItem(
        "Minhas Presenças",
        reverse("presente:my_attendances"),
        icon="bi bi-check2-circle",
        weight=2,  # controla a ordem
    ),
)

Menu.add_item(
    "presente",
    MenuItem(
        "Minhas Atividades",
        reverse("presente:activity_list"),
        icon="bi bi-list-check",
        check=lambda r: r.user.is_authenticated,
        weight=3,  # controla a ordem
    )
)
Menu.add_item(
    "presente",
    MenuItem(
        "Minhas Pontuações",
        reverse("presente:minhas_pontuacoes"),
        icon="bi bi-dice-6",
        check=lambda r: r.user.is_authenticated,
        weight=4,  # controla a ordem
    ),
)

Menu.add_item("presente",
    MenuItem(
        "Ranking",
        reverse("presente:ranking"),
        icon="bi bi-trophy",
        weight=5  # controla a ordem
    )
)
# ADMINISTRAÇÃO section starts here (items below appear under "ADMINISTRAÇÃO" header)

Menu.add_item(
    "presente",
    MenuItem(
        "Atividades",
        reverse("presente:admin_activities"),
        icon="bi bi-list-check",
        check=lambda r: r.user.is_superuser or r.user.is_staff,
        weight=10
    ),
)

Menu.add_item(
    "presente",
    MenuItem(
        "Usuários",
        reverse("users:user_list"),
        icon="bi bi-person",
        check=lambda r: r.user.is_superuser or r.user.is_staff,
        weight=11
    ),
)

Menu.add_item(
    "presente",
    MenuItem(
        "Redes",
        reverse("presente:network_list"),
        icon="bi bi-hdd-network",
        check=lambda r: r.user.is_superuser or r.user.is_staff,
        weight=12
    ),
)
Menu.add_item(
    "presente",
    MenuItem(
            "Eventos",
            reverse("presente:evento_list"),
            icon="bi bi-calendar-event",
            weight=13,  # maior para cair depois da linha de ADMINISTRAÇÃO
            check=lambda r: r.user.is_superuser or r.user.is_staff,

              
            
    ),     
    )
