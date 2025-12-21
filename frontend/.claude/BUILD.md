# Frontend BUILD.md - Frontend Build Control Document

**LAST VERIFIED**: 2024-12-21 22:30 UTC
**STATUS**: STABLE (Backend refactoring in progress)

---

## CRITICAL: FRONTEND IS SECONDARY

The current refactoring effort is focused on the BACKEND. Frontend changes should only be made:
1. After backend API changes are complete
2. To add new endpoints for claims/issues/gates
3. To display new data from the auditable build system

**DO NOT** start frontend work until backend Phase 5 is complete.

---

## FRONTEND STRUCTURE

```
frontend/
├── src/
│   ├── api.ts              # API client (19KB) - central API layer
│   ├── App.tsx             # Main app with routing
│   ├── main.tsx            # Entry point
│   ├── styles.css          # Global styles
│   ├── components/         # Reusable components
│   │   ├── Layout.tsx      # Main layout wrapper
│   │   ├── DocxTemplateEditor.tsx  # DOCX template editor (40KB)
│   │   ├── ProgressIndicator.tsx   # Progress display
│   │   └── SourceCard.tsx          # Source citation card
│   ├── pages/              # Route pages
│   │   ├── WritePage.tsx           # Main procedure writing
│   │   ├── RunPage.tsx             # Run details view
│   │   ├── RunsPage.tsx            # Run history list
│   │   ├── SettingsPage.tsx        # App settings
│   │   ├── SourcesPage.tsx         # Source management
│   │   ├── ProtocolsPage.tsx       # Protocol library
│   │   ├── TemplatesPage.tsx       # Template management
│   │   ├── TemplateEditorPage.tsx  # Template editing
│   │   ├── StylesPage.tsx          # Style configuration
│   │   ├── IngestPage.tsx          # Document ingestion
│   │   ├── DiffPage.tsx            # Version diff view
│   │   └── VersionHistoryPage.tsx  # Version history
│   └── hooks/              # Custom React hooks
├── package.json            # Dependencies
├── vite.config.ts          # Vite configuration
└── tsconfig.json           # TypeScript config
```

---

## TECHNOLOGY STACK

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.x | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 5.x | Build tool |
| React Router | 6.x | Routing |
| TailwindCSS | 3.x | Styling |

---

## API CLIENT (api.ts)

**Central API client at `src/api.ts`** - All backend communication goes through this file.

**Current Endpoints Used**:
| Function | Endpoint | Method |
|----------|----------|--------|
| getStatus() | /api/status | GET |
| writeProcedure() | /api/write | POST |
| getRuns() | /api/runs | GET |
| getRun(id) | /api/runs/{id} | GET |
| getProtocols() | /api/protocols | GET |
| uploadProtocol() | /api/protocols/upload | POST |
| ingestPdf() | /api/ingest/pdf | POST |
| ingestUrl() | /api/ingest/url | POST |

**Planned Endpoints** (after backend Phase 5):
| Function | Endpoint | Method |
|----------|----------|--------|
| getClaims(runId) | /api/runs/{id}/claims | GET |
| getIssues(runId) | /api/runs/{id}/issues | GET |
| getGates(runId) | /api/runs/{id}/gates | GET |
| downloadBundle(runId) | /api/runs/{id}/bundle | GET |

---

## COMMANDS

```bash
# Install dependencies
cd frontend && npm install

# Development server
npm run dev

# Build for production
npm run build

# Type checking
npm run typecheck

# Lint
npm run lint
```

---

## PAGES OVERVIEW

| Page | Route | Purpose |
|------|-------|---------|
| WritePage | / | Generate new procedures |
| RunsPage | /runs | View run history |
| RunPage | /runs/:id | View specific run details |
| SourcesPage | /sources | Manage sources |
| ProtocolsPage | /protocols | Protocol library |
| TemplatesPage | /templates | Manage DOCX templates |
| SettingsPage | /settings | App configuration |
| IngestPage | /ingest | Import documents |

---

## FUTURE FRONTEND TASKS (After Backend Phase 5)

| ID | Task | Description |
|----|------|-------------|
| FE-001 | Add ClaimsPanel component | Display extracted claims |
| FE-002 | Add IssuesPanel component | Show S0/S1/S2 issues |
| FE-003 | Add GatesPanel component | Show gate pass/fail |
| FE-004 | Add BundleDownload button | Download release ZIP |
| FE-005 | Update RunPage | Integrate claims/issues/gates |
| FE-006 | Add EvidenceBindingView | Visualize claim-evidence links |

---

## DEPENDENCIES ON BACKEND

Frontend is blocked on these backend tasks:
- [ ] P5-001: GET /api/runs/{id}/claims
- [ ] P5-002: GET /api/runs/{id}/issues
- [ ] P5-003: GET /api/runs/{id}/gates
- [ ] P5-004: GET /api/runs/{id}/bundle

**DO NOT** start frontend tasks until these are complete.

---

**Document Version**: 1.0
**Created**: 2024-12-21
