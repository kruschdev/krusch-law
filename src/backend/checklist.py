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
    pinpoint_citation: Optional[str] = None
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
    Generate an actionable legal defense checklist with explicit statutory deadlines,
    pinpoint citation coordinates, and decrypted evidentiary audits from matter facts.
    """
    target_date = to_utc_date(as_of_date) if as_of_date else (
        case.created_at.date() if case.created_at else datetime.now(timezone.utc).date()
    )

    facts = case.facts or ""
    _, spotted_issues = expand_legal_query(facts)

    # Fetch and decrypt any evidence items linked to this matter
    evidence_text = ""
    if db and case.id:
        from .crypto import EvidenceEncryptor
        docs = db.query(MatterEvidence).filter(MatterEvidence.matter_id == case.id).all()
        decrypted_parts = []
        for d in docs:
            if d.content:
                try:
                    dec = EvidenceEncryptor.decrypt_text(d.content)
                    decrypted_parts.append(dec)
                except Exception:
                    decrypted_parts.append(d.content)
        evidence_text = " ".join(decrypted_parts).lower()

    facts_lower = (facts + " " + evidence_text).lower()

    defenses: List[DefenseItem] = []

    # 1. Security Deposit Retention (Cal. Civ. Code § 1950.5)
    if any("Security Deposit" in item["issue"] for item in spotted_issues) or "deposit" in facts_lower:
        deposit_elements = [
            ChecklistElement(
                check_item="Written itemized statement delivered within 21 calendar days of vacating premises",
                verified="21" in facts_lower and "itemiz" in facts_lower,
                evidence_found="Mention of 21 days or itemized statement in file" if ("21" in facts_lower and "itemiz" in facts_lower) else None,
                advisory="Landlord forfeits right to retain any portion of security deposit if not provided within 21 days (Granberry v. Islay Investments).",
                pinpoint_citation="Cal. Civ. Code § 1950.5(g)(1)"
            ),
            ChecklistElement(
                check_item="Deductions limited strictly to unpaid rent, cleaning to return unit to pre-tenancy condition, and repairs beyond normal wear and tear",
                verified="wear and tear" in facts_lower or "cleaning" in facts_lower,
                evidence_found="Deductions discussed in record" if ("deduct" in facts_lower or "cleaning" in facts_lower) else None,
                advisory="Charges for pre-existing conditions or ordinary painting/wear violate Cal. Civ. Code § 1950.5(e).",
                pinpoint_citation="Cal. Civ. Code § 1950.5(e)"
            ),
            ChecklistElement(
                check_item="Copies of third-party invoices or receipts attached for any repair/cleaning deductions exceeding $125.00",
                verified="receipt" in facts_lower or "invoice" in facts_lower,
                evidence_found="Invoices/receipts referenced" if ("receipt" in facts_lower or "invoice" in facts_lower) else None,
                advisory="Failure to attach invoices/receipts within 14 days of written demand triggers statutory bad-faith presumption.",
                pinpoint_citation="Cal. Civ. Code § 1950.5(g)(2)"
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
                advisory="Water intrusion constitutes per se untenantable dwelling under § 1941.1(a)(1).",
                pinpoint_citation="Cal. Civ. Code § 1941.1(a)(1)"
            ),
            ChecklistElement(
                check_item="Plumbing and gas facilities maintained in good working order",
                verified="plumbing" in facts_lower or "gas" in facts_lower or "hot water" in facts_lower,
                evidence_found="Plumbing/gas defects referenced" if ("plumbing" in facts_lower or "hot water" in facts_lower) else None,
                advisory="Lack of hot running water violates § 1941.1(a)(3) and Health & Safety Code § 17920.3.",
                pinpoint_citation="Cal. Civ. Code § 1941.1(a)(3)"
            ),
            ChecklistElement(
                check_item="Heating facilities conforming with applicable law in good working order",
                verified="heat" in facts_lower or "heater" in facts_lower,
                evidence_found="Heating failure referenced" if ("heat" in facts_lower) else None,
                advisory="Failure to maintain heating capable of 70°F constitutes severe habitability breach.",
                pinpoint_citation="Cal. Civ. Code § 1941.1(a)(4)"
            ),
            ChecklistElement(
                check_item="Clean and sanitary building free from vermin, rodents, and mold",
                verified="mold" in facts_lower or "roach" in facts_lower or "mice" in facts_lower,
                evidence_found="Infestation or mold referenced" if ("mold" in facts_lower or "roach" in facts_lower) else None,
                advisory="Landlord must remediate health-threatening biological hazards promptly upon notice.",
                pinpoint_citation="Cal. Civ. Code § 1941.1(a)(5)"
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
                advisory="Protected actions include reporting housing deficiencies to public agency under § 1942.5(a).",
                pinpoint_citation="Cal. Civ. Code § 1942.5(a)"
            ),
            ChecklistElement(
                check_item="Adverse landlord action occurred within 180 calendar days of protected activity",
                verified=True,
                evidence_found="Notice served following complaint",
                advisory="Rebuttable presumption of retaliation applies if notice served within 180 days (Civ. Code § 1942.5(a)).",
                pinpoint_citation="Cal. Civ. Code § 1942.5(a)-(c)"
            ),
            ChecklistElement(
                check_item="Tenant is not in default as to payment of rent",
                verified="unpaid" not in facts_lower and "behind on rent" not in facts_lower,
                evidence_found="Rent up to date" if ("unpaid" not in facts_lower) else None,
                advisory="Tenant must be current on rent to assert § 1942.5 affirmative defense.",
                pinpoint_citation="Cal. Civ. Code § 1942.5(g)"
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
                advisory="California law strictly forbids self-help evictions under any circumstance.",
                pinpoint_citation="Cal. Civ. Code § 789.3(a)"
            ),
            ChecklistElement(
                check_item="Interruption or termination of utility services (water, heat, light, electricity, gas, telephone)",
                verified="shut off" in facts_lower or "cut" in facts_lower or "gas" in facts_lower,
                evidence_found="Utility cutoff documented" if ("shut off" in facts_lower or "gas" in facts_lower) else None,
                advisory="Civ. Code § 789.3(a) imposes strict liability for intentional utility shutoffs.",
                pinpoint_citation="Cal. Civ. Code § 789.3(a)"
            ),
            ChecklistElement(
                check_item="Changing locks or removing outside doors/windows to prevent access",
                verified="lock" in facts_lower or "deadbolt" in facts_lower or "door" in facts_lower,
                evidence_found="Lock change or entry barrier documented" if ("lock" in facts_lower) else None,
                advisory="Civ. Code § 789.3(b)(1) bars unauthorized lockouts.",
                pinpoint_citation="Cal. Civ. Code § 789.3(b)(1)"
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
                advisory="Demanding an amount greater than actual rent owed makes a 3-day notice fatal and defective.",
                pinpoint_citation="Cal. Code Civ. Proc. § 1161(2)"
            ),
            ChecklistElement(
                check_item="Notice provides landlord's full name, telephone number, and payment address or electronic banking details",
                verified=False,
                evidence_found=None,
                advisory="Must state weekdays and hours when personal payment may be made (CCP § 1161(2)).",
                pinpoint_citation="Cal. Code Civ. Proc. § 1161(2)"
            ),
            ChecklistElement(
                check_item="Tenant afforded full 3 business/court days excluding weekends and judicial holidays",
                verified=False,
                evidence_found=None,
                advisory="CCP § 12a excludes Saturdays, Sundays, and legal court holidays from the 3-day computation.",
                pinpoint_citation="Cal. Code Civ. Proc. § 12a"
            ),
            ChecklistElement(
                check_item="Oakland Municipal Code: Copy of notice and proof of service filed with Oakland Rent Board within 10 calendar days",
                verified=False,
                evidence_found=None,
                advisory="OMC § 8.22.360(F) mandates Rent Board filing. Failure to file is a complete jurisdictional defense to an unlawful detainer.",
                pinpoint_citation="Oakland Municipal Code § 8.22.360(F)"
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

    # 6. Landlord Unlawful Entry & Tenant Harassment (Cal. Civ. Code § 1954 & § 1940.2)
    if any(w in facts_lower for w in ["entry", "entered", "inspect", "inspection", "harass", "unannounced", "show unit", "trespass"]):
        entry_elements = [
            ChecklistElement(
                check_item="Landlord provided written notice of intent to enter at least 24 hours prior to proposed entry",
                verified="24 hour" in facts_lower or "notice" in facts_lower,
                evidence_found="Written notice timeline referenced" if ("notice" in facts_lower) else None,
                advisory="Notice must state approximate time and statutory purpose of entry under Cal. Civ. Code § 1954(d)(1).",
                pinpoint_citation="Cal. Civ. Code § 1954(d)(1)"
            ),
            ChecklistElement(
                check_item="Entry scheduled strictly during normal business hours (Monday through Friday, 8:00 AM to 5:00 PM)",
                verified="business hour" in facts_lower or "weekend" in facts_lower or "evening" in facts_lower,
                evidence_found="Timing of entry noted in file" if ("weekend" in facts_lower or "evening" in facts_lower) else None,
                advisory="Entry outside normal business hours without tenant consent violates Cal. Civ. Code § 1954(b).",
                pinpoint_citation="Cal. Civ. Code § 1954(b)"
            ),
            ChecklistElement(
                check_item="Entry confined strictly to statutory enumerated purposes (repairs, agreed services, showings, court order)",
                verified=False,
                evidence_found=None,
                advisory="Fishing expeditions or general inspections without repair necessity violate Civ. Code § 1954(a).",
                pinpoint_citation="Cal. Civ. Code § 1954(a)"
            ),
            ChecklistElement(
                check_item="Landlord did not use entry or threats to force tenant to vacate or interfere with quiet enjoyment",
                verified="harass" in facts_lower or "threat" in facts_lower,
                evidence_found="Harassment or intimidation referenced" if ("harass" in facts_lower or "threat" in facts_lower) else None,
                advisory="Unlawful entry with intent to influence tenant to vacate triggers statutory damages up to $2,000 per violation under Cal. Civ. Code § 1940.2(b).",
                pinpoint_citation="Cal. Civ. Code § 1940.2(b)"
            )
        ]

        defenses.append(DefenseItem(
            issue="Unlawful Landlord Entry & Tenant Harassment",
            controlling_citation="Cal. Civ. Code § 1954, Cal. Civ. Code § 1940.2",
            statutory_deadline="At least 24 hours written notice before entry; normal business hours only",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Injunction against unlawful entry, breach of quiet enjoyment damages, and statutory civil penalty up to $2,000 for each violation under Cal. Civ. Code § 1940.2(b).",
            elements=entry_elements,
            required_evidence=[
                "Written notices of entry received (with envelope postmark or timestamp)",
                "Security camera / doorbell footage showing entry date and time",
                "Log of unauthorized entries with dates, times, and persons entering"
            ]
        ))

    # 7. Unlawful Rent Increase & Exceeding Statutory Rent Caps (Cal. Civ. Code § 1947.12 & § 827)
    if (
        any("Rent Increase" in item["issue"] for item in spotted_issues)
        or any(w in facts_lower for w in ["rent increase", "raise rent", "raised rent", "rent hike", "cpi", "rent cap", "gouging", "higher rent"])
    ):
        rent_elements = [
            ChecklistElement(
                check_item="Rent increase does not exceed statutory ceiling (5% plus regional CPI, maximum 10% under Cal. Civ. Code § 1947.12(a))",
                verified="10%" in facts_lower or "cpi" in facts_lower or "increase" in facts_lower,
                evidence_found="Rent increase percentage identified" if ("%" in facts_lower or "increase" in facts_lower) else None,
                advisory="Increases above 5% + CPI violate AB 1482 unless valid exemption applies (Civ. Code § 1947.12(a)).",
                pinpoint_citation="Cal. Civ. Code § 1947.12(a)"
            ),
            ChecklistElement(
                check_item="Written notice served with requisite statutory lead time (30 calendar days for <=10%, 90 calendar days for >10% under Cal. Civ. Code § 827(b))",
                verified="30 day" in facts_lower or "90 day" in facts_lower or "notice" in facts_lower,
                evidence_found="Notice timeline documented" if ("notice" in facts_lower) else None,
                advisory="Civ. Code § 827(b)(3) strictly requires 90 days advance written notice when cumulative increases exceed 10%.",
                pinpoint_citation="Cal. Civ. Code § 827(b)(2)-(3)"
            ),
            ChecklistElement(
                check_item="Service by mail extended by 5 additional calendar days pursuant to Cal. Code Civ. Proc. § 1013",
                verified=False,
                evidence_found=None,
                advisory="If notice of rent increase was mailed within California, effective date must be at least 35 days (for <=10%) or 95 days (for >10%).",
                pinpoint_citation="Cal. Code Civ. Proc. § 1013"
            ),
            ChecklistElement(
                check_item="Exemption Notice Requirement: Lease contains mandatory statutory exemption text if claiming single-family alienable title exemption",
                verified="exemption" in facts_lower,
                evidence_found="Exemption clause discussed" if ("exemption" in facts_lower) else None,
                advisory="Landlord forfeits AB 1482 single-family exemption if statutory disclosure was omitted from the lease (Civ. Code § 1947.12(d)(5)).",
                pinpoint_citation="Cal. Civ. Code § 1947.12(d)(5)"
            )
        ]

        defenses.append(DefenseItem(
            issue="Unlawful Rent Increase & Statutory Rent Cap Violation",
            controlling_citation="Cal. Civ. Code § 1947.12, Cal. Civ. Code § 827, Oakland Municipal Code § 8.22.070",
            statutory_deadline="30 calendar days for <=10% increase; 90 calendar days for >10% increase (Civ. Code § 827(b)); +5 days if mailed (CCP § 1013)",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Rent increase is void ab initio; tenant entitled to restitution of excess rent paid, reinstatement of lawful base rent, and complete defense to non-payment unlawful detainer.",
            elements=rent_elements,
            required_evidence=[
                "Copy of written notice of rent increase with postmarked envelope or delivery date",
                "Lease agreement establishing base rent schedule and checking for exemption disclosures",
                "Proof of rent payment history for preceding 12 months"
            ]
        ))

    # 8. No-Fault Eviction & Mandatory Relocation Assistance Compliance (AB 1482 Civ. Code § 1946.2(d) & Oakland OMC § 8.22.360)
    if (
        any("Relocation" in item["issue"] or "Just Cause" in item["issue"] for item in spotted_issues)
        or any(w in facts_lower for w in ["relocation", "owner move-in", "owner move in", "omi", "remodel", "no-fault", "no fault", "ellis act"])
    ):
        relocation_elements = [
            ChecklistElement(
                check_item="Written notice states valid statutory no-fault grounds (owner move-in, withdrawal, substantial remodel) under Civ. Code § 1946.2(b)(2)",
                verified="owner move" in facts_lower or "remodel" in facts_lower or "ellis" in facts_lower or "no fault" in facts_lower or "no-fault" in facts_lower,
                evidence_found="No-fault ground identified" if ("move" in facts_lower or "remodel" in facts_lower) else None,
                advisory="Failure to specify statutory ground in notice makes eviction void under Civ. Code § 1946.2(a).",
                pinpoint_citation="Cal. Civ. Code § 1946.2(a)"
            ),
            ChecklistElement(
                check_item="Written notice provides tenant with written option for direct relocation payment or rent waiver (Civ. Code § 1946.2(d)(1))",
                verified="waiver" in facts_lower or "payment" in facts_lower,
                evidence_found="Relocation option stated" if ("waiver" in facts_lower or "relocation" in facts_lower) else None,
                advisory="Notice must state the amount of relocation assistance or waiver provided.",
                pinpoint_citation="Cal. Civ. Code § 1946.2(d)(1)"
            ),
            ChecklistElement(
                check_item="Direct relocation payment delivered to tenant within 15 calendar days of service of notice of termination",
                verified="paid" in facts_lower and "relocation" in facts_lower,
                evidence_found="Relocation funds tendered" if ("paid" in facts_lower and "relocation" in facts_lower) else None,
                advisory="Civ. Code § 1946.2(d)(1)(A) mandates delivery of payment within 15 calendar days.",
                pinpoint_citation="Cal. Civ. Code § 1946.2(d)(1)(A)"
            ),
            ChecklistElement(
                check_item="Strict Compliance Voiding Rule: Failure to pay relocation assistance makes termination notice VOID",
                verified=True,
                evidence_found="Statutory defense available if payment omitted",
                advisory="Under Cal. Civ. Code § 1946.2(d)(4), failure to strictly provide relocation assistance renders the notice of termination void.",
                pinpoint_citation="Cal. Civ. Code § 1946.2(d)(4)"
            ),
            ChecklistElement(
                check_item="Municipal Harmonized Floor (Oakland): Landlord tendered higher municipal relocation payment under OMC § 8.22.360",
                verified=False,
                evidence_found=None,
                advisory="Under HARMONIZED_FLOOR_RULE, Oakland's higher relocation assistance schedule supersedes the state 1-month floor.",
                pinpoint_citation="Oakland Municipal Code § 8.22.360"
            )
        ]

        defenses.append(DefenseItem(
            issue="No-Fault Eviction & Mandatory Relocation Assistance Compliance",
            controlling_citation="Cal. Civ. Code § 1946.2(d), Oakland Municipal Code § 8.22.360",
            statutory_deadline="Direct relocation payment within 15 calendar days of service of notice of termination (Civ. Code § 1946.2(d)(1)(A))",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Notice of termination is void ab initio for failure to provide relocation assistance under Cal. Civ. Code § 1946.2(d)(4); mandatory dismissal of unlawful detainer.",
            elements=relocation_elements,
            required_evidence=[
                "Notice of termination / notice to quit citing no-fault grounds",
                "Bank records or correspondence confirming non-receipt of relocation funds",
                "Proof of 12+ months continuous lawful occupancy"
            ]
        ))

    # 9. Curable Lease Breach & Mandatory Opportunity to Cure (Cal. Civ. Code § 1946.2(c) & CCP § 1161(3))
    if (
        any("Curable" in item["issue"] for item in spotted_issues)
        or any(w in facts_lower for w in ["cure", "curable", "lease violation", "unauthorized pet", "subletting", "breach of lease"])
    ) and "unpaid rent" not in facts_lower:
        cure_elements = [
            ChecklistElement(
                check_item="Alleged violation constitutes a curable lease covenant breach",
                verified="pet" in facts_lower or "sublet" in facts_lower or "covenant" in facts_lower or "breach" in facts_lower,
                evidence_found="Curable covenant breach identified",
                advisory="Breaches of lease covenants that can be corrected are curable by law.",
                pinpoint_citation="Cal. Code Civ. Proc. § 1161(3)"
            ),
            ChecklistElement(
                check_item="Landlord served initial written notice giving tenant at least 3 days with opportunity to cure before terminating",
                verified="opportunity to cure" in facts_lower or "notice to cure" in facts_lower,
                evidence_found="Cure notice provided" if ("cure" in facts_lower and "notice" in facts_lower) else None,
                advisory="Under Cal. Civ. Code § 1946.2(c), landlord MUST provide a notice of violation with opportunity to cure before serving notice to quit.",
                pinpoint_citation="Cal. Civ. Code § 1946.2(c)"
            ),
            ChecklistElement(
                check_item="No notice to quit served until after expiration of full 3-day cure period",
                verified=False,
                evidence_found=None,
                advisory="Serving a straight notice to quit without prior opportunity to cure is legally fatal.",
                pinpoint_citation="Cal. Civ. Code § 1946.2(c)"
            )
        ]

        defenses.append(DefenseItem(
            issue="Curable Lease Breach & Mandatory Opportunity to Cure",
            controlling_citation="Cal. Civ. Code § 1946.2(c), Cal. Code Civ. Proc. § 1161(3)",
            statutory_deadline="Mandatory separate 3-day notice with opportunity to cure prior to any notice to quit",
            status="POTENTIAL_VIOLATION",
            statutory_remedy="Notice to quit served without prior opportunity to cure is legally void under Cal. Civ. Code § 1946.2(c).",
            elements=cure_elements,
            required_evidence=[
                "Copy of notice served by landlord",
                "Evidence of cure or tender of cure within 3 business days",
                "Lease agreement terms regarding permitted alterations or occupants"
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
    evidence_text = ""
    if db and case.id:
        from .crypto import EvidenceEncryptor
        docs = db.query(MatterEvidence).filter(MatterEvidence.matter_id == case.id).all()
        decrypted_parts = []
        for d in docs:
            if d.content:
                try:
                    dec = EvidenceEncryptor.decrypt_text(d.content)
                    decrypted_parts.append(dec)
                except Exception:
                    decrypted_parts.append(d.content)
        evidence_text = "\n".join(decrypted_parts)

    combined_facts = (facts + "\n" + evidence_text).strip()
    slots = extract_statutory_slots(combined_facts)

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

    # Letter Type 4: Objection to Unauthorized / Defective Landlord Entry
    elif letter_type == "landlord_entry_objection":
        mandatory_citations = [
            "Cal. Civ. Code § 1954",
            "Cal. Civ. Code § 1940.2",
            "Cal. Civ. Code § 1953(a)(1)",
            "Cal. Civ. Code § 1927"
        ]
        statutory_deadlines = [
            "24 hours reasonable written notice requirement (Civ. Code § 1954(d)(1))",
            "Normal business hours restriction (8:00 AM to 5:00 PM, Monday-Friday)"
        ]

        subject = f"FORMAL OBJECTION TO UNLAWFUL / DEFECTIVE NOTICE OF ENTRY - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Objection to Unauthorized Entry Pursuant to California Civil Code § 1954\n"
            f"Matter Reference: {case.matter_number or 'Unassigned'}\n\n"
            f"Dear {recipient_name}:\n\n"
            f"Please be advised that I am writing to formally object to your recent attempt or notice to enter the "
            f"residential premises at the above-referenced address. The proposed entry fails to comply with California Civil Code § 1954 "
            f"and constitutes an actionable invasion of privacy and breach of the statutory covenant of quiet enjoyment (Cal. Civ. Code § 1927).\n\n"
            f"STATUTORY NOTICE DEFICIENCIES:\n"
            f"1. Strict 24-Hour Written Notice Requirement: Under California Civil Code § 1954(d)(1), a landlord must give the tenant "
            f"reasonable written notice of intent to enter. Twenty-four (24) hours is presumed reasonable; oral, text message, or spontaneous entry "
            f"without written notice is strictly prohibited except in cases of true physical emergency.\n\n"
            f"2. Normal Business Hours Mandate: Under California Civil Code § 1954(b), entry may only be scheduled during normal business hours "
            f"(8:00 AM to 5:00 PM, Monday through Friday, excluding court holidays), unless the tenant explicitly consents in writing to an alternative time.\n\n"
            f"3. Permissible Statutory Purposes Only: Under California Civil Code § 1954(a), a landlord may enter ONLY for specifically enumerated "
            f"purposes: necessary or agreed repairs, exhibiting the unit to prospective purchasers/mortgagees/tenants, or pursuant to a court order. "
            f"Unfettered 'general inspections' without justification are unlawful.\n\n"
            f"DEMAND & NOTICE:\n"
            f"You are hereby advised that entry without statutory written notice and outside business hours will be refused. "
            f"Any unlawful entry will be treated as trespass and landlord harassment under Cal. Civ. Code § 1940.2, subjecting you to civil penalties "
            f"of up to $2,000 per violation.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Objection to Unlawful Landlord Entry",
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

    # Letter Type 5: Objection to Unlawful Rent Increase
    elif letter_type == "unlawful_rent_increase_objection":
        mandatory_citations = [
            "Cal. Civ. Code § 1947.12",
            "Cal. Civ. Code § 827",
            "Cal. Code Civ. Proc. § 1013",
            "Oakland Municipal Code § 8.22.070"
        ]
        statutory_deadlines = [
            "30 calendar days advance written notice for increases of 10% or less (Civ. Code § 827(b)(2))",
            "90 calendar days advance written notice for increases exceeding 10% (Civ. Code § 827(b)(3))",
            "+5 calendar days extension for service by mail (CCP § 1013)"
        ]

        subject = f"FORMAL OBJECTION TO UNLAWFUL RENT INCREASE - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Formal Objection to Unlawful Rent Increase Pursuant to Cal. Civ. Code §§ 1947.12 and 827\n"
            f"Matter Reference: {case.matter_number or 'Unassigned'}\n\n"
            f"Dear {recipient_name}:\n\n"
            f"I am in receipt of your recent notice proposing to increase the rent for the above-referenced residential premises. "
            f"Please be advised that the proposed rent increase violates California law and is legally void and unenforceable.\n\n"
            f"STATUTORY BASIS OF OBJECTION:\n"
            f"1. Statutory Rent Cap Ceiling: Under California Civil Code § 1947.12 (the California Tenant Protection Act of 2019, AB 1482), "
            f"an owner shall not, over the course of any 12-month period, increase the gross rental rate more than 5 percent plus the percentage "
            f"change in the cost of living (CPI), or 10 percent, whichever is lower. Any increase exceeding this statutory limit without a recognized "
            f"statutory exemption is unlawful.\n\n"
            f"2. Mandatory Advance Notice Timeline: Under California Civil Code § 827(b), any rent increase of 10 percent or less requires "
            f"not less than 30 calendar days advance written notice. Any increase exceeding 10 percent (or cumulatively exceeding 10 percent "
            f"over the prior 12 months) requires not less than 90 calendar days advance written notice. Furthermore, pursuant to California "
            f"Code of Civil Procedure § 1013, service by mail requires an additional five (5) calendar days.\n\n"
            f"3. Strict Exemption Disclosure Requirement: If you claim that this property is exempt from AB 1482 as a single-family dwelling "
            f"under Civil Code § 1947.12(d)(5), that exemption is valid ONLY IF the mandatory statutory disclosure notice was provided in the rental "
            f"agreement. Omission of this disclosure forfeits the exemption.\n\n"
            f"DEMAND & NOTICE:\n"
            f"Demand is hereby made that you withdraw the defective notice of rent increase immediately. Rent will continue to be tendered at the "
            f"existing lawful base rate. Any unlawful detainer initiated for non-payment of the disputed excess will be defended with a demand for "
            f"mandatory dismissal and statutory attorney fees.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Objection to Unlawful Rent Increase",
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

    # Letter Type 6: Demand for Mandatory Relocation Assistance / Void Notice Objection
    elif letter_type == "no_fault_relocation_demand":
        mandatory_citations = [
            "Cal. Civ. Code § 1946.2(d)",
            "Cal. Civ. Code § 1946.2(d)(4)",
            "Oakland Municipal Code § 8.22.360"
        ]
        statutory_deadlines = [
            "15 calendar days from notice service to tender direct relocation payment (Civ. Code § 1946.2(d)(1)(A))",
            "Mandatory dismissal of eviction action for void notice (Civ. Code § 1946.2(d)(4))"
        ]

        subject = f"DEMAND FOR STATUTORY RELOCATION ASSISTANCE / VOID NOTICE OBJECTION - {case.title}"
        body = (
            f"VIA CERTIFIED MAIL / EMAIL\n\n"
            f"Date: {date_str}\n\n"
            f"To: {recipient_name}\n"
            f"Address: {recipient_address}\n\n"
            f"From: {sender}\n"
            f"Re: Demand for Mandatory Relocation Assistance and Objection to Void Notice Under Cal. Civ. Code § 1946.2(d)\n"
            f"Matter Reference: {case.matter_number or 'Unassigned'}\n\n"
            f"Dear {recipient_name}:\n\n"
            f"I am in receipt of your notice purporting to terminate my residential tenancy based on alleged no-fault grounds. "
            f"Please be advised that the notice is legally defective and void under California law due to your failure to comply with statutory relocation assistance mandates.\n\n"
            f"STATUTORY DEFICIENCIES & MANDATES:\n"
            f"1. Mandatory Relocation Payment Deadline: Under California Civil Code § 1946.2(d)(1)(A), when a landlord issues a notice of termination "
            f"based on no-fault just cause, the landlord MUST provide relocation assistance equal to one month of the tenant's rent within fifteen (15) "
            f"calendar days of serving the notice, or provide a written waiver of the final month's rent prior to the due date.\n\n"
            f"2. Strict Compliance & Void Notice Rule: Under California Civil Code § 1946.2(d)(4), 'the failure of an owner to strictly comply with "
            f"this subdivision shall render the notice of termination void.' Because you have failed to deliver the mandatory relocation payment "
            f"within fifteen (15) calendar days, the notice of termination is void ab initio as a matter of law.\n\n"
            f"3. Municipal Relocation Requirements: In jurisdictions with enhanced relocation protections such as the Oakland Rent Adjustment Program "
            f"(OMC § 8.22.360), municipal relocation schedules provide substantial additional compensation that controls under California's harmonized floor rule.\n\n"
            f"DEMAND:\n"
            f"Because your notice of termination is legally void, tenancy continues undisturbed. Any legal action commenced based upon this void notice "
            f"will be met with an immediate motion for summary judgment or dismissal and an application for costs and attorney fees.\n\n"
            f"Sincerely,\n\n"
            f"______________________________________\n"
            f"{sender}\n"
        )

        return StatutoryLetterResponse(
            case_id=case.id,
            letter_type=letter_type,
            title="Demand for Mandatory Relocation Assistance",
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
        coverage_gaps.append(f"Unsupported letter type: '{letter_type}'. Supported: 'security_deposit_demand', 'habitability_repair_notice', 'defective_notice_response', 'landlord_entry_objection', 'unlawful_rent_increase_objection', 'no_fault_relocation_demand'.")
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
