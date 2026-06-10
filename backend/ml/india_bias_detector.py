from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Any

# Surname to caste group mapping
# Based on common Indian surnames
UPPER_CASTE_SURNAMES = [
    "sharma", "verma", "mishra", "tiwari", 
    "pandey", "dubey", "shukla", "trivedi",
    "joshi", "pant", "dixit", "bajpai",
    "iyer", "iyengar", "menon", "nair",
    "pillai", "namboothiri", "reddy", "rao",
    "bhat", "hegde", "kulkarni", "joshi",
    "mukherjee", "chatterjee", "banerjee",
    "bhattacharya", "sen", "bose", "ghosh",
    "mehta", "shah", "patel", "desai",
    "kapoor", "khanna", "malhotra", "chopra",
    "singh", "gill", "sidhu", "grewal",
    "agrawal", "agarwal", "aggarwal",
]

OBC_SURNAMES = [
    "yadav", "kushwaha", "maurya", "lodhi",
    "kurmi", "koeri", "prajapati", "kewat",
    "bind", "nishad", "mallah", "kahar",
    "gujjar", "ahir", "jat", "saini",
    "teli", "khatik", "lohar", "luhar",
    "kumhar", "darji", "nai", "hajam",
]

SC_SURNAMES = [
    "chamar", "jatav", "valmiki", "balmiki",
    "dhobi", "pasi", "kori", "bhar",
    "musahar", "dom", "nat", "kanjar",
    "mahar", "mang", "chambhar", "holar",
    "pariah", "pulaya", "cheruma",
]

ST_SURNAMES = [
    "munda", "oraon", "santal", "ho",
    "gond", "bhil", "meena", "garasia",
    "sahariya", "kol", "korku", "baiga",
]

MUSLIM_SURNAMES = [
    "khan", "ansari", "qureshi", "siddiqui",
    "sheikh", "malik", "mirza", "hussain",
    "ali", "ahmed", "mohammad", "pathan",
    "shaikh", "mansoori", "saifi", "lodhi",
    "abbasi", "farooqui", "hashmi", "rizvi",
]

CHRISTIAN_SURNAMES = [
    "masih", "massey", "watson", "fernandez",
    "dsouza", "d'souza", "pereira", "rodrigues",
    "pinto", "lobo", "sequeira", "gomes",
    "xavier", "mathew", "thomas", "george",
    "philip", "jacob", "john", "paul",
]

NORTH_INDIA_STATES = [
    "uttar pradesh", "bihar", "rajasthan",
    "madhya pradesh", "haryana", "punjab",
    "uttarakhand", "himachal pradesh",
    "jharkhand", "chhattisgarh"
]

SOUTH_INDIA_STATES = [
    "tamil nadu", "kerala", "karnataka",
    "andhra pradesh", "telangana"
]

METRO_CITIES = [
    "mumbai", "delhi", "bangalore", 
    "bengaluru", "hyderabad", "chennai",
    "kolkata", "pune", "ahmedabad"
]


def infer_caste_group(surname: str) -> str:
    s = surname.lower().strip()
    if s in UPPER_CASTE_SURNAMES:
        return "Upper Caste"
    elif s in OBC_SURNAMES:
        return "OBC"
    elif s in SC_SURNAMES:
        return "SC"
    elif s in ST_SURNAMES:
        return "ST"
    else:
        return "Unknown"


def infer_religion(surname: str) -> str:
    s = surname.lower().strip()
    if s in MUSLIM_SURNAMES:
        return "Muslim"
    elif s in CHRISTIAN_SURNAMES:
        return "Christian"
    elif s in UPPER_CASTE_SURNAMES + OBC_SURNAMES:
        return "Hindu (likely)"
    else:
        return "Unknown"


