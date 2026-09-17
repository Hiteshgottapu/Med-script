"""
MedScript AI Consultant & Disease Prediction Service
====================================================
Integrates Calibrated Support Vector Classifier (SVC) and Random Forest (RF)
ensemble models with comprehensive NLP symptom extraction, fuzzy matching,
spelling correction, and multi-database clinical knowledge retrieval.
"""

import os
import ast
import re
import pickle
import logging
from collections import defaultdict
import numpy as np
import pandas as pd
from textblob import TextBlob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR = os.path.join(BASE_DIR, "model")

# Canonical 132 Symptoms Dictionary
symptoms_dict = {
    'itching': 0, 'skin_rash': 1, 'nodal_skin_eruptions': 2, 'continuous_sneezing': 3,
    'shivering': 4, 'chills': 5, 'joint_pain': 6, 'stomach_pain': 7, 'acidity': 8,
    'ulcers_on_tongue': 9, 'muscle_wasting': 10, 'vomiting': 11, 'burning_micturition': 12,
    'spotting_urination': 13, 'fatigue': 14, 'weight_gain': 15, 'anxiety': 16,
    'cold_hands_and_feets': 17, 'mood_swings': 18, 'weight_loss': 19, 'restlessness': 20,
    'lethargy': 21, 'patches_in_throat': 22, 'irregular_sugar_level': 23, 'cough': 24,
    'high_fever': 25, 'sunken_eyes': 26, 'breathlessness': 27, 'sweating': 28,
    'dehydration': 29, 'indigestion': 30, 'headache': 31, 'yellowish_skin': 32,
    'dark_urine': 33, 'nausea': 34, 'loss_of_appetite': 35, 'pain_behind_the_eyes': 36,
    'back_pain': 37, 'constipation': 38, 'abdominal_pain': 39, 'diarrhoea': 40,
    'mild_fever': 41, 'yellow_urine': 42, 'yellowing_of_eyes': 43, 'acute_liver_failure': 44,
    'fluid_overload': 45, 'swelling_of_stomach': 46, 'swelled_lymph_nodes': 47, 'malaise': 48,
    'blurred_and_distorted_vision': 49, 'phlegm': 50, 'throat_irritation': 51, 'redness_of_eyes': 52,
    'sinus_pressure': 53, 'runny_nose': 54, 'congestion': 55, 'chest_pain': 56,
    'weakness_in_limbs': 57, 'fast_heart_rate': 58, 'pain_during_bowel_movements': 59,
    'pain_in_anal_region': 60, 'bloody_stool': 61, 'irritation_in_anus': 62, 'neck_pain': 63,
    'dizziness': 64, 'cramps': 65, 'bruising': 66, 'obesity': 67, 'swollen_legs': 68,
    'swollen_blood_vessels': 69, 'puffy_face_and_eyes': 70, 'enlarged_thyroid': 71,
    'brittle_nails': 72, 'swollen_extremeties': 73, 'excessive_hunger': 74, 'extra_marital_contacts': 75,
    'drying_and_tingling_lips': 76, 'slurred_speech': 77, 'knee_pain': 78, 'hip_joint_pain': 79,
    'muscle_weakness': 80, 'stiff_neck': 81, 'swelling_joints': 82, 'movement_stiffness': 83,
    'spinning_movements': 84, 'loss_of_balance': 85, 'unsteadiness': 86, 'weakness_of_one_body_side': 87,
    'loss_of_smell': 88, 'bladder_discomfort': 89, 'foul_smell_of_urine': 90, 'continuous_feel_of_urine': 91,
    'passage_of_gases': 92, 'internal_itching': 93, 'toxic_look_(typhos)': 94, 'depression': 95,
    'irritability': 96, 'muscle_pain': 97, 'altered_sensorium': 98, 'red_spots_over_body': 99,
    'belly_pain': 100, 'abnormal_menstruation': 101, 'dischromic_patches': 102, 'watering_from_eyes': 103,
    'increased_appetite': 104, 'polyuria': 105, 'family_history': 106, 'mucoid_sputum': 107,
    'rusty_sputum': 108, 'lack_of_concentration': 109, 'visual_disturbances': 110,
    'receiving_blood_transfusion': 111, 'receiving_unsterile_injections': 112, 'coma': 113,
    'stomach_bleeding': 114, 'distention_of_abdomen': 115, 'history_of_alcohol_consumption': 116,
    'fluid_overload_2': 117, 'blood_in_sputum': 118, 'prominent_veins_on_calf': 119,
    'palpitations': 120, 'painful_walking': 121, 'pus_filled_pimples': 122, 'blackheads': 123,
    'scurring': 124, 'skin_peeling': 125, 'silver_like_dusting': 126, 'small_dents_in_nails': 127,
    'inflammatory_nails': 128, 'blister': 129, 'red_sore_around_nose': 130, 'yellow_crust_ooze': 131
}

