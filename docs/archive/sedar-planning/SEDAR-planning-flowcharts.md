# SEDAR Odoo Planning Flowcharts

## Core Principle

The Document Module is the source of truth for every document that moves through the Odoo system.

Other modules may request, display, approve, or consume documents, but they should not own document CRUD, document storage, document status, or document history.

## Level 1: System Boundary Flow

```mermaid
flowchart LR
    subgraph Website["SEDAR Website"]
        Careers["Careers Tab"]
        Contact["Contact Us Form"]
    end

    subgraph PreEmployment["Pre-Employment / Job Application"]
        Application["Job Application Fields"]
        RequiredDocs["Required Document Rules<br/>based on job title"]
        UploadRequest["Applicant Document Requests"]
    end

    subgraph DocumentModule["Document Module<br/>SOURCE OF TRUTH"]
        DocTypes["Document Types"]
        DocRecords["Document Records"]
        DocStatus["Document Status"]
        DocHistory["Audit Trail / History"]
        DocAccess["Access Rules"]
    end

    subgraph Dashboard["Applicant / Employee Dashboard"]
        ApplicantView["Applicant Required Documents"]
        EmployeeView["Employee Issued Documents"]
        UploadUI["Upload / View / Download UI"]
    end

    subgraph HR["HR / Finance / Admin"]
        IssueDoc["Issue Document"]
        RequestDoc["Request Document"]
        ReviewDoc["Review / Approve / Reject"]
    end

    subgraph EmployeeEntity["User Entity Model"]
        ApplicantUser["Applicant User"]
        EmployeeUser["Employee User"]
        Profile["Employee Profile"]
    end

    Careers --> Application
    Application --> RequiredDocs
    RequiredDocs --> UploadRequest
    UploadRequest --> DocumentModule

    HR --> RequestDoc --> DocumentModule
    HR --> IssueDoc --> DocumentModule
    HR --> ReviewDoc --> DocumentModule

    DocumentModule --> Dashboard
    ApplicantView --> UploadUI
    EmployeeView --> UploadUI

    Application -. accepted / converted .-> EmployeeEntity
    EmployeeEntity --> Dashboard
    Dashboard --> DocumentModule
```

## Level 2: Hiring And Document Lifecycle

```mermaid
flowchart TD
    Start["Applicant visits Careers Tab"]
    SelectJob["Applicant selects job opening"]
    FillForm["Applicant fills job application fields"]
    DetermineDocs["System determines required documents<br/>from job title / position rules"]
    CreateApplicant["Create applicant record"]
    CreatePortalUser["Create applicant portal user<br/>or invite applicant"]
    CreateDocRequests["Create document request records<br/>inside Document Module"]
    ApplicantDashboard["Applicant Dashboard shows required documents"]
    UploadDocs["Applicant uploads documents"]
    StoreDocs["Document Module stores files, metadata, status, and history"]
    HRReview["HR reviews submitted documents"]
    Decision{"Document accepted?"}
    Reject["Mark rejected with reason<br/>request resubmission"]
    Accept["Mark accepted"]
    ApplicationDecision{"Applicant hired?"}
    Archive["Keep applicant records and documents<br/>according to retention policy"]
    ConvertEmployee["Convert applicant to employee"]
    EmployeeDashboard["Employee Dashboard"]
    EmployeeDocs["Show employee document requirements<br/>and HR-issued documents"]
    HRIssued["HR / Finance issues future documents<br/>through Document Module"]

    Start --> SelectJob --> FillForm --> DetermineDocs --> CreateApplicant
    CreateApplicant --> CreatePortalUser --> CreateDocRequests --> ApplicantDashboard
    ApplicantDashboard --> UploadDocs --> StoreDocs --> HRReview --> Decision
    Decision -- No --> Reject --> ApplicantDashboard
    Decision -- Yes --> Accept --> ApplicationDecision
    ApplicationDecision -- No --> Archive
    ApplicationDecision -- Yes --> ConvertEmployee --> EmployeeDashboard
    ConvertEmployee --> EmployeeDocs
    HRIssued --> EmployeeDocs
    EmployeeDocs --> StoreDocs
```

## Suggested Module Boundaries

### Website / Careers

Owns:
- Public job listing display
- Public application entry point
- Contact form routing

Does not own:
- Document storage
- Document validation state
- Employee profile data

### Job Application / Hiring

Owns:
- Applicant record
- Job application fields
- Hiring pipeline status
- Mapping selected job title to required document rules
- Conversion from applicant to employee

Does not own:
- Raw document CRUD
- HR-issued employee documents
- Long-term document history

### Document Module

Owns:
- Document type definitions
- Document request records
- Uploaded files
- Document metadata
- Document status: requested, submitted, under review, accepted, rejected, expired
- Document ownership and relation to applicant, employee, department, or company
- Audit trail
- Access control rules
- Expiration and renewal tracking

Does not own:
- Hiring decision
- Employee master profile fields
- Finance or HR business decisions

### Applicant / Employee Dashboard

Owns:
- User-facing document views
- Upload, download, and status display
- Notifications or reminders shown to the user

Does not own:
- Document CRUD logic
- Document status authority
- Required document rules

### HR / Finance / Admin

Owns:
- Requesting documents
- Issuing documents
- Reviewing documents
- Approving or rejecting submitted documents

Does not own:
- Separate document storage outside the Document Module

## Development Notes

- Treat every document as a `document.record` or equivalent central model.
- Link documents to business entities using references such as applicant, employee, department, job position, or request owner.
- The dashboard should query the Document Module instead of duplicating document state.
- Hiring should create document requests, not documents directly owned by the hiring module.
- Employee conversion should preserve applicant document history.
- HR-issued documents should use the same document lifecycle as applicant-uploaded documents where possible.

