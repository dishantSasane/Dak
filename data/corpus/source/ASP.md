# Vantara Health Cover - synthetic policy wording

SYNTHETIC DEMO DOCUMENT. Not an insurance contract or an approved insurance product.

Fictional issuer: Vantara General Insurance. Product code: ASP.
Document ID: VGI-ASP-SYN-2026-01. Wording version: 1.0. Corpus version: 1.
Prepared for Dak on 2026-10-19. All amounts, time limits and procedures below are fictional test rules.
The legacy seed product name Arogya Sanjeevani Health Insurance maps to this synthetic ASP wording only.

## ASP-C01 | Scope and schedule precedence

This fixture describes medical expense cover for the named synthetic policyholder. The individual policy record supplies the insured persons, start date, end date, insured amount and selected endorsements. A generic answer may describe this wording, but it must not substitute an example for a customer's record. Where a schedule explicitly changes a default below, the recorded schedule controls and the response requires a customer-specific lookup.

## ASP-C02 | Hospital admission

An eligible hospital admission involves medically necessary treatment prescribed by a registered medical practitioner and an overnight stay of at least 24 hours. Observation solely for routine screening is outside this benefit. Admission notes, the discharge summary and itemised bills are evidence for assessment. Meeting the stay requirement alone does not establish that the particular claim satisfies every other condition.

## ASP-C03 | Day-care procedures

A procedure performed in a licensed day-care facility can be assessed without an overnight stay when medical advances make a shorter admission appropriate. The procedure record must identify the treatment and explain the short stay. Routine outpatient consultations, screening packages and pharmacy purchases are not converted into day-care treatment by describing them as procedures.

## ASP-C04 | Expenses around admission

Related diagnostic tests and prescribed medicines incurred in the 20 days before admission and the 45 days after discharge may be assessed with the associated hospital claim. The treating practitioner must connect them to the admitted condition. These windows do not create a separate allowance for unrelated conditions and do not override the policy period, waiting periods or remaining insured amount.

## ASP-C05 | Room and intensive care limits

The default room allowance is INR 2,800 per day. The default intensive care allowance is INR 5,600 per day. A recorded endorsement may replace these defaults. A reviewer identifies the eligible days and any applicable limit using the hospital bill. The assistant must not calculate a personal hospital entitlement from these daily figures without the bill and the applicable policy record.

## ASP-C06 | Emergency transport

Emergency road ambulance expenses associated with an assessed hospital admission have a default limit of Rs 3,500 for each admission. This allowance concerns the road transfer to a hospital and does not extend to an air ambulance, routine transport home or accommodation for accompanying relatives. A dated transport receipt and the medical reason for emergency transfer support the request.

## ASP-C07 | Initial waiting period

The default initial waiting period for illness is 30 days from the policy start date. Some synthetic schedules instead record 60 days or 90 days. The recorded waiting_period_end date is inclusive: an illness event on that date remains inside the waiting period, and the following date is outside it. An accident exception is described separately in ASP-C08; the assistant must not silently apply that exception to a personal claim.

## ASP-C08 | Accident exception and human review

The initial illness waiting period does not apply to treatment caused directly by a documented accidental injury occurring within the policy period. This exception does not remove exclusions, exhaustion of the insured amount or cancellation. If the deterministic calculator reports an initial waiting-period block but retrieved evidence suggests this exception, preserve both findings and refer the conflict to a human reviewer rather than deciding the claim.

## ASP-C09 | Pre-existing conditions

A declared condition that existed before the policy started uses the pre_existing_waiting_period_end date in the synthetic schedule. Fixture schedules may use 240 days, 365 days or 730 days; these are scenario choices, not regulatory requirements. The end date is inclusive. A general question can describe the mechanism, but the assistant needs the policy record and relevant medical history to discuss an individual's waiting-period position.

## ASP-C10 | Co-payment

The default co-payment is 5% of the amount assessed as admissible, with the remainder subject to the available insured amount. A schedule may instead record 0%, 10% or 20%. For this demo's preliminary calculator, first cap the requested amount at the remaining insured amount, then apply the recorded co-payment percentage. This calculation is advisory and omits benefit-specific assessments; it is not a claim decision or payment promise.

## ASP-C11 | Medical exclusions

Routine health checks, treatment solely for cosmetic preference, fertility services and treatment without a documented medical indication are outside this fixture's base benefits. Reconstructive treatment following an assessed accidental injury requires individual review and is not automatically excluded as cosmetic. A diagnosis label alone cannot establish the applicable exclusion. The reviewer must consider the medical evidence and the complete circumstances.

## ASP-C12 | Consumables and disputed rejections

Consumables recorded by the hospital as necessary components of an otherwise assessed surgical procedure are not excluded merely because they are described as consumables. Personal toiletries and visitor supplies remain outside the benefit. A complaint about a rejection based only on a blanket consumables exclusion must be checked against the bill, this clause and any internally disputed claim record; it requires human review when the evidence conflicts.

## ASP-C13 | Claim evidence and attachments

The standard evidence list is a completed claim form, discharge summary, itemised hospital bill, payment receipts and relevant investigation reports. An accidental injury may additionally require an incident report when available. Dak checks attachment names and presence only. It does not certify document contents or authenticity. Missing documents should be listed individually; receiving an attachment is not evidence that the claim is admissible.

## ASP-C14 | Insured amount and remaining balance

The insured amount and remaining balance are customer-specific fields in the policy record. Assessed settlements reduce the remaining balance; the remaining balance cannot become negative. This generic wording supplies no customer's balance and no universal insured amount. A draft must not infer or invent that amount from a premium, a product name or another customer's case. A depleted balance is a review finding, not an automated customer-facing rejection.

## ASP-C15 | Intimation and delayed notification

The customer should notify the claims team as soon as reasonably possible after admission and include the policy number, admission date and treating hospital. A late notification accompanied by an explanation is sent for review rather than automatically rejected. An acknowledgement confirms receipt only. It must not say that cover has been accepted, that reimbursement is certain or that a decision has already been made.

## ASP-C16 | Period, renewal and cancellation

The event must be compared with the start and end dates in the recorded schedule. A cancellation effective on the event date blocks the preliminary active-policy check; an event before a recorded cancellation date requires assessment under the then-current record. Renewal is a separate recorded period and must not be assumed from a previous year's schedule. This fixture makes no automatic promise of renewal or restoration of a depleted balance.

## ASP-C17 | Complaint handling

A complaint should identify the policy number, any claim reference and the specific disputed action. The reviewer can examine prior correspondence and explain the relevant clause. A further complaint after at least 2 earlier complaints on the same policy is escalated for a consolidated review. Formal regulatory or legal language is always referred to a human, regardless of whether the customer uses a polite or angry tone.

## ASP-C18 | Supported answers and limits

This wording supports questions about the fictional health benefits above. It does not describe travel cover, pet cover, investment returns, a hospital's current network status or the status of an individual payment. A question requiring absent information must be referred rather than answered from general insurance knowledge. All claim outcomes and any commitments outside these written fixture rules remain decisions for the human reviewer.
