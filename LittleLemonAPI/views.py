from rest_framework import generics
from django.shortcuts import get_object_or_404
from django.http.response import JsonResponse, HttpResponseBadRequest
from .serializers import MenuItemSerializer, UserSerializer, UserCartSerializer, UserOrdersSerializer
from .models import MenuItem, OrderItem, Cart, Order
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.contrib.auth.models import User, Group
from rest_framework.response import Response
from .permissions import *
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

# Create your views here.

# Mixins to avoid duplicate code

class AdminsForPostMixin():
    def get_permissions(self):
        print(self.request.method)
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsManager()]
        
        return [AllowAny()]
    

class ThrottleForAnonsAndUsersMixin():
    throttle_classes = [AnonRateThrottle, UserRateThrottle]


# Views

class MenuItemsView(AdminsForPostMixin, ThrottleForAnonsAndUsersMixin, generics.ListAPIView, generics.ListCreateAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    ordering_fields = ['price']
    search_fields = ['title']


class MenuItemView(generics.RetrieveAPIView, generics.RetrieveUpdateDestroyAPIView, AdminsForPostMixin, ThrottleForAnonsAndUsersMixin):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer


class ManagersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    queryset = User.objects.filter(groups__name='Managers')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        username = request.data['username']
        if username:
            user = get_object_or_404(User, username=username)
            manager_group = Group.objects.get(name='manager')
            manager_group.user_set.add(user)
            return JsonResponse(status=201, data={'message':'User added to Manager Group'})


class ManagerDeleteView(generics.DestroyAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.filter(groups__name='manager')

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        user = get_object_or_404(User, pk=pk)
        managers = Group.objects.get(name='manager')
        managers.user_set.remove(user)
        return JsonResponse(status=200, data={'message':'User removed from manager group'})


class DeliveryCrewUsersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    queryset = User.objects.filter(groups__name='delivery-crew')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, *args, **kwargs):
        username = request.data['username']
        if username:
            user = get_object_or_404(User, username=username)
            crew = Group.objects.get(name='delivery-crew')
            crew.user_set.add(user)
            return JsonResponse(status=201, data={'message':'User added to delivery-crew group'})


class RemoveDeliveryCrewUserView(generics.RetrieveDestroyAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = User.objects.filter(groups__name='delivery-crew')

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        user = get_object_or_404(User, pk=pk)
        managers = Group.objects.get(name='delivery-crew')
        managers.user_set.remove(user)
        return JsonResponse(status=201, data={'message':'User removed from the delivery-crew group'})


class CustomerCartView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    serializer_class = UserCartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self, *args, **kwargs):
        cart = Cart.objects.filter(user=self.request.user)
        return cart

    def post(self, request, *arg, **kwargs):
        serialized_item = UserCartSerializer(data=request.data)
        serialized_item.is_valid(raise_exception=True)
        id = request.data['menuitem']
        quantity = request.data['quantity']
        item = get_object_or_404(MenuItem, id=id)
        price = int(quantity) * item.price
        try:
            Cart.objects.create(user=request.user, quantity=quantity, unit_price=item.price, price=price, menuitem_id=id)
        except:
            return JsonResponse(status=409, data={'message':'Item already in cart'})
        return JsonResponse(status=201, data={'message':'Item added to cart!'})


    def delete(self, request, *arg, **kwargs):
        if request.data['menuitem']:
            serialized_item = UserCartSerializer(data=request.data)
            serialized_item.is_valid(raise_exception=True)
            menuitem = request.data['menuitem']
            cart = get_object_or_404(Cart, user=request.user, menuitem=menuitem )
            cart.delete()
            return JsonResponse(status=200, data={'message':'Item removed from cart'})
        else:
            Cart.objects.filter(user=request.user).delete()
            return JsonResponse(status=201, data={'message':'All Items removed from cart'})


class OrdersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserOrdersSerializer
        
    def get_queryset(self, *args, **kwargs):
        if self.request.user.groups.filter(name='Managers').exists() or self.request.user.is_superuser == True :
            query = Order.objects.all()
        elif self.request.user.groups.filter(name='Delivery crew').exists():
            query = Order.objects.filter(delivery_crew=self.request.user)
        else:
            query = Order.objects.filter(user=self.request.user)
        return query

    def get_permissions(self):
        
        if self.request.method == 'GET' or 'POST' : 
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsAdminUser]
        return[permission() for permission in permission_classes]

    def post(self, request, *args, **kwargs):
        cart = Cart.objects.filter(user=request.user)

        if cart.count() == 0:
            return HttpResponseBadRequest()
        
        total = sum([item.total() for item in cart])
        order = Order.objects.create(user=request.user, status=False, total=total)
        
        for i in cart.values():
            menuitem = get_object_or_404(MenuItem, id=i['menuitem_id'])
            orderitem = OrderItem.objects.create(order=order, menuitem=menuitem, quantity=i['quantity'])
            orderitem.save()
        
        cart.delete()
        return JsonResponse(status=201, data={'message':'Your order has been placed! Your order number: {}'.format(str(order.id))})


class OrderView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserOrdersSerializer
    
    def get_permissions(self):
        order = Order.objects.get(pk=self.kwargs['pk'])
        if self.request.user == order.user and self.request.method == 'GET':
            permission_classes = [IsAuthenticated]
        elif self.request.method == 'PUT' or self.request.method == 'DELETE':
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated, IsAdminUser]
        return[permission() for permission in permission_classes] 

    def get_queryset(self, *args, **kwargs):
            query = OrderItem.objects.filter(order_id=self.kwargs['pk'])
            return query

    def patch(self, request, *args, **kwargs):
        order = Order.objects.get(pk=self.kwargs['pk'])
        order.status = not order.status
        order.save()
        return JsonResponse(status=200, data={'message':'Status of order #'+ str(order.id)+' changed to '+str(order.status)})

    def put(self, request, *args, **kwargs):
        serialized_item = UserOrdersSerializer(data=request.data)
        serialized_item.is_valid(raise_exception=True)
        order_pk = self.kwargs['pk']
        crew_pk = request.data['delivery_crew'] 
        order = get_object_or_404(Order, pk=order_pk)
        crew = get_object_or_404(User, pk=crew_pk)
        order.delivery_crew = crew
        order.save()
        return JsonResponse(status=201, data={'message':str(crew.username)+' was assigned to order #'+str(order.id)})

    def delete(self, request, *args, **kwargs):
        order = Order.objects.get(pk=self.kwargs['pk'])
        order_number = str(order.id)
        order.delete()
        return JsonResponse(status=200, data={'message':'Order #{} was deleted'.format(order_number)})