from rest_framework.response import Response


def success(data=None, *, meta=None, status=200):
    return Response({"success": True, "data": data, "meta": meta, "error": None}, status=status)


def error(code, message, *, fields=None, status=400):
    return Response(
        {
            "success": False,
            "data": None,
            "meta": None,
            "error": {"code": code, "message": message, "fields": fields or {}},
        },
        status=status,
    )
