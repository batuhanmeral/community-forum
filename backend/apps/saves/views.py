from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import SavedItem
from .serializers import SavedItemSerializer, SaveRequestSerializer


class SavedItemListCreateView(generics.ListCreateAPIView):
    serializer_class = SavedItemSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = SavedItem.objects.filter(user=self.request.user).select_related("content_type")
        type_filter = self.request.query_params.get("type")
        if type_filter in ("post", "comment"):
            qs = qs.filter(content_type__model=type_filter)
        return qs

    def create(self, request, *args, **kwargs):
        payload = SaveRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        ct = payload.validated_data["_content_type"]
        object_id = payload.validated_data["object_id"]

        existing = SavedItem.objects.filter(
            user=request.user, content_type=ct, object_id=object_id
        ).first()
        if existing is not None:
            existing.delete()
            return Response({"is_saved": False}, status=status.HTTP_200_OK)

        item = SavedItem.objects.create(
            user=request.user, content_type=ct, object_id=object_id
        )
        return Response(
            {"is_saved": True, "saved": SavedItemSerializer(item, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )
