// Ergonomic aliases over the OpenAPI-generated wire contracts. Do not add
// handwritten transport fields here; regenerate generated.ts from FastAPI.
import type { components } from './generated';

export type ListingSummary = components['schemas']['ListingSummary'];
export type ListingPage = components['schemas']['ListingPage'];
export type ListingDetail = components['schemas']['ListingDetail'];
export type SearchProfile = components['schemas']['SearchProfileResponse'];
export type SearchProfileCreate = components['schemas']['SearchProfileCreate'];
export type Worker = components['schemas']['WorkerResponse'];
export type ManualImport = components['schemas']['ManualImportRequest'];
export type ProblemDetails = components['schemas']['ProblemDetails'];
export type Notification = components['schemas']['NotificationResponse'];
export type ListingEvaluation = components['schemas']['ListingEvaluationResponse'];
export type FeedbackCreate = components['schemas']['FeedbackCreate'];
export type Product = components['schemas']['ProductResponse'];
export type ProductPage = components['schemas']['ProductPage'];
export type ProviderSyncRun = components['schemas']['ProviderSyncRunResponse'];
export type ProviderSyncRunPage = components['schemas']['ProviderSyncRunPage'];
export type ProviderConfiguration = components['schemas']['ProviderConfigurationResponse'];
export type ProviderConfigurationUpsert = components['schemas']['ProviderConfigurationUpsert'];
export type MailImport = components['schemas']['MailImportResponse'];
export type AnalysisJob = components['schemas']['JobResponse'];
export type PriceObservation = components['schemas']['PriceObservationResponse'];
export type ListingImage = components['schemas']['ListingImageResponse'];
export type ImageAccess = components['schemas']['ImageAccessResponse'];

export type SystemStatus = components['schemas']['SystemStatusResponse'];

export type { components, operations, paths } from './generated';
