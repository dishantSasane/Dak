# Vantara Term Life Cover - synthetic policy wording

SYNTHETIC DEMO DOCUMENT. Not an insurance contract or an approved insurance product.

Fictional issuer: Vantara General Insurance. Product code: TRM.
Document ID: VGI-TRM-SYN-2026-01. Wording version: 1.0. Corpus version: 1.
Prepared for Dak on 2026-10-19. All amounts, time limits and procedures below are fictional test rules.
The legacy seed product name Term Life Insurance maps to this synthetic TRM wording only.
This fictional project groups product lines under one demo issuer; no real general-insurer life licence is implied.

## TRM-C01 | Protection-only purpose

This fixture describes a protection-only term cover for the person named in the synthetic policy schedule. It is not an investment account and does not provide an investment return. The schedule supplies the start and end dates, recorded protection amount and premium mode. Only a human reviewer can determine a death claim after examining the records and relevant evidence.

## TRM-C02 | Death intimation

A beneficiary can notify the team that the named life assured has died and provide the policy number, date of death and contact details for correspondence. This begins an evidence-gathering process. Receipt of a notification, creation of a case token and attachment upload do not confirm that a benefit is payable. A customer acknowledgement must not announce an approval, rejection or likelihood of either outcome.

## TRM-C03 | Protection amount

The amount of protection is held in the individual policy record. No fixed customer benefit or universal multiplier is supplied by this synthetic wording. The assistant must not calculate an amount from premium frequency or use another customer's record as a reference. Any potential deductions, prior payments or conflicting schedule entries require human assessment before a figure can be communicated as a claim outcome.

## TRM-C04 | Initial risk waiting period

The default non-accidental initial risk waiting period in this synthetic fixture is 45 days. A synthetic schedule may specify a different waiting_period_end date, and that recorded date is inclusive. A death on the recorded end date remains inside the waiting period; the next date is outside it. The assistant must retrieve the record rather than infer the boundary from the product name or the default alone.

## TRM-C05 | Accidental death during waiting

A death reported as directly resulting from an accident within the recorded policy period may require different treatment from non-accidental death during the initial risk waiting period. That exception requires evidence of cause and human assessment. If a general calculator blocks the event but a retrieved clause suggests this exception, retain the disagreement and escalate. The drafting model must not waive a block or tell the beneficiary the claim is payable.

## TRM-C06 | Non-accidental death during waiting

For this fixture, the reviewer examines a request concerning non-accidental death inside the waiting period for a possible return of recorded base premiums, rather than assuming the full protection amount applies. This is an internal assessment path, not a guarantee of any refund. Taxes, separate riders, evidence gaps and schedule differences must be examined individually. The assistant does not compute or promise a refund.

## TRM-C07 | Premium frequency and due records

The schedule records monthly, quarterly or annual premium frequency and the latest recorded payment date. A payment date alone is insufficient to establish all instalments due or the exact grace-period end. The assistant must not construct a new due-date ledger from the frequency label. A dispute over whether a payment was received or allocated requires the payment team and supporting evidence.

## TRM-C08 | Grace period and lapse review

This fixture uses a default grace period of 18 days for a monthly premium and 32 days for a quarterly or annual premium. These are deliberately fictional durations. The due date and unpaid instalments must be confirmed before applying the rule. A currently lapsed label does not alone settle whether an earlier event fell inside a valid period or grace period; the reviewer must examine the historical record.

## TRM-C09 | Revival is not automatic

A request to revive lapsed cover is considered separately from a claim intimation. Payment of overdue premiums or sending a revival request does not automatically establish that cover resumed. The reviewer needs a recorded revival acceptance and effective date. If those records are missing, the assistant must identify the gap and refer the case rather than invent a revival date or recalculate cover from a bank transfer.

## TRM-C10 | Nominee and claimant identity

The recorded nominee details help identify the person to contact, but they do not remove the need to establish the claimant's identity and entitlement. A mismatch between the sender and nominee requires a human to check the relationship and documents. The assistant must not reveal a nominee's identity to an unrelated sender or assume that possession of a policy number establishes entitlement to a benefit.

## TRM-C11 | Standard death-claim evidence

Standard supporting items are a completed death-claim form, death certificate, claimant identity evidence, policy reference and payment account evidence supplied through an appropriate review channel. Medical records may be needed to understand the cause and timing of death. The demo uses synthetic documents only. Dak inventories filenames and presence; it does not verify identity documents, read bank records or establish their authenticity.

## TRM-C12 | Additional accident evidence

When accidental death is described, the reviewer may need a police report, available post-mortem report and an incident account in addition to the standard evidence. Unavailable documents should be identified individually and referred with an explanation. The assistant must not infer cause of death from the existence of a filename, a brief email statement or the emotional tone of the sender.

## TRM-C13 | Special exclusion review

An event involving intentional self-harm during the first 12 months from commencement or a recorded revival is a specialist review case in this synthetic wording. The assistant must not determine intent, infer a cause from euphemisms or announce an exclusion as a decided outcome. Medical evidence, chronology and the applicable schedule must be examined by a human with the full record.

## TRM-C14 | End of term and maturity

There is no maturity payment or savings balance under this fixture's base protection-only cover. A scheduled end date marks the end of the recorded term unless a distinct accepted change exists. This clause does not determine a death claim relating to an earlier event. The assistant must distinguish an enquiry about surviving the term from a notification of death before the term ended.

## TRM-C15 | Optional riders

A rider exists only when it is recorded in the individual schedule. A label such as accident_cover or critical_illness indicates an additional record may be relevant, but this base document does not define that rider's benefit, evidence or amount. Where the separate rider wording is absent, refer the question. Do not borrow a health benefit or motor accident rule to fill the missing term-life rider wording.

## TRM-C16 | Cancellation and historical events

A recorded cancellation date is compared with the event date rather than applied retrospectively without examination. An event before commencement is outside the preliminary policy-period check. An event after the recorded end date requires a human to check for a distinct valid continuation. The assistant cannot infer that a cancellation, lapse or revival occurred merely because a customer uses those words in correspondence.

## TRM-C17 | Complaint, dispute and legal reference

A complaint about delay, nomination, premium allocation or a disputed earlier decision should identify the policy and relevant case reference. The reviewer compares the record with the specific clause and explains any uncertainty in an internal note. A regulatory or legal reference triggers human escalation. A repeated complaint requires a consolidated review; a sympathetic reply must not promise a benefit, reversal or compensation.

## TRM-C18 | Boundaries of supported answers

This corpus does not describe annuities, pension withdrawals, unit-linked investments, tax advice or benefits under an employer's group scheme. It supplies no current claim status, bank transfer date or guaranteed assessment timeline. If those facts are missing, the appropriate answer is a referral rather than a plausible estimate. Bereavement correspondence should remain concise, respectful and neutral about outcomes.
