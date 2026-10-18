# DocuMind API

واجهة SaaS بـ FastAPI: كل شركة بترفع ملفاتها النصية، وتسأل أسئلة وتاخد الإجابة من ملفاتها هي بس.
دلوقتي الإجابة بتيجي من بحث بالكلمات، وبعد كده هيبقى ذكاء اصطناعي.

## التشغيل

```bash
uv sync
cp .env.example .env   # وغيّر المفاتيح اللي فيه
uv run fastapi dev
```

صفحة التوثيق هتلاقيها على http://127.0.0.1:8000/docs، ودوس **Authorize** وحط الـ API key بتاع الشركة.

## الإعدادات

بتتقري من متغيرات البيئة أو من ملف `.env`.

| المتغير | الافتراضي | يعني إيه |
|---|---|---|
| `ORGS` | `[]` | الشركات بصيغة JSON: `[{"id": "...", "name": "...", "api_key": "..."}]`، وكل شركة بمفتاح مختلف |
| `MAX_UPLOAD_BYTES` | `2097152` | أقصى حجم للملف (2 ميجا) |
| `DAILY_QUESTION_QUOTA` | `20` | أقصى عدد أسئلة لكل شركة في اليوم (بتوقيت UTC) |
| `ENVIRONMENT` | `development` | `development` أو `staging` أو `production` |
| `DEBUG` | `false` | **لازم تفضل `false` برا جهازك**، لأنها بتعرض تفاصيل الأخطاء للعميل |

مفتاح حقيقي تعمله بالأمر ده:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## الـ endpoints

كل حاجة تحت `/api/v1` لازم تتبعت معاها هيدر `X-API-Key`.

| الطريقة | المسار | بيعمل إيه |
|---|---|---|
| GET | `/health` | حالة السيرفر ونسخته، ومش محتاج مفتاح |
| GET | `/api/v1/me` | الشركة صاحبة المفتاح |
| POST | `/api/v1/documents` | رفع ملف `.txt` أو `.md`، وبيرجع `202` والملف بيتقسم في الخلفية |
| GET | `/api/v1/documents` | ملفات الشركة، بـ `status` و`limit` و`after` لتقسيم الصفحات |
| GET | `/api/v1/documents/{id}` | ملف واحد وحالته: `processing` أو `ready` أو `failed` |
| DELETE | `/api/v1/documents/{id}` | مسح الملف وفقراته، وبيرجع `204` |
| POST | `/api/v1/ask` | `{"question": "..."}` من 3 لـ 500 حرف، وبيرجع الإجابة ومصادرها |

مثال:

```bash
curl -X POST localhost:8000/api/v1/documents -H "X-API-Key: dev-acme-change-me" -F "file=@notes.txt"
curl -X POST localhost:8000/api/v1/ask -H "X-API-Key: dev-acme-change-me" \
  -H "Content-Type: application/json" -d '{"question": "ما هي مدة العقد؟"}'
```

## الإيرورز

كل الإيرورز بترجع بنفس الشكل:

```json
{"error": {"code": "quota_exceeded", "message": "خلصت حد الأسئلة النهارده (20 سؤال)، جرّب تاني بكره", "request_id": "3f2a..."}}
```

| الكود | الحالة | امتى |
|---|---|---|
| `missing_api_key` / `invalid_api_key` | 401 | المفتاح مش موجود أو غلط |
| `document_not_found` | 404 | الملف مش موجود أو بتاع شركة تانية |
| `unsupported_file_type` | 422 | نوع الملف مش `.txt` أو `.md` |
| `file_too_large` | 413 | الملف أكبر من `MAX_UPLOAD_BYTES` |
| `validation_error` | 422 | البيانات غلط، والتفاصيل في `details` |
| `quota_exceeded` | 429 | الشركة خلصت أسئلة النهارده |
| `not_found` / `method_not_allowed` | 404 / 405 | المسار مش موجود أو الطريقة غلط |
| `internal_error` | 500 | خطأ عندنا: رسالة عامة للعميل، والتفاصيل كلها في السجل |

لو الملف فشل وهو بيتقسم، بيرجع `"status": "failed"` والسبب في `error`، زي إنه فاضي أو مش UTF-8.

كل رد معاه هيدر `X-Request-Id`، وكل سطر في السجل معاه نفس الرقم. ولو عميل اشتكى من خطأ، دوّر برقم الطلب بتاعه في السجل.

## الهيكل

```
app/api/v1        routers رفيعة، بتستقبل الطلب وترجّع الرد بس
app/services      منطق البيزنس
app/repositories  التخزين (في الذاكرة دلوقتي)، وكل دالة بتاخد org_id
app/schemas       شكل الطلبات والردود
app/core          الإعدادات والاعتماديات والإيرورز والسجل
```

الـ router بيكلم الـ service بس، ومبيكلمش الـ repository مباشرة. وعزل الشركات بيحصل في الـ repositories: أي ملف بتاع شركة تانية بيرجع كأنه مش موجود.

## التستات

```bash
uv run pytest
```