def extract_surname(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return parts[-1].lower()
    return parts[0].lower() if parts else ""


def detect_regional_bias(
    df: pd.DataFrame,
    decision_column: str,
    state_column: str = "state",
    city_column: str = "city",
) -> dict:
    
    if state_column not in df.columns:
        return {"detected": False}
    
    df = df.copy()
    df["_region"] = df[state_column].str.lower().apply(
        lambda s: "North India" 
        if s in NORTH_INDIA_STATES
        else "South India" 
        if s in SOUTH_INDIA_STATES
        else "Other"
    )
    
    df["_outcome"] = (
        df[decision_column] == 1
    ).astype(int)
    
    region_rates = df.groupby(
        "_region"
    )["_outcome"].mean()
    
    if len(region_rates) > 1:
        di = (
            region_rates.min() / 
            region_rates.max()
        )
        return {
            "detected": bool(di < 0.80),
            "disparate_impact": round(float(di), 4),
            "rates": {
                k: round(float(v), 4) 
                for k, v in region_rates.items()
            }
        }
    
    return {"detected": False}


def run_india_bias_scan(
    df: pd.DataFrame,
    decision_column: str = "hired",
    positive_value: Any = 1,
    name_column: str = "name",
) -> dict[str, Any]:
    
    results = {
        "caste_bias": None,
        "religion_bias": None,
        "regional_bias": None,
        "surname_proxy_detected": False,
        "high_risk_dimensions": [],
        "group_selection_rates": {},
        "india_fairness_score": 100,
        "findings": [],
    }
    
    if name_column not in df.columns:
        results["findings"].append(
            "Name column not found — "
            "surname analysis skipped"
        )
        return results
    
    # Extract surnames and infer groups
    df = df.copy()
    df["_surname"] = df[name_column].apply(
        extract_surname
    )
    df["_caste_group"] = df["_surname"].apply(
        infer_caste_group
    )
    df["_religion"] = df["_surname"].apply(
        infer_religion
    )
    df["_outcome"] = (
        df[decision_column] == positive_value
    ).astype(int)
    
    # Caste bias analysis
    caste_groups = df[
        df["_caste_group"] != "Unknown"
    ].groupby("_caste_group")["_outcome"].mean()
    
    if len(caste_groups) > 1:
        max_rate = caste_groups.max()
        min_rate = caste_groups.min()
        
        if max_rate > 0:
            caste_di = min_rate / max_rate
        else:
            caste_di = 1.0
            
        results["caste_bias"] = {
            "disparate_impact": round(
                float(caste_di), 4
            ),
            "selection_rates": {
                k: round(float(v), 4) 
                for k, v in caste_groups.items()
            },
            "bias_detected": bool(caste_di < 0.80),
            "highest_selected_group": (
                caste_groups.idxmax()
            ),
            "lowest_selected_group": (
                caste_groups.idxmin()
            ),
        }
        
        if caste_di < 0.80:
            results["high_risk_dimensions"].append(
                "caste"
            )
            results["findings"].append(
                f"Caste bias detected: "
                f"{caste_groups.idxmin()} candidates "
                f"selected at {caste_di:.0%} the rate "
                f"of {caste_groups.idxmax()} candidates"
            )
    
    # Religion bias analysis
    religion_groups = df[
        ~df["_religion"].str.contains("Unknown")
    ].groupby("_religion")["_outcome"].mean()
    
    if len(religion_groups) > 1:
        max_rate = religion_groups.max()
        min_rate = religion_groups.min()
        
        if max_rate > 0:
            religion_di = min_rate / max_rate
        else:
            religion_di = 1.0
            
        results["religion_bias"] = {
            "disparate_impact": round(
                float(religion_di), 4
            ),
            "selection_rates": {
                k: round(float(v), 4)
                for k, v in religion_groups.items()
            },
            "bias_detected": bool(religion_di < 0.80),
        }
        
        if religion_di < 0.80:
            results["high_risk_dimensions"].append(
                "religion"
            )
            results["findings"].append(
                f"Religion bias detected: "
                f"Disparate Impact {religion_di:.4f}"
            )
    
    # Check if surname is being used as proxy
    # High correlation between surname and outcome
    # suggests proxy discrimination
    if len(df["_surname"].unique()) > 10:
        surname_rates = df.groupby(
            "_surname"
        )["_outcome"].mean()
        
        if surname_rates.std() > 0.3:
            results["surname_proxy_detected"] = True
            results["high_risk_dimensions"].append(
                "surname_proxy"
            )
            results["findings"].append(
                "WARNING: High variance in outcomes "
                "by surname suggests surname may be "
                "used as a proxy for caste/religion "
                "discrimination"
            )
            
    # Check for regional bias if state column exists
    regional_result = detect_regional_bias(
        df, 
        decision_column="_outcome", 
        state_column="state" if "state" in df.columns else "Location"
    )
    results["regional_bias"] = regional_result
    if regional_result.get("detected"):
        results["high_risk_dimensions"].append("region")
        results["findings"].append(
            f"Regional bias detected: Disparate Impact "
            f"{regional_result['disparate_impact']:.4f} "
            f"between North and South India"
        )
    
    # Calculate India fairness score
    penalties = 0
    if results.get("caste_bias") and results["caste_bias"].get("bias_detected"):
        penalties += 30
    if results.get("religion_bias") and results["religion_bias"].get("bias_detected"):
        penalties += 25
    if results["surname_proxy_detected"]:
        penalties += 20
    if results.get("regional_bias") and results["regional_bias"].get("detected"):
        penalties += 15
        
    results["india_fairness_score"] = max(
        100 - penalties, 0
    )
    
    return results
