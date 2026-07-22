# ADR 0001: Modulares Monorepo

Status: angenommen

Die Backend-Domäne bleibt in kleinen Python-Paketen. TypeScript-Clients werden aus OpenAPI und
JSON-Schemas erzeugt. Dadurch existiert nur eine Implementierung von Scoring, Providerverträgen
und Autorisierungsregeln, während Angular und eine spätere ERP-Integration stabile Wire-Verträge
verwenden können.
