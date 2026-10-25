import pytest

from app.main import app

ERROR_REF = "#/components/schemas/ErrorOut"


def response_schema(path: str, method: str, status: str) -> dict:
    responses = app.openapi()["paths"][path][method]["responses"]
    assert status in responses, f"{method.upper()} {path} مش موثّق فيه {status}"
    return responses[status]["content"]["application/json"]["schema"]


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/api/v1/documents/{doc_id}", "get", "404"),
        ("/api/v1/documents/{doc_id}", "delete", "404"),
        ("/api/v1/documents", "post", "413"),
        ("/api/v1/ask", "post", "429"),
    ],
)
def test_service_errors_are_documented(path, method, status):
    assert response_schema(path, method, status) == {"$ref": ERROR_REF}


def test_every_documented_error_uses_error_out():
    # أي رد إيرور موثّق لازم يبقى بنفس الشكل
    # عشان الواجهة الأمامية تتعامل مع كل الإيرورز بطريقة واحدة
    # 4xx / 5xx -> ErrorOut
    wrong = []
    for path, methods in app.openapi()["paths"].items():
        for method, operation in methods.items():
            for status, response in operation["responses"].items():
                if not status.startswith(("4", "5")):
                    continue
                schema = response["content"]["application/json"]["schema"]
                if schema != {"$ref": ERROR_REF}:
                    wrong.append(f"{method.upper()} {path} {status}")

    assert wrong == []
