// الملف ده مش بيشتغل، ده بيتأكد بس إن الأنواع المتولدة بتمسك الغلط زي ما احنا عايزين
// لو أي سطر تحت علامة الخطأ المتوقع بقى سليم التشييك هيفشل
// npm run check
import type { AskOut, DocumentStatus, ErrorOut } from "./index";

// رد سليم بكل حقوله
export const ok: AskOut = { answer: "سنة واحدة", sources: [], usage: null };

// حقل الاستخدام لازم يتبعت حتى لو فاضي
// @ts-expect-error usage is required
export const missingUsage: AskOut = { answer: "x", sources: [] };

// اسم حقل غلط
// @ts-expect-error sorces does not exist
export const typo: AskOut = { answer: "x", sorces: [], usage: null };

// لازم نتأكد إن حقل الاستخدام مش فاضي قبل ما نقرا منه
export function tokens(res: AskOut): number {
  // @ts-expect-error res.usage is possibly null
  const unsafe: number = res.usage.input_tokens;
  return res.usage ? res.usage.input_tokens : unsafe;
}

// الحالة ليها 3 قيم بس
export const ready: DocumentStatus = "ready";
// @ts-expect-error "done" is not a document status
export const done: DocumentStatus = "done";

// رقم الطلب موجود في كل إيرور
export const requestId = (e: ErrorOut): string => e.error.request_id;
