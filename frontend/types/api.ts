import type { components } from './api-schema'

type Schemas = components['schemas']

// rates
export type CurrencyInfo = Schemas['CurrencyInfo']
export type CurrenciesResponse = Schemas['CurrenciesResponse']
export type SinglePairResponse = Schemas['SinglePairResponse']
export type BaseRatesResponse = Schemas['BaseRatesResponse']
export type RatePoint = Schemas['RatePoint']
export type HistoryPoint = Schemas['HistoryPoint']
export type HistoryResponse = Schemas['HistoryResponse']

// sources
export type SourceInfo = Schemas['SourceInfo']
export type SourceHealthInfo = Schemas['SourceHealthInfo']
export type SourcesResponse = Schemas['SourcesResponse']

// usage
export type UsageDayPoint = Schemas['UsageDayPoint']
export type UsageEndpointPoint = Schemas['UsageEndpointPoint']
export type UsageSummaryResponse = Schemas['UsageSummaryResponse']

// auth
export type UserMe = Schemas['UserMe']
export type VerifyResponse = Schemas['VerifyResponse']
export type RequestLinkResponse = Schemas['RequestLinkResponse']
export type LogoutResponse = Schemas['LogoutResponse']

// api key groups + keys
export type GroupInfo = Schemas['GroupInfo']
export type GroupsResponse = Schemas['GroupsResponse']
export type KeyInfo = Schemas['KeyInfo']
export type KeysResponse = Schemas['KeysResponse']
export type KeyCreatedResponse = Schemas['KeyCreatedResponse']

// admin
export type AuditEntryInfo = Schemas['AuditEntryInfo']
export type AuditLogResponse = Schemas['AuditLogResponse']
