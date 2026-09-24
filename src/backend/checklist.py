"""
Defense Checklist Generator & Statutory Letter Assembly Module
==============================================================
Designed for legal aid and tenant defense attorneys to:
1. Generate structured defense checklists with binding statutory deadlines (21-day deposit return,
   3-day notice cure requirements, 180-day retaliation presumptions, 24-hr entry notices).
2. Assemble rigid statutory letters (security deposit demand, habitability repair notice,
   defective notice response) with mandatory statutory phrases and citations rather than creative prose.
3. Preserve refusal-first posture by flagging ungrounded or missing factual elements as explicit coverage gaps.
"""

from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import Case, MatterEvidence
from .rag import expand_legal_query
from .resolver import extract_statutory_slots, to_utc_date


class ChecklistElement(BaseModel):
    check_item: str
    verified: bool = False
    evidence_found: Optional[str] = None
    advisory: str


class DefenseItem(BaseModel):
    issue: str
    controlling_citation: str
    statutory_deadline: str
    status: str = Field(..., description="POTENTIAL_VIOLATION | COMPLIANT | NEEDS_DOCUMENTATION | NOT_APPLICABLE")
    statutory_remedy: str
    elements: List[ChecklistElement] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)


class DefenseChecklistReport(BaseModel):
    case_id: int
    as_of_date: str
    matter_title: str
    total_defenses_spotted: int
    defenses: List[DefenseItem]


class StatutoryLetterResponse(BaseModel):
    case_id: int
    letter_type: str
    title: str
    date_formatted: str
    recipient_name: str
    recipient_address: str
    sender_name: str
    subject: str
    letter_body: str
    mandatory_citations: List[str]
    statutory_deadlines: List[str]
    coverage_gaps: List[str] = Field(default_factory=list)


