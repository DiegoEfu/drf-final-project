from rest_framework import generics
from django.shortcuts import get_object_or_404
from django.http.response import JsonResponse, HttpResponseBadRequest
from .serializers import MenuItemSerializer, UserSerializer, UserCartSerializer, OrderItemSerializer, UserOrdersSerializer
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


class MenuItemView(ThrottleForAnonsAndUsersMixin, generics.RetrieveAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    lookup_field = 'id'
    lookup_url_kwarg = "menuItem"

    def get_permissions(self):
        print(self.request.method)
        if self.request.method in ['POST', 'PUT', 'DELETE']:
            return [IsAuthenticated(), IsManager()]
        
        return [AllowAny()]


class ManagersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    queryset = User.objects.filter(groups__name='manager')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, *args, **kwargs):
        username = request.data['username']
        if username:
            user = get_object_or_404(User, username=username)
            manager_group = Group.objects.get(name='manager')
            manager_group.user_set.add(user)
            return JsonResponse(status=201, data={'message':'User added to Manager Group.'})


class ManagerDeleteView(generics.DestroyAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager]
    queryset = User.objects.filter(groups__name='manager')

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs['userId']
        user = get_object_or_404(User, pk=pk)
        managers = Group.objects.get(name='manager')
        managers.user_set.remove(user)
        return JsonResponse(status=200, data={'message':'User removed from manager Group.'})


class DeliveryCrewUsersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    queryset = User.objects.filter(groups__name='delivery-crew')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, *args, **kwargs):
        username = request.data['username']
        if username:
            user = get_object_or_404(User, username=username)
            crew = Group.objects.get(name='delivery-crew')
            crew.user_set.add(user)
            return JsonResponse(status=201, data={'message':'User added to delivery-crew Group.'})


class RemoveDeliveryCrewUserView(generics.RetrieveDestroyAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager]
    queryset = User.objects.filter(groups__name='delivery-crew')

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs['userId']
        user = get_object_or_404(User, pk=pk)
        managers = Group.objects.get(name='delivery-crew')
        managers.user_set.remove(user)
        return JsonResponse(status=201, data={'message':'User removed from the delivery-crew Group.'})


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
        except Exception as e:
            print(str(e))
            return JsonResponse(status=409, data={'message':'Item already in cart'})
        return JsonResponse(status=201, data={'message':'Item added to cart!'})


    def delete(self, request, *arg, **kwargs):
        Cart.objects.filter(user=request.user).delete()
        return JsonResponse(status=201, data={'message':'All items were removed from the cart.'})


class OrdersView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserOrdersSerializer
        
    def get_queryset(self, *args, **kwargs):
        if self.request.user.groups.filter(name='manager').exists() or self.request.user.is_superuser:
            query = Order.objects.all()
        elif self.request.user.groups.filter(name='delivery-crew').exists():
            query = Order.objects.filter(delivery_crew=self.request.user)
        else:
            query = Order.objects.filter(user=self.request.user)
        return query

    def get_permissions(self):
        
        if self.request.method in ['GET', 'POST']: 
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
            orderitem = OrderItem.objects.create(order=order, unit_price=i['unit_price'], price=i['price'], menuitem=menuitem, quantity=i['quantity'])
            orderitem.save()
        
        cart.delete()
        return JsonResponse(status=201, data={'message':'Your order has been placed! Your order number: {}'.format(str(order.id))})


class OrderView(generics.ListCreateAPIView, ThrottleForAnonsAndUsersMixin):
    serializer_class = UserOrdersSerializer
    
    def get_permissions(self):
        if(self.request.method == 'DELETE'):
            permission_classes = [IsAuthenticated, IsManager]
        elif(self.request.method in ['PUT', 'PATCH', 'GET']):            
            permission_classes = [IsAuthenticated]
        return[permission() for permission in permission_classes] 

    def get_queryset(self, *args, **kwargs):
        query = Order.objects.filter(pk=self.kwargs['orderId'])
        return query
    
    def get(self, request, *args, **kwargs):
        if(request.user.groups.filter(name="manager").exists()):
            return super().get(request, *args, **kwargs)
        elif(request.user.groups.filter(name="delivery-crew").exists()):
            if(self.get_queryset()[0].delivery_crew == request.user):
                return super().get(request, *args, **kwargs)
            elif(self.get_queryset()[0].user == request.user):
                return super().get(request, *args, **kwargs)
        elif(self.get_queryset()[0].user == request.user):
                return super().get(request, *args, **kwargs)
        
        return JsonResponse(status = 403, data={"message": "You don't have the required permissions."})
    
    def update_data(self, request, order):
        user = request.user

        if(user.groups.filter(name='manager').exists()):
            serialized_item = UserOrdersSerializer(data=request.data)
            serialized_item.is_valid(raise_exception=True)
            order_pk = self.kwargs['orderId']
            crew_pk = request.data['delivery_crew'] 
            order = get_object_or_404(Order, pk=order_pk)
            crew = get_object_or_404(User, pk=crew_pk)
            if(crew.groups.filter(name="delivery-crew").exists()):
                order.delivery_crew = crew
                order.save()
                return JsonResponse(status=201, data={'message': f'Updated. {crew.username} was assigned to order #{order.id}'})
            else:
                return HttpResponseBadRequest()
        elif(user.groups.filter(name='delivery-crew').exists()):
            print("B")
            order = Order.objects.get(pk=self.kwargs['orderId'])
            if(order.delivery_crew and order.delivery_crew.pk == request.user.pk):
                order.status = request.data.get('status')
                order.save()
                return JsonResponse(status=200, data={'message': f'Status of order #{order.id} changed to {order.status}.'})
            else:
                return JsonResponse(status = 403, data={'message': "You are not the delivery crew assigned to this order."})
        else: # Customer
            print("C")
            if(request.data):
                serialized_item = UserOrdersSerializer(data=request.data, instance=Order.objects.get(pk=self.kwargs['orderId']))
                if(request.user.pk == serialized_item.instance.user.pk):
                    serialized_item.is_valid(raise_exception=True)
                    serialized_item.save()
                    return JsonResponse(status=201, data={'message': f'Order Updated.'})
                else:
                    return JsonResponse(status = 403, data={'message': "You are not the owner of the order."})
            else:
                return HttpResponseBadRequest()

    def patch(self, request, *args, **kwargs):
        return self.update_data(request, Order.objects.get(pk = kwargs.get('orderId')))

    def put(self, request, *args, **kwargs):
        return self.update_data(request, Order.objects.get(pk = kwargs.get('orderId')))

    def delete(self, request, *args, **kwargs):
        order = Order.objects.get(pk=self.kwargs['orderId'])
        order_number = str(order.id)
        order.delete()
        return JsonResponse(status=200, data={'message':f'Order #{order_number} was deleted.'})
    