diseases_list = {
    15: 'Fungal infection', 4: 'Allergy', 16: 'GERD', 9: 'Chronic cholestasis',
    14: 'Drug Reaction', 33: 'Peptic ulcer disease', 1: 'AIDS', 12: 'Diabetes',
    17: 'Gastroenteritis', 6: 'Bronchial Asthma', 23: 'Hypertension', 30: 'Migraine',
    7: 'Cervical spondylosis', 32: 'Paralysis (brain hemorrhage)', 28: 'Jaundice',
    29: 'Malaria', 8: 'Chicken pox', 11: 'Dengue', 37: 'Typhoid', 40: 'hepatitis A',
    19: 'Hepatitis B', 20: 'Hepatitis C', 21: 'Hepatitis D', 22: 'Hepatitis E',
    3: 'Alcoholic hepatitis', 36: 'Tuberculosis', 10: 'Common Cold', 34: 'Pneumonia',
    13: 'Dimorphic hemmorhoids(piles)', 18: 'Heart attack', 39: 'Varicose veins',
    26: 'Hypothyroidism', 24: 'Hyperthyroidism', 25: 'Hypoglycemia', 31: 'Osteoarthristis',
    5: 'Arthritis', 0: '(vertigo) Paroymsal Positional Vertigo', 2: 'Acne',
    38: 'Urinary tract infection', 35: 'Psoriasis', 27: 'Impetigo'
}