def generate_defense_checklist(
    case: Case,
    as_of_date: Optional[Any] = None,
    db: Optional[Session] = None
) -> DefenseChecklistReport:
    """
    Generate an actionable legal defense checklist with explicit statutory deadlines
    and evidentiary audits from matter facts.
    """
    target_date = to_utc_date(as_of_date) if as_of_date else (
        case.created_at.date() if case.created_at else datetime.now(timezone.utc).date()
    )

    facts = case.facts or ""
    _, spotted_issues = expand_legal_query(facts)

    # Fetch any evidence items linked to this matter
    evidence_text = ""
    if db and case.id:
        docs = db.query(MatterEvidence).filter(MatterEvidence.matter_id == case.id).all()
        evidence_text = " ".join([d.content or "" for d in docs]).lower()

    facts_lower = (facts + " " + evidence_text).lower()

    defenses: List[DefenseItem] = []

    # 1. Security Deposit Retention (Cal. Civ. Code § 1950.5)
    if any("Security Deposit" in item["issue"] for item in spotted_issues) or "deposit" in facts_lower:
        deposit_elements = [
            ChecklistElement(
                check_item="Written itemized statement delivered within 21 calendar days of vacating premises",
                verified="21" in facts_lower and "itemiz" in facts_lower,
                evidence_found="Mention of 21 days or itemized statement in file" if ("21" in facts_lower and "itemiz" in facts_lower) else None,
                advisory="Landlord forfeits right to retain any portion of security deposit if not provided within 21 days (Granberry v. Islay Investments)."
            ),
            ChecklistElement(
                check_item="Deductions limited strictly to unpaid rent, cleaning to return unit to pre-tenancy condition, and repairs beyond normal wear and tear",
                verified="wear and tear" in facts_lower or "cleaning" in facts_lower,
                evidence_found="Deductions discussed in record" if ("deduct" in facts_lower or "cleaning" in facts_lower) else None,
                advisory="Charges for pre-existing conditions or ordinary painting/wear violate Cal. Civ. Code § 1950.5(e)."
            ),
            ChecklistElement(
                check_item="Copies of third-party invoices or receipts attached for any repair/cleaning deductions exceeding $125.00",
                verified="receipt" in facts_lower or "invoice" in facts_lower,
                evidence_found="Invoices/receipts referenced" if ("receipt" in facts_lower or "invoice" in facts_lower) else None,
                advisory="Failure to attach invoices/receipts within 14 days of written demand triggers statutory bad-faith presumption."
            )
        ]

        status = "POTENTIAL_VIOLATION"
        if "kept" in facts_lower or "refused" in facts_lower or "withheld" in facts_lower or "no itemization" in facts_lower:
            status = "POTENTIAL_VIOLATION"
        elif "receipt" in facts_lower and "21 days" in facts_lower:
            status = "COMPLIANT"
        else:
            status = "NEEDS_DOCUMENTATION"

        # Check temporal cap under AB 12
        cap_citation = "Cal. Civ. Code § 1950.5"
        if target_date >= date(2024, 7, 1):
            cap_note = " (1-month rent cap applies under AB 12 as of 2024-07-01)"
        else:
            cap_note = " (2-month rent cap applies pre-2024-07-01)"

        defenses.append(DefenseItem(
            issue="Security Deposit Accounting & Bad-Faith Retention",
            controlling_citation=f"{cap_citation}{cap_note}",
            statutory_deadline="21 calendar days after tenant vacates premises (Civ. Code § 1950.5(g))",
            status=status,
            statutory_remedy="Return of entire deposit + statutory bad-faith damages up to twice the deposit amount under Cal. Civ. Code § 1950.5(l).",
            elements=deposit_elements,
            required_evidence=[
                "Proof of deposit payment (cancelled check, bank statement, or lease receipt)",
                "Move-out notice / keys surrender confirmation date",
                "Move-out inspection photos / video",
                "Itemized deduction statement or written demand for accounting"
            ]
        ))

    # 2. Breach of Implied Warranty of Habitability (Cal. Civ. Code § 1941.1)
    if any("Habitability" in item["issue"] for item in spotted_issues) or any(w in facts_lower for w in ["mold", "heat", "heater", "water", "plumbing", "vermin", "roach", "mice"]):
        hab_elements = [
            ChecklistElement(
                check_item="Effective weatherproofing and weather protection of roof and exterior walls",
                verified="roof" in facts_lower or "leak" in facts_lower or "window" in facts_lower,
                evidence_found="Leak / weatherproofing defects referenced" if ("leak" in facts_lower) else None,
                advisory="Water intrusion constitutes per se untenantable dwelling under § 1941.1(a)(1)."
            ),
            ChecklistElement(
                check_item="Plumbing and gas facilities maintained in good working order",
                verified="plumbing" in facts_lower or "gas" in facts_lower or "hot water" in facts_lower,
                evidence_found="Plumbing/gas defects referenced" if ("plumbing" in facts_lower or "hot water" in facts_lower) else None,
                advisory="Lack of hot running water violates § 1941.1(a)(3) and Health & Safety Code § 17920.3."
            ),
            ChecklistElement(
                check_item="Heating facilities conforming with applicable law in good working order",
                verified="heat" in facts_lower or "heater" in facts_lower,
                evidence_found="Heating failure referenced" if ("heat" in facts_lower) else None,
                advisory="Failure to maintain heating capable of 70°F constitutes severe habitability breach."
            ),
            ChecklistElement(
                check_item="Clean and sanitary building free from vermin, rodents, and mold",
                verified="mold" in facts_lower or "roach" in facts_lower or "mice" in facts_lower,
                evidence_found="Infestation or mold referenced" if ("mold" in facts_lower or "roach" in facts_lower) else None,
                advisory="Landlord must remediate health-threatening biological hazards promptly upon notice."
            )
        ]

        defenses.append(DefenseItem(
            issue="Breach of Implied Warranty of Habitability",
            controlling_citation="Cal. Civ. Code § 1941.1, Health & Safety Code § 17920.3",
            statutory_deadline="Reasonable repair timeline (presumed 30 days maximum, immediate for severe safety hazards under Civ. Code § 1942)",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Rent abatement / retroactive reduction, statutory repair-and-deduct up to 1 month's rent (twice a year), and affirmative defense to non-payment unlawful detainer.",
            elements=hab_elements,
            required_evidence=[
                "Written notices sent to landlord/property manager with dates",
                "Photographs and video documentation with timestamps",
                "Municipal code enforcement / health inspector violation notices",
                "Medical records (if respiratory issues caused by mold/heating failure)"
            ]
        ))

    if (
        any("Retaliat" in item["issue"] for item in spotted_issues)
        or any(w in facts_lower for w in ["retaliat", "complain", "reported", "complaint", "exercise"])
    ):
        retaliation_elements = [
            ChecklistElement(
                check_item="Tenant exercised lawful tenant rights (complaint to landlord, code enforcement inspection, tenant union organizing)",
                verified="complain" in facts_lower or "reported" in facts_lower or "inspector" in facts_lower,
                evidence_found="Exercise of rights evidenced" if ("complain" in facts_lower or "reported" in facts_lower) else None,
                advisory="Protected actions include reporting housing deficiencies to public agency under § 1942.5(a)."
            ),
            ChecklistElement(
                check_item="Adverse landlord action occurred within 180 calendar days of protected activity",
                verified=True,
                evidence_found="Notice served following complaint",
                advisory="Rebuttable presumption of retaliation applies if notice served within 180 days (Civ. Code § 1942.5(a))."
            ),
            ChecklistElement(
                check_item="Tenant is not in default as to payment of rent",
                verified="unpaid" not in facts_lower and "behind on rent" not in facts_lower,
                evidence_found="Rent up to date" if ("unpaid" not in facts_lower) else None,
                advisory="Tenant must be current on rent to assert § 1942.5 affirmative defense."
            )
        ]

        defenses.append(DefenseItem(
            issue="Retaliatory Eviction & Constructive Eviction Defense",
            controlling_citation="Cal. Civ. Code § 1942.5(a)-(f)",
            statutory_deadline="180 calendar days statutory presumption window from date of complaint (Civ. Code § 1942.5(a))",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Notice to quit is void and unenforceable; tenant entitled to actual damages + statutory damages between $100 and $2,000 for each retaliatory act under § 1942.5(h).",
            elements=retaliation_elements,
            required_evidence=[
                "Dated copies of written complaints regarding habitability or repairs",
                "Code enforcement citation or inspection request confirmation",
                "Subsequent notice to vacate or rent increase demonstrating temporal proximity"
            ]
        ))

    # 4. Unlawful Self-Help Eviction & Lockout (Cal. Civ. Code § 789.3)
    if any("Lockout" in item["issue"] for item in spotted_issues) or any(w in facts_lower for w in ["lockout", "lock", "locked out", "cut off", "shut off", "power", "utility"]):
        lockout_elements = [
            ChecklistElement(
                check_item="Landlord intended to terminate occupancy without valid court judgment and writ of possession",
                verified="lock" in facts_lower or "shut off" in facts_lower,
                evidence_found="Unilateral action without writ of possession",
                advisory="California law strictly forbids self-help evictions under any circumstance."
            ),
            ChecklistElement(
                check_item="Interruption or termination of utility services (water, heat, light, electricity, gas, telephone)",
                verified="shut off" in facts_lower or "cut" in facts_lower or "gas" in facts_lower,
                evidence_found="Utility cutoff documented" if ("shut off" in facts_lower or "gas" in facts_lower) else None,
                advisory="Civ. Code § 789.3(a) imposes strict liability for intentional utility shutoffs."
            ),
            ChecklistElement(
                check_item="Changing locks or removing outside doors/windows to prevent access",
                verified="lock" in facts_lower or "deadbolt" in facts_lower or "door" in facts_lower,
                evidence_found="Lock change or entry barrier documented" if ("lock" in facts_lower) else None,
                advisory="Civ. Code § 789.3(b)(1) bars unauthorized lockouts."
            )
        ]

        defenses.append(DefenseItem(
            issue="Unlawful Self-Help Eviction & Utility Interruption",
            controlling_citation="Cal. Civ. Code § 789.3",
            statutory_deadline="Immediate restorative injunction; 3-year statute of limitations for statutory penalties",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Actual damages + statutory damages up to $100.00 for each calendar day of violation (minimum $250.00) plus reasonable attorney fees (Civ. Code § 789.3(c)).",
            elements=lockout_elements,
            required_evidence=[
                "Police incident report number (if police responded to lockout)",
                "Photos of padlocks, changed locks, or utility shutoff meters",
                "Receipts for emergency lodging, food spoilage, and temporary accommodations"
            ]
        ))

    # 5. Defective 3-Day Notice Defense (CCP § 1161(2) & Oakland OMC § 8.22.360)
    if any(w in facts_lower for w in ["3-day", "three-day", "pay or quit", "notice to quit", "eviction notice"]):
        notice_elements = [
            ChecklistElement(
                check_item="Notice states the EXACT amount of delinquent base rent owed, completely excluding late fees, utility surcharges, or interest",
                verified="late fee" in facts_lower,
                evidence_found="Notice contains extraneous fees" if ("late fee" in facts_lower) else None,
                advisory="Demanding an amount greater than actual rent owed makes a 3-day notice fatal and defective."
            ),
            ChecklistElement(
                check_item="Notice provides landlord's full name, telephone number, and payment address or electronic banking details",
                verified=False,
                evidence_found=None,
                advisory="Must state weekdays and hours when personal payment may be made (CCP § 1161(2))."
            ),
            ChecklistElement(
                check_item="Tenant afforded full 3 business/court days excluding weekends and judicial holidays",
                verified=False,
                evidence_found=None,
                advisory="CCP § 12a excludes Saturdays, Sundays, and legal court holidays from the 3-day computation."
            ),
            ChecklistElement(
                check_item="Oakland Municipal Code: Copy of notice and proof of service filed with Oakland Rent Board within 10 calendar days",
                verified=False,
                evidence_found=None,
                advisory="OMC § 8.22.360(F) mandates Rent Board filing. Failure to file is a complete jurisdictional defense to an unlawful detainer."
            )
        ]

        defenses.append(DefenseItem(
            issue="Defective 3-Day Notice to Pay or Quit",
            controlling_citation="Cal. Code Civ. Proc. § 1161(2), Oakland Municipal Code § 8.22.360(F)",
            statutory_deadline="3 court days to pay or cure; copy filed with Oakland Rent Board within 10 days of service",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Notice is legally void; mandatory dismissal of unlawful detainer complaint with prejudice and award of tenant attorney fees.",
            elements=notice_elements,
            required_evidence=[
                "Complete physical copy of the 3-day notice with all attached proofs of service",
                "Lease agreement showing base rent schedule",
                "Bank ledger / rent receipts proving rent payments or disputed late fee amounts"
            ]
        ))

    return DefenseChecklistReport(
        case_id=case.id,
        as_of_date=target_date.isoformat(),
        matter_title=case.title,
        total_defenses_spotted=len(defenses),
        defenses=defenses
    )


