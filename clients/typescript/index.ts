// أسماء قصيرة للأنواع اللي متولدة من الباك إند
// والملف المتولد نفسه متعدلوش بإيدك عشان أي تعديل هيتمسح مع التوليد الجاي
// schema.d.ts <- npm run generate
import type { components, paths } from "./schema";

export type { components, paths };

type Schemas = components["schemas"];

// الطلبات
export type AskIn = Schemas["AskIn"];

// الردود
export type AskOut = Schemas["AskOut"];
export type SourceOut = Schemas["SourceOut"];
export type UsageOut = Schemas["UsageOut"];
export type DocumentOut = Schemas["DocumentOut"];
export type DocumentListOut = Schemas["DocumentListOut"];
export type DocumentStatus = DocumentOut["status"];
export type OrgOut = Schemas["OrgOut"];
export type HealthOut = Schemas["HealthOut"];

// شكل أي إيرور راجع من الواجهة
export type ErrorOut = Schemas["ErrorOut"];
export type ErrorDetail = Schemas["ErrorDetail"];