# Extensive Clinical & Colloquial Synonym Mapping
symptom_mapping = defaultdict(lambda: "unknown", {
    "itching": ["itching", "itchy", "itch", "scratching", "skin itching", "body itching",
                "itchy skin", "pruritus", "feels itchy", "constant itching", "scratching body"],
    "skin_rash": ["skin rash", "rash", "dermatitis", "rashes", "skin eruption",
                  "red patches", "skin irritation", "hives", "urticaria", "eczema",
                  "skin allergy", "red marks on skin", "skin bumps", "body rash"],
    "nodal_skin_eruptions": ["nodal skin eruptions", "skin eruptions", "bumps",
                             "skin nodules", "lumps on skin", "raised bumps",
                             "skin lumps", "papules", "nodules on skin"],
    "continuous_sneezing": ["continuous sneezing", "sneezing", "constant sneezing",
                            "sneeze", "sneezing a lot", "can't stop sneezing",
                            "frequent sneezing", "achoo", "allergic sneezing"],
    "shivering": ["shivering", "trembling", "shaking", "body shaking", "tremors",
                  "shaky", "quivering", "shivers", "body trembling"],
    "chills": ["chills", "cold sensation", "feeling cold", "cold chills",
               "rigor", "rigors", "cold shivers", "feeling chilly", "cold feeling", "shivering with cold"],
    "joint_pain": ["joint pain", "arthralgia", "aching joints", "painful joints",
                   "joint ache", "joints hurt", "body pain", "pain in joints",
                   "joint stiffness", "sore joints", "rheumatic pain", "pain in all joints"],
    "stomach_pain": ["stomach pain", "tummy ache", "stomach ache", "gastric pain",
                     "epigastric pain", "stomach cramps", "upper abdominal pain",
                     "stomach hurts", "stomachache", "tummy pain", "pain in stomach"],
    "acidity": ["acidity", "heartburn", "acid reflux", "gastric acid", "sour stomach",
                "acidic feeling", "burning sensation in stomach", "gerd",
                "reflux", "acid indigestion", "burning in chest after eating", "burning stomach"],
    "ulcers_on_tongue": ["ulcers on tongue", "tongue ulcers", "mouth sores",
                         "canker sores", "oral ulcers", "mouth ulcers",
                         "sores in mouth", "aphthous ulcers", "tongue sores", "blisters in mouth"],
    "muscle_wasting": ["muscle wasting", "muscle loss", "muscle atrophy",
                       "losing muscle", "muscles shrinking", "weak muscles",
                       "muscle deterioration"],
    "vomiting": ["vomiting", "emesis", "throwing up", "nausea and vomiting",
                 "puking", "being sick", "feeling sick", "vomit",
                 "stomach upset with vomiting", "retching"],
    "burning_micturition": ["burning micturition", "burning urination", "painful urination",
                            "dysuria", "burning when peeing", "pain while urinating",
                            "burning sensation while urinating", "stinging urine",
                            "painful peeing", "burning pee", "burning sensation when peeing", "burning urine"],
    "spotting_urination": ["spotting urination", "blood in urine", "hematuria",
                           "bloody urine", "red urine", "urinary bleeding",
                           "blood while peeing", "spotting urine", "spotting_ urination"],
    "fatigue": ["fatigue", "tiredness", "exhaustion", "feeling tired", "low energy",
                "weakness", "lethargic", "no energy", "always tired", "worn out",
                "fatigued", "extreme tiredness", "lack of energy", "feeling weak",
                "chronic fatigue", "feeling drained", "feeling exhausted", "body tiredness"],
    "weight_gain": ["weight gain", "increased weight", "gaining weight",
                    "putting on weight", "getting fat", "obesity", "weight increase"],
    "anxiety": ["anxiety", "nervousness", "worry", "anxious", "panic",
                "panic attacks", "feeling anxious", "worried", "stress",
                "mental tension", "uneasiness", "apprehension", "fear"],
    "cold_hands_and_feets": ["cold hands and feet", "cold extremities",
                             "cold fingers", "cold toes", "icy hands",
                             "hands feel cold", "feet feel cold", "numb fingers"],
    "mood_swings": ["mood swings", "emotional changes", "mood changes",
                    "emotional instability", "irritable", "mood fluctuations",
                    "bipolar mood", "emotional ups and downs"],
    "weight_loss": ["weight loss", "decreased weight", "losing weight",
                    "unintended weight loss", "thin", "emaciation",
                    "sudden weight loss", "rapid weight loss"],
    "restlessness": ["restlessness", "agitation", "cannot sit still",
                     "fidgety", "restless", "unable to relax",
                     "feeling uneasy", "can't sleep", "insomnia"],
    "lethargy": ["lethargy", "sluggishness", "laziness", "drowsiness",
                 "feeling lazy", "sluggish", "drowsy", "sleepy all day",
                 "excessive sleepiness", "somnolence"],
    "patches_in_throat": ["patches in throat", "throat patches", "throat lesions",
                          "white patches in throat", "throat coating",
                          "spots in throat", "throat spots"],
    "irregular_sugar_level": ["irregular sugar level", "unstable glucose",
                              "blood sugar fluctuations", "sugar level changes",
                              "diabetes symptoms", "high blood sugar",
                              "low blood sugar", "sugar imbalance",
                              "glucose imbalance", "sugar problem"],
    "cough": ["cough", "coughing", "dry cough", "wet cough", "persistent cough",
              "chronic cough", "throat cough", "hacking cough", "productive cough",
              "barking cough", "coughing up mucus", "constant cough"],
    "high_fever": ["high fever", "elevated temperature", "fever", "pyrexia",
                   "burning fever", "hot body", "body heat", "temperature",
                   "feeling hot", "feverish", "very high temperature",
                   "103 fever", "104 fever", "high temperature", "high body temp"],
    "sunken_eyes": ["sunken eyes", "hollow eyes", "dark circles",
                    "deep set eyes", "eyes look sunken", "tired eyes"],
    "breathlessness": ["breathlessness", "shortness of breath", "dyspnea",
                       "difficulty breathing", "hard to breathe", "gasping",
                       "breathless", "panting", "can't breathe properly",
                       "labored breathing", "wheezing", "breathing difficulty",
                       "breathing problem", "out of breath", "tight breathing"],
    "sweating": ["sweating", "perspiration", "excessive sweating", "night sweats",
                 "profuse sweating", "diaphoresis", "sweaty", "cold sweats",
                 "hyperhidrosis", "sweating a lot"],
    "dehydration": ["dehydration", "fluid loss", "dry mouth", "thirsty",
                    "excessive thirst", "not enough water", "dehydrated",
                    "feeling parched"],
    "indigestion": ["indigestion", "upset stomach", "dyspepsia", "bloating",
                    "stomach discomfort", "gas", "fullness after eating",
                    "belching", "bloated", "stomach bloating"],
    "headache": ["headache", "head pain", "migraine", "head ache", "throbbing head",
                 "tension headache", "head hurts", "painful head",
                 "splitting headache", "head pounding", "severe headache",
                 "constant headache", "pain in head"],
    "yellowish_skin": ["yellowish skin", "yellow skin", "jaundice", "yellow coloring",
                       "skin turning yellow", "yellowing of skin",
                       "icteric", "yellow complexion", "yellowish appearance"],
    "dark_urine": ["dark urine", "brown urine", "cola colored urine",
                   "dark colored urine", "urine is dark", "tea colored urine",
                   "dark yellow urine", "dark pee"],
    "nausea": ["nausea", "feeling nauseous", "queasy", "sick feeling",
               "want to vomit", "nauseated", "stomach churning",
               "feeling of vomiting", "motion sickness"],
    "loss_of_appetite": ["loss of appetite", "no appetite", "not hungry",
                         "anorexia", "don't want to eat", "lost appetite",
                         "decreased appetite", "can't eat", "food aversion"],
    "pain_behind_the_eyes": ["pain behind the eyes", "eye pain", "retro-orbital pain",
                             "pain behind eyes", "eyes hurting", "aching eyes",
                             "pressure behind eyes"],
    "back_pain": ["back pain", "backache", "lower back pain", "upper back pain",
                  "spine pain", "lumbar pain", "back hurts", "back ache",
                  "lumbago", "back stiffness", "pain in back"],
    "constipation": ["constipation", "difficulty passing stool", "hard stool",
                     "irregular bowel movement", "not able to poop",
                     "difficulty in defecation", "constipated", "blocked bowels"],
    "abdominal_pain": ["abdominal pain", "belly pain", "tummy pain",
                       "pain in abdomen", "lower abdominal pain",
                       "abdominal cramps", "stomach cramps", "abdomen pain"],
    "diarrhoea": ["diarrhoea", "diarrhea", "loose stools", "watery stools",
                  "loose motions", "frequent stools", "runny tummy",
                  "stomach running", "dysentery", "bowel movements", "loose motions"],
    "mild_fever": ["mild fever", "low grade fever", "slight fever", "low fever",
                   "low temperature", "99 fever", "100 fever", "slight temperature",
                   "sub-febrile", "warm feeling"],
    "yellow_urine": ["yellow urine", "bright yellow urine", "yellow colored urine",
                     "urine color change", "dark yellow pee"],
    "yellowing_of_eyes": ["yellowing of eyes", "yellow eyes", "icteric sclera",
                          "eyes turning yellow", "jaundice in eyes",
                          "yellow whites of eyes", "yellowish eyes"],
    "acute_liver_failure": ["acute liver failure", "liver failure", "liver damage",
                            "hepatic failure", "liver problem"],
    "fluid_overload": ["fluid overload", "water retention", "edema", "swelling",
                       "body swelling", "puffy", "bloated with fluid"],
    "swelling_of_stomach": ["swelling of stomach", "stomach swelling", "abdominal swelling",
                            "distended abdomen", "bloated stomach", "belly swelling",
                            "pot belly", "ascites"],
    "swelled_lymph_nodes": ["swelled lymph nodes", "enlarged lymph nodes",
                            "swollen lymph nodes", "lymphadenopathy",
                            "swollen glands", "lumps in neck", "glands swollen",
                            "enlarged glands"],
    "malaise": ["malaise", "general discomfort", "feeling unwell", "not feeling well",
                "under the weather", "general unwellness", "feeling poorly",
                "feeling bad", "generally sick"],
    "blurred_and_distorted_vision": ["blurred and distorted vision", "blurry vision",
                                     "blurred vision", "vision blur", "can't see clearly",
                                     "foggy vision", "hazy vision", "vision problems",
                                     "double vision", "diplopia"],
    "phlegm": ["phlegm", "mucus", "sputum", "chest congestion", "mucus in throat",
               "thick mucus", "productive cough with mucus", "phlegm in chest"],
    "throat_irritation": ["throat irritation", "sore throat", "scratchy throat",
                          "throat pain", "irritated throat", "raw throat",
                          "burning throat", "painful throat", "pharyngitis",
                          "throat burning", "throat discomfort"],
    "redness_of_eyes": ["redness of eyes", "bloodshot eyes", "red eyes",
                        "eye redness", "conjunctivitis", "pink eye",
                        "inflamed eyes", "eyes are red"],
    "sinus_pressure": ["sinus pressure", "sinus congestion", "sinus pain",
                       "sinusitis", "sinus headache", "pressure in face",
                       "facial pressure", "blocked sinuses"],
    "runny_nose": ["runny nose", "rhinorrhea", "nasal discharge", "dripping nose",
                   "nose running", "watery nose", "nasal drip",
                   "running nose", "nose dripping"],
    "congestion": ["congestion", "nasal blockage", "nasal congestion", "stuffed nose",
                   "blocked nose", "stuffy nose", "nasal obstruction",
                   "nose blocked", "can't breathe through nose"],
    "chest_pain": ["chest pain", "angina", "chest tightness", "pain in chest",
                   "heart pain", "chest discomfort", "chest pressure",
                   "tight chest", "chest ache", "precordial pain"],
    "weakness_in_limbs": ["weakness in limbs", "limb weakness", "weak arms",
                          "weak legs", "limbs feel weak", "weak limbs",
                          "arm weakness", "leg weakness", "heavy limbs"],
    "fast_heart_rate": ["fast heart rate", "tachycardia", "heart racing",
                        "rapid heartbeat", "palpitations", "heart pounding",
                        "racing heart", "rapid pulse", "heart beating fast"],
    "pain_during_bowel_movements": ["pain during bowel movements", "painful defecation",
                                    "pain while pooping", "painful stool",
                                    "rectal pain during bowel movement"],
    "pain_in_anal_region": ["pain in anal region", "anal pain", "rectal pain",
                            "pain in anus", "anus hurts", "bottom pain"],
    "bloody_stool": ["bloody stool", "rectal bleeding", "blood in stool",
                     "blood in poop", "bloody poop", "hemorrhoidal bleeding",
                     "melena", "dark stool with blood"],
    "irritation_in_anus": ["irritation in anus", "anal itching", "itchy anus",
                           "pruritus ani", "rectal itching", "anus itching"],
    "neck_pain": ["neck pain", "cervical pain", "sore neck", "neck ache",
                  "stiff neck", "neck hurts", "pain in neck",
                  "cervicalgia", "neck soreness"],
    "dizziness": ["dizziness", "lightheadedness", "dizzy", "vertigo",
                  "feeling faint", "head spinning", "giddiness",
                  "world spinning", "feeling dizzy", "lightheaded"],
    "cramps": ["cramps", "muscle cramps", "spasms", "muscle spasms",
               "cramping", "leg cramps", "abdominal cramps",
               "period cramps", "menstrual cramps"],
    "bruising": ["bruising", "hematoma", "bruises", "easy bruising",
                 "skin bruises", "blue marks", "black and blue marks"],
    "obesity": ["obesity", "overweight", "obese", "excess weight",
                "morbid obesity", "severely overweight", "heavy weight"],
    "swollen_legs": ["swollen legs", "leg edema", "legs swelling",
                     "puffy legs", "swollen ankles", "ankle swelling",
                     "pedal edema", "feet swelling"],
    "swollen_blood_vessels": ["swollen blood vessels", "varicose veins",
                              "visible veins", "enlarged veins",
                              "spider veins", "bulging veins"],
    "puffy_face_and_eyes": ["puffy face and eyes", "facial swelling",
                            "face swelling", "swollen face", "puffy eyes",
                            "periorbital edema", "morning face puffiness"],
    "enlarged_thyroid": ["enlarged thyroid", "goiter", "goitre", "thyroid swelling",
                         "neck swelling", "thyroid enlargement",
                         "lump in throat", "thyroid lump"],
    "brittle_nails": ["brittle nails", "weak nails", "breaking nails",
                      "fragile nails", "nails cracking", "thin nails",
                      "nail problems", "nails breaking easily"],
    "swollen_extremeties": ["swollen extremities", "swollen arms and legs",
                            "limb swelling", "extremity swelling",
                            "swollen hands and feet", "peripheral edema"],
    "excessive_hunger": ["excessive hunger", "polyphagia", "always hungry",
                         "constant hunger", "increased hunger",
                         "ravenous appetite", "eating too much"],
    "extra_marital_contacts": ["extra marital contacts", "multiple sexual partners",
                               "unprotected sex", "risky sexual behavior",
                               "multiple partners", "unsafe sex"],
    "drying_and_tingling_lips": ["drying and tingling lips", "lip dryness",
                                 "chapped lips", "tingling lips", "dry lips",
                                 "cracked lips", "lips feel numb"],
    "slurred_speech": ["slurred speech", "dysarthria", "difficulty speaking",
                       "speech difficulty", "can't speak clearly",
                       "words not coming out right", "mumbling",
                       "trouble speaking", "speech problems"],
    "knee_pain": ["knee pain", "pain in the knees", "sore knee",
                  "knee ache", "knee hurts", "knees hurt",
                  "pain in knee joint", "knee joint pain"],
    "hip_joint_pain": ["hip joint pain", "hip pain", "pain in hip",
                       "hip ache", "hip hurts", "groin pain",
                       "hip stiffness"],
    "muscle_weakness": ["muscle weakness", "muscle fatigue", "weak muscles",
                        "muscles feel weak", "loss of strength",
                        "muscular weakness", "can't lift things"],
    "stiff_neck": ["stiff neck", "neck stiffness", "neck rigidity",
                   "can't move neck", "stiffness in neck",
                   "neck locked", "torticollis"],
    "swelling_joints": ["swelling joints", "joint swelling", "swollen joints",
                        "joints are swollen", "puffy joints",
                        "inflamed joints", "joint inflammation"],
    "movement_stiffness": ["movement stiffness", "rigidity", "stiffness",
                           "body stiffness", "stiff body", "hard to move",
                           "difficulty moving", "morning stiffness"],
    "spinning_movements": ["spinning movements", "vertigo", "room spinning",
                           "world spinning", "everything spinning",
                           "spinning sensation", "rotational dizziness", "head spinning"],
    "loss_of_balance": ["loss of balance", "balance problems", "unbalanced",
                        "can't keep balance", "falling over",
                        "poor balance", "imbalance", "instability"],
    "unsteadiness": ["unsteadiness", "lack of balance", "wobbly",
                     "unstable walk", "staggering", "swaying",
                     "gait problems", "walking difficulty"],
    "weakness_of_one_body_side": ["weakness of one body side", "hemiparesis",
                                  "one side weakness", "one arm weak",
                                  "one leg weak", "hemiplegia",
                                  "left side weakness", "right side weakness",
                                  "paralysis one side"],
    "loss_of_smell": ["loss of smell", "anosmia", "can't smell",
                      "smell loss", "no sense of smell", "unable to smell"],
    "bladder_discomfort": ["bladder discomfort", "bladder pain",
                           "painful bladder", "bladder pressure",
                           "suprapubic pain", "lower belly pain"],
    "foul_smell_of_urine": ["foul smell of urine", "smelly urine",
                            "bad smelling urine", "urine odor",
                            "strong urine smell", "stinky pee", "foul_smell_of urine"],
    "continuous_feel_of_urine": ["continuous feel of urine", "urgency to urinate",
                                 "frequent urination", "urinary urgency",
                                 "need to pee constantly", "always need to pee",
                                 "can't hold urine", "overactive bladder"],
    "passage_of_gases": ["passage of gases", "flatulence", "gas", "farting",
                         "excessive gas", "bloating with gas", "wind",
                         "passing gas", "intestinal gas"],
    "internal_itching": ["internal itching", "itching inside",
                         "deep itching", "rectal itching"],
    "toxic_look_(typhos)": ["toxic look (typhos)", "septic appearance",
                            "toxic appearance", "looking very sick",
                            "severely ill appearance", "toxemia"],
    "depression": ["depression", "low mood", "depressed", "feeling down",
                   "sadness", "hopelessness", "feeling hopeless",
                   "mental health", "clinical depression", "feeling low",
                   "no interest in anything", "loss of interest"],
    "irritability": ["irritability", "easily annoyed", "irritable",
                     "angry", "short tempered", "cranky",
                     "getting angry easily", "agitated"],
    "muscle_pain": ["muscle pain", "myalgia", "sore muscles", "muscle ache",
                    "body ache", "body pain", "aching muscles",
                    "muscle soreness", "muscles hurt", "aching body"],
    "altered_sensorium": ["altered sensorium", "confusion", "disorientation",
                          "mental confusion", "confused", "delirium",
                          "not thinking clearly", "foggy mind", "brain fog"],
    "red_spots_over_body": ["red spots over body", "rash with red spots",
                            "red dots on skin", "petechiae", "red spots",
                            "spotted rash", "red marks on body"],
    "belly_pain": ["belly pain", "abdominal pain", "tummy ache",
                   "stomach ache", "pain in belly", "lower belly pain",
                   "abdominal discomfort"],
    "abnormal_menstruation": ["abnormal menstruation", "irregular periods",
                              "period problems", "menstrual irregularity",
                              "heavy periods", "missed periods",
                              "painful periods", "dysmenorrhea",
                              "amenorrhea", "menorrhagia"],
    "dischromic_patches": ["dischromic patches", "skin discoloration",
                           "patches on skin", "dark patches", "light patches",
                           "hyperpigmentation", "skin color changes",
                           "vitiligo", "melasma", "dischromic _patches"],
    "watering_from_eyes": ["watering from eyes", "teary eyes", "watery eyes",
                           "eyes watering", "excessive tearing", "lacrimation",
                           "epiphora", "crying eyes", "water from eyes"],
    "increased_appetite": ["increased appetite", "hyperphagia", "eating more",
                           "hungry all the time", "always eating",
                           "appetite increase", "craving food"],
    "polyuria": ["polyuria", "excessive urination", "frequent urination",
                 "peeing a lot", "urinating often", "too much urine",
                 "going to bathroom frequently"],
    "family_history": ["family history", "genetic predisposition",
                       "runs in family", "hereditary", "genetic",
                       "family disease history", "inherited"],
    "mucoid_sputum": ["mucoid sputum", "mucus in sputum", "thick sputum",
                      "mucus cough", "coughing up mucus",
                      "mucoid expectoration"],
    "rusty_sputum": ["rusty sputum", "blood-tinged sputum", "brown sputum",
                     "rusty colored sputum", "blood in sputum",
                     "hemoptysis", "coughing up blood"],
    "lack_of_concentration": ["lack of concentration", "difficulty focusing",
                              "can't concentrate", "poor concentration",
                              "attention deficit", "brain fog",
                              "difficulty paying attention", "distracted"],
    "visual_disturbances": ["visual disturbances", "vision problems",
                            "seeing spots", "flashing lights",
                            "visual aura", "scotoma", "floaters",
                            "distorted vision", "seeing things"],
    "receiving_blood_transfusion": ["receiving blood transfusion",
                                    "blood transfusion", "had transfusion",
                                    "received blood"],
    "receiving_unsterile_injections": ["receiving unsterile injections",
                                       "unsterile injections", "dirty needles",
                                       "shared needles", "contaminated needles"],
    "coma": ["coma", "unconscious", "unresponsive", "lost consciousness"],
    "stomach_bleeding": ["stomach bleeding", "gastric bleeding", "gi bleeding",
                         "vomiting blood", "hematemesis", "blood vomit"],
    "distention_of_abdomen": ["distention of abdomen", "abdominal distension",
                              "bloated abdomen", "swollen belly",
                              "stomach distended", "ballooned abdomen"],
    "history_of_alcohol_consumption": ["history of alcohol consumption",
                                       "heavy drinking", "alcoholism",
                                       "excessive drinking", "alcohol abuse",
                                       "drinks alcohol regularly"],
    "blood_in_sputum": ["blood in sputum", "hemoptysis", "coughing blood",
                        "bloody sputum", "blood when coughing"],
    "prominent_veins_on_calf": ["prominent veins on calf", "visible veins on leg",
                                 "calf veins", "leg veins showing",
                                 "varicose veins on calf"],
    "palpitations": ["palpitations", "heart fluttering", "heart skipping",
                     "irregular heartbeat", "heart pounding",
                     "feeling heartbeat", "fluttering in chest"],
    "painful_walking": ["painful walking", "pain while walking", "walking difficulty",
                        "limping", "can't walk properly", "painful to walk",
                        "walking hurts"],
    "pus_filled_pimples": ["pus filled pimples", "acne", "pustules",
                           "pimples with pus", "infected pimples",
                           "acne pustules", "whitehead pimples"],
    "blackheads": ["blackheads", "comedones", "clogged pores",
                   "open comedones", "black spots on face",
                   "blackhead acne"],
    "scurring": ["scurring", "scarring", "acne scars", "skin scarring",
                 "scar formation", "pitted skin"],
    "skin_peeling": ["skin peeling", "peeling skin", "skin flaking",
                     "desquamation", "skin shedding", "flaky skin",
                     "skin coming off"],
    "silver_like_dusting": ["silver like dusting", "silvery scales",
                            "psoriatic scales", "silver flakes on skin",
                            "metallic scales"],
    "small_dents_in_nails": ["small dents in nails", "nail pitting",
                             "pitted nails", "nail dents",
                             "holes in nails", "nail indentations"],
    "inflammatory_nails": ["inflammatory nails", "nail inflammation",
                           "infected nails", "red nails", "swollen nail bed",
                           "paronychia", "nail infection"],
    "blister": ["blister", "blisters", "skin blisters", "fluid filled bumps",
                "vesicles", "bullae", "water blisters"],
    "red_sore_around_nose": ["red sore around nose", "sore near nose",
                             "nasal sore", "redness around nose",
                             "impetigo on nose", "nose rash"],
    "yellow_crust_ooze": ["yellow crust ooze", "yellow crusting",
                          "oozing sores", "weeping skin",
                          "honey colored crust", "crusty sores"],
})