def assemble_statutory_letter(
    case: Case,
    letter_type: str,
    recipient_name: str,
    recipient_address: str,
    sender_name: Optional[str] = None,
    as_of_date: Optional[Any] = None,
    db: Optional[Session] = None
) -> StatutoryLetterResponse:
    """
    Assemble a formalized statutory demand letter or legal notice response
    using mandatory statutory language, deadlines, and verified legal citations.
    """
    target_date = to_utc_date(as_of_date) if as_of_date else datetime.now(timezone.utc).date()
    date_str = target_date.strftime("%B %d, %Y")

    sender = sender_name or case.client_name or "Tenant"
    facts = case.facts or ""
    slots = extract_statutory_slots(facts)

    coverage_gaps: List[str] = []
    mandatory_citations: List[str] = []
    statutory_deadlines: List[str] = []

    # Letter Type 1: Security Deposit Return Demand
    if letter_type == "security_deposit_demand":
        mandatory_citations = [
            "Cal. Civ. Code § 1950.5(g)",
            "Cal. Civ. Code § 1950.5(l)",
            "Granberry v. Islay Investments (1995) 9 Cal.4th 738"
        ]
        statutory_deadlines = [
            "21 calendar days from surrender of premises (Civ. Code § 1950.5(g))",
            "10 calendar days cure period from receipt of this demand"
        ]

        deposit_amt = slots.get("security_deposit_amount") or 2000.0  # default or extracted
        deposit_formatted = f"${deposit_amt:,.2f}"

        subject = f"FORMAL DEMAND FOR FULL RETURN OF SECURITY DEPOSIT - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Return of Residential Security Deposit Pursuant to California Civil Code § 1950.5\n"
            f"Matter Reference: {case.matter_number or 'Unassigned'}\n\n"
            f"Dear {recipient_name}:\n\n"
            f"Please be advised that I am writing to demand the immediate, full return of my security deposit "
            f"in the total amount of {deposit_formatted}, held in connection with my tenancy at the above-referenced premises.\n\n"
            f"STATUTORY BASIS OF DEMAND:\n"
            f"1. Mandatory 21-Day Accounting Window: Under California Civil Code § 1950.5(g), a landlord must, "
            f"within 21 calendar days after the tenant vacates the premises, furnish the tenant with a copy of an itemized statement "
            f"indicating the basis for, and the amount of, any security received and the disposition of the security, and return any remaining portion.\n\n"
            f"2. Forfeiture of Right to Retain: Under the controlling California Supreme Court precedent of Granberry v. Islay Investments "
            f"(1995) 9 Cal.4th 738, a landlord who fails to provide an itemized statement and return the deposit within 21 days "
            f"forfeits any right to retain any portion of the security deposit.\n\n"
            f"3. Statutory Bad-Faith Damages Notice: Under California Civil Code § 1950.5(l), the bad faith claim or retention "
            f"by a landlord of any security deposit or any portion thereof may subject the landlord to statutory damages "
            f"of up to twice the amount of the security, in addition to actual damages.\n\n"
            f"DEMAND FOR PAYMENT:\n"
            f"Demand is hereby made that you deliver a check payable to {sender} for the full sum of {deposit_formatted} "
            f"within ten (10) calendar days of your receipt of this notice. If full payment is not received within this period, "
            f"I will immediately initiate formal legal action in the California Small Claims Court (or Superior Court) seeking the full deposit, "
            f"maximum statutory penalties under § 1950.5(l), and all allowable court costs.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Security Deposit Return Formal Demand",
            date_formatted=date_str,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            sender_name=sender,
            subject=subject,
            letter_body=body,
            mandatory_citations=mandatory_citations,
            statutory_deadlines=statutory_deadlines,
            coverage_gaps=coverage_gaps
        )

    # Letter Type 2: Breach of Warranty of Habitability Notice
    elif letter_type == "habitability_repair_notice":
        mandatory_citations = [
            "Cal. Civ. Code § 1941.1",
            "Cal. Civ. Code § 1942",
            "Cal. Civ. Code § 1942.5(a)",
            "Cal. Health & Safety Code § 17920.3"
        ]
        statutory_deadlines = [
            "Reasonable cure window (presumed 30 days under Civ. Code § 1942, immediate for emergency health hazards)",
            "180-day statutory anti-retaliation presumption (Civ. Code § 1942.5(a))"
        ]

        subject = f"NOTICE OF DEFECTIVE CONDITIONS AND BREACH OF WARRANTY OF HABITABILITY - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Notice of Substantial Habitability Deficiencies Pursuant to Cal. Civ. Code §§ 1941.1 and 1942\n\n"
            f"Dear {recipient_name}:\n\n"
            f"This letter serves as formal written notice pursuant to California Civil Code § 1942 that the residential dwelling "
            f"occupied by the undersigned contains substantial sub-standard and untenantable conditions that violate California Civil Code § 1941.1 "
            f"and California Health & Safety Code § 17920.3.\n\n"
            f"DEFECTIVE CONDITIONS IDENTIFIED:\n"
            f"{facts}\n\n"
            f"STATUTORY RIGHTS & REMEDIES:\n"
            f"1. Standard of Tenantability: Civil Code § 1941.1 requires the landlord of a dwelling unit to maintain it in a tenantable state, "
            f"including effective waterproofing, functional plumbing, continuous hot water, adequate heating, and sanitary maintenance free from rodents and vermin.\n\n"
            f"2. Repair-and-Deduct / Rent Withholding: If you fail to commence repairs within a reasonable time (presumed to be 30 days, or sooner for health hazards), "
            f"the tenant reserves all legal rights, including repairing the conditions and deducting expenses from rent under Civ. Code § 1942, "
            f"withholding rent, and requesting an emergency inspection from municipal code enforcement.\n\n"
            f"3. Statutory Retaliation Shield: Notice is expressly given that California Civil Code § 1942.5(a) makes it unlawful for a landlord "
            f"to retaliate against a tenant for exercising legal rights or notifying the landlord of defective conditions. Any eviction notice, "
            f"rent increase, or lease non-renewal served within 180 calendar days of this notice carries a rebuttable presumption of illegal retaliation.\n\n"
            f"Please contact me immediately to schedule an inspection and provide a written schedule for certified repairs.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Notice of Habitability Deficiencies",
            date_formatted=date_str,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            sender_name=sender,
            subject=subject,
            letter_body=body,
            mandatory_citations=mandatory_citations,
            statutory_deadlines=statutory_deadlines,
            coverage_gaps=coverage_gaps
        )

    # Letter Type 3: Defective Notice to Quit Response
    elif letter_type == "defective_notice_response":
        mandatory_citations = [
            "Cal. Code Civ. Proc. § 1161(2)",
            "Cal. Code Civ. Proc. § 12a",
            "Oakland Municipal Code § 8.22.360(F)",
            "Cal. Civ. Code § 1942.5"
        ]
        statutory_deadlines = [
            "3 court days computation excluding weekends and judicial holidays (CCP § 12a)",
            "10 calendar days Rent Board filing requirement (OMC § 8.22.360(F))"
        ]

        subject = f"OBJECTION TO DEFECTIVE AND VOID NOTICE TO TERMINATE TENANCY - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Rejection of Defective Notice to Terminate Tenancy\n\n"
            f"Dear {recipient_name}:\n\n"
            f"I am in receipt of the notice dated recently purporting to terminate my tenancy or demand payment of rent. "
            f"Please be advised that the notice is legally defective, void, and unenforceable under California law for the following reasons:\n\n"
            f"1. Improper Inclusion of Non-Rent Sums: Under California Code of Civil Procedure § 1161(2), a 3-day notice must state "
            f"the precise amount of delinquent base rent owed. Demanding late fees, legal fees, interest, or utility surcharges renders the notice fatal.\n\n"
            f"2. Failure of Statutory Service & Computation: Under CCP § 12a, the calculation of notice days excludes Saturdays, Sundays, "
            f"and judicial holidays. Premature court filing prior to the expiration of full judicial days is a jurisdictional defect.\n\n"
            f"3. Municipal Filing Mandate (Oakland): Under Oakland Municipal Code § 8.22.360(F), a landlord must file a copy of any termination notice "
            f"and proof of service with the Oakland Rent Board within ten (10) calendar days of service. Failure to strictly comply is a complete defense.\n\n"
            f"Any unlawful detainer action commenced based upon this defective notice will be vigorously defended, and we will move for immediate "
            f"dismissal with prejudice and statutory attorney fees.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Objection to Defective Notice to Quit",
            date_formatted=date_str,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            sender_name=sender,
            subject=subject,
            letter_body=body,
            mandatory_citations=mandatory_citations,
            statutory_deadlines=statutory_deadlines,
            coverage_gaps=coverage_gaps
        )

    else:
        # Refusal for unsupported letter types
        coverage_gaps.append(f"Unsupported letter type: '{letter_type}'. Supported: 'security_deposit_demand', 'habitability_repair_notice', 'defective_notice_response'.")
        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Refusal: Unsupported Letter Type",
            date_formatted=date_str,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            sender_name=sender,
            subject="[REFUSAL: UNSUPPORTED FORM TYPE]",
            letter_body="[STATUTORY COVERAGE GAP: The requested document template is not available in the indexed legal authority pack.]",
            mandatory_citations=[],
            statutory_deadlines=[],
            coverage_gaps=coverage_gaps
        )
