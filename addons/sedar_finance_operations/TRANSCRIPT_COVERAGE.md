# Finance Operations Interview Coverage

| Interview request | Baseline coverage |
| --- | --- |
| Roles and approvals | Cashier, Finance Officer, and Finance Manager groups imply native accounting roles. Manager checks protect rate, rebate, petty cash, advance, liquidation, and disbursement approvals. Account choices are kept out of cashier transaction entry. |
| Petty cash | Categories and funds map to native accounts/journals. Approval posts debit expense and credit cash, links the move, locks the record, and keeps chatter. |
| Employee advances | Release posts advance receivable against cash. FIFO liquidation, partial balances, expense/cash-return posting, status updates, locks, and audit links are included. |
| PO disbursements and checks | Approved PO, PO-created posted bill, and bill residual are hard gates. Native payment register creates and reconciles the payment. Check clearing, stale, and void states are tracked by journal. |
| Tariff billing and rebates | Terminal/service masters, effective approved client tariffs, job quantities, manager approval, posted customer invoices, and approved agent rebate accruals are included. |
| Collections | A posted customer invoice and chosen cash/bank journal drive native registered payments and reconciliation. Bounce removes reconciliation, cancels payment, and reopens the invoice. |
| Bank control | Manual statement values, posted journal book balance, outstanding checks, available cash, and balanced charge/interest adjustments use native ledger entries. |
| Search and reports | Native moves and stored move-line links cover PO, vessel, job, Community Maintenance work order, petty cash, advance, liquidation, disbursement, collection, billing, and bank adjustment. OCA General Ledger, Trial Balance, comparative Profit and Loss, comparative Balance Sheet, Cash Flow, and partner statements are included with PDF/XLSX support. |
| External needs | Live bank feeds, OCR/scanning of checks and receipts, bank API confirmation, printed controlled voucher layouts, and local tax rules need bank/provider access and a separate deployment scope. |

All ledger effects use native `account.move`, `account.payment`, journals, posting, and reconciliation. This addon does not replace Odoo accounting.
