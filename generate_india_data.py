import pandas as pd
import numpy as np
import random

# Fixed random state for reproducibility
np.random.seed(42)
random.seed(42)

# Names and groups
UPPER_CASTE = [
    "Rajesh Sharma", "Priya Mishra", "Amit Verma",
    "Sunita Tiwari", "Rahul Pandey", "Kavita Joshi",
    "Vikram Singh", "Anita Kulkarni", "Suresh Iyer",
    "Meera Pillai"
]

OBC = [
    "Ramesh Yadav", "Sunita Kushwaha", "Arun Maurya",
    "Geeta Kurmi", "Mohan Prajapati", "Sita Lodhi"
]

SC = [
    "Suresh Chamar", "Geeta Jatav", "Ramesh Valmiki",
    "Anita Dhobi", "Mohan Pasi"
]

MUSLIM = [
    "Mohammad Khan", "Fatima Ansari", 
    "Abdul Qureshi", "Aisha Siddiqui",
    "Rahul Sheikh", "Zainab Malik"
]

CHRISTIAN = [
    "Joseph Masih", "Mary Thomas", 
    "John Fernandez", "Sarah DSouza"
]

# Hiring Probabilities
HIRE_PROB = {
    "Upper Caste": 0.70,
    "OBC": 0.50,
    "SC": 0.30,
    "Muslim": 0.35,
    "Christian": 0.55
}

# Distribution of 300 rows
counts = {
    "Upper Caste": 100,
    "OBC": 70,
    "SC": 50,
    "Muslim": 50,
    "Christian": 30
}

data = []

# Generate data
for group, count in counts.items():
    if group == "Upper Caste":
        names_pool = UPPER_CASTE
        religion = "Hindu"
    elif group == "OBC":
        names_pool = OBC
        religion = "Hindu"
    elif group == "SC":
        names_pool = SC
        religion = "Hindu"
    elif group == "Muslim":
        names_pool = MUSLIM
        religion = "Muslim"
    else:
        names_pool = CHRISTIAN
        religion = "Christian"
        
    for _ in range(count):
        # Pick a random name from the pool
        name = random.choice(names_pool)
        
        # Gender inference from first name ending (rough heuristic)
        first_name = name.split()[0]
        if first_name in ["Priya", "Sunita", "Kavita", "Anita", "Meera", "Geeta", "Sita", "Fatima", "Aisha", "Zainab", "Mary", "Sarah"]:
            gender = "Female"
        else:
            gender = "Male"
            
        # Age
        age = np.random.randint(22, 45)
        
        # Statistically identical experience & education across groups
        years_experience = max(0, round(np.random.normal(5, 2.5), 1))
        education_tier = np.random.choice(["Tier 1", "Tier 2", "Tier 3"], p=[0.2, 0.5, 0.3])
        state = np.random.choice(["Maharashtra", "Delhi", "Karnataka", "Uttar Pradesh", "Tamil Nadu"])
        
        # Hired based on group probability
        hired = 1 if random.random() <= HIRE_PROB[group] else 0
        
        data.append({
            "name": name,
            "gender": gender,
            "age": age,
            "caste_group": group if religion == "Hindu" else "N/A",
            "religion": religion,
            "state": state,
            "years_experience": years_experience,
            "education_tier": education_tier,
            "hired": hired
        })

# Shuffle the dataset
random.shuffle(data)

df = pd.DataFrame(data)

# Reorder columns
df = df[["name", "gender", "age", "caste_group", "religion", "state", "years_experience", "education_tier", "hired"]]

df.to_csv("sample_india_hiring.csv", index=False)
print("Successfully generated sample_india_hiring.csv with 300 rows.")
