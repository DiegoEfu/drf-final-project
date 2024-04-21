from django.urls import path, include
from .views import *

urlpatterns = [
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),

    path('menu-items', MenuItemsView.as_view()),
    path('menu-items/<int:menuItem>', MenuItemView.as_view()),

    path('groups/manager/users', ManagersView.as_view()),
    path('groups/manager/users/<int:userId>', ManagerDeleteView.as_view()),
    path('groups/manager/delivery-crew/users', DeliveryCrewUsersView.as_view()),
    path('groups/manager/delivery-crew/users/<int:userId>', RemoveDeliveryCrewUserView.as_view()),

    path('cart/menu-items', CustomerCartView.as_view()),

    path('orders/', OrdersView.as_view()),
    path('orders/<int:orderId>', OrderView.as_view()),
]
