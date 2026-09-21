"""
claims_data.py — Curated dataset of 10 claims for Week 7 Practical Task Set D.

Requirements satisfied:
- Exactly 10 realistic claims over policy endorsements (HO-0304 to HO-0309).
- At least 3 claims where Step 3 strictly depends on what Step 2 found in adjuster notes:
  - CLM-2024-10002: Notes reveal continuous seepage > 14 days -> triggers E-11 water damage exclusion.
  - CLM-2024-10005: Notes reveal mold from long-term atmospheric humidity -> triggers E-22 mold exclusion.
  - CLM-2024-10007: Notes reveal earthquake tremors -> triggers E-31 earth movement exclusion.
  - CLM-2024-10010: Notes reveal commercial tax business client injury -> triggers E-19 business pursuits exclusion.
- Covered claims with deductible deductions (HO-0304 burst pipe, HO-0305 named storm).
- Clean ground-truth data to evaluate correctness (pass rate).
"""

from typing import Dict, Any, List

CLAIMS_DATABASE: Dict[str, Dict[str, Any]] = {
    "CLM-2024-10001": {
        "claim_id": "CLM-2024-10001",
        "policy_number": "POL-HO-772101",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-03-15",
        "claimed_amount": 3200.00,
        "excess_amount": 1500.00,
        "adjuster_notes": (
            "Insured reports burst supply line under kitchen sink on 15 Mar 2024. "
            "Water damage confined to kitchen cabinet base and vinyl flooring approx 12 sq ft. "
            "Plumber invoice confirms sudden failure of braided steel supply line, with no evidence "
            "of prior leakage or slow seepage. Repair estimate $3,200. Deductible $1,500. "
            "Policy form HO-0304 ed 03-24 applies."
        ),
        "expected_status": "COVERED",
        "expected_payout": 1700.00,
        "expected_exclusion": None,
        "dynamic_dependency": False,
        "description": "Sudden pipe burst — covered under HO-0304 after deductible."
    },
    "CLM-2024-10002": {
        "claim_id": "CLM-2024-10002",
        "policy_number": "POL-HO-772102",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-04-02",
        "claimed_amount": 4500.00,
        "excess_amount": 2000.00,
        "adjuster_notes": (
            "Insured reports water staining and rotted subfloor in upstairs bathroom. "
            "Adjuster inspection revealed continuous slow drip from toilet fill valve occurring "
            "over an estimated period of 6 months. Continuous seepage confirmed exceeding 14 "
            "consecutive days. Per CLAUSE WD-1 and Exclusion Table E-11 of HO-0304 ed 03-24, "
            "damage caused by continuous or repeated seepage or leakage over weeks/months is excluded. "
            "Claim denied."
        ),
        "expected_status": "DENIED",
        "expected_payout": 0.00,
        "expected_exclusion": "E-11",
        "dynamic_dependency": True,
        "description": "Continuous seepage > 14 days -> Step 2 notes trigger E-11 exclusion lookup."
    },
    "CLM-2024-10003": {
        "claim_id": "CLM-2024-10003",
        "policy_number": "POL-HO-772103",
        "form_number": "HO-0305",
        "edition_date": "03-24",
        "date_of_loss": "2024-05-10",
        "claimed_amount": 12500.00,
        "excess_amount": 5000.00,
        "adjuster_notes": (
            "Named Storm Ian-2024 made landfall within 50 miles of insured property on 10 May 2024. "
            "Severe wind ripped shingles off roof and caused partial structural collapse on north face. "
            "Valid loss under HO-0305 ed 03-24. Named Storm deductible applies per CLAUSE NS-2: "
            "mandatory $5,000 deductible. Claimed repair cost $12,500. Coverage confirmed."
        ),
        "expected_status": "COVERED",
        "expected_payout": 7500.00,
        "expected_exclusion": None,
        "dynamic_dependency": False,
        "description": "Named storm wind damage — covered under HO-0305 with storm deductible."
    },
    "CLM-2024-10004": {
        "claim_id": "CLM-2024-10004",
        "policy_number": "POL-HO-772104",
        "form_number": "HO-0306",
        "edition_date": "04-24",
        "date_of_loss": "2024-06-18",
        "claimed_amount": 6000.00,
        "excess_amount": 1000.00,
        "adjuster_notes": (
            "Insured discovers extensive black mold on basement drywall following confirmed sudden "
            "hot water heater tank burst on 18 Jun 2024. Mold remediation required immediately. "
            "Under HO-0306 ed 04-24, CLAUSE MF-2 explicitly covers mold remediation costs when "
            "the mold is the direct result of a sudden and accidental water discharge. Remediation "
            "cost $6,000. Policy excess $1,000 applies. Coverage confirmed."
        ),
        "expected_status": "COVERED",
        "expected_payout": 5000.00,
        "expected_exclusion": None,
        "dynamic_dependency": False,
        "description": "Mold resulting directly from sudden water discharge — covered under MF-2."
    },
    "CLM-2024-10005": {
        "claim_id": "CLM-2024-10005",
        "policy_number": "POL-HO-772105",
        "form_number": "HO-0306",
        "edition_date": "04-24",
        "date_of_loss": "2024-07-22",
        "claimed_amount": 3800.00,
        "excess_amount": 750.00,
        "adjuster_notes": (
            "Insured filed claim for mold found across exterior cedar siding and eaves. "
            "Physical inspection and laboratory swab analysis establish mold growth caused solely "
            "by ambient summer humidity, lack of ventilation, and seasonal weather condensation, "
            "not from any plumbing break or sudden accidental discharge. Under HO-0306 CLAUSE MF-4 "
            "and exclusion E-22, mold resulting from atmospheric humidity or condensation is excluded. "
            "Claim denied."
        ),
        "expected_status": "DENIED",
        "expected_payout": 0.00,
        "expected_exclusion": "E-22",
        "dynamic_dependency": True,
        "description": "Mold from ambient humidity -> Step 2 notes trigger E-22 exclusion lookup."
    },
    "CLM-2024-10006": {
        "claim_id": "CLM-2024-10006",
        "policy_number": "POL-HO-772106",
        "form_number": "HO-0307",
        "edition_date": "04-24",
        "date_of_loss": "2024-08-12",
        "claimed_amount": 4200.00,
        "excess_amount": 500.00,
        "adjuster_notes": (
            "Scheduled diamond engagement ring (Schedule Item #1, appraised at $4,500) reported lost/stolen "
            "during domestic transit on 12 Aug 2024. Police report filed. Scheduled Personal Property endorsement "
            "HO-0307 ed 04-24 CLAUSE SP-1 covers scheduled items against mysterious disappearance and theft "
            "worldwide. Claimed loss amount $4,200. Policy excess $500 applies. Coverage confirmed."
        ),
        "expected_status": "COVERED",
        "expected_payout": 3700.00,
        "expected_exclusion": None,
        "dynamic_dependency": False,
        "description": "Scheduled jewelry theft/disappearance — covered under HO-0307."
    },
    "CLM-2024-10007": {
        "claim_id": "CLM-2024-10007",
        "policy_number": "POL-HO-772107",
        "form_number": "HO-0308",
        "edition_date": "05-24",
        "date_of_loss": "2024-09-01",
        "claimed_amount": 18000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Insured reports cracked foundation, masonry separation, and shifted load-bearing wall "
            "following 4.2 magnitude regional earthquake tremors on 01 Sep 2024. Engineering inspection "
            "confirms damage was directly caused by seismic earth movement. Per HO-0308 ed 05-24 "
            "CLAUSE EM-1 and exclusion E-31, earthquake tremors and all forms of earth movement are "
            "expressly excluded. Claim denied in full."
        ),
        "expected_status": "DENIED",
        "expected_payout": 0.00,
        "expected_exclusion": "E-31",
        "dynamic_dependency": True,
        "description": "Earthquake tremors -> Step 2 notes trigger E-31 earth movement exclusion lookup."
    },
    "CLM-2024-10008": {
        "claim_id": "CLM-2024-10008",
        "policy_number": "POL-HO-772108",
        "form_number": "HO-0308",
        "edition_date": "05-24",
        "date_of_loss": "2024-09-15",
        "claimed_amount": 9500.00,
        "excess_amount": 1000.00,
        "adjuster_notes": (
            "Insured reports driveway collapse and subterranean cavity under detached garage. "
            "Geotechnical survey confirmed sinkhole collapse on 15 Sep 2024. Under HO-0308 ed 05-24 "
            "Exclusion Table, E-33 categorizes sinkhole collapse under the broad earth movement exclusion group. "
            "Entire loss excluded under policy terms. Claim denied."
        ),
        "expected_status": "DENIED",
        "expected_payout": 0.00,
        "expected_exclusion": "E-33",
        "dynamic_dependency": True,
        "description": "Sinkhole collapse -> Step 2 notes trigger E-33 sinkhole exclusion lookup."
    },
    "CLM-2024-10009": {
        "claim_id": "CLM-2024-10009",
        "policy_number": "POL-HO-772109",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-10-05",
        "claimed_amount": 800.00,
        "excess_amount": 1000.00,
        "adjuster_notes": (
            "Sudden break of washing machine cold water intake hose on 05 Oct 2024. "
            "Water spread across laundry room tile. Professional dry-out and baseboard replacement cost $800. "
            "Loss is covered under HO-0304 sudden and accidental water discharge. However, policy excess "
            "is $1,000. Because loss ($800) is below excess ($1,000), payable amount is $0.00."
        ),
        "expected_status": "COVERED",
        "expected_payout": 0.00,
        "expected_exclusion": None,
        "dynamic_dependency": False,
        "description": "Loss below deductible — covered event but payout is $0.00 after excess."
    },
    "CLM-2024-10010": {
        "claim_id": "CLM-2024-10010",
        "policy_number": "POL-HO-772110",
        "form_number": "HO-0309",
        "edition_date": "05-24",
        "date_of_loss": "2024-10-20",
        "claimed_amount": 5500.00,
        "excess_amount": 500.00,
        "adjuster_notes": (
            "Insured operates a commercial tax preparation and bookkeeping practice from residential home office. "
            "A paying client slipped on an office rug during a scheduled appointment and filed bodily injury claim. "
            "HO-0309 ed 05-24 CLAUSE BP-1 and Exclusion E-19 exclude bodily injury arising out of business pursuits "
            "conducted on the residence premises. Claim denied."
        ),
        "expected_status": "DENIED",
        "expected_payout": 0.00,
        "expected_exclusion": "E-19",
        "dynamic_dependency": True,
        "description": "Home business injury -> Step 2 notes trigger E-19 business pursuits exclusion."
    }
}


def get_all_claim_ids() -> List[str]:
    """Return the ordered list of all 10 claim IDs."""
    return list(CLAIMS_DATABASE.keys())


def get_claim_by_id(claim_id: str) -> Dict[str, Any]:
    """Retrieve raw claim record from database."""
    if claim_id not in CLAIMS_DATABASE:
        raise KeyError(f"Claim ID '{claim_id}' not found in database.")
    return CLAIMS_DATABASE[claim_id]