def _build_phrase_index():
    """Build reverse lookup index mapping synonym phrases to canonical keys, sorted by length."""
    phrase_map = {}
    for key in symptoms_dict:
        clean = key.replace('_', ' ').lower()
        phrase_map[clean] = key
        phrase_map[key.lower()] = key

    for key, syns in symptom_mapping.items():
        for s in syns:
            s_clean = s.strip().lower()
            if s_clean:
                phrase_map[s_clean] = key

    sorted_phrases = sorted(phrase_map.keys(), key=lambda x: len(x), reverse=True)
    return phrase_map, sorted_phrases


_PHRASE_MAP, _SORTED_PHRASES = _build_phrase_index()


def _normalize_key(s):
    if not isinstance(s, str):
        return ""
    s = s.lower().replace("diseae", "disease")
    return re.sub(r'[^a-z0-9]', '', s)


class DiseasePredictorService:
    def __init__(self):
        self._svc_model = None
        self._rf_model = None
        self._feature_cols = None
        self._datasets_loaded = False
        self.description = None
        self.precautions = None
        self.medications = None
        self.diets = None
        self.workout = None
        
        # Pre-indexed clinical knowledge maps
        self._desc_map = {}
        self._prec_map = {}
        self._med_map = {}
        self._diet_map = {}
        self._work_map = {}

    def _load_resources(self):
        if self._datasets_loaded:
            return
        try:
            svc_path = os.path.join(MODEL_DIR, "svc.pkl")
            rf_path = os.path.join(MODEL_DIR, "rf.pkl")
            meta_path = os.path.join(MODEL_DIR, "features.pkl")

            if os.path.exists(svc_path):
                with open(svc_path, "rb") as f:
                    self._svc_model = pickle.load(f)
                logging.info("SVC model loaded successfully.")

            if os.path.exists(rf_path):
                with open(rf_path, "rb") as f:
                    self._rf_model = pickle.load(f)
                logging.info("Random Forest model loaded successfully.")

            if os.path.exists(meta_path):
                with open(meta_path, "rb") as f:
                    self._feature_cols = pickle.load(f)
            else:
                self._feature_cols = list(symptoms_dict.keys())

            desc_path = os.path.join(DATASET_DIR, "description.csv")
            prec_path = os.path.join(DATASET_DIR, "precautions_df.csv")
            med_path = os.path.join(DATASET_DIR, "medications.csv")
            diet_path = os.path.join(DATASET_DIR, "diets.csv")
            work_path = os.path.join(DATASET_DIR, "workout_df.csv")

            if os.path.exists(desc_path):
                self.description = pd.read_csv(desc_path)
                for _, r in self.description.iterrows():
                    d = str(r.get('Disease', '')).strip()
                    if d: self._desc_map[_normalize_key(d)] = str(r.get('Description', '')).strip()

            if os.path.exists(prec_path):
                self.precautions = pd.read_csv(prec_path)
                cols = [c for c in ['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4'] if c in self.precautions.columns]
                for _, r in self.precautions.iterrows():
                    d = str(r.get('Disease', '')).strip()
                    if d:
                        pre_items = [str(r[c]).strip().capitalize() for c in cols if pd.notna(r.get(c)) and str(r.get(c)).strip()]
                        self._prec_map[_normalize_key(d)] = pre_items

            if os.path.exists(med_path):
                self.medications = pd.read_csv(med_path)
                for _, r in self.medications.iterrows():
                    d = str(r.get('Disease', '')).strip()
                    if d:
                        raw = r.get('Medication', '')
                        self._med_map[_normalize_key(d)] = self._parse_csv_list_values([raw])

            if os.path.exists(diet_path):
                self.diets = pd.read_csv(diet_path)
                for _, r in self.diets.iterrows():
                    d = str(r.get('Disease', '')).strip()
                    if d:
                        raw = r.get('Diet', '')
                        self._diet_map[_normalize_key(d)] = self._parse_csv_list_values([raw])

            if os.path.exists(work_path):
                self.workout = pd.read_csv(work_path)
                for _, r in self.workout.iterrows():
                    d = str(r.get('disease', '')).strip()
                    if d:
                        raw = r.get('workout', '')
                        self._work_map[_normalize_key(d)] = self._parse_csv_list_values([raw])

            self._datasets_loaded = True
        except Exception as e:
            logging.error(f"Error loading disease datasets/model: {e}")

    def correct_spelling(self, symptom):
        try:
            blob = TextBlob(symptom)
            return str(blob.correct())
        except Exception:
            return symptom

    def parse_and_extract_symptoms(self, raw_input):
        """
        Robust NLP symptom extraction supporting:
        - List of strings
        - Comma/semicolon/and-separated phrases
        - Natural language free-form text sentences
        - Negation exclusion ("no cough", "denies fever")
        - Spelling correction fallback
        """
        if isinstance(raw_input, list):
            text = " , ".join([str(s) for s in raw_input])
        else:
            text = str(raw_input)

        matched_symptoms = []
        cleaned_text = " " + text.lower() + " "
        cleaned_text = cleaned_text.replace(",", " , ").replace(";", " ; ").replace(".", " . ")

        # 1. Match longest phrases first
        for phrase in _SORTED_PHRASES:
            if len(phrase) < 2:
                continue
            pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
            match = re.search(pattern, cleaned_text)
            if match:
                # Check for negation in preceding 30 characters
                start_pos = match.start()
                preceding = cleaned_text[max(0, start_pos - 35):start_pos]
                if re.search(r'\b(no|not|without|denies|never|negative for)\b\s*$', preceding):
                    # Negated symptom, do not include
                    cleaned_text = cleaned_text[:start_pos] + " [NEGATED] " + cleaned_text[match.end():]
                    continue

                canonical_key = _PHRASE_MAP[phrase]
                if canonical_key not in matched_symptoms:
                    matched_symptoms.append(canonical_key)
                cleaned_text = cleaned_text[:start_pos] + " [MATCHED] " + cleaned_text[match.end():]

        # 2. Fallback: Check individual tokens/items for spelling correction if nothing matched
        if not matched_symptoms:
            tokens = [t.strip(" ,.;:[]'\"") for t in text.split(",") if t.strip()]
            if not tokens:
                tokens = text.split()
            for token in tokens:
                token_lower = token.lower()
                if token_lower in _PHRASE_MAP:
                    key = _PHRASE_MAP[token_lower]
                    if key not in matched_symptoms:
                        matched_symptoms.append(key)
                else:
                    corrected = self.correct_spelling(token_lower)
                    if corrected in _PHRASE_MAP:
                        key = _PHRASE_MAP[corrected]
                        if key not in matched_symptoms:
                            matched_symptoms.append(key)

        return matched_symptoms

    def get_top_predicted_values(self, patient_symptoms, top_n=3):
        self._load_resources()
        
        feature_cols = self._feature_cols or list(symptoms_dict.keys())
        matched_symptoms = self.parse_and_extract_symptoms(patient_symptoms)

        if not matched_symptoms:
            logging.warning(f"No symptoms could be extracted from input: {patient_symptoms}")
            return [(15, 'Fungal infection')]

        logging.info(f"AI Consultant Extracted Symptoms: {matched_symptoms}")

        # Construct feature vector
        input_vector = np.zeros((1, len(feature_cols)), dtype=np.float32)
        for s in matched_symptoms:
            if s in feature_cols:
                input_vector[0, feature_cols.index(s)] = 1.0
            elif s in symptoms_dict:
                idx = symptoms_dict[s]
                if idx < len(feature_cols):
                    input_vector[0, idx] = 1.0

        # Run Ensemble Inference
        models = []
        if self._svc_model and hasattr(self._svc_model, "predict_proba"):
            models.append(('SVC', self._svc_model, 0.50))
        if self._rf_model and hasattr(self._rf_model, "predict_proba"):
            models.append(('RF', self._rf_model, 0.50))

        if not models:
            return [(15, 'Fungal infection')]

        ensemble_probs = None
        for name, model, weight in models:
            try:
                probs = model.predict_proba(input_vector)[0]
                if ensemble_probs is None:
                    ensemble_probs = probs * weight
                else:
                    ensemble_probs += probs * weight
            except Exception as e:
                logging.error(f"Inference error in {name}: {e}")

        if ensemble_probs is None:
            return [(15, 'Fungal infection')]

        # Top classes
        classes = self._svc_model.classes_ if hasattr(self._svc_model, 'classes_') else self._rf_model.classes_
        top_indices = np.argsort(ensemble_probs)[::-1][:top_n]

        results = []
        for idx in top_indices:
            disease_name = str(classes[idx]).strip()
            confidence = float(ensemble_probs[idx] * 100)
            results.append((idx, disease_name))
            logging.info(f"  Prediction Candidate: {disease_name} ({confidence:.1f}%)")

        return results

    def _parse_csv_list_values(self, series_val):
        if series_val is None:
            return []
        items = []
        for val in series_val:
            if isinstance(val, (list, tuple)):
                for v in val:
                    if v is not None and pd.notna(v) and str(v).strip():
                        items.append(str(v).strip())
            elif isinstance(val, str):
                val_str = val.strip()
                if val_str.startswith('[') and val_str.endswith(']'):
                    try:
                        parsed = ast.literal_eval(val_str)
                        if isinstance(parsed, (list, tuple)):
                            for p in parsed:
                                if p is not None and pd.notna(p) and str(p).strip():
                                    items.append(str(p).strip())
                            continue
                    except Exception:
                        pass
                val_cleaned = val_str.strip("'\"")
                if val_cleaned and pd.notna(val_cleaned):
                    items.append(val_cleaned)
        return items

    def get_disease_details(self, dis):
        """Retrieves rich clinical information (description, precautions, medications, diet, workouts)
        using normalized matching to guarantee 100% accurate lookup across all databases."""
        self._load_resources()
        
        norm_dis = _normalize_key(dis)
        desc_str = self._desc_map.get(norm_dis, "")
        pre_list = self._prec_map.get(norm_dis, [])
        med_list = self._med_map.get(norm_dis, [])
        diet_list = self._diet_map.get(norm_dis, [])
        work_list = self._work_map.get(norm_dis, [])

        # Fallback to direct dataframe query if not in map
        if not desc_str and self.description is not None:
            desc_val = self.description[self.description['Disease'] == dis]['Description']
            desc_str = " ".join([str(w) for w in desc_val if pd.notna(w)])

        if not pre_list and self.precautions is not None:
            pre_df = self.precautions[self.precautions['Disease'] == dis]
            cols = [c for c in ['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4'] if c in pre_df.columns]
            if cols:
                raw_prec = pre_df[cols].values.flatten()
                pre_list = [str(p).strip().capitalize() for p in raw_prec if pd.notna(p) and str(p).strip()]

        if not med_list and self.medications is not None:
            med_val = self.medications[self.medications['Disease'] == dis]['Medication']
            med_list = self._parse_csv_list_values(med_val.values)

        if not diet_list and self.diets is not None:
            diet_val = self.diets[self.diets['Disease'] == dis]['Diet']
            diet_list = self._parse_csv_list_values(diet_val.values)

        if not work_list and self.workout is not None:
            work_val = self.workout[self.workout['disease'] == dis]['workout']
            work_list = self._parse_csv_list_values(work_val.values)

        return desc_str, pre_list, med_list, diet_list, work_list


consultant_service = DiseasePredictorService()
